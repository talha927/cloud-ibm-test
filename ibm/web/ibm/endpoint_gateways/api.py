import logging

from apiflask import abort, APIBlueprint, input, output

from ibm.auth import authenticate
from ibm.common.req_resp_schemas.schemas import get_pagination_schema, IBMResourceQuerySchema, PaginationQuerySchema, \
    WorkflowRootOutSchema
from ibm.middleware import log_activity
from ibm.models import IBMCloud, IBMEndpointGateway, IBMSecurityGroup, IBMVpcNetwork
from ibm.web import db as ibmdb
from ibm.web.common.utils import authorize_and_get_ibm_cloud, compose_ibm_resource_deletion_workflow, \
    compose_ibm_sync_resource_workflow, create_ibm_resource_creation_workflow, get_paginated_response_json, \
    verify_and_get_region, verify_references
from .schemas import IBMEndpointGatewayInSchema, IBMEndpointGatewayOutSchema, IBMEndpointGatewayResourceSchema, \
    IBMEndpointGatewaysListQuerySchema, UpdateIBMEndpointGatewaySchema

LOGGER = logging.getLogger(__name__)

ibm_endpoint_gateways = APIBlueprint('ibm_endpoint_gateways', __name__, tag="IBM Virtual Endpoint Gateways")


@ibm_endpoint_gateways.post('/endpoint_gateways')
@authenticate
@log_activity
@input(IBMEndpointGatewayInSchema)
@output(WorkflowRootOutSchema, status_code=202)
def create_ibm_endpoint_gateways(data, user):
    """
    Create IBM Virtual Endpoint Gateway
    This request creates an IBM Virtual Endpoint Gateways.
    """
    cloud_id = data["ibm_cloud"]["id"]
    region_id = data["region"]["id"]

    ibm_cloud = authorize_and_get_ibm_cloud(cloud_id=cloud_id, user=user)
    verify_and_get_region(ibm_cloud=ibm_cloud, region_id=region_id)

    verify_references(
        cloud_id=cloud_id, body_schema=IBMEndpointGatewayInSchema, resource_schema=IBMEndpointGatewayResourceSchema,
        data=data
    )

    workflow_root = create_ibm_resource_creation_workflow(
        user=user, resource_type=IBMEndpointGateway, data=data, validate=False)
    return workflow_root.to_json()


@ibm_endpoint_gateways.get('/endpoint_gateways')
@authenticate
@input(PaginationQuerySchema, location='query')
@input(IBMEndpointGatewaysListQuerySchema, location='query')
@output(get_pagination_schema(IBMEndpointGatewayOutSchema))
def list_ibm_endpoint_gateways(pagination_query_params, endpoint_gateway_res_query_params, user):
    """
    List IBM Virtual Endpoint Gateways
    This request lists all IBM Virtual Endpoint Gateways for the given cloud id.
    """
    cloud_id = endpoint_gateway_res_query_params["cloud_id"]
    region_id = endpoint_gateway_res_query_params.get("region_id")
    security_group_id = endpoint_gateway_res_query_params.get("security_group_id")
    vpc_id = endpoint_gateway_res_query_params.get("vpc_id")

    ibm_cloud = authorize_and_get_ibm_cloud(cloud_id=cloud_id, user=user)
    endpoint_gateways_query = ibmdb.session.query(IBMEndpointGateway).filter_by(cloud_id=cloud_id)

    if region_id:
        verify_and_get_region(ibm_cloud=ibm_cloud, region_id=region_id)
        endpoint_gateways_query = endpoint_gateways_query.filter_by(region_id=region_id)

    if security_group_id:
        security_group = ibmdb.session.query(IBMSecurityGroup).filter_by(id=security_group_id).first()
        if not security_group:
            message = f"IBM Security Group {security_group_id} not found."
            LOGGER.debug(message)
            abort(404, message)

        endpoint_gateways_query = endpoint_gateways_query.filter(
            IBMEndpointGateway.security_groups.in_(security_group_id))

    if vpc_id:
        security_group = ibmdb.session.query(IBMVpcNetwork).filter_by(id=security_group_id).first()
        if not security_group:
            message = f"IBM VPC {vpc_id} not found."
            LOGGER.debug(message)
            abort(404, message)

        endpoint_gateways_query = endpoint_gateways_query.filter_by(vpc_id=vpc_id)

    endpoint_gateways_page = endpoint_gateways_query.paginate(
        page=pagination_query_params["page"], per_page=pagination_query_params["per_page"], error_out=False
    )
    if not endpoint_gateways_page.items:
        return '', 204

    return get_paginated_response_json(
        items=[item.to_json() for item in endpoint_gateways_page.items],
        pagination_obj=endpoint_gateways_page
    )


@ibm_endpoint_gateways.get('/endpoint_gateways/<endpoint_gateway_id>')
@authenticate
@output(IBMEndpointGatewayOutSchema)
def get_ibm_endpoint_gateway(endpoint_gateway_id, user):
    """
    Get IBM Virtual Endpoint Gateways
    This request returns an IBM Virtual Endpoint Gateways provided its ID.
    """
    endpoint_gateway = ibmdb.session.query(IBMEndpointGateway).filter_by(
        id=endpoint_gateway_id
    ).join(IBMEndpointGateway.ibm_cloud).filter_by(
        user_id=user["id"], project_id=user["project_id"], deleted=False, status=IBMCloud.STATUS_VALID
    ).first()
    if not endpoint_gateway:
        message = f"IBM Endpoint Gateway with ID {endpoint_gateway_id}, does not exist"
        LOGGER.debug(message)
        abort(404, message)

    return endpoint_gateway.to_json()


@ibm_endpoint_gateways.patch('/endpoint_gateways/<endpoint_gateway_id>')
@authenticate
@input(UpdateIBMEndpointGatewaySchema)
@output(WorkflowRootOutSchema, status_code=202)
def update_ibm_endpoint_gateway(endpoint_gateway_id, data, user):
    """
    Update IBM Virtual Endpoint Gateways
    This request updates an IBM Virtual Endpoint Gateways
    """
    abort(404)


@ibm_endpoint_gateways.delete('/endpoint_gateways/<endpoint_gateway_id>')
@authenticate
@log_activity
@output(WorkflowRootOutSchema, status_code=202)
def delete_ibm_endpoint_gateway(endpoint_gateway_id, user):
    """
    Delete IBM Virtual Endpoint Gateways
    This request deletes an IBM Virtual Endpoint Gateways provided its ID.
    """
    endpoint_gateway = ibmdb.session.query(IBMEndpointGateway).filter_by(id=endpoint_gateway_id).first()

    if not endpoint_gateway:
        message = f"IBM Endpoint Gateway {endpoint_gateway} does not exist"
        LOGGER.debug(message)
        abort(404, message)

    authorize_and_get_ibm_cloud(cloud_id=endpoint_gateway.cloud_id, user=user)
    return compose_ibm_resource_deletion_workflow(
        user=user, resource_type=IBMEndpointGateway, resource_id=endpoint_gateway.id
    ).to_json(metadata=True)


@ibm_endpoint_gateways.post('/endpoint_gateways/targets/sync')
@authenticate
@input(IBMResourceQuerySchema, location="query")
@output(WorkflowRootOutSchema, status_code=202)
def sync_ibm_endpoint_gateway_targets(cloud_resource_param, user):
    """
    Sync IBM Virtual Endpoint Gateways
    This request sync an IBM Virtual Endpoint Gateways targets for FE.
    """
    cloud_id = cloud_resource_param["cloud_id"]
    authorize_and_get_ibm_cloud(cloud_id=cloud_id, user=user)

    return compose_ibm_sync_resource_workflow(
        user=user, resource_type=IBMEndpointGateway, data=cloud_resource_param
    ).to_json(metadata=True)
