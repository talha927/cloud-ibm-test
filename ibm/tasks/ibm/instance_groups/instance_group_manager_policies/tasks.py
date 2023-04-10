import logging
from copy import deepcopy
from ibm_cloud_sdk_core import ApiException

from ibm import get_db_session
from ibm.common.clients.ibm_clients import InstanceGroupsClient
from ibm.common.utils import update_id_or_name_references
from ibm.models import IBMInstanceGroup, IBMInstanceGroupManager, IBMInstanceGroupManagerPolicy, WorkflowTask
from ibm.tasks.celery_app import celery_app as celery
from ibm.tasks.common.tasks_base import IBMWorkflowTasksBase
from ibm.tasks.ibm.task_utils import load_previous_associated_resources
from ibm.web.ibm.instance_groups.instance_group_manager_policies.schemas import IBMInstanceGroupManagerPolicyInSchema, \
    IBMInstanceGroupManagerPolicyResourceSchema

LOGGER = logging.getLogger(__name__)


@celery.task(name="create_instance_group_manager_policy", base=IBMWorkflowTasksBase)
def create_instance_group_manager_policy(workflow_task_id):
    """
    Create an IBM Instance Group Manager Policy on IBM Cloud
    """
    with get_db_session() as db_session:
        workflow_task = db_session.query(WorkflowTask).filter_by(id=workflow_task_id).first()
        if not workflow_task:
            return

        workflow_task.status = WorkflowTask.STATUS_RUNNING
        db_session.commit()

        resource_data = deepcopy(workflow_task.task_metadata["resource_data"])
        resource_json = deepcopy(resource_data["resource_json"])
        cloud_id = resource_data["ibm_cloud"]["id"]
        instance_group_dict = deepcopy(resource_data["instance_group"])

        instance_group = \
            db_session.query(IBMInstanceGroup).filter_by(**instance_group_dict, cloud_id=cloud_id).first()
        if not instance_group:
            workflow_task.status = WorkflowTask.STATUS_FAILED
            workflow_task.message = \
                f"IBMInstanceGroup '{instance_group_dict.get('id') or instance_group_dict.get('name')}' not found"
            db_session.commit()
            LOGGER.info(workflow_task.message)
            return
        manager = instance_group.managers.filter_by(
            manager_type=IBMInstanceGroupManager.MANAGER_TYPE_AUTOSCALE).first()

        region_name = instance_group.region.name
        instance_group_resource_id = instance_group.resource_id
        instance_group_manager_resource_id = manager.resource_id

        previous_resources = load_previous_associated_resources(task=workflow_task, session=db_session)
        update_id_or_name_references(
            cloud_id=cloud_id, resource_json=resource_data, resource_schema=IBMInstanceGroupManagerPolicyInSchema,
            db_session=db_session, previous_resources=previous_resources
        )

        update_id_or_name_references(
            cloud_id=cloud_id, resource_json=resource_json, resource_schema=IBMInstanceGroupManagerPolicyResourceSchema,
            db_session=db_session, previous_resources=previous_resources
        )

    try:
        client = InstanceGroupsClient(cloud_id=cloud_id, region=region_name)
        resp_json = client.create_instance_group_manager_policy(
            instance_group_id=instance_group_resource_id,
            instance_group_manager_id=instance_group_manager_resource_id,
            instance_group_manager_policy_prototype=resource_json)
    except ApiException as ex:
        with get_db_session() as db_session:
            workflow_task = db_session.query(WorkflowTask).filter_by(id=workflow_task_id).first()
            if not workflow_task:
                return

            workflow_task.status = WorkflowTask.STATUS_FAILED
            workflow_task.message = f"Creation Failed. Reason: {str(ex.message)}"
            db_session.commit()

        LOGGER.info("Create Instance Group Manager Policy failed with status code " + str(ex.code) + ": " + ex.message)
        return

    with get_db_session() as db_session:
        workflow_task = db_session.query(WorkflowTask).filter_by(id=workflow_task_id).first()
        if not workflow_task:
            return

        with db_session.no_autoflush:
            instance_group = \
                db_session.query(IBMInstanceGroup).filter_by(**instance_group_dict, cloud_id=cloud_id).first()
            if not instance_group:
                workflow_task.status = WorkflowTask.STATUS_FAILED
                workflow_task.message = \
                    f"IBMInstanceGroup '{instance_group_dict.get('id') or instance_group_dict.get('name')}' not found"
                db_session.commit()
                LOGGER.info(workflow_task.message)
                return

            instance_group_manager_policy = IBMInstanceGroupManagerPolicy.from_ibm_json_body(resp_json)
            instance_group_manager_policy.instance_group_manager = manager
            db_session.add(instance_group_manager_policy)
            db_session.commit()
            workflow_task.status = WorkflowTask.STATUS_SUCCESSFUL
            workflow_task.resource_id = instance_group_manager_policy.id
            message = f"IBM Instance Group Manager Policy for cloud {cloud_id} creation successful"

        db_session.commit()
    LOGGER.info(message)


@celery.task(name="delete_instance_group_manager_policy", base=IBMWorkflowTasksBase)
def delete_instance_group_manager_policy(workflow_task_id):
    """
    IBM Instance Group Manager Policy deletion on IBM Cloud
    :param workflow_task_id:
    :return:
    """
    with get_db_session() as db_session:
        workflow_task: WorkflowTask = db_session.get(WorkflowTask, workflow_task_id)
        if not workflow_task:
            return

        workflow_task.status = WorkflowTask.STATUS_RUNNING
        db_session.commit()

        instance_group_manager_policy_id = workflow_task.resource_id
        instance_group_manager_policy = db_session.query(IBMInstanceGroupManagerPolicy).filter_by(
            id=instance_group_manager_policy_id).first()
        if not instance_group_manager_policy:
            workflow_task.status = WorkflowTask.STATUS_FAILED
            workflow_task.message = \
                f"IBMInstanceGroupManagerPolicy '{instance_group_manager_policy_id}' not found"
            db_session.commit()
            LOGGER.info(workflow_task.message)
            return

        cloud_id = instance_group_manager_policy.instance_group_manager.instance_group.cloud_id
        region_name = instance_group_manager_policy.instance_group_manager.instance_group.region.name
        instance_group_resource_id = instance_group_manager_policy.instance_group_manager.instance_group.resource_id
        instance_group_manager_resource_id = instance_group_manager_policy.instance_group_manager.resource_id
        instance_group_manager_policy_resource_id = instance_group_manager_policy.resource_id

    try:
        instance_group_client = InstanceGroupsClient(cloud_id, region=region_name)
        instance_group_client.delete_instance_group_manager_policy(
            instance_group_id=instance_group_resource_id,
            instance_group_manager_id=instance_group_manager_resource_id,
            instance_group_manager_policy_id=instance_group_manager_policy_resource_id)
        instance_group_client.get_instance_group_manager_policy(
            instance_group_id=instance_group_resource_id,
            instance_group_manager_id=instance_group_manager_resource_id,
            instance_group_manager_policy_id=instance_group_manager_policy_resource_id)

    except ApiException as ex:
        with get_db_session() as db_session:
            workflow_task: WorkflowTask = db_session.get(WorkflowTask, workflow_task_id)
            if not workflow_task:
                return

            if ex.code == 404:
                instance_group_manager_policy: IBMInstanceGroupManagerPolicy = db_session.get(
                    IBMInstanceGroupManagerPolicy, workflow_task.resource_id)
                if instance_group_manager_policy:
                    db_session.delete(instance_group_manager_policy)

                workflow_task.status = WorkflowTask.STATUS_SUCCESSFUL
                LOGGER.info(
                    f"IBM Instance Group Manager Policy {workflow_task.resource_id} for cloud {cloud_id} deletion "
                    f"successful.")

                db_session.commit()
                return
            else:
                workflow_task.status = WorkflowTask.STATUS_FAILED
                message = f"Cannot delete the Instance Group Manager Policy" \
                          f"{workflow_task.resource_id} due to reason: {str(ex.message)}"
                workflow_task.message = message
                db_session.commit()
                LOGGER.info(message)
                return

    LOGGER.info(f"IBM Instance Group Manager Policy {workflow_task.resource_id} for cloud {cloud_id} deletion "
                f"successful.")
