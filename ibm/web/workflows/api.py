import logging

from apiflask import abort, APIBlueprint, doc, input, output
from flask import Response

from config import PaginationConfig
from ibm.auth import authenticate, authenticate_api_key
from ibm.common.req_resp_schemas.schemas import get_pagination_schema, PaginationQuerySchema, WorkflowRootOutSchema
from ibm.models import IBMCloud, WorkflowRoot, WorkflowTask
from ibm.web import db as ibmdb
from ibm.web.common.utils import get_paginated_response_json
from ibm.web.workflows.utils import get_resource_json
from .schemas import WorkflowRootInfocusTasksOutOutSchema, WorkflowRootListQuerySchema, \
    WorkflowRootWithTasksOutSchema, WorkflowTaskOutSchema

LOGGER = logging.getLogger(__name__)

ibm_workflows = APIBlueprint('workflows', __name__, tag="Workflows")


@ibm_workflows.route('/workflows', methods=['GET'])
@authenticate
@input(PaginationQuerySchema, location='query')
@input(WorkflowRootListQuerySchema, location='query')
@output(get_pagination_schema(WorkflowRootOutSchema))
@doc(
    responses={
        204: "Successful - Empty Response because of empty list for the query"
    }
)
def list_workflows(pagination_query_params, workflow_query_params, user):
    """
    List all workflows
    This request lists all workflows for the project of the authenticated user calling the API.
    """
    page = pagination_query_params["page"]
    per_page = pagination_query_params["per_page"]

    workflow_roots_query = ibmdb.session.query(WorkflowRoot).filter_by(
        user_id=user["id"], project_id=user["project_id"], root_type=WorkflowRoot.ROOT_TYPE_NORMAL
    )

    if workflow_query_params["filter"]:
        statuses = workflow_query_params.get("statuses", [])
        status_list = list()
        for status in statuses:
            if status == "PENDING":
                status_list.extend(
                    [WorkflowRoot.STATUS_INITIATED, WorkflowRoot.STATUS_PENDING, WorkflowRoot.STATUS_RUNNING]
                )
            elif status == "COMPLETED_SUCCESSFULLY":
                status_list.append(WorkflowRoot.STATUS_C_SUCCESSFULLY)
            elif status == "COMPLETED_WITH_FAILURE":
                status_list.append(WorkflowRoot.STATUS_C_W_FAILURE)

        natures = workflow_query_params.get("natures", [])

        name_like = workflow_query_params.get("name_like")
        created_after = workflow_query_params.get("created_after")

        created_before = workflow_query_params.get("created_before")

        if status_list:
            workflow_roots_query = workflow_roots_query.filter(WorkflowRoot.status.in_(status_list))

        if natures:
            workflow_roots_query = workflow_roots_query.filter(WorkflowRoot.workflow_nature.in_(natures))

        if name_like:
            workflow_roots_query = \
                workflow_roots_query.filter(WorkflowRoot.workflow_name.like(f"%{name_like}%"))

        if created_after:
            workflow_roots_query = workflow_roots_query.filter(WorkflowRoot.created_at > created_after)

        if created_before:
            workflow_roots_query = workflow_roots_query.filter(WorkflowRoot.created_at < created_before)

    workflow_roots_query = workflow_roots_query.order_by(WorkflowRoot.created_at.desc())
    page_query_obj = workflow_roots_query.paginate(page, per_page, False, PaginationConfig.MAX_ITEMS_PER_PAGE)

    if not page_query_obj.items:
        return Response(status=204)

    return get_paginated_response_json(
        items=[item.to_json(metadata=True) for item in page_query_obj.items],
        pagination_obj=page_query_obj
    )


@ibm_workflows.route('/workflows/<root_id>', methods=['GET'])
@authenticate
@output(WorkflowRootWithTasksOutSchema)
def get_workflow(root_id, user):
    """
    Get a workflow by ID
    """
    workflow_root = ibmdb.session.query(WorkflowRoot).filter_by(
        id=root_id, user_id=user["id"], project_id=user["project_id"], root_type=WorkflowRoot.ROOT_TYPE_NORMAL
    ).first()
    if not workflow_root:
        LOGGER.info(f"No WorkflowRoot task exists with this ID {root_id}")
        abort(404)

    resp = workflow_root.to_json()
    resp["resource_json"] = get_resource_json(workflow_root=workflow_root)
    if workflow_root.workflow_nature == WorkflowTask.TYPE_SYNC and not resp["resource_json"]:
        resp["resource_json"] = {
            "result": [task["result"]["resource_json"] for task in resp[
                WorkflowRoot.ASSOCIATED_TASKS_KEY] if task["result"] and task["result"].get("resource_json")]
        }
    if resp.get('status') == WorkflowRoot.STATUS_C_W_FAILURE and resp.get('associated_tasks'):
        for task in resp.get('associated_tasks'):
            if task.get('status') == WorkflowTask.STATUS_FAILED and task.get('message'):
                if "Operation failed, Error-Code: 409, Error message: \nCannot delete the subnet while it is in use " \
                   "by one or more instances." in task.get('message'):
                    resp["message"] = "Some resources are deleted and some are pending due to load balancer is not" \
                                      " in stable state. Please try again after 15 (ten) minutes"

    return resp


@ibm_workflows.route('/workflows/<root_id>/in-focus', methods=['GET'])
@authenticate
@output(WorkflowRootInfocusTasksOutOutSchema)
def list_in_focus_tasks(root_id, user):
    """
    List all in_focus task for a WorkflowRoot
    """
    workflow_root = ibmdb.session.query(WorkflowRoot).filter_by(
        id=root_id, user_id=user["id"], project_id=user["project_id"], root_type=WorkflowRoot.ROOT_TYPE_NORMAL
    ).first()
    if not workflow_root:
        LOGGER.info(f"No WorkflowRoot task exists with this ID {root_id}")
        abort(404)

    resp = workflow_root.to_json()
    resp["in_focus_tasks"] = [task.to_json() for task in workflow_root.in_focus_tasks],
    return resp


@ibm_workflows.route('/workflows/<root_id>/tasks/<task_id>', methods=['GET'])
@authenticate
@output(WorkflowTaskOutSchema)
def get_workflow_task(root_id, task_id, user):
    """
    Get WorkflowTask provided root_id and task_id
    """
    workflow_task = ibmdb.session.query(WorkflowTask).filter_by(id=task_id, root_id=root_id).first()
    if not workflow_task or (workflow_task.root.user_id != user["id"]) or \
            (workflow_task.root.project_id != user["project_id"]) or \
            workflow_task.root.root_type != WorkflowRoot.ROOT_TYPE_NORMAL:
        LOGGER.info(f"No WorkflowTask task exists with this ID {task_id}")
        return abort(404)

    return workflow_task.to_json()


@ibm_workflows.route('/workflows/<root_id>/clouds/<cloud_id>', methods=['GET'])
@authenticate_api_key
@output(WorkflowRootWithTasksOutSchema)
def get_workflow_by_api_key(root_id, cloud_id):
    """
    This API is only created for db migration because they want authentication with api key instead of token
    Get a workflow by ID and cloud id
    """
    ibm_cloud = ibmdb.session.query(IBMCloud).filter_by(id=cloud_id).first()
    if not ibm_cloud:
        LOGGER.info(f"No IBM Cloud found with id {cloud_id}")
        return

    project_id = ibm_cloud.project_id
    user_id = ibm_cloud.user_id

    workflow_root = ibmdb.session.query(WorkflowRoot).filter_by(
        id=root_id, user_id=user_id, project_id=project_id, root_type=WorkflowRoot.ROOT_TYPE_NORMAL
    ).first()
    if not workflow_root:
        LOGGER.info(f"No WorkflowRoot task exists with this ID {root_id}")
        abort(404)

    resp = workflow_root.to_json()
    resp["resource_json"] = get_resource_json(workflow_root=workflow_root)
    if workflow_root.workflow_nature == WorkflowTask.TYPE_SYNC and not resp["resource_json"]:
        resp["resource_json"] = {
            "result": [task["result"]["resource_json"] for task in resp[
                WorkflowRoot.ASSOCIATED_TASKS_KEY] if task["result"] and task["result"].get("resource_json")]
        }
    if resp.get('status') == WorkflowRoot.STATUS_C_W_FAILURE and resp.get('associated_tasks'):
        for task in resp.get('associated_tasks'):
            if task.get('status') == WorkflowTask.STATUS_FAILED and task.get('message'):
                if "Operation failed, Error-Code: 409, Error message: \nCannot delete the subnet while it is in use " \
                   "by one or more instances." in task.get('message'):
                    resp["message"] = "Some resources are deleted and some are pending due to load balancer is not" \
                                      " in stable state. Please try again after 15 (ten) minutes"

    return resp
