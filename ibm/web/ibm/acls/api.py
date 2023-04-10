import logging

from apiflask import abort, APIBlueprint, input, output

from ibm.auth import authenticate
from ibm.common.req_resp_schemas.schemas import get_pagination_schema, PaginationQuerySchema, WorkflowRootOutSchema
from ibm.common.utils import get_resource_by_name_or_id
from ibm.middleware import log_activity
from ibm.models import IBMNetworkAcl, IBMNetworkAclRule, IBMSubnet, IBMVpcNetwork, WorkflowTask
from ibm.web import db as ibmdb
from ibm.web.common.utils import authorize_and_get_ibm_cloud, compose_ibm_resource_deletion_workflow, \
    create_ibm_resource_creation_workflow, get_paginated_response_json, verify_and_get_region, verify_references
from .schemas import IBMAclInSchema, IBMAclListQuerySchema, IBMAclOutSchema, IBMAclResourceSchema, IBMAclRuleInSchema, \
    IBMAclRuleOutSchema, IBMAclRuleQuerySchema, IBMAclRuleResourceSchema, UpdateIBMAclRuleSchema, UpdateIBMAclSchema

LOGGER = logging.getLogger(__name__)

ibm_acls = APIBlueprint('ibm_acls', __name__, tag="Acls")


@ibm_acls.post('/network_acls')
@authenticate
@log_activity
@input(IBMAclInSchema)
@output(WorkflowRootOutSchema, status_code=202)
def create_ibm_acl(data, user):
    """
    Create an IBM Acl
    This request creates an IBM Acl.
    """

    cloud_id = data["ibm_cloud"]["id"]
    region_id = data["region"]["id"]
    resource_json = data["resource_json"]

    ibm_cloud = authorize_and_get_ibm_cloud(cloud_id=cloud_id, user=user)
    verify_and_get_region(ibm_cloud=ibm_cloud, region_id=region_id)

    verify_references(
        cloud_id=cloud_id, body_schema=IBMAclInSchema, resource_schema=IBMAclResourceSchema,
        data=data
    )

    subnets = resource_json.pop('subnets', [])

    workflow_root = create_ibm_resource_creation_workflow(
        user=user, resource_type=IBMNetworkAcl, data=data, validate=False
    )
    # if validation task then creation_task = workflow_root.next_tasks[1]
    creation_task = workflow_root.next_tasks[0]
    for subnet in subnets:
        subnet_obj, message = get_resource_by_name_or_id(cloud_id, IBMSubnet, ibmdb.session, subnet)
        if message:
            abort(404, message)

        attachment_task = WorkflowTask(
            task_type=WorkflowTask.TYPE_ATTACH, resource_type=f'{IBMSubnet.__name__}-{IBMNetworkAcl.__name__}',
            task_metadata={"resource_data": data, "subnet_id": subnet_obj.id}
        )

        creation_task.add_next_task(attachment_task)
    ibmdb.session.commit()

    return workflow_root.to_json()


@ibm_acls.get('/network_acls')
@authenticate
@input(IBMAclListQuerySchema, location='query')
@input(PaginationQuerySchema, location='query')
@output(get_pagination_schema(IBMAclOutSchema))
def list_ibm_acls(regional_res_query_params, pagination_query_params, user):
    """
    List IBM Acls
    This request lists all IBM Acls for the given cloud id.
    """
    cloud_id = regional_res_query_params["cloud_id"]
    region_id = regional_res_query_params.get("region_id")
    vpc_id = regional_res_query_params.get("vpc_id")
    is_default = regional_res_query_params.get("is_default")
    subnet_id = regional_res_query_params.get("subnet_id")

    ibm_cloud = authorize_and_get_ibm_cloud(cloud_id=cloud_id, user=user)
    network_acls_query = ibmdb.session.query(IBMNetworkAcl).filter_by(cloud_id=cloud_id)

    if region_id:
        verify_and_get_region(ibm_cloud=ibm_cloud, region_id=region_id)
        network_acls_query = network_acls_query.filter_by(region_id=region_id)

    if vpc_id:
        vpc = ibmdb.session.query(IBMVpcNetwork).filter_by(id=vpc_id).first()
        if not vpc:
            message = f"IBM VPC {vpc_id} does not exist"
            LOGGER.debug(message)
            abort(404, message)
            return

        network_acls_query = network_acls_query.filter_by(vpc_id=vpc_id)

    if is_default in [True, False]:
        network_acls_query = network_acls_query.filter_by(is_default=is_default)

    if subnet_id:
        subnet = ibmdb.session.query(IBMSubnet).filter_by(id=subnet_id).first()
        if not subnet:
            message = f"IBM Subnet {subnet_id} does not exist"
            LOGGER.debug(message)
            abort(404, message)
            return
        network_acls_query = network_acls_query.filter(IBMNetworkAcl.subnets.in_(subnet_id))

    network_acls_page = network_acls_query.paginate(
        page=pagination_query_params["page"], per_page=pagination_query_params["per_page"], error_out=False
    )
    if not network_acls_page.items:
        return '', 204

    return get_paginated_response_json(
        items=[item.to_json() for item in network_acls_page.items],
        pagination_obj=network_acls_page
    )


@ibm_acls.get('/network_acls/<network_acl_id>')
@authenticate
@output(IBMAclOutSchema)
def get_ibm_acl(network_acl_id, user):
    """
    Get IBM Acl
    This request returns an IBM Acl provided its ID.
    """
    acl = ibmdb.session.query(IBMNetworkAcl).filter_by(
        id=network_acl_id
    ).join(IBMNetworkAcl.ibm_cloud).filter_by(
        user_id=user["id"], project_id=user["project_id"], deleted=False
    ).first()
    if not acl:
        message = f"IBM Acl {network_acl_id} does not exist"
        LOGGER.debug(message)
        abort(404, message)

    return acl.to_json()


@ibm_acls.route('/network_acls/<network_acl_id>', methods=['PATCH'])
@authenticate
@input(UpdateIBMAclSchema)
@output(WorkflowRootOutSchema, status_code=202)
def update_ibm_acl(network_acl_id, data, user):
    """
    Update IBM Acl
    This request updates an IBM Acl
    """
    abort(404)


@ibm_acls.delete('/network_acls/<network_acl_id>')
@authenticate
@log_activity
@output(WorkflowRootOutSchema, status_code=202)
def delete_ibm_acl(network_acl_id, user):
    """
    Delete IBM VPC Acl
    This request deletes an IBM Acl provided its ID.
    """
    network_acl = ibmdb.session.query(IBMNetworkAcl).filter_by(
        id=network_acl_id
    ).join(IBMNetworkAcl.ibm_cloud).filter_by(
        user_id=user["id"], project_id=user["project_id"], deleted=False
    ).first()
    if not network_acl:
        message = f"IBM Network Acl {network_acl_id} does not exist"
        LOGGER.debug(message)
        abort(404, message)

    # TODO will add these checks when we have update api ready
    # if network_acl.is_default:
    #     message = f"You can not Delete a default Network Acl"
    #     LOGGER.debug(message)
    #     abort(405, message)
    # if not network_acl.is_deletable:
    #     message = f"Please attach this Acls subnet to another Acl before deleting this Acl"
    #     LOGGER.debug(message)
    #     abort(409, message)

    return compose_ibm_resource_deletion_workflow(
        user=user, resource_type=IBMNetworkAcl, resource_id=network_acl_id
    ).to_json(metadata=True)


@ibm_acls.post('/network_acl_rules')
@authenticate
@input(IBMAclRuleInSchema)
@output(WorkflowRootOutSchema, status_code=202)
def create_ibm_acl_rule(data, user):
    """
    Create an IBM Acl Rule
    This request creates an IBM Acl Rule.
    """
    cloud_id = data["ibm_cloud"]["id"]

    authorize_and_get_ibm_cloud(cloud_id=cloud_id, user=user)

    verify_references(
        cloud_id=cloud_id, body_schema=IBMAclRuleInSchema, resource_schema=IBMAclRuleResourceSchema,
        data=data
    )
    workflow_root = create_ibm_resource_creation_workflow(
        user=user, resource_type=IBMNetworkAclRule, data=data, validate=False
    )
    return workflow_root.to_json()


@ibm_acls.get('/network_acl_rules')
@authenticate
@input(IBMAclRuleQuerySchema, location='query')
@input(PaginationQuerySchema, location='query')
@output(get_pagination_schema(IBMAclRuleOutSchema))
def list_ibm_acl_rules(acl_rule_query_params, pagination_query_params, user):
    """
    List IBM Acl Rules
    This request lists all IBM Acl Rules for the given cloud id.
    """
    cloud_id = acl_rule_query_params["cloud_id"]
    acl_id = acl_rule_query_params["acl_id"]

    authorize_and_get_ibm_cloud(cloud_id=cloud_id, user=user)

    acl_query = ibmdb.session.query(IBMNetworkAcl).filter_by(id=acl_id, cloud_id=cloud_id)
    if not acl_query:
        message = f"IBM acl {acl_id} does not exist"
        LOGGER.debug(message)
        abort(404, message)

    network_acl_rules_query = ibmdb.session.query(IBMNetworkAclRule).filter_by(acl_id=acl_id)

    network_acl_rules_page = network_acl_rules_query.paginate(
        page=pagination_query_params["page"], per_page=pagination_query_params["per_page"], error_out=False
    )
    if not network_acl_rules_page.items:
        return '', 204

    return get_paginated_response_json(
        items=[item.to_json() for item in network_acl_rules_page.items],
        pagination_obj=network_acl_rules_page
    )


@ibm_acls.route('/network_acl_rules/<network_acl_rule_id>', methods=['GET'])
@authenticate
@output(IBMAclRuleOutSchema)
def get_ibm_acl_rule(network_acl_rule_id, user):
    """
    Get IBM Acl Rule
    This request returns an IBM Acl Rule provided its ID.
    """
    acl_rule = ibmdb.session.query(IBMNetworkAclRule).filter_by(
        id=network_acl_rule_id). \
        join(IBMNetworkAcl.ibm_cloud).filter_by(
        user_id=user["id"], project_id=user["project_id"], deleted=False).first()
    if not acl_rule:
        message = f"IBM Acl Rule {network_acl_rule_id} does not exist"
        LOGGER.debug(message)
        abort(404, message)

    return acl_rule.to_json()


@ibm_acls.route('/network_acl_rules/<network_acl_rule_id>', methods=["PATCH"])
@authenticate
@input(UpdateIBMAclRuleSchema)
@output(WorkflowRootOutSchema, status_code=202)
def update_ibm_acl_rule(network_acl_rule_id, user):
    """
    Update an IBM Acl Rule
    This request updates an IBM Acl Rule.
    """
    abort(404)


@ibm_acls.delete('/network_acl_rules/<network_acl_rule_id>')
@authenticate
@output(WorkflowRootOutSchema, status_code=202)
def delete_ibm_acl_rule(network_acl_rule_id, user):
    """
    Delete IBM VPC Acl Rule
    This request deletes an IBM Acl Rule provided its ID.
    """
    acl_rule = ibmdb.session.query(IBMNetworkAclRule).filter_by(
        id=network_acl_rule_id).first()
    if not acl_rule:
        message = f"IBM Network Acl Rule {network_acl_rule_id} does not exist"
        LOGGER.debug(message)
        abort(404, message)

    authorize_and_get_ibm_cloud(cloud_id=acl_rule.network_acl.ibm_cloud.id, user=user)
    return compose_ibm_resource_deletion_workflow(
        user=user, resource_type=IBMNetworkAclRule, resource_id=network_acl_rule_id
    ).to_json(metadata=True)
