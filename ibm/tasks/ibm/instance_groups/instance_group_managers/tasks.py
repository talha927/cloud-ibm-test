import logging
from copy import deepcopy
from ibm_cloud_sdk_core import ApiException

from ibm import get_db_session
from ibm.common.clients.ibm_clients import InstanceGroupsClient
from ibm.common.utils import update_id_or_name_references
from ibm.models import IBMCloud, IBMInstanceGroup, IBMInstanceGroupManager, WorkflowTask
from ibm.tasks.celery_app import celery_app as celery
from ibm.tasks.common.tasks_base import IBMWorkflowTasksBase
from ibm.tasks.ibm.task_utils import load_previous_associated_resources
from ibm.web.ibm.instance_groups.instance_group_managers.schemas import IBMInstanceGroupManagerInSchema, \
    IBMInstanceGroupManagerResourceSchema

LOGGER = logging.getLogger(__name__)


@celery.task(name="create_instance_group_manager", base=IBMWorkflowTasksBase)
def create_instance_group_manager(workflow_task_id):
    """
    Create an IBM Instance Group Manager on IBM Cloud
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

        region_name = instance_group.region.name
        instance_group_resource_id = instance_group.resource_id

        previous_resources = load_previous_associated_resources(task=workflow_task, session=db_session)
        update_id_or_name_references(
            cloud_id=cloud_id, resource_json=resource_data, resource_schema=IBMInstanceGroupManagerInSchema,
            db_session=db_session, previous_resources=previous_resources
        )

        update_id_or_name_references(
            cloud_id=cloud_id, resource_json=resource_json, resource_schema=IBMInstanceGroupManagerResourceSchema,
            db_session=db_session, previous_resources=previous_resources
        )

    try:
        client = InstanceGroupsClient(cloud_id=cloud_id, region=region_name)
        resp_json = client.create_instance_group_manager(instance_group_id=instance_group_resource_id,
                                                         instance_group_manager_prototype=resource_json)
    except ApiException as ex:
        with get_db_session() as db_session:
            workflow_task = db_session.query(WorkflowTask).filter_by(id=workflow_task_id).first()
            if not workflow_task:
                return

            workflow_task.status = WorkflowTask.STATUS_FAILED
            workflow_task.message = f"Creation Failed. Reason: {str(ex.message)}"
            db_session.commit()

        LOGGER.info("Create Instance Group Manager failed with status code " + str(ex.code) + ": " + ex.message)
        return

    with get_db_session() as db_session:
        workflow_task = db_session.query(WorkflowTask).filter_by(id=workflow_task_id).first()
        if not workflow_task:
            return
        ibm_cloud = db_session.query(IBMCloud).filter_by(id=cloud_id).first()
        if not ibm_cloud:
            workflow_task.status = WorkflowTask.STATUS_FAILED
            workflow_task.message = \
                f"IBMCloud '{cloud_id}' not found"
            db_session.commit()
            LOGGER.info(workflow_task.message)
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
            instance_group_manager = IBMInstanceGroupManager.from_ibm_json_body(resp_json)
            instance_group_manager.ibm_cloud = ibm_cloud
            instance_group_manager.instance_group = instance_group
            instance_group_manager_id = instance_group_manager.id
            workflow_task.status = WorkflowTask.STATUS_SUCCESSFUL
            workflow_task.resource_id = instance_group_manager_id
            db_session.commit()

    LOGGER.info(
        f"IBMInstanceGroupManager successfully created for instance Group "
        f"{instance_group_dict.get('id') or instance_group_dict.get('name')}")


@celery.task(name="delete_instance_group_manager", base=IBMWorkflowTasksBase)
def delete_instance_group_manager(workflow_task_id):
    """
    IBM Instance Group Manager deletion on IBM Cloud
    :param workflow_task_id:
    :return:
    """
    with get_db_session() as db_session:
        workflow_task: WorkflowTask = db_session.get(WorkflowTask, workflow_task_id)
        if not workflow_task:
            return

        workflow_task.status = WorkflowTask.STATUS_RUNNING
        db_session.commit()

        instance_group_manager_id = workflow_task.resource_id
        instance_group_manager = db_session.query(IBMInstanceGroupManager).filter_by(
            id=instance_group_manager_id).first()
        if not instance_group_manager:
            workflow_task.status = WorkflowTask.STATUS_FAILED
            workflow_task.message = \
                f"IBMInstanceGroupManager '{instance_group_manager_id}' not found"
            db_session.commit()
            LOGGER.info(workflow_task.message)
            return

        cloud_id = instance_group_manager.instance_group.cloud_id
        region_name = instance_group_manager.instance_group.region.name
        instance_group_resource_id = instance_group_manager.instance_group.resource_id
        instance_group_manager_resource_id = instance_group_manager.resource_id

    try:
        instance_group_client = InstanceGroupsClient(cloud_id, region=region_name)
        instance_group_client.delete_instance_group_manager(
            instance_group_id=instance_group_resource_id, instance_group_manager_id=instance_group_manager_resource_id)
        instance_group_client.get_instance_group_manager(
            instance_group_id=instance_group_resource_id,
            instance_group_manager_resource_id=instance_group_manager_resource_id)

    except ApiException as ex:
        with get_db_session() as db_session:
            workflow_task: WorkflowTask = db_session.get(WorkflowTask, workflow_task_id)
            if not workflow_task:
                return

            if ex.code == 404:
                instance_group_manager: IBMInstanceGroupManager = db_session.get(
                    IBMInstanceGroupManager, workflow_task.resource_id)
                if instance_group_manager:
                    db_session.delete(instance_group_manager)

                workflow_task.status = WorkflowTask.STATUS_SUCCESSFUL
                LOGGER.info(
                    f"IBM Instance Group Manager {workflow_task.resource_id} for cloud {cloud_id} deletion successful.")

                db_session.commit()
                return
            else:
                workflow_task.status = WorkflowTask.STATUS_FAILED
                message = f"Cannot delete the Instance Group Manager" \
                          f"{workflow_task.resource_id} due to reason: {str(ex.message)}"
                workflow_task.message = message
                db_session.commit()
                LOGGER.info(message)
                return

    LOGGER.info(f"IBM Instance Group Manager {workflow_task.resource_id} for cloud {cloud_id} deletion successful.")


@celery.task(name="update_instance_group_manager", base=IBMWorkflowTasksBase)
def update_instance_group_manager(workflow_task_id):
    """
    Update an IBM Instance Group Manager on IBM Cloud
    """
    with get_db_session() as db_session:
        workflow_task: WorkflowTask = db_session.get(WorkflowTask, workflow_task_id)
        if not workflow_task:
            return

        workflow_task.status = WorkflowTask.STATUS_RUNNING
        db_session.commit()

        resource_data = deepcopy(workflow_task.task_metadata["resource_data"])

        instance_group_manager_id = workflow_task.resource_id
        instance_group_manager = db_session.query(IBMInstanceGroupManager).filter_by(
            id=instance_group_manager_id).first()
        if not instance_group_manager:
            workflow_task.status = WorkflowTask.STATUS_FAILED
            workflow_task.message = \
                f"IBMInstanceGroupManager '{instance_group_manager_id}' not found"
            db_session.commit()
            LOGGER.info(workflow_task.message)
            return

        cloud_id = instance_group_manager.instance_group.cloud_id
        region_name = instance_group_manager.instance_group.region.name
        instance_group_resource_id = instance_group_manager.instance_group.resource_id
        instance_group_manager_resource_id = instance_group_manager.resource_id
        resource_data.pop('ibm_cloud', None)
        resource_data.pop('instance_group', None)

    try:
        client = InstanceGroupsClient(cloud_id=cloud_id, region=region_name)
        resp_json = client.update_instance_group_manager(instance_group_id=instance_group_resource_id,
                                                         instance_group_manager_id=instance_group_manager_resource_id,
                                                         instance_group_manager_json=resource_data)
    except ApiException as ex:
        with get_db_session() as db_session:
            workflow_task = db_session.query(WorkflowTask).filter_by(id=workflow_task_id).first()
            if not workflow_task:
                return

            workflow_task.status = WorkflowTask.STATUS_FAILED
            workflow_task.message = str(ex.message)
            ibm_cloud = db_session.query(IBMCloud).filter_by(id=workflow_task.resource_id).first()
            if ibm_cloud:
                ibm_cloud.status = IBMCloud.STATUS_INVALID
            db_session.commit()

        LOGGER.info(str(ex.message))
        return

    with get_db_session() as db_session:
        workflow_task = db_session.query(WorkflowTask).filter_by(id=workflow_task_id).first()
        if not workflow_task:
            return

        ibm_cloud = db_session.query(IBMCloud).filter_by(id=cloud_id).first()
        if not ibm_cloud:
            workflow_task.status = WorkflowTask.STATUS_FAILED
            workflow_task.message = f"IBMCloud '{cloud_id}' not found"
            db_session.commit()
            LOGGER.info(workflow_task.message)
            return

        with db_session.no_autoflush:
            instance_group_manager = db_session.query(IBMInstanceGroupManager).filter_by(
                id=instance_group_manager_id).first()
            if not instance_group_manager:
                workflow_task.status = WorkflowTask.STATUS_FAILED
                workflow_task.message = \
                    f"IBMInstanceGroupManager '{instance_group_manager_id}' not found"
                db_session.commit()
                LOGGER.info(workflow_task.message)
                return

            configured_ig_manager = IBMInstanceGroupManager.from_ibm_json_body(resp_json)
            instance_group_manager.update_from_obj(configured_ig_manager)
            if instance_group_manager.manager_type == IBMInstanceGroupManager.MANAGER_TYPE_AUTOSCALE:
                instance_group_manager.auto_scale_prototype.update_from_obj(instance_group_manager.auto_scale_prototype)
            elif instance_group_manager.manager_type == IBMInstanceGroupManager.MANAGER_TYPE_SCHEDULED:
                instance_group_manager.update_from_obj(instance_group_manager)

            workflow_task.status = WorkflowTask.STATUS_SUCCESSFUL
            db_session.commit()
        LOGGER.info(
            f"IBMInstanceGroupManager successfully updated with ID {instance_group_manager.id}")
