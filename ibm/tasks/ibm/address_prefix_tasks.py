from copy import deepcopy
from ibm_cloud_sdk_core import ApiException

from ibm import get_db_session, LOGGER
from ibm.common.clients.ibm_clients import VPCsClient
from ibm.common.utils import update_id_or_name_references
from ibm.models import IBMAddressPrefix, IBMRegion, IBMVpcNetwork, IBMZone, WorkflowTask
from ibm.models.ibm.resource_log_models import IBMResourceLog
from ibm.tasks.celery_app import celery_app as celery
from ibm.tasks.common.tasks_base import IBMWorkflowTasksBase
from ibm.tasks.ibm.task_utils import load_previous_associated_resources
from ibm.web.ibm.address_prefixes.schemas import IBMAddressPrefixInSchema, IBMAddressPrefixResourceSchema


@celery.task(name="create_address_prefix", base=IBMWorkflowTasksBase)
def create_address_prefix(workflow_task_id):
    """
    Create an IBM Address Prefix on IBM Cloud
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
            cloud_id=cloud_id, resource_json=resource_data, resource_schema=IBMAddressPrefixInSchema,
            db_session=db_session, previous_resources=previous_resources
        )

        update_id_or_name_references(
            cloud_id=cloud_id, resource_json=resource_json, resource_schema=IBMAddressPrefixResourceSchema,
            db_session=db_session, previous_resources=previous_resources
        )

        vpc_resource_id = resource_data["vpc"]["id"]

    try:
        client = VPCsClient(cloud_id=cloud_id, region=region_name)
        address_prefix_json = client.create_address_prefix(vpc_id=vpc_resource_id, address_prefix_json=resource_json)

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

        with db_session.no_autoflush:
            zone = \
                db_session.query(IBMZone).filter_by(name=address_prefix_json["zone"]["name"], cloud_id=cloud_id).first()
            vpc_network = \
                db_session.query(IBMVpcNetwork).filter_by(resource_id=vpc_resource_id, cloud_id=cloud_id).first()

            if address_prefix_json["is_default"]:
                for existing_address_prefix in \
                        vpc_network.address_prefixes.filter_by(zone_id=zone.id, is_default=True).all():
                    existing_address_prefix.is_default = False

            address_prefix = IBMAddressPrefix.from_ibm_json_body(json_body=address_prefix_json)
            address_prefix.zone = zone
            address_prefix.vpc_network = vpc_network
            address_prefix_json = address_prefix.to_json()
            address_prefix_json["created_at"] = str(address_prefix.created_at)

            IBMResourceLog(
                resource_id=address_prefix.resource_id, region=zone.region,
                status=IBMResourceLog.STATUS_ADDED, resource_type=IBMAddressPrefix.__name__,
                data=address_prefix_json)
            db_session.commit()
        workflow_task.resource_id = address_prefix.id
        workflow_task.status = WorkflowTask.STATUS_SUCCESSFUL
        message = f"IBM Address Prefix '{address_prefix_json['name']}' creation for cloud '{cloud_id}' successful"
        db_session.commit()

    LOGGER.success(message)


@celery.task(name="delete_address_prefix", base=IBMWorkflowTasksBase)
def delete_address_prefix(workflow_task_id):
    """
    Delete an IBM Address Prefix
    :param workflow_task_id:
    :return:
    """
    with get_db_session() as db_session:
        workflow_task = db_session.query(WorkflowTask).filter_by(id=workflow_task_id).first()
        if not workflow_task:
            return

        workflow_task.status = WorkflowTask.STATUS_RUNNING
        db_session.commit()

        address_prefix = db_session.query(IBMAddressPrefix).filter_by(id=workflow_task.resource_id).first()
        if not address_prefix:
            workflow_task.status = WorkflowTask.STATUS_FAILED
            workflow_task.message = f"IBMAddressPrefix '{workflow_task.resource_id}' not found"
            db_session.commit()
            LOGGER.error(workflow_task.message)
            return

        vpc_resource_id = address_prefix.vpc_network.resource_id
        region_name = address_prefix.region.name
        address_prefix_resource_id = address_prefix.resource_id
        cloud_id = address_prefix.cloud_id
        address_prefix_name = address_prefix.name

    try:
        vpc_client = VPCsClient(cloud_id, region=region_name)
        vpc_client.delete_address_prefix(vpc_id=vpc_resource_id, address_prefix_id=address_prefix_resource_id)

    except ApiException as ex:
        with get_db_session() as db_session:
            workflow_task = db_session.query(WorkflowTask).filter_by(id=workflow_task_id).first()
            if not workflow_task:
                return

            if ex.code == 404:  # 404 means resource is not found on IBM Cloud.
                address_prefix = db_session.query(IBMAddressPrefix).filter_by(id=workflow_task.resource_id).first()
                if address_prefix:
                    address_prefix_json = address_prefix.to_json()
                    address_prefix_json["created_at"] = str(address_prefix_json["created_at"])

                    IBMResourceLog(
                        resource_id=address_prefix.resource_id, region=address_prefix.region,
                        status=IBMResourceLog.STATUS_DELETED, resource_type=IBMAddressPrefix.__name__,
                        data=address_prefix_json)

                    db_session.delete(address_prefix)

                workflow_task.status = WorkflowTask.STATUS_SUCCESSFUL
                db_session.commit()
                LOGGER.success(f"IBM Address Prefix {address_prefix_name} for cloud {cloud_id} deletion successful.")
                return

            IBMResourceLog(
                resource_id=address_prefix.resource_id, region=address_prefix.region,
                status=IBMResourceLog.STATUS_DELETED, resource_type=IBMAddressPrefix.__name__,
                data=address_prefix.to_json())

            workflow_task.status = WorkflowTask.STATUS_FAILED
            workflow_task.message = f"Deletion Failed. Reason: {str(ex.message)}"
            db_session.commit()
            LOGGER.fail(workflow_task.message)
            return

    with get_db_session() as db_session:
        workflow_task = db_session.query(WorkflowTask).filter_by(id=workflow_task_id).first()
        if not workflow_task:
            return

        address_prefix = db_session.query(IBMAddressPrefix).filter_by(id=workflow_task.resource_id).first()
        if address_prefix:
            db_session.delete(address_prefix)

        address_prefix_json = address_prefix.to_json()
        address_prefix_json["created_at"] = str(address_prefix_json["created_at"])

        IBMResourceLog(
            resource_id=address_prefix.resource_id, region=address_prefix.region,
            status=IBMResourceLog.STATUS_DELETED, resource_type=IBMAddressPrefix.__name__,
            data=address_prefix_json)

        workflow_task.status = WorkflowTask.STATUS_SUCCESSFUL
        LOGGER.success(f"IBM Address Prefix {address_prefix_name} for cloud {cloud_id} deletion successful.")
        db_session.commit()
