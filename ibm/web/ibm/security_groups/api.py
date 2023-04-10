import logging

from apiflask import abort, APIBlueprint, input, output
from ibm.auth import authenticate
from ibm.common.req_resp_schemas.schemas import get_pagination_schema, PaginationQuerySchema, WorkflowRootOutSchema
from ibm.common.utils import get_resource_by_name_or_id
from ibm.middleware import log_activity
from ibm.models import IBMEndpointGateway, IBMLoadBalancer, IBMNetworkInterface, IBMSecurityGroup, \
    IBMSecurityGroupRule, IBMVpcNetwork, WorkflowTask, IBMVpnGateway
from ibm.web import db as ibmdb
from ibm.web.common.utils import authorize_and_get_ibm_cloud, compose_ibm_resource_attachment_workflow, \
    compose_ibm_resource_deletion_workflow, compose_ibm_resource_detachment_workflow, \
    create_ibm_resource_creation_workflow, get_paginated_response_json, verify_and_get_region, verify_references
from .schemas import IBMSecurityGroupInSchema, IBMSecurityGroupOutSchema, IBMSecurityGroupResourceListQuerySchema, \
    IBMSecurityGroupResourceSchema, IBMSecurityGroupRuleInSchema, IBMSecurityGroupRuleOutSchema, \
    IBMSecurityGroupRuleResourceListQuerySchema, IBMSecurityGroupRuleResourceSchema, SecurityGroupTargetSchema, \
    UpdateIBMSecurityGroupRuleSchema, UpdateIBMSecurityGroupSchema

LOGGER = logging.getLogger(__name__)

ibm_security_groups = APIBlueprint('ibm_security_groups', __name__, tag="IBM Security Groups")


@ibm_security_groups.post('/security_groups')
@authenticate
@log_activity
@input(IBMSecurityGroupInSchema)
@output(WorkflowRootOutSchema, status_code=202)
def create_ibm_security_group(data, user):
    """
    Create IBM Security Groups
    This request creates an IBM Security Groups.
    """
    cloud_id = data["ibm_cloud"]["id"]
    region_id = data["region"]["id"]
    resource_json = data["resource_json"]

    ibm_cloud = authorize_and_get_ibm_cloud(cloud_id=cloud_id, user=user)
    verify_and_get_region(ibm_cloud=ibm_cloud, region_id=region_id)

    verify_references(
        cloud_id=cloud_id, body_schema=IBMSecurityGroupInSchema, resource_schema=IBMSecurityGroupResourceSchema,
        data=data
    )

    workflow_root = create_ibm_resource_creation_workflow(
        user=user, resource_type=IBMSecurityGroup, data=data, validate=False)

    if resource_json.get("target"):
        target = resource_json["target"]
        creation_task = workflow_root.next_tasks[0]
        task_metadata = {
            "security_group": {
                "name": resource_json["name"]
            },
            "region": data["region"]
        }

        for network_interface in target.get("network_interfaces", []):
            target, message = \
                get_resource_by_name_or_id(cloud_id, IBMNetworkInterface, ibmdb.session, network_interface)

            if message:
                LOGGER.info(message)
                continue

            task_metadata["network_interface"] = {"id": target.id}
            attachment_task = WorkflowTask(
                task_type=WorkflowTask.TYPE_ATTACH, resource_type=IBMSecurityGroup.__name__,
                task_metadata={"resource_data": task_metadata}
            )

            creation_task.add_next_task(attachment_task)
            ibmdb.session.commit()

        for load_balancer in target.get("load_balancers", []):
            target, message = get_resource_by_name_or_id(cloud_id, IBMLoadBalancer, ibmdb.session, load_balancer)

            if message:
                LOGGER.info(message)
                continue

            task_metadata["load_balancer"] = {"id": target.id}
            attachment_task = WorkflowTask(
                task_type=WorkflowTask.TYPE_ATTACH, resource_type=IBMSecurityGroup.__name__,
                task_metadata={"resource_data": task_metadata}
            )
            creation_task.add_next_task(attachment_task)
            ibmdb.session.commit()

        for endpoint_gateway in target.get("endpoint_gateways", []):
            target, message = \
                get_resource_by_name_or_id(cloud_id, IBMEndpointGateway, ibmdb.session, endpoint_gateway)

            if message:
                LOGGER.info(message)
                continue

            task_metadata["endpoint_gateway"] = {"id": target.id}
            attachment_task = WorkflowTask(
                task_type=WorkflowTask.TYPE_ATTACH, resource_type=IBMSecurityGroup.__name__,
                task_metadata={"resource_data": task_metadata}
            )
            creation_task.add_next_task(attachment_task)
            ibmdb.session.commit()

    return workflow_root.to_json()


@ibm_security_groups.get('/security_groups')
@authenticate
@input(PaginationQuerySchema, location='query')
@input(IBMSecurityGroupResourceListQuerySchema, location='query')
@output(get_pagination_schema(IBMSecurityGroupOutSchema))
def list_ibm_security_groups(pagination_query_params, vpc_res_query_params, user):
    """
    List IBM Security Groups
    This request lists all IBM Security Groups for the given cloud id.
    """
    cloud_id = vpc_res_query_params["cloud_id"]
    region_id = vpc_res_query_params.get("region_id")
    vpc_id = vpc_res_query_params.get("vpc_id")
    default = vpc_res_query_params.get("default")
    ibm_cloud = authorize_and_get_ibm_cloud(cloud_id=cloud_id, user=user)

    security_group_query = ibmdb.session.query(IBMSecurityGroup).filter_by(cloud_id=cloud_id)
    if region_id:
        verify_and_get_region(ibm_cloud=ibm_cloud, region_id=region_id)
        security_group_query = security_group_query.filter_by(region_id=region_id)

    if vpc_id:
        vpc = ibmdb.session.query(IBMVpcNetwork).filter_by(id=vpc_id).first()
        if not vpc:
            message = f"IBM VPC Network with id  {vpc_id} does not exist"
            LOGGER.debug(message)
            abort(404, message)

        security_group_query = security_group_query.filter_by(vpc_id=vpc_id)

    if default is not None:
        if default:
            security_group_query = security_group_query.filter_by(is_default=True)
        else:
            security_group_query = security_group_query.filter_by(is_default=False)

    security_group_page = security_group_query.paginate(
        page=pagination_query_params["page"], per_page=pagination_query_params["per_page"], error_out=False
    )
    if not security_group_page.items:
        return '', 204

    return get_paginated_response_json(
        items=[item.to_json() for item in security_group_page.items],
        pagination_obj=security_group_page
    )


@ibm_security_groups.get('/security_groups/<security_group_id>')
@authenticate
@output(IBMSecurityGroupOutSchema)
def get_ibm_security_group(security_group_id, user):
    """
    Get IBM Security Groups
    This request returns an IBM Security Groups provided its ID.
    """
    security_group = ibmdb.session.query(IBMSecurityGroup).filter_by(
        id=security_group_id
    ).join(IBMSecurityGroup.ibm_cloud).filter_by(
        user_id=user["id"], project_id=user["project_id"], deleted=False
    ).first()
    if not security_group:
        message = f"IBM Security Group {security_group_id} does not exist"
        LOGGER.debug(message)
        abort(404, message)

    return security_group.to_json()


@ibm_security_groups.patch('/security_groups/<security_group_id>')
@authenticate
@input(UpdateIBMSecurityGroupSchema)
@output(WorkflowRootOutSchema, status_code=202)
def update_ibm_security_group(security_group_id, data, user):
    """
    Update IBM Security Groups
    This request updates an IBM Security Groups
    """
    abort(404)


@ibm_security_groups.delete('/security_groups/<security_group_id>')
@authenticate
@log_activity
@output(WorkflowRootOutSchema, status_code=202)
def delete_ibm_security_group(security_group_id, user):
    """
    Delete IBM Security Groups
    This request deletes an IBM Security Groups provided its ID.
    """
    security_group: IBMSecurityGroup = ibmdb.session.query(IBMSecurityGroup).filter_by(id=security_group_id) \
        .join(IBMSecurityGroup.ibm_cloud) \
        .filter_by(user_id=user["id"], project_id=user["project_id"], deleted=False).first()
    if not security_group:
        message = f"IBM Security Group {security_group_id} does not exist"
        LOGGER.debug(message)
        abort(404, message)

    if security_group.is_default:
        message = f"Default Security Group {security_group_id} of the vpc {security_group.vpc_network.name} " \
                  f"cannot be deleted."
        LOGGER.debug(message)
        abort(409, message)

    if not security_group.is_deletable:
        message = "Before you delete a security group, make sure to detach all attached resources " \
                  "from the security group."
        LOGGER.debug(message)
        abort(409, message)

    return compose_ibm_resource_deletion_workflow(
        user=user, resource_type=IBMSecurityGroup, resource_id=security_group_id
    ).to_json(metadata=True)


@ibm_security_groups.post('/security_group_rules')
@authenticate
@input(IBMSecurityGroupRuleInSchema)
@output(WorkflowRootOutSchema, status_code=202)
def create_ibm_security_group_rule(data, user):
    """
    Create IBM Security Group Rule
    This request creates an IBM Security Group rule.
    """
    cloud_id = data["ibm_cloud"]["id"]
    authorize_and_get_ibm_cloud(cloud_id=cloud_id, user=user)

    verify_references(
        cloud_id=cloud_id, body_schema=IBMSecurityGroupRuleInSchema, resource_schema=IBMSecurityGroupRuleResourceSchema,
        data=data
    )

    workflow_root = create_ibm_resource_creation_workflow(
        user=user, resource_type=IBMSecurityGroupRule, data=data, validate=False
    )
    return workflow_root.to_json()


@ibm_security_groups.get('/security_group_rules')
@authenticate
@input(PaginationQuerySchema, location='query')
@input(IBMSecurityGroupRuleResourceListQuerySchema, location='query')
@output(get_pagination_schema(IBMSecurityGroupRuleOutSchema))
def list_ibm_security_group_rules(pagination_query_params, security_group_res_query_params, user):
    """
    List IBM Security Group Rule
    This request lists all IBM Security Group Rule for the given cloud id and security group.
    """
    cloud_id = security_group_res_query_params["cloud_id"]
    security_group_id = security_group_res_query_params["security_group_id"]
    authorize_and_get_ibm_cloud(cloud_id=cloud_id, user=user)

    security_group = ibmdb.session.query(IBMSecurityGroup).filter_by(
        id=security_group_id)
    if not security_group:
        message = f"IBM Security Group {security_group_id} does not exist"
        LOGGER.debug(message)
        abort(404, message)

    security_group_rule_query = ibmdb.session.query(IBMSecurityGroupRule).filter_by(
        security_group_id=security_group_id)

    security_group_rule_page = security_group_rule_query.paginate(
        page=pagination_query_params["page"], per_page=pagination_query_params["per_page"], error_out=False
    )
    if not security_group_rule_page.items:
        return '', 204

    return get_paginated_response_json(
        items=[item.to_json() for item in security_group_rule_page.items],
        pagination_obj=security_group_rule_page
    )


@ibm_security_groups.get('/security_group_rules/<security_group_rule_id>')
@authenticate
@output(IBMSecurityGroupRuleOutSchema)
def get_ibm_security_group_rule(security_group_rule_id, user):
    """
    Get IBM Security Group Rules
    This request returns an IBM Security Group Rule provided its ID.
    """
    security_group_rule = ibmdb.session.query(IBMSecurityGroupRule).filter_by(
        id=security_group_rule_id
    ).join(IBMSecurityGroup.ibm_cloud).filter_by(
        user_id=user["id"], project_id=user["project_id"], deleted=False
    ).first()
    if not security_group_rule:
        message = f"IBM Security Group Rule {security_group_rule_id} does not exist"
        LOGGER.debug(message)
        abort(404, message)

    return security_group_rule.to_json()


@ibm_security_groups.patch('/security_group_rules/<security_group_rule_id>')
@authenticate
@input(UpdateIBMSecurityGroupRuleSchema)
@output(WorkflowRootOutSchema, status_code=202)
def update_ibm_security_group_rule(security_group_rule_id, data, user):
    """
    Update IBM Security Group Rule
    This request updates an IBM Security Group rule
    """
    abort(404)


@ibm_security_groups.delete('/security_group_rules/<security_group_rule_id>')
@authenticate
@output(WorkflowRootOutSchema, status_code=202)
def delete_ibm_security_group_rule(security_group_rule_id, user):
    """
    Delete IBM Security Group Rule
    This request deletes an IBM Security Group rule provided its ID.
    """
    security_group_rule: IBMSecurityGroupRule = ibmdb.session.query(IBMSecurityGroupRule) \
        .filter_by(id=security_group_rule_id).first()
    if not security_group_rule:
        message = f"IBM Security Group Rule {security_group_rule_id} does not exist"
        LOGGER.debug(message)
        abort(404, message)

    authorize_and_get_ibm_cloud(cloud_id=security_group_rule.security_group.ibm_cloud.id, user=user)

    return compose_ibm_resource_deletion_workflow(
        user=user, resource_type=IBMSecurityGroupRule, resource_id=security_group_rule_id
    ).to_json(metadata=True)


@ibm_security_groups.put('/security_groups/<security_group_id>')
@authenticate
@input(SecurityGroupTargetSchema)
@output(WorkflowRootOutSchema, status_code=202)
def attach_ibm_security_group_target(security_group_id, target_data, user):
    """
    Attach IBM Security Group with Target (network interface, loadbalancer)
    """
    security_group: IBMSecurityGroup = ibmdb.session.query(IBMSecurityGroup) \
        .filter_by(id=security_group_id).first()
    if not security_group:
        message = f"IBM Security Group {security_group_id} does not exist"
        LOGGER.debug(message)
        abort(404, message)

    authorize_and_get_ibm_cloud(cloud_id=security_group.ibm_cloud.id, user=user)
    task_metadata = {
        "security_group": {
            "id": security_group.id
        },
        "region": {
            "id": security_group.region.id
        }
    }
    if target_data.get("network_interface"):
        target, message = get_resource_by_name_or_id(security_group.ibm_cloud.id, IBMNetworkInterface, ibmdb.session,
                                                     target_data["network_interface"])
        if message:
            LOGGER.info(message)
            abort(404, message)

        task_metadata["network_interface"] = target_data["network_interface"]
        workflow_root = compose_ibm_resource_attachment_workflow(
            user=user, resource_type=IBMSecurityGroup, resource_id=security_group_id,
            data=task_metadata
        )

    elif target_data.get("load_balancer"):
        target, message = get_resource_by_name_or_id(security_group.ibm_cloud.id, IBMNetworkInterface, ibmdb.session,
                                                     target_data["load_balancer"])
        if message:
            LOGGER.info(message)
            abort(404, message)

        task_metadata["load_balancer"] = target_data["load_balancer"]
        workflow_root = compose_ibm_resource_attachment_workflow(
            user=user, resource_type=IBMSecurityGroup, resource_id=security_group_id,
            data=task_metadata
        )

    return workflow_root.to_json()


@ibm_security_groups.delete('/security_groups/<security_group_id>')
@authenticate
@input(SecurityGroupTargetSchema)
@output(WorkflowRootOutSchema, status_code=202)
def remove_ibm_security_group_target(security_group_id, target_data, user):
    """
    Detach IBM Security Group with Target (network interface, loadbalancer)
    """
    security_group: IBMSecurityGroup = ibmdb.session.query(IBMSecurityGroup) \
        .filter_by(id=security_group_id).first()
    if not security_group:
        message = f"IBM Security Group {security_group_id} does not exist"
        LOGGER.debug(message)
        abort(404, message)

    authorize_and_get_ibm_cloud(cloud_id=security_group.ibm_cloud.id, user=user)
    task_metadata = {
        "security_group": {
            "id": security_group.id
        },
        "region": {
            "id": security_group.region.id
        }
    }
    if target_data.get("network_interface"):
        target, message = get_resource_by_name_or_id(security_group.ibm_cloud.id, IBMNetworkInterface, ibmdb.session,
                                                     target_data["network_interface"])
        if message:
            LOGGER.info(message)
            abort(404, message)

        task_metadata["network_interface"] = target_data["network_interface"]
        workflow_root = compose_ibm_resource_detachment_workflow(
            user=user, resource_type=IBMSecurityGroup, resource_id=security_group_id,
            data=task_metadata
        )

    elif target_data.get("load_balancer"):
        target, message = get_resource_by_name_or_id(security_group.ibm_cloud.id, IBMLoadBalancer, ibmdb.session,
                                                     target_data["load_balancer"])
        if message:
            LOGGER.info(message)
            abort(404, message)

        task_metadata["load_balancer"] = target_data["load_balancer"]
        workflow_root = compose_ibm_resource_detachment_workflow(
            user=user, resource_type=IBMSecurityGroup, resource_id=security_group_id,
            data=task_metadata
        )

    elif target_data.get("endpoint_gateway"):
        target, message = get_resource_by_name_or_id(security_group.ibm_cloud.id, IBMEndpointGateway, ibmdb.session,
                                                     target_data["endpoint_gateway"])
        if message:
            LOGGER.info(message)
            abort(404, message)

        task_metadata["endpoint_gateway"] = target_data["endpoint_gateway"]
        workflow_root = compose_ibm_resource_detachment_workflow(
            user=user, resource_type=IBMSecurityGroup, resource_id=security_group_id,
            data=task_metadata
        )

    elif target_data.get("vpn_server"):
        target, message = get_resource_by_name_or_id(security_group.ibm_cloud.id, IBMVpnGateway, ibmdb.session,
                                                     target_data["vpn_server"])
        if message:
            LOGGER.info(message)
            abort(404, message)

        task_metadata["vpn_server"] = target_data["vpn_server"]
        workflow_root = compose_ibm_resource_detachment_workflow(
            user=user, resource_type=IBMSecurityGroup, resource_id=security_group_id,
            data=task_metadata
        )

    return workflow_root.to_json()
