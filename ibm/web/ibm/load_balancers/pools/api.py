import logging

from apiflask import abort, APIBlueprint, doc, input, output

from ibm.auth import authenticate
from ibm.common.req_resp_schemas.schemas import get_pagination_schema, PaginationQuerySchema, WorkflowRootOutSchema
from ibm.models import IBMLoadBalancer, IBMPool
from ibm.web import db as ibmdb
from ibm.web.common.utils import authorize_and_get_ibm_cloud, compose_ibm_resource_deletion_workflow, \
    create_ibm_resource_creation_workflow, get_paginated_response_json, verify_and_get_region, verify_references
from ibm.web.ibm.load_balancers.pools.schemas import IBMLoadBalancerPoolHealthMonitorOutSchema, \
    IBMLoadBalancerPoolInSchema, IBMLoadBalancerPoolListQuerySchema, IBMLoadBalancerPoolOutSchema, \
    IBMLoadBalancerPoolResourceSchema, IBMLoadBalancerPoolUpdateSchema

LOGGER = logging.getLogger(__name__)

ibm_lb_pools = APIBlueprint('ibm_lb_pools', __name__, tag="IBM Load Balancers")


@ibm_lb_pools.post("/load_balancer_pools")
@authenticate
@input(IBMLoadBalancerPoolInSchema)
@output(WorkflowRootOutSchema, status_code=202)
def create_load_balancer_pool(data, user):
    """
    Create an IBM Load Balancer Pool
    This request creates an IBM Load Balancer Pool with VPC+ on IBM Cloud.
    """
    cloud_id = data["ibm_cloud"]["id"]
    region_id = data["region"]["id"]
    load_balancer_id = data["load_balancer"]["id"]

    ibm_cloud = authorize_and_get_ibm_cloud(cloud_id=cloud_id, user=user)
    verify_and_get_region(ibm_cloud, region_id)

    load_balancer: IBMLoadBalancer = ibmdb.session.query(IBMLoadBalancer).filter_by(id=load_balancer_id,
                                                                                    cloud_id=cloud_id).first()
    if not load_balancer:
        message = f"IBM Load Balancer {load_balancer_id} does not exist."
        LOGGER.debug(message)
        abort(404, message)

    # TODO: may be validation task
    if load_balancer.family == "Network" and data["resource_json"]["protocol"] != "tcp":
        message = "IBM Load Balancer with family 'Network' only support protocol: 'tcp'"
        LOGGER.debug(message)
        abort(404, message)

    verify_references(
        cloud_id=cloud_id, body_schema=IBMLoadBalancerPoolInSchema,
        resource_schema=IBMLoadBalancerPoolResourceSchema, data=data
    )

    workflow_root = create_ibm_resource_creation_workflow(
        user=user, resource_type=IBMPool, data=data, validate=False
    )
    return workflow_root.to_json()


@ibm_lb_pools.get("/load_balancer_pools")
@authenticate
@input(IBMLoadBalancerPoolListQuerySchema, location='query')
@input(PaginationQuerySchema, location='query')
@output(get_pagination_schema(IBMLoadBalancerPoolOutSchema))
@doc(
    responses={
        204: "No records found"
    }
)
def list_load_balancer_pools(regional_res_query_params, pagination_query_params, user):
    """
    List IBM Load Balancer Pools for an IBM Load Balancer
    This request lists all IBM Load Balancer Pools for the project of the authenticated user calling the API.
    """
    cloud_id = regional_res_query_params["cloud_id"]
    load_balancer_id = regional_res_query_params.get("load_balancer_id")
    protocol = regional_res_query_params.get("protocol")

    authorize_and_get_ibm_cloud(cloud_id=cloud_id, user=user)
    filters = {
        "cloud_id": cloud_id
    }

    if load_balancer_id:
        load_balancer = ibmdb.session.query(IBMLoadBalancer).get(load_balancer_id)
        if not load_balancer:
            message = f"IBM Load Balancer {load_balancer_id} does not exist."
            LOGGER.debug(message)
            abort(404, message)

        filters["load_balancer_id"] = load_balancer_id

    if protocol:
        filters["protocol"] = protocol

    load_balancer_pools_query = ibmdb.session.query(IBMPool).filter_by(**filters)
    load_balancer_pools_page = load_balancer_pools_query.paginate(
        page=pagination_query_params["page"], per_page=pagination_query_params["per_page"], error_out=False
    )

    if not load_balancer_pools_page.items:
        return '', 204

    return get_paginated_response_json(
        items=[item.to_json() for item in load_balancer_pools_page.items],
        pagination_obj=load_balancer_pools_page
    )


@ibm_lb_pools.get("/load_balancer_pools/<pool_id>")
@authenticate
@output(IBMLoadBalancerPoolOutSchema)
def get_load_balancer_pool(pool_id, user):
    """
    Get an IBM Load Balancer Pool
    This request returns an IBM Load Balancer Pool provided its ID.
    """
    pool = ibmdb.session.query(IBMPool).filter_by(
        id=pool_id
    ).join(IBMPool.ibm_cloud).filter_by(
        user_id=user["id"], project_id=user["project_id"], deleted=False).first()
    if not pool:
        message = f"IBM Pool {pool_id} does not exist"
        LOGGER.debug(message)
        abort(404, message)

    return pool.to_json()


@ibm_lb_pools.get("/load_balancer_pools/<pool_id>/health_monitor")
@authenticate
@output(IBMLoadBalancerPoolHealthMonitorOutSchema)
def get_load_balancer_pool_heath_monitor(pool_id, user):
    """
    Get an IBM Load Balancer Pool Health Monitor
    This request returns an IBM Load Balancer Pool Health Monitor provided its ID.
    """
    pool: IBMPool = ibmdb.session.query(IBMPool).filter_by(
        id=pool_id
    ).join(IBMPool.ibm_cloud).filter_by(
        user_id=user["id"], project_id=user["project_id"], deleted=False).first()
    if not pool:
        message = f"IBM Pool {pool_id} does not exist"
        LOGGER.debug(message)
        abort(404, message)

    if not pool.health_monitor:
        message = f"Health Monitor for IBM Pool {pool_id} does not exist"
        LOGGER.debug(message)
        abort(204, message)

    return pool.health_monitor.to_json()


@ibm_lb_pools.patch("/load_balancer_pools/<pool_id>")
@authenticate
@input(IBMLoadBalancerPoolUpdateSchema)
@output(WorkflowRootOutSchema, status_code=202)
def update_load_balancer_pool(pool_id, data, user):
    """
    Update an IBM Load Balancer Pool
    This request updates an IBM Load Balancer Pool
    """
    abort(404)


@ibm_lb_pools.delete("/load_balancer_pools/<pool_id>")
@authenticate
@output(WorkflowRootOutSchema, status_code=202)
def delete_load_balancer_pool(pool_id, user):
    """
    Delete an IBM Load Balancer Pool
    This request deletes an IBM Load Balancer Pool provided its ID.
    """
    pool = ibmdb.session.get(IBMPool, pool_id)
    if not pool:
        message = f"IBM Pool {pool_id} does not exist"
        LOGGER.debug(message)
        abort(404, message)

    authorize_and_get_ibm_cloud(cloud_id=pool.ibm_cloud.id, user=user)

    return compose_ibm_resource_deletion_workflow(
        user=user, resource_type=IBMPool, resource_id=pool_id
    ).to_json(metadata=True)
