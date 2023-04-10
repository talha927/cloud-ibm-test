import logging
from copy import deepcopy
from ibm_cloud_sdk_core import ApiException

from ibm import get_db_session
from ibm.common.clients.ibm_clients import SSHKeysClient
from ibm.common.utils import update_id_or_name_references
from ibm.models import IBMRegion, IBMResourceGroup, IBMResourceLog, IBMSshKey, WorkflowTask
from ibm.tasks.celery_app import celery_app as celery
from ibm.tasks.common.tasks_base import IBMWorkflowTasksBase
from ibm.tasks.ibm.task_utils import load_previous_associated_resources
from ibm.web.ibm.ssh_keys.schemas import IBMSshKeyInSchema, IBMSshKeyResourceSchema

LOGGER = logging.getLogger(__name__)


@celery.task(name="create_ssh_key", base=IBMWorkflowTasksBase)
def create_ssh_key(workflow_task_id):
    """
    Create an IBM SSH Key on IBM Cloud
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
            LOGGER.info(workflow_task.message)
            return

        if region.ibm_status == IBMRegion.IBM_STATUS_UNAVAILABLE:
            workflow_task.status = WorkflowTask.STATUS_FAILED
            workflow_task.message = f"IBMRegion '{region.name}' unavailable"
            db_session.commit()
            LOGGER.info(workflow_task.message)
            return

        region_name = region.name

        previous_resources = load_previous_associated_resources(task=workflow_task, session=db_session)
        update_id_or_name_references(
            cloud_id=cloud_id, resource_json=resource_data, resource_schema=IBMSshKeyInSchema,
            db_session=db_session, previous_resources=previous_resources
        )

        update_id_or_name_references(
            cloud_id=cloud_id, resource_json=resource_json, resource_schema=IBMSshKeyResourceSchema,
            db_session=db_session, previous_resources=previous_resources
        )

    try:
        client = SSHKeysClient(cloud_id=cloud_id, region=region_name)
        ssh_key_json = client.create_ssh_key(key_json=resource_json)
    except ApiException as ex:
        with get_db_session() as db_session:
            workflow_task = db_session.query(WorkflowTask).filter_by(id=workflow_task_id).first()
            if not workflow_task:
                return
            if ex.code == 400 or ex.code == 409:
                split_public_key = resource_json["public_key"].rsplit(" ", 1)

                ssh_key_obj = db_session.query(IBMSshKey).filter_by(
                    name=resource_json["name"], public_key=split_public_key[0], region_id=region_id).first()

                if not ssh_key_obj:
                    ssh_key_obj = db_session.query(IBMSshKey).filter_by(
                        name=resource_json["name"], public_key=resource_json["public_key"], region_id=region_id).first()
                workflow_task.resource_id = ssh_key_obj.id
                workflow_task.status = WorkflowTask.STATUS_SUCCESSFUL
                workflow_task.message = f"IBMSshKey Already with same name and public key exist in db with ID:" \
                                        f"{ssh_key_obj.id}"
                LOGGER.info(workflow_task.message)
                db_session.commit()
                return

            workflow_task.status = WorkflowTask.STATUS_FAILED
            workflow_task.message = f"Creation Failed. Reason: {str(ex.message)}"
            db_session.commit()

        LOGGER.info("Create SSH Key failed with status code " + str(ex.code) + ": " + ex.message)
        return

    with get_db_session() as db_session:
        workflow_task = db_session.query(WorkflowTask).filter_by(id=workflow_task_id).first()
        if not workflow_task:
            return

        with db_session.no_autoflush:
            region = db_session.query(IBMRegion).filter_by(id=region_id, cloud_id=cloud_id).first()
            resource_group = \
                db_session.query(IBMResourceGroup).filter_by(
                    resource_id=ssh_key_json["resource_group"]["id"], cloud_id=cloud_id
                ).first()

            ssh_key = IBMSshKey.from_ibm_json_body(json_body=ssh_key_json)
            ssh_key.region = region
            ssh_key.resource_group = resource_group
            db_session.commit()

        ssh_key_json = ssh_key.to_json()
        ssh_key_json["created_at"] = str(ssh_key_json["created_at"])

        IBMResourceLog(
            resource_id=ssh_key.resource_id, region=ssh_key.region,
            status=IBMResourceLog.STATUS_ADDED, resource_type=IBMSshKey.__name__,
            data=ssh_key_json)

        workflow_task.status = WorkflowTask.STATUS_SUCCESSFUL
        workflow_task.resource_id = ssh_key.id
        message = f"IBM SSH Key '{ssh_key_json['name']}' creation for cloud '{cloud_id}' successful"
        db_session.commit()

    LOGGER.info(message)


@celery.task(name="delete_ssh_key", base=IBMWorkflowTasksBase)
def delete_ssh_key(workflow_task_id):
    """
    Delete an IBM SSH Key
    :param workflow_task_id:
    :return:
    """
    with get_db_session() as db_session:
        workflow_task: WorkflowTask = db_session.get(WorkflowTask, workflow_task_id)
        if not workflow_task:
            return

        workflow_task.status = WorkflowTask.STATUS_RUNNING
        db_session.commit()

        ssh_key: IBMSshKey = db_session.get(IBMSshKey, workflow_task.resource_id)
        if not ssh_key:
            workflow_task.status = WorkflowTask.STATUS_FAILED
            workflow_task.message = f"IBMSshKey '{workflow_task.resource_id}' not found"
            db_session.commit()
            LOGGER.info(workflow_task.message)
            return

        region_name = ssh_key.region.name
        ssh_key_resource_id = ssh_key.resource_id
        cloud_id = ssh_key.cloud_id
        ssh_key_name = ssh_key.name
    try:
        ssh_key_client = SSHKeysClient(cloud_id, region_name)
        ssh_key_client.delete_ssh_key(ssh_key_resource_id)

    except ApiException as ex:
        with get_db_session() as db_session:
            workflow_task: WorkflowTask = db_session.get(WorkflowTask, workflow_task_id)
            if not workflow_task:
                return

            if ex.code == 404:  # 404 means resource is not found on IBM Cloud.
                ssh_key: IBMSshKey = db_session.get(IBMSshKey, workflow_task.resource_id)
                if ssh_key:
                    ssh_key_json = ssh_key.to_json()
                    ssh_key_json["created_at"] = str(ssh_key_json["created_at"])

                    IBMResourceLog(
                        resource_id=ssh_key.resource_id, region=ssh_key.region,
                        status=IBMResourceLog.STATUS_DELETED, resource_type=IBMSshKey.__name__,
                        data=ssh_key_json)

                    db_session.delete(ssh_key)

                workflow_task.status = WorkflowTask.STATUS_SUCCESSFUL
                LOGGER.info(f"IBM SSH Key {ssh_key_name} for cloud {ssh_key.cloud_id} deletion successful.")
                db_session.commit()
                return
            else:
                LOGGER.info(f"IBM SSH Key {ssh_key_name} for cloud {cloud_id} deletion failed.")
                workflow_task.status = WorkflowTask.STATUS_FAILED
                workflow_task.message = f"Deletion Failed. Reason: {str(ex.message)}"
                db_session.commit()
                return

    with get_db_session() as db_session:
        workflow_task: WorkflowTask = db_session.get(WorkflowTask, workflow_task_id)
        if not workflow_task:
            return

        ssh_key: IBMSshKey = db_session.get(IBMSshKey, workflow_task.resource_id)
        if ssh_key:
            ssh_key_json = ssh_key.to_json()
            ssh_key_json["created_at"] = str(ssh_key_json["created_at"])

            IBMResourceLog(
                resource_id=ssh_key.resource_id, region=ssh_key.region,
                status=IBMResourceLog.STATUS_DELETED, resource_type=IBMSshKey.__name__,
                data=ssh_key_json)

            db_session.delete(ssh_key)

        workflow_task.status = WorkflowTask.STATUS_SUCCESSFUL
        LOGGER.info(f"IBM SSH Key {ssh_key_name} for cloud {cloud_id} deletion successful.")
        db_session.commit()
        return
