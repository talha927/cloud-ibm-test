import logging

from apiflask import abort, APIBlueprint, input, output

from ibm.auth import authenticate
from ibm.common.req_resp_schemas.schemas import get_pagination_schema, PaginationQuerySchema, WorkflowRootOutSchema
from ibm.models import IBMInstance, IBMNetworkInterface, IBMPool, IBMPoolMember
from ibm.web import db as ibmdb
from ibm.web.common.utils import authorize_and_get_ibm_cloud, compose_ibm_resource_deletion_workflow, \
    create_ibm_resource_creation_workflow, get_paginated_response_json, verify_references
from ibm.web.ibm.load_balancers.pools.members.schema import IBMLoadBalancerPoolMemberInSchema, \
    IBMLoadBalancerPoolMemberOutSchema, IBMLoadBalancerPoolMemberResourceSchema, \
    IBMLoadBalancerPoolMemberUpdateSchema, IBMLoadBalancerPoolQuerySchema

LOGGER = logging.getLogger(__name__)

ibm_lb_pool_members = APIBlueprint('ibm_lb_pool_members', __name__, tag="IBM Load Balancers")


@ibm_lb_pool_members.post("/pool_members")
@authenticate
@input(IBMLoadBalancerPoolMemberInSchema)
@output(WorkflowRootOutSchema, status_code=202)
def create_load_balancer_pool_member(data, user):
    """
    Create an IBM Load Balancer Listener Pool Member
    This request creates an IBM Load Balancer Listener Pool Member with VPC+ on IBM Cloud.
    """
    cloud_id = data["ibm_cloud"]["id"]
    pool_id = data["pool"]["id"]

    authorize_and_get_ibm_cloud(cloud_id=cloud_id, user=user)

    # TODO: may be validation task
    pool: IBMPool = ibmdb.session.query(IBMPool).filter_by(id=pool_id).first()
    if not pool:
        message = f"IBM Pool {pool_id} does not exist"
        LOGGER.debug(message)
        abort(404, message)

    target = data["resource_json"]["target"]
    if target["type"] == "instance":
        instance = ibmdb.session.query(IBMInstance).filter_by(id=target.get("id"), cloud_id=cloud_id).first()
        if not instance:
            message = f"IBMInstance {target.get('id')} does not exist"
            LOGGER.debug(message)
            abort(404, message)

        # TODO: may be validation task
        if pool.load_balancer.family == "Application":
            message = "Member Target Instance is not supported for Load Balancer Family 'Application'. You must " \
                      "provide Target 'address'. (hint: 'Network' Family supports Target as Instance)'"
            LOGGER.debug(message)
            abort(404, message)

    elif target["type"] == "network_interface":
        instance = ibmdb.session.query(IBMNetworkInterface).filter_by(id=target.get("id"), cloud_id=cloud_id).first()
        if not instance:
            message = f"IBMNetworkInterface {target.get('id')} does not exist"
            LOGGER.debug(message)
            abort(404, message)

    verify_references(
        cloud_id=cloud_id, body_schema=IBMLoadBalancerPoolMemberInSchema,
        resource_schema=IBMLoadBalancerPoolMemberResourceSchema, data=data
    )

    workflow_root = create_ibm_resource_creation_workflow(
        user=user, resource_type=IBMPoolMember, data=data, validate=False
    )
    return workflow_root.to_json()


@ibm_lb_pool_members.get("/pool_members")
@authenticate
@input(IBMLoadBalancerPoolQuerySchema, location='query')
@input(PaginationQuerySchema, location='query')
@output(get_pagination_schema(IBMLoadBalancerPoolMemberOutSchema))
def list_load_balancer_pool_members(pool_query_params, pagination_query_params, user):
    """
    List IBM Load Balancer Pool Members for an IBM Load Balancer
    This request lists all IBM Load Balancer Pool Members for the project of the authenticated user calling the API.
    """
    cloud_id = pool_query_params["cloud_id"]
    pool_id = pool_query_params["pool_id"]

    authorize_and_get_ibm_cloud(cloud_id=cloud_id, user=user)

    pool_members_query = ibmdb.session.query(IBMPoolMember).filter_by(pool_id=pool_id)

    lb_pool_members_page = pool_members_query.paginate(
        page=pagination_query_params["page"], per_page=pagination_query_params["per_page"], error_out=False
    )
    if not lb_pool_members_page.items:
        return '', 204
    return get_paginated_response_json(
        items=[item.to_json() for item in lb_pool_members_page.items],
        pagination_obj=lb_pool_members_page
    )


@ibm_lb_pool_members.get("/pool_members/<member_id>")
@authenticate
@output(IBMLoadBalancerPoolMemberOutSchema)
def get_load_balancer_pool_member(member_id, user):
    """
    Get an IBM Load Balancer Pool Member
    This request returns an IBM Load Balancer Pool Member provided its ID.
    """
    pool_member = ibmdb.session.query(IBMPoolMember).filter_by(id=member_id).first()
    if not pool_member:
        message = f"IBM Load Balancer Pool member {member_id} does not exist"
        LOGGER.debug(message)
        abort(404, message)

    authorize_and_get_ibm_cloud(pool_member.pool.cloud_id, user)

    return pool_member.to_json()


@ibm_lb_pool_members.patch("/pool_members/<member_id>")
@authenticate
@input(IBMLoadBalancerPoolMemberUpdateSchema)
@output(WorkflowRootOutSchema, status_code=202)
def update_load_balancer_pool_member(member_id, data, user):
    """
    Update an IBM Load Balancer Pool Member
    This request updates an IBM Load Balancer Pool Member
    """
    abort(404)


@ibm_lb_pool_members.delete("/pool_members/<member_id>")
@authenticate
@output(WorkflowRootOutSchema, status_code=202)
def delete_load_balancer_pool_member(member_id, user):
    """
    Delete an IBM Load Balancer Pool Member
    This request deletes an IBM Load Balancer Pool Member provided its ID.
    """
    pool_member = ibmdb.session.get(IBMPoolMember, member_id)
    if not pool_member:
        message = f"IBM Pool Member {member_id} does not exist"
        LOGGER.debug(message)
        abort(404, message)

    authorize_and_get_ibm_cloud(cloud_id=pool_member.pool.ibm_cloud.id, user=user)

    return compose_ibm_resource_deletion_workflow(
        user=user, resource_type=IBMPoolMember, resource_id=member_id
    ).to_json(metadata=True)
