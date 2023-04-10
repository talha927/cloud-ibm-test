import logging
from copy import deepcopy
from ibm_cloud_sdk_core import ApiException

from ibm import get_db_session
from ibm.common.clients.ibm_clients import SnapshotsClient
from ibm.common.utils import get_resource_by_name_or_id, update_id_or_name_references
from ibm.models import IBMIdleResource, IBMImage, IBMOperatingSystem, IBMRegion, IBMResourceGroup, IBMResourceLog, \
    IBMSnapshot, IBMVolume, WorkflowTask, IBMResourceTracking
from ibm.tasks.celery_app import celery_app as celery
from ibm.tasks.common.tasks_base import IBMWorkflowTasksBase
from ibm.tasks.ibm.task_utils import load_previous_associated_resources
from ibm.web.ibm.snapshots.schemas import IBMSnapshotInSchema, IBMSnapshotResourceSchema
from ibm.web.resource_tracking.utils import create_resource_tracking_object

LOGGER = logging.getLogger(__name__)


@celery.task(name="validate_snapshot", base=IBMWorkflowTasksBase)
def validate_snapshot(workflow_task_id):
    """
    Validate IBM Snapshot on IBM Cloud
    """
    with get_db_session() as db_session:
        workflow_task = db_session.query(WorkflowTask).filter_by(id=workflow_task_id).first()
        if not workflow_task:
            return

        workflow_task.status = WorkflowTask.STATUS_RUNNING
        db_session.commit()

        resource_data = deepcopy(workflow_task.task_metadata["resource_data"])
        name = resource_data["resource_json"]["name"]
        resource_group_json = resource_data["resource_json"]["resource_group"]
        cloud_id = resource_data["ibm_cloud"]["id"]
        region_id = resource_data["region"]["id"]

        snapshot = db_session.query(IBMSnapshot).filter_by(name=name, region_id=region_id, cloud_id=cloud_id).first()
        if snapshot:
            workflow_task.status = WorkflowTask.STATUS_FAILED
            workflow_task.message = f"IBM Snapshot with name {name} already exists in DB."
            db_session.commit()
            LOGGER.info(workflow_task.message)
            return

        resource_group, _ = get_resource_by_name_or_id(
            cloud_id, IBMResourceGroup, db_session, resource_group_json)

        region = db_session.query(IBMRegion).filter_by(id=region_id, cloud_id=cloud_id).first()
        if not region:
            workflow_task.status = WorkflowTask.STATUS_FAILED
            workflow_task.message = f"IBM Region '{region_id}' not found"
            db_session.commit()
            LOGGER.info(workflow_task.message)
            return

        if region.ibm_status == IBMRegion.IBM_STATUS_UNAVAILABLE:
            workflow_task.status = WorkflowTask.STATUS_FAILED
            workflow_task.message = f"IBM Region '{region.name}' unavailable"
            db_session.commit()
            LOGGER.info(workflow_task.message)
            return

        region_name = region.name

    try:
        client = SnapshotsClient(cloud_id=cloud_id, region=region_name)
        snapshots_list = client.list_snapshots(resource_group_id=resource_group.resource_id, name=name)
    except ApiException as ex:
        with get_db_session() as db_session:
            workflow_task = db_session.query(WorkflowTask).filter_by(id=workflow_task_id).first()
            if not workflow_task:
                return

            workflow_task.status = WorkflowTask.STATUS_FAILED
            workflow_task.message = f"Validation Failed. Reason: {str(ex.message)}"
            db_session.commit()

        LOGGER.info(ex.message)
        return

    with get_db_session() as db_session:
        workflow_task = db_session.query(WorkflowTask).filter_by(id=workflow_task_id).first()
        if not workflow_task:
            return

        for snapshot in snapshots_list:
            if snapshot["name"] == name:
                workflow_task.status = WorkflowTask.STATUS_FAILED
                message = f"IBM Snapshot with name {name} already exists on IBM."
                workflow_task.message = message
                db_session.commit()
                LOGGER.info(message)
                return

        workflow_task.status = WorkflowTask.STATUS_SUCCESSFUL
        db_session.commit()

    LOGGER.info(f"IBM Snapshot '{name}' for cloud '{cloud_id}' validated successfully.")


@celery.task(name="create_snapshot", base=IBMWorkflowTasksBase)
def create_snapshot(workflow_task_id):
    """
    Create an IBM Snapshot on IBM Cloud
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
            workflow_task.message = f"IBM Region '{region_id}' not found"
            db_session.commit()
            LOGGER.info(workflow_task.message)
            return

        if region.ibm_status == IBMRegion.IBM_STATUS_UNAVAILABLE:
            workflow_task.status = WorkflowTask.STATUS_FAILED
            workflow_task.message = f"IBM Region '{region.name}' unavailable"
            db_session.commit()
            LOGGER.info(workflow_task.message)
            return

        region_name = region.name

        previous_resources = load_previous_associated_resources(task=workflow_task, session=db_session)
        update_id_or_name_references(
            cloud_id=cloud_id, resource_json=resource_data, resource_schema=IBMSnapshotInSchema,
            db_session=db_session, previous_resources=previous_resources
        )

        update_id_or_name_references(
            cloud_id=cloud_id, resource_json=resource_json, resource_schema=IBMSnapshotResourceSchema,
            db_session=db_session, previous_resources=previous_resources
        )

    try:
        client = SnapshotsClient(cloud_id=cloud_id, region=region_name)
        resp_json = client.create_snapshot(snapshot_json=resource_json)
    except ApiException as ex:
        with get_db_session() as db_session:
            workflow_task = db_session.query(WorkflowTask).filter_by(id=workflow_task_id).first()
            if not workflow_task:
                return

            workflow_task.status = WorkflowTask.STATUS_FAILED
            workflow_task.message = f"Creation Failed. Reason: {str(ex.message)}"
            db_session.commit()

        LOGGER.info("Create Snapshot failed with status code " + str(ex.code) + ": " + ex.message)
        return

    with get_db_session() as db_session:
        workflow_task = db_session.query(WorkflowTask).filter_by(id=workflow_task_id).first()
        if not workflow_task:
            return

        snapshot_life_cycle_state = resp_json["lifecycle_state"]
        snapshot_name = resp_json["name"]
        snapshot_resource_id = resp_json["id"]
        if snapshot_life_cycle_state in [IBMSnapshot.STATE_STABLE, IBMSnapshot.STATE_PENDING,
                                         IBMSnapshot.STATE_WAITING]:
            metadata = deepcopy(workflow_task.task_metadata) if workflow_task.task_metadata else {}
            metadata["ibm_resource_id"] = snapshot_resource_id
            workflow_task.task_metadata = metadata
            workflow_task.status = WorkflowTask.STATUS_RUNNING_WAIT
            message = f"IBM Snapshot {snapshot_name} for cloud {cloud_id} creation waiting"
        else:
            message = f"IBM Snapshot {snapshot_name} for cloud {cloud_id} creation failed"
            workflow_task.message = message
            workflow_task.status = WorkflowTask.STATUS_FAILED

        db_session.commit()

    LOGGER.info(message)


@celery.task(name="create_wait_snapshot", base=IBMWorkflowTasksBase)
def create_wait_snapshot(workflow_task_id):
    """
    Wait for an IBM Snapshot creation on IBM Cloud
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
            workflow_task.message = f"IBM Region '{region_id}' not found"
            db_session.commit()
            LOGGER.info(workflow_task.message)
            return

        if region.ibm_status == IBMRegion.IBM_STATUS_UNAVAILABLE:
            workflow_task.status = WorkflowTask.STATUS_FAILED
            workflow_task.message = f"IBM Region '{region.name}' unavailable"
            db_session.commit()
            LOGGER.info(workflow_task.message)
            return

        region_name = region.name
        resource_id = workflow_task.task_metadata["ibm_resource_id"]

    try:
        client = SnapshotsClient(cloud_id=cloud_id, region=region_name)
        snapshot_json = client.get_snapshot(snapshot_id=resource_id)
    except ApiException as ex:
        with get_db_session() as db_session:
            workflow_task = db_session.query(WorkflowTask).filter_by(id=workflow_task_id).first()
            if not workflow_task:
                return

            workflow_task.status = WorkflowTask.STATUS_FAILED
            workflow_task.message = f"Creation Failed. Reason: {str(ex.message)}"
            db_session.commit()

        LOGGER.info(ex.message)
        return

    with get_db_session() as db_session:
        workflow_task = db_session.query(WorkflowTask).filter_by(id=workflow_task_id).first()
        if not workflow_task:
            return

        if snapshot_json["lifecycle_state"] in [IBMSnapshot.STATE_FAILED]:
            workflow_task.status = WorkflowTask.STATUS_FAILED
            workflow_task.message = f"IBM Snapshot '{snapshot_json['name']}' creation for cloud '{cloud_id}' " \
                                    f"failed on IBM Cloud"
            db_session.commit()
            LOGGER.info(workflow_task.message)
            return

        elif snapshot_json["lifecycle_state"] == IBMSnapshot.STATE_PENDING:
            workflow_task.status = WorkflowTask.STATUS_RUNNING_WAIT
            db_session.commit()
            LOGGER.info(f"IBM Snapshot '{snapshot_json['name']}' creation for cloud '{cloud_id}' waiting")
            return

        with db_session.no_autoflush:
            region = db_session.query(IBMRegion).filter_by(
                name=region_name, cloud_id=cloud_id).first()
            resource_group = db_session.query(IBMResourceGroup).filter_by(
                resource_id=snapshot_json["resource_group"]["id"], cloud_id=cloud_id).first()
            source_volume = db_session.query(IBMVolume).filter_by(
                resource_id=snapshot_json.get("source_volume", {}).get("id"), cloud_id=cloud_id).first()
            image = db_session.query(IBMImage).filter_by(
                resource_id=snapshot_json.get("source_image", {}).get("id"), cloud_id=cloud_id).first()
            operating_system = db_session.query(IBMOperatingSystem).filter_by(
                name=snapshot_json.get("operating_system", {}).get("name"), cloud_id=cloud_id).first()

            if not (resource_group and region):
                workflow_task.status = WorkflowTask.STATUS_FAILED
                workflow_task.message = \
                    "Creation Successful but record update failed. The records will update next time discovery runs"
                db_session.commit()
                LOGGER.info(workflow_task.message)
                return

            snapshot = IBMSnapshot.from_ibm_json_body(json_body=snapshot_json)
            snapshot.region = region
            snapshot.resource_group = resource_group
            snapshot.source_volume = source_volume
            snapshot.source_image = image
            snapshot.operating_system = operating_system
            db_session.commit()

        snapshot_json = snapshot.to_json()
        snapshot_json["created_at"] = str(snapshot_json["created_at"])

        IBMResourceLog(
            resource_id=snapshot.resource_id, region=snapshot.region,
            status=IBMResourceLog.STATUS_ADDED, resource_type=IBMSnapshot.__name__,
            data=snapshot_json)

        workflow_task.status = WorkflowTask.STATUS_SUCCESSFUL
        workflow_task.resource_id = snapshot.id
        db_session.commit()

    LOGGER.info(f"IBM Snapshot '{snapshot_json['name']}' creation for cloud '{cloud_id}' successful")


@celery.task(name="delete_snapshot", base=IBMWorkflowTasksBase)
def delete_snapshot(workflow_task_id):
    """
    Delete an IBM Snapshot on IBM Cloud
    """
    with get_db_session() as db_session:
        workflow_task: WorkflowTask = db_session.query(WorkflowTask).filter_by(id=workflow_task_id).first()
        if not workflow_task:
            return

        workflow_task.status = WorkflowTask.STATUS_RUNNING
        db_session.commit()

        snapshot: IBMSnapshot = db_session.query(IBMSnapshot).filter_by(id=workflow_task.resource_id).first()
        if not snapshot:
            workflow_task.status = WorkflowTask.STATUS_FAILED
            workflow_task.message = f"IBMSnapshot '{workflow_task.resource_id}' not found"
            db_session.commit()
            LOGGER.info(workflow_task.message)
            return

        region_name = snapshot.region.name
        snapshot_resource_id = snapshot.resource_id
        cloud_id = snapshot.cloud_id

    try:
        client = SnapshotsClient(cloud_id, region=region_name)
        client.delete_snapshot(snapshot_id=snapshot_resource_id)
        snapshot_json = client.get_snapshot(snapshot_id=snapshot_resource_id)

    except ApiException as ex:
        # IBM Snapshot is deleted from IBM Cloud Console, but we still have it on VPC + side.
        with get_db_session() as db_session:
            workflow_task: WorkflowTask = db_session.query(WorkflowTask).filter_by(id=workflow_task_id).first()
            if not workflow_task:
                return

            if ex.code == 404:  # 404 means resource is not found on IBM Cloud.
                workflow_task: WorkflowTask = db_session.query(WorkflowTask).get(workflow_task_id)
                if not workflow_task:
                    return

                snapshot: IBMSnapshot = db_session.query(IBMSnapshot).get(workflow_task.resource_id)

                db_session.query(IBMIdleResource).filter_by(cloud_id=snapshot.cloud_id,
                                                            db_resource_id=snapshot.id).delete()
                if snapshot:
                    db_session.delete(snapshot)

                snapshot_json = snapshot.to_json()
                snapshot_json["created_at"] = str(snapshot_json["created_at"])

                IBMResourceLog(
                    resource_id=snapshot.resource_id, region=snapshot.region,
                    status=IBMResourceLog.STATUS_DELETED, resource_type=IBMSnapshot.__name__,
                    data=snapshot.to_json())

                workflow_task.status = WorkflowTask.STATUS_SUCCESSFUL
                LOGGER.info(
                    f"IBM Snapshot {snapshot.name} for cloud {snapshot.cloud_id} deletion "
                    f"successful.")

                db_session.commit()
                return
            else:
                workflow_task.status = WorkflowTask.STATUS_FAILED
                workflow_task.message = f"Deletion Failed. Reason: {str(ex.message)}"
                db_session.commit()
                LOGGER.info(f"IBM Snapshot {snapshot.name} for cloud {snapshot.cloud_id} deletion failed.")
                return

    with get_db_session() as db_session:
        workflow_task: WorkflowTask = db_session.query(WorkflowTask).filter_by(id=workflow_task_id).first()
        if not workflow_task:
            return

        snapshot: IBMSnapshot = db_session.query(IBMSnapshot).filter_by(
            id=workflow_task.resource_id
        ).first()

        snapshot_status = snapshot_json["lifecycle_state"]

        if snapshot_status in [IBMSnapshot.STATE_STABLE, IBMSnapshot.STATE_FAILED]:
            message = f"IBM Snapshot {snapshot.name} for cloud {snapshot.cloud_id} deletion " \
                      f"failed on IBM Cloud"
            workflow_task.status = WorkflowTask.STATUS_FAILED
            workflow_task.message = message
        else:
            message = f"IBM Snapshot {snapshot.name} for cloud {snapshot.cloud_id} deletion waiting"
            workflow_task.status = WorkflowTask.STATUS_RUNNING_WAIT

        db_session.commit()

    LOGGER.info(message)


@celery.task(name="delete_wait_snapshot", base=IBMWorkflowTasksBase)
def delete_wait_snapshot(workflow_task_id):
    """
    Wait task for Deletion of an IBM Snapshot on IBM Cloud
    """
    with get_db_session() as db_session:
        workflow_task: WorkflowTask = db_session.query(WorkflowTask).filter_by(id=workflow_task_id).first()
        if not workflow_task:
            return

        workflow_task.status = WorkflowTask.STATUS_RUNNING
        db_session.commit()

        snapshot: IBMSnapshot = db_session.query(IBMSnapshot).filter_by(id=workflow_task.resource_id).first()
        if not snapshot:
            workflow_task.status = WorkflowTask.STATUS_FAILED
            workflow_task.message = f"IBMSnapshot '{workflow_task.resource_id}' not found"
            db_session.commit()
            LOGGER.info(workflow_task.message)
            return

        region_name = snapshot.region.name
        snapshot_resource_id = snapshot.resource_id
        cloud_id = snapshot.cloud_id

    try:
        client = SnapshotsClient(cloud_id, region=region_name)
        snapshot_json = client.get_snapshot(snapshot_id=snapshot_resource_id)

    except ApiException as ex:
        with get_db_session() as db_session:
            workflow_task: WorkflowTask = db_session.query(WorkflowTask).filter_by(id=workflow_task_id).first()
            if not workflow_task:
                return

            if ex.code == 404:  # 404 means resource is not found on IBM Cloud.
                snapshot: IBMSnapshot = db_session.query(IBMSnapshot).filter_by(
                    id=workflow_task.resource_id).first()
                snapshot_json = snapshot.to_json()
                snapshot_json["created_at"] = str(snapshot_json["created_at"])

                IBMResourceLog(
                    resource_id=snapshot.resource_id, region=snapshot.region,
                    status=IBMResourceLog.STATUS_DELETED, resource_type=IBMSnapshot.__name__,
                    data=snapshot.to_json()
                )
                # Adding resource to IBMResourceTracking
                create_resource_tracking_object(db_resource=snapshot, action_type=IBMResourceTracking.DELETED,
                                                session=db_session)
                db_session.delete(snapshot)

                workflow_task.status = WorkflowTask.STATUS_SUCCESSFUL
                LOGGER.info(
                    f"IBM Snapshot {snapshot_resource_id} for cloud {cloud_id} deletion successful.")

                db_session.commit()
                return
            else:
                workflow_task.status = WorkflowTask.STATUS_FAILED
                workflow_task.message = str(ex.message)
                db_session.commit()
                LOGGER.info(str(ex.message))
                return

    with get_db_session() as db_session:
        workflow_task: WorkflowTask = db_session.query(WorkflowTask).filter_by(id=workflow_task_id).first()
        if not workflow_task:
            return

        if snapshot_json["lifecycle_state"] == IBMSnapshot.STATE_DELETING:
            workflow_task.status = WorkflowTask.STATUS_RUNNING_WAIT
            message = f"IBM Snapshot {snapshot_resource_id} for cloud {cloud_id} deletion waiting"
            workflow_task.message = message
            db_session.commit()
            return

        message = f"IBM Snapshot {snapshot_resource_id} for cloud {cloud_id} deletion failed"
        workflow_task.message = message
        workflow_task.status = WorkflowTask.STATUS_FAILED
        db_session.commit()

    LOGGER.info(message)


@celery.task(name="delete_volume_attached_snapshots", base=IBMWorkflowTasksBase)
def delete_volume_attached_snapshots(workflow_task_id):
    """
    Deletion of IBM Snapshots attached to a volume on IBM Cloud
    """
    with get_db_session() as db_session:
        workflow_task: WorkflowTask = db_session.query(WorkflowTask).filter_by(id=workflow_task_id).first()
        if not workflow_task:
            return

        workflow_task.status = WorkflowTask.STATUS_RUNNING
        db_session.commit()

        volume: IBMVolume = db_session.query(IBMVolume).filter_by(id=workflow_task.resource_id).first()
        if not volume:
            workflow_task.status = WorkflowTask.STATUS_FAILED
            workflow_task.message = f"IBM Volume '{workflow_task.resource_id}' not found"
            db_session.commit()
            LOGGER.info(workflow_task.message)
            return

        region_name = volume.region.name
        volume_resource_id = volume.resource_id
        cloud_id = volume.cloud_id

    try:
        client = SnapshotsClient(cloud_id, region=region_name)
        client.delete_filtered_collection_of_snapshots(source_volume_id=volume_resource_id)

    except ApiException as ex:
        # IBM Volume is deleted from IBM Cloud Console, but we still have it on VPC + side.
        with get_db_session() as db_session:
            workflow_task: WorkflowTask = db_session.query(WorkflowTask).filter_by(id=workflow_task_id).first()
            if not workflow_task:
                return

            volume: IBMVolume = db_session.query(IBMVolume).filter_by(id=workflow_task.resource_id).first()
            if volume:
                db_session.query(IBMSnapshot).filter_by(source_volume_id=volume.id).delete()
                workflow_task.status = WorkflowTask.STATUS_SUCCESSFUL
                LOGGER.info(
                    f"IBM Volume {volume_resource_id} attached snapshots for cloud {cloud_id} deleted successfully.")
                db_session.commit()
                return

            if ex.code == 400:
                db_session.delete(volume)
                workflow_task.message = f"IBM Snapshots attached with volume {volume_resource_id} for " \
                                        f"cloud {cloud_id} deletion failed."
            else:
                workflow_task.message = str(ex.message)
                LOGGER.info(workflow_task.message)
                workflow_task.status = WorkflowTask.STATUS_FAILED
                db_session.commit()
                return

    with get_db_session() as db_session:
        workflow_task: WorkflowTask = db_session.query(WorkflowTask).filter_by(id=workflow_task_id).first()
        if not workflow_task:
            return

        db_session.query(IBMSnapshot).filter_by(source_volume_id=workflow_task.resource_id).delete()
        workflow_task.status = WorkflowTask.STATUS_SUCCESSFUL
        message = f"IBM Volume {volume_resource_id} attached snapshots for cloud {cloud_id} deleted successfully."

    LOGGER.info(message)
