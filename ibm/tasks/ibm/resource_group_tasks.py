from ibm_cloud_sdk_core import ApiException

from ibm import get_db_session, LOGGER
from ibm.common.clients.ibm_clients import ResourceGroupsClient
from ibm.models import IBMCloud, IBMResourceGroup, WorkflowTask
from ibm.tasks.celery_app import celery_app as celery
from ibm.tasks.common.tasks_base import IBMWorkflowTasksBase


@celery.task(name="update_resource_groups", base=IBMWorkflowTasksBase)
def update_resource_groups(workflow_task_id):
    """
    Update Resource Groups
    """
    with get_db_session() as db_session:
        workflow_task = db_session.query(WorkflowTask).filter_by(id=workflow_task_id).first()
        if not workflow_task:
            return

        workflow_task.status = WorkflowTask.STATUS_RUNNING
        db_session.commit()

        task_metadata = workflow_task.task_metadata
        if not task_metadata:
            workflow_task.status = WorkflowTask.STATUS_FAILED
            workflow_task.message = "Internal Server Error"
            db_session.commit()
            LOGGER.error(workflow_task.message)
            return

        cloud_id = task_metadata["cloud_id"]
        if not cloud_id:
            workflow_task.status = WorkflowTask.STATUS_FAILED
            workflow_task.message = "Internal Server Error"
            db_session.commit()
            LOGGER.error(workflow_task.message)
            return

        ibm_cloud = db_session.query(IBMCloud).filter_by(id=cloud_id).first()
        if not ibm_cloud:
            workflow_task.status = WorkflowTask.STATUS_FAILED
            workflow_task.message = f"IBMCloud '{task_metadata['cloud_id']}' not found"
            db_session.commit()
            LOGGER.error(workflow_task.message)
            return

    try:
        rg_client = ResourceGroupsClient(cloud_id)
        resource_group_dicts = rg_client.list_resource_groups()
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

            LOGGER.error(workflow_task.message)
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
            LOGGER.error(workflow_task.message)
            return

        updated_resource_ids = set([resource_group_dict["id"] for resource_group_dict in resource_group_dicts])
        db_session.query(IBMResourceGroup).filter(
            IBMResourceGroup.cloud_id == cloud_id, IBMResourceGroup.resource_id.not_in(updated_resource_ids)
        ).delete()

        db_resource_groups = db_session.query(IBMResourceGroup).filter_by(cloud_id=cloud_id).all()
        db_rg_resource_id_rg_obj_dict = {
            db_resource_group.resource_id: db_resource_group for db_resource_group in db_resource_groups
        }
        for resource_group_dict in resource_group_dicts:
            parsed_resource_group = IBMResourceGroup.from_ibm_json_body(resource_group_dict)
            if parsed_resource_group.resource_id in db_rg_resource_id_rg_obj_dict:
                db_rg_resource_id_rg_obj_dict[parsed_resource_group.resource_id].update_from_obj(parsed_resource_group)
            else:
                parsed_resource_group.ibm_cloud = ibm_cloud

        workflow_task.status = WorkflowTask.STATUS_SUCCESSFUL
        db_session.commit()
        LOGGER.success(f"Resource groups for {ibm_cloud.id} updated successfully")
