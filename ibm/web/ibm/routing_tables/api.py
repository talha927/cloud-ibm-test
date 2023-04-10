import logging

from apiflask import abort, APIBlueprint, input, output

from ibm.auth import authenticate
from ibm.common.req_resp_schemas.schemas import get_pagination_schema, IBMVPCRegionalResourceListQuerySchema, \
    PaginationQuerySchema, WorkflowRootOutSchema
from ibm.middleware import log_activity
from ibm.models import IBMRoutingTable, IBMRoutingTableRoute, IBMVpcNetwork
from ibm.web import db as ibmdb
from ibm.web.common.utils import authorize_and_get_ibm_cloud, compose_ibm_resource_deletion_workflow, \
    create_ibm_resource_creation_workflow, get_paginated_response_json, verify_and_get_region, \
    verify_nested_references, verify_references
from ibm.web.ibm.routing_tables.schemas import IBMRoutingTableInSchema, IBMRoutingTableOutSchema, \
    IBMRoutingTableResourceSchema, IBMRoutingTableRouteInSchema, IBMRoutingTableRouteListQuerySchema, \
    IBMRoutingTableRouteOutSchema

LOGGER = logging.getLogger(__name__)
ibm_routing_tables = APIBlueprint('ibm_routing_tables', __name__, tag="IBM Routing Tables")


@ibm_routing_tables.post('/routing_tables')
@authenticate
@log_activity
@input(IBMRoutingTableInSchema)
@output(WorkflowRootOutSchema, status_code=202)
def create_ibm_routing_table(data, user):
    """
    Create an IBM Routing Table
    This request creates an IBM Routing table on IBM Cloud.
    """

    cloud_id = data["ibm_cloud"]["id"]
    region_id = data["region"]["id"]

    ibm_cloud = authorize_and_get_ibm_cloud(cloud_id=cloud_id, user=user)
    verify_and_get_region(ibm_cloud=ibm_cloud, region_id=region_id)

    verify_references(
        cloud_id=cloud_id, body_schema=IBMRoutingTableInSchema, resource_schema=IBMRoutingTableResourceSchema,
        data=data
    )
    for route_data in data["resource_json"].get("routes", []):
        verify_nested_references(
            cloud_id=cloud_id, nested_resource_schema=IBMRoutingTableRouteInSchema, data=route_data
        )

    workflow_root = create_ibm_resource_creation_workflow(
        user=user, resource_type=IBMRoutingTable, data=data, validate=False
    )
    return workflow_root.to_json()


@ibm_routing_tables.get('/routing_tables')
@authenticate
@input(IBMVPCRegionalResourceListQuerySchema, location='query')
@input(PaginationQuerySchema, location='query')
@output(get_pagination_schema(IBMRoutingTableOutSchema))
def list_ibm_routing_tables(vpc_regional_res_query_params, pagination_query_params, user):
    """
    List IBM Routing Tables
    This request lists IBM Routing Tables according to the query params.
    """
    cloud_id = vpc_regional_res_query_params["cloud_id"]
    region_id = vpc_regional_res_query_params.get("region_id")
    vpc_id = vpc_regional_res_query_params.get("vpc_id")

    ibm_cloud = authorize_and_get_ibm_cloud(cloud_id=cloud_id, user=user)
    routing_tables_query = ibmdb.session.query(IBMRoutingTable).filter_by(cloud_id=cloud_id)

    if region_id:
        verify_and_get_region(ibm_cloud=ibm_cloud, region_id=region_id)
        routing_tables_query = routing_tables_query.filter_by(region_id=region_id)

    if vpc_id:
        if not ibmdb.session.query(IBMVpcNetwork).filter_by(id=vpc_id).first():
            message = f"IBM VPC {vpc_id} does not exist"
            LOGGER.debug(message)
            abort(404, message)

        routing_tables_query = routing_tables_query.filter_by(vpc_id=vpc_id)

    routing_tables_page = routing_tables_query.paginate(
        page=pagination_query_params["page"], per_page=pagination_query_params["per_page"], error_out=False
    )
    if not routing_tables_page.items:
        return '', 204

    return get_paginated_response_json(
        items=[item.to_json() for item in routing_tables_page.items],
        pagination_obj=routing_tables_page
    )


@ibm_routing_tables.get('/routing_tables/<routing_table_id>')
@authenticate
@output(IBMRoutingTableOutSchema)
def get_ibm_routing_table(routing_table_id, user):
    """
    Get an IBM Routing Table by ID
    This request returns an IBM Routing Table provided its ID.
    """
    routing_table = ibmdb.session.query(IBMRoutingTable).filter_by(
        id=routing_table_id
    ).join(IBMRoutingTable.ibm_cloud).filter_by(
        user_id=user["id"], project_id=user["project_id"], deleted=False
    ).first()
    if not routing_table:
        message = f"IBM Routing Table {routing_table_id} does not exist"
        LOGGER.debug(message)
        abort(404, message)

    return routing_table.to_json()


@ibm_routing_tables.delete('/routing_tables/<routing_table_id>')
@authenticate
@log_activity
@output(WorkflowRootOutSchema, status_code=202)
def delete_ibm_routing_table(routing_table_id, user):
    """
    Delete an IBM Routing Table
    This request deletes an IBM Routing Table provided its ID.
    """
    routing_table = ibmdb.session.query(IBMRoutingTable).filter_by(
        id=routing_table_id
    ).join(IBMRoutingTable.ibm_cloud).filter_by(
        user_id=user["id"], project_id=user["project_id"], deleted=False
    ).first()
    if not routing_table:
        message = f"IBM Routing Table {routing_table_id} does not exist"
        LOGGER.debug(message)
        abort(404, message)

    return \
        compose_ibm_resource_deletion_workflow(
            user=user, resource_type=IBMRoutingTable, resource_id=routing_table_id
        ).to_json(metadata=True)


@ibm_routing_tables.get('/routing_table_routes')
@authenticate
@input(IBMRoutingTableRouteListQuerySchema, location='query')
@input(PaginationQuerySchema, location='query')
@output(get_pagination_schema(IBMRoutingTableRouteOutSchema))
def list_ibm_routing_table_routes(route_list_query_params, pagination_query_params, user):
    """
    List Routes of a specified IBM Routing Table
    This request returns all routes of an IBM routing table specified by its ID.
    """
    routing_table_id = route_list_query_params["routing_table_id"]
    cloud_id = route_list_query_params["cloud_id"]
    routing_table = ibmdb.session.query(IBMRoutingTable).filter_by(
        id=routing_table_id
    ).join(IBMRoutingTable.ibm_cloud).filter_by(
        id=cloud_id, user_id=user["id"], project_id=user["project_id"], deleted=False
    ).first()
    if not routing_table:
        message = f"IBM Routing Table {routing_table_id} does not exist"
        LOGGER.debug(message)
        abort(404, message)

    routes_page = routing_table.routes.paginate(
        page=pagination_query_params["page"], per_page=pagination_query_params["per_page"], error_out=False
    )
    if not routes_page.items:
        return '', 204

    return get_paginated_response_json(
        items=[item.to_json() for item in routes_page.items],
        pagination_obj=routes_page
    )


@ibm_routing_tables.get('/routing_table_routes/<route_id>')
@authenticate
@output(IBMRoutingTableRouteOutSchema)
def get_ibm_routing_table_route(route_id, user):
    """
    Get an IBM Routing Table Route by ID
    This request returns an IBM Routing Table Route provided its ID.
    """
    routing_table_route = ibmdb.session.query(IBMRoutingTableRoute).filter_by(
        id=route_id
    ).join(IBMRoutingTableRoute.ibm_cloud).filter_by(
        user_id=user["id"], project_id=user["project_id"], deleted=False
    ).first()
    if not routing_table_route:
        message = f"IBM Routing Table Route {route_id} does not exist"
        LOGGER.debug(message)
        abort(404, message)

    return routing_table_route.to_json()
