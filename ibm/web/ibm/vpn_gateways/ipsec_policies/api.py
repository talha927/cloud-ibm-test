import logging

from apiflask import abort, APIBlueprint, input, output

from ibm.auth import authenticate
from ibm.common.req_resp_schemas.schemas import get_pagination_schema, IBMRegionalResourceListQuerySchema, \
    PaginationQuerySchema, WorkflowRootOutSchema
from ibm.models import IBMIPSecPolicy
from ibm.web import db as ibmdb
from ibm.web.common.utils import authorize_and_get_ibm_cloud, compose_ibm_resource_deletion_workflow, \
    create_ibm_resource_creation_workflow, get_paginated_response_json, verify_and_get_region, verify_references
from .schemas import IBMIPSecPoliciesInSchema, IBMIPSecPoliciesResourceSchema, IBMIPSecPolicyOutSchema, \
    UpdateIBMIPSecPoliciesSchema

LOGGER = logging.getLogger(__name__)
ibm_ipsec_policies = APIBlueprint('ibm_ipsec_policies', __name__, tag="IPSec Policies")


@ibm_ipsec_policies.post('/ipsec_policies')
@authenticate
@input(IBMIPSecPoliciesInSchema)
@output(WorkflowRootOutSchema, status_code=202)
def create_ibm_ipsec_policy(data, user):
    """
    Create an IPsec policy
    This request creates a new IPsec policy.
    """
    cloud_id = data["ibm_cloud"]["id"]
    region_id = data["region"]["id"]

    ibm_cloud = authorize_and_get_ibm_cloud(cloud_id=cloud_id, user=user)
    verify_and_get_region(ibm_cloud=ibm_cloud, region_id=region_id)

    verify_references(
        cloud_id=cloud_id, body_schema=IBMIPSecPoliciesInSchema, resource_schema=IBMIPSecPoliciesResourceSchema,
        data=data
    )

    workflow_root = create_ibm_resource_creation_workflow(
        user=user, resource_type=IBMIPSecPolicy, data=data, validate=False
    )
    return workflow_root.to_json()


@ibm_ipsec_policies.route('/ipsec_policies', methods=["GET"])
@authenticate
@input(IBMRegionalResourceListQuerySchema, location='query')
@input(PaginationQuerySchema, location='query')
@output(get_pagination_schema(IBMIPSecPolicyOutSchema))
def list_ibm_ipsec_policies(regional_res_query_params, pagination_query_params, user):
    """
    List all IPsec policies
    This request lists all IPsec policies in the region.
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

    ipsec_policy_query = ibmdb.session.query(IBMIPSecPolicy).filter_by(cloud_id=cloud_id)
    if region:
        ipsec_policy_query = ipsec_policy_query.filter_by(region_id=region_id)

    ipsec_policies_page = ipsec_policy_query.paginate(
        page=pagination_query_params["page"], per_page=pagination_query_params["per_page"], error_out=False
    )
    if not ipsec_policies_page.items:
        return '', 204

    return get_paginated_response_json(
        items=[item.to_json() for item in ipsec_policies_page.items],
        pagination_obj=ipsec_policies_page
    )


@ibm_ipsec_policies.route('/ipsec_policies/<ipsec_policy_id>', methods=['GET'])
@authenticate
@output(IBMIPSecPolicyOutSchema)
def get_ibm_ipsec_policy(ipsec_policy_id, user):
    """
    Retrieve an IPsec policy
    This request retrieves a single IPsec policy specified by the identifier in the URL.
    """
    ipsec_policy = ibmdb.session.query(IBMIPSecPolicy).filter_by(
        id=ipsec_policy_id
    ).join(IBMIPSecPolicy.ibm_cloud).filter_by(
        user_id=user["id"], project_id=user["project_id"], deleted=False
    ).first()
    if not ipsec_policy:
        message = f"IBM IPSEC Policy {ipsec_policy_id} does not exist"
        LOGGER.debug(message)
        abort(404, message)

    return ipsec_policy.to_json()


@ibm_ipsec_policies.route('/ipsec_policies/<ipsec_policy_id>', methods=['PATCH'])
@authenticate
@input(UpdateIBMIPSecPoliciesSchema)
@output(WorkflowRootOutSchema, status_code=202)
def update_ibm_ipsec_policy(ipsec_policy_id, data, user):
    """
    Update an IPsec policy
    This request updates the properties of an existing IPsec policy.
    """
    abort(404)


@ibm_ipsec_policies.delete('/ipsec_policies/<ipsec_policy_id>')
@authenticate
@output(WorkflowRootOutSchema, status_code=202)
def delete_ibm_ipsec_policy(ipsec_policy_id, user):
    """
    Delete an IPsec policy
    This request deletes an IPsec policy. This operation cannot be reversed.
    """
    ipsec_policy = ibmdb.session.query(IBMIPSecPolicy).filter_by(
        id=ipsec_policy_id
    ).join(IBMIPSecPolicy.ibm_cloud).filter_by(
        user_id=user["id"], project_id=user["project_id"], deleted=False
    ).first()
    if not ipsec_policy:
        message = f"IBM IPSEC Policy {ipsec_policy_id} does not exist"
        LOGGER.debug(message)
        abort(404, message)
    # TODO will add this check when we have update api ready
    # if not ipsec_policy.is_deletable:
    #     message = f"The IPSEC policy {ipsec_policy.name} is in use and cannot be deleted."
    #     LOGGER.debug(message)
    #     abort(409, message)

    return compose_ibm_resource_deletion_workflow(
        user=user, resource_type=IBMIPSecPolicy, resource_id=ipsec_policy_id
    ).to_json(metadata=True)
