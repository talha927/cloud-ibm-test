import logging

from apiflask import abort, APIBlueprint, input, output

from ibm.auth import authenticate
from ibm.common.req_resp_schemas.schemas import get_pagination_schema, IBMDedicatedHostGroupListQuerySchema, \
    PaginationQuerySchema, WorkflowRootOutSchema
from ibm.middleware import log_activity
from ibm.models import IBMDedicatedHostGroup, IBMDedicatedHostProfile
from ibm.web import db as ibmdb
from ibm.web.common.utils import authorize_and_get_ibm_cloud, compose_ibm_resource_deletion_workflow, \
    create_ibm_resource_creation_workflow, get_paginated_response_json, verify_and_get_region, verify_and_get_zone, \
    verify_references
from .schemas import IBMDedicatedHostGroupInSchema, IBMDedicatedHostGroupOutSchema, \
    IBMDedicatedHostGroupResourceSchema, IBMUpdateDedicatedHostGroupSchema

LOGGER = logging.getLogger(__name__)
ibm_dedicated_host_groups = APIBlueprint('ibm_dedicated_host_groups', __name__, tag="IBM Dedicated Host Groups")


@ibm_dedicated_host_groups.post('/dedicated_host/groups')
@authenticate
@log_activity
@input(IBMDedicatedHostGroupInSchema)
@output(WorkflowRootOutSchema, status_code=202)
def create_ibm_dedicated_host_group(data, user):
    """
    Add an IBM Dedicated Host Group
    This request creates and IBM Dedicated Host Group
    """
    cloud_id = data["ibm_cloud"]["id"]
    region_id = data["region"]["id"]

    ibm_cloud = authorize_and_get_ibm_cloud(cloud_id=cloud_id, user=user)
    verify_and_get_region(ibm_cloud=ibm_cloud, region_id=region_id)

    verify_references(
        cloud_id=cloud_id, body_schema=IBMDedicatedHostGroupInSchema,
        resource_schema=IBMDedicatedHostGroupResourceSchema,
        data=data
    )

    workflow_root = create_ibm_resource_creation_workflow(
        user=user, resource_type=IBMDedicatedHostGroup, data=data, validate=False
    )
    return workflow_root.to_json()


@ibm_dedicated_host_groups.delete('/dedicated_host/groups/<dedicated_host_group_id>')
@authenticate
@log_activity
@output(WorkflowRootOutSchema, status_code=202)
def delete_ibm_dedicated_host_group(dedicated_host_group_id, user):
    """
    Delete an IBM Dedicated Host Group
    This request deletes and IBM Dedicated Host Group
    """
    dedicated_host_group = ibmdb.session.query(IBMDedicatedHostGroup).filter_by(
        id=dedicated_host_group_id
    ).join(IBMDedicatedHostGroup.ibm_cloud).filter_by(
        user_id=user["id"], project_id=user["project_id"], deleted=False
    ).first()
    if not dedicated_host_group:
        message = f"IBM Dedicated Host Group {dedicated_host_group_id} does not exist"
        LOGGER.debug(message)
        abort(404, message)

    return compose_ibm_resource_deletion_workflow(
        user=user, resource_type=IBMDedicatedHostGroup, resource_id=dedicated_host_group_id
    ).to_json(metadata=True)


@ibm_dedicated_host_groups.get('/dedicated_host/groups')
@authenticate
@input(IBMDedicatedHostGroupListQuerySchema, location='query')
@input(PaginationQuerySchema, location='query')
@output(get_pagination_schema(IBMDedicatedHostGroupOutSchema))
def list_ibm_dedicated_host_groups(zonal_res_query_params, pagination_query_params, user):
    """
    List IBM Dedicated Host Groups
    This request lists all IBM Dedicated Host Groups
    """
    cloud_id = zonal_res_query_params["cloud_id"]
    zone_id = zonal_res_query_params.get("zone_id")
    region_id = zonal_res_query_params.get("region_id")
    dh_profile_id = zonal_res_query_params.get("dh_profile_id")

    ibm_cloud = authorize_and_get_ibm_cloud(cloud_id=cloud_id, user=user)
    dh_groups_query = ibmdb.session.query(IBMDedicatedHostGroup).filter_by(cloud_id=cloud_id)

    if dh_profile_id:
        dh_profile = ibmdb.session.query(IBMDedicatedHostProfile).filter_by(id=dh_profile_id).first()
        if not dh_profile:
            message = f"IBM Dedicated Host Profile {dh_profile_id} not found"
            LOGGER.debug(message)
            abort(409, message)

        dh_groups_query = dh_groups_query.filter_by(family=dh_profile.family, class_=dh_profile.class_)

    if region_id:
        verify_and_get_region(ibm_cloud=ibm_cloud, region_id=region_id)
        dh_groups_query = dh_groups_query.filter_by(region_id=region_id)

    if zone_id:
        verify_and_get_zone(cloud_id=cloud_id, zone_id=zone_id)
        dh_groups_query = dh_groups_query.filter_by(zone_id=zone_id)

    dh_groups_page = dh_groups_query.paginate(
        page=pagination_query_params["page"], per_page=pagination_query_params["per_page"], error_out=False
    )
    if not dh_groups_page.items:
        return '', 204

    return get_paginated_response_json(
        items=[item.to_json() for item in dh_groups_page.items],
        pagination_obj=dh_groups_page
    )


@ibm_dedicated_host_groups.get('/dedicated_host/groups/<dedicated_host_group_id>')
@authenticate
@output(IBMDedicatedHostGroupOutSchema)
def get_ibm_dedicated_host_group(dedicated_host_group_id, user):
    """
    Get IBM Dedicated Host Groups
    This request returns an IBM Dedicated Host Groups provided its ID
    """
    dh_group = ibmdb.session.query(IBMDedicatedHostGroup).filter_by(
        id=dedicated_host_group_id
    ).join(IBMDedicatedHostGroup.ibm_cloud).filter_by(
        user_id=user["id"], project_id=user["project_id"], deleted=False
    ).first()
    if not dh_group:
        message = f"IBM Dedicated Host Group {dedicated_host_group_id} does not exist"
        LOGGER.debug(message)
        abort(404, message)

    return dh_group.to_json()


@ibm_dedicated_host_groups.patch('/dedicated_host/groups/<dedicated_host_group_id>')
@authenticate
@input(IBMUpdateDedicatedHostGroupSchema)
@output(WorkflowRootOutSchema, status_code=202)
def update_ibm_dedicated_host_group(dedicated_host_group_id, data, user):
    """
    Update IBM Dedicated Host Groups
    This request updates an IBM Dedicated Host Groups provided its ID
    """
    abort(404)
