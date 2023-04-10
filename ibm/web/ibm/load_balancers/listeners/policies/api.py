import logging

from apiflask import abort, APIBlueprint, input, output

from ibm.auth import authenticate
from ibm.common.req_resp_schemas.schemas import get_pagination_schema, PaginationQuerySchema, WorkflowRootOutSchema
from ibm.models import IBMListener, IBMListenerPolicy
from ibm.web import db as ibmdb
from ibm.web.common.utils import authorize_and_get_ibm_cloud, compose_ibm_resource_deletion_workflow, \
    create_ibm_resource_creation_workflow, \
    get_paginated_response_json, verify_and_get_region, verify_nested_references, verify_references
from .rules.schemas import IBMListenerPolicyRuleInSchema
from .schemas import IBMListenerPolicyInSchema, IBMListenerPolicyOutSchema, IBMListenerPolicyResourceSchema, \
    IBMListenerQuerySchema, UpdateIBMListenerPolicySchema

LOGGER = logging.getLogger(__name__)

ibm_lb_listener_policies = APIBlueprint('ibm_lb_listener_policies', __name__, tag="IBM Load Balancers")


@ibm_lb_listener_policies.post("/listener_policies")
@authenticate
@input(IBMListenerPolicyInSchema)
@output(WorkflowRootOutSchema, status_code=202)
def create_load_balancer_listener_policy(data, user):
    """
    Create an IBM Load Balancer Listener Policy
    This request creates an IBM Load Balancer Listener Policy with VPC+ on IBM Cloud.
    """
    cloud_id = data["ibm_cloud"]["id"]
    region_id = data["region"]["id"]
    listener_id_or_name = data["listener"].get('id') or data["listener"].get("name")

    ibm_cloud = authorize_and_get_ibm_cloud(cloud_id=cloud_id, user=user)
    verify_and_get_region(ibm_cloud, region_id)

    listener = ibmdb.session.query(IBMListener).filter_by(**data["listener"]).first()
    if not listener:
        message = f"IBM Listener {listener_id_or_name} does not exist."
        LOGGER.debug(message)
        abort(404, message)

    verify_references(
        cloud_id=cloud_id, body_schema=IBMListenerPolicyInSchema,
        resource_schema=IBMListenerPolicyResourceSchema, data=data
    )

    for rule_data in data["resource_json"].get("rules", []):
        verify_nested_references(
            cloud_id=cloud_id, nested_resource_schema=IBMListenerPolicyRuleInSchema, data=rule_data
        )

    return create_ibm_resource_creation_workflow(
        user=user, resource_type=IBMListenerPolicy, data=data, validate=False
    ).to_json()


@ibm_lb_listener_policies.get("/listener_policies")
@authenticate
@input(IBMListenerQuerySchema, location='query')
@input(PaginationQuerySchema, location='query')
@output(get_pagination_schema(IBMListenerPolicyOutSchema))
def list_load_balancer_listener_policies(regional_res_query_params, pagination_query_params, user):
    """
    List IBM Load Balancer Policies for an IBM Load Balancer Listener
    This request lists all IBM Load Balancer Listener Policies for the project of the authenticated user calling the
    API.
    """
    listener_id = regional_res_query_params["listener_id"]

    listener = ibmdb.session.get(IBMListener, listener_id)
    if not listener:
        message = f"IBM Listener {listener_id} does not exist."
        LOGGER.debug(message)
        abort(404, message)

    authorize_and_get_ibm_cloud(listener.cloud_id, user)

    listener_policies_query = ibmdb.session.query(IBMListenerPolicy).filter_by(lb_listener_id=listener_id)
    listener_policies_page = listener_policies_query.paginate(
        page=pagination_query_params["page"], per_page=pagination_query_params["per_page"], error_out=False
    )

    if not listener_policies_page.items:
        return '', 204

    return get_paginated_response_json(
        items=[item.to_json() for item in listener_policies_page.items],
        pagination_obj=listener_policies_page
    )


@ibm_lb_listener_policies.get("/listener_policies/<policy_id>")
@authenticate
@output(IBMListenerPolicyOutSchema)
def get_load_balancer_listener_policy(policy_id, user):
    """
    Get an IBM Load Balancer Listener Policy
    This request returns an IBM Load Balancer Listener Policy provided its ID.
    """
    policy = ibmdb.session.query(IBMListenerPolicy).filter_by(
        id=policy_id
    ).join(IBMListener.ibm_cloud).filter_by(
        user_id=user["id"], project_id=user["project_id"], deleted=False
    ).first()
    if not policy:
        message = f"IBM Policy {policy_id} does not exist"
        LOGGER.debug(message)
        abort(404, message)

    return policy.to_json()


@ibm_lb_listener_policies.patch("/listener_policies/<policy_id>")
@authenticate
@input(UpdateIBMListenerPolicySchema)
@output(WorkflowRootOutSchema, status_code=202)
def update_load_balancer_listener_policy(policy_id, data, user):
    """
    Update an IBM Load Balancer Listener Policy
    This request updates an IBM Load Balancer Listener Policy
    """
    abort(404)


@ibm_lb_listener_policies.delete("/listener_policies/<policy_id>")
@authenticate
@output(WorkflowRootOutSchema, status_code=202)
def delete_load_balancer_listener_policy(policy_id, user):
    """
    Delete an IBM Load Balancer Listener Policy
    This request deletes an IBM Load Balancer Listener Policy provided its ID.
    """
    policy = ibmdb.session.query(IBMListenerPolicy).filter_by(id=policy_id).first()
    if not policy:
        message = f"IBM Listener Policy {policy_id} does not exist"
        LOGGER.debug(message)
        abort(404, message)

    authorize_and_get_ibm_cloud(cloud_id=policy.listener.ibm_cloud.id, user=user)

    return compose_ibm_resource_deletion_workflow(
        user=user, resource_type=IBMListenerPolicy, resource_id=policy_id
    ).to_json(metadata=True)
