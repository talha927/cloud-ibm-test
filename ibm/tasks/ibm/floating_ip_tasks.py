from copy import deepcopy
from ibm_cloud_sdk_core import ApiException

from ibm import get_db_session, LOGGER
from ibm.common.clients.ibm_clients import FloatingIPsClient
from ibm.common.utils import update_id_or_name_references
from ibm.models import IBMFloatingIP, IBMIdleResource, IBMNetworkInterface, IBMPublicGateway, IBMRegion, \
    IBMResourceGroup, IBMResourceLog, IBMResourceTracking, IBMZone, WorkflowTask
from ibm.tasks.celery_app import celery_app as celery
from ibm.tasks.common.tasks_base import IBMWorkflowTasksBase
from ibm.tasks.ibm.task_utils import load_previous_associated_resources
from ibm.web.ibm.floating_ips.schemas import IBMFloatingIPInSchema, IBMFloatingIPResourceSchema
from ibm.web.resource_tracking.utils import create_resource_tracking_object


@celery.task(name="create_floating_ip", base=IBMWorkflowTasksBase)
def create_floating_ip(workflow_task_id):
    """
    Create an IBM Floating Ip on IBM Cloud
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
            cloud_id=cloud_id, resource_json=resource_data, resource_schema=IBMFloatingIPInSchema,
            db_session=db_session, previous_resources=previous_resources
        )

        update_id_or_name_references(
            cloud_id=cloud_id, resource_json=resource_json, resource_schema=IBMFloatingIPResourceSchema,
            db_session=db_session, previous_resources=previous_resources
        )

    try:
        client = FloatingIPsClient(cloud_id=cloud_id, region=region_name)
        resp_json = client.reserve_floating_ip(floating_ip_json=resource_json)
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

        floating_ip_status = resp_json["status"]
        floating_ip_name = resp_json["name"]
        floating_ip_resource_id = resp_json["id"]
        if floating_ip_status in [IBMFloatingIP.STATUS_AVAILABLE, IBMFloatingIP.STATUS_PENDING]:
            metadata = workflow_task.task_metadata.copy() if workflow_task.task_metadata else {}
            metadata["ibm_resource_id"] = floating_ip_resource_id
            workflow_task.task_metadata = metadata

            workflow_task.status = WorkflowTask.STATUS_RUNNING_WAIT
            workflow_task.message = f"IBM Floating IP {floating_ip_name} for cloud {cloud_id} creation waiting"
            LOGGER.note(workflow_task.message)
        else:
            message = f"IBM Floating IP {floating_ip_name} for cloud {cloud_id} creation failed"
            workflow_task.message = message
            LOGGER.fail(message)
            workflow_task.status = WorkflowTask.STATUS_FAILED

        db_session.commit()


@celery.task(name="create_wait_floating_ip", base=IBMWorkflowTasksBase)
def create_wait_floating_ip(workflow_task_id):
    """
    Wait for an IBM Floating IP creation on IBM Cloud
    """
    with get_db_session() as db_session:
        workflow_task = db_session.query(WorkflowTask).filter_by(id=workflow_task_id).first()
        if not workflow_task:
            return

        workflow_task.status = WorkflowTask.STATUS_RUNNING
        db_session.commit()

        resource_data = deepcopy(workflow_task.task_metadata["resource_data"])
        cloud_id = resource_data["ibm_cloud"]["id"]
        region_id = resource_data["region"].get("id")
        zone_dict = resource_data["resource_json"].get("zone")
        if zone_dict:
            zone = db_session.query(IBMZone).filter_by(**zone_dict).first()
            if not zone:
                workflow_task.status = WorkflowTask.STATUS_FAILED
                workflow_task.message = f"IBMRegion '{zone_dict}' not found"
                db_session.commit()
                LOGGER.error(workflow_task.message)
                return
            if zone.ibm_status == IBMZone.IBM_STATUS_UNAVAILABLE:
                workflow_task.status = WorkflowTask.STATUS_FAILED
                workflow_task.message = f"IBMZone '{zone.name}' unavailable"
                db_session.commit()
                LOGGER.error(workflow_task.message)
                return
            region_name = zone.region.name
        elif region_id:
            region = db_session.query(IBMRegion).filter_by(id=region_id, cloud_id=cloud_id).first()
            if not region:
                workflow_task.status = WorkflowTask.STATUS_FAILED
                workflow_task.message = f"IBMRegion '{region_id}' not found"
                db_session.commit()
                LOGGER.error(workflow_task.message)
                return
            region_name = region.name

        resource_id = workflow_task.task_metadata["ibm_resource_id"]
    try:
        client = FloatingIPsClient(cloud_id=cloud_id, region=region_name)
        floating_ip_json = client.get_floating_ip(floating_ip_id=resource_id)
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

        if floating_ip_json["status"] == IBMFloatingIP.STATUS_FAILED:
            workflow_task.status = WorkflowTask.STATUS_FAILED
            workflow_task.message = f"IBM Floating IP '{floating_ip_json['name']}' creation for cloud '{cloud_id}' " \
                                    f"failed on IBM Cloud"
            db_session.commit()
            LOGGER.fail(workflow_task.message)
            return

        elif floating_ip_json["status"] == IBMFloatingIP.STATUS_PENDING:
            workflow_task.status = WorkflowTask.STATUS_RUNNING_WAIT
            db_session.commit()
            LOGGER.info(f"IBM Floating Ip '{floating_ip_json['name']}' creation for cloud '{cloud_id}' waiting")
            return

        with db_session.no_autoflush:
            zone = db_session.query(IBMZone).filter_by(name=floating_ip_json["zone"]["name"], cloud_id=cloud_id).first()

            resource_group = db_session.query(IBMResourceGroup).filter_by(
                resource_id=floating_ip_json["resource_group"]["id"], cloud_id=cloud_id).first()

            if floating_ip_json.get("target"):
                if floating_ip_json["target"]["resource_type"] == IBMNetworkInterface.TYPE_NETWORK_INTERFACE:
                    target = db_session.query(IBMNetworkInterface).filter_by(
                        resource_id=floating_ip_json["target"]["id"], cloud_id=cloud_id).first()
                else:
                    target = db_session.query(IBMPublicGateway).filter_by(
                        resource_id=floating_ip_json["target"]["id"], cloud_id=cloud_id).first()

                if not target:
                    workflow_task.status = WorkflowTask.STATUS_FAILED
                    workflow_task.message = \
                        "Creation Successful but record update failed. The records will update next time " \
                        "discovery runs"
                    db_session.commit()
                    LOGGER.note(workflow_task.message)
                    return

            if not (resource_group and zone):
                workflow_task.status = WorkflowTask.STATUS_FAILED
                workflow_task.message = \
                    "Creation Successful but record update failed. The records will update next time discovery runs"
                db_session.commit()
                LOGGER.note(workflow_task.message)
                return

            floating_ip = IBMFloatingIP.from_ibm_json_body(json_body=floating_ip_json)
            floating_ip.zone = zone
            floating_ip.resource_group = resource_group
            if floating_ip_json.get("target"):
                if floating_ip_json["target"]["resource_type"] == IBMNetworkInterface.TYPE_NETWORK_INTERFACE:
                    floating_ip.network_interface = target
                else:
                    floating_ip_json.public_gateway = target

            db_session.commit()

        workflow_task.status = WorkflowTask.STATUS_SUCCESSFUL
        floating_ip_json = floating_ip.to_json()
        floating_ip_json["created_at"] = str(floating_ip_json["created_at"])

        IBMResourceLog(
            resource_id=floating_ip.resource_id, region=floating_ip.zone.region,
            status=IBMResourceLog.STATUS_ADDED, resource_type=IBMFloatingIP.__name__,
            data=floating_ip_json)

        db_session.commit()

    LOGGER.success(f"IBM Floating IP '{floating_ip_json['name']}' creation for cloud '{cloud_id}' successful")


@celery.task(name="delete_floating_ip", base=IBMWorkflowTasksBase)
def delete_floating_ip(workflow_task_id):
    """
    Delete an IBM Floating Ip on IBM Cloud
    """
    with get_db_session() as db_session:
        workflow_task: WorkflowTask = db_session.query(WorkflowTask).filter_by(id=workflow_task_id).first()
        if not workflow_task:
            return

        workflow_task.status = WorkflowTask.STATUS_RUNNING
        db_session.commit()

        floating_ip: IBMFloatingIP = db_session.query(IBMFloatingIP).filter_by(id=workflow_task.resource_id).first()
        if not floating_ip:
            workflow_task.status = WorkflowTask.STATUS_FAILED
            workflow_task.message = f"IBM Floating Ip '{workflow_task.resource_id}' not found"
            db_session.commit()
            LOGGER.error(workflow_task.message)
            return

        region_name = floating_ip.region.name
        floating_ip_resource_id = floating_ip.resource_id
        cloud_id = floating_ip.cloud_id

    try:
        client = FloatingIPsClient(cloud_id, region=region_name)
        client.release_floating_ip(floating_ip_id=floating_ip_resource_id)
        floating_ip_json = client.get_floating_ip(floating_ip_id=floating_ip_resource_id)

    except ApiException as ex:
        # IBM Floating Ip is deleted from IBM Cloud Console, but we still have it on VPC + side.
        with get_db_session() as db_session:
            workflow_task: WorkflowTask = db_session.query(WorkflowTask).filter_by(id=workflow_task_id).first()
            if not workflow_task:
                return

            if ex.code == 404:  # 404 means resource is not found on IBM Cloud.
                floating_ip: IBMFloatingIP = db_session.query(IBMFloatingIP).filter_by(id=workflow_task.resource_id) \
                    .first()
                if floating_ip:
                    floating_ip_json = floating_ip.to_json()
                    floating_ip_json["created_at"] = str(floating_ip_json["created_at"])

                    IBMResourceLog(
                        resource_id=floating_ip.resource_id, region=floating_ip.zone.region,
                        status=IBMResourceLog.STATUS_DELETED, resource_type=IBMFloatingIP.__name__,
                        data=floating_ip_json)

                    # Adding resource to IBMResourceTracking
                    create_resource_tracking_object(db_resource=floating_ip, action_type=IBMResourceTracking.DELETED,
                                                    session=db_session)

                    db_session.query(IBMIdleResource).filter_by(cloud_id=floating_ip.cloud_id,
                                                                db_resource_id=floating_ip.id).delete()
                    db_session.delete(floating_ip)

                workflow_task.status = WorkflowTask.STATUS_SUCCESSFUL
                LOGGER.success(
                    f"IBM Floating Ip {floating_ip_resource_id} for cloud {cloud_id} deletion successful.")
                db_session.commit()
                return
            else:
                workflow_task.status = WorkflowTask.STATUS_FAILED
                workflow_task.message = f"Deletion Failed: Reason: {str(ex.message)}"
                db_session.commit()
                LOGGER.fail(workflow_task.message)
                return

    with get_db_session() as db_session:
        workflow_task: WorkflowTask = db_session.query(WorkflowTask).filter_by(id=workflow_task_id).first()
        if not workflow_task:
            return

        floating_ip_status = floating_ip_json["status"]
        floating_ip_name = floating_ip_json["name"]
        if floating_ip_status != IBMFloatingIP.STATUS_DELETING:
            message = f"IBM Floating Ip {floating_ip_resource_id} for cloud {cloud_id} deletion failed"
            workflow_task.message = message
            workflow_task.status = WorkflowTask.STATUS_FAILED
            LOGGER.fail(message)
            db_session.commit()
            return

        workflow_task.status = WorkflowTask.STATUS_RUNNING_WAIT
        message = f"IBM Floating Ip {floating_ip_name} for cloud {floating_ip_resource_id} deletion waiting"
        db_session.commit()
        LOGGER.info(message)


@celery.task(name="delete_wait_floating_ip", base=IBMWorkflowTasksBase)
def delete_wait_floating_ip(workflow_task_id):
    """
    Wait task for Deletion of an IBM Floating Ip on IBM Cloud
    """
    with get_db_session() as db_session:
        workflow_task: WorkflowTask = db_session.query(WorkflowTask).filter_by(id=workflow_task_id).first()
        if not workflow_task:
            return

        workflow_task.status = WorkflowTask.STATUS_RUNNING
        db_session.commit()

        floating_ip: IBMFloatingIP = db_session.query(IBMFloatingIP).filter_by(id=workflow_task.resource_id).first()
        if not floating_ip:
            workflow_task.status = WorkflowTask.STATUS_FAILED
            workflow_task.message = f"IBMFloatingIp '{workflow_task.resource_id}' not found"
            db_session.commit()
            LOGGER.error(workflow_task.message)
            return

        region_name = floating_ip.region.name
        floating_ip_resource_id = floating_ip.resource_id
        cloud_id = floating_ip.cloud_id

    try:
        client = FloatingIPsClient(cloud_id, region=region_name)
        floating_ip_json = client.get_floating_ip(floating_ip_id=floating_ip_resource_id)

    except ApiException as ex:
        with get_db_session() as db_session:
            workflow_task: WorkflowTask = db_session.query(WorkflowTask).filter_by(id=workflow_task_id).first()
            if not workflow_task:
                return

            if ex.code == 404:  # 404 means resource is not found on IBM Cloud.
                floating_ip: IBMFloatingIP = db_session.query(IBMFloatingIP).filter_by(
                    id=workflow_task.resource_id).first()

                # Adding resource to IBMResourceTracking
                create_resource_tracking_object(db_resource=floating_ip, action_type=IBMResourceTracking.DELETED,
                                                session=db_session)
                if floating_ip:
                    db_session.delete(floating_ip)

                workflow_task.status = WorkflowTask.STATUS_SUCCESSFUL
                LOGGER.success(
                    f"IBM Floating Ip {floating_ip_resource_id} for cloud {cloud_id} deletion successful.")
                floating_ip_json = floating_ip.to_json()
                floating_ip_json["created_at"] = str(floating_ip_json["created_at"])

                IBMResourceLog(
                    resource_id=floating_ip.resource_id, region=floating_ip.zone.region,
                    status=IBMResourceLog.STATUS_DELETED, resource_type=IBMFloatingIP.__name__,
                    data=floating_ip_json)
                db_session.commit()
                return
            else:
                workflow_task.status = WorkflowTask.STATUS_FAILED
                workflow_task.message = f"Deletion Failed: Reason: {str(ex.message)}"
                db_session.commit()
                LOGGER.fail(workflow_task.message)
                return

    with get_db_session() as db_session:
        workflow_task: WorkflowTask = db_session.query(WorkflowTask).filter_by(id=workflow_task_id).first()
        if not workflow_task:
            return

        floating_ip_status = floating_ip_json["status"]
        floating_ip_name = floating_ip_json["name"]
        if floating_ip_status != IBMFloatingIP.STATUS_DELETING:
            message = f"IBM Floating Ip {floating_ip_resource_id} for cloud {cloud_id} deletion failed"
            workflow_task.message = message
            workflow_task.status = WorkflowTask.STATUS_FAILED
            LOGGER.fail(message)
            db_session.commit()
            return

        workflow_task.status = WorkflowTask.STATUS_RUNNING_WAIT
        message = f"IBM Floating Ip {floating_ip_name} for cloud {floating_ip_resource_id} deletion waiting"
        db_session.commit()
        LOGGER.info(message)
