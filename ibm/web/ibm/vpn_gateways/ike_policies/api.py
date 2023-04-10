import logging

from apiflask import abort, APIBlueprint, input, output

from ibm.auth import authenticate
from ibm.common.req_resp_schemas.schemas import get_pagination_schema, IBMRegionalResourceListQuerySchema, \
    IBMResourceQuerySchema, IBMVpnQueryParamSchema, PaginationQuerySchema, WorkflowRootOutSchema
from ibm.models import IBMIKEPolicy
from ibm.web import db as ibmdb
from ibm.web.common.utils import authorize_and_get_ibm_cloud, compose_ibm_resource_deletion_workflow, \
    create_ibm_resource_creation_workflow, get_paginated_response_json, verify_and_get_region, verify_references
from ibm.web.ibm.vpn_gateways.schemas import IBMVpnGatewayConnectionOutSchema
from .schemas import IBMIKEPoliciesInSchema, IBMIKEPoliciesResourceSchema, IBMIKEPolicyOutSchema, \
    UpdateIBMIKEPoliciesSchema

LOGGER = logging.getLogger(__name__)

ibm_ike_policies = APIBlueprint('ibm_ike_policies', __name__, tag="Ike Policies")


@ibm_ike_policies.post('/ike_policies')
@authenticate
@input(IBMIKEPoliciesInSchema)
@output(WorkflowRootOutSchema, status_code=202)
def create_ibm_ike_policy(data, user):
    """
    Create an IKE policy
    This request creates a new IKE policy.
    """
    cloud_id = data["ibm_cloud"]["id"]
    region_id = data["region"]["id"]

    ibm_cloud = authorize_and_get_ibm_cloud(cloud_id=cloud_id, user=user)
    verify_and_get_region(ibm_cloud=ibm_cloud, region_id=region_id)

    verify_references(
        cloud_id=cloud_id, body_schema=IBMIKEPoliciesInSchema, resource_schema=IBMIKEPoliciesResourceSchema, data=data
    )

    workflow_root = create_ibm_resource_creation_workflow(
        user=user, resource_type=IBMIKEPolicy, data=data, validate=False
    )
    return workflow_root.to_json()


@ibm_ike_policies.get('/ike_policies')
@authenticate
@input(IBMRegionalResourceListQuerySchema, location='query')
@input(PaginationQuerySchema, location='query')
@output(get_pagination_schema(IBMIKEPolicyOutSchema))
def list_ibm_ike_policies(regional_res_query_params, pagination_query_params, user):
    """
    List all IKE policies
    This request lists all IKE policies in the region.
    """
    cloud_id = regional_res_query_params["cloud_id"]
    region_id = regional_res_query_params.get("region_id")

    ibm_cloud = authorize_and_get_ibm_cloud(cloud_id=cloud_id, user=user)

    region = None
    if region_id:
        region = ibm_cloud.regions.filter_by(id=region_id).first()
        if not region:
            message = f"IBM Region {region_id} does not exist"
            LOGGER.debug(message)
            abort(404, message)

    ike_policy_query = ibmdb.session.query(IBMIKEPolicy).filter_by(cloud_id=cloud_id)
    if region:
        ike_policy_query = ike_policy_query.filter_by(region_id=region_id)

    ike_policies_page = ike_policy_query.paginate(
        page=pagination_query_params["page"], per_page=pagination_query_params["per_page"], error_out=False
    )
    if not ike_policies_page.items:
        return '', 204

    return get_paginated_response_json(
        items=[item.to_json() for item in ike_policies_page.items],
        pagination_obj=ike_policies_page
    )


@ibm_ike_policies.route('/ike_policies/<ike_policy_id>', methods=['GET'])
@authenticate
@output(IBMIKEPolicyOutSchema)
def get_ibm_ike_policy(ike_policy_id, user):
    """
    Retrieve an IKE policy
    This request retrieves a single IKE policy specified by the identifier in the URL.
    """
    ike_policy = ibmdb.session.query(IBMIKEPolicy).filter_by(
        id=ike_policy_id
    ).join(IBMIKEPolicy.ibm_cloud).filter_by(
        user_id=user["id"], project_id=user["project_id"], deleted=False
    ).first()
    if not ike_policy:
        message = f"IBM IKE Policy {ike_policy_id} does not exist"
        LOGGER.debug(message)
        abort(404, message)

    return ike_policy.to_json()


@ibm_ike_policies.route('/ike_policies/<ike_policy_id>', methods=['PATCH'])
@authenticate
@input(UpdateIBMIKEPoliciesSchema)
@output(WorkflowRootOutSchema, status_code=202)
def update_ibm_ike_policy(ike_policy_id, data, user):
    """
    Update an IKE policy
    This request updates the properties of an existing IKE policy.
    """
    abort(404)


@ibm_ike_policies.delete('/ike_policies/<ike_policy_id>')
@authenticate
@output(WorkflowRootOutSchema, status_code=202)
def delete_ibm_ike_policy(ike_policy_id, user):
    """
    Delete an IKE policy
    This request deletes an IKE policy. This operation cannot be reversed.
    """
    ike_policy = ibmdb.session.query(IBMIKEPolicy).filter_by(
        id=ike_policy_id
    ).join(IBMIKEPolicy.ibm_cloud).filter_by(
        user_id=user["id"], project_id=user["project_id"], deleted=False
    ).first()
    if not ike_policy:
        message = f"IBM IKE Policy {ike_policy_id} does not exist"
        LOGGER.debug(message)
        abort(404, message)
    # TODO will add this check when we have update api ready
    # if not ike_policy.is_deletable:
    #     message = f"The IKE policy {ike_policy.name} is in use and cannot be deleted."
    #     LOGGER.debug(message)
    #     abort(409, message)

    return compose_ibm_resource_deletion_workflow(
        user=user, resource_type=IBMIKEPolicy, resource_id=ike_policy_id
    ).to_json(metadata=True)


@ibm_ike_policies.route('/connections', methods=["GET"])
@authenticate
@input(IBMVpnQueryParamSchema(only=("ike_policy_id",)), location='query')
@input(IBMResourceQuerySchema, location='query')
@input(PaginationQuerySchema, location='query')
@output(get_pagination_schema(IBMVpnGatewayConnectionOutSchema))
def list_ibm_ike_policy_connections(ike_policy_query_params, listing_query_params, pagination_query_params, user):
    """
    List all VPN gateway connections that use a specified IKE policy
    This request lists all VPN gateway connections that use a policy
    """
    abort(404)
