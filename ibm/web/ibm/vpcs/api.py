from apiflask import abort, APIBlueprint, doc, input, output
from ibm import LOGGER
from ibm.auth import authenticate
from ibm.common.req_resp_schemas.schemas import get_pagination_schema, IBMRegionalResourceListQuerySchema, \
    IBMResourceQuerySchema, PaginationQuerySchema, WorkflowRootOutSchema
from ibm.middleware import log_activity
from ibm.models import IBMInstance, IBMTag, IBMVpcNetwork, WorkflowRoot, WorkflowTask
from ibm.web import db as ibmdb
from ibm.web.common.utils import authorize_and_get_ibm_cloud, compose_ibm_vpc_deletion_workflow, \
    create_ibm_resource_creation_workflow, get_paginated_response_json, verify_and_get_region, verify_references
from .schemas import IBMVpcActionInSchema, IBMVpcNetworkInSchema, IBMVpcNetworkOutSchema, \
    IBMVpcNetworkResourceSchema, IBMVpcNetworkSearchSchema

ibm_vpc_networks = APIBlueprint('ibm_vpc_networks', __name__, tag="IBM VPC Networks")


@ibm_vpc_networks.route('/vpcs', methods=['POST'])
@authenticate
@log_activity
@input(IBMVpcNetworkInSchema)
@output(WorkflowRootOutSchema, status_code=202)
def create_vpc(data, user):
    """
    Create IBM VPC Network
    This request creates an IBM VPC Network.
    """
    cloud_id = data["ibm_cloud"]["id"]
    region_id = data["region"]["id"]

    ibm_cloud = authorize_and_get_ibm_cloud(cloud_id=cloud_id, user=user)
    verify_and_get_region(ibm_cloud=ibm_cloud, region_id=region_id)

    verify_references(
        cloud_id=cloud_id, body_schema=IBMVpcNetworkInSchema, resource_schema=IBMVpcNetworkResourceSchema, data=data
    )

    workflow_root = create_ibm_resource_creation_workflow(
        user=user, resource_type=IBMVpcNetwork, data=data, validate=False
    )

    return workflow_root.to_json()


@ibm_vpc_networks.route('/vpcs', methods=['GET'])
@authenticate
@input(IBMRegionalResourceListQuerySchema, location='query')
@input(PaginationQuerySchema, location='query')
@input(IBMVpcNetworkSearchSchema, location='query')
@output(get_pagination_schema(IBMVpcNetworkOutSchema))
@doc(
    responses={
        204: "No records found"
    }
)
def list_vpcs(regional_res_query_params, pagination_query_params, search_query_params, user):
    """
    List IBM VPC Networks
    This request lists all IBM VPC Networks for the project of the authenticated user calling the API.
    """
    cloud_id = regional_res_query_params["cloud_id"]
    region_id = regional_res_query_params.get("region_id")

    ibm_cloud = authorize_and_get_ibm_cloud(cloud_id=cloud_id, user=user)

    region = None
    if region_id:
        region = ibm_cloud.regions.filter_by(id=region_id).first()
        if not region:
            message = f"IBM Region {region_id} does not exist"
            LOGGER.error(message)
            abort(404, message)

    vpc_networks_query = ibmdb.session.query(IBMVpcNetwork).filter_by(cloud_id=cloud_id)
    if region:
        vpc_networks_query = vpc_networks_query.filter_by(region_id=region_id)

    if search_query_params.get('untag_vpc') in [True, "True", "TRUE", "true", "1", 1]:
        tags = ibmdb.session.query(IBMTag).filter_by(cloud_id=cloud_id, resource_type='vpc').filter(
            IBMTag.name.contains('purpose:')).all()
        resource_ids = [tag.resource_id for tag in tags]
        vpc_networks_query = vpc_networks_query.filter((IBMVpcNetwork.id.not_in(resource_ids))).filter_by(
            cloud_id=cloud_id)

    vpc_networks_page = vpc_networks_query.paginate(
        page=pagination_query_params["page"], per_page=pagination_query_params["per_page"], error_out=False
    )
    if not vpc_networks_page.items:
        return '', 204

    return get_paginated_response_json(
        items=[item.to_json(session=ibmdb.session) for item in vpc_networks_page.items],
        pagination_obj=vpc_networks_page
    )


@ibm_vpc_networks.route('/vpcs/<vpc_id>', methods=['GET'])
@authenticate
@output(IBMVpcNetworkOutSchema)
def get_vpc(vpc_id, user):
    """
    Get IBM VPC Network
    This request returns an IBM VPC Network provided its ID.
    """
    vpc_network = ibmdb.session.query(IBMVpcNetwork).filter_by(
        id=vpc_id
    ).join(IBMVpcNetwork.ibm_cloud).filter_by(
        user_id=user["id"], project_id=user["project_id"], deleted=False
    ).first()
    if not vpc_network:
        message = f"IBM VPC Network {vpc_id} does not exist"
        LOGGER.error(message)
        abort(404, message)
    return vpc_network.to_json(session=ibmdb.session)


@ibm_vpc_networks.route('/vpcs/<vpc_id>', methods=['PATCH'])
@authenticate
@input(IBMVpcNetworkResourceSchema(only=("name",)))
@output(WorkflowRootOutSchema, status_code=202)
def update_vpc(vpc_id, data, user):
    """
    Update IBM Cloud
    This request updates an IBM Cloud
    """
    abort(404)


@ibm_vpc_networks.delete('/vpcs/<vpc_id>')
@authenticate
@log_activity
@output(WorkflowRootOutSchema, status_code=202)
def delete_vpc(vpc_id, user):
    """
    Delete IBM VPC Networks and its related Resources
    This request deletes an IBM VPC Network provided its ID and all its resources.
    """
    vpc = ibmdb.session.query(IBMVpcNetwork).filter_by(
        id=vpc_id
    ).join(IBMVpcNetwork.ibm_cloud).filter_by(
        user_id=user["id"], project_id=user["project_id"], deleted=False
    ).first()

    if not vpc:
        message = f"IBM Vpc {vpc_id} does not exist"
        LOGGER.error(message)
        abort(404, message)

    return compose_ibm_vpc_deletion_workflow(
        user=user, resource_type=IBMVpcNetwork, resource_id=vpc_id
    ).to_json(metadata=True)


@ibm_vpc_networks.post('/vpcs/action')
@authenticate
@input(IBMResourceQuerySchema, location='query')
@input(IBMVpcActionInSchema)
@output(WorkflowRootOutSchema, status_code=202)
def update_vpc_action(cloud_query_schema, data, user):
    """
    Pause a vpc or a list of vpcs based on their ids or tags.
    """

    cloud_id = cloud_query_schema["cloud_id"]
    authorize_and_get_ibm_cloud(cloud_id=cloud_id, user=user)
    vpc_set = set()
    for vpc_id in data.get("vpc_ids", []):
        vpc = ibmdb.session.query(IBMVpcNetwork).filter_by(
            id=vpc_id
        ).join(IBMVpcNetwork.ibm_cloud).filter_by(
            user_id=user["id"], project_id=user["project_id"], deleted=False).first()

        if not vpc:
            message = f"IBM VPC Network with ID {vpc_id} does not exist"
            LOGGER.error(message)
            abort(404, message)

        vpc_set.add(vpc)

    for tag in data.get("tags", []):
        ibm_tag = ibmdb.session.query(IBMTag).filter_by(
            name=tag["tag_name"], region_id=tag["region_id"], cloud_id=cloud_id).first()
        if not ibm_tag:
            message = f"The Tag with name {tag['tag_name']} does not exist in DB"
            LOGGER.error(message)
            abort(404, message)

        vpc = ibmdb.session.query(IBMVpcNetwork).filter_by(id=ibm_tag.resource_id, cloud_id=cloud_id).first()
        if not vpc:
            message = f"IBM Vpc with ID {ibm_tag.resource_id} not found in DB"
            LOGGER.error(message)
            abort(404, message)

        vpc_set.add(vpc)

    workflow_root = WorkflowRoot(
        user_id=user['id'], workflow_name=IBMVpcNetwork.__name__, workflow_nature="START/STOP",
        project_id=user["project_id"])

    instance_state = "running" if data["action"] == "stop" else "stopped"
    task_type = WorkflowTask.TYPE_STOP if data["action"] == "stop" else WorkflowTask.TYPE_START
    instance_ids = set()
    for vpc in vpc_set:
        instances = vpc.instances.filter_by(status=instance_state).all()
        for instance in instances:
            instance_ids.add(instance.id)
            instance_state_task = WorkflowTask(
                resource_type=IBMInstance.__name__, task_type=task_type, resource_id=instance.id)
            workflow_root.add_next_task(instance_state_task)

    for instance_id in data.get("instance_ids", []):
        instance = ibmdb.session.query(IBMInstance).filter_by(
            id=instance_id, cloud_id=cloud_id, status=instance_state).first()
        if not instance:
            continue

        if instance.id in instance_ids:
            continue

        instance_state_task = WorkflowTask(
            resource_type=IBMInstance.__name__, task_type=task_type, resource_id=instance.id)
        workflow_root.add_next_task(instance_state_task)

    ibmdb.session.add(workflow_root)
    ibmdb.session.commit()
    return workflow_root.to_json()
