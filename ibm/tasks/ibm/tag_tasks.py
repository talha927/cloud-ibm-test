from ibm_cloud_sdk_core import ApiException

from ibm import get_db_session, LOGGER
from ibm.common.clients.ibm_clients import TagsClient
from ibm.models import IBMCloud, IBMResourceLog, IBMTag, WorkflowTask
from ibm.tasks.celery_app import celery_app as celery
from ibm.tasks.common.tasks_base import IBMWorkflowTasksBase
from ibm.web.ibm.tags.consts import IBM_TAG_TO_RESOURCE_MAPPER


@celery.task(name="create_tag", base=IBMWorkflowTasksBase)
def create_ibm_tag(workflow_task_id):
    """
    Create an IBM tag on IBM Cloud
    """
    with get_db_session() as db_session:
        workflow_task = db_session.query(WorkflowTask).filter_by(id=workflow_task_id).first()
        if not workflow_task:
            return

        workflow_task.status = WorkflowTask.STATUS_RUNNING
        db_session.commit()

        resource_data = workflow_task.task_metadata["resource_data"]
        resource_json = resource_data["resource_json"]
        cloud_id = resource_data["ibm_cloud"]["id"]

        cloud = db_session.query(IBMCloud).filter_by(id=cloud_id, deleted=False).first()
        if not cloud:
            workflow_task.status = WorkflowTask.STATUS_FAILED
            workflow_task.message = f"IBMCloud '{cloud_id}' not found"
            db_session.commit()
            LOGGER.error(workflow_task.message)
            return

        previous_task = workflow_task.previous_tasks.first()
        resource_id = previous_task.resource_id if previous_task else resource_json.get('resource_id')
        db_resource = db_session.query(IBM_TAG_TO_RESOURCE_MAPPER[resource_json['resource_type']]).filter_by(
            id=resource_id).first()
        if not db_resource:
            workflow_task.status = WorkflowTask.STATUS_FAILED
            msg = f"IBM {resource_json['resource_type']} with ID {resource_id} not found in DB"
            workflow_task.message = msg
            db_session.commit()
            LOGGER.error(msg)
            return

        tag_json = {
            'tag_name': resource_json['tag_name'],
            'resources': [{'resource_id': db_resource.crn}]
        }

    try:
        client = TagsClient(cloud_id=cloud_id)
        client.attach_tag(tag_json=tag_json, tag_type=resource_json['tag_type'])

    except ApiException as ex:
        with get_db_session() as db_session:
            workflow_task = db_session.query(WorkflowTask).filter_by(id=workflow_task_id).first()
            if not workflow_task:
                return

            workflow_task.status = WorkflowTask.STATUS_FAILED
            workflow_task.message = f"Creation Failed. Reason: {str(ex.message)}"
            db_session.commit()

        LOGGER.error(workflow_task.message)
        return

    with get_db_session() as db_session:
        workflow_task = db_session.query(WorkflowTask).filter_by(id=workflow_task_id).first()
        if not workflow_task:
            return

        cloud = db_session.query(IBMCloud).filter_by(id=cloud_id, deleted=False).first()
        if not cloud:
            workflow_task.status = WorkflowTask.STATUS_FAILED
            workflow_task.message = f"IBMCloud '{cloud_id}' not found"
            db_session.commit()
            LOGGER.info(workflow_task.message)
            return

        db_resource = db_session.query(
            IBM_TAG_TO_RESOURCE_MAPPER[resource_json['resource_type']]).filter_by(id=resource_id).first()
        if not db_resource:
            workflow_task.status = WorkflowTask.STATUS_FAILED
            workflow_task.message = f"DB Resource with ID '{resource_json['resource_id']}' not found in DB"
            db_session.commit()
            LOGGER.error(workflow_task.message)
            return

        tag = IBMTag(
            name=resource_json['tag_name'],
            tag_type=resource_json['tag_type'],
            resource_id=db_resource.id,
            resource_crn=db_resource.crn,
            resource_type=resource_json['resource_type']
        )
        tag.cloud_id = cloud_id
        db_session.add(tag)
        log = IBMResourceLog(
            resource_id=f"{tag.resource_id}-{tag.name}", status=IBMResourceLog.STATUS_ADDED,
            resource_type=IBMTag.__name__, data=tag.to_json())
        log.cloud_id = cloud_id
        db_session.add(log)
        workflow_task.resource_id = tag.id
        workflow_task.status = WorkflowTask.STATUS_SUCCESSFUL
        db_session.commit()


@celery.task(name="delete_tag", base=IBMWorkflowTasksBase)
def delete_ibm_tag(workflow_task_id):
    """
    Delete an IBM tag on IBM Cloud
    """
    with get_db_session() as db_session:
        workflow_task = db_session.query(WorkflowTask).filter_by(id=workflow_task_id).first()
        if not workflow_task:
            return

        workflow_task.status = WorkflowTask.STATUS_RUNNING
        db_session.commit()

        tag: IBMTag = db_session.get(IBMTag, workflow_task.resource_id)
        if not tag:
            workflow_task.status = WorkflowTask.STATUS_FAILED
            workflow_task.message = f"IBMTag '{workflow_task.resource_id}' not found"
            db_session.commit()
            LOGGER.info(workflow_task.message)
            return

        db_resource = db_session.query(
            IBM_TAG_TO_RESOURCE_MAPPER[tag.resource_type]).filter_by(id=tag.resource_id).first()
        if not db_resource:
            workflow_task.status = WorkflowTask.STATUS_FAILED
            workflow_task.message = f"DB Resource with ID '{tag.resource_id}' not found in DB"
            db_session.commit()
            LOGGER.info(workflow_task.message)
            return

        cloud_id = tag.cloud_id
        tag_type = tag.tag_type
        tag_json = {
            'tag_name': tag.name,
            'resources': [{'resource_id': db_resource.crn}]
        }

    try:
        client = TagsClient(cloud_id=cloud_id)
        client.detach_tag(tag_json=tag_json, tag_type=tag_type)

    except ApiException as ex:
        with get_db_session() as db_session:
            workflow_task = db_session.query(WorkflowTask).filter_by(id=workflow_task_id).first()
            if not workflow_task:
                return

            workflow_task.status = WorkflowTask.STATUS_FAILED
            workflow_task.message = f"Deletion Failed. Reason: {str(ex.message)}"
            db_session.commit()

        LOGGER.error(workflow_task.message)
        return

    with get_db_session() as db_session:
        workflow_task = db_session.query(WorkflowTask).filter_by(id=workflow_task_id).first()
        if not workflow_task:
            return

        tag: IBMTag = db_session.get(IBMTag, workflow_task.resource_id)
        if not tag:
            workflow_task.status = WorkflowTask.STATUS_FAILED
            workflow_task.message = f"IBMTag '{workflow_task.resource_id}' not found"
            db_session.commit()
            LOGGER.info(workflow_task.message)
            return

        log = IBMResourceLog(
            resource_id=f"{tag.resource_id}-{tag.name}", status=IBMResourceLog.STATUS_DELETED,
            resource_type=IBMTag.__name__, data=tag.to_json())
        log.cloud_id = cloud_id
        db_session.delete(tag)
        db_session.add(log)
        workflow_task.status = WorkflowTask.STATUS_SUCCESSFUL
        db_session.commit()
        LOGGER.info(f"IBM TAG {workflow_task.resource_id} for cloud {cloud_id} deletion successful.")
