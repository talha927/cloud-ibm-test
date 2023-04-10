import logging

from apiflask import abort, APIBlueprint, input, output

from ibm.auth import authenticate
from ibm.common.req_resp_schemas.schemas import get_pagination_schema, IBMZonalResourceListQuerySchema, \
    PaginationQuerySchema, WorkflowRootOutSchema
from ibm.middleware import log_activity
from ibm.models import IBMPublicGateway, IBMZone
from ibm.web import db as ibmdb
from ibm.web.common.utils import authorize_and_get_ibm_cloud, compose_ibm_resource_deletion_workflow, \
    create_ibm_resource_creation_workflow, get_paginated_response_json, verify_and_get_region, verify_references
from .schemas import IBMPublicGatewayInSchema, IBMPublicGatewayOutSchema, IBMPublicGatewayResourceSchema, \
    UpdateIBMPublicGatewaySchema

LOGGER = logging.getLogger(__name__)

ibm_public_gateways = APIBlueprint('ibm_public_gateways', __name__, tag="IBM Public Gateways")


@ibm_public_gateways.route('/public_gateways', methods=['POST'])
@authenticate
@log_activity
@input(IBMPublicGatewayInSchema)
@output(WorkflowRootOutSchema, status_code=202)
def create_ibm_public_gateway(data, user):
    """
    Create IBM Public Gateway
    This request creates an IBM Public gateway.
    """
    cloud_id = data["ibm_cloud"]["id"]
    region_id = data["region"]["id"]

    ibm_cloud = authorize_and_get_ibm_cloud(cloud_id=cloud_id, user=user)
    verify_and_get_region(ibm_cloud=ibm_cloud, region_id=region_id)

    verify_references(
        cloud_id=cloud_id, body_schema=IBMPublicGatewayInSchema, resource_schema=IBMPublicGatewayResourceSchema,
        data=data
    )

    workflow_root = create_ibm_resource_creation_workflow(
        user=user, resource_type=IBMPublicGateway, data=data, validate=False
    )
    return workflow_root.to_json()


@ibm_public_gateways.route('/public_gateways', methods=['GET'])
@authenticate
@input(IBMZonalResourceListQuerySchema, location='query')
@input(PaginationQuerySchema, location='query')
@output(get_pagination_schema(IBMPublicGatewayOutSchema))
def list_ibm_public_gateways(zonal_res_query_params, pagination_query_params, user):
    """
    List IBM Public Gateways
    This request lists all IBM Public Gateway for the given cloud id.
    """
    cloud_id = zonal_res_query_params["cloud_id"]
    region_id = zonal_res_query_params.get("region_id")
    zone_id = zonal_res_query_params.get("zone_id")

    ibm_cloud = authorize_and_get_ibm_cloud(cloud_id=cloud_id, user=user)

    region = None
    if region_id:
        region = verify_and_get_region(ibm_cloud=ibm_cloud, region_id=region_id)

    zone = None
    if zone_id:
        zone = ibmdb.session.query(IBMZone).filter_by(id=zone_id, cloud_id=cloud_id).first()
        if not zone:
            abort(404, f"IBM Zone {zone_id} does not exist")

    pgw_query = ibmdb.session.query(IBMPublicGateway).filter_by(cloud_id=cloud_id)
    if region:
        pgw_query = pgw_query.filter_by(region_id=region_id)

    if zone:
        pgw_query = pgw_query.filter_by(zone_id=zone_id)

    pgw_page = pgw_query.paginate(
        page=pagination_query_params["page"], per_page=pagination_query_params["per_page"], error_out=False
    )
    if not pgw_page.items:
        return '', 204

    return get_paginated_response_json(
        items=[item.to_json() for item in pgw_page.items],
        pagination_obj=pgw_page
    )


@ibm_public_gateways.route('/public_gateways/<public_gateway_id>', methods=['GET'])
@authenticate
@output(IBMPublicGatewayOutSchema)
def get_ibm_public_gateway(public_gateway_id, user):
    """
    Get IBM Public Gateways
    This request returns an IBM Public Gateway provided its ID.
    """
    public_gateway = ibmdb.session.query(IBMPublicGateway).filter_by(
        id=public_gateway_id
    ).join(IBMPublicGateway.ibm_cloud).filter_by(
        user_id=user["id"], project_id=user["project_id"], deleted=False
    ).first()
    if not public_gateway:
        message = f"IBM Public Gateway {public_gateway_id} does not exist"
        LOGGER.debug(message)
        abort(404, message)

    return public_gateway.to_json()


@ibm_public_gateways.route('/public_gateways/<public_gateway_id>', methods=['PATCH'])
@authenticate
@input(UpdateIBMPublicGatewaySchema)
@output(IBMPublicGatewayOutSchema, status_code=202)
def update_ibm_public_gateway(public_gateway_id, data, user):
    """
    Update IBM Public Gateway
    This request updates an IBM Public Gateways
    """
    abort(404)


@ibm_public_gateways.route('/public_gateways/<public_gateway_id>', methods=['DELETE'])
@authenticate
@log_activity
@output(WorkflowRootOutSchema, status_code=202)
def delete_ibm_public_gateway(public_gateway_id, user):
    """
    Delete IBM Public Gateway
    This request deletes an IBM Public Gateways provided its ID.
    """
    public_gateway: IBMPublicGateway = ibmdb.session.query(IBMPublicGateway).filter_by(id=public_gateway_id) \
        .join(IBMPublicGateway.ibm_cloud).filter_by(user_id=user["id"], project_id=user["project_id"], deleted=False) \
        .first()

    if not public_gateway:
        message = f"IBM Public Gateway {public_gateway_id} does not exist"
        LOGGER.debug(message)
        abort(404, message)

    if public_gateway.subnets.count():
        message = f"IBM Public Gateway {public_gateway_id} cannot be deleted. Attached to other resources."
        LOGGER.debug(message)
        abort(409, message)

    return compose_ibm_resource_deletion_workflow(
        user=user, resource_type=IBMPublicGateway, resource_id=public_gateway_id
    ).to_json(metadata=True)
