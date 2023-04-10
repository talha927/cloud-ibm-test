import logging
from copy import deepcopy
from ibm_cloud_sdk_core import ApiException

from ibm import get_db_session
from ibm.common.clients.ibm_clients import LoadBalancersClient
from ibm.common.utils import update_id_or_name_references
from ibm.models import IBMListener, IBMListenerPolicy, IBMListenerPolicyRule, IBMLoadBalancer, IBMPool, IBMRegion, \
    LBCommonConsts, WorkflowTask
from ibm.tasks.celery_app import celery_app as celery
from ibm.tasks.common.tasks_base import IBMWorkflowTasksBase
from ibm.tasks.ibm.task_utils import load_previous_associated_resources
from ibm.web.ibm.load_balancers.listeners.policies.rules.schemas import IBMListenerPolicyRuleResourceSchema
from ibm.web.ibm.load_balancers.listeners.policies.schemas import IBMListenerPolicyInSchema, \
    IBMListenerPolicyResourceSchema

LOGGER = logging.getLogger(__name__)


@celery.task(name="create_listener_policy", base=IBMWorkflowTasksBase)
def create_listener_policy(workflow_task_id):
    """
    Create an IBM Listener Policy on IBM Cloud
    """
    with get_db_session() as db_session:
        workflow_task: WorkflowTask = db_session.get(WorkflowTask, workflow_task_id)
        if not workflow_task:
            return

        workflow_task.status = WorkflowTask.STATUS_RUNNING
        db_session.commit()

        resource_data = deepcopy(workflow_task.task_metadata["resource_data"])
        resource_json = deepcopy(resource_data["resource_json"])
        cloud_id = resource_data["ibm_cloud"]["id"]
        region_id = resource_data["region"]["id"]
        listener_id_or_name = resource_data["listener"].get('id') or resource_data["listener"].get("name")

        region: IBMRegion = db_session.get(IBMRegion, region_id)
        if not region:
            workflow_task.status = WorkflowTask.STATUS_FAILED
            workflow_task.message = f"IBMRegion `{region_id}` not found."
            db_session.commit()
            LOGGER.info(workflow_task.message)
            return

        if region.ibm_status == IBMRegion.IBM_STATUS_UNAVAILABLE:
            workflow_task.status = WorkflowTask.STATUS_FAILED
            workflow_task.message = f"IBMRegion '{region.name}' unavailable."
            db_session.commit()
            LOGGER.info(workflow_task.message)
            return

        listener: IBMListener = db_session.query(IBMListener).filter_by(**resource_data["listener"]).first()
        if not listener:
            workflow_task.status = WorkflowTask.STATUS_FAILED
            workflow_task.message = f"IBMListener `{listener_id_or_name}` not found."
            db_session.commit()
            LOGGER.info(workflow_task.message)
            return

        previous_resources = load_previous_associated_resources(task=workflow_task, session=db_session)
        update_id_or_name_references(
            cloud_id=cloud_id, resource_json=resource_data, resource_schema=IBMListenerPolicyInSchema,
            db_session=db_session, previous_resources=previous_resources
        )

        update_id_or_name_references(
            cloud_id=cloud_id, resource_json=resource_json, resource_schema=IBMListenerPolicyResourceSchema,
            db_session=db_session, previous_resources=previous_resources
        )

        for rule_resource_json in resource_json.get("rules", []):
            update_id_or_name_references(
                cloud_id=cloud_id, resource_json=rule_resource_json, previous_resources=previous_resources,
                resource_schema=IBMListenerPolicyRuleResourceSchema, db_session=db_session)

        if "target" in resource_json:
            if "id" in resource_json["target"]:
                pool_id = resource_json["target"]["id"]
                pool: IBMPool = db_session.query(IBMPool).filter_by(id=pool_id).first()
                if not pool:
                    workflow_task.status = WorkflowTask.STATUS_FAILED
                    workflow_task.message = f"IBMPool with `{pool_id}` not found."
                    db_session.commit()
                    LOGGER.info(workflow_task.message)
                    return

                resource_json["target"]["id"] = pool.resource_id
            elif "policy_redirect_url" in resource_json["target"]:
                resource_json.update(**resource_json["policy_redirect_url"])
                del resource_json["policy_redirect_url"]

            elif "https_redirect_url" in resource_json["target"]:
                resource_json.update(**resource_json["https_redirect_url"])
                del resource_json["https_redirect_url"]

        load_balancer_resource_id = listener.load_balancer.resource_id
        listener_resource_id = listener.resource_id

    try:
        client = LoadBalancersClient(cloud_id=cloud_id, region=region.name)
        resp_json = client.create_load_balancer_listener_policy(
            load_balancer_id=load_balancer_resource_id,
            listener_id=listener_resource_id, policy_json=resource_json
        )
    except ApiException as ex:
        with get_db_session() as db_session:
            workflow_task: WorkflowTask = db_session.get(WorkflowTask, workflow_task_id)
            if not workflow_task:
                return

            workflow_task.status = WorkflowTask.STATUS_FAILED
            workflow_task.message = f"Creation Failed. Reason: {str(ex.message)}"
            db_session.commit()

        LOGGER.info("Create Listener Policy failed with status code " + str(ex.code) + ": " + ex.message)
        return

    with get_db_session() as db_session:
        workflow_task: WorkflowTask = db_session.get(WorkflowTask, workflow_task_id)
        if not workflow_task:
            return

        policy_name = resp_json["name"]
        policy_status = resp_json["provisioning_status"]
        policy_resource_id = resp_json["id"]

        if policy_status in [LBCommonConsts.PROVISIONING_STATUS_ACTIVE,
                             LBCommonConsts.PROVISIONING_STATUS_CREATE_PENDING]:
            metadata = workflow_task.task_metadata.copy() if workflow_task.task_metadata else {}
            metadata["ibm_resource_id"] = policy_resource_id
            workflow_task.task_metadata = metadata

            workflow_task.status = WorkflowTask.STATUS_RUNNING_WAIT
            message = f"IBM Listener Policy '{policy_name}' for cloud {cloud_id} creation waiting."
        else:
            message = f"IBM Listener Policy '{policy_name}' for cloud {cloud_id} creation failed."
            workflow_task.message = message
            workflow_task.status = WorkflowTask.STATUS_FAILED
        db_session.commit()
    LOGGER.info(message)


@celery.task(name="create_wait_listener_policy", base=IBMWorkflowTasksBase)
def create_wait_listener_policy(workflow_task_id):
    """
    Wait for an IBM Listener Policy creation on IBM Cloud
    """
    with get_db_session() as db_session:
        workflow_task: WorkflowTask = db_session.get(WorkflowTask, workflow_task_id)
        if not workflow_task:
            return

        workflow_task.status = WorkflowTask.STATUS_RUNNING
        db_session.commit()

        resource_data = deepcopy(workflow_task.task_metadata["resource_data"])
        cloud_id = resource_data["ibm_cloud"]["id"]
        region_id = resource_data["region"]["id"]
        listener_id_or_name = resource_data["listener"].get('id') or resource_data["listener"].get("name")

        region: IBMRegion = db_session.get(IBMRegion, region_id)
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
            LOGGER.info(workflow_task.message)
            return

        listener: IBMListener = db_session.query(IBMListener).filter_by(**resource_data["listener"]).first()
        if not listener:
            workflow_task.status = WorkflowTask.STATUS_FAILED
            workflow_task.message = f"IBMListener `{listener_id_or_name}` not found."
            db_session.commit()
            LOGGER.info(workflow_task.message)
            return

        load_balancer_resource_id = listener.load_balancer.resource_id
        listener_resource_id = listener.resource_id
        policy_resource_id = workflow_task.task_metadata["ibm_resource_id"]

    try:
        client = LoadBalancersClient(cloud_id=cloud_id, region=region.name)
        policy_json = client.get_load_balancer_listener_policy(load_balancer_id=load_balancer_resource_id,
                                                               listener_id=listener_resource_id,
                                                               policy_id=policy_resource_id)
        policy_rules_json_list = []
        if "rules" in policy_json:
            policy_rules_json_list = client.list_load_balancer_listener_policy_rules(
                load_balancer_id=load_balancer_resource_id, listener_id=listener_resource_id,
                policy_id=policy_resource_id
            )

    except ApiException as ex:
        with get_db_session() as db_session:
            workflow_task = db_session.get(WorkflowTask, workflow_task_id)
            if not workflow_task:
                return

            workflow_task.status = WorkflowTask.STATUS_FAILED
            workflow_task.message = f"Creation Failed. Reason: {str(ex.message)}"
            db_session.commit()

        LOGGER.info("Create Load Balancer Listener Policy failed with status code " + str(ex.code) + ": " + ex.message)
        return

    with get_db_session() as db_session:
        workflow_task = db_session.get(WorkflowTask, workflow_task_id)
        if not workflow_task:
            return

        policy_name = policy_json["name"]
        policy_status = policy_json["provisioning_status"]

        if policy_status == LBCommonConsts.PROVISIONING_STATUS_ACTIVE:
            with db_session.no_autoflush:
                load_balancer = db_session.query(IBMLoadBalancer).filter_by(
                    resource_id=load_balancer_resource_id).first()
                if not load_balancer:
                    workflow_task.status = WorkflowTask.STATUS_FAILED
                    workflow_task.message = \
                        "Creation Successful but record update failed. The records will update next time discovery runs"
                    db_session.commit()
                    return

                listener = db_session.get(IBMListener, resource_data["listener"]["id"])
                if not listener:
                    workflow_task.status = WorkflowTask.STATUS_FAILED
                    workflow_task.message = \
                        "Creation Successful but record update failed. The records will update next time discovery runs"
                    db_session.commit()
                    return

                policy: IBMListenerPolicy = IBMListenerPolicy.from_ibm_json_body(
                    json_body=policy_json, db_session=db_session
                )
                policy.rules.extend(
                    [IBMListenerPolicyRule.from_ibm_json_body(json_) for json_ in policy_rules_json_list]
                )
                policy.listener = listener
                policy_id = policy.id
                db_session.commit()

            workflow_task.status = WorkflowTask.STATUS_SUCCESSFUL
            workflow_task.resource_id = policy_id
            message = f"IBM Listener Policy '{policy_name}' for cloud {cloud_id} creation successful"
        elif policy_status == LBCommonConsts.PROVISIONING_STATUS_CREATE_PENDING:
            workflow_task.status = WorkflowTask.STATUS_RUNNING_WAIT
            message = f"IBM Listener Policy '{policy_name}' for cloud {cloud_id} creation waiting"
        else:
            message = f"IBM Listener Policy '{policy_name}' for cloud {cloud_id} creation failed"
            workflow_task.message = message
            workflow_task.status = WorkflowTask.STATUS_FAILED
        db_session.commit()
    LOGGER.info(message)


@celery.task(name="delete_listener_policy", base=IBMWorkflowTasksBase)
def delete_listener_policy(workflow_task_id):
    """
    Delete an IBM Listener Policy
    :param workflow_task_id:
    :return:
    """

    with get_db_session() as db_session:
        workflow_task: WorkflowTask = db_session.get(WorkflowTask, workflow_task_id)
        if not workflow_task:
            return

        workflow_task.status = WorkflowTask.STATUS_RUNNING
        db_session.commit()

        policy: IBMListenerPolicy = db_session.get(IBMListenerPolicy, workflow_task.resource_id)
        if not policy:
            workflow_task.status = WorkflowTask.STATUS_FAILED
            workflow_task.message = f"IBMListenerPolicy '{workflow_task.resource_id}' not found"
            db_session.commit()
            LOGGER.info(workflow_task.message)
            return

        cloud_id = policy.listener.cloud_id
        region_name = policy.listener.region.name
        policy_resource_id = policy.resource_id
        listener_resource_id = policy.listener.resource_id
        load_balancer_resource_id = policy.listener.load_balancer.resource_id

    try:
        load_balancer_client = LoadBalancersClient(cloud_id, region=region_name)
        load_balancer_client.delete_load_balancer_listener_policy(
            load_balancer_id=load_balancer_resource_id,
            listener_id=listener_resource_id, policy_id=policy_resource_id
        )
        policy_json = load_balancer_client.get_load_balancer_listener_policy(
            load_balancer_id=load_balancer_resource_id, listener_id=listener_resource_id,
            policy_id=policy_resource_id
        )
    except ApiException as ex:
        with get_db_session() as db_session:
            workflow_task: WorkflowTask = db_session.get(WorkflowTask, workflow_task_id)
            if not workflow_task:
                return

            if ex.code == 404:
                policy: IBMListenerPolicy = db_session.get(IBMListenerPolicy, workflow_task.resource_id)
                if policy:
                    db_session.delete(policy)

                workflow_task.status = WorkflowTask.STATUS_SUCCESSFUL
                LOGGER.info(
                    f"IBM Listener Policy {workflow_task.resource_id} for cloud {cloud_id} deletion successful.")
                db_session.commit()
                return

            workflow_task.status = WorkflowTask.STATUS_FAILED
            message = f"Cannot delete the listener policy {workflow_task.resource_id} due to reason: {str(ex.message)}"
            workflow_task.message = message
            db_session.commit()
            LOGGER.info(message)
            return

    with get_db_session() as db_session:
        workflow_task: WorkflowTask = db_session.get(WorkflowTask, workflow_task_id)
        if not workflow_task:
            return

        if policy_json["provisioning_status"] in [LBCommonConsts.PROVISIONING_STATUS_DELETE_PENDING,
                                                  LBCommonConsts.PROVISIONING_STATUS_UPDATE_PENDING,
                                                  LBCommonConsts.PROVISIONING_STATUS_MAINTENANCE_PENDING]:
            workflow_task.status = WorkflowTask.STATUS_RUNNING_WAIT
            message = f"IBM Listener Policy {workflow_task.resource_id} for cloud {cloud_id} deletion waiting"
        else:
            message = f"IBM Listener Policy {workflow_task.resource_id} for cloud {cloud_id} deletion failed"
            workflow_task.message = message
            workflow_task.status = WorkflowTask.STATUS_FAILED

        db_session.commit()
    LOGGER.info(message)


@celery.task(name="delete_wait_listener_policy", base=IBMWorkflowTasksBase)
def delete_wait_listener_policy(workflow_task_id):
    """
    Wait for an IBM Listener Policy deletion on IBM Cloud.
    :param workflow_task_id:
    :return:
    """
    with get_db_session() as db_session:
        workflow_task: WorkflowTask = db_session.get(WorkflowTask, workflow_task_id)
        if not workflow_task:
            return

        workflow_task.status = WorkflowTask.STATUS_RUNNING
        db_session.commit()

        policy: IBMListenerPolicy = db_session.get(IBMListenerPolicy, workflow_task.resource_id)
        if not policy:
            workflow_task.status = WorkflowTask.STATUS_SUCCESSFUL
            db_session.commit()
            LOGGER.info(f"IBMListenerPolicy '{workflow_task.resource_id}' deletion successful.")
            return

        cloud_id = policy.listener.cloud_id
        region_name = policy.listener.region.name
        policy_resource_id = policy.resource_id
        listener_resource_id = policy.listener.resource_id
        load_balancer_resource_id = policy.listener.load_balancer.resource_id

    try:
        load_balancer_client = LoadBalancersClient(cloud_id, region=region_name)
        resp_json = load_balancer_client.get_load_balancer_listener_policy(
            load_balancer_id=load_balancer_resource_id, listener_id=listener_resource_id,
            policy_id=policy_resource_id
        )
    except ApiException as ex:
        with get_db_session() as db_session:
            workflow_task: WorkflowTask = db_session.get(WorkflowTask, workflow_task_id)
            if not workflow_task:
                return

            if ex.code == 404:
                policy: IBMListenerPolicy = db_session.get(IBMListenerPolicy, workflow_task.resource_id)
                if policy:
                    db_session.delete(policy)

                workflow_task.status = WorkflowTask.STATUS_SUCCESSFUL
                LOGGER.info(
                    f"IBM Listener Policy {workflow_task.resource_id} for cloud {cloud_id} deletion successful.")
                db_session.commit()
                return

            workflow_task.status = WorkflowTask.STATUS_FAILED
            message = f"Cannot delete the listener policy {workflow_task.resource_id} due to reason: {str(ex.message)}"
            workflow_task.message = message
            db_session.commit()
            LOGGER.info(message)
            return

    with get_db_session() as db_session:
        workflow_task: WorkflowTask = db_session.get(WorkflowTask, workflow_task_id)
        if not workflow_task:
            return

        if resp_json["provisioning_status"] in [LBCommonConsts.PROVISIONING_STATUS_DELETE_PENDING,
                                                LBCommonConsts.PROVISIONING_STATUS_UPDATE_PENDING,
                                                LBCommonConsts.PROVISIONING_STATUS_MAINTENANCE_PENDING]:
            workflow_task.status = WorkflowTask.STATUS_RUNNING_WAIT
            message = f"IBM Listener Policy {workflow_task.resource_id} for cloud {cloud_id} deletion waiting"
        else:
            message = f"IBM Listener Policy {workflow_task.resource_id} for cloud {cloud_id} deletion failed"
            workflow_task.message = message
            workflow_task.status = WorkflowTask.STATUS_FAILED

        db_session.commit()
    LOGGER.info(message)
