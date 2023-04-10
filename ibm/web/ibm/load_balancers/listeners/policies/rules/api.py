import logging

from apiflask import abort, APIBlueprint, input, output

from ibm.auth import authenticate
from ibm.common.req_resp_schemas.schemas import get_pagination_schema, PaginationQuerySchema, WorkflowRootOutSchema
from ibm.models import IBMListenerPolicy, IBMListenerPolicyRule
from ibm.web import db as ibmdb
from ibm.web.common.utils import authorize_and_get_ibm_cloud, compose_ibm_resource_deletion_workflow, \
    create_ibm_resource_creation_workflow, \
    get_paginated_response_json, verify_and_get_region, verify_references
from ibm.web.ibm.load_balancers.listeners.policies.rules.schemas import IBMListenerPolicyRuleInSchema, \
    IBMListenerPolicyRuleOutSchema, IBMListenerPolicyRuleResourceSchema, UpdateIBMListenerPolicyRuleSchema
from ibm.web.ibm.load_balancers.listeners.policies.schemas import IBMPolicyRuleListQuerySchema

LOGGER = logging.getLogger(__name__)
ibm_lb_listener_policy_rules = APIBlueprint('ibm_lb_listener_policy_rules', __name__, tag="IBM Load Balancers")


@ibm_lb_listener_policy_rules.post("/listener_policy_rules")
@authenticate
@input(IBMListenerPolicyRuleInSchema)
@output(WorkflowRootOutSchema, status_code=202)
def create_load_balancer_listener_policy_rule(data, user):
    """
    Create an IBM Load Balancer Listener Policy Rule
    This request creates an IBM Load Balancer Listener Policy Rule with VPC+ on IBM Cloud.
    """
    cloud_id = data["ibm_cloud"]["id"]
    region_id = data["region"]["id"]
    policy_name_id_dict = data["policy"]

    ibm_cloud = authorize_and_get_ibm_cloud(cloud_id=cloud_id, user=user)
    verify_and_get_region(ibm_cloud, region_id)

    policy = ibmdb.session.query(IBMListenerPolicy).filter_by(**policy_name_id_dict).first()
    if not policy:
        message = f"IBM Listener Policy {policy_name_id_dict.get('id') or policy_name_id_dict.get('name')} does not " \
                  f"exist."
        LOGGER.debug(message)
        abort(404, message)

    verify_references(
        cloud_id=cloud_id, body_schema=IBMListenerPolicyRuleInSchema,
        resource_schema=IBMListenerPolicyRuleResourceSchema, data=data
    )

    return create_ibm_resource_creation_workflow(
        user=user, resource_type=IBMListenerPolicyRule, data=data, validate=False
    ).to_json()


@ibm_lb_listener_policy_rules.get("/listener_policy_rules")
@authenticate
@input(IBMPolicyRuleListQuerySchema, location='query')
@input(PaginationQuerySchema, location='query')
@output(get_pagination_schema(IBMListenerPolicyRuleOutSchema))
def list_load_balancer_listener_policy_rules(policy_query_params, pagination_query_params, user):
    """
    List IBM Load Balancer Policy Rules for an IBM Load Balancer Listener Policy
    This request lists all IBM LB Listener Policy Rules for the project of the authenticated user calling the API.
    """
    cloud_id = policy_query_params["cloud_id"]
    policy_id = policy_query_params["policy_id"]

    authorize_and_get_ibm_cloud(cloud_id, user)

    policy = ibmdb.session.get(IBMListenerPolicy, policy_id)
    if not policy:
        message = f"IBM Listener Policy {policy_id} does not exist."
        LOGGER.debug(message)
        abort(404, message)

    policy_rules_query = ibmdb.session.query(IBMListenerPolicyRule).filter_by(lb_listener_policy_id=policy_id)
    policy_rules_page = policy_rules_query.paginate(
        page=pagination_query_params["page"], per_page=pagination_query_params["per_page"], error_out=False
    )

    if not policy_rules_page.items:
        return '', 204

    return get_paginated_response_json(
        items=[item.to_json() for item in policy_rules_page.items],
        pagination_obj=policy_rules_page
    )


@ibm_lb_listener_policy_rules.get("/listener_policy_rules/<rule_id>")
@authenticate
@output(IBMListenerPolicyRuleOutSchema)
def get_load_balancer_listener_policy(rule_id, user):
    """
    Get an IBM Load Balancer Listener Policy Rule
    This request returns an IBM Load Balancer Listener Policy Rule provided its ID.
    """
    policy_rule = ibmdb.session.query(IBMListenerPolicyRule).filter_by(
        id=rule_id
    ).first()
    if not policy_rule:
        message = f"IBM Policy Rule {rule_id} does not exist"
        LOGGER.debug(message)
        abort(404, message)

    authorize_and_get_ibm_cloud(cloud_id=policy_rule.lb_listener_policy.listener.cloud_id, user=user)

    return policy_rule.to_json()


@ibm_lb_listener_policy_rules.patch("/listener_policy_rules/<rule_id>")
@authenticate
@input(UpdateIBMListenerPolicyRuleSchema)
@output(WorkflowRootOutSchema, status_code=202)
def update_load_balancer_listener_policy(rule_id, data, user):
    """
    Update an IBM Load Balancer Listener Policy Rule
    This request updates an IBM Load Balancer Listener Policy Rule
    """
    abort(404)


@ibm_lb_listener_policy_rules.delete("/listener_policy_rules/<rule_id>")
@authenticate
@output(WorkflowRootOutSchema, status_code=202)
def delete_load_balancer_listener_policy(rule_id, user):
    """
    Delete an IBM Load Balancer Listener Policy Rule
    This request deletes an IBM Load Balancer Listener Policy Rule provided its ID.
    """
    policy_rule = ibmdb.session.query(IBMListenerPolicyRule).filter_by(
        id=rule_id
    ).first()
    if not policy_rule:
        message = f"IBM Policy Rule {rule_id} does not exist"
        LOGGER.debug(message)
        abort(404, message)

    authorize_and_get_ibm_cloud(cloud_id=policy_rule.lb_listener_policy.listener.cloud_id, user=user)

    return compose_ibm_resource_deletion_workflow(
        user=user, resource_type=IBMListenerPolicyRule, resource_id=rule_id
    ).to_json(metadata=True)
