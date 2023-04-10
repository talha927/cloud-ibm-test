import logging

from apiflask import abort, APIBlueprint, doc, input, output

from ibm.auth import authenticate
from ibm.common.req_resp_schemas.schemas import get_pagination_schema, IBMRegionalResourceListQuerySchema, \
    PaginationQuerySchema, WorkflowRootOutSchema
from ibm.middleware import log_activity
from ibm.models import IBMPlacementGroup
from ibm.web import db as ibmdb
from ibm.web.common.utils import authorize_and_get_ibm_cloud, compose_ibm_resource_deletion_workflow, \
    create_ibm_resource_creation_workflow, get_paginated_response_json, verify_and_get_region, verify_references
from ibm.web.ibm.placement_groups.schemas import IBMPlacementGroupInSchema, IBMPlacementGroupOutSchema, \
    IBMPlacementGroupResourceSchema

LOGGER = logging.getLogger(__name__)

ibm_placement_groups = APIBlueprint('ibm_placement_groups', __name__, tag="IBM Placement Groups")


@ibm_placement_groups.post('/placement_groups')
@authenticate
@log_activity
@input(IBMPlacementGroupInSchema)
@output(WorkflowRootOutSchema, status_code=202)
def create_ibm_placement_group(data, user):
    """
    Create IBM Placement Group
    This request creates an IBM Placement Group.
    """
    cloud_id = data["ibm_cloud"]["id"]
    region_id = data["region"]["id"]

    ibm_cloud = authorize_and_get_ibm_cloud(cloud_id=cloud_id, user=user)
    verify_and_get_region(ibm_cloud=ibm_cloud, region_id=region_id)

    verify_references(
        cloud_id=cloud_id, body_schema=IBMPlacementGroupInSchema, resource_schema=IBMPlacementGroupResourceSchema,
        data=data
    )

    return create_ibm_resource_creation_workflow(
        user=user, resource_type=IBMPlacementGroup, data=data, validate=False
    ).to_json()


@ibm_placement_groups.get("/placement_groups")
@authenticate
@input(IBMRegionalResourceListQuerySchema, location="query")
@input(PaginationQuerySchema, location='query')
@output(get_pagination_schema(IBMPlacementGroupOutSchema))
@doc(
    responses={
        204: "No records found"
    }
)
def list_placement_groups(regional_res_query_params, pagination_query_params, user):
    """
    List IBM Placement Groups
    This request lists all IBM Placement Groups for the project of the authenticated user calling the API.
    """
    cloud_id = regional_res_query_params["cloud_id"]
    region_id = regional_res_query_params.get("region_id")

    ibm_cloud = authorize_and_get_ibm_cloud(cloud_id, user)
    filters = {
        "cloud_id": cloud_id
    }

    if region_id:
        verify_and_get_region(ibm_cloud, region_id)
        filters["region_id"] = region_id

    placement_groups_page = ibmdb.session.query(IBMPlacementGroup).filter_by(**filters).paginate(
        page=pagination_query_params["page"], per_page=pagination_query_params["per_page"], error_out=False
    )
    if not placement_groups_page:
        return "", 204

    return get_paginated_response_json(
        items=[item.to_json() for item in placement_groups_page.items],
        pagination_obj=placement_groups_page
    )


@ibm_placement_groups.get("/placement_groups/<placement_group_id>")
@authenticate
@output(IBMPlacementGroupOutSchema)
def get_placement_group(placement_group_id, user):
    """
    Get an IBM Placement Group
    This request returns an IBM Placement Group provided its ID.
    """
    placement_group = ibmdb.session.query(IBMPlacementGroup).filter_by(
        id=placement_group_id
    ).join(IBMPlacementGroup.ibm_cloud).filter_by(
        user_id=user["id"], project_id=user["project_id"], deleted=False
    ).first()
    if not placement_group:
        message = f"IBM Placement Group `{placement_group_id}` does not exist."
        LOGGER.debug(message)
        abort(404, message)

    return placement_group.to_json()


@ibm_placement_groups.delete("/placement_groups/<placement_group_id>")
@authenticate
@log_activity
@output(WorkflowRootOutSchema, status_code=202)
def delete_placement_group(placement_group_id, user):
    """
    Delete an IBM Placement Group on IBM Cloud
    This request deletes an IBM Placement Group provided its ID from IBM Cloud.
    """
    placement_group = ibmdb.session.query(IBMPlacementGroup).filter_by(
        id=placement_group_id
    ).join(IBMPlacementGroup.ibm_cloud).filter_by(
        user_id=user["id"], project_id=user["project_id"], deleted=False
    ).first()
    if not placement_group:
        message = f"IBM Placement Group `{placement_group_id}` does not exist."
        LOGGER.debug(message)
        abort(404, message)

    return compose_ibm_resource_deletion_workflow(
        user=user, resource_type=IBMPlacementGroup, resource_id=placement_group_id
    ).to_json(metadata=True)
