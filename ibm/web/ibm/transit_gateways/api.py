import logging

from apiflask import abort, input, output, APIBlueprint
from flask import jsonify

from ibm.auth import authenticate
from ibm.common.clients.softlayer_clients import SoftlayerSubnetClient
from ibm.common.req_resp_schemas.schemas import get_pagination_schema, IBMRegionalResourceListQuerySchema, \
    PaginationQuerySchema, WorkflowRootOutSchema
from ibm.models import IBMTransitGateway, IBMTransitGatewayConnection, IBMVpcNetwork, \
    IBMTransitGatewayConnectionPrefixFilter, SoftlayerCloud, IBMTransitGatewayRouteReport
from ibm.web import db as ibmdb
from ibm.web.common.utils import authorize_and_get_ibm_cloud, compose_ibm_resource_deletion_workflow, \
    create_ibm_resource_creation_workflow, get_paginated_response_json, verify_references, \
    compose_ibm_transit_gateway_deletion_workflow, verify_and_get_region
from .schemas import IBMTransitGatewayInSchema, IBMTransitGatewayResourceSchema, IBMTransitGatewayOutSchema, \
    IBMTransitGatewayConnectionInSchema, IBMTransitGatewayConnectionResourceSchema, \
    IBMTransitGatewayConnectionPrefixFilterInSchema, IBMTransitGatewayConnectionPrefixFilterResourceSchema, \
    IBMTransitGatewayConnectionOutSchema, IBMTransitGatewayConnectionPrefixFilterOutSchema, \
    IBMListTransitConnectionOutSchema, IBMTransitGatewayQuerySchema, IBMTransitGatewayConnectionQuerySchema, \
    IBMTransitGatewayRouteReportInSchema, IBMTransitGatewayRouteReportResourceSchema, \
    IBMTransitGatewayRouteReportOutSchema
from .utils import create_ibm_transit_gateway_creation_workflow, create_ibm_transit_gateway_connection_creation_workflow

ibm_transit_gateways = APIBlueprint('ibm_transit_gateways', __name__, tag="IBM Transit Gateways")

LOGGER = logging.getLogger(__name__)


@ibm_transit_gateways.post('/transit_gateways')
@authenticate
@input(IBMTransitGatewayInSchema)
@output(WorkflowRootOutSchema, status_code=202)
def create_ibm_transit_gateway(data, user):
    """
    Create an IBM Transit Gateway
    This request registers an IBM Transit Gateway with VPC+.
    """
    cloud_id = data["ibm_cloud"]["id"]

    authorize_and_get_ibm_cloud(cloud_id=cloud_id, user=user)

    verify_references(
        cloud_id=cloud_id, body_schema=IBMTransitGatewayInSchema, resource_schema=IBMTransitGatewayResourceSchema,
        data=data
    )

    for connection in data.get("connections", []):
        if connection.get("network_type") == "vpc":
            vpc_id = connection["vpc"]["id"]
            vpc = ibmdb.session.query(IBMVpcNetwork).filter_by(id=vpc_id, cloud_id=cloud_id).first()
            if not vpc:
                message = f"IBM VPC Network with ID {vpc_id} does not exist"
                LOGGER.debug(message)
                abort(404, message)

    workflow_root = create_ibm_transit_gateway_creation_workflow(
        data, user, cloud_id, db_session=ibmdb.session, sketch=False)

    return workflow_root.to_json(metadata=True)


@ibm_transit_gateways.get('/transit_gateways')
@authenticate
@input(IBMRegionalResourceListQuerySchema, location='query')
@input(PaginationQuerySchema, location='query')
@output(get_pagination_schema(IBMTransitGatewayOutSchema))
def list_ibm_transit_gateways(res_query_params, pagination_query_params, user):
    """
    List IBM Transit Gateways
    This request lists all IBM Transit Gateways for the project of the authenticated user calling the API.
    """
    cloud_id = res_query_params["cloud_id"]
    region_id = res_query_params.get("region_id")

    ibm_cloud = authorize_and_get_ibm_cloud(cloud_id=cloud_id, user=user)
    transit_gateways_query = ibmdb.session.query(IBMTransitGateway).filter_by(cloud_id=cloud_id)

    if region_id:
        verify_and_get_region(ibm_cloud=ibm_cloud, region_id=region_id)
        transit_gateways_query = transit_gateways_query.filter_by(region_id=region_id)

    transit_gateway_page = transit_gateways_query.paginate(
        page=pagination_query_params["page"], per_page=pagination_query_params["per_page"], error_out=False
    )
    if not transit_gateway_page.items:
        return '', 204

    return get_paginated_response_json(
        items=[item.to_json() for item in transit_gateway_page.items],
        pagination_obj=transit_gateway_page
    )


@ibm_transit_gateways.get('/transit_gateways/<transit_gateway_id>')
@authenticate
@output(IBMTransitGatewayOutSchema)
def get_ibm_transit_gateway(transit_gateway_id, user):
    """
    Get an IBM Transit Gateway
    This request returns an IBM Transit Gateway provided its ID.
    """
    transit_gateway = ibmdb.session.query(IBMTransitGateway).filter_by(
        id=transit_gateway_id
    ).join(IBMTransitGateway.ibm_cloud).filter_by(
        user_id=user["id"], project_id=user["project_id"], deleted=False
    ).first()
    if not transit_gateway:
        message = f"IBM Transit Gateway with ID {transit_gateway_id} does not exist"
        LOGGER.debug(message)
        abort(404, message)

    return transit_gateway.to_json()


@ibm_transit_gateways.delete('/transit_gateways/<transit_gateway_id>')
@authenticate
@output(WorkflowRootOutSchema, status_code=202)
def delete_ibm_transit_gateway(transit_gateway_id, user):
    """
    Delete an IBM Transit Gateway
    This request deletes an IBM Transit Gateway provided its ID.
    """
    transit_gateway: IBMTransitGateway = ibmdb.session.query(IBMTransitGateway).filter_by(id=transit_gateway_id) \
        .join(IBMTransitGateway.ibm_cloud).filter_by(user_id=user["id"], project_id=user["project_id"], deleted=False) \
        .first()
    if not transit_gateway:
        message = f"IBM Transit Gateway {transit_gateway_id} does not exist"
        LOGGER.debug(message)
        abort(404, message)

    return compose_ibm_transit_gateway_deletion_workflow(
        user=user, resource_type=IBMTransitGateway, resource_id=transit_gateway_id
    ).to_json(metadata=True)


@ibm_transit_gateways.patch('/transit_gateways/<transit_gateway_id>')
@authenticate
@input(IBMTransitGatewayResourceSchema)
@output(WorkflowRootOutSchema, status_code=202)
def update_transit_gateway(transit_gateway_id, data, user):
    """
    Update IBM Cloud
    This request updates an IBM Transit Gateway on IBM Cloud
    """
    abort(404)


@ibm_transit_gateways.post('/tg_connections')
@authenticate
@input(IBMTransitGatewayConnectionInSchema)
@output(WorkflowRootOutSchema, status_code=202)
def create_transit_gateway_connection(data, user):
    """
    Create IBM Transit gateway Connection
    """
    cloud_id = data["ibm_cloud"]["id"]
    transit_gateway_id = data["transit_gateway"]["id"]

    transit_gateway = ibmdb.session.query(IBMTransitGateway).filter_by(id=transit_gateway_id, cloud_id=cloud_id).first()
    if not transit_gateway:
        message = f"IBM Transit Gateway with ID {transit_gateway_id} does not exist"
        LOGGER.debug(message)
        abort(404, message)

    if data["resource_json"]["network_type"] == "vpc":
        vpc_id = data["resource_json"]["vpc"]["id"]
        vpc = ibmdb.session.query(IBMVpcNetwork).filter_by(id=vpc_id, cloud_id=cloud_id).first()
        if not vpc:
            message = f"IBM VPC Network with ID {vpc_id} does not exist"
            LOGGER.debug(message)
            abort(404, message)

    authorize_and_get_ibm_cloud(cloud_id=cloud_id, user=user)

    verify_references(
        cloud_id=cloud_id, body_schema=IBMTransitGatewayConnectionInSchema,
        resource_schema=IBMTransitGatewayConnectionResourceSchema,
        data=data
    )

    workflow_root = create_ibm_transit_gateway_connection_creation_workflow(
        data, user, cloud_id, db_session=ibmdb.session, sketch=False)

    return workflow_root.to_json(metadata=True)


@ibm_transit_gateways.get('/tg_connections')
@authenticate
@input(IBMTransitGatewayQuerySchema, location='query')
@input(PaginationQuerySchema, location='query')
@output(get_pagination_schema(IBMTransitGatewayConnectionOutSchema))
def list_ibm_transit_gateway_connections(transit_gateway_id_query_params, pagination_query_params, user):
    """
    List IBM Transit Gateway Connections
    This request lists all IBM Transit Gateway Connections for the project of the authenticated user calling the API
    """
    cloud_id = transit_gateway_id_query_params["cloud_id"]
    transit_gateway_id = transit_gateway_id_query_params["transit_gateway_id"]

    authorize_and_get_ibm_cloud(cloud_id=cloud_id, user=user)

    transit_gateways_query = ibmdb.session.query(IBMTransitGateway).filter_by(id=transit_gateway_id, cloud_id=cloud_id)
    if not transit_gateways_query:
        message = f"IBM Transit Gateway with Transit Gateway ID {transit_gateway_id} does not exist"
        LOGGER.debug(message)
        abort(404, message)

    transit_gateway_connections_query = ibmdb.session.query(IBMTransitGatewayConnection).filter_by(
        transit_gateway_id=transit_gateway_id, cloud_id=cloud_id)
    if not transit_gateway_connections_query:
        message = f"IBM Transit Gateway Connection with Transit Gateway ID {transit_gateway_id} does not exist"
        LOGGER.debug(message)
        abort(404, message)

    transit_gateway_connections_page = transit_gateway_connections_query.paginate(
        page=pagination_query_params["page"], per_page=pagination_query_params["per_page"], error_out=False
    )
    if not transit_gateway_connections_page.items:
        return '', 204

    return get_paginated_response_json(
        items=[item.to_json() for item in transit_gateway_connections_page.items],
        pagination_obj=transit_gateway_connections_page
    )


@ibm_transit_gateways.get('/tg_connections/<connection_id>')
@authenticate
@output(IBMTransitGatewayConnectionOutSchema)
def get_ibm_transit_gateway_connection(connection_id, user):
    """
    Get an IBM Transit Gateway Connection
    This request returns an IBM Transit Gateway Connection provided its ID
    """
    transit_gateway_connection: IBMTransitGatewayConnection = ibmdb.session.query(IBMTransitGatewayConnection). \
        filter_by(id=connection_id).join(IBMTransitGatewayConnection.ibm_cloud). \
        filter_by(user_id=user["id"], project_id=user["project_id"], deleted=False) \
        .first()
    if not transit_gateway_connection:
        message = f"IBM Transit Gateway Connection with ID {connection_id} does not exist"
        LOGGER.debug(message)
        abort(404, message)

    return transit_gateway_connection.to_json()


@ibm_transit_gateways.delete('/tg_connections/<connection_id>')
@authenticate
@output(WorkflowRootOutSchema, status_code=202)
def delete_ibm_transit_gateway_connection(connection_id, user):
    """
    Delete an IBM Transit Gateway Connection
    This request deletes an IBM Transit Gateway Connection provided its ID
    """
    transit_gateway_connection: IBMTransitGatewayConnection = ibmdb.session.query(IBMTransitGatewayConnection). \
        filter_by(id=connection_id).join(IBMTransitGatewayConnection.ibm_cloud). \
        filter_by(user_id=user["id"], project_id=user["project_id"], deleted=False) \
        .first()
    if not transit_gateway_connection:
        message = f"IBM Transit Gateway Connection with ID {connection_id} does not exist"
        LOGGER.debug(message)
        abort(404, message)

    return compose_ibm_resource_deletion_workflow(
        user=user, resource_type=IBMTransitGatewayConnection, resource_id=connection_id
    ).to_json(metadata=True)


@ibm_transit_gateways.patch('/tg_connections/<connection_id>')
@authenticate
@input(IBMTransitGatewayConnectionResourceSchema)
@output(WorkflowRootOutSchema, status_code=202)
def update_transit_gateway_connection(connection_id, data, user):
    """
    Update IBM Cloud
    This request updates Transit Gateway Connection on IBM Cloud
    """
    abort(404)


@ibm_transit_gateways.post('/prefix_filters')
@authenticate
@input(IBMTransitGatewayConnectionPrefixFilterInSchema)
@output(WorkflowRootOutSchema, status_code=202)
def create_ibm_transit_gateway_connection_prefix_filter(data, user):
    """
    Create IBM Transit gateway Connection Prefix Filter
    This request create Transit Gateway Connection Prefix Filter on VPC+
    """
    cloud_id = data["ibm_cloud"]["id"]
    transit_gateway_id = data["transit_gateway"]["id"]
    connection_id = data["transit_gateway_connection"]["id"]

    transit_gateway = ibmdb.session.query(IBMTransitGateway).filter_by(id=transit_gateway_id, cloud_id=cloud_id).first()
    if not transit_gateway:
        message = f"IBM Transit Gateway with ID {transit_gateway_id} does not exist"
        LOGGER.debug(message)
        abort(404, message)

    transit_gateway_connection: IBMTransitGatewayConnection = ibmdb.session.query(IBMTransitGatewayConnection). \
        filter_by(id=connection_id).join(IBMTransitGatewayConnection.ibm_cloud). \
        filter_by(user_id=user["id"], project_id=user["project_id"], deleted=False) \
        .first()

    if not transit_gateway_connection:
        message = f"IBM Transit Gateway Connection with ID {connection_id} does not exist"
        LOGGER.debug(message)
        abort(404, message)

    authorize_and_get_ibm_cloud(cloud_id=cloud_id, user=user)

    verify_references(
        cloud_id=cloud_id, body_schema=IBMTransitGatewayConnectionPrefixFilterInSchema,
        resource_schema=IBMTransitGatewayConnectionPrefixFilterResourceSchema,
        data=data
    )

    workflow_root = create_ibm_resource_creation_workflow(
        user=user, resource_type=IBMTransitGatewayConnectionPrefixFilter, data=data, validate=False
    )
    return workflow_root.to_json()


@ibm_transit_gateways.get('/prefix_filters/<filter_id>')
@authenticate
@output(IBMTransitGatewayConnectionPrefixFilterOutSchema)
def get_ibm_transit_gateway_connection_prefix_filter(filter_id, user):
    """
    Get an IBM Transit Gateway Connection Prefix Filter
    This request returns an IBM Transit Gateway Connection Prefix Filter provided by its ID i-e filter_id
    """
    transit_gateway_connection_prefix_filter: IBMTransitGatewayConnectionPrefixFilter = ibmdb.session.query(
        IBMTransitGatewayConnectionPrefixFilter). \
        filter_by(id=filter_id).join(
        IBMTransitGatewayConnectionPrefixFilter.ibm_cloud).filter_by(
        user_id=user["id"], project_id=user["project_id"], deleted=False
    ).first()
    if not transit_gateway_connection_prefix_filter:
        message = f"IBM Transit Gateway Connection Prefix Filter With ID {filter_id} does not exist"
        LOGGER.debug(message)
        abort(404, message)

    return transit_gateway_connection_prefix_filter.to_json()


@ibm_transit_gateways.get('/prefix_filters')
@authenticate
@input(IBMTransitGatewayConnectionQuerySchema, location='query')
@input(PaginationQuerySchema, location='query')
@output(get_pagination_schema(IBMTransitGatewayConnectionPrefixFilterOutSchema))
def list_ibm_transit_gateway_connection_prefix_filters(transit_gateway_connection_query_params, pagination_query_params,
                                                       user):
    """
    List IBM Transit Gateways Connection Prefix Filters
    This request lists all IBM Transit Gateways Connection Prefix Filters for the project of the authenticated user
    calling the API
    """
    cloud_id = transit_gateway_connection_query_params["cloud_id"]
    transit_gateway_id = transit_gateway_connection_query_params["transit_gateway_id"]
    transit_gateway_connection_id = transit_gateway_connection_query_params["transit_gateway_connection_id"]

    authorize_and_get_ibm_cloud(cloud_id=cloud_id, user=user)

    transit_gateway_connections_prefix_filter_query = ibmdb.session.query(
        IBMTransitGatewayConnectionPrefixFilter).filter_by(cloud_id=cloud_id).join(
        IBMTransitGatewayConnection).filter_by(id=transit_gateway_connection_id).join(
        IBMTransitGateway).filter_by(id=transit_gateway_id)
    if not transit_gateway_connections_prefix_filter_query:
        message = f"IBM Transit Gateway Connection Prefix Filter with {transit_gateway_connection_id} does not exist"
        LOGGER.debug(message)
        abort(404, message)

    transit_gateway_connections_prefix_filters_page = transit_gateway_connections_prefix_filter_query.paginate(
        page=pagination_query_params["page"], per_page=pagination_query_params["per_page"], error_out=False
    )
    if not transit_gateway_connections_prefix_filters_page.items:
        return '', 204

    return get_paginated_response_json(
        items=[item.to_json() for item in transit_gateway_connections_prefix_filters_page.items],
        pagination_obj=transit_gateway_connections_prefix_filters_page
    )


@ibm_transit_gateways.delete('/prefix_filters/<filter_id>')
@authenticate
@output(WorkflowRootOutSchema, status_code=202)
def delete_ibm_transit_gateway_connection_prefix_filter(filter_id, user):
    """
    Delete an IBM Transit Gateway Connection Prefix Filter
    This request deletes an IBM Transit Gateway Connection Prefix Filter By its ID
    """
    transit_gateway_connection_prefix_filter: IBMTransitGatewayConnectionPrefixFilter = ibmdb.session.query(
        IBMTransitGatewayConnectionPrefixFilter).filter_by(id=filter_id).first()
    if not transit_gateway_connection_prefix_filter:
        message = f"IBM Transit Gateway Connection Prefix Filter with ID {filter_id} does not exist"
        LOGGER.debug(message)
        abort(404, message)

    authorize_and_get_ibm_cloud(cloud_id=transit_gateway_connection_prefix_filter.cloud_id, user=user)

    return compose_ibm_resource_deletion_workflow(
        user=user, resource_type=IBMTransitGatewayConnectionPrefixFilter, resource_id=filter_id
    ).to_json(metadata=True)


@ibm_transit_gateways.patch('/prefix_filters/<filter_id>')
@authenticate
@input(IBMTransitGatewayConnectionPrefixFilterResourceSchema)
@output(WorkflowRootOutSchema, status_code=202)
def update_transit_gateway_connection_prefix_filter(filter_id, data, user):
    """
    Update IBM Cloud
    This request updates an IBM Transit Gateway Connection Prefix Filter IBM Cloud
    """
    abort(404)


@ibm_transit_gateways.get('/transit_connections')
@authenticate
@input(IBMRegionalResourceListQuerySchema, location='query')
@input(PaginationQuerySchema, location='query')
@output(get_pagination_schema(IBMListTransitConnectionOutSchema))
def list_ibm_transit_connections(res_query_params, pagination_query_params, user):
    """
    List IBM Transit Connections
    This request lists all IBM Transit Connections on IBM Cloud for the project of the authenticated user calling the
     API
    """
    cloud_id = res_query_params["cloud_id"]
    authorize_and_get_ibm_cloud(cloud_id=cloud_id, user=user)

    transit_gateway_connections_query = ibmdb.session.query(IBMTransitGatewayConnection).filter_by(cloud_id=cloud_id)
    if not transit_gateway_connections_query:
        message = f"IBM Transit Gateway Connection with Cloud ID {cloud_id} does not exist"
        LOGGER.debug(message)
        abort(404, message)

    transit_gateway_connections_page = transit_gateway_connections_query.paginate(
        page=pagination_query_params["page"], per_page=pagination_query_params["per_page"], error_out=False
    )
    if not transit_gateway_connections_page.items:
        return '', 204

    return get_paginated_response_json(
        items=[item.to_json() for item in transit_gateway_connections_page.items],
        pagination_obj=transit_gateway_connections_page
    )


@ibm_transit_gateways.get("/softlayer_clouds/<softlayer_cloud_id>/validate_vpc_prefixes")
@authenticate
def validate_vpc_prefixes(softlayer_cloud_id, user):
    """
    Validate VPC Prefixes
    This API lists all Prohibited Prefixes and Subnet IP addresses which should not be created as a prefix Filter in VPC
    connection to avoid overlapping with the Classic Infrastructure Resources
    """
    prohibited_blocks = ['10.0.0.0/14', '10.200.0.0/14', '10.198.0.0/15', '10.254.0.0/16']

    softlayer_cloud_account = ibmdb.session.query(SoftlayerCloud).filter_by(user_id=user["id"],
                                                                            project_id=user["project_id"],
                                                                            id=softlayer_cloud_id,
                                                                            status=SoftlayerCloud.STATUS_VALID).first()
    if not softlayer_cloud_account:
        message = f"SoftlayerCloud: {softlayer_cloud_id} does not exist OR Not Valid"
        LOGGER.info(message)
        abort(404, message)

    subnet_client = SoftlayerSubnetClient(softlayer_cloud_id)
    classic_infrastructure_subnets = subnet_client.list_private_subnets()
    for subnet in classic_infrastructure_subnets:
        prohibited_blocks.append(subnet.address)

    return jsonify({"Prohibited_Prefixes_In_VPC_Connection": prohibited_blocks})


@ibm_transit_gateways.post('/route_reports')
@authenticate
@input(IBMTransitGatewayRouteReportInSchema)
@output(WorkflowRootOutSchema, status_code=202)
def create_transit_gateway_route_report(data, user):
    """
    Create IBM Transit gateway Route Report
    This request Creates (Generate) an IBM Transit Gateway Route Report with VPC+
    """
    cloud_id = data["ibm_cloud"]["id"]
    transit_gateway_id = data["resource_json"]["transit_gateway"]["id"]

    transit_gateway = ibmdb.session.query(IBMTransitGateway).filter_by(id=transit_gateway_id, cloud_id=cloud_id).first()
    if not transit_gateway:
        message = f"IBM Transit Gateway with ID {transit_gateway_id} does not exist"
        LOGGER.debug(message)
        abort(404, message)

    authorize_and_get_ibm_cloud(cloud_id=cloud_id, user=user)

    verify_references(
        cloud_id=cloud_id, body_schema=IBMTransitGatewayRouteReportInSchema,
        resource_schema=IBMTransitGatewayRouteReportResourceSchema,
        data=data
    )

    workflow_root = create_ibm_resource_creation_workflow(
        user=user, resource_type=IBMTransitGatewayRouteReport, data=data, validate=False
    )
    return workflow_root.to_json()


@ibm_transit_gateways.get('/route_reports/<route_report_id>')
@authenticate
@output(IBMTransitGatewayRouteReportOutSchema)
def get_ibm_transit_gateway_route_report(route_report_id, user):
    """
    Get an IBM Transit Gateway Route Report
    This request returns an IBM Transit Gateway Route Report provided its ID
    """

    transit_gateway_route_report: IBMTransitGatewayRouteReport = ibmdb.session.query(IBMTransitGatewayRouteReport). \
        filter_by(id=route_report_id).join(IBMTransitGatewayRouteReport.ibm_cloud). \
        filter_by(user_id=user["id"], project_id=user["project_id"], deleted=False) \
        .first()
    if not transit_gateway_route_report:
        message = f"IBM Transit Gateway Route Report with ID {route_report_id} does not exist"
        LOGGER.debug(message)
        abort(404, message)

    return transit_gateway_route_report.to_json()


@ibm_transit_gateways.get('/route_reports')
@authenticate
@input(IBMTransitGatewayConnectionQuerySchema(only=['transit_gateway_id']), location='query')
@input(IBMRegionalResourceListQuerySchema, location='query')
@input(PaginationQuerySchema, location='query')
@output(get_pagination_schema(IBMTransitGatewayRouteReportOutSchema))
def list_ibm_transit_gateway_route_reports(transit_gateway_query_param,
                                           res_query_params, pagination_query_params, user):
    """
    List IBM Transit Gateway Route Reports
    This request lists all IBM Transit Gateway Routes Reports for the project of the authenticated user calling the API
    """
    cloud_id = res_query_params["cloud_id"]
    region_id = res_query_params.get("region_id")
    transit_gateway_id = transit_gateway_query_param["transit_gateway_id"]
    ibm_cloud = authorize_and_get_ibm_cloud(cloud_id=cloud_id, user=user)

    transit_gateway_route_report_query = ibmdb.session.query(IBMTransitGatewayRouteReport).filter_by(
        transit_gateway_id=transit_gateway_id, cloud_id=cloud_id)

    if not transit_gateway_route_report_query:
        message = f"IBM Transit Gateway Route Report with Transit Gateway ID {transit_gateway_id} does not exist"
        LOGGER.debug(message)
        abort(404, message)

    if region_id:
        verify_and_get_region(ibm_cloud=ibm_cloud, region_id=region_id)
        transit_gateway_route_report_query = transit_gateway_route_report_query.filter_by(region_id=region_id)

    transit_gateway_route_report_page = transit_gateway_route_report_query.paginate(
        page=pagination_query_params["page"], per_page=pagination_query_params["per_page"], error_out=False
    )
    if not transit_gateway_route_report_page.items:
        return '', 204

    return get_paginated_response_json(
        items=[item.to_json() for item in transit_gateway_route_report_page.items],
        pagination_obj=transit_gateway_route_report_page
    )


@ibm_transit_gateways.delete('/route_reports/<route_report_id>')
@authenticate
@output(WorkflowRootOutSchema, status_code=202)
def delete_ibm_transit_gateway_route_report(route_report_id, user):
    """
    Delete an IBM Transit Gateway Route Report
    This request deletes an IBM Transit Gateway Connection provided its ID

    """
    transit_gateway_route_report: IBMTransitGatewayRouteReport = ibmdb.session.query(IBMTransitGatewayRouteReport). \
        filter_by(id=route_report_id).join(IBMTransitGatewayRouteReport.ibm_cloud). \
        filter_by(user_id=user["id"], project_id=user["project_id"], deleted=False) \
        .first()
    if not transit_gateway_route_report:
        message = f"IBM Transit Gateway Route Report with ID {route_report_id} does not exist"
        LOGGER.debug(message)
        abort(404, message)

    return compose_ibm_resource_deletion_workflow(
        user=user, resource_type=IBMTransitGatewayRouteReport, resource_id=route_report_id,
    ).to_json(metadata=True)
