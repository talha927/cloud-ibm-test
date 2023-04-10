import logging

from apiflask import abort, APIBlueprint, input, output

from ibm.auth import authenticate
from ibm.common.req_resp_schemas.schemas import get_pagination_schema, IBMZonalResourceListQuerySchema, \
    PaginationQuerySchema, WorkflowRootOutSchema
from ibm.middleware import log_activity
from ibm.models import IBMDedicatedHost, IBMInstance
from ibm.web import db as ibmdb
from ibm.web.common.utils import authorize_and_get_ibm_cloud, compose_ibm_resource_deletion_workflow, \
    create_ibm_resource_creation_workflow, get_paginated_response_json, verify_and_get_region, verify_and_get_zone, \
    verify_references
from .schemas import IBMDedicatedHostInSchema, IBMDedicatedHostOutSchema, IBMDedicatedHostResourceSchema, \
    IBMUpdateDedicatedHostSchema

LOGGER = logging.getLogger(__name__)
ibm_dedicated_hosts = APIBlueprint('ibm_dedicated_hosts', __name__, tag="IBM Dedicated Hosts")


@ibm_dedicated_hosts.post('/dedicated_hosts')
@authenticate
@log_activity
@input(IBMDedicatedHostInSchema)
@output(WorkflowRootOutSchema, status_code=202)
def create_ibm_dedicated_host(data, user):
    """
    Create IBM Dedicated Hosts
    This request creates an IBM Dedicated Host
    """
    cloud_id = data["ibm_cloud"]["id"]
    region_id = data["region"]["id"]

    ibm_cloud = authorize_and_get_ibm_cloud(cloud_id=cloud_id, user=user)
    verify_and_get_region(ibm_cloud=ibm_cloud, region_id=region_id)

    verify_references(
        cloud_id=cloud_id, body_schema=IBMDedicatedHostInSchema, resource_schema=IBMDedicatedHostResourceSchema,
        data=data
    )

    workflow_root = create_ibm_resource_creation_workflow(
        user=user, resource_type=IBMDedicatedHost, data=data, validate=False
    )
    return workflow_root.to_json()


@ibm_dedicated_hosts.delete('/dedicated_hosts/<dedicated_host_id>')
@authenticate
@log_activity
@output(WorkflowRootOutSchema, status_code=202)
def delete_ibm_dedicated_host(dedicated_host_id, user):
    """
    Delete IBM Dedicated Host
    This request deletes an IBM Dedicated Host
    """
    dedicated_host = ibmdb.session.query(IBMDedicatedHost).filter_by(
        id=dedicated_host_id
    ).join(IBMDedicatedHost.ibm_cloud).filter_by(
        user_id=user["id"], project_id=user["project_id"], deleted=False
    ).first()
    if not dedicated_host:
        message = f"IBM Dedicated Host {dedicated_host_id} does not exist"
        LOGGER.debug(message)
        abort(404, message)

    # TODO: uncomment after update call
    # if dedicated_host.instance_placement_enabled:
    #     message = f"Please disable Instance Placement on this IBM Dedicated Host {dedicated_host_id}"
    #     LOGGER.debug(message)
    #     abort(404, message)

    instance_count = ibmdb.session.query(IBMInstance).filter_by(dedicated_host_id=dedicated_host_id).count()
    if instance_count:
        message = f"Please delete instances attach to this IBM Dedicated Host {dedicated_host_id}"
        LOGGER.debug(message)
        abort(409, message)

    return compose_ibm_resource_deletion_workflow(
        user=user, resource_type=IBMDedicatedHost, resource_id=dedicated_host_id
    ).to_json(metadata=True)


@ibm_dedicated_hosts.get('/dedicated_hosts')
@authenticate
@input(IBMZonalResourceListQuerySchema, location='query')
@input(PaginationQuerySchema, location='query')
@output(get_pagination_schema(IBMDedicatedHostOutSchema))
def list_ibm_dedicated_hosts(zonal_res_query_params, pagination_query_params, user):
    """
    List IBM Dedicated Hosts
    This requests list all IBM Dedicated Hosts for a given cloud
    """
    cloud_id = zonal_res_query_params["cloud_id"]
    zone_id = zonal_res_query_params.get("zone_id")
    region_id = zonal_res_query_params.get("region_id")

    ibm_cloud = authorize_and_get_ibm_cloud(cloud_id=cloud_id, user=user)
    dedicated_hosts_query = ibmdb.session.query(IBMDedicatedHost).filter_by(cloud_id=cloud_id)

    if region_id:
        verify_and_get_region(ibm_cloud=ibm_cloud, region_id=region_id)
        dedicated_hosts_query = dedicated_hosts_query.filter_by(region_id=region_id)

    if zone_id:
        verify_and_get_zone(cloud_id=cloud_id, zone_id=zone_id)
        dedicated_hosts_query = dedicated_hosts_query.filter_by(zone_id=zone_id)

    dedicated_hosts_page = dedicated_hosts_query.paginate(
        page=pagination_query_params["page"], per_page=pagination_query_params["per_page"], error_out=False
    )
    if not dedicated_hosts_page.items:
        return '', 204

    return get_paginated_response_json(
        items=[item.to_json() for item in dedicated_hosts_page.items],
        pagination_obj=dedicated_hosts_page
    )


@ibm_dedicated_hosts.get('/dedicated_hosts/<dedicated_host_id>')
@authenticate
@output(IBMDedicatedHostOutSchema)
def get_ibm_dedicated_host(dedicated_host_id, user):
    """
    Get IBM Dedicated Hosts
    This request returns an IBM Dedicated Hosts provided its ID
    """
    dedicated_host = ibmdb.session.query(IBMDedicatedHost).filter_by(
        id=dedicated_host_id
    ).join(IBMDedicatedHost.ibm_cloud).filter_by(
        user_id=user["id"], project_id=user["project_id"], deleted=False
    ).first()
    if not dedicated_host:
        message = f"IBM Dedicated Host {dedicated_host_id} does not exist"
        LOGGER.debug(message)
        abort(404, message)

    return dedicated_host.to_json()


@ibm_dedicated_hosts.patch('/dedicated_hosts/<dedicated_host_id>')
@authenticate
@input(IBMUpdateDedicatedHostSchema)
@output(WorkflowRootOutSchema, status_code=202)
def update_ibm_dedicated_host(dedicated_host_id, data, user):
    """
    Update IBM Dedicated Host
    This request updates an IBM Dedicated Host
    """
    abort(404)
