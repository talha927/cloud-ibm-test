from copy import deepcopy
from ibm_cloud_sdk_core import ApiException

from ibm import get_db_session, LOGGER
from ibm.common.clients.ibm_clients import DedicatedHostsClient
from ibm.common.utils import update_id_or_name_references
from ibm.models import IBMDedicatedHost, IBMDedicatedHostGroup, IBMDedicatedHostProfile, IBMIdleResource, IBMRegion, \
    IBMResourceGroup, IBMResourceLog, IBMResourceTracking, IBMZone, WorkflowTask
from ibm.tasks.celery_app import celery_app as celery
from ibm.tasks.common.tasks_base import IBMWorkflowTasksBase
from ibm.tasks.ibm.task_utils import load_previous_associated_resources
from ibm.web.ibm.dedicated_hosts.schemas import IBMDedicatedHostInSchema, IBMDedicatedHostResourceSchema
from ibm.web.resource_tracking.utils import create_resource_tracking_object


@celery.task(name="create_dedicated_host", base=IBMWorkflowTasksBase)
def create_ibm_dedicated_host(workflow_task_id):
    """
    Create an IBM Dedicated Host Key on IBM Cloud
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
        dh_profile_id = resource_json["profile"]["id"]

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
            cloud_id=cloud_id, resource_json=resource_data, resource_schema=IBMDedicatedHostInSchema,
            db_session=db_session, previous_resources=previous_resources
        )
        update_id_or_name_references(
            cloud_id=cloud_id, resource_json=resource_json, resource_schema=IBMDedicatedHostResourceSchema,
            db_session=db_session, previous_resources=previous_resources
        )

    try:
        client = DedicatedHostsClient(cloud_id=cloud_id, region=region_name)
        resp_json = client.create_dedicated_host(dedicated_host_json=resource_json)
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

        with db_session.no_autoflush:
            zone = db_session.query(IBMZone).filter_by(name=resp_json["zone"]["name"], cloud_id=cloud_id).first()
            resource_group = \
                db_session.query(IBMResourceGroup).filter_by(
                    resource_id=resp_json["resource_group"]["id"], cloud_id=cloud_id
                ).first()
            dedicated_host_profile = db_session.query(IBMDedicatedHostProfile).filter_by(id=dh_profile_id,
                                                                                         cloud_id=cloud_id).first()
            if not (zone and resource_group and dedicated_host_profile):
                workflow_task.status = WorkflowTask.STATUS_FAILED
                workflow_task.message = \
                    "Creation Successful but record update failed. The records will update next time discovery runs"
                db_session.commit()
                LOGGER.note(workflow_task.message)
                return

            dedicated_host = IBMDedicatedHost.from_ibm_json_body(json_body=resp_json)
            dedicated_host.zone = zone
            dedicated_host.resource_group = resource_group
            dedicated_host.dedicated_host_profile = dedicated_host_profile
            if resp_json.get("group").get("id"):
                dedicated_host_group = db_session.query(IBMDedicatedHostGroup).filter_by(
                    resource_id=resp_json["group"]["id"], cloud_id=cloud_id).first()
            if dedicated_host_group:
                dedicated_host.dedicated_host_group = dedicated_host_group

            db_session.commit()

            dedicated_host_json = dedicated_host.to_json()
            dedicated_host_json["created_at"] = str(dedicated_host_json["created_at"])

            IBMResourceLog(
                resource_id=dedicated_host.resource_id, region=zone.region,
                status=IBMResourceLog.STATUS_ADDED, resource_type=IBMDedicatedHost.__name__,
                data=dedicated_host_json)

            workflow_task.status = WorkflowTask.STATUS_SUCCESSFUL
            db_session.commit()
            LOGGER.success(f"IBM Dedicated Host '{resp_json['name']}' creation for cloud '{cloud_id}' successful")


@celery.task(name="delete_dedicated_host", base=IBMWorkflowTasksBase)
def delete_dedicated_host(workflow_task_id):
    """
    Delete an IBM Dedicated Host
    :param workflow_task_id:
    :return:
    """
    with get_db_session() as db_session:
        workflow_task: WorkflowTask = db_session.query(WorkflowTask).get(workflow_task_id)
        if not workflow_task:
            return

        workflow_task.status = WorkflowTask.STATUS_RUNNING
        db_session.commit()

        dedicated_host: IBMDedicatedHost = db_session.query(IBMDedicatedHost).get(workflow_task.resource_id)
        if not dedicated_host:
            workflow_task.status = WorkflowTask.STATUS_FAILED
            workflow_task.message = f"IBMDedicatedHost '{workflow_task.resource_id}' not found"
            db_session.commit()
            LOGGER.error(workflow_task.message)
            return

        region_name = dedicated_host.region.name
        dedicated_host_id = dedicated_host.resource_id
        cloud_id = dedicated_host.cloud_id
    try:
        dedicated_host_client = DedicatedHostsClient(cloud_id, region=region_name)
        dedicated_host_client.delete_dedicated_host(dedicated_host_id)
        dedicated_host_json = dedicated_host_client.get_dedicated_host(dedicated_host_id)

    except ApiException as ex:
        # IBM Dedicated Host is deleted from IBM Cloud Console, but we still have it on VPC + side.
        with get_db_session() as db_session:
            if ex.code == 404:  # 404 means resource is not found on IBM Cloud.
                workflow_task: WorkflowTask = db_session.query(WorkflowTask).get(workflow_task_id)
                if not workflow_task:
                    return

                dedicated_host: IBMDedicatedHost = db_session.query(IBMDedicatedHost).get(workflow_task.resource_id)

                db_session.query(IBMIdleResource).filter_by(cloud_id=dedicated_host.cloud_id,
                                                            db_resource_id=dedicated_host.id).delete()
                if dedicated_host:
                    db_session.delete(dedicated_host)

                dedicated_host_json = dedicated_host.to_json()
                dedicated_host_json["created_at"] = str(dedicated_host_json["created_at"])

                IBMResourceLog(
                    resource_id=dedicated_host.resource_id, region=dedicated_host.zone.region,
                    status=IBMResourceLog.STATUS_DELETED, resource_type=IBMDedicatedHost.__name__,
                    data=dedicated_host.to_json())

                workflow_task.status = WorkflowTask.STATUS_SUCCESSFUL
                LOGGER.success(
                    f"IBM Dedicated Host {dedicated_host.name} for cloud {dedicated_host.cloud_id} deletion "
                    f"successful.")

                IBMResourceLog(
                    resource_id=dedicated_host.resource_id, region=dedicated_host.zone.region,
                    status=IBMResourceLog.STATUS_ADDED, resource_type=IBMDedicatedHostGroup.__name__,
                    data=dedicated_host.to_json())

                db_session.commit()
                return

            workflow_task.status = WorkflowTask.STATUS_FAILED
            workflow_task.message = f"Deletion Failed. Reason: {str(ex.message)}"
            db_session.commit()
            LOGGER.fail(
                f"IBM Dedicated Host {dedicated_host.name} for cloud {dedicated_host.cloud_id} deletion failed.")
            return

    with get_db_session() as db_session:
        workflow_task: WorkflowTask = db_session.query(WorkflowTask).get(workflow_task_id)
        if not workflow_task:
            return

        dedicated_host: IBMDedicatedHost = db_session.query(IBMDedicatedHost).filter_by(
            id=workflow_task.resource_id
        ).first()

        dedicated_host_status = dedicated_host_json["lifecycle_state"]

        if dedicated_host_status in [IBMDedicatedHost.LIFECYCLE_STATE_STABLE, IBMDedicatedHost.LIFECYCLE_STATE_FAILED]:
            message = f"IBM Dedicated Host {dedicated_host.name} for cloud {dedicated_host.cloud_id} deletion " \
                      f"failed on IBM Cloud"
            workflow_task.status = WorkflowTask.STATUS_FAILED
            workflow_task.message = message
            LOGGER.fail(workflow_task.message)
        else:
            message = f"IBM Dedicated Host {dedicated_host.name} for cloud {dedicated_host.cloud_id} deletion waiting"
            LOGGER.info(message)
            workflow_task.status = WorkflowTask.STATUS_RUNNING_WAIT

        db_session.commit()


@celery.task(name="delete_wait_dedicated_host", base=IBMWorkflowTasksBase)
def delete_wait_dedicated_host(workflow_task_id):
    """
    Wait for an IBM Dedicated Host deletion on IBM Cloud.
    :param workflow_task_id:
    :return:
    """
    with get_db_session() as db_session:
        workflow_task: WorkflowTask = db_session.query(WorkflowTask).get(workflow_task_id)
        if not workflow_task:
            return

        workflow_task.status = WorkflowTask.STATUS_RUNNING
        db_session.commit()

        dedicated_host: IBMDedicatedHost = db_session.query(IBMDedicatedHost).get(workflow_task.resource_id)
        if not dedicated_host:
            workflow_task.status = WorkflowTask.STATUS_FAILED
            workflow_task.message = f"IBMDedicatedHost '{workflow_task.resource_id}' not found"
            db_session.commit()
            LOGGER.error(workflow_task.message)
            return

        region_name = dedicated_host.region.name
        dedicated_host_id = dedicated_host.resource_id
        cloud_id = dedicated_host.cloud_id
    try:
        dedicated_host_client = DedicatedHostsClient(cloud_id, region=region_name)
        resp_json = dedicated_host_client.get_dedicated_host(dedicated_host_id)

    except ApiException as ex:
        with get_db_session() as db_session:
            if ex.code == 404:  # 404 means resource is not found on IBM Cloud.
                workflow_task: WorkflowTask = db_session.query(WorkflowTask).get(workflow_task_id)
                if not workflow_task:
                    return

                dedicated_host: IBMDedicatedHost = db_session.query(IBMDedicatedHost).get(workflow_task.resource_id)
                if dedicated_host:
                    dedicated_host_json = dedicated_host.to_json()
                    dedicated_host_json["created_at"] = str(dedicated_host_json["created_at"])

                    IBMResourceLog(
                        resource_id=dedicated_host.resource_id, region=dedicated_host.zone.region,
                        status=IBMResourceLog.STATUS_DELETED, resource_type=IBMDedicatedHost.__name__,
                        data=dedicated_host.to_json())

                    # Adding resource to IBMResourceTracking
                    create_resource_tracking_object(db_resource=dedicated_host, action_type=IBMResourceTracking.DELETED,
                                                    session=db_session)

                    db_session.delete(dedicated_host)

                workflow_task.status = WorkflowTask.STATUS_SUCCESSFUL
                db_session.commit()
                LOGGER.success(
                    f"IBM Dedicated Host {dedicated_host.name} for cloud {dedicated_host.cloud_id} deletion "
                    f"successful.")
                return

            workflow_task.status = WorkflowTask.STATUS_FAILED
            workflow_task.message = f"Deletion Failed. Reason: {str(ex.message)}"
            db_session.commit()
            LOGGER.fail(workflow_task.message)
            return

    dedicated_host_status = resp_json["lifecycle_state"]
    with get_db_session() as db_session:
        workflow_task: WorkflowTask = db_session.query(WorkflowTask).get(workflow_task_id)
        if not workflow_task:
            return

        if dedicated_host_status in [IBMDedicatedHost.LIFECYCLE_STATE_STABLE, IBMDedicatedHost.LIFECYCLE_STATE_FAILED]:
            message = f"IBM Dedicated Host {dedicated_host.name} for cloud {dedicated_host.cloud_id} deletion " \
                      f"failed on IBM Cloud"
            workflow_task.status = WorkflowTask.STATUS_FAILED
            workflow_task.message = message
            LOGGER.fail(message)
        else:
            message = f"IBM Dedicated Host {dedicated_host.name} for cloud {dedicated_host.cloud_id} deletion waiting"
            workflow_task.status = WorkflowTask.STATUS_RUNNING_WAIT
            LOGGER.info(message)

        db_session.commit()
