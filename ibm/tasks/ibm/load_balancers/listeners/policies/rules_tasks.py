import logging
from copy import deepcopy
from ibm_cloud_sdk_core import ApiException

from ibm import get_db_session
from ibm.common.clients.ibm_clients import LoadBalancersClient
from ibm.common.utils import update_id_or_name_references
from ibm.models import IBMListenerPolicy, IBMListenerPolicyRule, IBMRegion, WorkflowTask
from ibm.models.ibm.load_balancer_models import LBCommonConsts
from ibm.tasks.celery_app import celery_app as celery
from ibm.tasks.common.tasks_base import IBMWorkflowTasksBase
from ibm.tasks.ibm.task_utils import load_previous_associated_resources
from ibm.web.ibm.load_balancers.listeners.policies.rules.schemas import IBMListenerPolicyRuleInSchema, \
    IBMListenerPolicyRuleResourceSchema

LOGGER = logging.getLogger(__name__)


@celery.task(name="create_listener_policy_rule", base=IBMWorkflowTasksBase)
def create_listener_policy_rule(workflow_task_id):
    """
    Create an IBM Listener Policy Rule on IBM Cloud
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
        policy_id_or_name = resource_data["policy"].get('id') or resource_data["policy"].get("name")

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

        policy: IBMListenerPolicy = db_session.query(IBMListenerPolicy).filter_by(**resource_data["policy"]).first()
        if not policy:
            workflow_task.status = WorkflowTask.STATUS_FAILED
            workflow_task.message = f"IBMListenerPolicy `{policy_id_or_name}` not found."
            db_session.commit()
            LOGGER.info(workflow_task.message)
            return

        previous_resources = load_previous_associated_resources(task=workflow_task, session=db_session)
        update_id_or_name_references(
            cloud_id=cloud_id, resource_json=resource_data, resource_schema=IBMListenerPolicyRuleInSchema,
            db_session=db_session, previous_resources=previous_resources
        )

        update_id_or_name_references(
            cloud_id=cloud_id, resource_json=resource_json, resource_schema=IBMListenerPolicyRuleResourceSchema,
            db_session=db_session, previous_resources=previous_resources
        )

        region_name = region.name
        policy_resource_id = policy.resource_id
        listener_resource_id = policy.listener.resource_id
        load_balancer_resource_id = policy.listener.load_balancer.resource_id

    try:
        client = LoadBalancersClient(cloud_id=cloud_id, region=region_name)
        rule_json = client.create_load_balancer_listener_policy_rule(
            load_balancer_id=load_balancer_resource_id,
            listener_id=listener_resource_id, policy_id=policy_resource_id, rule_json=resource_json
        )
    except ApiException as ex:
        with get_db_session() as db_session:
            workflow_task: WorkflowTask = db_session.get(WorkflowTask, workflow_task_id)
            if not workflow_task:
                return

            workflow_task.status = WorkflowTask.STATUS_FAILED
            workflow_task.message = f"Creation Failed. Reason: {str(ex.message)}"
            db_session.commit()

        LOGGER.info("Create Listener Policy Rule failed with status code " + str(ex.code) + ": " + ex.message)
        return

    with get_db_session() as db_session:
        workflow_task: WorkflowTask = db_session.get(WorkflowTask, workflow_task_id)
        if not workflow_task:
            return

        rule_name = f"{rule_json['condition']}-{rule_json['type']}-{rule_json['value']}"
        if rule_json["provisioning_status"] in [LBCommonConsts.PROVISIONING_STATUS_ACTIVE,
                                                LBCommonConsts.PROVISIONING_STATUS_CREATE_PENDING]:
            metadata = deepcopy(workflow_task.task_metadata)
            metadata["ibm_resource_id"] = rule_json["id"]
            workflow_task.task_metadata = metadata

            workflow_task.status = WorkflowTask.STATUS_RUNNING_WAIT
            message = f"IBM Listener Policy Rule '{rule_name}' for cloud {cloud_id} creation waiting."
        else:
            message = f"IBM Listener Policy Rule '{rule_name}' for cloud {cloud_id} creation failed."
            workflow_task.message = message
            workflow_task.status = WorkflowTask.STATUS_FAILED
        db_session.commit()
    LOGGER.info(message)


@celery.task(name="create_wait_listener_policy_rule", base=IBMWorkflowTasksBase)
def create_wait_listener_policy_rule(workflow_task_id):
    """
    Wait for an IBM Listener Policy Rule creation on IBM Cloud
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
        policy_id_or_name = resource_data["policy"].get('id') or resource_data["policy"].get("name")

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

        policy: IBMListenerPolicy = db_session.query(IBMListenerPolicy).filter_by(**resource_data["policy"]).first()
        if not policy:
            workflow_task.status = WorkflowTask.STATUS_FAILED
            workflow_task.message = f"IBMListenerPolicy `{policy_id_or_name}` not found."
            db_session.commit()
            LOGGER.info(workflow_task.message)
            return

        region_name = region.name
        rule_resource_id = workflow_task.task_metadata["ibm_resource_id"]
        policy_resource_id = policy.resource_id
        listener_resource_id = policy.listener.resource_id
        load_balancer_resource_id = policy.listener.load_balancer.resource_id

    try:
        client = LoadBalancersClient(cloud_id=cloud_id, region=region_name)
        rule_json = client.get_load_balancer_listener_policy_rule(
            load_balancer_id=load_balancer_resource_id, listener_id=listener_resource_id,
            policy_id=policy_resource_id, rule_id=rule_resource_id)

    except ApiException as ex:
        with get_db_session() as db_session:
            workflow_task = db_session.get(WorkflowTask, workflow_task_id)
            if not workflow_task:
                return

            workflow_task.status = WorkflowTask.STATUS_FAILED
            workflow_task.message = f"Creation Failed. Reason: {str(ex.message)}"
            db_session.commit()

        LOGGER.info("Create Wait Listener Policy Rule failed with status code " + str(ex.code) + ": " + ex.message)
        return

    with get_db_session() as db_session:
        workflow_task = db_session.get(WorkflowTask, workflow_task_id)
        if not workflow_task:
            return

        policy: IBMListenerPolicy = db_session.query(IBMListenerPolicy).filter_by(**resource_data["policy"]).first()
        if not policy:
            workflow_task.status = WorkflowTask.STATUS_FAILED
            workflow_task.message = f"IBMListenerPolicy `{policy_id_or_name}` not found."
            db_session.commit()
            LOGGER.info(workflow_task.message)
            return

        rule_name = f"{rule_json['condition']}-{rule_json['type']}-{rule_json['value']}"
        rule_status = rule_json["provisioning_status"]
        if rule_status == LBCommonConsts.PROVISIONING_STATUS_ACTIVE:
            with db_session.no_autoflush:
                rule = IBMListenerPolicyRule.from_ibm_json_body(json_body=rule_json)
                rule.lb_listener_policy = policy
                rule_id = rule.id
                db_session.commit()

            workflow_task.status = WorkflowTask.STATUS_SUCCESSFUL
            workflow_task.resource_id = rule_id
            message = f"IBM Listener Policy Rule '{rule_name}' for cloud {cloud_id} creation successful"
        elif rule_status == LBCommonConsts.PROVISIONING_STATUS_CREATE_PENDING:
            workflow_task.status = WorkflowTask.STATUS_RUNNING_WAIT
            message = f"IBM Listener Policy Rule '{rule_name}' for cloud {cloud_id} creation waiting"
        else:
            message = f"IBM Listener Policy Rule '{rule_name}' for cloud {cloud_id} creation failed"
            workflow_task.message = message
            workflow_task.status = WorkflowTask.STATUS_FAILED
        db_session.commit()
    LOGGER.info(message)


@celery.task(name="delete_listener_policy_rule", base=IBMWorkflowTasksBase)
def delete_listener_policy_rule(workflow_task_id):
    """
    Delete an IBM Listener Policy Rule
    :param workflow_task_id:
    :return:
    """

    with get_db_session() as db_session:
        workflow_task: WorkflowTask = db_session.get(WorkflowTask, workflow_task_id)
        if not workflow_task:
            return

        workflow_task.status = WorkflowTask.STATUS_RUNNING
        db_session.commit()

        policy_rule: IBMListenerPolicyRule = db_session.get(IBMListenerPolicyRule, workflow_task.resource_id)
        if not policy_rule:
            workflow_task.status = WorkflowTask.STATUS_FAILED
            workflow_task.message = f"IBMListenerPolicyRule '{workflow_task.resource_id}' not found"
            db_session.commit()
            LOGGER.info(workflow_task.message)
            return

        policy = policy_rule.lb_listener_policy
        cloud_id = policy.listener.cloud_id
        region_name = policy.listener.region.name
        rule_resource_id = policy_rule.resource_id
        policy_resource_id = policy.resource_id
        listener_resource_id = policy.listener.resource_id
        load_balancer_resource_id = policy.listener.load_balancer.resource_id

    try:
        load_balancer_client = LoadBalancersClient(cloud_id, region=region_name)
        load_balancer_client.delete_load_balancer_listener_policy_rule(load_balancer_id=load_balancer_resource_id,
                                                                       listener_id=listener_resource_id,
                                                                       policy_id=policy_resource_id,
                                                                       rule_id=rule_resource_id)
        rule_json = load_balancer_client.get_load_balancer_listener_policy_rule(
            load_balancer_id=load_balancer_resource_id, listener_id=listener_resource_id,
            policy_id=policy_resource_id, rule_id=rule_resource_id)

    except ApiException as ex:
        with get_db_session() as db_session:
            workflow_task: WorkflowTask = db_session.get(WorkflowTask, workflow_task_id)
            if not workflow_task:
                return

            if ex.code == 404:
                policy_rule: IBMListenerPolicyRule = db_session.get(IBMListenerPolicyRule, workflow_task.resource_id)
                if policy_rule:
                    db_session.delete(policy_rule)

                workflow_task.status = WorkflowTask.STATUS_SUCCESSFUL
                LOGGER.info(
                    f"IBM Listener Policy Rule {workflow_task.resource_id} for cloud {cloud_id} deletion successful.")
                db_session.commit()
                return

            workflow_task.status = WorkflowTask.STATUS_FAILED
            message = f"Cannot delete the listener policy_rule rule {workflow_task.resource_id} due to reason: " \
                      f"{str(ex.message)}"
            workflow_task.message = message
            db_session.commit()
            LOGGER.info(message)
            return

    with get_db_session() as db_session:
        workflow_task: WorkflowTask = db_session.get(WorkflowTask, workflow_task_id)
        if not workflow_task:
            return

        if rule_json["provisioning_status"] in [LBCommonConsts.PROVISIONING_STATUS_DELETE_PENDING,
                                                LBCommonConsts.PROVISIONING_STATUS_UPDATE_PENDING,
                                                LBCommonConsts.PROVISIONING_STATUS_MAINTENANCE_PENDING]:
            workflow_task.status = WorkflowTask.STATUS_RUNNING_WAIT
            message = f"IBM Listener Policy Rule {workflow_task.resource_id} for cloud {cloud_id} deletion waiting"
        else:
            message = f"IBM Listener Policy Rule {workflow_task.resource_id} for cloud {cloud_id} deletion failed"
            workflow_task.message = message
            workflow_task.status = WorkflowTask.STATUS_FAILED

        db_session.commit()
    LOGGER.info(message)


@celery.task(name="delete_wait_listener_policy_rule", base=IBMWorkflowTasksBase)
def delete_wait_listener_policy_rule(workflow_task_id):
    """
    Wait for an IBM Listener Policy Rule deletion on IBM Cloud.
    :param workflow_task_id:
    :return:
    """
    with get_db_session() as db_session:
        workflow_task: WorkflowTask = db_session.get(WorkflowTask, workflow_task_id)
        if not workflow_task:
            return

        workflow_task.status = WorkflowTask.STATUS_RUNNING
        db_session.commit()

        policy_rule: IBMListenerPolicyRule = db_session.get(IBMListenerPolicyRule, workflow_task.resource_id)
        if not policy_rule:
            workflow_task.status = WorkflowTask.STATUS_SUCCESSFUL
            db_session.commit()
            LOGGER.info(f"IBMListenerPolicyRule '{workflow_task.resource_id}' deletion successful.")
            return

        policy_rule = policy_rule.lb_listener_policy
        cloud_id = policy_rule.listener.cloud_id
        region_name = policy_rule.listener.region.name
        rule_resource_id = policy_rule.resource_id
        policy_resource_id = policy_rule.resource_id
        listener_resource_id = policy_rule.listener.resource_id
        load_balancer_resource_id = policy_rule.listener.load_balancer.resource_id

    try:
        load_balancer_client = LoadBalancersClient(cloud_id, region=region_name)
        resp_json = load_balancer_client.get_load_balancer_listener_policy_rule(
            load_balancer_id=load_balancer_resource_id, listener_id=listener_resource_id,
            policy_id=policy_resource_id, rule_id=rule_resource_id
        )

    except ApiException as ex:
        with get_db_session() as db_session:
            workflow_task: WorkflowTask = db_session.get(WorkflowTask, workflow_task_id)
            if not workflow_task:
                return

            if ex.code == 404:
                policy_rule: IBMListenerPolicyRule = db_session.get(IBMListenerPolicyRule, workflow_task.resource_id)
                if policy_rule:
                    db_session.delete(policy_rule)

                workflow_task.status = WorkflowTask.STATUS_SUCCESSFUL
                LOGGER.info(
                    f"IBM Listener Policy Rule {workflow_task.resource_id} for cloud {cloud_id} deletion successful.")
                db_session.commit()
                return

            workflow_task.status = WorkflowTask.STATUS_FAILED
            message = f"Cannot delete the listener policy_rule rule {workflow_task.resource_id} due to reason: " \
                      f"{str(ex.message)}"
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
            message = f"IBM Listener Policy Rule {workflow_task.resource_id} for cloud {cloud_id} deletion waiting"
        else:
            message = f"IBM Listener Policy Rule {workflow_task.resource_id} for cloud {cloud_id} deletion failed"
            workflow_task.message = message
            workflow_task.status = WorkflowTask.STATUS_FAILED

        db_session.commit()
    LOGGER.info(message)
