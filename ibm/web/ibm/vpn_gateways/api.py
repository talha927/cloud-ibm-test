import logging

from apiflask import abort, APIBlueprint, input, output

from ibm.auth import authenticate
from ibm.common.req_resp_schemas.schemas import get_pagination_schema, IBMRegionalResourceListQuerySchema, \
    IBMResourceQuerySchema, IBMVpnQueryParamSchema, PaginationQuerySchema, WorkflowRootOutSchema
from ibm.middleware import log_activity
from ibm.models import IBMVpnConnection, IBMVpnGateway, WorkflowTask
from ibm.web import db as ibmdb
from ibm.web.common.utils import authorize_and_get_ibm_cloud, compose_ibm_resource_deletion_workflow, \
    create_ibm_resource_creation_workflow, get_paginated_response_json, verify_and_get_region, verify_references
from .schemas import IBMVpnGatewayConnectionInSchema, IBMVpnGatewayConnectionOutSchema, \
    IBMVpnGatewayConnectionsResourceSchema, IBMVpnGatewayInSchema, IBMVpnGatewayOutSchema, \
    IBMVpnGatewaysResourceSchema, IBMVpnQuerySchema, UpdateIBMVpnGatewayConnectionsResourceSchema, \
    UpdateIBMVpnGatewaysResourceSchema

LOGGER = logging.getLogger(__name__)
ibm_vpn_gateways = APIBlueprint('ibm_vpn_gateways', __name__, tag="IBM Vpn Gateways")


@ibm_vpn_gateways.post('/vpn_gateways')
@authenticate
@log_activity
@input(IBMVpnGatewayInSchema)
@output(WorkflowRootOutSchema, status_code=202)
def create_ibm_vpn_gateway(data, user):
    """
    Create a VPN gateway
    This request creates a new VPN gateway.
    """
    cloud_id = data["ibm_cloud"]["id"]
    region_id = data["region"]["id"]
    resource_json = data["resource_json"]

    ibm_cloud = authorize_and_get_ibm_cloud(cloud_id=cloud_id, user=user)
    verify_and_get_region(ibm_cloud=ibm_cloud, region_id=region_id)

    verify_references(
        cloud_id=cloud_id, body_schema=IBMVpnGatewayInSchema, resource_schema=IBMVpnGatewaysResourceSchema, data=data
    )

    workflow_root = create_ibm_resource_creation_workflow(
        user=user, resource_type=IBMVpnGateway, data=data, validate=False)
    for connection in resource_json.get("connections", []):
        connection_data = {
            "ibm_cloud": {"id": cloud_id},
            "region": {"id": region_id},
            "vpn_gateway": {"name": resource_json["name"]},
            "resource_json": connection
        }

        conn_creation_task = WorkflowTask(
            task_type=WorkflowTask.TYPE_CREATE, resource_type=IBMVpnConnection.__name__,
            task_metadata={"resource_data": connection_data}
        )

        creation_task = workflow_root.next_tasks[0]
        creation_task.add_next_task(conn_creation_task)
        ibmdb.session.commit()

    return workflow_root.to_json()


@ibm_vpn_gateways.get('/vpn_gateways')
@authenticate
@input(IBMRegionalResourceListQuerySchema, location='query')
@input(PaginationQuerySchema, location='query')
@output(get_pagination_schema(IBMVpnGatewayOutSchema))
def list_ibm_vpn_gateways(regional_res_query_params, pagination_query_params, user):
    """
    List all VPN gateways
    This request lists all VPN gateways in the region.
    """
    cloud_id = regional_res_query_params["cloud_id"]
    region_id = regional_res_query_params.get("region_id")

    ibm_cloud = authorize_and_get_ibm_cloud(cloud_id=cloud_id, user=user)
    vpn_gateway_query = ibmdb.session.query(IBMVpnGateway).filter_by(cloud_id=cloud_id)

    if region_id:
        verify_and_get_region(ibm_cloud=ibm_cloud, region_id=region_id)
        vpn_gateway_query = vpn_gateway_query.filter_by(region_id=region_id)

    vpn_gateways_page = vpn_gateway_query.paginate(
        page=pagination_query_params["page"], per_page=pagination_query_params["per_page"], error_out=False
    )
    if not vpn_gateways_page.items:
        return '', 204

    return get_paginated_response_json(
        items=[item.to_json() for item in vpn_gateways_page.items],
        pagination_obj=vpn_gateways_page
    )


@ibm_vpn_gateways.get('/vpn_gateways/<vpn_gateway_id>')
@authenticate
@output(IBMVpnGatewayOutSchema)
def get_ibm_vpn_gateway(vpn_gateway_id, user):
    """
    Retrieve a VPN gateway
    This request retrieves a single VPN gateway specified by the identifier in the URL.
    """
    vpn_gateway = ibmdb.session.query(IBMVpnGateway).filter_by(
        id=vpn_gateway_id
    ).join(IBMVpnGateway.ibm_cloud).filter_by(
        user_id=user["id"], project_id=user["project_id"], deleted=False
    ).first()
    if not vpn_gateway:
        message = f"IBM Vpn Gateway {vpn_gateway_id} does not exist"
        LOGGER.debug(message)
        abort(404, message)

    return vpn_gateway.to_json()


@ibm_vpn_gateways.route('/vpn_gateways/<vpn_gateway_id>', methods=['PATCH'])
@authenticate
@input(UpdateIBMVpnGatewaysResourceSchema)
@output(WorkflowRootOutSchema, status_code=202)
def update_ibm_vpn_gateway(vpn_gateway_id, data, user):
    """
    Update a VPN gateway
    This request updates the properties of an existing VPN gateway.
    """
    abort(404)


@ibm_vpn_gateways.delete('/vpn_gateways/<vpn_gateway_id>')
@authenticate
@log_activity
@output(WorkflowRootOutSchema, status_code=202)
def delete_ibm_vpn_gateway(vpn_gateway_id, user):
    """
    Delete a VPN gateway
    This request deletes a VPN gateway.
    """
    vpn_gateway = ibmdb.session.query(IBMVpnGateway).filter_by(
        id=vpn_gateway_id
    ).join(IBMVpnGateway.ibm_cloud).filter_by(
        user_id=user["id"], project_id=user["project_id"], deleted=False
    ).first()

    if not vpn_gateway:
        message = f"IBM Vpn Gateway {vpn_gateway_id} does not exist"
        LOGGER.debug(message)
        abort(404, message)

    # TODO will add this check once update call is done
    # if not vpn_gateway.is_deletable:
    #     message = f"This Vpn Gateway '{vpn_gateway_id}' has attached Connections. " \
    #               f"Please delete them and try again later."
    #     LOGGER.debug(message)
    #     abort(404, message)

    return compose_ibm_resource_deletion_workflow(
        user=user, resource_type=IBMVpnGateway, resource_id=vpn_gateway_id
    ).to_json(metadata=True)


@ibm_vpn_gateways.post('/vpn_connections')
@authenticate
@input(IBMVpnGatewayConnectionInSchema)
@output(WorkflowRootOutSchema, status_code=202)
def create_ibm_vpn_gateway_connection(data, user):
    """
    Create a connection for a VPN gateway
    This request creates a new VPN gateway connection.
    """
    cloud_id = data["ibm_cloud"]["id"]
    vpn_gateway_id = data["vpn_gateway"]["id"]

    authorize_and_get_ibm_cloud(cloud_id=cloud_id, user=user)

    vpn_gateway = ibmdb.session.query(IBMVpnGateway).filter_by(id=vpn_gateway_id, cloud_id=cloud_id).first()
    if not vpn_gateway:
        message = f"IBM vpn gateway {vpn_gateway_id} does not exist"
        LOGGER.debug(message)
        abort(404, message)

    verify_references(
        cloud_id=cloud_id, body_schema=IBMVpnGatewayConnectionInSchema,
        resource_schema=IBMVpnGatewayConnectionsResourceSchema, data=data
    )

    workflow_root = create_ibm_resource_creation_workflow(
        user=user, resource_type=IBMVpnConnection, data=data, validate=False
    )
    return workflow_root.to_json()


@ibm_vpn_gateways.get('/vpn_connections')
@authenticate
@input(IBMVpnQuerySchema, location='query')
@input(PaginationQuerySchema, location='query')
@output(get_pagination_schema(IBMVpnGatewayConnectionOutSchema))
def list_ibm_vpn_gateway_connections(vpn_id_query_params, pagination_query_params, user):
    """
    List all connections of a VPN gateway
    This request lists all connections of a VPN gateway.
    """
    cloud_id = vpn_id_query_params["cloud_id"]
    vpn_id = vpn_id_query_params["vpn_id"]

    authorize_and_get_ibm_cloud(cloud_id=cloud_id, user=user)

    vpn_query = ibmdb.session.query(IBMVpnGateway).filter_by(id=vpn_id, cloud_id=cloud_id)
    if not vpn_query:
        message = f"IBM vpn {vpn_id} does not exist"
        LOGGER.debug(message)
        abort(404, message)

    vpn_connections_query = ibmdb.session.query(IBMVpnConnection).filter_by(vpn_gateway_id=vpn_id)

    vpn_connections_page = vpn_connections_query.paginate(
        page=pagination_query_params["page"], per_page=pagination_query_params["per_page"], error_out=False
    )
    if not vpn_connections_page.items:
        return '', 204

    return get_paginated_response_json(
        items=[item.to_json() for item in vpn_connections_page.items],
        pagination_obj=vpn_connections_page
    )


@ibm_vpn_gateways.get('/vpn_connections/<vpn_connection_id>')
@authenticate
@output(IBMVpnGatewayConnectionOutSchema)
def get_ibm_vpn_gateway_connection(vpn_connection_id, user):
    """
    Retrieve a VPN gateway connection
    This request retrieves a single VPN gateway connection specified by the identifier in the URL.
    """
    vpn_gateway_connection = ibmdb.session.query(IBMVpnConnection).filter_by(
        id=vpn_connection_id). \
        join(IBMVpnGateway.ibm_cloud).filter_by(
        user_id=user["id"], project_id=user["project_id"], deleted=False).first()
    if not vpn_gateway_connection:
        message = f"IBM Vpn connection {vpn_connection_id} does not exist"
        LOGGER.debug(message)
        abort(404, message)

    return vpn_gateway_connection.to_json()


@ibm_vpn_gateways.route('/vpn_connections/<vpn_connection_id>',
                        methods=['PATCH'])
@authenticate
@input(UpdateIBMVpnGatewayConnectionsResourceSchema)
@output(WorkflowRootOutSchema, status_code=202)
def update_ibm_vpn_gateway_connection(vpn_gateway_id, connection_id, data, user):
    """
    Update a VPN gateway connection
    This request updates the properties of an existing VPN gateway connection.
    """
    abort(404)


@ibm_vpn_gateways.delete('/vpn_connections/<vpn_connection_id>')
@authenticate
@output(WorkflowRootOutSchema, status_code=202)
def delete_ibm_vpn_gateway_connection(vpn_connection_id, user):
    """
    Delete a VPN gateway connection
    This request deletes a VPN gateway connection. This operation cannot be reversed.
    """
    connection = ibmdb.session.query(IBMVpnConnection).filter_by(id=vpn_connection_id).first()

    if not connection:
        message = f"IBM Vpn Connection {vpn_connection_id} does not exist"
        LOGGER.debug(message)
        abort(404, message)

    authorize_and_get_ibm_cloud(cloud_id=connection.vpn_gateway.ibm_cloud.id, user=user)

    return compose_ibm_resource_deletion_workflow(
        user=user, resource_type=IBMVpnConnection, resource_id=vpn_connection_id
    ).to_json(metadata=True)


@ibm_vpn_gateways.route('/local_cidrs', methods=["GET"])
@authenticate
@input(IBMVpnQueryParamSchema(only=("vpn_gateway_id", "connection_id")), location='query')
@input(IBMResourceQuerySchema, location='query')
@input(PaginationQuerySchema, location='query')
@output(get_pagination_schema(IBMVpnGatewayConnectionsResourceSchema(only=("local_cidrs",))))
def list_ibm_vpn_gateway_connection_local_cidrs(vpn_query_params, connection_query_params, listing_query_params,
                                                pagination_query_params, user):
    """
    List all local CIDRs for a VPN gateway connection
    This request lists all local CIDRs for a VPN gateway connection.
    """
    abort(404)


@ibm_vpn_gateways.route('/local_cidrs/<cidr_prefix>/<prefix_length>', methods=['DELETE'])
@authenticate
@input(IBMVpnQueryParamSchema(only=("vpn_gateway_id", "connection_id")), location='query')
@output(WorkflowRootOutSchema, status_code=202)
def delete_ibm_vpn_gateway_connection_local_cidr(cidr_prefix, prefix_length, vpn_query_params, connection_query_params,
                                                 user):
    """
    Remove a local CIDR from a VPN gateway connection
    This request removes a CIDR from a VPN gateway connection.
    """
    abort(404)


@ibm_vpn_gateways.route('/local_cidrs/<cidr_prefix>/<prefix_length>', methods=['GET'])
@authenticate
@input(IBMVpnQueryParamSchema(only=("vpn_gateway_id", "connection_id")), location='query')
@output(IBMVpnGatewayConnectionsResourceSchema(only=("local_cidrs",)))
def get_ibm_vpn_gateway_connection_local_cidr(cidr_prefix, prefix_length, vpn_query_params, connection_query_params,
                                              user):
    """
    Check if the specified local CIDR exists on a VPN gateway connection
    This request succeeds if a CIDR exists on the specified VPN gateway connection and fails otherwise.
    """
    abort(404)


@ibm_vpn_gateways.route('/local_cidrs/<cidr_prefix>/<prefix_length>', methods=['PATCH'])
@authenticate
@input(IBMVpnQueryParamSchema(only=("vpn_gateway_id", "connection_id")), location='query')
@input(IBMVpnGatewayConnectionsResourceSchema(only=("local_cidrs",)))
@output(WorkflowRootOutSchema, status_code=202)
def update_ibm_vpn_gateway_connection_local_cidr(cidr_prefix, prefix_length, vpn_query_params, connection_query_params,
                                                 user):
    """
    Set a local CIDR on a VPN gateway connection
    This request adds the specified CIDR to the specified VPN gateway connection. A request body is not required, and
    if supplied, is ignored. This request succeeds if the CIDR already exists on the specified VPN gateway connection.
    """
    abort(404)


@ibm_vpn_gateways.route('/peer_cidrs', methods=["GET"])
@authenticate
@input(IBMVpnQueryParamSchema(only=("vpn_gateway_id", "connection_id")), location='query')
@input(IBMResourceQuerySchema, location='query')
@input(PaginationQuerySchema, location='query')
@output(get_pagination_schema(IBMVpnGatewayConnectionsResourceSchema(only=("peer_cidrs",))))
def list_ibm_vpn_gateway_connection_peer_cidrs(vpn_query_params, connection_query_params, listing_query_params,
                                               pagination_query_params, user):
    """
    List all peer CIDRs for a VPN gateway connection
    This request lists all peer CIDRs for a VPN gateway connection.
    """
    abort(404)


@ibm_vpn_gateways.route('/peer_cidrs/<cidr_prefix>/<prefix_length>', methods=['DELETE'])
@authenticate
@input(IBMVpnQueryParamSchema(only=("vpn_gateway_id", "connection_id")), location='query')
@output(WorkflowRootOutSchema, status_code=202)
def delete_ibm_vpn_gateway_connection_peer_cidr(cidr_prefix, prefix_length, vpn_query_params, connection_query_params,
                                                user):
    """
    Remove a peer CIDR from a VPN gateway connection
    This request removes a CIDR from a VPN gateway connection.
    """
    abort(404)


@ibm_vpn_gateways.route('/peer_cidrs/<cidr_prefix>/<prefix_length>', methods=['GET'])
@authenticate
@input(IBMVpnQueryParamSchema(only=("vpn_gateway_id", "connection_id")), location='query')
@output(IBMVpnGatewayConnectionsResourceSchema(only=("peer_cidrs",)))
def get_ibm_vpn_gateway_connection_peer_cidr(cidr_prefix, prefix_length, vpn_query_params, connection_query_params,
                                             user):
    """
    Check if the specified peer CIDR exists on a VPN gateway connection
    This request succeeds if a CIDR exists on the specified VPN gateway connection and fails otherwise.
    """
    abort(404)


@ibm_vpn_gateways.route('/peer_cidrs/<cidr_prefix>/<prefix_length>', methods=['PATCH'])
@authenticate
@input(IBMVpnQueryParamSchema(only=("vpn_gateway_id", "connection_id")), location='query')
@input(IBMVpnGatewayConnectionsResourceSchema(only=("peer_cidrs",)))
@output(WorkflowRootOutSchema, status_code=202)
def update_ibm_vpn_gateway_connection_peer_cidr(cidr_prefix, prefix_length, vpn_query_params, connection_query_params,
                                                user):
    """
    Set a peer CIDR on a VPN gateway connection
    This request adds the specified CIDR to the specified VPN gateway connection. A request body is not required, and
    if supplied, is ignored. This request succeeds if the CIDR already exists on the specified VPN gateway connection.
    """
    abort(404)
