import logging
from copy import deepcopy
from ibm_cloud_sdk_core import ApiException

from ibm import get_db_session
from ibm.common.clients.ibm_clients import InstancesClient
from ibm.common.utils import update_id_or_name_references
from ibm.models import IBMInstance, IBMRegion, IBMResourceLog, IBMVolume, IBMVolumeAttachment, \
    IBMZone, WorkflowTask
from ibm.tasks.celery_app import celery_app as celery
from ibm.tasks.common.tasks_base import IBMWorkflowTasksBase
from ibm.tasks.ibm.task_utils import load_previous_associated_resources
from ibm.web.ibm.instances.volume_attachments.schemas import IBMVolumeAttachmentInSchema, \
    IBMVolumeAttachmentResourceSchema

LOGGER = logging.getLogger(__name__)


@celery.task(name="create_instance_volume_attachment", base=IBMWorkflowTasksBase)
def create_instance_volume_attachment(workflow_task_id):
    """
    Create an IBM Volume Attachment on IBM Cloud Instance
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
        region_id = resource_data["region"]["id"]
        instance_id = resource_data["instance"]["id"]

        region = db_session.query(IBMRegion).filter_by(id=region_id, cloud_id=cloud_id).first()
        if not region:
            workflow_task.status = WorkflowTask.STATUS_FAILED
            workflow_task.message = f"IBMRegion '{region_id}' not found"
            db_session.commit()
            LOGGER.info(workflow_task.message)
            return

        if region.ibm_status == IBMZone.IBM_STATUS_UNAVAILABLE:
            workflow_task.status = WorkflowTask.STATUS_FAILED
            workflow_task.message = f"IBMRegion '{region.name}' unavailable"
            db_session.commit()
            LOGGER.info(workflow_task.message)
            return

        instance = db_session.query(IBMInstance).filter_by(id=instance_id, cloud_id=cloud_id).first()
        if not instance:
            workflow_task.status = WorkflowTask.STATUS_FAILED
            workflow_task.message = f"IBMInstance '{instance_id}' not found"
            db_session.commit()
            LOGGER.info(workflow_task.message)
            return

        region_name = region.name

        if resource_json.get("volume_by_id"):
            volume = db_session.query(IBMVolume).filter_by(
                id=resource_json["volume_by_id"]["id"],
                region_id=region_id
            ).first()
            resource_json.pop("volume_by_id")
            resource_json["volume"] = {"id": volume.resource_id}

        previous_resources = load_previous_associated_resources(task=workflow_task, session=db_session)
        update_id_or_name_references(
            cloud_id=cloud_id, resource_json=resource_data, resource_schema=IBMVolumeAttachmentInSchema,
            db_session=db_session, previous_resources=previous_resources
        )
        update_id_or_name_references(
            cloud_id=cloud_id, resource_json=resource_json, resource_schema=IBMVolumeAttachmentResourceSchema,
            db_session=db_session, previous_resources=previous_resources
        )
        instance_resource_id = instance.resource_id
    try:
        client = InstancesClient(cloud_id=cloud_id, region=region_name)
        LOGGER.info(resource_json)
        resp_json = client.create_instance_volume_attachment(instance_id=instance_resource_id,
                                                             volume_attachment_json=resource_json)
    except ApiException as ex:
        with get_db_session() as db_session:
            workflow_task = db_session.query(WorkflowTask).filter_by(id=workflow_task_id).first()
            if not workflow_task:
                return

            workflow_task.status = WorkflowTask.STATUS_FAILED
            workflow_task.message = f"Creation Failed. Reason: {str(ex.message)}"
            db_session.commit()

        LOGGER.info("Create Instance Volume Attachment failed with status code " + str(ex.code) + ": " + ex.message)
        return

    with get_db_session() as db_session:
        workflow_task = db_session.query(WorkflowTask).filter_by(id=workflow_task_id).first()
        if not workflow_task:
            return

        volume_attachment_status = resp_json["status"]
        volume_attachment_name = resp_json["name"]
        volume_attachment_resource_id = resp_json["id"]
        if volume_attachment_status in [IBMVolumeAttachment.STATUS_ATTACHED, IBMVolumeAttachment.STATUS_ATTACHING]:
            metadata = deepcopy(workflow_task.task_metadata)
            metadata["ibm_resource_id"] = volume_attachment_resource_id
            workflow_task.task_metadata = metadata
            workflow_task.status = WorkflowTask.STATUS_RUNNING_WAIT
            message = f"IBM Volume Attachment {volume_attachment_name} for cloud {cloud_id} creation waiting"
        else:
            message = f"IBM Volume Attachment {volume_attachment_name} for cloud {cloud_id} creation failed"
            workflow_task.message = message
            workflow_task.status = WorkflowTask.STATUS_FAILED
        db_session.commit()
    LOGGER.info(message)


@celery.task(name="create_wait_instance_volume_attachment", base=IBMWorkflowTasksBase)
def create_wait_instance_volume_attachment(workflow_task_id):
    """
    Wait for an IBM Volume Attachment on IBM Cloud Instance to get available
    """
    with get_db_session() as db_session:
        workflow_task = db_session.query(WorkflowTask).filter_by(id=workflow_task_id).first()
        if not workflow_task:
            return

        workflow_task.status = WorkflowTask.STATUS_RUNNING
        db_session.commit()

        resource_data = deepcopy(workflow_task.task_metadata["resource_data"])
        cloud_id = resource_data["ibm_cloud"]["id"]
        region_id = resource_data["region"]["id"]
        instance_id = resource_data["instance"]["id"]

        region = db_session.query(IBMRegion).filter_by(id=region_id, cloud_id=cloud_id).first()
        if not region:
            workflow_task.status = WorkflowTask.STATUS_FAILED
            workflow_task.message = f"IBMRegion '{region_id}' not found"
            db_session.commit()
            LOGGER.info(workflow_task.message)
            return

        if region.ibm_status == IBMZone.IBM_STATUS_UNAVAILABLE:
            workflow_task.status = WorkflowTask.STATUS_FAILED
            workflow_task.message = f"IBMRegion '{region.name}' unavailable"
            db_session.commit()
            LOGGER.info(workflow_task.message)
            return
        instance = db_session.query(IBMInstance).filter_by(id=instance_id, cloud_id=cloud_id).first()
        if not instance:
            workflow_task.status = WorkflowTask.STATUS_FAILED
            workflow_task.message = f"IBMInstance '{instance_id}' not found"
            db_session.commit()
            LOGGER.info(workflow_task.message)
            return
        instance_resource_id = instance.resource_id
        instance_id = instance.id
        region_name = region.name
        resource_id = workflow_task.task_metadata["ibm_resource_id"]
    try:
        client = InstancesClient(cloud_id=cloud_id, region=region_name)
        volume_attachment_json = client.get_instance_volume_attachment(instance_id=instance_resource_id,
                                                                       volume_attachment_id=resource_id)
    except ApiException as ex:
        with get_db_session() as db_session:
            workflow_task = db_session.query(WorkflowTask).filter_by(id=workflow_task_id).first()
            if not workflow_task:
                return

            workflow_task.status = WorkflowTask.STATUS_FAILED
            workflow_task.message = f"Creation Failed. Reason: {str(ex.message)}"
            db_session.commit()

        LOGGER.info("Create Instance Volume Attachment failed with status code " + str(ex.code) + ": " + ex.message)
        return
    with get_db_session() as db_session:
        workflow_task = db_session.query(WorkflowTask).filter_by(id=workflow_task_id).first()
        if not workflow_task:
            return

        if volume_attachment_json["status"] in [IBMVolumeAttachment.STATUS_DETACHING,
                                                IBMVolumeAttachment.STATUS_DELETING]:
            workflow_task.status = WorkflowTask.STATUS_FAILED
            workflow_task.message = f"IBM Volume Attachment '{volume_attachment_json['name']}' creation for cloud '" \
                                    f"{cloud_id}' " \
                                    f"failed on IBM Cloud"
            db_session.commit()
            LOGGER.info(workflow_task.message)
            return
        elif volume_attachment_json["status"] == IBMVolumeAttachment.STATUS_ATTACHING:
            workflow_task.status = WorkflowTask.STATUS_RUNNING_WAIT
            db_session.commit()
            LOGGER.info(
                f"IBM Volume Attachment '{volume_attachment_json['name']}' creation for cloud '{cloud_id}' waiting")
            return
        elif volume_attachment_json["status"] == IBMVolumeAttachment.STATUS_ATTACHED:
            with db_session.no_autoflush:
                instance = db_session.query(IBMInstance).filter_by(id=instance_id, cloud_id=cloud_id).first()
                if not instance:
                    workflow_task.status = WorkflowTask.STATUS_FAILED
                    workflow_task.message = f"IBMInstance '{instance_id}' not found"
                    db_session.commit()
                    LOGGER.info(workflow_task.message)
                    return

                volume_attachment = IBMVolumeAttachment.from_ibm_json_body(volume_attachment_json)
                volume = db_session.query(IBMVolume).filter_by(resource_id=volume_attachment_json["volume"]["id"],
                                                               cloud_id=cloud_id).first()
                if not volume:
                    volume = IBMVolume.from_ibm_json_body(volume_attachment_json["volume"])
                volume_attachment.cloud_id = cloud_id
                volume_attachment.instance_id = instance_id
                volume_attachment.volume = volume
                volume_attachment.zone = volume.zone
                instance.volume_attachments.append(volume_attachment)
                db_session.commit()

            volume_attachment_json = volume_attachment.to_json()
            volume_attachment_json["created_at"] = str(volume_attachment_json["created_at"])

            IBMResourceLog(
                resource_id=volume_attachment.resource_id, region=volume_attachment.zone.region,
                status=IBMResourceLog.STATUS_ADDED, resource_type=IBMVolumeAttachment.__name__,
                data=volume_attachment_json)

            workflow_task.status = WorkflowTask.STATUS_SUCCESSFUL
            workflow_task.resource_id = volume_attachment.id
            db_session.commit()
            LOGGER.info(
                f"IBM Volume Attachment '{volume_attachment_json['name']}' creation for cloud '{cloud_id}' successful")


@celery.task(name="delete_instance_volume_attachment", base=IBMWorkflowTasksBase)
def delete_instance_volume_attachment(workflow_task_id):
    """
    Delete an IBM Volume Attachment
    :param workflow_task_id:
    :return:
    """
    with get_db_session() as db_session:
        workflow_task: WorkflowTask = db_session.query(WorkflowTask).filter_by(id=workflow_task_id).first()
        if not workflow_task:
            return

        workflow_task.status = WorkflowTask.STATUS_RUNNING
        db_session.commit()

        volume_attachment: IBMVolumeAttachment = db_session.query(IBMVolumeAttachment).filter_by(
            id=workflow_task.resource_id).first()
        if not volume_attachment:
            workflow_task.status = WorkflowTask.STATUS_SUCCESSFUL
            LOGGER.info(f"IBM Volume Attachment {workflow_task.resource_id} deletion successful.")
            db_session.commit()
            return

        region_name = volume_attachment.instance.region.name
        instance_resource_id = volume_attachment.instance.resource_id
        volume_attachment_resource_id = volume_attachment.resource_id
        cloud_id = volume_attachment.cloud_id

    try:
        client = InstancesClient(cloud_id, region=region_name)
        client.delete_instance_volume_attachment(instance_id=instance_resource_id,
                                                 volume_attachment_id=volume_attachment_resource_id)
        volume_attachment_json = client.get_instance_volume_attachment(
            instance_id=instance_resource_id,
            volume_attachment_id=volume_attachment_resource_id)
    except ApiException as ex:
        with get_db_session() as db_session:
            workflow_task = db_session.query(WorkflowTask).filter_by(id=workflow_task_id).first()
            if not workflow_task:
                return

            if ex.code == 404:
                volume_attachment = db_session.query(IBMVolumeAttachment).filter_by(
                    id=workflow_task.resource_id).first()
                if volume_attachment:
                    try:
                        if volume_attachment.instnace:
                            instance = volume_attachment.instance
                            instance.volume_attachments.remove(volume_attachment)
                    except (ValueError, AttributeError):
                        pass
                    volume_attachment_json = volume_attachment.to_json()
                    volume_attachment_json["created_at"] = str(volume_attachment_json["created_at"])

                    IBMResourceLog(
                        resource_id=volume_attachment.resource_id, region=volume_attachment.zone.region,
                        status=IBMResourceLog.STATUS_DELETED, resource_type=IBMVolumeAttachment.__name__,
                        data=volume_attachment_json)

                    db_session.delete(volume_attachment)

                workflow_task.status = WorkflowTask.STATUS_SUCCESSFUL
                LOGGER.info(f"IBM Volume Attachment {workflow_task.resource_id} deletion successful.")
                db_session.commit()
                return
            else:
                workflow_task.status = WorkflowTask.STATUS_FAILED
                message = f"IBMVolumeAttachment {workflow_task.resource_id} failed due to reason: {str(ex.message)}"
                workflow_task.message = message
                db_session.commit()
                LOGGER.info(message)
                return

    with get_db_session() as db_session:
        workflow_task: WorkflowTask = db_session.query(WorkflowTask).filter_by(id=workflow_task_id).first()
        if not workflow_task:
            return

        volume_attachment_status = volume_attachment_json["status"]
        if volume_attachment_status in [IBMVolumeAttachment.STATUS_DELETING, IBMVolumeAttachment.STATUS_DETACHING]:
            workflow_task.status = WorkflowTask.STATUS_RUNNING_WAIT
            message = f"IBM Volume Attachment {workflow_task.resource_id} deletion waiting."
        else:
            message = f"IBM Volume Attachment {workflow_task.resource_id} deletion failed."
            workflow_task.message = message
            workflow_task.status = WorkflowTask.STATUS_FAILED

        db_session.commit()
    LOGGER.info(message)


@celery.task(name="delete_wait_instance_volume_attachment", base=IBMWorkflowTasksBase)
def delete_wait_instance_volume_attachment(workflow_task_id):
    """
    Wait for an IBM Volume Attachment deletion on IBM Cloud.
    :param workflow_task_id:
    :return:
    """
    with get_db_session() as db_session:
        workflow_task: WorkflowTask = db_session.query(WorkflowTask).filter_by(id=workflow_task_id).first()
        if not workflow_task:
            return

        workflow_task.status = WorkflowTask.STATUS_RUNNING
        db_session.commit()

        volume_attachment = db_session.query(IBMVolumeAttachment).filter_by(
            id=workflow_task.resource_id).first()
        if not volume_attachment:
            workflow_task.status = WorkflowTask.STATUS_SUCCESSFUL
            db_session.commit()
            LOGGER.info(f"IBM Volume Attachment {workflow_task.resource_id} deletion successful.")
            return

        region_name = volume_attachment.region.name
        instance_resource_id = volume_attachment.instance.resource_id
        volume_attachment_resource_id = volume_attachment.resource_id
        cloud_id = volume_attachment.cloud_id

    try:
        client = InstancesClient(cloud_id, region=region_name)
        volume_attachment_json = client.get_instance_volume_attachment(
            instance_id=instance_resource_id, volume_attachment_id=volume_attachment_resource_id
        )
    except ApiException as ex:
        with get_db_session() as db_session:
            workflow_task = db_session.query(WorkflowTask).filter_by(id=workflow_task_id).first()
            if not workflow_task:
                return

            if ex.code == 404:
                volume_attachment = db_session.query(IBMVolumeAttachment).filter_by(
                    id=workflow_task.resource_id).first()
                if volume_attachment:
                    try:
                        if volume_attachment.instance:
                            instance = volume_attachment.instance
                            instance.volume_attachments.remove(volume_attachment)
                    except (ValueError, AttributeError):
                        pass

                    volume_attachment_json = volume_attachment.to_json()
                    volume_attachment_json["created_at"] = str(volume_attachment_json["created_at"])

                    IBMResourceLog(
                        resource_id=volume_attachment.resource_id, region=volume_attachment.zone.region,
                        status=IBMResourceLog.STATUS_DELETED, resource_type=IBMVolumeAttachment.__name__,
                        data=volume_attachment_json)

                    db_session.delete(volume_attachment)
                workflow_task.status = WorkflowTask.STATUS_SUCCESSFUL
                LOGGER.info(f"IBM Volume Attachment {workflow_task.resource_id} deletion successful.")
                db_session.commit()
                return
            else:
                workflow_task.status = WorkflowTask.STATUS_FAILED
                message = f"IBMVolumeAttachment {workflow_task.resource_id} failed due to reason: {str(ex.message)}"
                workflow_task.message = message
                db_session.commit()
                LOGGER.info(message)
                return

    with get_db_session() as db_session:
        workflow_task: WorkflowTask = db_session.query(WorkflowTask).filter_by(id=workflow_task_id).first()
        if not workflow_task:
            return

        if volume_attachment_json["status"] in [IBMVolumeAttachment.STATUS_DELETING,
                                                IBMVolumeAttachment.STATUS_ATTACHING]:
            workflow_task.status = WorkflowTask.STATUS_RUNNING_WAIT
            message = f"IBM Volume Attachment {workflow_task.resource_id} deletion waiting."
        else:
            message = f"IBM Volume Attachment {workflow_task.resource_id} deletion failed."
            workflow_task.message = message
            workflow_task.status = WorkflowTask.STATUS_FAILED

        db_session.commit()
    LOGGER.info(message)
