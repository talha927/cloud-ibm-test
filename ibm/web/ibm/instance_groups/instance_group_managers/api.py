import logging

from apiflask import abort, APIBlueprint, input, output

from ibm.auth import authenticate
from ibm.common.req_resp_schemas.schemas import get_pagination_schema, PaginationQuerySchema, WorkflowRootOutSchema
from ibm.models import IBMInstanceGroup, IBMInstanceGroupManager, WorkflowRoot, WorkflowTask
from ibm.web import db as ibmdb
from ibm.web.common.utils import authorize_and_get_ibm_cloud, compose_ibm_resource_deletion_workflow, \
    create_ibm_resource_creation_workflow, \
    get_paginated_response_json, verify_references
from .schemas import IBMInstanceGroupManagerInSchema, IBMInstanceGroupManagerListQuerySchema, \
    IBMInstanceGroupManagerOutSchema, \
    IBMInstanceGroupManagerResourceSchema, IBMInstanceGroupManagerUpdateSchema

LOGGER = logging.getLogger(__name__)

ibm_instance_group_managers = APIBlueprint('ibm_instance_group_managers', __name__, tag="IBM Instance Groups")


@ibm_instance_group_managers.post('/instance_group_managers')
@authenticate
@input(IBMInstanceGroupManagerInSchema)
@output(WorkflowRootOutSchema, status_code=202)
def create_ibm_instance_group_manager(data, user):
    """
    Create IBM Instance Group Manager
    This request create an instance group manager on IBM Cloud
    """
    cloud_id = data["ibm_cloud"]["id"]

    authorize_and_get_ibm_cloud(cloud_id=cloud_id, user=user)

    verify_references(
        cloud_id=cloud_id, body_schema=IBMInstanceGroupManagerInSchema,
        resource_schema=IBMInstanceGroupManagerResourceSchema, data=data
    )

    workflow_root = create_ibm_resource_creation_workflow(
        user=user, resource_type=IBMInstanceGroupManager, data=data, validate=False
    )
    return workflow_root.to_json()


@ibm_instance_group_managers.get('/instance_group_managers/<manager_id>')
@authenticate
@output(IBMInstanceGroupManagerOutSchema)
def get_ibm_instance_group_manager(manager_id, user):
    """
    Get IBM Instance Group Manager
    This request will fetch Instance Group manager from IBM Cloud
    """

    instance_group_manager = ibmdb.session.query(IBMInstanceGroupManager).filter_by(id=manager_id).join(
        IBMInstanceGroup.ibm_cloud).filter_by(user_id=user["id"], project_id=user["project_id"], deleted=False).first()
    if not instance_group_manager:
        message = f"IBM Instance Group Manager {manager_id} does not exist"
        LOGGER.debug(message)
        abort(404, message)
    return instance_group_manager.to_json()


@ibm_instance_group_managers.get('/instance_group_managers')
@authenticate
@input(IBMInstanceGroupManagerListQuerySchema, location='query')
@input(PaginationQuerySchema, location='query')
@output(get_pagination_schema(IBMInstanceGroupManagerOutSchema))
def list_ibm_instance_group_managers(instance_group_manager_list_query_params, pagination_query_params, user):
    """
    List IBM Instance Group Managers
    This request fetches all instance group managers from IBM Cloud
    """
    cloud_id = instance_group_manager_list_query_params["cloud_id"]
    instance_group_id = instance_group_manager_list_query_params["instance_group_id"]

    authorize_and_get_ibm_cloud(cloud_id=cloud_id, user=user)

    instance_group = ibmdb.session.query(IBMInstanceGroup).filter_by(id=instance_group_id, cloud_id=cloud_id).first()
    if not instance_group:
        message = f"IBM Instance Group {instance_group_id} does not exist"
        LOGGER.debug(message)
        abort(404, message)

    instance_group_manager_query = ibmdb.session.query(IBMInstanceGroupManager).filter_by(
        instance_group_id=instance_group_id)

    instance_group_managers_page = instance_group_manager_query.paginate(
        page=pagination_query_params["page"], per_page=pagination_query_params["per_page"], error_out=False
    )
    if not instance_group_managers_page.items:
        return '', 204

    return get_paginated_response_json(
        items=[item.to_json() for item in instance_group_managers_page.items],
        pagination_obj=instance_group_managers_page
    )


@ibm_instance_group_managers.delete('/instance_group_managers/<manager_id>')
@authenticate
@output(WorkflowRootOutSchema, status_code=202)
def delete_ibm_instance_group_manager(manager_id, user):
    """
    Delete IBM Instance Group Manager
    This request deletes an IBM Instance Group Manager provided its ID.
    """
    instance_group_manager = ibmdb.session.query(IBMInstanceGroupManager).filter_by(id=manager_id).first()
    if not instance_group_manager:
        message = f"IBM Instance Group Manager {manager_id} does not exist"
        LOGGER.debug(message)
        abort(404, message)

    authorize_and_get_ibm_cloud(
        cloud_id=instance_group_manager.instance_group.ibm_cloud.id, user=user)

    return compose_ibm_resource_deletion_workflow(
        user=user, resource_type=IBMInstanceGroupManager, resource_id=manager_id
    ).to_json(metadata=True)


@ibm_instance_group_managers.patch('/instance_group_managers/<instance_group_manager_id>')
@authenticate
@input(IBMInstanceGroupManagerUpdateSchema)
@output(WorkflowRootOutSchema, status_code=202)
def update_ibm_instance_group_manager(instance_group_manager_id, data, user):
    """
    Update IBM Instance Group Manager
    """
    cloud_id = data["ibm_cloud"]["id"]

    authorize_and_get_ibm_cloud(cloud_id=cloud_id, user=user)

    instance_group_manager = ibmdb.session.query(IBMInstanceGroupManager).filter_by(id=instance_group_manager_id).join(
        IBMInstanceGroup.ibm_cloud).filter_by(user_id=user["id"], project_id=user["project_id"], deleted=False).first()
    if not instance_group_manager:
        message = f"IBM Instance Group Manager {instance_group_manager_id} does not exist"
        LOGGER.debug(message)
        abort(404, message)

    workflow_name = ' '.join([IBMInstanceGroupManager.__name__, instance_group_manager.name])

    workflow_root = WorkflowRoot(
        user_id=user["id"],
        project_id=user["project_id"],
        workflow_name=workflow_name,
        workflow_nature=WorkflowTask.TYPE_UPDATE
    )

    update_task = WorkflowTask(
        task_type=WorkflowTask.TYPE_UPDATE, resource_type=IBMInstanceGroupManager.__name__,
        resource_id=instance_group_manager.id,
        task_metadata={"resource_data": data}
    )
    workflow_root.add_next_task(update_task)
    ibmdb.session.add(workflow_root)
    ibmdb.session.commit()

    return workflow_root
