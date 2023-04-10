from datetime import datetime

from celery_singleton import Singleton
from ibm_cloud_sdk_core import ApiException
from ibm_cloud_sdk_core.authenticators import IAMAuthenticator
from ibm_platform_services import IamIdentityV1
from sdcclient import SdMonitorClient
from sqlalchemy import inspect

from config import IBMSyncConfigs
from ibm import get_db_session, LOGGER, mangos_ibm as mangos
from ibm.common.clients.ibm_clients.cloud_account_details.account_details import CloudAccountDetailsClient
from ibm.common.clients.ibm_clients.exceptions import IBMAuthError, IBMConnectError, IBMExecuteError, \
    IBMInvalidRequestError
from ibm.models import IBMCloud, IBMMonitoringToken, IBMRegion, IBMResourceGroup, IBMZone, WorkflowTask
from ibm.tasks.celery_app import celery_app as celery
from ibm.tasks.common.tasks_base import IBMWorkflowTasksBase
from ibm.tasks.ibm.consts import MONITORING_INSTANCE_URL
from ibm.tasks.ibm.task_utils import get_relative_time_seconds
from mangos_grpc_client.ibm.exceptions import MangosGRPCError


@celery.task(name="validate_update_cloud_api_key", base=IBMWorkflowTasksBase)
def validate_update_cloud_api_key(workflow_task_id):
    """
    Get ID of the API Key provided
    """
    with get_db_session() as db_session:
        workflow_task = db_session.query(WorkflowTask).filter_by(id=workflow_task_id).first()
        if not workflow_task:
            return

        cloud_id = workflow_task.task_metadata["cloud_id"]
        if not cloud_id:
            workflow_task.status = WorkflowTask.STATUS_FAILED
            workflow_task.message = "'cloud_id' is required for 'validate_update_cloud_api_key'. Please provide."
            db_session.commit()
            LOGGER.error(workflow_task.message)
            return

        workflow_task.status = WorkflowTask.STATUS_RUNNING
        db_session.commit()

        ibm_cloud = db_session.query(IBMCloud).filter_by(id=cloud_id).first()
        if not ibm_cloud:
            workflow_task.status = WorkflowTask.STATUS_FAILED
            workflow_task.message = f"IBMCloud '{workflow_task.resource_id}' not found"
            db_session.commit()
            LOGGER.error(workflow_task.message)
            return

        data = workflow_task.task_metadata.get("data", {})
        if data and "api_key" in data:
            api_key = data["api_key"]
        else:
            api_key = ibm_cloud.api_key

    try:
        authenticator = IAMAuthenticator(api_key)
        service_client = IamIdentityV1(authenticator=authenticator)
        api_key_id = service_client.get_api_keys_details(iam_api_key=api_key).get_result()["id"]
    except ApiException as ex:
        with get_db_session() as db_session:
            workflow_task = db_session.query(WorkflowTask).filter_by(id=workflow_task_id).first()
            if not workflow_task:
                return

            workflow_task.status = WorkflowTask.STATUS_FAILED
            workflow_task.message = "Method failed with status code " + str(ex.code) + ": " + ex.message
            ibm_cloud = db_session.query(IBMCloud).filter_by(id=cloud_id).first()
            if ibm_cloud:
                ibm_cloud.status = IBMCloud.STATUS_INVALID
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

        ibm_cloud.api_key_id = api_key_id
        ibm_cloud.status = IBMCloud.STATUS_VALID
        workflow_task.resource_id = ibm_cloud.id
        workflow_task.status = WorkflowTask.STATUS_SUCCESSFUL
        db_session.commit()
        LOGGER.success(f"API Key ID for IBM Cloud {ibm_cloud.id} fetched successfully")


@celery.task(name="validate_ibm_monitoring_tokens", base=IBMWorkflowTasksBase)
def validate_ibm_monitoring_tokens(workflow_task_id):
    """
    Validate Ibm monitoring Instance tokens.
    """
    with get_db_session() as db_session:
        workflow_task = db_session.query(WorkflowTask).filter_by(id=workflow_task_id).first()
        if not workflow_task:
            return

        workflow_task.status = WorkflowTask.STATUS_RUNNING
        db_session.commit()

        task_metadata = workflow_task.task_metadata
        region_name = task_metadata["region"]
        token = task_metadata["token"]

    url = MONITORING_INSTANCE_URL.format(region_name=region_name)
    monitoring_client = SdMonitorClient(sdc_url=url, token=token)
    start_time = get_relative_time_seconds(days_count=1)
    ok, res = monitoring_client.get_data([{"id": "ibm_is_instance_memory_usage_percentage"}], start_time)
    if not ok:
        with get_db_session() as db_session:
            workflow_task = db_session.query(WorkflowTask).filter_by(id=workflow_task_id).first()
            if not workflow_task:
                return

            workflow_task.status = WorkflowTask.STATUS_FAILED
            workflow_task.message = str(res)
            db_session.commit()
            LOGGER.error(workflow_task.message)
            return

    with get_db_session() as db_session:
        workflow_task = db_session.query(WorkflowTask).filter_by(id=workflow_task_id).first()
        if not workflow_task:
            return

        workflow_task.status = WorkflowTask.STATUS_SUCCESSFUL
        db_session.commit()

    LOGGER.success(f"Monitoring token for region {region_name} validated successfully")


@celery.task(name="add_ibm_monitoring_tokens", base=IBMWorkflowTasksBase)
def add_ibm_monitoring_tokens(workflow_task_id):
    """
    Add Ibm monitoring Instance tokens.
    """
    with get_db_session() as db_session:
        workflow_task = db_session.query(WorkflowTask).filter_by(id=workflow_task_id).first()
        if not workflow_task:
            return

        task_metadata = workflow_task.task_metadata
        region_id = task_metadata.get("region_id")
        token = task_metadata.get("token")
        if not task_metadata.get("region_id"):
            workflow_task.status = WorkflowTask.STATUS_FAILED
            workflow_task.message = "'region_id' is required for 'validate_ibm_monitoring_tokens'. Please provide."
            db_session.commit()
            LOGGER.error(workflow_task.message)
            return

        workflow_task.status = WorkflowTask.STATUS_RUNNING
        db_session.commit()

        ibm_region = db_session.query(IBMRegion).filter_by(id=region_id).first()
        if not ibm_region:
            workflow_task.status = WorkflowTask.STATUS_FAILED
            workflow_task.message = f"IBMRegion '{region_id}' not found"
            db_session.commit()
            LOGGER.error(workflow_task.message)
            return

        region_name = ibm_region.name
        cloud_id = ibm_region.ibm_cloud.id

    url = MONITORING_INSTANCE_URL.format(region_name=region_name)
    monitoring_client = SdMonitorClient(sdc_url=url, token=token)
    start_time = get_relative_time_seconds(days_count=1)
    ok, res = monitoring_client.get_data([{"id": "ibm_is_instance_memory_usage_percentage"}], start_time)
    if not ok:
        with get_db_session() as db_session:
            workflow_task = db_session.query(WorkflowTask).filter_by(id=workflow_task_id).first()
            if not workflow_task:
                return

            monitoring_token = db_session.query(IBMMonitoringToken).filter_by(region_id=region_id).first()
            if not monitoring_token:
                workflow_task.status = WorkflowTask.STATUS_FAILED
                workflow_task.message = f"IBMMonitoringToken for region_id: '{region_id}' not found"
                db_session.commit()
                LOGGER.error(workflow_task.message)
                return

            monitoring_token.status = IBMMonitoringToken.STATUS_INVALID
            workflow_task.status = WorkflowTask.STATUS_FAILED
            workflow_task.message = str(res)
            db_session.commit()
            LOGGER.error(workflow_task.message)
            return

    with get_db_session() as db_session:
        workflow_task = db_session.query(WorkflowTask).filter_by(id=workflow_task_id).first()
        if not workflow_task:
            return

        monitoring_token = db_session.query(IBMMonitoringToken).filter_by(region_id=region_id).first()
        if not monitoring_token:
            workflow_task.status = WorkflowTask.STATUS_FAILED
            workflow_task.message = f"IBMMonitoringToken for region_id: '{region_id}' not found"
            db_session.commit()
            LOGGER.error(workflow_task.message)
            return

        monitoring_token.status = IBMMonitoringToken.STATUS_VALID
        workflow_task.resource_id = cloud_id
        workflow_task.status = WorkflowTask.STATUS_SUCCESSFUL
        db_session.commit()
        LOGGER.success(f"Monitoring token for IBM Cloud {cloud_id} in region {region_id} validated successfully")


@celery.task(name="add_account_id_to_cloud", base=IBMWorkflowTasksBase)
def add_account_id_to_cloud(workflow_task_id):
    """
    Save Account ID for the cloud
    """
    with get_db_session() as db_session:
        workflow_task = db_session.query(WorkflowTask).filter_by(id=workflow_task_id).first()
        if not workflow_task:
            return

        workflow_task.status = WorkflowTask.STATUS_RUNNING
        db_session.commit()
        task_metadata = workflow_task.task_metadata
        if not task_metadata:
            workflow_task.status = WorkflowTask.STATUS_FAILED
            workflow_task.message = "Internal Server Error"
            db_session.commit()
            LOGGER.error(workflow_task.message)
            return

        cloud_id = task_metadata["cloud_id"]
        if not cloud_id:
            workflow_task.status = WorkflowTask.STATUS_FAILED
            workflow_task.message = "Internal Server Error"
            db_session.commit()
            LOGGER.error(workflow_task.message)
            return

        ibm_cloud = db_session.query(IBMCloud).filter_by(id=cloud_id).first()
        if not ibm_cloud:
            workflow_task.status = WorkflowTask.STATUS_FAILED
            workflow_task.message = f"IBMCloud '{task_metadata['cloud_id']}' not found"
            db_session.commit()
            LOGGER.error(workflow_task.message)
            return

        api_key_id = ibm_cloud.api_key_id

        try:
            client = CloudAccountDetailsClient(cloud_id=cloud_id)
            resp_json = client.get_account_details(api_key_id=api_key_id)
        except (IBMAuthError, IBMConnectError, IBMExecuteError, IBMInvalidRequestError) as ex:
            with get_db_session() as db_session:
                workflow_task = db_session.query(WorkflowTask).filter_by(id=workflow_task_id).first()
                if not workflow_task:
                    return

                workflow_task.status = WorkflowTask.STATUS_FAILED
                workflow_task.message = f"Creation Failed. Reason: {str(ex)}"
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

        workflow_task.status = WorkflowTask.STATUS_SUCCESSFUL
        ibm_cloud.account_id = resp_json["account_id"]
        db_session.commit()

    LOGGER.success(f"Account ID for IBM Cloud {cloud_id} saved successfully")


@celery.task(name="delete_ibm_cloud", base=IBMWorkflowTasksBase)
def delete_ibm_cloud(workflow_task_id):
    """
    This task ensures the smooth deletion of cloud accounts
    """
    with get_db_session() as db_session:
        workflow_task = db_session.query(WorkflowTask).filter_by(id=workflow_task_id).first()
        if not workflow_task:
            return

        workflow_task.status = WorkflowTask.STATUS_RUNNING
        db_session.commit()
        cloud_id = workflow_task.task_metadata["cloud_id"]

        cloud = db_session.query(IBMCloud).filter_by(id=cloud_id, deleted=True).first()
        if not cloud:
            workflow_task.status = WorkflowTask.STATUS_FAILED
            workflow_task.message = f"IBM Cloud {cloud_id} not found in DB"
            db_session.commit()
            LOGGER.info(workflow_task.message)
            return

        cloud.deleted = True
        workflow_task.status = WorkflowTask.STATUS_SUCCESSFUL
        db_session.commit()

        LOGGER.info(f"IBM Cloud {cloud_id} deleted successfully")


@celery.task(name='delete_clouds_initiator', base=Singleton)
def delete_clouds_initiator():
    """Initiate delete task for clouds with deleted 'true'"""

    with get_db_session() as db_session:
        clouds = db_session.query(IBMCloud).filter_by(deleted=True).all()
        for cloud in clouds:
            delete_cloud.delay(cloud.id)


@celery.task(name='delete_cloud', queue="sync_queue", base=Singleton)
def delete_cloud(cloud_id):
    """Delete cloud with provided ID"""

    ins_obj = inspect(IBMCloud)
    with get_db_session() as db_session:
        cloud = db_session.query(IBMCloud).filter_by(id=cloud_id, deleted=True).first()
        if not cloud:
            return

        regions = db_session.query(IBMRegion).filter_by(cloud_id=cloud_id).all()
        zones = db_session.query(IBMZone).filter_by(cloud_id=cloud_id).all()
        resource_groups = db_session.query(IBMResourceGroup).filter_by(cloud_id=cloud_id).all()
        for relation in ins_obj.relationships:
            if relation.mapper.class_ in [IBMRegion, IBMZone, IBMResourceGroup]:
                continue

            start_time = datetime.utcnow()
            resources = db_session.query(relation.mapper.class_).filter_by(cloud_id=cloud_id).limit(500).all()
            resources_count = len(resources)
            while resources:
                LOGGER.info(f"**Deleting {resources_count} {relation.mapper.class_.__name__} resources")
                for resource in resources:
                    db_session.delete(resource)

                db_session.commit()

                resources = db_session.query(relation.mapper.class_).filter_by(cloud_id=cloud_id).limit(500).all()
                resources_count = resources_count + len(resources)

            if resources_count:
                LOGGER.info(
                    f"**{resources_count} {relation.mapper.class_.__name__} resources deleted in: "
                    f"{(datetime.utcnow() - start_time).total_seconds()} seconds")

            db_session.commit()

        for zone in zones:
            db_session.delete(zone)
        db_session.commit()

        for region in regions:
            db_session.delete(region)
        db_session.commit()

        for resource_group in resource_groups:
            db_session.delete(resource_group)
        db_session.commit()

        start_time = datetime.utcnow()
        LOGGER.info(f"**Deleting cloud with ID {cloud_id}")
        db_session.delete(cloud)
        db_session.commit()
        LOGGER.info(
            f"**IBM Cloud with ID {cloud_id} deleted successfully in: "
            f"{(datetime.utcnow() - start_time).total_seconds()} seconds")


@celery.task(name="update_ibm_cloud", base=IBMWorkflowTasksBase)
def update_ibm_cloud(workflow_task_id):
    """
    Update an IBM Cloud Account
    """

    with get_db_session() as db_session:
        workflow_task = db_session.query(WorkflowTask).filter_by(id=workflow_task_id).first()
        if not workflow_task:
            return

        workflow_task.status = WorkflowTask.STATUS_RUNNING
        db_session.commit()

        cloud_id = workflow_task.task_metadata["cloud_id"]
        if not cloud_id:
            workflow_task.status = WorkflowTask.STATUS_FAILED
            workflow_task.message = "'cloud_id' is required for 'update_ibm_cloud'. Please provide."
            db_session.commit()
            LOGGER.error(workflow_task.message)
            return

        ibm_cloud: IBMCloud = db_session.query(IBMCloud).filter_by(id=cloud_id).first()
        if not ibm_cloud:
            workflow_task.status = WorkflowTask.STATUS_FAILED
            workflow_task.message = f"IBMCloud '{cloud_id}' not found"
            db_session.commit()
            LOGGER.error(workflow_task.message)
            return

        data = workflow_task.task_metadata["data"]
        if not data:
            workflow_task.status = WorkflowTask.STATUS_FAILED
            workflow_task.message = "'data' key not provided for the 'update_ibm_cloud' task."
            db_session.commit()
            LOGGER.error(workflow_task.message)
            return

        if "name" in data:
            ibm_cloud.name = data["name"]
        ibm_cloud.metadata_ = workflow_task.task_metadata["user"]

        workflow_task.resource_id = ibm_cloud.id
        workflow_task.status = WorkflowTask.STATUS_SUCCESSFUL
        db_session.commit()

        LOGGER.success(f"IBM Cloud '{ibm_cloud.id}' Updated successfully")


@celery.task(name="sync_ibm_clouds_with_mangos", base=Singleton)
def sync_ibm_clouds_with_mangos():
    """Sync ibm clouds between mangos and vpc"""

    with get_db_session() as db_session:
        clouds = db_session.query(IBMCloud).filter_by(added_in_mangos=False, status=IBMCloud.STATUS_VALID,
                                                      deleted=False).all()

        for cloud in clouds:
            api_key = cloud.api_key
            api_key_id = cloud.api_key_id
            account_id = cloud.account_id
            ibm_cloud_id = cloud.id
            ibm_cloud_name = cloud.name
            try:
                mangos.add_cloud(api_key=api_key, api_key_id=api_key_id, account_id=account_id)
            except MangosGRPCError as ex:
                LOGGER.info(f"Error: {ex} for cloud_id: {ibm_cloud_id} and name: {ibm_cloud_name}")
                continue

            cloud = db_session.query(IBMCloud).filter_by(id=cloud.id).first()
            if not cloud:
                LOGGER.info(f'IBM Cloud against ID: {cloud.id} not found in db')
                return

            cloud.added_in_mangos = True
            db_session.commit()

    if IBMSyncConfigs.ENV_PROD != "true":
        return

    api_key_ids = mangos.get_clouds()
    with get_db_session() as db_session:
        for db_cloud in db_session.query(IBMCloud).filter_by(added_in_mangos=True).all():
            if db_cloud.api_key_id not in api_key_ids:
                db_cloud.added_in_mangos = False
                db_session.commit()

    for api_key_id in api_key_ids:
        with get_db_session() as db_session:
            cloud = db_session.query(IBMCloud).filter_by(api_key_id=api_key_id, deleted=False).first()

        if not cloud:
            try:
                mangos.delete_cloud(api_key_id)
            except MangosGRPCError as ex:
                LOGGER.info(ex)
                continue
