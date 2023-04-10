from copy import deepcopy
from ibm_cloud_sdk_core import ApiException

from ibm import get_db_session, LOGGER
from ibm.common.clients.ibm_clients import ResourceInstancesClient
from ibm.models import IBMCloud, IBMCloudObjectStorage, IBMResourceGroup, IBMServiceCredentialKey, WorkflowTask
from ibm.tasks.celery_app import celery_app as celery
from ibm.tasks.common.tasks_base import IBMWorkflowTasksBase


@celery.task(name="sync_credential_keys", base=IBMWorkflowTasksBase)
def sync_credential_keys(workflow_task_id):
    """
    Sync Service Credential Keys with IBM.
    """
    with get_db_session() as db_session:
        workflow_task = db_session.query(WorkflowTask).filter_by(id=workflow_task_id).first()
        if not workflow_task:
            return

        workflow_task.status = WorkflowTask.STATUS_RUNNING
        db_session.commit()

        resource_data = deepcopy(workflow_task.task_metadata["resource_data"])
        cloud_id = resource_data["cloud_id"]
        ibm_cloud = db_session.query(IBMCloud).filter_by(id=cloud_id).first()
        if not ibm_cloud:
            workflow_task.status = WorkflowTask.STATUS_FAILED
            workflow_task.message = f"IBMCloud '{cloud_id}' not found"
            db_session.commit()
            LOGGER.error(workflow_task.message)
            return

    try:
        client = ResourceInstancesClient(cloud_id=cloud_id)
        fetched_credentials_keys_dicts_list = client.list_resource_keys()

        updated_credential_keys_names = [keys_dict["name"] for keys_dict in fetched_credentials_keys_dicts_list]

    except ApiException as ex:
        with get_db_session() as db_session:
            workflow_task = db_session.query(WorkflowTask).filter_by(id=workflow_task_id).first()
            if not workflow_task:
                return

            workflow_task.status = WorkflowTask.STATUS_FAILED
            workflow_task.message = f"Method Failed. Reason: {str(ex.message)}"
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

        deletable_key = db_session.query(IBMServiceCredentialKey).filter(
            IBMServiceCredentialKey.cloud_id == cloud_id,
            IBMServiceCredentialKey.name.not_in(updated_credential_keys_names)
        ).all()
        for key in deletable_key:
            db_session.delete(key)
            db_session.commit()

        db_credential_keys = db_session.query(IBMServiceCredentialKey).filter_by(
            cloud_id=cloud_id).all()
        db_credential_keys_names_list = [db_credential_key.name
                                         for db_credential_key in db_credential_keys]

        for keys_dict in fetched_credentials_keys_dicts_list:
            # TODO: This check is to ignore the database-for-mongodb/Administrator keys.
            #  Those need further research before implementation as they differ from normal hmac keys payload.
            if not all([keys_dict.get("role"), keys_dict["credentials"].get("resource_instance_id")]):
                continue

            parsed_keys = IBMServiceCredentialKey.from_ibm_json_body(keys_dict)
            if parsed_keys.name in db_credential_keys_names_list:
                continue
            else:
                cos = db_session.query(IBMCloudObjectStorage).filter_by(
                    crn=keys_dict["credentials"]["resource_instance_id"], cloud_id=cloud_id).first()
                if not cos:
                    workflow_task.status = WorkflowTask.STATUS_FAILED
                    workflow_task.message = \
                        f"IBM Cloud Object Storage '{keys_dict['credentials']['resource_instance_id']}' not found"
                    db_session.commit()
                    LOGGER.error(workflow_task.message)
                    return

                resource_group = db_session.query(IBMResourceGroup).filter_by(
                    resource_id=keys_dict["resource_group_id"], cloud_id=cloud_id).first()

                if not resource_group:
                    workflow_task.status = WorkflowTask.STATUS_FAILED
                    workflow_task.message = f"IBM Resource Group '{keys_dict['resource_group_id']}' not found"
                    db_session.commit()
                    LOGGER.error(workflow_task.message)
                    return

                parsed_keys.cloud_object_storage = cos
                parsed_keys.resource_group = resource_group
                parsed_keys.ibm_cloud = ibm_cloud

            db_session.commit()

        workflow_task.status = WorkflowTask.STATUS_SUCCESSFUL
        db_session.commit()

    LOGGER.success(f"IBM Service Credential Keys for cloud id {cloud_id} updated successfully.")
