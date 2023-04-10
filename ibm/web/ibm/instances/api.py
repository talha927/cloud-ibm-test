import logging

from apiflask import abort, APIBlueprint, input, output

from ibm.auth import authenticate
from ibm.middleware import log_activity, log_instance_activity
from ibm.common.consts import FAILED, SUCCESS
from ibm.common.req_resp_schemas.schemas import get_pagination_schema, PaginationQuerySchema, WorkflowRootOutSchema
from ibm.models import IBMInstance, IBMSubnet, IBMVpcNetwork, WorkflowRoot, WorkflowTask
from ibm.web import db as ibmdb
from ibm.web.common.utils import authorize_and_get_ibm_cloud, compose_ibm_resource_deletion_workflow, \
    get_paginated_response_json, verify_and_get_region, verify_and_get_zone, verify_references
from ibm.web.ibm.instances.schemas import IBMInstanceInSchema, IBMInstanceOutSchema, IBMInstanceResourceSchema, \
    IBMInstanceStatusQuerySchema, IBMInstanceUpdateSchema, IBMInstanceVolumeMigrationUpdateSchema, \
    IBMRightSizeInSchema, IBMRightSizeResourceSchema, IBMStartStopSchema
from .utils import create_ibm_instance_creation_workflow

LOGGER = logging.getLogger(__name__)

ibm_instances = APIBlueprint('ibm_instances', __name__, tag="IBM Instances")


@ibm_instances.post('/instances')
@authenticate
@log_activity
@input(IBMInstanceInSchema)
@output(WorkflowRootOutSchema, status_code=202)
def create_ibm_instance(data, user):
    """
    Create IBM Instance
    This request create an instance on IBM Cloud
    """
    cloud_id = data["ibm_cloud"]["id"]
    region_id = data["region"]["id"]

    ibm_cloud = authorize_and_get_ibm_cloud(cloud_id=cloud_id, user=user)
    verify_and_get_region(ibm_cloud=ibm_cloud, region_id=region_id)

    verify_references(
        cloud_id=cloud_id, body_schema=IBMInstanceInSchema, resource_schema=IBMInstanceResourceSchema, data=data
    )

    workflow_root = create_ibm_instance_creation_workflow(user=user, data=data)
    return workflow_root.to_json()


@ibm_instances.get('/instances/<instance_id>')
@authenticate
@output(IBMInstanceOutSchema, status_code=200)
def get_ibm_instance(instance_id, user):
    """
    Get IBM Instance
    This request will fetch Instances from IBM Cloud
    """
    instance = ibmdb.session.query(IBMInstance).filter_by(
        id=instance_id
    ).join(IBMInstance.ibm_cloud).filter_by(
        user_id=user["id"], project_id=user["project_id"], deleted=False
    ).first()
    if not instance:
        message = f"IBM Instance {instance_id} does not exist"
        LOGGER.debug(message)
        abort(404, message)
    return instance.to_json()


@ibm_instances.get('/instances')
@authenticate
@input(IBMInstanceStatusQuerySchema, location='query')
@input(PaginationQuerySchema, location='query')
@output(get_pagination_schema(IBMInstanceOutSchema))
def list_ibm_instances(regional_res_query_params, pagination_query_params, user):
    """
    List IBM Instances
    This request fetches all instances from IBM Cloud
    """
    cloud_id = regional_res_query_params["cloud_id"]
    region_id = regional_res_query_params.get("region_id")
    zone_id = regional_res_query_params.get("zone_id")
    vpc_id = regional_res_query_params.get("vpc_id")
    subnet_id = regional_res_query_params.get("subnet_id")
    ibm_status = regional_res_query_params.get("ibm_status")

    ibm_cloud = authorize_and_get_ibm_cloud(cloud_id=cloud_id, user=user)

    instances_query = ibmdb.session.query(IBMInstance).filter_by(cloud_id=cloud_id)

    if region_id:
        verify_and_get_region(ibm_cloud=ibm_cloud, region_id=region_id)
        instances_query = instances_query.filter_by(region_id=region_id)

    if zone_id:
        verify_and_get_zone(cloud_id=cloud_id, zone_id=zone_id)
        instances_query = instances_query.filter_by(zone_id=zone_id)

    if ibm_status:
        instances_query = instances_query.filter_by(status=ibm_status)

    if vpc_id:
        vpc = ibmdb.session.query(IBMVpcNetwork).filter_by(id=vpc_id).first()
        if not vpc:
            message = f"IBMVpcNetwork {vpc_id} does not exist"
            LOGGER.debug(message)
            abort(404, message)
        instances_query = instances_query.filter_by(vpc_id=vpc_id)

    if subnet_id:
        subnet = ibmdb.session.query(IBMSubnet).filter_by(id=subnet_id).first()
        if not subnet:
            message = f"IBMSubnet {subnet_id} does not exist"
            LOGGER.debug(message)
            abort(404, message)
        instances_query = instances_query.join(
            IBMInstance.network_interfaces
        ).filter_by(subnet_id=subnet_id)

    instances_page = instances_query.paginate(
        page=pagination_query_params["page"], per_page=pagination_query_params["per_page"], error_out=False
    )
    if not instances_page.items:
        return '', 204

    return get_paginated_response_json(
        items=[item.to_json() for item in instances_page.items],
        pagination_obj=instances_page
    )


@ibm_instances.patch('/instances/<instance_id>')
@authenticate
@input(IBMInstanceUpdateSchema)
@output(WorkflowRootOutSchema, status_code=202)
def update_ibm_instance(instance_id, data, user):
    """
    Update IBM Instance
    This request updates an Instance
    """
    abort(404)


@ibm_instances.delete('/instances/<instance_id>')
@authenticate
@log_activity
@output(WorkflowRootOutSchema, status_code=202)
def delete_ibm_instance(instance_id, user):
    """
    Delete IBM Instance
    This request deletes an IBM Instance provided its ID.
    """
    instance = ibmdb.session.query(IBMInstance).filter_by(
        id=instance_id
    ).join(IBMInstance.ibm_cloud).filter_by(
        user_id=user["id"], project_id=user["project_id"], deleted=False
    ).first()
    if not instance:
        message = f"IBM Instance {instance_id} does not exist"
        LOGGER.debug(message)
        abort(404, message)

    # TODO: Uncomment when we have update api call
    # if not instance.is_deletable:
    #     message = f"The instance {instance_id} has floating IP addresses. Unbind or release the floating IP addresses"
    #     LOGGER.debug(message)
    #     abort(404, message)

    return compose_ibm_resource_deletion_workflow(
        user=user, resource_type=IBMInstance, resource_id=instance_id
    ).to_json(metadata=True)


@ibm_instances.put("/clouds/<cloud_id>/regions/<region_id>/instances/<instance_name>/secondary-volume-migration/")
@input(IBMInstanceVolumeMigrationUpdateSchema)
def update_svm_report(cloud_id, region_id, instance_name, data):
    """
    Update secondary volume migration report
    """
    # from ibm.tasks.ibm.instance_tasks import delete_windows_resources
    ibm_instance = ibmdb.session.query(IBMInstance).filter_by(
        name=instance_name, region_id=region_id, cloud_id=cloud_id
    ).first()
    if not ibm_instance:
        message = f"IBM Instance {instance_name} does not exist"
        LOGGER.debug(message)
        abort(404, message)

    if ibm_instance.volume_migration_report and ibm_instance.volume_migration_report["status"] in [SUCCESS, FAILED]:
        message = f"Already volume migration completed for IBM Instance {data['instance_id']}."
        LOGGER.debug(message)
        abort(400, message)

    # TODO Revisit Volume migration resources deletion
    # if data["status"] in {SUCCESS, FAILED}:
    #     delete_windows_resources.delay(instance.id)
    #     task.status = data["status"]
    #     LOGGER.info(
    #         "Secondary Volume Migration for Windows is '{status}' for instance '{name}' and ID:'{instance_id}'
    #         ".format(
    #             status=task.status, name=instance.name, instance_id=instance.id
    #         )
    #     )

    ibm_instance.volume_migration_report = data
    ibmdb.session.commit()

    return '', 204


@ibm_instances.post('/clouds/<cloud_id>/instances/attribute')
@authenticate
@input(IBMRightSizeInSchema, location='json')
@output(WorkflowRootOutSchema, status_code=202)
def right_size_ibm_instance(cloud_id, data, user):
    """
    Right Size IBM Instance
    This request will Right Size an instance on IBM Cloud
    """
    region_id = data["region"]["id"]
    resource_json = data["resource_json"]
    instance_id = data["resource_json"]["instance_id"]

    ibm_cloud = authorize_and_get_ibm_cloud(cloud_id=cloud_id, user=user)
    verify_and_get_region(ibm_cloud=ibm_cloud, region_id=region_id)

    verify_references(
        cloud_id=cloud_id, body_schema=IBMRightSizeInSchema, resource_schema=IBMRightSizeResourceSchema,
        data=data
    )

    ibm_instance = ibmdb.session.query(IBMInstance).filter_by(
        id=instance_id, cloud_id=cloud_id, region_id=region_id
    ).first()
    if not ibm_instance:
        message = f"IBM Instance {instance_id} does not exist"
        LOGGER.debug(message)
        abort(404, message)

    workflow_root = WorkflowRoot(
        user_id=user['id'], workflow_name=IBMInstance.__name__, workflow_nature="UPDATE",
        project_id=user["project_id"])

    json_data = {
        "ibm_cloud": {"id": cloud_id},
        "region": {"id": region_id},
        "resource_json": resource_json
    }

    update_ibm_instance_task = WorkflowTask(
        task_type=WorkflowTask.TYPE_UPDATE, resource_type=IBMInstance.__name__,
        task_metadata={"resource_data": json_data}
    )

    instance_stop_task = WorkflowTask(
        resource_type=IBMInstance.__name__, task_type=WorkflowTask.TYPE_STOP, resource_id=ibm_instance.id)

    instance_start_task = WorkflowTask(
        resource_type=IBMInstance.__name__, task_type=WorkflowTask.TYPE_START, resource_id=ibm_instance.id)

    workflow_root.add_next_task(instance_stop_task)
    instance_stop_task.add_next_task(update_ibm_instance_task)
    update_ibm_instance_task.add_next_task(instance_start_task)

    ibmdb.session.add(workflow_root)
    ibmdb.session.commit()

    return workflow_root.to_json()


@ibm_instances.patch('/instances')
@authenticate
@log_instance_activity
@input(IBMStartStopSchema, location='json')
def update_ibm_instances(data, user):
    """
    Stop and start ibm instances.
    """
    cloud_id = data["ibm_cloud"]["id"]

    authorize_and_get_ibm_cloud(cloud_id=cloud_id, user=user)

    action = data['action'].upper()

    workflow_root = WorkflowRoot(
        user_id=user["id"],
        project_id=user["project_id"],
        workflow_name=IBMInstance.__name__,
        workflow_nature=action
    )

    instance_state = "running" if data["action"] == "stop" else "stopped"

    for instance_id in data["instance_ids"]:
        existing_instance = ibmdb.session.query(IBMInstance).filter_by(
            id=instance_id, cloud_id=cloud_id, status=instance_state).first()
        if not existing_instance:
            message = f"No IBM Instance found with ID {instance_id} or it is already in {action} state"
            LOGGER.debug(message)
            abort(404, message)

        task_type = WorkflowTask.TYPE_STOP if data['action'] == "stop" else WorkflowTask.TYPE_START

        workflow_task = WorkflowTask(
            resource_type=IBMInstance.__name__, task_type=task_type, resource_id=existing_instance.id)
        workflow_root.add_next_task(workflow_task)

    ibmdb.session.add(workflow_root)
    ibmdb.session.commit()
    return workflow_root.to_json()
