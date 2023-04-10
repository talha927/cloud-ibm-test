import logging

from apiflask import abort, APIBlueprint, input, output

from ibm.auth import authenticate
from ibm.common.req_resp_schemas.schemas import get_pagination_schema, PaginationQuerySchema, WorkflowRootOutSchema
from ibm.models import IBMFloatingIP, IBMNetworkInterface
from ibm.web import db as ibmdb
from ibm.web.common.utils import authorize_and_get_ibm_cloud, compose_ibm_resource_deletion_workflow, \
    create_ibm_resource_creation_workflow, \
    get_paginated_response_json, verify_and_get_region, verify_and_get_zone, verify_references
from .schemas import IBMFloatingIPInSchema, IBMFloatingIpListQuerySchema, IBMFloatingIpOutSchema, \
    IBMFloatingIPResourceSchema, UpdateIBMFloatingIpSchema

LOGGER = logging.getLogger(__name__)
ibm_floating_ips = APIBlueprint('ibm_floating_ips', __name__, tag="IBM Floating Ips")


@ibm_floating_ips.route('/floating_ips', methods=['POST'])
@authenticate
@input(IBMFloatingIPInSchema, location='json')
@output(WorkflowRootOutSchema, status_code=202)
def create_ibm_floating_ips(data, user):
    """
    Create IBM Floating Ips
    This request creates an IBM Floating Ips.
    """
    cloud_id = data["ibm_cloud"]["id"]
    region_id = data["region"]["id"]

    ibm_cloud = authorize_and_get_ibm_cloud(cloud_id=cloud_id, user=user)
    verify_and_get_region(ibm_cloud=ibm_cloud, region_id=region_id)

    verify_references(
        cloud_id=cloud_id, body_schema=IBMFloatingIPInSchema, resource_schema=IBMFloatingIPResourceSchema, data=data
    )

    workflow_root = create_ibm_resource_creation_workflow(
        user=user, resource_type=IBMFloatingIP, data=data, validate=False)
    return workflow_root.to_json()


@ibm_floating_ips.route('/floating_ips', methods=['GET'])
@authenticate
@input(PaginationQuerySchema, location='query')
@input(IBMFloatingIpListQuerySchema, location='query')
@output(get_pagination_schema(IBMFloatingIpOutSchema))
def list_ibm_floating_ips(pagination_query_params, floating_ip_res_query_params, user):
    """
    List IBM Floating Ips
    This request lists all IBM Floating Ips for the given cloud id.
    """
    cloud_id = floating_ip_res_query_params["cloud_id"]
    region_id = floating_ip_res_query_params.get("region_id")
    zone_id = floating_ip_res_query_params.get("zone_id")
    network_interface_id = floating_ip_res_query_params.get("network_interface_id")
    reserved = floating_ip_res_query_params.get("reserved")

    ibm_cloud = authorize_and_get_ibm_cloud(cloud_id=cloud_id, user=user)
    floating_ips_query = ibmdb.session.query(IBMFloatingIP).filter_by(cloud_id=cloud_id)

    if region_id:
        verify_and_get_region(ibm_cloud=ibm_cloud, region_id=region_id)
        floating_ips_query = floating_ips_query.filter_by(region_id=region_id)

    if zone_id:
        verify_and_get_zone(cloud_id=cloud_id, zone_id=zone_id)
        floating_ips_query = floating_ips_query.filter_by(zone_id=zone_id)

    if network_interface_id:
        network_interface = ibmdb.session.query(IBMNetworkInterface).filter_by(id=network_interface_id)
        if not network_interface:
            message = f"IBM Network Interface {network_interface_id} not found."
            LOGGER.debug(message)
            abort(404, message)

        floating_ips_query = ibmdb.session.query(IBMFloatingIP).filter_by(network_interface_id=network_interface_id)

    if reserved is not None:
        if not reserved:
            floating_ips_query = ibmdb.session.query(IBMFloatingIP).filter(
                IBMFloatingIP.network_interface_id.is_(None), IBMFloatingIP.public_gateway_id.is_(None),
                IBMFloatingIP.region_id == region_id, IBMFloatingIP.zone_id == zone_id)
        else:
            floating_ips_query = ibmdb.session.query(IBMFloatingIP).filter(
                IBMFloatingIP.network_interface_id.isnot(None) | IBMFloatingIP.public_gateway_id.isnot(None),
                IBMFloatingIP.region_id == region_id, IBMFloatingIP.zone_id == zone_id)

    floating_ips_page = floating_ips_query.paginate(
        page=pagination_query_params["page"], per_page=pagination_query_params["per_page"], error_out=False
    )
    if not floating_ips_page.items:
        return '', 204

    return get_paginated_response_json(
        items=[item.to_json() for item in floating_ips_page.items],
        pagination_obj=floating_ips_page
    )


@ibm_floating_ips.route('/floating_ips/<floating_ip_id>', methods=['GET'])
@authenticate
@output(IBMFloatingIpOutSchema)
def get_ibm_floating_ip(floating_ip_id, user):
    """
    Get IBM Floating Ips
    This request returns an IBM Floating Ips provided its ID.
    """
    floating_ip = ibmdb.session.query(IBMFloatingIP).filter_by(
        id=floating_ip_id
    ).join(IBMFloatingIP.ibm_cloud).filter_by(
        user_id=user["id"], project_id=user["project_id"], deleted=False
    ).first()
    if not floating_ip:
        message = f"IBM Floating IP with ID {floating_ip_id}, does not exist"
        LOGGER.debug(message)
        abort(404, message)

    return floating_ip.to_json()


@ibm_floating_ips.route('/floating_ips/<floating_ip_id>', methods=['PATCH'])
@authenticate
@input(UpdateIBMFloatingIpSchema)
@output(WorkflowRootOutSchema, status_code=202)
def update_ibm_floating_ip(floating_ip_id, data, user):
    """
    Update IBM Floating Ips
    This request updates an IBM Floating Ips
    """
    abort(404)


@ibm_floating_ips.route('/floating_ips/<floating_ip_id>', methods=['DELETE'])
@authenticate
@output(WorkflowRootOutSchema, status_code=202)
def delete_ibm_floating_ip(floating_ip_id, user):
    """
    Delete IBM Floating Ips
    This request deletes an IBM Floating Ips provided its ID.
    """
    floating_ip = ibmdb.session.query(IBMFloatingIP).filter_by(id=floating_ip_id) \
        .join(IBMFloatingIP.ibm_cloud).filter_by(user_id=user["id"], project_id=user["project_id"], deleted=False) \
        .first()

    if not floating_ip:
        message = f"IBM Floating Ip {floating_ip} does not exist"
        LOGGER.debug(message)
        abort(404, message)

    if floating_ip.public_gateway:
        message = f"IBM Floating Ip {floating_ip} cannot be delete. Attached with a public gateway."
        LOGGER.debug(message)
        abort(409, message)

    return compose_ibm_resource_deletion_workflow(
        user=user, resource_type=IBMFloatingIP, resource_id=floating_ip.id
    ).to_json(metadata=True)
