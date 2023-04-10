import logging

from apiflask import abort, APIBlueprint, input, output

from ibm.auth import authenticate
from ibm.common.req_resp_schemas.schemas import get_pagination_schema, \
    PaginationQuerySchema, WorkflowRootOutSchema
from ibm.models import IBMInstanceGroupManager, IBMInstanceGroupManagerAction
from ibm.web import db as ibmdb
from ibm.web.common.utils import authorize_and_get_ibm_cloud, compose_ibm_resource_deletion_workflow, \
    create_ibm_resource_creation_workflow, \
    get_paginated_response_json, verify_references
from .schemas import IBMInstanceGroupManagerActionInSchema, IBMInstanceGroupManagerActionOutSchema, \
    IBMInstanceGroupManagerActionResourceSchema, IBMInstanceGroupManagerActionUpdateSchema
from ..schemas import IBMInstanceGroupListQuerySchema

LOGGER = logging.getLogger(__name__)
ibm_instance_group_manager_actions = APIBlueprint(
    'ibm_instance_group_manager_actions', __name__, tag="IBM Instance Groups")


@ibm_instance_group_manager_actions.post('/instance_group_manager_actions')
@authenticate
@input(IBMInstanceGroupManagerActionInSchema)
@output(WorkflowRootOutSchema, status_code=202)
def create_ibm_instance_group_manager_action(data, user):
    """
    Create IBM Instance Group Manager Action
    This request create an instance group manager action on IBM Cloud
    """
    cloud_id = data["ibm_cloud"]["id"]
    if data.get("resource_json", {}).get("run_at"):
        data["resource_json"]["run_at"] = str(data["resource_json"].get("run_at"))

    authorize_and_get_ibm_cloud(cloud_id=cloud_id, user=user)

    verify_references(
        cloud_id=cloud_id, body_schema=IBMInstanceGroupManagerActionInSchema,
        resource_schema=IBMInstanceGroupManagerActionResourceSchema, data=data
    )

    workflow_root = create_ibm_resource_creation_workflow(
        user=user, resource_type=IBMInstanceGroupManagerAction, data=data, validate=False
    )
    return workflow_root.to_json()


@ibm_instance_group_manager_actions.get('/instance_group_manager_actions/<action_id>')
@authenticate
@output(IBMInstanceGroupManagerActionOutSchema, status_code=200)
def get_ibm_instance_group_manager_action(action_id, user):
    """
    Get IBM Instance Group Manager Action
    This request will fetch Instance Group Manager Action from IBM Cloud
    """
    instance_group_manager_action = ibmdb.session.query(
        IBMInstanceGroupManagerAction).filter_by(id=action_id).first()
    if not instance_group_manager_action:
        message = f"IBM Instance Group Manager Action {action_id} does not exist"
        LOGGER.debug(message)
        abort(404, message)
    return instance_group_manager_action.to_json()


@ibm_instance_group_manager_actions.get('/instance_group_manager_actions')
@authenticate
@input(IBMInstanceGroupListQuerySchema, location='query')
@input(PaginationQuerySchema, location='query')
@output(get_pagination_schema(IBMInstanceGroupManagerActionOutSchema))
def list_ibm_instance_group_manager_actions(instance_group_list_query_params, pagination_query_params, user):
    """
    List Instance Group Manager Actions
    This request fetches all instance group manager actions from IBM Cloud
    """
    cloud_id = instance_group_list_query_params["cloud_id"]
    instance_group_manager_id = instance_group_list_query_params["instance_group_manager_id"]

    authorize_and_get_ibm_cloud(cloud_id=cloud_id, user=user)

    instance_group_manager = ibmdb.session.query(IBMInstanceGroupManager).filter_by(
        id=instance_group_manager_id).first()
    if not instance_group_manager:
        message = f"IBM Instance Group Manager {instance_group_manager_id} does not exist"
        LOGGER.debug(message)
        abort(404, message)

    instance_group_manager_action_query = ibmdb.session.query(IBMInstanceGroupManagerAction).filter_by(
        manager_id=instance_group_manager_id)

    instance_group_manager_actions_page = instance_group_manager_action_query.paginate(
        page=pagination_query_params["page"], per_page=pagination_query_params["per_page"], error_out=False
    )
    if not instance_group_manager_actions_page.items:
        return '', 204

    return get_paginated_response_json(
        items=[item.to_json() for item in instance_group_manager_actions_page.items],
        pagination_obj=instance_group_manager_actions_page
    )


@ibm_instance_group_manager_actions.patch('/instance_group_manager_actions/<action_id>')
@authenticate
@input(IBMInstanceGroupManagerActionUpdateSchema)
@output(WorkflowRootOutSchema, status_code=202)
def update_ibm_instance_group_manager_action(action_id, data, user):
    """
    Update IBM Instance Group Manager Action
    This request updates an Instance Group Manager action
    """
    abort(404)


@ibm_instance_group_manager_actions.delete('/instance_group_manager_actions/<action_id>')
@authenticate
@output(WorkflowRootOutSchema, status_code=202)
def delete_ibm_instance_group_manager_action(action_id, user):
    """
    Delete IBM Instance Group Manager Action
    This request deletes an IBM Instance Group Manager Action provided its ID.
    """
    instance_group_manager_action = ibmdb.session.query(
        IBMInstanceGroupManagerAction).filter_by(id=action_id).first()
    if not instance_group_manager_action:
        message = f"IBM Instance Group Manager Action {action_id} does not exist"
        LOGGER.debug(message)
        abort(404, message)

    authorize_and_get_ibm_cloud(
        cloud_id=instance_group_manager_action.instance_group_manager.instance_group.cloud_id, user=user)

    return compose_ibm_resource_deletion_workflow(
        user=user, resource_type=IBMInstanceGroupManagerAction, resource_id=action_id
    ).to_json(metadata=True)
