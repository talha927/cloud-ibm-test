import logging
from copy import deepcopy
from ibm_cloud_sdk_core import ApiException

from ibm import get_db_session
from ibm.common.clients.ibm_clients import InstanceGroupsClient
from ibm.common.utils import update_id_or_name_references
from ibm.models import IBMInstanceGroup, IBMInstanceGroupManager, IBMInstanceGroupManagerAction, WorkflowTask
from ibm.tasks.celery_app import celery_app as celery
from ibm.tasks.common.tasks_base import IBMWorkflowTasksBase
from ibm.tasks.ibm.task_utils import load_previous_associated_resources
from ibm.web.ibm.instance_groups.instance_group_manager_actions.schemas import IBMInstanceGroupManagerActionInSchema, \
    IBMInstanceGroupManagerActionResourceSchema

LOGGER = logging.getLogger(__name__)


@celery.task(name="create_instance_group_manager_action", base=IBMWorkflowTasksBase)
def create_instance_group_manager_action(workflow_task_id):
    """
    Create an IBM Instance Group Manager Action on IBM Cloud
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
        instance_group_manager_dict = deepcopy(resource_data["instance_group_manager"])

        instance_group = \
            db_session.query(IBMInstanceGroup).filter_by(**instance_group_dict, cloud_id=cloud_id).first()
        if not instance_group:
            workflow_task.status = WorkflowTask.STATUS_FAILED
            workflow_task.message = \
                f"IBMInstanceGroup '{instance_group_dict.get('id') or instance_group_dict.get('name')}' not found"
            db_session.commit()
            LOGGER.info(workflow_task.message)
            return

        instance_group_manager = \
            db_session.query(IBMInstanceGroupManager).filter_by(
                **instance_group_manager_dict, instance_group_id=instance_group.id).first()
        if not instance_group_manager:
            workflow_task.status = WorkflowTask.STATUS_FAILED
            workflow_task.message = \
                f"IBMInstanceGroupManager '" \
                f"{instance_group_manager_dict.get('id') or instance_group_manager_dict.get('name')}' not found"
            db_session.commit()
            LOGGER.info(workflow_task.message)
            return

        auto_scale_manager_id = resource_json.get("manager", {}).get("id")
        if auto_scale_manager_id:
            autoscale_instance_group_manager = \
                db_session.query(IBMInstanceGroupManager).filter_by(id=auto_scale_manager_id).first()
            if not autoscale_instance_group_manager:
                workflow_task.status = WorkflowTask.STATUS_FAILED
                workflow_task.message = \
                    f"IBM Instance Group Manager {auto_scale_manager_id} not found"
                db_session.commit()
                LOGGER.info(workflow_task.message)
                return
        if resource_json.get("manager", {}).get("id"):
            resource_json["manager"]["id"] = autoscale_instance_group_manager.resource_id

        region_name = instance_group.region.name
        instance_group_resource_id = instance_group.resource_id
        instance_group_manager_resource_id = instance_group_manager.resource_id

        # This is not required but would help with code consistency
        previous_resources = load_previous_associated_resources(task=workflow_task, session=db_session)
        update_id_or_name_references(
            cloud_id=cloud_id, resource_json=resource_data, resource_schema=IBMInstanceGroupManagerActionInSchema,
            db_session=db_session, previous_resources=previous_resources
        )

        update_id_or_name_references(
            cloud_id=cloud_id, resource_json=resource_json, resource_schema=IBMInstanceGroupManagerActionResourceSchema,
            db_session=db_session, previous_resources=previous_resources
        )

    try:
        client = InstanceGroupsClient(cloud_id=cloud_id, region=region_name)
        resp_json = client.create_instance_group_manager_action(
            instance_group_id=instance_group_resource_id,
            instance_group_manager_id=instance_group_manager_resource_id,
            instance_group_manager_action_prototype=resource_json)
    except ApiException as ex:
        with get_db_session() as db_session:
            workflow_task = db_session.query(WorkflowTask).filter_by(id=workflow_task_id).first()
            if not workflow_task:
                return

            workflow_task.status = WorkflowTask.STATUS_FAILED
            workflow_task.message = f"Creation Failed. Reason: {str(ex.message)}"
            db_session.commit()

        LOGGER.info("Create Instance Group Manager Action failed with status code " + str(ex.code) + ": " + ex.message)
        return

    with get_db_session() as db_session:
        workflow_task = db_session.query(WorkflowTask).filter_by(id=workflow_task_id).first()
        if not workflow_task:
            return

        instance_group_manager_action_status = resp_json["status"]
        instance_group_manager_action_name = resp_json["name"]
        instance_group_manager_action_resource_id = resp_json["id"]
        if instance_group_manager_action_status in [IBMInstanceGroupManagerAction.STATUS_ACTIVE,
                                                    IBMInstanceGroupManagerAction.STATUS_COMPLETED]:
            metadata = workflow_task.task_metadata.copy() if workflow_task.task_metadata else {}
            metadata["ibm_resource_id"] = instance_group_manager_action_resource_id
            workflow_task.task_metadata = metadata

            workflow_task.status = WorkflowTask.STATUS_RUNNING_WAIT
            message = f"IBM Instance Group Manager Action {instance_group_manager_action_name} for cloud {cloud_id}" \
                      f" creation waiting "
        elif instance_group_manager_action_status == IBMInstanceGroupManagerAction.STATUS_INCOMPATIBLE:
            workflow_task.status = WorkflowTask.STATUS_FAILED
            message = "Action parameters are not compatible with the group or manager"
        elif instance_group_manager_action_status == IBMInstanceGroupManagerAction.STATUS_OMITTED:
            workflow_task.status = WorkflowTask.STATUS_FAILED
            message = "Action was not applied because this action's manager was disabled"
        else:
            message = f"IBM Instance Group Manager Action {instance_group_manager_action_name} for cloud {cloud_id}" \
                      f" creation failed"
            workflow_task.message = message
            workflow_task.status = WorkflowTask.STATUS_FAILED
        db_session.commit()
    LOGGER.info(message)


@celery.task(name="create_wait_instance_group_manager_action", base=IBMWorkflowTasksBase)
def create_wait_instance_group_manager_action(workflow_task_id):
    """
    Wait for an IBM Instance Group Manager Action creation on IBM Cloud
    """
    with get_db_session() as db_session:
        workflow_task = db_session.query(WorkflowTask).filter_by(id=workflow_task_id).first()
        if not workflow_task:
            return

        workflow_task.status = WorkflowTask.STATUS_RUNNING
        db_session.commit()

        resource_data = deepcopy(workflow_task.task_metadata["resource_data"])
        cloud_id = resource_data["ibm_cloud"]["id"]
        instance_group_dict = deepcopy(resource_data["instance_group"])
        instance_group_manager_dict = deepcopy(resource_data["instance_group_manager"])

        instance_group = \
            db_session.query(IBMInstanceGroup).filter_by(**instance_group_dict, cloud_id=cloud_id).first()
        if not instance_group:
            workflow_task.status = WorkflowTask.STATUS_FAILED
            workflow_task.message = \
                f"IBMInstanceGroup '{instance_group_dict.get('id') or instance_group_dict.get('name')}' not found"
            db_session.commit()
            LOGGER.info(workflow_task.message)
            return

        instance_group_manager = \
            db_session.query(IBMInstanceGroupManager).filter_by(
                **instance_group_manager_dict, instance_group_id=instance_group.id).first()
        if not instance_group_manager:
            workflow_task.status = WorkflowTask.STATUS_FAILED
            workflow_task.message = \
                f"IBMInstanceGroupManager '" \
                f"{instance_group_manager_dict.get('id') or instance_group_manager_dict.get('name')}' not found"
            db_session.commit()
            LOGGER.info(workflow_task.message)
            return

        region_name = instance_group.region.name
        instance_group_resource_id = instance_group.resource_id
        instance_group_manager_resource_id = instance_group_manager.resource_id
        resource_id = workflow_task.task_metadata["ibm_resource_id"]

    try:
        client = InstanceGroupsClient(cloud_id=cloud_id, region=region_name)
        instance_group_manager_action_json = client.get_instance_group_manager_action(
            instance_group_id=instance_group_resource_id,
            instance_group_manager_id=instance_group_manager_resource_id,
            instance_group_manager_action_id=resource_id)
    except ApiException as ex:
        with get_db_session() as db_session:
            workflow_task = db_session.query(WorkflowTask).filter_by(id=workflow_task_id).first()
            if not workflow_task:
                return

            workflow_task.status = WorkflowTask.STATUS_FAILED
            workflow_task.message = f"Creation Failed. Reason: {str(ex.message)}"
            db_session.commit()

        LOGGER.info(
            "Create Wait Instance Group Manager Action failed with status code " + str(ex.code) + ": " + ex.message)
        return

    with get_db_session() as db_session:
        workflow_task = db_session.query(WorkflowTask).filter_by(id=workflow_task_id).first()
        if not workflow_task:
            return
        instance_group_manager_action_name = instance_group_manager_action_json["name"]
        instance_group_manager_action_status = instance_group_manager_action_json["status"]

        if instance_group_manager_action_status in [IBMInstanceGroupManagerAction.STATUS_COMPLETED,
                                                    IBMInstanceGroupManagerAction.STATUS_ACTIVE]:
            with db_session.no_autoflush:
                instance_group = \
                    db_session.query(IBMInstanceGroup).filter_by(**instance_group_dict, cloud_id=cloud_id).first()
                if not instance_group:
                    workflow_task.status = WorkflowTask.STATUS_FAILED
                    workflow_task.message = \
                        f"IBMInstanceGroup '{instance_group_dict.get('id') or instance_group_dict.get('name')}' not " \
                        f"found "
                    db_session.commit()
                    LOGGER.info(workflow_task.message)
                    return

                instance_group_manager = \
                    db_session.query(IBMInstanceGroupManager).filter_by(
                        **instance_group_manager_dict, instance_group_id=instance_group.id).first()
                if not instance_group_manager:
                    workflow_task.status = WorkflowTask.STATUS_FAILED
                    workflow_task.message = \
                        f"IBMInstanceGroupManager '" \
                        f"{instance_group_manager_dict.get('id') or instance_group_manager_dict.get('name')}' not found"
                    db_session.commit()
                    LOGGER.info(workflow_task.message)
                    return

                instance_group_manager_action = IBMInstanceGroupManagerAction.from_ibm_json_body(
                    json_body=instance_group_manager_action_json)
                instance_group_manager_action.instance_group_manager = instance_group_manager
                instance_group_manager_action_id = instance_group_manager_action.id
                db_session.commit()

            workflow_task.status = WorkflowTask.STATUS_SUCCESSFUL
            workflow_task.resource_id = instance_group_manager_action_id
            message = f"IBM Instance Group Manager Action {instance_group_manager_action_name} for cloud {cloud_id} " \
                      f"creation successful"
        elif instance_group_manager_action_status == IBMInstanceGroupManagerAction.STATUS_ACTIVE:
            workflow_task.status = WorkflowTask.STATUS_RUNNING_WAIT
            message = f"IBM Instance Group Manager Action {instance_group_manager_action_name} for cloud " \
                      f"{cloud_id} creation waiting"
        else:
            message = f"IBM Instance Group Manager Action {instance_group_manager_action_name} for cloud" \
                      f" {cloud_id} creation failed"
            workflow_task.message = message
            workflow_task.status = WorkflowTask.STATUS_FAILED
        db_session.commit()
    LOGGER.info(message)


@celery.task(name="delete_instance_group_manager_action", base=IBMWorkflowTasksBase)
def delete_instance_group_manager_action(workflow_task_id):
    """
    Delete an IBM Instance Group Manager Action
    :param workflow_task_id:
    :return:
    """

    with get_db_session() as db_session:
        workflow_task: WorkflowTask = db_session.get(WorkflowTask, workflow_task_id)
        if not workflow_task:
            return

        workflow_task.status = WorkflowTask.STATUS_RUNNING
        db_session.commit()

        instance_group_manager_action: IBMInstanceGroupManagerAction = db_session.get(
            IBMInstanceGroupManagerAction, workflow_task.resource_id)
        if not instance_group_manager_action:
            workflow_task.status = WorkflowTask.STATUS_FAILED
            workflow_task.message = f"IBM Instance Group Manager Action '{workflow_task.resource_id}' not found"
            db_session.commit()
            LOGGER.info(workflow_task.message)
            return

        cloud_id = instance_group_manager_action.instance_group_manager.instance_group.cloud_id
        region_name = instance_group_manager_action.instance_group_manager.instance_group.region.name
        instance_group_resource_id = instance_group_manager_action.instance_group_manager.instance_group.resource_id
        instance_group_manager_resource_id = instance_group_manager_action.instance_group_manager.resource_id
        instance_group_manager_action_resource_id = instance_group_manager_action.resource_id

    try:
        instance_group_manager_action_client = InstanceGroupsClient(cloud_id, region=region_name)
        instance_group_manager_action_client.delete_instance_group_manager_action(
            instance_group_id=instance_group_resource_id, instance_group_manager_id=instance_group_manager_resource_id,
            instance_group_manager_action_id=instance_group_manager_action_resource_id)
        instance_group_manager_action_json = instance_group_manager_action_client.get_instance_group_manager_action(
            instance_group_id=instance_group_resource_id,
            instance_group_manager_id=instance_group_manager_resource_id,
            instance_group_manager_action_id=instance_group_manager_action_resource_id)

    except ApiException as ex:
        with get_db_session() as db_session:
            workflow_task: WorkflowTask = db_session.get(WorkflowTask, workflow_task_id)
            if not workflow_task:
                return

            if ex.code == 404:
                instance_group_manager_action: IBMInstanceGroupManagerAction = db_session.get(
                    IBMInstanceGroupManagerAction, workflow_task.resource_id)
                if instance_group_manager_action:
                    db_session.delete(instance_group_manager_action)

                workflow_task.status = WorkflowTask.STATUS_SUCCESSFUL
                LOGGER.info(
                    f"IBM Instance Group Manager Action {workflow_task.resource_id} for cloud {cloud_id} deletion "
                    f"successful.")
                db_session.commit()
                return
            else:
                workflow_task.status = WorkflowTask.STATUS_FAILED
                message = f"Cannot delete the Instance Group Manager Action {workflow_task.resource_id} due to" \
                          f"reason: {str(ex.message)}"
                workflow_task.message = message
                db_session.commit()
                LOGGER.info(message)
                return

    with get_db_session() as db_session:
        workflow_task: WorkflowTask = db_session.get(WorkflowTask, workflow_task_id)
        if not workflow_task:
            return

        instance_group_manager_action_status = instance_group_manager_action_json["status"]
        instance_group_manager_action_name = instance_group_manager_action_json["name"]
        if instance_group_manager_action_status in [IBMInstanceGroupManagerAction.STATUS_ACTIVE,
                                                    IBMInstanceGroupManagerAction.STATUS_COMPLETED]:
            workflow_task.status = WorkflowTask.STATUS_RUNNING_WAIT
            message = f"IBM Instance Group Manager Action {instance_group_manager_action_name} for cloud {cloud_id} " \
                      f"deletion waiting"
        else:
            message = f"IBM Instance Group Manager Action {instance_group_manager_action_name} for cloud {cloud_id} " \
                      f"deletion failed"
            workflow_task.message = message
            workflow_task.status = WorkflowTask.STATUS_FAILED

        db_session.commit()
    LOGGER.info(message)


@celery.task(name="delete_wait_instance_group_manager_action", base=IBMWorkflowTasksBase)
def delete_wait_instance_group_manager_action(workflow_task_id):
    """
    Wait for an IBM Instance Group Manager Action deletion on IBM Cloud
    :param workflow_task_id:
    :return:
    """
    with get_db_session() as db_session:
        workflow_task: WorkflowTask = db_session.get(WorkflowTask, workflow_task_id)
        if not workflow_task:
            return

        workflow_task.status = WorkflowTask.STATUS_RUNNING
        db_session.commit()

        instance_group_manager_action: IBMInstanceGroupManagerAction = db_session.get(IBMInstanceGroupManagerAction,
                                                                                      workflow_task.resource_id)
        if not instance_group_manager_action:
            workflow_task.status = WorkflowTask.STATUS_SUCCESSFUL
            db_session.commit()
            LOGGER.info(f"IBMInstanceGroupManagerAction '{workflow_task.resource_id}' deletion successful.")
            return

        cloud_id = instance_group_manager_action.instance_group_manager.instance_group.cloud_id
        region_name = instance_group_manager_action.instance_group_manager.instance_group.region.name
        instance_group_resource_id = instance_group_manager_action.instance_group_manager.instance_group.resource_id
        instance_group_manager_resource_id = instance_group_manager_action.instance_group_manager.resource_id
        instance_group_manager_action_resource_id = instance_group_manager_action.resource_id

    try:
        instance_group_manager_action_client = InstanceGroupsClient(cloud_id, region=region_name)
        resp_json = instance_group_manager_action_client.get_instance_group_manager_action(
            instance_group_id=instance_group_resource_id,
            instance_group_manager_id=instance_group_manager_resource_id,
            instance_group_manager_action_id=instance_group_manager_action_resource_id)

    except ApiException as ex:
        with get_db_session() as db_session:
            workflow_task: WorkflowTask = db_session.get(WorkflowTask, workflow_task_id)
            if not workflow_task:
                return

            if ex.code == 404:
                instance_group_manager_action: IBMInstanceGroupManagerAction = db_session.get(
                    IBMInstanceGroupManagerAction, workflow_task.resource_id)
                if instance_group_manager_action:
                    db_session.delete(instance_group_manager_action)

                workflow_task.status = WorkflowTask.STATUS_SUCCESSFUL
                LOGGER.info(
                    f"IBM Instance Group Manager Action {workflow_task.resource_id} for cloud {cloud_id} deletion "
                    f"successful.")
                db_session.commit()
                return
            else:
                workflow_task.status = WorkflowTask.STATUS_FAILED
                message = f"Cannot delete the Instance Group Manager Action {workflow_task.resource_id} due to " \
                          f"reason: {str(ex.message)}"
                workflow_task.message = message
                db_session.commit()
                LOGGER.info(message)
                return

    with get_db_session() as db_session:
        workflow_task: WorkflowTask = db_session.get(WorkflowTask, workflow_task_id)
        if not workflow_task:
            return

        instance_group_manager_action_status = resp_json["status"]
        instance_group_manager_action_name = resp_json["name"]
        if instance_group_manager_action_status in [IBMInstanceGroupManagerAction.STATUS_ACTIVE,
                                                    IBMInstanceGroupManagerAction.STATUS_COMPLETED]:
            workflow_task.status = WorkflowTask.STATUS_RUNNING_WAIT
            message = f"IBM Instance Group Manager Action {instance_group_manager_action_name} for cloud {cloud_id} " \
                      f"deletion waiting"
        else:
            message = f"IBM Instance Group Manager Action {instance_group_manager_action_name} for cloud {cloud_id} " \
                      f"deletion failed"
            workflow_task.message = message
            workflow_task.status = WorkflowTask.STATUS_FAILED

        db_session.commit()
    LOGGER.info(message)
