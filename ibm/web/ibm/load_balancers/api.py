import logging

from apiflask import abort, APIBlueprint, doc, input, output

from ibm.auth import authenticate
from ibm.common.req_resp_schemas.schemas import get_pagination_schema, \
    IBMRegionalResourceListQuerySchema, IBMResourceQuerySchema, PaginationQuerySchema, WorkflowRootOutSchema
from ibm.middleware import log_activity
from ibm.models import IBMLoadBalancer, IBMLoadBalancerProfile, IBMPool, WorkflowRoot
from ibm.web import db as ibmdb
from ibm.web.common.utils import authorize_and_get_ibm_cloud, compose_ibm_resource_deletion_workflow, \
    compose_ibm_sync_resource_workflow, create_ibm_resource_creation_workflow, \
    get_paginated_response_json, verify_and_get_region, verify_references
from .schemas import IBMInstanceGroupAttachedListQuerySchema, IBMLoadBalancerInSchema, IBMLoadBalancerOutSchema, \
    IBMLoadBalancerProfileListQuerySchema, IBMLoadBalancerProfileOutSchema, IBMLoadBalancerResourceSchema, \
    UpdateIBMLoadBalancerSchema

LOGGER = logging.getLogger(__name__)

ibm_load_balancers = APIBlueprint('ibm_load_balancers', __name__, tag="IBM Load Balancers")


@ibm_load_balancers.post("/load_balancers")
@authenticate
@log_activity
@input(IBMLoadBalancerInSchema)
@output(WorkflowRootOutSchema, status_code=202)
def create_load_balancer(data, user):
    """
    Create an IBM Load Balancer
    This request creates an IBM Load Balancers with VPC+ on IBM Cloud.
    """
    cloud_id = data["ibm_cloud"]["id"]
    region_id = data["region"]["id"]
    ibm_cloud = authorize_and_get_ibm_cloud(cloud_id=cloud_id, user=user)
    verify_and_get_region(ibm_cloud=ibm_cloud, region_id=region_id)

    verify_references(
        cloud_id=cloud_id, body_schema=IBMLoadBalancerInSchema, resource_schema=IBMLoadBalancerResourceSchema, data=data
    )

    workflow_root = create_ibm_resource_creation_workflow(
        user=user, resource_type=IBMLoadBalancer, data=data, validate=False
    )
    return workflow_root.to_json()


@ibm_load_balancers.get("/load_balancers")
@authenticate
@input(IBMRegionalResourceListQuerySchema, location='query')
@input(IBMInstanceGroupAttachedListQuerySchema, location='query')
@input(PaginationQuerySchema, location='query')
@output(get_pagination_schema(IBMLoadBalancerOutSchema))
@doc(
    responses={
        204: "No records found"
    }
)
def list_load_balancers(regional_res_query_params, attached_id_query_params, pagination_query_params, user):
    """
    List IBM Load Balancers
    This request lists all IBM Load Balancers for the project of the authenticated user calling the API.
    """
    cloud_id = regional_res_query_params["cloud_id"]
    region_id = regional_res_query_params.get("region_id")
    is_ig_attached = attached_id_query_params.get("is_ig_attached")

    ibm_cloud = authorize_and_get_ibm_cloud(cloud_id=cloud_id, user=user)
    filters = {
        "cloud_id": cloud_id
    }

    if region_id:
        filters["region_id"] = region_id
        verify_and_get_region(ibm_cloud, region_id)

    load_balancers_query = ibmdb.session.query(IBMLoadBalancer).filter_by(**filters)

    if is_ig_attached is not None:
        if is_ig_attached:
            load_balancers_query = ibm_cloud.load_balancers.filter(~IBMPool.instance_groups.any(),
                                                                   IBMLoadBalancer.pools.any())
        else:
            load_balancers_query = ibm_cloud.load_balancers.filter(IBMPool.instance_groups.any(),
                                                                   IBMLoadBalancer.pools.any())

    load_balancers_page = load_balancers_query.paginate(
        page=pagination_query_params["page"], per_page=pagination_query_params["per_page"], error_out=False
    )
    if not load_balancers_page.items:
        return '', 204

    return get_paginated_response_json(
        items=[item.to_json() for item in load_balancers_page.items],
        pagination_obj=load_balancers_page
    )


@ibm_load_balancers.post("/load_balancer/profiles/sync")
@authenticate
@input(IBMResourceQuerySchema, location="query")
@output(WorkflowRootOutSchema, status_code=202)
def sync_load_balancer_profiles(regional_query_params, user):
    """
    Sync all IBM Load Balancer Profiles
    This request sync all IBM Load Balancer Profiles.
    :param regional_query_params:
    :param user:
    :return:
    """
    cloud_id = regional_query_params["cloud_id"]

    authorize_and_get_ibm_cloud(cloud_id, user)

    workflow_root: WorkflowRoot = ibmdb.session.query(WorkflowRoot).filter(
        WorkflowRoot.user_id == user["id"], WorkflowRoot.project_id == user["project_id"],
        WorkflowRoot.workflow_name == IBMLoadBalancerProfile.__name__, WorkflowRoot.workflow_nature == "SYNC",
        WorkflowRoot.status.in_(
            {
                WorkflowRoot.STATUS_ON_HOLD,
                WorkflowRoot.STATUS_PENDING,
                WorkflowRoot.STATUS_INITIATED,
                WorkflowRoot.STATUS_RUNNING
            }
        )).first()

    if workflow_root and workflow_root.fe_request_data == regional_query_params:
        return workflow_root.to_json()

    return compose_ibm_sync_resource_workflow(
        user, resource_type=IBMLoadBalancerProfile,
        data=regional_query_params
    ).to_json()


@ibm_load_balancers.get("/load_balancer/profiles")
@authenticate
@input(IBMLoadBalancerProfileListQuerySchema, location='query')
@input(PaginationQuerySchema, location='query')
@output(get_pagination_schema(IBMLoadBalancerProfileOutSchema))
@doc(
    responses={
        204: "No records found"
    }
)
def list_load_balancer_profiles(regional_res_query_params, pagination_query_params, user):
    """
    List all Load Balancer Profiles
    This request lists all IBM Load Balancer Profiles for the project of the authenticated user calling the API.
    :param regional_res_query_params:
    :param pagination_query_params:
    :param user:
    :return:
    """
    minimal = regional_res_query_params.get("minimal")

    lb_profiles_query = ibmdb.session.query(IBMLoadBalancerProfile)

    if minimal:
        lb_profiles_query = lb_profiles_query.filter(IBMLoadBalancerProfile.name.in_(["dynamic", "network-fixed"]))

    lb_profiles_page = lb_profiles_query.paginate(
        page=pagination_query_params["page"], per_page=pagination_query_params["per_page"], error_out=False
    )
    if not lb_profiles_page.items:
        return '', 204

    return get_paginated_response_json(
        items=[item.to_json() for item in lb_profiles_page.items],
        pagination_obj=lb_profiles_page
    )


@ibm_load_balancers.get("/load_balancers/<load_balancer_id>")
@authenticate
@output(IBMLoadBalancerOutSchema)
def get_load_balancer(load_balancer_id, user):
    """
    Get an IBM Load Balancer
    This request returns an IBM Load Balancer provided its ID.
    """
    load_balancer = ibmdb.session.query(IBMLoadBalancer).filter_by(
        id=load_balancer_id
    ).join(IBMLoadBalancer.ibm_cloud).filter_by(
        user_id=user["id"], project_id=user["project_id"], deleted=False
    ).first()
    if not load_balancer:
        message = f"IBM Load Balancer {load_balancer_id} does not exist"
        LOGGER.debug(message)
        abort(404, message)

    return load_balancer.to_json()


@ibm_load_balancers.patch("/load_balancers/<load_balancer_id>")
@authenticate
@input(UpdateIBMLoadBalancerSchema)
@output(WorkflowRootOutSchema, status_code=202)
def update_load_balancer(load_balancer_id, data, user):
    """
    Update an IBM Load Balancer
    This request updates an IBM Load Balancer
    """
    abort(404)


@ibm_load_balancers.delete("/load_balancers/<load_balancer_id>")
@authenticate
@log_activity
@output(WorkflowRootOutSchema, status_code=202)
def delete_load_balancer(load_balancer_id, user):
    """
    Delete an IBM Load Balancer
    This request deletes an IBM Load Balancer provided its ID.
    """
    load_balancer = ibmdb.session.query(IBMLoadBalancer).filter_by(
        id=load_balancer_id
    ).join(IBMLoadBalancer.ibm_cloud).filter_by(
        user_id=user["id"], project_id=user["project_id"], deleted=False
    ).first()
    if not load_balancer:
        message = f"IBM Load Balancer {load_balancer_id} does not exist"
        LOGGER.debug(message)
        abort(404, message)

    return compose_ibm_resource_deletion_workflow(
        user=user, resource_type=IBMLoadBalancer, resource_id=load_balancer_id
    ).to_json(metadata=True)
