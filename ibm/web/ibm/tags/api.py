import logging

from apiflask import abort, APIBlueprint, input, output
from flask import request

from ibm.auth import authenticate, Response
from ibm.common.consts import MONTHS_STR_TO_INT
from ibm.common.req_resp_schemas.schemas import get_pagination_schema, PaginationQuerySchema, WorkflowRootOutSchema
from ibm.common.utils import get_month_interval
from ibm.models import IBMCostPerTag, IBMTag, WorkflowRoot, WorkflowTask
from ibm.web import db as ibmdb
from ibm.web.common.utils import authorize_and_get_ibm_cloud, compose_ibm_resource_deletion_workflow, \
    create_ibm_resource_creation_workflow, get_paginated_response_json
from .schemas import IBMTagInSchema, IBMTagOutSchema, IBMTagPerCostOutSchema
from ..costs.schemas import IBMCloudQuerySchema

LOGGER = logging.getLogger(__name__)
ibm_tags = APIBlueprint('ibm_tags', __name__, tag="IBM Tags")


@ibm_tags.post('/tags')
@authenticate
@input(IBMTagInSchema)
@output(WorkflowRootOutSchema, status_code=202)
def create_ibm_tag(data, user):
    """
    Create an IBM Tag
    This request registers an IBM Tag with VPC+.
    """
    cloud_id = data["ibm_cloud"]["id"]

    authorize_and_get_ibm_cloud(cloud_id=cloud_id, user=user)
    workflow_root = create_ibm_resource_creation_workflow(user=user, resource_type=IBMTag, data=data, validate=False)
    return workflow_root.to_json()


@ibm_tags.put('/tags/<tag_id>')
@authenticate
@input(IBMTagInSchema)
@output(WorkflowRootOutSchema, status_code=202)
def update_ibm_tag(tag_id, data, user):
    """
    Update an IBM Tag
    This request registers an IBM Tag with VPC+.
    """
    cloud_id = data["ibm_cloud"]["id"]

    authorize_and_get_ibm_cloud(cloud_id=cloud_id, user=user)

    workflow_name = IBMTag.__name__
    if data["resource_json"].get("name"):
        workflow_name = ' '.join([workflow_name, data["resource_json"]["name"]])

    workflow_root = WorkflowRoot(
        user_id=user["id"], project_id=user["project_id"], workflow_name=workflow_name, workflow_nature="CREATE",
        fe_request_data=data
    )
    deletion_task = WorkflowTask(
        task_type=WorkflowTask.TYPE_DELETE, resource_type=IBMTag.__name__, resource_id=tag_id,
        task_metadata={"resource_id": tag_id}
    )
    workflow_root.add_next_task(deletion_task)

    creation_task = WorkflowTask(
        task_type=WorkflowTask.TYPE_CREATE, resource_type=IBMTag.__name__, task_metadata={"resource_data": data}
    )
    deletion_task.add_next_task(creation_task)

    ibmdb.session.add(workflow_root)
    ibmdb.session.commit()

    return workflow_root.to_json()


@ibm_tags.get('/tags')
@authenticate
@input(IBMCloudQuerySchema, location='query')
@input(PaginationQuerySchema, location='query')
@output(get_pagination_schema(IBMTagOutSchema))
def list_ibm_tags(query_params, pagination_query_params, user):
    """
    List IBM Tags
    This request lists all IBM Tags for the project of the authenticated user calling the API.
    """
    cloud_id = query_params.get("cloud_id")
    authorize_and_get_ibm_cloud(cloud_id=cloud_id, user=user)
    tags_query = ibmdb.session.query(IBMTag).filter_by(cloud_id=cloud_id)
    tags_query = tags_query.filter(IBMTag.resource_id != "None")

    tags_page = tags_query.paginate(
        page=pagination_query_params["page"], per_page=pagination_query_params["per_page"], error_out=False)
    if not tags_page.items:
        return '', 204

    return get_paginated_response_json(
        items=[item.to_json() for item in tags_page.items],
        pagination_obj=tags_page
    )


@ibm_tags.get('/tags/<tag_id>')
@authenticate
@output(IBMTagOutSchema)
def get_ibm_tag(tag_id, user):
    """
    Get an IBM Tag
    This request returns an IBM Ssh Key provided its ID.
    """
    tag = ibmdb.session.query(IBMTag).filter_by(
        id=tag_id).join(IBMTag.ibm_cloud).filter_by(
        user_id=user["id"], project_id=user["project_id"], deleted=False).first()
    if not tag:
        message = f"IBM Tag {tag_id} does not exist"
        LOGGER.debug(message)
        abort(404, message)

    return tag.to_json()


@ibm_tags.delete('/tags/<tag_id>')
@authenticate
@output(WorkflowRootOutSchema, status_code=202)
def delete_ibm_tag(tag_id, user):
    """
    Delete an IBM Tag
    This request deletes an IBM Tag provided its ID.
    """
    ibm_tag = ibmdb.session.query(IBMTag).filter_by(
        id=tag_id).join(IBMTag.ibm_cloud).filter_by(
        user_id=user["id"], project_id=user["project_id"], deleted=False).first()
    if not ibm_tag:
        message = f"IBM Tag {ibm_tag} does not exist"
        LOGGER.debug(message)
        abort(404, message)

    return compose_ibm_resource_deletion_workflow(
        user=user, resource_type=IBMTag, resource_id=tag_id).to_json(metadata=True)


@ibm_tags.get('/cost_per_tags')
@authenticate
@input(IBMCloudQuerySchema, location='query')
@input(PaginationQuerySchema, location='query')
@output(get_pagination_schema(IBMTagPerCostOutSchema))
def list_ibm_cost_per_tags(query_params, pagination_query_params, user):
    """
    List IBM Cost Per Tags
    This request lists all IBM Cost Per Tags for the project of the authenticated user calling the API.
    """
    month = request.args.get('month')
    if month and month.lower() not in MONTHS_STR_TO_INT.keys():
        return Response(status=400)

    start, end = get_month_interval(month)
    cloud_id = query_params.get("cloud_id")
    authorize_and_get_ibm_cloud(cloud_id=cloud_id, user=user)
    tags_per_cost_query = ibmdb.session.query(IBMCostPerTag).filter_by(cloud_id=cloud_id, date=start)

    tags_per_cost_page = tags_per_cost_query.paginate(
        page=pagination_query_params["page"], per_page=pagination_query_params["per_page"], error_out=False)
    if not tags_per_cost_page.items:
        return '', 204

    return get_paginated_response_json(
        items=[item.to_json() for item in tags_per_cost_page.items],
        pagination_obj=tags_per_cost_page
    )
