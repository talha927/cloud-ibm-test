from copy import deepcopy
from ibm_cloud_sdk_core import ApiException

from ibm import get_db_session, LOGGER
from ibm.common.clients.ibm_clients import VPNsClient
from ibm.common.utils import update_id_or_name_references
from ibm.models import IBMIKEPolicy, IBMRegion, IBMResourceGroup, IBMResourceLog, WorkflowTask
from ibm.tasks.celery_app import celery_app as celery
from ibm.tasks.common.tasks_base import IBMWorkflowTasksBase
from ibm.tasks.ibm.task_utils import load_previous_associated_resources
from ibm.web.ibm.vpn_gateways.ike_policies.schemas import IBMIKEPoliciesInSchema, IBMIKEPoliciesResourceSchema


@celery.task(name="create_ike_policy", base=IBMWorkflowTasksBase)
def create_ike_policy(workflow_task_id):
    """
    Create an IBM IKE Policy on IBM Cloud
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
            cloud_id=cloud_id, resource_json=resource_data, resource_schema=IBMIKEPoliciesInSchema,
            db_session=db_session, previous_resources=previous_resources
        )

        update_id_or_name_references(
            cloud_id=cloud_id, resource_json=resource_json, resource_schema=IBMIKEPoliciesResourceSchema,
            db_session=db_session, previous_resources=previous_resources
        )

    try:
        client = VPNsClient(cloud_id=cloud_id, region=region_name)
        # TODO: we need to do in proper way
        if resource_json.get("dh_group"):
            resource_json["dh_group"] = int(resource_json["dh_group"])
        ike_policy_json = client.create_ike_policy(ike_policy_json=resource_json)
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
                    resource_id=ike_policy_json["resource_group"]["id"], cloud_id=cloud_id
                ).first()

            if not region or not resource_group:
                workflow_task.status = WorkflowTask.STATUS_FAILED
                workflow_task.message = \
                    "Creation Successful but record update failed. The records will update next time discovery runs"
                db_session.commit()
                LOGGER.note(workflow_task.message)

            ike_policy = IBMIKEPolicy.from_ibm_json_body(json_body=ike_policy_json)
            ike_policy.region = region
            ike_policy.resource_group = resource_group
            db_session.commit()

        ike_policy_json = ike_policy.to_json()
        ike_policy_json["created_at"] = str(ike_policy_json["created_at"])

        IBMResourceLog(
            resource_id=ike_policy.resource_id, region=ike_policy.region,
            status=IBMResourceLog.STATUS_ADDED, resource_type=IBMIKEPolicy.__name__,
            data=ike_policy_json)

        workflow_task.status = WorkflowTask.STATUS_SUCCESSFUL
        workflow_task.resource_id = ike_policy.id
        db_session.commit()
        LOGGER.success(f"IBM IKE Policy '{ike_policy_json['name']}' creation for cloud '{cloud_id}' successful")


@celery.task(name="delete_ike_policy", base=IBMWorkflowTasksBase)
def delete_ike_policy(workflow_task_id):
    """
    Delete an IBM Ike Policy
    :param workflow_task_id:
    :return:
    """

    with get_db_session() as db_session:
        workflow_task = db_session.query(WorkflowTask).filter_by(id=workflow_task_id).first()
        if not workflow_task:
            return

        workflow_task.status = WorkflowTask.STATUS_RUNNING
        db_session.commit()
        ike_policy: IBMIKEPolicy = db_session.query(IBMIKEPolicy).filter_by(id=workflow_task.resource_id).first()
        if not ike_policy:
            workflow_task.status = WorkflowTask.STATUS_FAILED
            workflow_task.message = f"IBM Ike Policy '{workflow_task.resource_id}' not found"
            db_session.commit()
            LOGGER.error(workflow_task.message)
            return

        region_name = ike_policy.region.name
        ike_policy_resource_id = ike_policy.resource_id
        cloud_id = ike_policy.cloud_id
        ike_policy_name = ike_policy.name
    try:
        ike_policy_client = VPNsClient(cloud_id, region=region_name)
        ike_policy_client.delete_ike_policy(ike_policy_id=ike_policy_resource_id)

    except ApiException as ex:
        with get_db_session() as db_session:
            workflow_task = db_session.query(WorkflowTask).filter_by(id=workflow_task_id).first()
            if not workflow_task:
                return

            if ex.code == 404:  # 404 means resource is not found on IBM Cloud.
                ike_policy: IBMIKEPolicy = db_session.query(IBMIKEPolicy).filter_by(
                    id=workflow_task.resource_id).first()
                if ike_policy:
                    db_session.delete(ike_policy)

                workflow_task.status = WorkflowTask.STATUS_SUCCESSFUL
                workflow_task.resource_id = ike_policy.id
                LOGGER.success(f"IBM IKE Policy {ike_policy_name} for cloud {cloud_id} deletion successful.")

                ike_policy_json = ike_policy.to_json()
                ike_policy_json["created_at"] = str(ike_policy_json["created_at"])

                IBMResourceLog(
                    resource_id=ike_policy.resource_id, region=ike_policy.region,
                    status=IBMResourceLog.STATUS_DELETED, resource_type=IBMIKEPolicy.__name__,
                    data=ike_policy_json)
                db_session.commit()
                return

            else:
                workflow_task.status = WorkflowTask.STATUS_FAILED
                workflow_task.message = \
                    f"IBM IKE Policy {workflow_task.resource_id} deletion failed. Reason: {str(ex.message)}"
                db_session.commit()
                LOGGER.fail(workflow_task.message)
                return

    with get_db_session() as db_session:
        workflow_task = db_session.query(WorkflowTask).filter_by(id=workflow_task_id).first()
        if not workflow_task:
            return

        ike_policy: IBMIKEPolicy = db_session.query(IBMIKEPolicy).filter_by(
            id=workflow_task.resource_id).first()
        if ike_policy:
            ike_policy_json = ike_policy.to_json()
            ike_policy_json["created_at"] = str(ike_policy_json["created_at"])

            IBMResourceLog(
                resource_id=ike_policy.resource_id, region=ike_policy.region,
                status=IBMResourceLog.STATUS_DELETED, resource_type=IBMIKEPolicy.__name__,
                data=ike_policy_json)

            db_session.delete(ike_policy)

        workflow_task.status = WorkflowTask.STATUS_SUCCESSFUL
        workflow_task.resource_id = ike_policy.id
        LOGGER.success(f"IBM IKE Policy {ike_policy_name} for cloud {cloud_id} deletion successful.")
        db_session.commit()
