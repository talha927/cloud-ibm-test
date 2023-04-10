import logging
from copy import deepcopy
from ibm_cloud_sdk_core import ApiException

from ibm import get_db_session
from ibm.common.clients.ibm_clients import PlacementGroupsClient
from ibm.common.utils import is_valid_uuid, update_id_or_name_references
from ibm.models import IBMPlacementGroup, IBMRegion, IBMResourceGroup, IBMResourceLog, WorkflowTask
from ibm.tasks.celery_app import celery_app as celery
from ibm.tasks.common.tasks_base import IBMWorkflowTasksBase
from ibm.tasks.ibm.task_utils import load_previous_associated_resources
from ibm.web.ibm.placement_groups.schemas import IBMPlacementGroupResourceSchema

LOGGER = logging.getLogger(__name__)


@celery.task(name="create_placement_group", base=IBMWorkflowTasksBase)
def create_placement_group(workflow_task_id):
    """
    Create an IBM Placement Group on IBM Cloud
    :param workflow_task_id:
    :return:
    """
    with get_db_session() as db_session:
        workflow_task: WorkflowTask = db_session.query(WorkflowTask).get(workflow_task_id)
        if not workflow_task:
            return

        workflow_task.status = WorkflowTask.STATUS_RUNNING
        db_session.commit()

        resource_data = deepcopy(workflow_task.task_metadata["resource_data"])
        resource_json = deepcopy(resource_data["resource_json"])
        cloud_id = resource_data["ibm_cloud"]["id"]
        region_id = resource_data["region"]["id"]
        placement_group_name = resource_json["name"]

        region: IBMRegion = db_session.query(IBMRegion).get(region_id)
        if not region:
            workflow_task.status = WorkflowTask.STATUS_FAILED
            workflow_task.message = f"IBMRegion '{region_id}' not found."
            db_session.commit()
            LOGGER.info(workflow_task.message)
            return

        if region.ibm_status == IBMRegion.IBM_STATUS_UNAVAILABLE:
            workflow_task.status = WorkflowTask.STATUS_FAILED
            workflow_task.message = f"IBMRegion '{region.name}' unavailable."
            db_session.commit()

        previous_resources = load_previous_associated_resources(task=workflow_task, session=db_session)
        update_id_or_name_references(
            cloud_id=cloud_id, resource_json=resource_json, resource_schema=IBMPlacementGroupResourceSchema,
            db_session=db_session, previous_resources=previous_resources
        )
        region_name = region.name

    try:
        client = PlacementGroupsClient(cloud_id, region=region_name)
        placement_group_json = client.create_placement_group(placement_group_json=resource_json)

    except ApiException as ex:
        with get_db_session() as db_session:
            workflow_task: WorkflowTask = db_session.query(WorkflowTask).get(workflow_task_id)
            if not workflow_task:
                return

            workflow_task.status = WorkflowTask.STATUS_FAILED
            workflow_task.message = f"IBMPlacementGroup Creation with name `{placement_group_name}`" \
                                    f" Failed. Reason: {str(ex.message)}"
            db_session.commit()
        LOGGER.info(workflow_task.message)
        return

    with get_db_session() as db_session:
        workflow_task: WorkflowTask = db_session.query(WorkflowTask).get(workflow_task_id)
        if not workflow_task:
            return

        if placement_group_json["lifecycle_state"] in [IBMPlacementGroup.LIFECYCLE_STATE_STABLE,
                                                       IBMPlacementGroup.LIFECYCLE_STATE_WAITING,
                                                       IBMPlacementGroup.LIFECYCLE_STATE_PENDING,
                                                       IBMPlacementGroup.LIFECYCLE_STATE_SUSPENDED,
                                                       IBMPlacementGroup.LIFECYCLE_STATE_UPDATING]:
            metadata = deepcopy(workflow_task.task_metadata) if workflow_task.task_metadata else {}
            metadata["ibm_resource_id"] = placement_group_json["id"]
            workflow_task.task_metadata = metadata

            workflow_task.status = WorkflowTask.STATUS_RUNNING_WAIT
            message = f"IBM Placement Group {placement_group_name} for cloud {cloud_id} creation waiting."
        else:
            message = f"IBM Placement Group {placement_group_name} for cloud {cloud_id} creation failed."
            workflow_task.message = message
            workflow_task.status = WorkflowTask.STATUS_FAILED

        db_session.commit()
    LOGGER.info(message)


@celery.task(name="create_wait_placement_group", base=IBMWorkflowTasksBase)
def create_wait_placement_group(workflow_task_id):
    """
    Wait for an IBM Placement Group creation on IBM Cloud.
    :param workflow_task_id:
    :return:
    """
    with get_db_session() as db_session:
        workflow_task: WorkflowTask = db_session.query(WorkflowTask).get(workflow_task_id)
        if not workflow_task:
            return

        workflow_task.status = WorkflowTask.STATUS_RUNNING
        db_session.commit()

        resource_data = workflow_task.task_metadata["resource_data"]
        cloud_id = resource_data["ibm_cloud"]["id"]
        region_id = resource_data["region"]["id"]

        region: IBMRegion = db_session.query(IBMRegion).get(region_id)
        if not region:
            workflow_task.status = WorkflowTask.STATUS_FAILED
            workflow_task.message = f"IBMRegion `{region_id}` not found."
            db_session.commit()
            LOGGER.info(workflow_task.message)
            return

        if region.ibm_status == IBMRegion.IBM_STATUS_UNAVAILABLE:
            workflow_task.status = WorkflowTask.STATUS_FAILED
            workflow_task.message = f"IBMRegion `{region.name}` unavailable."
            db_session.commit()
            LOGGER.info(workflow_task.message)
            return

        region_name = region.name
        placement_group_resource_id = workflow_task.task_metadata["ibm_resource_id"]

    try:
        client = PlacementGroupsClient(cloud_id, region=region_name)
        placement_group_json = client.get_placement_group(placement_group_resource_id)
    except ApiException as ex:
        with get_db_session() as db_session:
            workflow_task: WorkflowTask = db_session.query(WorkflowTask).get(workflow_task_id)
            if not workflow_task:
                return

            workflow_task.status = WorkflowTask.STATUS_FAILED
            workflow_task.message = f"IBMPlacementGroup Creation Failed. Reason: {str(ex.message)}"
            db_session.commit()
        LOGGER.info("Create Wait Placement Group failed with status code " + str(ex.code) + ": " + ex.message)
        return

    with get_db_session() as db_session:
        workflow_task: WorkflowTask = db_session.query(WorkflowTask).get(workflow_task_id)
        if not workflow_task:
            return

        placement_group_name = placement_group_json["name"]
        if placement_group_json["lifecycle_state"] == IBMPlacementGroup.LIFECYCLE_STATE_STABLE:
            with db_session.no_autoflush:
                region = db_session.query(IBMRegion).filter_by(id=region_id, cloud_id=cloud_id).first()
                resource_group = \
                    db_session.query(IBMResourceGroup).filter_by(
                        resource_id=placement_group_json["resource_group"]["id"], cloud_id=cloud_id
                    ).first()
                if not (resource_group and region):
                    workflow_task.status = WorkflowTask.STATUS_FAILED
                    workflow_task.message = \
                        "Creation Successful but record update failed. The records will update next time " \
                        "discovery runs "
                    db_session.commit()
                    return

                placement_group = IBMPlacementGroup.from_ibm_json_body(placement_group_json)
                if "id" in resource_data and is_valid_uuid(resource_data["id"]):
                    placement_group.id = resource_data["id"]
                placement_group.region = region
                placement_group.resource_group = resource_group
                db_session.commit()

            workflow_task.status = WorkflowTask.STATUS_SUCCESSFUL

            placement_group_json = placement_group.to_json()
            placement_group_json["created_at"] = str(placement_group_json["created_at"])

            IBMResourceLog(
                resource_id=placement_group.resource_id, region=placement_group.region,
                status=IBMResourceLog.STATUS_ADDED, resource_type=IBMPlacementGroup.__name__,
                data=placement_group_json)

            workflow_task.resource_id = placement_group.id
            message = f"IBM Placement Group `{placement_group_name}` for cloud `{cloud_id}` creation successful."
        elif placement_group_json["lifecycle_state"] in [IBMPlacementGroup.LIFECYCLE_STATE_WAITING,
                                                         IBMPlacementGroup.LIFECYCLE_STATE_PENDING,
                                                         IBMPlacementGroup.LIFECYCLE_STATE_SUSPENDED,
                                                         IBMPlacementGroup.LIFECYCLE_STATE_UPDATING]:
            workflow_task.status = WorkflowTask.STATUS_RUNNING_WAIT
            message = f"IBM Placement Group `{placement_group_name}` for cloud `{cloud_id}` creation waiting."
        else:
            message = f"IBM Placement Group `{placement_group_name}` for cloud `{cloud_id}` creation failed."
            workflow_task.message = message
            workflow_task.status = WorkflowTask.STATUS_FAILED

        db_session.commit()
    LOGGER.info(message)


@celery.task(name="delete_placement_group", base=IBMWorkflowTasksBase)
def delete_placement_group(workflow_task_id):
    """
    Delete an IBM Placement Group on IBM Cloud.
    :param workflow_task_id:
    :return:
    """
    with get_db_session() as db_session:
        workflow_task: WorkflowTask = db_session.query(WorkflowTask).get(workflow_task_id)
        if not workflow_task:
            return

        workflow_task.status = WorkflowTask.STATUS_RUNNING
        db_session.commit()

        placement_group: IBMPlacementGroup = db_session.query(IBMPlacementGroup).get(workflow_task.resource_id)
        if not placement_group:
            workflow_task.status = WorkflowTask.STATUS_FAILED
            workflow_task.message = f"IBMPlacementGroup {workflow_task.resource_id} not found."
            db_session.commit()
            LOGGER.info(workflow_task.message)
            return

        placement_group_resource_id = placement_group.resource_id
        region_name = placement_group.region.name
        cloud_id = placement_group.cloud_id

    try:
        client = PlacementGroupsClient(cloud_id, region=region_name)
        client.delete_placement_group(placement_group_resource_id)
        placement_group_json = client.get_placement_group(placement_group_resource_id)
    except ApiException as ex:
        with get_db_session() as db_session:
            workflow_task: WorkflowTask = db_session.query(WorkflowTask).get(workflow_task_id)
            if not workflow_task:
                return

            if ex.code == 404:
                placement_group: IBMPlacementGroup = db_session.query(IBMPlacementGroup).get(workflow_task.resource_id)
                if placement_group:
                    placement_group_json = placement_group.to_json()
                    placement_group_json["created_at"] = str(placement_group_json["created_at"])
                    IBMResourceLog(
                        resource_id=placement_group.resource_id, region=placement_group.region,
                        status=IBMResourceLog.STATUS_DELETED, resource_type=IBMPlacementGroup.__name__,
                        data=placement_group_json)

                    db_session.delete(placement_group)

                workflow_task.status = WorkflowTask.STATUS_SUCCESSFUL
                LOGGER.info(
                    f"IBMPlacementGroup {placement_group.name} for cloud {placement_group.cloud_id} "
                    f"deletion successful.")
                db_session.commit()
                return
            else:
                workflow_task.status = WorkflowTask.STATUS_FAILED
                message = f"IBMPlacementGroup {placement_group.name} deletion failed due to {str(ex.message)}"
                workflow_task.message = message
                db_session.commit()
                LOGGER.info(message)
                return

    with get_db_session() as db_session:
        workflow_task: WorkflowTask = db_session.query(WorkflowTask).get(workflow_task_id)
        if not workflow_task:
            return

        placement_group_name = placement_group_json["name"]
        if placement_group_json["lifecycle_state"] in [IBMPlacementGroup.LIFECYCLE_STATE_STABLE,
                                                       IBMPlacementGroup.LIFECYCLE_STATE_DELETING,
                                                       IBMPlacementGroup.LIFECYCLE_STATE_WAITING,
                                                       IBMPlacementGroup.LIFECYCLE_STATE_PENDING,
                                                       IBMPlacementGroup.LIFECYCLE_STATE_SUSPENDED,
                                                       IBMPlacementGroup.LIFECYCLE_STATE_UPDATING]:
            workflow_task.status = WorkflowTask.STATUS_RUNNING_WAIT
            message = f"IBMPlacementGroup `{placement_group_name}` for cloud `{placement_group.cloud_id}` " \
                      f"deletion waiting."
        else:
            message = f"IBMPlacementGroup `{placement_group_name}` for cloud `{placement_group.cloud_id}` " \
                      f"deletion failed."
            workflow_task.message = message
            workflow_task.status = WorkflowTask.STATUS_FAILED

        db_session.commit()
    LOGGER.info(message)


@celery.task(name="delete_wait_placement_group", base=IBMWorkflowTasksBase)
def delete_wait_placement_group(workflow_task_id):
    """
    Wait for an IBM Placement Group deletion on IBM Cloud.
    :param workflow_task_id:
    :return:
    """
    with get_db_session() as db_session:
        workflow_task: WorkflowTask = db_session.query(WorkflowTask).get(workflow_task_id)
        if not workflow_task:
            return

        workflow_task.status = WorkflowTask.STATUS_RUNNING
        db_session.commit()

        placement_group: IBMPlacementGroup = db_session.query(IBMPlacementGroup).get(workflow_task.resource_id)
        if not placement_group:
            workflow_task.status = WorkflowTask.STATUS_SUCCESSFUL
            db_session.commit()
            LOGGER.info(f"IBMPlacementGroup {workflow_task.resource_id} deletion successful.")
            return

        placement_group_resource_id = placement_group.resource_id
        region_name = placement_group.region.name
        cloud_id = placement_group.cloud_id

    try:
        client = PlacementGroupsClient(cloud_id, region=region_name)
        placement_group_json = client.get_placement_group(placement_group_resource_id)
    except ApiException as ex:
        with get_db_session() as db_session:
            workflow_task: WorkflowTask = db_session.query(WorkflowTask).get(workflow_task_id)
            if not workflow_task:
                return

            if ex.code == 404:
                placement_group: IBMPlacementGroup = db_session.query(IBMPlacementGroup).get(workflow_task.resource_id)
                if placement_group:
                    placement_group_json = placement_group.to_json()
                    placement_group_json["created_at"] = str(placement_group_json["created_at"])
                    IBMResourceLog(
                        resource_id=placement_group.resource_id, region=placement_group.region,
                        status=IBMResourceLog.STATUS_DELETED, resource_type=IBMPlacementGroup.__name__,
                        data=placement_group_json)

                    db_session.delete(placement_group)

                workflow_task.status = WorkflowTask.STATUS_SUCCESSFUL
                LOGGER.info(
                    f"IBMPlacementGroup {placement_group.name} for cloud {placement_group.cloud_id} "
                    f"deletion successful.")
                db_session.commit()
                return
            else:
                workflow_task.status = WorkflowTask.STATUS_FAILED
                message = f"IBMPlacementGroup {placement_group.name} deletion failed due to {str(ex.message)}"
                workflow_task.message = message
                db_session.commit()
                LOGGER.info(message)
                return

    with get_db_session() as db_session:
        workflow_task: WorkflowTask = db_session.query(WorkflowTask).get(workflow_task_id)
        if not workflow_task:
            return

        placement_group_name = placement_group_json["name"]
        if placement_group_json["lifecycle_state"] in [IBMPlacementGroup.LIFECYCLE_STATE_STABLE,
                                                       IBMPlacementGroup.LIFECYCLE_STATE_DELETING,
                                                       IBMPlacementGroup.LIFECYCLE_STATE_WAITING,
                                                       IBMPlacementGroup.LIFECYCLE_STATE_PENDING,
                                                       IBMPlacementGroup.LIFECYCLE_STATE_SUSPENDED,
                                                       IBMPlacementGroup.LIFECYCLE_STATE_UPDATING]:
            workflow_task.status = WorkflowTask.STATUS_RUNNING_WAIT
            message = f"IBMPlacementGroup `{placement_group_name}` for cloud `{placement_group.cloud_id}` " \
                      f"deletion waiting."
        else:
            message = f"IBMPlacementGroup `{placement_group_name}` for cloud `{placement_group.cloud_id}` " \
                      f"deletion failed."
            workflow_task.message = message
            workflow_task.status = WorkflowTask.STATUS_FAILED

        db_session.commit()
    LOGGER.info(message)
