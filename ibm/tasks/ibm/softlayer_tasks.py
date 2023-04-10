import logging

from ibm import get_db_session
from ibm.common.clients.softlayer_clients import SoftlayerImageClient, SoftlayerInstanceClient
from ibm.common.clients.softlayer_clients.base_client import SoftLayerClient
from ibm.common.clients.softlayer_clients.exceptions import SLAuthError, SLExecuteError, SLRateLimitExceededError
from ibm.common.clients.softlayer_clients.instances.consts import INSTANCE_ONLY_ID_NAME_MASK, VIRTUAL_SERVER_MASK
from ibm.models import IBMRegion, SoftlayerCloud, WorkflowTask
from ibm.tasks.celery_app import celery_app as celery
from ibm.tasks.common.tasks_base import IBMWorkflowTasksBase
from ibm.web.softlayer.instances.utils import return_operating_system_objects

LOGGER = logging.getLogger(__name__)


@celery.task(name="validate_softlayer_account", base=IBMWorkflowTasksBase)
def validate_softlayer_account(workflow_task_id):
    """
    Create and Validate a Softlayer Account
    """
    with get_db_session() as db_session:
        workflow_task = db_session.query(WorkflowTask).filter_by(id=workflow_task_id).first()
        if not workflow_task:
            return

        softlayer_cloud_id = workflow_task.task_metadata["softlayer_cloud_id"]
        if not softlayer_cloud_id:
            workflow_task.status = WorkflowTask.STATUS_FAILED
            workflow_task.message = "'softlayer_cloud_id' is required for 'validate_softlayer_account'."
            db_session.commit()
            LOGGER.info(workflow_task.message)
            return

        workflow_task.status = WorkflowTask.STATUS_RUNNING
        db_session.commit()

        LOGGER.info(f"Authenticating Softlayer Cloud: {softlayer_cloud_id}")
        account = db_session.query(SoftlayerCloud).filter_by(id=softlayer_cloud_id).first()
        if not account:
            workflow_task.status = WorkflowTask.STATUS_FAILED
            workflow_task.message = f"SoftlayerCloud '{softlayer_cloud_id}' not found"
            db_session.commit()
            LOGGER.info(workflow_task.message)
            return

    try:
        client = SoftLayerClient(softlayer_cloud_id)
        client.authenticate_sl_account()
    except (SLAuthError, SLExecuteError, SLRateLimitExceededError) as ex:
        # TODO, Retry mechanisame for SLRateLimitExceededError
        with get_db_session() as db_session:
            workflow_task = db_session.query(WorkflowTask).filter_by(id=workflow_task_id).first()
            if not workflow_task:
                return

            account = db_session.query(SoftlayerCloud).filter_by(id=softlayer_cloud_id).first()
            if not account:
                workflow_task.status = WorkflowTask.STATUS_FAILED
                workflow_task.message = f"SoftlayerCloud '{softlayer_cloud_id}' not found"
                workflow_task.status = WorkflowTask.STATUS_FAILED
                db_session.commit()
                LOGGER.info(workflow_task.message)
                return

            account.status = SoftlayerCloud.STATUS_INVALID
            workflow_task.status = WorkflowTask.STATUS_SUCCESSFUL
            workflow_task.message = f"Softlayer Cloud {softlayer_cloud_id} Authentication Failed. Reason: {str(ex)}"
            db_session.commit()
            LOGGER.info(workflow_task.message)
        return

    with get_db_session() as db_session:
        workflow_task = db_session.query(WorkflowTask).filter_by(id=workflow_task_id).first()
        if not workflow_task:
            return

        account = db_session.query(SoftlayerCloud).filter_by(id=softlayer_cloud_id).first()
        if not account:
            workflow_task.status = WorkflowTask.STATUS_FAILED
            workflow_task.message = f"SoftlayerCloud '{softlayer_cloud_id}' not found"
            db_session.commit()
            LOGGER.info(workflow_task.message)
            return

        account.status = SoftlayerCloud.STATUS_VALID
        workflow_task.resource_id = account.id
        workflow_task.status = WorkflowTask.STATUS_SUCCESSFUL
        workflow_task.message = f"Softlayer Cloud {softlayer_cloud_id} Authenticated Successfully"
        db_session.commit()
        LOGGER.info(workflow_task.message)


@celery.task(name="sync_softlayer_images", base=IBMWorkflowTasksBase)
def sync_softlayer_images(workflow_task_id):
    """
    Sync Softlayer/Classic Images for account provided
    """
    with get_db_session() as db_session:
        workflow_task = db_session.query(WorkflowTask).filter_by(id=workflow_task_id).first()
        if not workflow_task:
            return

        workflow_task.status = WorkflowTask.STATUS_RUNNING
        db_session.commit()
        resource_data = workflow_task.task_metadata["resource_data"]
        account_id = resource_data["account_id"]
        region_id = resource_data["region_id"]
        account = db_session.query(SoftlayerCloud).filter_by(
            id=account_id, status=SoftlayerCloud.STATUS_VALID
        ).first()
        if not account:
            workflow_task.status = WorkflowTask.STATUS_FAILED
            workflow_task.message = f"SoftlayerCloud '{account_id}' not found"
            db_session.commit()
            LOGGER.info(workflow_task.message)
            return
        region = db_session.query(IBMRegion).filter_by(
            id=region_id, ibm_status=IBMRegion.IBM_STATUS_AVAILABLE
        ).first()
        if not region:
            workflow_task.status = WorkflowTask.STATUS_FAILED
            workflow_task.message = f"IBMRegion '{region_id}' not found"
            db_session.commit()
            LOGGER.info(workflow_task.message)
            return
    try:
        image_client = SoftlayerImageClient(cloud_id=account_id)
        images = image_client.list_private_images_name()
    except (SLAuthError, SLExecuteError, SLRateLimitExceededError) as ex:
        with get_db_session() as db_session:
            workflow_task = db_session.query(WorkflowTask).filter_by(id=workflow_task_id).first()
            if not workflow_task:
                return

            # TODO, Retry mechaniseme for SLRateLimitExceededError
            workflow_task.status = WorkflowTask.STATUS_FAILED
            workflow_task.message = f"Softlayer Image for Softlayer Cloud {account_id} Failed to sync. Reason: " \
                                    f"{str(ex)}"
            db_session.commit()
            LOGGER.info(workflow_task.message)
            return
    with get_db_session() as db_session:
        workflow_task = db_session.query(WorkflowTask).filter_by(id=workflow_task_id).first()
        if not workflow_task:
            return
        for img in images:
            img["operating_systems"] = return_operating_system_objects(
                image_name=img["image_name"], region_id=region_id, db_session=db_session)
        workflow_task.status = WorkflowTask.STATUS_SUCCESSFUL
        workflow_task.result = {"resource_json": images}
        db_session.commit()
        LOGGER.info(f"Softlayer Image for Softlayer Cloud {account_id} sync Successful ... ! ")


@celery.task(name="sync_softlayer_instances", base=IBMWorkflowTasksBase)
def sync_softlayer_instances(workflow_task_id):
    """
    Sync Softlayer/Classic Instances/VSIs for account provided
    """
    with get_db_session() as db_session:
        workflow_task = db_session.query(WorkflowTask).filter_by(id=workflow_task_id).first()
        if not workflow_task:
            return

        workflow_task.status = WorkflowTask.STATUS_RUNNING
        db_session.commit()
        resource_data = workflow_task.task_metadata["resource_data"]
        account_id = resource_data["account_id"]
        region_id = resource_data.get("region_id")
        account = db_session.query(SoftlayerCloud).filter_by(
            id=account_id, status=SoftlayerCloud.STATUS_VALID
        ).first()
        if not account:
            workflow_task.status = WorkflowTask.STATUS_FAILED
            workflow_task.message = f"SoftlayerCloud '{account_id}' not found"
            db_session.commit()
            LOGGER.info(workflow_task.message)
            return
        if region_id:
            region = db_session.query(IBMRegion).filter_by(
                id=region_id, ibm_status=IBMRegion.IBM_STATUS_AVAILABLE
            ).first()
            if not region:
                workflow_task.status = WorkflowTask.STATUS_FAILED
                workflow_task.message = f"IBMRegion '{region_id}' not found"
                db_session.commit()
                LOGGER.info(workflow_task.message)
                return
    try:
        client = SoftlayerInstanceClient(cloud_id=account_id)
        instances = client.list_instances(mask=INSTANCE_ONLY_ID_NAME_MASK)
    except (SLAuthError, SLExecuteError, SLRateLimitExceededError) as ex:
        # TODO, Retry mechanism for SLRateLimitExceededError
        with get_db_session() as db_session:
            workflow_task = db_session.query(WorkflowTask).filter_by(id=workflow_task_id).first()
            if not workflow_task:
                return

        workflow_task.status = WorkflowTask.STATUS_FAILED
        workflow_task.message = f"Softlayer Instances for Softlayer Cloud {account_id} Failed to sync. Reason: " \
                                f"{str(ex)}"
        db_session.commit()
        LOGGER.info(workflow_task.message)
        return
    with get_db_session() as db_session:
        workflow_task = db_session.query(WorkflowTask).filter_by(id=workflow_task_id).first()
        if not workflow_task:
            return
        workflow_task.status = WorkflowTask.STATUS_SUCCESSFUL
        workflow_task.result = {"resource_json": instances}
        db_session.commit()
        LOGGER.info(f"Softlayer Instances for Softlayer Cloud {account_id} synced Successful ... ! ")


@celery.task(name="sync_softlayer_instance", base=IBMWorkflowTasksBase)
def sync_softlayer_instance(workflow_task_id):
    """
    Sync Softlayer/Classic Instance for account's id and Instance id provided
    """
    with get_db_session() as db_session:
        workflow_task = db_session.query(WorkflowTask).filter_by(id=workflow_task_id).first()
        if not workflow_task:
            return

        workflow_task.status = WorkflowTask.STATUS_RUNNING
        db_session.commit()
        resource_data = workflow_task.task_metadata["resource_data"]
        account_id = resource_data["account_id"]
        region_id = resource_data.get("region_id")
        instance_id = resource_data["instance_id"]
        account = db_session.query(SoftlayerCloud).filter_by(
            id=account_id, status=SoftlayerCloud.STATUS_VALID
        ).first()
        if not account:
            workflow_task.status = WorkflowTask.STATUS_FAILED
            workflow_task.message = f"SoftlayerCloud '{account_id}' not found"
            db_session.commit()
            LOGGER.info(workflow_task.message)
            return
        if region_id:
            region = db_session.query(IBMRegion).filter_by(
                id=region_id, ibm_status=IBMRegion.IBM_STATUS_AVAILABLE
            ).first()
            if not region:
                workflow_task.status = WorkflowTask.STATUS_FAILED
                workflow_task.message = f"IBMRegion '{region_id}' not found"
                db_session.commit()
                LOGGER.info(workflow_task.message)
                return
    try:
        client = SoftlayerInstanceClient(cloud_id=account_id)
        instance = client.get_instance_by_id(instance_id, to_ibm=True, mask=VIRTUAL_SERVER_MASK)
    except (SLAuthError, SLExecuteError, SLRateLimitExceededError) as ex:
        # TODO, Retry mechaniseme for SLRateLimitExceededError
        with get_db_session() as db_session:
            workflow_task = db_session.query(WorkflowTask).filter_by(id=workflow_task_id).first()
            if not workflow_task:
                return

        workflow_task.status = WorkflowTask.STATUS_FAILED
        workflow_task.message = f"Softlayer Instance {instance_id} for Softlayer Cloud {account_id} Failed to sync." \
                                f" Reason: {str(ex)}"
        db_session.commit()
        LOGGER.info(workflow_task.message)
        return
    with get_db_session() as db_session:
        workflow_task = db_session.query(WorkflowTask).filter_by(id=workflow_task_id).first()
        if not workflow_task:
            return
        if region_id:
            instance["operating_systems"] = return_operating_system_objects(
                image_name=instance["original_image"]["name"], region_id=region_id,
                db_session=db_session
            )
        workflow_task.status = WorkflowTask.STATUS_SUCCESSFUL
        workflow_task.result = {"resource_json": instance}
        db_session.commit()
        LOGGER.info(f"Softlayer Instance {instance_id} for Softlayer Cloud {account_id} synced Successful ... ! ")
