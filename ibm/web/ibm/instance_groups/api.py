import logging

from apiflask import abort, APIBlueprint, input, output

from ibm.auth import authenticate
from ibm.common.req_resp_schemas.schemas import get_pagination_schema, IBMRegionalResourceListQuerySchema, \
    PaginationQuerySchema, WorkflowRootOutSchema
from ibm.middleware import log_activity
from ibm.models import IBMInstanceGroup, IBMInstanceGroupManager, IBMInstanceGroupManagerPolicy, \
    IBMInstanceGroupMembership, WorkflowRoot, WorkflowTask
from ibm.web import db as ibmdb
from ibm.web.common.utils import authorize_and_get_ibm_cloud, create_ibm_resource_creation_workflow, \
    get_paginated_response_json, verify_and_get_region, verify_references
from .schemas import IBMInstanceGroupInSchema, IBMInstanceGroupOutSchema, IBMInstanceGroupResourceSchema, \
    IBMInstanceGroupUpdateSchema

LOGGER = logging.getLogger(__name__)
ibm_instance_groups = APIBlueprint('ibm_instance_groups', __name__, tag="IBM Instance Groups")


@ibm_instance_groups.post('/instance_groups')
@authenticate
@log_activity
@input(IBMInstanceGroupInSchema)
@output(WorkflowRootOutSchema, status_code=202)
def create_ibm_instance_group(data, user):
    """
    Create IBM Instance Group
    This request create an instance group on IBM Cloud
    """
    cloud_id = data["ibm_cloud"]["id"]
    region_id = data["region"]["id"]
    resource_json = data["resource_json"]

    ibm_cloud = authorize_and_get_ibm_cloud(cloud_id=cloud_id, user=user)
    verify_and_get_region(ibm_cloud=ibm_cloud, region_id=region_id)

    verify_references(
        cloud_id=cloud_id, body_schema=IBMInstanceGroupInSchema, resource_schema=IBMInstanceGroupResourceSchema,
        data=data
    )

    workflow_root = create_ibm_resource_creation_workflow(
        user=user, resource_type=IBMInstanceGroup, data=data, validate=False
    )
    managers = resource_json.get("instance_group_managers")
    policies = resource_json.get("instance_group_manager_policies")
    if managers:
        manager_data = {
            "ibm_cloud": {"id": cloud_id},
            "region": {"id": region_id},
            "instance_group": {"name": resource_json["name"]},
            "resource_json": managers
        }

        manager_creation_task = WorkflowTask(
            task_type=WorkflowTask.TYPE_CREATE, resource_type=IBMInstanceGroupManager.__name__,
            task_metadata={"resource_data": manager_data}
        )

        if policies:
            policy_data = {
                "ibm_cloud": {"id": cloud_id},
                "region": {"id": region_id},
                "instance_group": {"name": resource_json["name"]},
                "resource_json": policies
            }

            policies_creation_task = WorkflowTask(
                task_type=WorkflowTask.TYPE_CREATE, resource_type=IBMInstanceGroupManagerPolicy.__name__,
                task_metadata={"resource_data": policy_data}
            )

            creation_task = workflow_root.next_tasks[0]
            creation_task.add_next_task(manager_creation_task)
            manager_creation_task.add_next_task(policies_creation_task)
            ibmdb.session.commit()

        creation_task = workflow_root.next_tasks[0]
        creation_task.add_next_task(manager_creation_task)
        ibmdb.session.add(workflow_root)
        ibmdb.session.commit()

    creation_task = workflow_root.next_tasks[0]
    ibmdb.session.add(workflow_root)
    ibmdb.session.commit()

    return workflow_root.to_json()


@ibm_instance_groups.get('/instance_groups/<instance_group_id>')
@authenticate
@output(IBMInstanceGroupOutSchema, status_code=200)
def get_ibm_instance_group(instance_group_id, user):
    """
    Get IBM Instance Group
    This request will fetch Instance Groups from IBM Cloud
    """
    instance_group = ibmdb.session.query(IBMInstanceGroup).filter_by(
        id=instance_group_id
    ).join(IBMInstanceGroup.ibm_cloud).filter_by(
        user_id=user["id"], project_id=user["project_id"], deleted=False
    ).first()
    if not instance_group:
        message = f"IBM Instance Group {instance_group_id} does not exist"
        LOGGER.debug(message)
        abort(404, message)
    return instance_group.to_json()


@ibm_instance_groups.get('/instance_groups')
@authenticate
@input(IBMRegionalResourceListQuerySchema, location='query')
@input(PaginationQuerySchema, location='query')
@output(get_pagination_schema(IBMInstanceGroupOutSchema))
def list_ibm_instance_groups(regional_res_query_params, pagination_query_params, user):
    """
    List IBM Instance Groups
    This request fetches all instance groups from IBM Cloud
    """
    cloud_id = regional_res_query_params["cloud_id"]
    region_id = regional_res_query_params.get("region_id")

    ibm_cloud = authorize_and_get_ibm_cloud(cloud_id=cloud_id, user=user)

    instance_groups_query = ibmdb.session.query(IBMInstanceGroup).filter_by(cloud_id=cloud_id)

    if region_id:
        verify_and_get_region(ibm_cloud=ibm_cloud, region_id=region_id)
        instance_groups_query = instance_groups_query.filter_by(region_id=region_id)

    instance_groups_page = instance_groups_query.paginate(
        page=pagination_query_params["page"], per_page=pagination_query_params["per_page"], error_out=False
    )
    if not instance_groups_page.items:
        return '', 204

    return get_paginated_response_json(
        items=[item.to_json() for item in instance_groups_page.items],
        pagination_obj=instance_groups_page
    )


@ibm_instance_groups.patch('/instance_groups/<instance_group_id>')
@authenticate
@input(IBMInstanceGroupUpdateSchema)
@output(WorkflowRootOutSchema, status_code=202)
def update_ibm_instance_group(instance_group_id, data, user):
    """
    Update IBM Instance Group
    This request updates an Instance Group
    """
    abort(404)


@ibm_instance_groups.delete('/instance_groups/<instance_group_id>')
@authenticate
@log_activity
@output(WorkflowRootOutSchema, status_code=202)
def delete_ibm_instance_group(instance_group_id, user):
    """
    Delete IBM Instance Group
    This request deletes an IBM Instance Group provided its ID.
    """
    instance_group = ibmdb.session.query(IBMInstanceGroup).filter_by(
        id=instance_group_id
    ).join(IBMInstanceGroup.ibm_cloud).filter_by(
        user_id=user["id"], project_id=user["project_id"], deleted=False
    ).first()
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
        resource_type=IBMInstanceGroup.__name__,
        resource_id=instance_group.id
    )

    membership_deletion_task = WorkflowTask(
        task_type=WorkflowTask.TYPE_DELETE,
        resource_type=f'{IBMInstanceGroupMembership.__name__}-{IBMInstanceGroup.__name__}',
        resource_id=instance_group.id
    )

    workflow_root.add_next_task(workflow_task)
    workflow_task.add_previous_task(membership_deletion_task)
    ibmdb.session.add(workflow_root)
    ibmdb.session.commit()
    return workflow_root.to_json(metadata=True)
