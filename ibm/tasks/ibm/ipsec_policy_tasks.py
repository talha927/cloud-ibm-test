from copy import deepcopy
from ibm_cloud_sdk_core import ApiException

from ibm import get_db_session, LOGGER
from ibm.common.clients.ibm_clients import VPNsClient
from ibm.common.utils import update_id_or_name_references
from ibm.models import IBMIPSecPolicy, IBMRegion, IBMResourceGroup, IBMResourceLog, WorkflowTask
from ibm.tasks.celery_app import celery_app as celery
from ibm.tasks.common.tasks_base import IBMWorkflowTasksBase
from ibm.tasks.ibm.task_utils import load_previous_associated_resources
from ibm.web.ibm.vpn_gateways.ipsec_policies.schemas import IBMIPSecPoliciesInSchema, IBMIPSecPoliciesResourceSchema


@celery.task(name="create_ipsec_policy", base=IBMWorkflowTasksBase)
def create_ipsec_policy(workflow_task_id):
    """
    Create an IBM IPSEC Policy on IBM Cloud
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
            cloud_id=cloud_id, resource_json=resource_data, resource_schema=IBMIPSecPoliciesInSchema,
            db_session=db_session, previous_resources=previous_resources
        )

        update_id_or_name_references(
            cloud_id=cloud_id, resource_json=resource_json, resource_schema=IBMIPSecPoliciesResourceSchema,
            db_session=db_session, previous_resources=previous_resources
        )

    try:
        client = VPNsClient(cloud_id=cloud_id, region=region_name)
        ipsec_policy_json = client.create_ipsec_policy(ipsec_policy_json=resource_json)
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
            region = db_session.query(IBMRegion).filter_by(id=region_id, cloud_id=cloud_id).first()
            resource_group = \
                db_session.query(IBMResourceGroup).filter_by(
                    resource_id=ipsec_policy_json["resource_group"]["id"], cloud_id=cloud_id
                ).first()

            if not region or not resource_group:
                workflow_task.status = WorkflowTask.STATUS_FAILED
                workflow_task.message = \
                    "Creation Successful but record update failed. The records will update next time discovery runs"
                db_session.commit()
                LOGGER.note(workflow_task.message)

            ipsec_policy = IBMIPSecPolicy.from_ibm_json_body(json_body=ipsec_policy_json)
            ipsec_policy.region = region
            ipsec_policy.resource_group = resource_group
            db_session.commit()

        workflow_task.status = WorkflowTask.STATUS_SUCCESSFUL
        ipsec_policy_json = ipsec_policy.to_json()
        ipsec_policy_json["created_at"] = str(ipsec_policy_json["created_at"])

        IBMResourceLog(
            resource_id=ipsec_policy.resource_id, region=ipsec_policy.region,
            status=IBMResourceLog.STATUS_ADDED, resource_type=IBMIPSecPolicy.__name__,
            data=ipsec_policy_json)

        workflow_task.resource_id = ipsec_policy.id
        db_session.commit()
        LOGGER.success(f"IBM IPSEC Policy '{ipsec_policy_json['name']}' creation for cloud '{cloud_id}' successful")


@celery.task(name="delete_ipsec_policy", base=IBMWorkflowTasksBase)
def delete_ipsec_policy(workflow_task_id):
    """
    Delete an IBM Ipsec Policy
    :param workflow_task_id:
    :return:
    """

    with get_db_session() as db_session:
        workflow_task: WorkflowTask = db_session.query(WorkflowTask).filter_by(id=workflow_task_id).first()
        if not workflow_task:
            return

        workflow_task.status = WorkflowTask.STATUS_RUNNING
        db_session.commit()

        ipsec_policy: IBMIPSecPolicy = db_session.query(IBMIPSecPolicy).filter_by(id=workflow_task.resource_id).first()
        if not ipsec_policy:
            workflow_task.status = WorkflowTask.STATUS_FAILED
            workflow_task.message = f"IBM Ipsec Policy '{workflow_task.resource_id}' not found"
            db_session.commit()
            LOGGER.error(workflow_task.message)
            return

        region_name = ipsec_policy.region.name
        ipsec_policy_resource_id = ipsec_policy.resource_id
        cloud_id = ipsec_policy.cloud_id
        ipsec_policy_name = ipsec_policy.name
    try:
        ipsec_policy_client = VPNsClient(cloud_id, region=region_name)
        ipsec_policy_client.delete_ipsec_policy(ipsec_policy_id=ipsec_policy_resource_id)

    except ApiException as ex:
        with get_db_session() as db_session:
            workflow_task = db_session.query(WorkflowTask).filter_by(id=workflow_task_id).first()
            if not workflow_task:
                return

            if ex.code == 404:  # 404 means resource is not found on IBM Cloud.
                ipsec_policy: IBMIPSecPolicy = db_session.query(IBMIPSecPolicy).filter_by(
                    id=workflow_task.resource_id).first()
                if ipsec_policy:
                    db_session.delete(ipsec_policy)

                workflow_task.status = WorkflowTask.STATUS_SUCCESSFUL
                workflow_task.resource_id = ipsec_policy.id
                ipsec_policy_json = ipsec_policy.to_json()
                ipsec_policy_json["created_at"] = str(ipsec_policy_json["created_at"])

                IBMResourceLog(
                    resource_id=ipsec_policy.resource_id, region=ipsec_policy.region,
                    status=IBMResourceLog.STATUS_DELETED, resource_type=IBMIPSecPolicy.__name__,
                    data=ipsec_policy_json)

                LOGGER.success(f"IBM IPSEC Policy {ipsec_policy_name} for cloud {cloud_id} deletion successful.")
                db_session.commit()
                return

            else:
                workflow_task.status = WorkflowTask.STATUS_FAILED
                workflow_task.message = \
                    f"IBMIPSECPolicy {workflow_task.resource_id} deletion failed. Reason: {str(ex.message)}"
                db_session.commit()
                LOGGER.fail(workflow_task.message)

    with get_db_session() as db_session:
        workflow_task = db_session.query(WorkflowTask).filter_by(id=workflow_task_id).first()
        if not workflow_task:
            return

        ipsec_policy: IBMIPSecPolicy = db_session.query(IBMIPSecPolicy).filter_by(
            id=workflow_task.resource_id).first()
        if ipsec_policy:
            db_session.delete(ipsec_policy)

        workflow_task.status = WorkflowTask.STATUS_SUCCESSFUL

        ipsec_policy_json = ipsec_policy.to_json()
        ipsec_policy_json["created_at"] = str(ipsec_policy_json["created_at"])

        IBMResourceLog(
            resource_id=ipsec_policy.resource_id, region=ipsec_policy.region,
            status=IBMResourceLog.STATUS_DELETED, resource_type=IBMIPSecPolicy.__name__,
            data=ipsec_policy_json)

        workflow_task.resource_id = ipsec_policy.id
        LOGGER.success(f"IBM IPSEC Policy {ipsec_policy_name} for cloud {cloud_id} deletion successful.")
        db_session.commit()
