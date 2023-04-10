import logging

from apiflask import abort, APIBlueprint, input, output

from ibm.auth import authenticate
from ibm.common.req_resp_schemas.schemas import get_pagination_schema, IBMInstanceQuerySchema, PaginationQuerySchema, \
    WorkflowRootOutSchema
from .schemas import IBMInstanceDiskOutSchema, IBMInstanceDiskUpdateSchema

LOGGER = logging.getLogger(__name__)

ibm_instance_disks = APIBlueprint('ibm_instance_disks', __name__, tag="IBM Instance Disks")


@ibm_instance_disks.get('/instances/disks')
@authenticate
@input(IBMInstanceQuerySchema, location='query')
@input(PaginationQuerySchema, location='query')
@output(get_pagination_schema(IBMInstanceDiskOutSchema))
def list_ibm_instance_disks(listing_query_params, pagination_query_params, user):
    """
    List IBM Instance Disks
    This request lists all IBM Instance Disks for the project of the authenticated user calling the API.
    """
    abort(404)


@ibm_instance_disks.get('/instances/disks/<disk_id>')
@authenticate
@output(IBMInstanceDiskOutSchema)
def get_ibm_instance_disk(disk_id, user):
    """
    Get an IBM Instance Disk
    This request returns an IBM Instance Disk provided its ID.
    """
    abort(404)


@ibm_instance_disks.patch('/instances/disks/<disk_id>')
@authenticate
@input(IBMInstanceDiskUpdateSchema)
@output(WorkflowRootOutSchema, status_code=202)
def update_ibm_instance_disk(disk_id, data, user):
    """
    Update an IBM Instance Disk
    This request updates an IBM Instance Disk provided its ID.
    """
    abort(404)
