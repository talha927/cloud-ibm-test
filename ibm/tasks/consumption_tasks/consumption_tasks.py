import logging

from consumption_client import Consumption
from consumption_client.rest import ApiException
from subscription_client import SubscriptionApi
from subscription_client.rest import ApiException as subException

from ibm import get_db_session
from ibm.common.consts import ONPREM
from ibm.common.utils import init_consumption_client, init_subscription_client
from ibm.models import DisasterRecoveryBackup, IBMCloud, IBMIdleResource, IBMInstance, IBMVpcNetwork, WorkflowTask
from ibm.tasks.celery_app import celery_app as celery
from ibm.tasks.common.tasks_base import IBMWorkflowTasksBase
from ibm.tasks.draas_tasks.utils import get_consumption_resource_from_db

LOGGER = logging.getLogger(__name__)


@celery.task(name="add_cost_consumption", base=IBMWorkflowTasksBase, queue='consumption_queue')
def add_cost_consumption_task(workflow_task_id):
    """Add Consumption data related to cost to Consumption Microservice"""
    with get_db_session() as db_session:
        workflow_task = db_session.query(WorkflowTask).filter_by(id=workflow_task_id).first()
        if not workflow_task:
            return

        workflow_task.status = WorkflowTask.STATUS_RUNNING
        db_session.commit()
        task_metadata = workflow_task.task_metadata
        cloud_id = task_metadata["cloud_id"]

        cloud = db_session.query(IBMCloud).filter_by(id=cloud_id).first()
        if not cloud:
            workflow_task.status = WorkflowTask.STATUS_FAILED
            workflow_task.message = f"IBM Cloud {task_metadata['cloud_id']} not found in DB"
            db_session.commit()
            LOGGER.info(workflow_task.message)
            return

        project_id = cloud.project_id
        resource_id = cloud.id
        cloud_settings = cloud.settings
        cost_opt_enabled = cloud.ENABLE if cloud_settings.cost_optimization_enabled else cloud.DISABLE
        metadata = dict()
        metadata['nodes'] = 0
        metadata['idle'] = 0

    try:
        subscription_client = SubscriptionApi(init_subscription_client())
        subscriptions = subscription_client.get_subscriptions(project_id=project_id)

    except subException as ex:
        with get_db_session() as db_session:
            workflow_task = db_session.query(WorkflowTask).filter_by(id=workflow_task_id).first()
            if not workflow_task:
                return

            workflow_task.message = f"Exception when calling SubscriptionApi->get_subscription: {ex.status}:{ex.reason}"
            workflow_task.status = WorkflowTask.STATUS_FAILED
            db_session.commit()
            LOGGER.info(workflow_task.message)
            LOGGER.info(ex)
            return

    if not subscriptions:
        with get_db_session() as db_session:
            workflow_task = db_session.query(WorkflowTask).filter_by(id=workflow_task_id).first()
            if not workflow_task:
                return

            workflow_task.message = f"No subscription found for project ID {project_id}"
            workflow_task.status = WorkflowTask.STATUS_FAILED
            db_session.commit()
            LOGGER.info(workflow_task.message)
            return

    LOGGER.info(f"Subscription successfully fetched with service ID : {subscriptions[0].service_id}")
    service_id = subscriptions[0].service_id

    try:
        client = init_consumption_client()
        consumption = Consumption(
            project_id=project_id, cloud_id=resource_id, cloud_type="IBM", service_function=cost_opt_enabled,
            service_id=service_id, resource_id=resource_id, resource_type="Global",
            service_type="Manage Account - Cost Optimization",
            metadata=metadata)

        client.add_consumption(consumption=consumption, x_user_email=task_metadata.get('email'))

    except ApiException as ex:
        with get_db_session() as db_session:
            workflow_task = db_session.query(WorkflowTask).filter_by(id=workflow_task_id).first()
            if not workflow_task:
                return

            workflow_task.message = f"Exception when calling ConsumptionApi->add_consumption: {ex.status}:{ex.reason}"
            workflow_task.status = WorkflowTask.STATUS_FAILED
            db_session.commit()
            LOGGER.info(workflow_task.message)
            LOGGER.info(ex)
            return

    with get_db_session() as db_session:
        workflow_task = db_session.query(WorkflowTask).filter_by(id=workflow_task_id).first()
        if not workflow_task:
            return

        workflow_task.status = WorkflowTask.STATUS_SUCCESSFUL
        db_session.commit()
        LOGGER.info(f"Cost Consumption Data added successfully for cloud with ID {task_metadata['cloud_id']}")


@celery.task(name="update_cost_consumption_stats_task", queue='consumption_queue')
def update_cost_consumption_stats_task():
    """
    This task sends the current count of idle and nodes to consumption.
    """
    with get_db_session() as db_session:

        for cloud in db_session.query(IBMCloud).filter_by(deleted=False, status='VALID').all():
            cloud_settings = cloud.settings
            if cloud_settings and not cloud_settings.cost_optimization_enabled:
                continue
            metadata = dict()
            project_id = cloud.project_id
            email = cloud.metadata_.get("email")
            resource_id = cloud.id

            LOGGER.debug(f"Sending stats to consumption for cloud {cloud.id}")

            cost_optimization_enable = cloud.ENABLE if cloud_settings.cost_optimization_enabled else cloud.DISABLE
            idle_resources_resource_ids = db_session.query(IBMIdleResource.db_resource_id).filter_by(
                cloud_id=cloud.id).all()

            active_instance_ids = db_session.query(IBMInstance.id).filter_by(
                cloud_id=cloud.id, status=IBMInstance.STATUS_RUNNING).filter(
                IBMInstance.id.not_in(idle_resources_resource_ids)).all()
            metadata['idle'] = len(idle_resources_resource_ids)
            metadata['nodes'] = len(active_instance_ids)

            try:
                subscription_client = SubscriptionApi(init_subscription_client())
                subscriptions = subscription_client.get_subscriptions(project_id=project_id)

            except subException as ex:
                LOGGER.info(ex)
                return

            if not subscriptions:
                LOGGER.info(f"No subscription found for project ID {project_id}")
                return

            LOGGER.info(f"Subscription successfully fetched with service ID : {subscriptions[0].service_id}")

            service_id = subscriptions[0].service_id

            try:
                client = init_consumption_client()
                consumption = Consumption(
                    project_id=project_id, cloud_id=resource_id, cloud_type="IBM",
                    service_function=cost_optimization_enable, service_id=service_id, resource_id=resource_id,
                    resource_type="Global", service_type="Manage Account - Cost Optimization", metadata=metadata)
                client.add_consumption(consumption=consumption, x_user_email=email)

            except ApiException as ex:
                LOGGER.info(ex)
                return

            LOGGER.info(f"Cost Consumption Data added successfully for cloud with ID {cloud.id}")


@celery.task(name="add_backup_consumption", base=IBMWorkflowTasksBase, queue='consumption_queue')
def add_backup_consumption_task(workflow_task_id):
    """Add Consumption data related to back-up to Consumption Microservice"""

    with get_db_session() as db_session:
        workflow_task = db_session.query(WorkflowTask).filter_by(id=workflow_task_id).first()
        if not workflow_task:
            return

        workflow_task.status = WorkflowTask.STATUS_RUNNING
        db_session.commit()
        task_metadata = workflow_task.task_metadata
        backup_id = task_metadata["backup_id"]

        LOGGER.debug("task_metadata = ", task_metadata)
        backup = db_session.query(DisasterRecoveryBackup).filter_by(id=backup_id).first()
        if not backup:
            workflow_task.status = WorkflowTask.STATUS_FAILED
            workflow_task.message = f"DisasterRecoveryBackup {task_metadata['backup_id']} not found in DB"
            db_session.commit()
            LOGGER.info(workflow_task.message)
            return

        blueprint = backup.disaster_recovery_resource_blueprint
        cloud_id = blueprint.cloud_id
        cloud = blueprint.ibm_cloud

        project_id = cloud.project_id
        user_id = cloud.user_id
        resource_type = blueprint.resource_type

        resource = get_consumption_resource_from_db(session=db_session, cloud_id=cloud_id,
                                                    resource_type=blueprint.resource_type,
                                                    resource_id=blueprint.resource_id)
        if not resource:
            msg = f"IBM Resource {blueprint.resource_type} with ID {blueprint.resource_id} not found in DB"
            workflow_task.message = msg
            workflow_task.status = WorkflowTask.STATUS_FAILED
            db_session.commit()
            return

        if blueprint.resource_type == IBMVpcNetwork.__name__:
            service_type = "DRaaS - VPC"
            metadata = resource.get_subresources_count()

        elif blueprint.resource_type == "IKS":
            nodes = 0
            workers = resource.worker_pools.all()
            for worker in workers:
                nodes += int(worker.worker_count)
            service_type = "DRaaS - K8s/OpenShift"
            metadata = {'nodes': nodes}

        elif blueprint.resource_type == ONPREM:
            nodes = resource.worker_count
            service_type = "DRaaS - K8s/OpenShift"
            metadata = {'nodes': nodes}

        LOGGER.debug(f"{service_type} metadata = {metadata}")
        LOGGER.debug(f"project id = {project_id}")

    try:
        subscription_client = SubscriptionApi(init_subscription_client())
        subscriptions = subscription_client.get_subscriptions(project_id=project_id)

    except subException as ex:
        with get_db_session() as db_session:
            workflow_task = db_session.query(WorkflowTask).filter_by(id=workflow_task_id).first()
            if not workflow_task:
                return

            workflow_task.message = f"Exception when calling SubscriptionnApi->get_consumption: {ex.status}:{ex.reason}"
            workflow_task.status = WorkflowTask.STATUS_FAILED
            db_session.commit()
            LOGGER.info(workflow_task.message)
            LOGGER.info(ex)
            return

    if not subscriptions:
        with get_db_session() as db_session:
            workflow_task = db_session.query(WorkflowTask).filter_by(id=workflow_task_id).first()
            if not workflow_task:
                return

            workflow_task.message = f"No subscription found for project ID {project_id}"
            workflow_task.status = WorkflowTask.STATUS_FAILED
            db_session.commit()
            LOGGER.info(workflow_task.message)
            return

    LOGGER.debug(f"subscriptions = {subscriptions}")
    LOGGER.info(f"Subscription successfully fetched with service ID : {subscriptions[0].service_id}")
    service_id = subscriptions[0].service_id

    try:
        client = init_consumption_client()
        consumption = Consumption(
            project_id=project_id, cloud_id=cloud_id, cloud_type="IBM", user_id=user_id, service_function="BACKUP",
            service_id=service_id, resource_id=blueprint.resource_id, resource_type=resource_type,
            service_type=service_type, metadata=metadata)

        client.add_consumption(consumption=consumption)

    except ApiException as ex:
        with get_db_session() as db_session:
            workflow_task = db_session.query(WorkflowTask).filter_by(id=workflow_task_id).first()
            if not workflow_task:
                return

            workflow_task.message = f"Exception when calling ConsumptionApi->add_consumption: {ex.status}:{ex.reason}"
            workflow_task.status = WorkflowTask.STATUS_FAILED
            db_session.commit()
            LOGGER.info(workflow_task.message)
            return

    with get_db_session() as db_session:
        workflow_task = db_session.query(WorkflowTask).filter_by(id=workflow_task_id).first()
        if not workflow_task:
            return

        workflow_task.status = WorkflowTask.STATUS_SUCCESSFUL
        db_session.commit()
        LOGGER.info(f"Consumption Data added successfully for BACKUP with ID {task_metadata['backup_id']}")
