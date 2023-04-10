from copy import deepcopy
from ibm_cloud_sdk_core import ApiException

from ibm import get_db_session, LOGGER
from ibm.common.clients.ibm_clients import VolumesClient
from ibm.common.utils import update_id_or_name_references
from ibm.models import IBMIdleResource, IBMResourceGroup, IBMResourceLog, IBMResourceTracking, IBMVolume, \
    IBMVolumeProfile, IBMZone, WorkflowTask, IBMRegion
from ibm.tasks.celery_app import celery_app as celery
from ibm.tasks.common.tasks_base import IBMWorkflowTasksBase
from ibm.tasks.ibm.task_utils import load_previous_associated_resources
from ibm.web.ibm.volumes.schemas import IBMVolumeInSchema, IBMVolumeResourceSchema
from ibm.web.resource_tracking.utils import create_resource_tracking_object


@celery.task(name="create_volume", base=IBMWorkflowTasksBase)
def create_ibm_volume(workflow_task_id):
    """
    Create an IBM Volume Key on IBM Cloud
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

        region = db_session.query(IBMRegion).filter_by(id=region_id, cloud_id=cloud_id).first()
        if not region:
            workflow_task.status = WorkflowTask.STATUS_FAILED
            workflow_task.message = f"IBMRegion '{region_id}' not found"
            db_session.commit()
            LOGGER.error(workflow_task.message)
            return

        if region.ibm_status == IBMRegion.IBM_STATUS_UNAVAILABLE:
            workflow_task.status = WorkflowTask.STATUS_FAILED
            workflow_task.message = f"IBMRegion '{region.name}' unavailable"
            db_session.commit()
            LOGGER.error(workflow_task.message)
            return

        region_name = region.name

        previous_resources = load_previous_associated_resources(task=workflow_task, session=db_session)
        update_id_or_name_references(
            cloud_id=cloud_id, resource_json=resource_data, resource_schema=IBMVolumeInSchema,
            db_session=db_session, previous_resources=previous_resources
        )

        update_id_or_name_references(
            cloud_id=cloud_id, resource_json=resource_json, resource_schema=IBMVolumeResourceSchema,
            db_session=db_session, previous_resources=previous_resources
        )

    try:
        client = VolumesClient(cloud_id=cloud_id, region=region_name)
        resp_json = client.create_volume(volume_json=resource_json)
    except ApiException as ex:
        with get_db_session() as db_session:
            workflow_task = db_session.query(WorkflowTask).filter_by(id=workflow_task_id).first()
            if not workflow_task:
                return

            workflow_task.status = WorkflowTask.STATUS_FAILED
            workflow_task.message = f"Creation Failed. Reason: {str(ex.message)}"
            db_session.commit()
            LOGGER.fail(workflow_task.message)
            return

    with get_db_session() as db_session:
        workflow_task = db_session.query(WorkflowTask).filter_by(id=workflow_task_id).first()
        if not workflow_task:
            return

        volume_status = resp_json["status"]
        volume_name = resp_json["name"]
        volume_resource_id = resp_json["id"]
        if volume_status in [IBMVolume.STATUS_AVAILABLE, IBMVolume.STATUS_PENDING]:
            metadata = workflow_task.task_metadata.copy() if workflow_task.task_metadata else {}
            metadata["ibm_resource_id"] = volume_resource_id
            workflow_task.task_metadata = metadata

            workflow_task.status = WorkflowTask.STATUS_RUNNING_WAIT
            message = f"IBM VPC Network {volume_name} for cloud {cloud_id} creation waiting"
            LOGGER.info(message)
        else:
            workflow_task.message = f"IBM VPC Network {volume_name} for cloud {cloud_id} creation failed"
            workflow_task.status = WorkflowTask.STATUS_FAILED
            LOGGER.fail(workflow_task.message)

        db_session.commit()


@celery.task(name="create_wait_ibm_volume", base=IBMWorkflowTasksBase)
def create_wait_ibm_volume(workflow_task_id):
    """
    Wait for an IBM Volume creation on IBM Cloud
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

        region = db_session.query(IBMRegion).filter_by(id=region_id, cloud_id=cloud_id).first()
        if not region:
            workflow_task.status = WorkflowTask.STATUS_FAILED
            workflow_task.message = f"IBMRegion '{region_id}' not found"
            db_session.commit()
            LOGGER.error(workflow_task.message)
            return

        if region.ibm_status == IBMRegion.IBM_STATUS_UNAVAILABLE:
            workflow_task.status = WorkflowTask.STATUS_FAILED
            workflow_task.message = f"IBMRegion '{region.name}' unavailable"
            db_session.commit()
            LOGGER.error(workflow_task.message)
            return

        region_name = region.name
        resource_id = workflow_task.task_metadata["ibm_resource_id"]

    try:
        client = VolumesClient(cloud_id=cloud_id, region=region_name)
        volume_json = client.get_volume(volume_id=resource_id)
    except ApiException as ex:
        with get_db_session() as db_session:
            workflow_task = db_session.query(WorkflowTask).filter_by(id=workflow_task_id).first()
            if not workflow_task:
                return

            workflow_task.status = WorkflowTask.STATUS_FAILED
            workflow_task.message = f"Creation Failed. Reason: {str(ex.message)}"
            db_session.commit()
            LOGGER.fail(workflow_task.message)
            return

    with get_db_session() as db_session:
        workflow_task = db_session.query(WorkflowTask).filter_by(id=workflow_task_id).first()
        if not workflow_task:
            return

        if volume_json["status"] == IBMVolume.STATUS_FAILED:
            workflow_task.status = WorkflowTask.STATUS_FAILED
            workflow_task.message = f"IBM Volume '{volume_json['name']}' creation for cloud '{cloud_id}' " \
                                    f"failed on IBM Cloud"
            db_session.commit()
            LOGGER.fail(workflow_task.message)
            return

        elif volume_json["status"] == IBMVolume.STATUS_PENDING:
            workflow_task.status = WorkflowTask.STATUS_RUNNING_WAIT
            db_session.commit()
            LOGGER.info(f"IBM Volume '{volume_json['name']}' creation for cloud '{cloud_id}' waiting")
            return

        with db_session.no_autoflush:
            zone = db_session.query(IBMZone).filter_by(name=volume_json["zone"]["name"], cloud_id=cloud_id).first()
            resource_group = db_session.query(IBMResourceGroup).filter_by(
                resource_id=volume_json["resource_group"]["id"], cloud_id=cloud_id).first()
            volume_profile = db_session.query(IBMVolumeProfile).filter_by(name=volume_json["profile"]["name"],
                                                                          cloud_id=cloud_id).first()
            volume = IBMVolume.from_ibm_json_body(json_body=volume_json)
            volume.zone = zone
            volume.resource_group = resource_group
            volume.volume_profile = volume_profile

            volume_json = volume.to_json()
            volume_json["created_at"] = str(volume_json["created_at"])

            IBMResourceLog(
                resource_id=volume.resource_id, region=volume.zone.region,
                status=IBMResourceLog.STATUS_ADDED, resource_type=IBMVolume.__name__,
                data=volume_json)

            db_session.commit()

        workflow_task.status = WorkflowTask.STATUS_SUCCESSFUL
        workflow_task.resource_id = volume.id
        db_session.commit()

    LOGGER.success(f"IBM Volume '{volume_json['name']}' creation for cloud '{cloud_id}' successful")


@celery.task(name="delete_volume", base=IBMWorkflowTasksBase)
def delete_volume(workflow_task_id):
    """
    Delete an IBM Volume
    :param workflow_task_id:
    :return:
    """

    with get_db_session() as db_session:
        workflow_task: WorkflowTask = db_session.query(WorkflowTask).get(workflow_task_id)
        if not workflow_task:
            return

        workflow_task.status = WorkflowTask.STATUS_RUNNING
        db_session.commit()

        volume: IBMVolume = db_session.query(IBMVolume).get(workflow_task.resource_id)
        if not volume:
            workflow_task.status = WorkflowTask.STATUS_FAILED
            workflow_task.message = f"IBMVolume {volume.name} not found."
            db_session.commit()
            LOGGER.error(workflow_task.message)
            return

        region_name = volume.region.name
        volume_resource_id = volume.resource_id
        cloud_id = volume.cloud_id

    try:
        client = VolumesClient(cloud_id, region=region_name)
        client.delete_volume(volume_resource_id)
        volume_json = client.get_volume(volume_resource_id)

    except ApiException as ex:
        with get_db_session() as db_session:
            workflow_task = db_session.query(WorkflowTask).get(workflow_task_id)
            if not workflow_task:
                return

            if ex.code == 404:
                volume = db_session.query(IBMVolume).get(workflow_task.resource_id)
                if volume:
                    volume_json = volume.to_json()
                    volume_json["created_at"] = str(volume_json["created_at"])

                    IBMResourceLog(
                        resource_id=volume.resource_id, region=volume.zone.region,
                        status=IBMResourceLog.STATUS_DELETED, resource_type=IBMVolume.__name__,
                        data=volume_json)

                    db_session.query(IBMIdleResource).filter_by(cloud_id=volume.cloud_id,
                                                                db_resource_id=volume.id).delete()
                    db_session.delete(volume)

                workflow_task.status = WorkflowTask.STATUS_SUCCESSFUL
                LOGGER.success(f"IBM Volume {volume.name} for cloud {volume.cloud_id} deletion successful.")
                db_session.commit()
                return
            else:
                workflow_task.status = WorkflowTask.STATUS_FAILED
                workflow_task.message = f"IBM Volume {volume.name} deletion failed due to {str(ex.message)}"
                db_session.commit()
                LOGGER.fail(workflow_task.message)
                return

    with get_db_session() as db_session:
        workflow_task: WorkflowTask = db_session.query(WorkflowTask).get(workflow_task_id)
        if not workflow_task:
            return

        volume_status = volume_json["status"]
        volume_name = volume_json["name"]
        if volume_status in [IBMVolume.STATUS_PENDING_DELETION, IBMVolume.STATUS_PENDING]:
            workflow_task.status = WorkflowTask.STATUS_RUNNING_WAIT
            LOGGER.info(f"IBM Volume {volume_name} for cloud {volume.cloud_id} deletion waiting")
        else:
            workflow_task.message = f"IBM Volume {volume_name} for cloud {volume.cloud_id} deletion failed"
            workflow_task.status = WorkflowTask.STATUS_FAILED
            LOGGER.fail(workflow_task.message)

        db_session.commit()


@celery.task(name="delete_wait_volume", base=IBMWorkflowTasksBase)
def delete_wait_volume(workflow_task_id):
    """
    Wait for an IBM Volume deletion on IBM Cloud.
    :param workflow_task_id:
    :return:
    """
    with get_db_session() as db_session:
        workflow_task: WorkflowTask = db_session.query(WorkflowTask).get(workflow_task_id)
        if not workflow_task:
            return

        workflow_task.status = WorkflowTask.STATUS_RUNNING
        db_session.commit()

        volume: IBMVolume = db_session.query(IBMVolume).get(workflow_task.resource_id)
        if not volume:
            workflow_task.status = WorkflowTask.STATUS_SUCCESSFUL
            db_session.commit()
            LOGGER.success(f"IBM Volume {workflow_task.resource_id} deletion successful.")
            return

        region_name = volume.region.name
        volume_resource_id = volume.resource_id
        cloud_id = volume.cloud_id

    try:
        client = VolumesClient(cloud_id, region=region_name)
        volume_json = client.get_volume(volume_resource_id)
    except ApiException as ex:
        with get_db_session() as db_session:
            workflow_task = db_session.query(WorkflowTask).get(workflow_task_id)
            if not workflow_task:
                return

            if ex.code == 404:
                volume = db_session.query(IBMVolume).get(workflow_task.resource_id)
                if volume:
                    volume_json = volume.to_json()
                    volume_json["created_at"] = str(volume_json["created_at"])

                    IBMResourceLog(
                        resource_id=volume.resource_id, region=volume.zone.region,
                        status=IBMResourceLog.STATUS_DELETED, resource_type=IBMVolume.__name__,
                        data=volume_json)

                    # Adding resource to IBMResourceTracking
                    create_resource_tracking_object(db_resource=volume, action_type=IBMResourceTracking.DELETED,
                                                    session=db_session)
                    db_session.delete(volume)

                workflow_task.status = WorkflowTask.STATUS_SUCCESSFUL
                LOGGER.success(f"IBM Volume {volume.name} for cloud {volume.cloud_id} deletion successful.")

                volume_json = volume.to_json()
                volume_json["created_at"] = str(volume_json["created_at"])

                IBMResourceLog(
                    resource_id=volume.resource_id, region=volume.zone.region,
                    status=IBMResourceLog.STATUS_DELETED, resource_type=IBMVolume.__name__,
                    data=volume_json)

                db_session.commit()
                return
            else:
                workflow_task.status = WorkflowTask.STATUS_FAILED
                workflow_task.message = f"IBM Volume {volume.name} deletion failed due to {str(ex.message)}"
                db_session.commit()
                LOGGER.fail(workflow_task.message)
                return

    with get_db_session() as db_session:
        workflow_task: WorkflowTask = db_session.query(WorkflowTask).get(workflow_task_id)
        if not workflow_task:
            return

        if volume_json["status"] in [IBMVolume.STATUS_PENDING_DELETION, IBMVolume.STATUS_PENDING]:
            workflow_task.status = WorkflowTask.STATUS_RUNNING_WAIT
            LOGGER.info(f"IBM Volume {volume.name} for cloud {volume.cloud_id} deletion waiting")
        else:
            workflow_task.message = f"IBM Volume {volume.name} for cloud {volume.cloud_id} deletion failed"
            LOGGER.fail(workflow_task.message)
            workflow_task.status = WorkflowTask.STATUS_FAILED

        db_session.commit()
