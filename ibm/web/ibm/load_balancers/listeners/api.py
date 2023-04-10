import logging

from apiflask import abort, APIBlueprint, doc, input, output

from ibm.auth import authenticate
from ibm.common.req_resp_schemas.schemas import get_pagination_schema, PaginationQuerySchema, WorkflowRootOutSchema
from ibm.models import IBMListener, IBMLoadBalancer
from ibm.web import db as ibmdb
from ibm.web.common.utils import authorize_and_get_ibm_cloud, compose_ibm_resource_deletion_workflow, \
    create_ibm_resource_creation_workflow, get_paginated_response_json, verify_and_get_region, \
    verify_references
from ibm.web.ibm.load_balancers.listeners.schemas import IBMLoadBalancerListenerInSchema, \
    IBMLoadBalancerListenerListQuerySchema, IBMLoadBalancerListenerOutSchema, IBMLoadBalancerListenerResourceSchema, \
    IBMUpdateListenerSchema

LOGGER = logging.getLogger(__name__)

ibm_lb_listeners = APIBlueprint('ibm_lb_listeners', __name__, tag="IBM Load Balancers")


@ibm_lb_listeners.post("/load_balancer_listeners")
@authenticate
@input(IBMLoadBalancerListenerInSchema)
@output(WorkflowRootOutSchema, status_code=202)
def create_load_balancer_listener(data, user):
    """
    Create an IBM Load Balancer Listener
    This request creates an IBM Load Balancer Listeners with VPC+ on IBM Cloud.
    """
    cloud_id = data["ibm_cloud"]["id"]
    region_id = data["region"]["id"]
    load_balancer_id_or_name = data["load_balancer"].get("id") or data["load_balancer"].get("name")

    ibm_cloud = authorize_and_get_ibm_cloud(cloud_id=cloud_id, user=user)
    verify_and_get_region(ibm_cloud, region_id)

    load_balancer = ibmdb.session.query(IBMLoadBalancer).filter_by(**data["load_balancer"], cloud_id=cloud_id).first()
    if not load_balancer:
        message = f"IBM Load Balancer {load_balancer_id_or_name} does not exist."
        LOGGER.debug(message)
        abort(404, message)

    verify_references(
        cloud_id=cloud_id, body_schema=IBMLoadBalancerListenerInSchema,
        resource_schema=IBMLoadBalancerListenerResourceSchema, data=data
    )

    workflow_root = create_ibm_resource_creation_workflow(
        user=user, resource_type=IBMListener, data=data, validate=False
    )
    return workflow_root.to_json()


@ibm_lb_listeners.get("/load_balancer_listeners")
@authenticate
@input(IBMLoadBalancerListenerListQuerySchema, location='query')
@input(PaginationQuerySchema, location='query')
@output(get_pagination_schema(IBMLoadBalancerListenerOutSchema))
@doc(
    responses={
        204: "No records found"
    }
)
def list_load_balancer_listeners(regional_res_query_params, pagination_query_params, user):
    """
    List IBM Load Balancer Listener for an IBM Load Balancer
    This request lists all IBM Load Balancer Listener for the project of the authenticated user calling the API.
    """
    cloud_id = regional_res_query_params["cloud_id"]
    region_id = regional_res_query_params.get("region_id")
    load_balancer_id = regional_res_query_params.get("load_balancer_id")

    ibm_cloud = authorize_and_get_ibm_cloud(cloud_id=cloud_id, user=user)
    filters = {
        "cloud_id": cloud_id
    }

    if region_id:
        verify_and_get_region(ibm_cloud, region_id)
        filters["region_id"] = region_id

    if load_balancer_id:
        filters["load_balancer_id"] = load_balancer_id
        load_balancer = ibmdb.session.get(IBMLoadBalancer, load_balancer_id)
        if not load_balancer:
            message = f"IBM Load Balancer {load_balancer_id} does not exist."
            LOGGER.debug(message)
            abort(404, message)

    load_balancer_listeners_query = ibmdb.session.query(IBMListener).filter_by(**filters)
    load_balancer_listeners_page = load_balancer_listeners_query.paginate(
        page=pagination_query_params["page"], per_page=pagination_query_params["per_page"], error_out=False
    )

    if not load_balancer_listeners_page.items:
        return '', 204

    return get_paginated_response_json(
        items=[item.to_json() for item in load_balancer_listeners_page.items],
        pagination_obj=load_balancer_listeners_page
    )


@ibm_lb_listeners.get("/load_balancer_listeners/<listener_id>")
@authenticate
@output(IBMLoadBalancerListenerOutSchema)
def get_load_balancer_listener(listener_id, user):
    """
    Get an IBM Load Balancer Listener
    This request returns an IBM Load Balancer Listener provided its ID.
    """
    listener = ibmdb.session.query(IBMListener).filter_by(id=listener_id).first()
    if not listener:
        message = f"IBM Listener {listener_id} does not exist"
        LOGGER.debug(message)
        abort(404, message)

    authorize_and_get_ibm_cloud(listener.cloud_id, user)

    return listener.to_json()


@ibm_lb_listeners.patch("/load_balancer_listeners/<listener_id>")
@authenticate
@input(IBMUpdateListenerSchema)
@output(WorkflowRootOutSchema, status_code=202)
def update_load_balancer_listener(listener_id, data, user):
    """
    Update an IBM Load Balancer Listener
    This request updates an IBM Load Balancer Listener
    """
    abort(404)


@ibm_lb_listeners.delete("/load_balancer_listeners/<listener_id>")
@authenticate
@output(WorkflowRootOutSchema, status_code=202)
def delete_load_balancer_listener(listener_id, user):
    """
    Delete an IBM Load Balancer Listener
    This request deletes an IBM Load Balancer Listener provided its ID.
    """
    listener = ibmdb.session.query(IBMListener).filter_by(id=listener_id).first()
    if not listener:
        message = f"IBM Listener {listener_id} does not exist"
        LOGGER.debug(message)
        abort(404, message)

    authorize_and_get_ibm_cloud(listener.cloud_id, user)

    return compose_ibm_resource_deletion_workflow(
        user=user, resource_type=IBMListener, resource_id=listener_id
    ).to_json(metadata=True)
