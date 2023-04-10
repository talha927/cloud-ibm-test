import logging

from apiflask import abort, APIBlueprint, input, output

from ibm.auth import authenticate
from ibm.common.req_resp_schemas.schemas import get_pagination_schema, PaginationQuerySchema, WorkflowRootOutSchema
from ibm.models import IBMInstanceGroup, IBMInstanceGroupMembership, WorkflowRoot, WorkflowTask
from ibm.web import db as ibmdb
from ibm.web.common.utils import authorize_and_get_ibm_cloud, compose_ibm_resource_deletion_workflow, \
    get_paginated_response_json
from .schemas import IBMInstanceGroupMembershipListQuerySchema, IBMInstanceGroupMembershipOutSchema, \
    IBMInstanceGroupMembershipUpdateSchema

LOGGER = logging.getLogger(__name__)

ibm_instance_group_memberships = APIBlueprint(
    'ibm_instance_group_memberships', __name__, tag="IBM Instance Groups")


@ibm_instance_group_memberships.get('/instance_group_memberships/<membership_id>')
@authenticate
@output(IBMInstanceGroupMembershipOutSchema, status_code=200)
def get_ibm_instance_group_membership(membership_id, user):
    """
    Get IBM Instance Group Membership
    This request will fetch Instance Group membership from IBM Cloud
    """
    instance_group_membership = ibmdb.session.query(

        IBMInstanceGroupMembership).filter_by(id=membership_id).first()
    if not instance_group_membership:
        message = f"IBM Instance Group Membership {membership_id} does not exist"
        LOGGER.debug(message)
        abort(404, message)
    return instance_group_membership.to_json()


@ibm_instance_group_memberships.get('/instance_group_memberships')
@authenticate
@input(IBMInstanceGroupMembershipListQuerySchema, location='query')
@input(PaginationQuerySchema, location='query')
@output(get_pagination_schema(IBMInstanceGroupMembershipOutSchema))
def list_ibm_instance_group_memberships(instance_group_membership_list_query_params, pagination_query_params, user):
    """
    List IBM Instance Group Memberships
    This request fetches all instance group memberships from IBM Cloud
    """
    cloud_id = instance_group_membership_list_query_params["cloud_id"]
    instance_group_id = instance_group_membership_list_query_params["instance_group_id"]

    authorize_and_get_ibm_cloud(cloud_id=cloud_id, user=user)

    instance_group = ibmdb.session.query(IBMInstanceGroup).filter_by(id=instance_group_id, cloud_id=cloud_id).first()
    if not instance_group:
        message = f"IBM Instance Group {instance_group_id} does not exist"
        LOGGER.debug(message)
        abort(404, message)

    instance_group_membership_query = ibmdb.session.query(IBMInstanceGroupMembership).filter_by(
        instance_group_id=instance_group_id)

    instance_group_memberships_page = instance_group_membership_query.paginate(
        page=pagination_query_params["page"], per_page=pagination_query_params["per_page"], error_out=False
    )
    if not instance_group_memberships_page.items:
        return '', 204

    return get_paginated_response_json(
        items=[item.to_json() for item in instance_group_memberships_page.items],
        pagination_obj=instance_group_memberships_page
    )


@ibm_instance_group_memberships.patch('/instance_group_memberships/<membership_id>')
@authenticate
@input(IBMInstanceGroupMembershipUpdateSchema)
@output(WorkflowRootOutSchema, status_code=202)
def update_ibm_instance_group_membership(membership_id, data, user):
    """
    Update IBM Instance Group Membership
    This request updates an Instance Group Membership
    """
    abort(404)


@ibm_instance_group_memberships.delete('/instance_group_memberships/<membership_id>')
@authenticate
@output(WorkflowRootOutSchema, status_code=202)
def delete_ibm_instance_group_membership(membership_id, user):
    """
    Delete IBM Instance Group Membership
    This request deletes an IBM Instance Group Membership provided its ID.
    """
    instance_group_membership = ibmdb.session.query(
        IBMInstanceGroupMembership).filter_by(id=membership_id).first()
    if not instance_group_membership:
        message = f"IBM Instance Group Membership {membership_id} does not exist"
        LOGGER.debug(message)
        abort(404, message)

    return compose_ibm_resource_deletion_workflow(
        user=user, resource_type=IBMInstanceGroupMembership, resource_id=membership_id
    ).to_json(metadata=True)


@ibm_instance_group_memberships.delete('/instance_group_memberships')
@authenticate
@input(IBMInstanceGroupMembershipListQuerySchema, location='query')
@output(IBMInstanceGroupMembershipOutSchema)
def delete_all_ibm_instance_group_memberships(instance_group_membership_list_query_params, user):
    """
    Delete All IBM Instance Group Memberships
    This request deletes all instance group memberships from IBM Cloud
    """
    cloud_id = instance_group_membership_list_query_params["cloud_id"]
    instance_group_id = instance_group_membership_list_query_params["instance_group_id"]

    authorize_and_get_ibm_cloud(cloud_id=cloud_id, user=user)

    instance_group = ibmdb.session.query(IBMInstanceGroup).filter_by(id=instance_group_id, cloud_id=cloud_id).first()
    if not instance_group:
        message = f"IBM Instance Group {instance_group_id} does not exist"
        LOGGER.debug(message)
        abort(404, message)

    workflow_root = WorkflowRoot(
        user_id=user["id"],
        project_id=user["project_id"],
        workflow_name=f"{IBMInstanceGroup.__name__} ({instance_group.name})",
        workflow_nature="DELETE"
    )
    workflow_task = WorkflowTask(
        task_type=WorkflowTask.TYPE_DELETE,
        resource_type=f'{IBMInstanceGroupMembership.__name__}-{IBMInstanceGroup.__name__}',
        resource_id=instance_group.id
    )
    workflow_root.add_next_task(workflow_task)
    ibmdb.session.add(workflow_root)
    ibmdb.session.commit()
