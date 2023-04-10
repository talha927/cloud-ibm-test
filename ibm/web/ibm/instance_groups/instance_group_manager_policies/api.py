import logging

from apiflask import abort, APIBlueprint, input, output

from ibm.auth import authenticate
from ibm.common.req_resp_schemas.schemas import get_pagination_schema, \
    PaginationQuerySchema, WorkflowRootOutSchema
from ibm.models import IBMInstanceGroupManager, \
    IBMInstanceGroupManagerPolicy
from ibm.web import db as ibmdb
from ibm.web.common.utils import authorize_and_get_ibm_cloud, compose_ibm_resource_deletion_workflow, \
    create_ibm_resource_creation_workflow, \
    get_paginated_response_json, verify_references
from .schemas import IBMInstanceGroupManagerPolicyInSchema, IBMInstanceGroupManagerPolicyOutSchema, \
    IBMInstanceGroupManagerPolicyResourceSchema, IBMInstanceGroupManagerPolicyUpdateSchema
from ..schemas import IBMInstanceGroupListQuerySchema

LOGGER = logging.getLogger(__name__)

ibm_instance_group_manager_policies = APIBlueprint(
    'ibm_instance_group_manager_policies', __name__, tag="IBM Instance Groups")


@ibm_instance_group_manager_policies.post('/instance_group_manager_policies')
@authenticate
@input(IBMInstanceGroupManagerPolicyInSchema)
@output(WorkflowRootOutSchema, status_code=202)
def create_ibm_instance_group_manager_policy(data, user):
    """
    Create IBM Instance Group Manager Policy
    This request create an instance group manager policy on IBM Cloud
    """
    cloud_id = data["ibm_cloud"]["id"]

    authorize_and_get_ibm_cloud(cloud_id=cloud_id, user=user)

    verify_references(
        cloud_id=cloud_id, body_schema=IBMInstanceGroupManagerPolicyInSchema,
        resource_schema=IBMInstanceGroupManagerPolicyResourceSchema, data=data
    )

    workflow_root = create_ibm_resource_creation_workflow(
        user=user, resource_type=IBMInstanceGroupManagerPolicy, data=data, validate=False
    )
    return workflow_root.to_json()


@ibm_instance_group_manager_policies.get('/instance_group_manager_policies/<policy_id>')
@authenticate
@output(IBMInstanceGroupManagerPolicyOutSchema, status_code=200)
def get_ibm_instance_group_manager_policy(policy_id, user):
    """
    Get IBM Instance Group Manager Policy
    This request will fetch Instance Group Manager Policy from IBM Cloud
    """
    instance_group_manager_policy = ibmdb.session.query(
        IBMInstanceGroupManagerPolicy).filter_by(id=policy_id).first()
    if not instance_group_manager_policy:
        message = f"IBM Instance Group Manager Policy {policy_id} does not exist"
        LOGGER.debug(message)
        abort(404, message)
    return instance_group_manager_policy.to_json()


@ibm_instance_group_manager_policies.get('/instance_group_manager_policies')
@authenticate
@input(IBMInstanceGroupListQuerySchema, location='query')
@input(PaginationQuerySchema, location='query')
@output(get_pagination_schema(IBMInstanceGroupManagerPolicyOutSchema))
def list_ibm_instance_group_manager_policies(instance_group_list_query_params, pagination_query_params, user):
    """
    List IBM Instance Group Policies
    This request list all instance group policies from IBM Cloud
    """
    cloud_id = instance_group_list_query_params["cloud_id"]
    instance_group_manager_id = instance_group_list_query_params["instance_group_manager_id"]

    authorize_and_get_ibm_cloud(cloud_id=cloud_id, user=user)

    instance_group_manager = ibmdb.session.query(IBMInstanceGroupManager).filter_by(
        id=instance_group_manager_id).first()
    if not instance_group_manager:
        message = f"IBM Instance Group Manager {instance_group_manager_id} does not exist"
        LOGGER.debug(message)
        abort(404, message)

    instance_group_manager_policy_query = ibmdb.session.query(IBMInstanceGroupManagerPolicy).filter_by(
        manager_id=instance_group_manager_id)

    instance_group_manager_policies_page = instance_group_manager_policy_query.paginate(
        page=pagination_query_params["page"], per_page=pagination_query_params["per_page"], error_out=False
    )
    if not instance_group_manager_policies_page.items:
        return '', 204

    return get_paginated_response_json(
        items=[item.to_json() for item in instance_group_manager_policies_page.items],
        pagination_obj=instance_group_manager_policies_page
    )


@ibm_instance_group_manager_policies.patch('/instance_group_manager_policies/<policy_id>')
@authenticate
@input(IBMInstanceGroupManagerPolicyUpdateSchema)
@output(WorkflowRootOutSchema, status_code=202)
def update_ibm_instance_group_manager_policy(policy_id, data, user):
    """
    Update IBM Instance Group Manager Policy
    This request updates an Instance Group Manager policy
    """
    abort(404)


@ibm_instance_group_manager_policies.delete('/instance_group_manager_policies/<policy_id>')
@authenticate
@output(WorkflowRootOutSchema, status_code=202)
def delete_ibm_instance_group_manager_policy(policy_id, user):
    """
    Delete IBM Instance Group Manager Policy
    This request deletes an IBM Instance Group Manager Policy provided its ID.
    """
    instance_group_manager_policy = ibmdb.session.query(
        IBMInstanceGroupManagerPolicy).filter_by(id=policy_id).first()
    if not instance_group_manager_policy:
        message = f"IBM Instance Group Manager Policy {policy_id} does not exist"
        LOGGER.debug(message)
        abort(404, message)

    authorize_and_get_ibm_cloud(
        cloud_id=instance_group_manager_policy.instance_group_manager.instance_group.ibm_cloud.id, user=user)

    return compose_ibm_resource_deletion_workflow(
        user=user, resource_type=IBMInstanceGroupManagerPolicy, resource_id=policy_id
    ).to_json(metadata=True)
