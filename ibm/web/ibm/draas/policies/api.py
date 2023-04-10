import logging

from apiflask import abort, doc, input, output

from ibm.auth import authenticate
from ibm.models import DisasterRecoveryScheduledPolicy
from ibm.web import db as ibmdb
from ibm.common.req_resp_schemas.schemas import get_pagination_schema, PaginationQuerySchema
from ibm.web.common.utils import authorize_and_get_ibm_cloud, get_paginated_response_json
from ibm.web.ibm.draas import ibm_draas
from .schemas import DisasterRecoveryDeletePolicyOutSchema, DisasterRecoveryPolicyInSchema, \
    DisasterRecoveryPolicyOutSchema, DisasterRecoveryPolicyQuerySchema

LOGGER = logging.getLogger(__name__)


@ibm_draas.route('/draas-policies', methods=['GET'])
@authenticate
@input(PaginationQuerySchema, location='query')
@input(DisasterRecoveryPolicyQuerySchema, location='query')
@output(get_pagination_schema(DisasterRecoveryPolicyOutSchema))
@doc(
    responses={
        204: "No records found"
    }
)
def list_draas_policies(pagination_params, draas_policy_query_params, user):
    """
    List IBM Draas Policies
    This request lists all IBM Draas Policies against provided Policy Resource ID.
    """
    cloud_id = draas_policy_query_params["cloud_id"]
    authorize_and_get_ibm_cloud(cloud_id=cloud_id, user=user)

    draas_policies_page = ibmdb.session.query(DisasterRecoveryScheduledPolicy).filter_by(
        **draas_policy_query_params
    ).paginate(
        page=pagination_params["page"], per_page=pagination_params["per_page"], error_out=False
    )
    if not draas_policies_page.items:
        return '', 204

    return get_paginated_response_json(
        items=[item.to_json() for item in draas_policies_page.items],
        pagination_obj=draas_policies_page
    )


@ibm_draas.route('/draas-policies/<draas_policy_id>', methods=['GET'])
@authenticate
@input(DisasterRecoveryPolicyQuerySchema, location='query')
@output(DisasterRecoveryPolicyOutSchema)
def get_ibm_draas_policy(draas_policy_id, draas_policy_query_params, user):
    """
    Get IBM Draas Policy
    This request returns an IBM Draas Policy provided its ID.
    """
    cloud_id = draas_policy_query_params["cloud_id"]
    authorize_and_get_ibm_cloud(cloud_id=cloud_id, user=user)
    disaster_recovery_policy = ibmdb.session.query(DisasterRecoveryScheduledPolicy).filter_by(
        id=draas_policy_id,
        cloud_id=draas_policy_query_params["cloud_id"]
    ).first()

    if not disaster_recovery_policy:
        message = f"No Disaster recovery Policy found with ID {draas_policy_id}"
        LOGGER.debug(message)
        abort(404, message)

    return disaster_recovery_policy.to_json()


@ibm_draas.route('/draas-policies/<draas_policy_id>', methods=['DELETE'])
@authenticate
@input(DisasterRecoveryPolicyQuerySchema, location='query')
@output(DisasterRecoveryDeletePolicyOutSchema, status_code=204)
def delete_ibm_draas_policy(draas_policy_id, draas_policy_query_params, user):
    """
    Delete IBM Draas Policy.
    This request returns an IBM Draas Policy id.
    """
    cloud_id = draas_policy_query_params["cloud_id"]
    authorize_and_get_ibm_cloud(cloud_id=cloud_id, user=user)

    draas_policy = ibmdb.session.query(DisasterRecoveryScheduledPolicy).filter_by(
        id=draas_policy_id, cloud_id=draas_policy_query_params["cloud_id"]).first()
    if not draas_policy:
        message = f"No Disaster recovery Policy found with ID {draas_policy_id}"
        LOGGER.debug(message)
        abort(404, message)

    ibmdb.session.delete(draas_policy)
    ibmdb.session.commit()


@ibm_draas.route('/draas-policies', methods=['PUT'])
@authenticate
@input(DisasterRecoveryPolicyQuerySchema, location='query')
@input(DisasterRecoveryPolicyInSchema)
@output(DisasterRecoveryPolicyOutSchema)
def create_ibm_draas_policy(draas_policy_query_params, draas_policy_params, user):
    """
    Add IBM Draas Policy.
    """
    cloud_id = draas_policy_query_params["cloud_id"]
    cloud = authorize_and_get_ibm_cloud(cloud_id=cloud_id, user=user)

    draas_policy = ibmdb.session.query(DisasterRecoveryScheduledPolicy).filter_by(
        scheduled_cron_pattern=draas_policy_params["scheduled_cron_pattern"],
        backup_count=draas_policy_params.get("backup_count", 1),
        cloud_id=draas_policy_query_params["cloud_id"]).first()
    if not draas_policy:
        draas_policy = DisasterRecoveryScheduledPolicy(
            scheduled_cron_pattern=draas_policy_params["scheduled_cron_pattern"],
            backup_count=draas_policy_params.get("backup_count", 1),
            description=draas_policy_params.get("description")
        )

        draas_policy.ibm_cloud = cloud
        ibmdb.session.commit()

    return draas_policy.to_json()
