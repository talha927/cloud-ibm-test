import logging

from apiflask import abort, APIBlueprint, input, output

from ibm.auth import authenticate
from ibm.common.req_resp_schemas.schemas import get_pagination_schema, PaginationQuerySchema, WorkflowRootOutSchema
from ibm.models import IBMDedicatedHost, IBMDedicatedHostDisk
from ibm.web import db as ibmdb
from ibm.web.common.utils import authorize_and_get_ibm_cloud, get_paginated_response_json, verify_and_get_region, \
    verify_and_get_zone
from .schemas import IBMDedicatedHostDiskOutSchema, IBMUpdateDedicatedHostDiskSchema
from ..schemas import IBMDedicatedHostResourceListQuerySchema

LOGGER = logging.getLogger(__name__)

ibm_dedicated_host_disks = APIBlueprint('ibm_dedicated_host_disks', __name__, tag="IBM Dedicated Host Disks")


@ibm_dedicated_host_disks.get('/dedicated_host/disks')
@authenticate
@input(IBMDedicatedHostResourceListQuerySchema, location='query')
@input(PaginationQuerySchema, location='query')
@output(get_pagination_schema(IBMDedicatedHostDiskOutSchema))
def list_ibm_dedicated_host_disks(dedicated_host_res_query_params, pagination_query_params, user):
    """
    List IBM Dedicated Host Disks
    This requests list all IBM Dedicated Host Disks for a given cloud
    """
    cloud_id = dedicated_host_res_query_params["cloud_id"]
    zone_id = dedicated_host_res_query_params.get("zone_id")
    region_id = dedicated_host_res_query_params.get("region_id")
    dedicated_host_id = dedicated_host_res_query_params['dedicated_host_id']

    dedicated_host = ibmdb.session.query(IBMDedicatedHost).filter_by(cloud_id=cloud_id, id=dedicated_host_id).first()
    if not dedicated_host:
        message = f"IBM Dedicated Host {dedicated_host_id} does not exist"
        LOGGER.debug(message)
        abort(404, message)

    ibm_cloud = authorize_and_get_ibm_cloud(cloud_id=cloud_id, user=user)
    dh_disks_query = ibmdb.session.query(IBMDedicatedHostDisk).filter_by(cloud_id=cloud_id,
                                                                         dedicated_host_id=dedicated_host_id)

    if region_id:
        verify_and_get_region(ibm_cloud=ibm_cloud, region_id=region_id)
        dh_disks_query = dh_disks_query.filter_by(region_id=region_id)

    if zone_id:
        verify_and_get_zone(cloud_id=cloud_id, zone_id=zone_id)
        dh_disks_query = dh_disks_query.filter_by(zone_id=zone_id)

    dh_disks_page = dh_disks_query.paginate(
        page=pagination_query_params["page"], per_page=pagination_query_params["per_page"], error_out=False
    )
    if not dh_disks_page.items:
        return '', 204

    return get_paginated_response_json(
        items=[item.to_json() for item in dh_disks_page.items],
        pagination_obj=dh_disks_page
    )


@ibm_dedicated_host_disks.get('/dedicated_host/disks/<disk_id>')
@authenticate
@input(IBMDedicatedHostResourceListQuerySchema, location='query')
@output(IBMDedicatedHostDiskOutSchema)
def get_ibm_dedicated_host_disk(disk_id, dedicated_host_res_query_params, user):
    """
    Get IBM Dedicated Hosts Disks
    This request returns an IBM Dedicated Host Disks provided its ID
    """
    cloud_id = dedicated_host_res_query_params["cloud_id"]
    dedicated_host_id = dedicated_host_res_query_params['dedicated_host_id']

    dedicated_host = ibmdb.session.query(IBMDedicatedHost).filter_by(cloud_id=cloud_id, id=dedicated_host_id).first()
    if not dedicated_host:
        message = f"IBM Dedicated Host {dedicated_host_id} does not exist"
        LOGGER.debug(message)
        abort(404, message)

    dh_disk = ibmdb.session.query(IBMDedicatedHostDisk).filter_by(
        id=disk_id, dedicated_host_id=dedicated_host_id
    ).join(IBMDedicatedHostDisk.ibm_cloud).filter_by(
        user_id=user["id"], project_id=user["project_id"], deleted=False
    ).first()
    if not dh_disk:
        message = f"IBM Dedicated Host Disk {disk_id} does not exist"
        LOGGER.debug(message)
        abort(404, message)

    return dh_disk.to_json()


@ibm_dedicated_host_disks.patch('/dedicated_host/disks/<disk_id>')
@authenticate
@input(IBMUpdateDedicatedHostDiskSchema)
@output(WorkflowRootOutSchema, status_code=202)
def update_ibm_dedicated_host_disk(disk_id, data, user):
    """
    Update IBM Dedicated Hosts Disks
    This request updates an IBM Dedicated Host Disks
    """
    abort(404)
