from copy import deepcopy
from ibm_cloud_sdk_core import ApiException

from ibm import get_db_session, LOGGER
from ibm.common.clients.ibm_clients import DedicatedHostsClient
from ibm.common.utils import update_id_or_name_references
from ibm.models import IBMDedicatedHostGroup, IBMDedicatedHostProfile, IBMRegion, IBMResourceGroup, IBMZone, \
    WorkflowTask
from ibm.models.ibm.resource_log_models import IBMResourceLog
from ibm.tasks.celery_app import celery_app as celery
from ibm.tasks.common.tasks_base import IBMWorkflowTasksBase
from ibm.tasks.ibm.task_utils import load_previous_associated_resources
from ibm.web.ibm.dedicated_hosts.dedicated_host_groups.schemas import IBMDedicatedHostGroupInSchema, \
    IBMDedicatedHostGroupResourceSchema


@celery.task(name="create_dedicated_host_group", base=IBMWorkflowTasksBase)
def create_ibm_dedicated_host_group(workflow_task_id):
    """
    Create an IBM Dedicated Host Group Key on IBM Cloud
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
        dh_profile_dict = resource_json["profile"]

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
        dh_profile = \
            db_session.query(IBMDedicatedHostProfile).filter_by(**dh_profile_dict, cloud_id=cloud_id).first()
        if not dh_profile:
            workflow_task.status = WorkflowTask.STATUS_FAILED
            workflow_task.message = f"IBMDedicatedHostProfile " \
                                    f"'{dh_profile_dict.get('id') or dh_profile_dict.get('name')}' not found"
            db_session.commit()
            LOGGER.error(workflow_task.message)
            return

        resource_json["class_"] = dh_profile.class_
        resource_json["family"] = dh_profile.family
        resource_json.pop("profile")

        previous_resources = load_previous_associated_resources(task=workflow_task, session=db_session)
        update_id_or_name_references(
            cloud_id=cloud_id, resource_json=resource_data, resource_schema=IBMDedicatedHostGroupInSchema,
            db_session=db_session, previous_resources=previous_resources
        )
        update_id_or_name_references(
            cloud_id=cloud_id, resource_json=resource_json, resource_schema=IBMDedicatedHostGroupResourceSchema,
            db_session=db_session, previous_resources=previous_resources
        )

    try:
        client = DedicatedHostsClient(cloud_id=cloud_id, region=region_name)
        resp_json = client.create_dedicated_host_group(dedicated_host_group_json=resource_json)
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
            zone = db_session.query(IBMZone).filter_by(name=resp_json["zone"]["name"], cloud_id=cloud_id).first()
            resource_group = \
                db_session.query(IBMResourceGroup).filter_by(
                    resource_id=resp_json["resource_group"]["id"], cloud_id=cloud_id
                ).first()
            if not (zone and resource_group):
                workflow_task.status = WorkflowTask.STATUS_FAILED
                workflow_task.message = \
                    "Creation Successful but record update failed. The records will update next time discovery runs"
                db_session.commit()
                LOGGER.note(workflow_task.message)
                return

            dedicated_host_group = IBMDedicatedHostGroup.from_ibm_json_body(json_body=resp_json)
            dedicated_host_group.zone = zone
            dedicated_host_group.resource_group = resource_group
            dedicated_host_group_json = dedicated_host_group.to_json()
            dedicated_host_group_json["created_at"] = str(dedicated_host_group_json["created_at"])

            IBMResourceLog(
                resource_id=dedicated_host_group.resource_id, region=zone.region,
                status=IBMResourceLog.STATUS_ADDED, resource_type=IBMDedicatedHostGroup.__name__,
                data=dedicated_host_group_json)

            db_session.commit()
            workflow_task.status = WorkflowTask.STATUS_SUCCESSFUL
            message = f"IBM Dedicated Host Group '{resp_json['name']}' creation for cloud '{cloud_id}' successful"
            db_session.commit()

        LOGGER.success(message)


@celery.task(name="delete_dedicated_host_group", base=IBMWorkflowTasksBase)
def delete_dedicated_host_group(workflow_task_id):
    """
    Delete an IBM Dedicated Host Group
    :param workflow_task_id:
    :return:
    """
    with get_db_session() as db_session:
        workflow_task = db_session.query(WorkflowTask).filter_by(id=workflow_task_id).first()
        if not workflow_task:
            return

        workflow_task.status = WorkflowTask.STATUS_RUNNING
        db_session.commit()

        dedicated_host_group = db_session.query(IBMDedicatedHostGroup).filter_by(id=workflow_task.resource_id).first()
        if not dedicated_host_group:
            workflow_task.status = WorkflowTask.STATUS_FAILED
            workflow_task.message = f"IBMDedicatedHostGroup '{workflow_task.resource_id}' not found"
            db_session.commit()
            LOGGER.error(workflow_task.message)
            return

        region_name = dedicated_host_group.region.name
        dedicated_host_group_resource_id = dedicated_host_group.resource_id
        cloud_id = dedicated_host_group.cloud_id
        dh_group_name = dedicated_host_group.name

    try:
        dedicated_host_client = DedicatedHostsClient(cloud_id, region=region_name)
        dedicated_host_client.delete_dedicated_host_group(dedicated_host_group_resource_id)

    except ApiException as ex:
        with get_db_session() as db_session:
            workflow_task = db_session.query(WorkflowTask).filter_by(id=workflow_task_id).first()
            if not workflow_task:
                return

            if ex.code == 404:  # 404 means resource is not found on IBM Cloud.
                dedicated_host_group = db_session.query(IBMDedicatedHostGroup).filter_by(
                    id=workflow_task.resource_id).first()
                if dedicated_host_group:
                    db_session.delete(dedicated_host_group)

                IBMResourceLog(
                    resource_id=dedicated_host_group.resource_id, region=dedicated_host_group.region,
                    status=IBMResourceLog.STATUS_DELETED, resource_type=IBMDedicatedHostGroup.__name__,
                    data=dedicated_host_group.to_json())

                workflow_task.status = WorkflowTask.STATUS_SUCCESSFUL
                LOGGER.success(f"IBM DedicatedHostGroup {dh_group_name} for cloud {cloud_id} deletion successful.")
                db_session.commit()
                return

            workflow_task.status = WorkflowTask.STATUS_FAILED
            workflow_task.message = f"Deletion Failed. Reason: {str(ex.message)}"
            db_session.commit()
            LOGGER.fail(workflow_task.message)
            return

    with get_db_session() as db_session:
        workflow_task = db_session.query(WorkflowTask).filter_by(id=workflow_task_id).first()
        if not workflow_task:
            return

        dedicated_host_group = db_session.query(IBMDedicatedHostGroup).filter_by(id=workflow_task.resource_id).first()
        if dedicated_host_group:
            db_session.delete(dedicated_host_group)

        dedicated_host_group_json = dedicated_host_group.to_json()
        dedicated_host_group_json["created_at"] = str(dedicated_host_group_json["created_at"])

        IBMResourceLog(
            resource_id=dedicated_host_group.resource_id, region=dedicated_host_group.region,
            status=IBMResourceLog.STATUS_DELETED, resource_type=IBMDedicatedHostGroup.__name__,
            data=dedicated_host_group_json)

        workflow_task.status = WorkflowTask.STATUS_SUCCESSFUL
        LOGGER.success(f"IBM DedicatedHostGroup {dh_group_name} for cloud {cloud_id} deletion successful.")
        db_session.commit()
