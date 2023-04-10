"""
This file contains background and scheduled tasks related to Image Migration
"""
import datetime

import ibm_boto3
from ibm_botocore.client import Config
from jsonschema import validate, ValidationError
from SoftLayer.exceptions import SoftLayerAPIError

from ibm import get_db_session, LOGGER
from ibm.common.clients.ibm_clients.urls import AUTH_URL, BUCKETS_BASE_URL
from ibm.common.image_conversion.ic_softlayer_manager import ICSoftlayerManager
from ibm.common.image_conversion.ic_softlayer_manager.exceptions import SLAuthException, \
    SLResourceNotFoundException, UnexpectedSLError
from ibm.common.image_conversion.ic_softlayer_manager.instance_response_schema import instance_response_schema
from ibm.common.image_conversion.ssh_manager import SSHManager
from ibm.models import IBMCloud, IBMCOSBucket, ImageConversionInstance, ImageConversionTask, ImageConversionTaskLog
from ibm.tasks.celery_app import celery_app as celery


@celery.task(name="ic_task_distributor", queue="image_conversion_queue")
def image_conversion_task_distributor():
    """
    Scheduled function that handles distribution of tasks to instances (also creates instance entries in database)
    """
    # TODO: find a logic so that if this task is already running, it should not run again
    with get_db_session() as db_session:
        all_instances = db_session.query(ImageConversionInstance).filter_by(
            status=ImageConversionInstance.STATUS_ACTIVE).all()
        for instance in all_instances:
            if instance.task and instance.task.status not in \
                    {ImageConversionTask.STATUS_SUCCESSFUL, ImageConversionTask.STATUS_FAILED}:
                continue

            instance.status = ImageConversionInstance.STATUS_DELETE_PENDING
            instance.task = None
            db_session.commit()

        for created_task in db_session.query(ImageConversionTask).filter_by(
                status=ImageConversionTask.STATUS_CREATED).all():
            if created_task.instance:
                continue

            new_instance = ImageConversionInstance(created_task.region)
            new_instance.task = created_task
            db_session.add(new_instance)
            db_session.commit()


@celery.task(name="ic_instances_overseer", queue="image_conversion_queue")
def image_conversion_instances_overseer():
    """
    Scheduled function that handles creation and deletion of image conversion instances
    """
    # TODO: find a logic so that if this task is already running, it should not run again
    with get_db_session() as db_session:
        create_pending_state_instances = db_session.query(ImageConversionInstance).filter_by(
            status=ImageConversionInstance.STATUS_CREATE_PENDING).all()
        creating_state_instances = db_session.query(ImageConversionInstance).filter_by(
            status=ImageConversionInstance.STATUS_CREATING).all()

        for create_pending_state_instance in create_pending_state_instances:
            initiate_pending_instance_creation.delay(create_pending_state_instance.id)

        for creating_state_instance in creating_state_instances:
            get_update_creating_instance.delay(creating_state_instance.id)

        start_time = datetime.datetime.utcnow() - datetime.timedelta(days=2)
        deleting_resedue_instances = db_session.query(ImageConversionInstance).filter(
            ImageConversionInstance.created_at < start_time).all()

        for delete_resedue_instance in deleting_resedue_instances:
            delete_resedue_instance.status = ImageConversionInstance.STATUS_DELETE_PENDING
            db_session.commit()

        delete_pending_state_instances = db_session.query(ImageConversionInstance).filter_by(
            status=ImageConversionInstance.STATUS_DELETE_PENDING).all()
        deleting_state_instances = db_session.query(ImageConversionInstance).filter_by(
            status=ImageConversionInstance.STATUS_DELETING).all()

        for delete_pending_state_instance in delete_pending_state_instances:
            initiate_pending_instance_deletion.delay(delete_pending_state_instance.id)

        for deleting_state_instance in deleting_state_instances:
            get_delete_deleting_instance.delay(deleting_state_instance.id)


@celery.task(name="ic_initiate_pending_instance_creation", queue="image_conversion_queue")
def initiate_pending_instance_creation(instance_id):
    """
    Task to initiate instance creation on Softlayer for STATUS_CREATE_PENDING instances
    :param instance_id: <string> ImageConversionInstance ID
    """
    with get_db_session() as db_session:
        instance = db_session.query(ImageConversionInstance).filter_by(id=instance_id).first()
        if not instance or instance.status != ImageConversionInstance.STATUS_CREATE_PENDING or instance.softlayer_id:
            return

        try:
            ic_softlayer_manager = ICSoftlayerManager()
            response = ic_softlayer_manager.create_instance(instance.to_softlayer_json())
        except (SLAuthException, UnexpectedSLError, SoftLayerAPIError) as ex:
            LOGGER.info(ex)
            if instance.task:
                instance.task.status = ImageConversionTask.STATUS_FAILED
                instance.task.message = str(ex)
                db_session.commit()
            return

        instance.softlayer_id = response["id"]
        instance.status = ImageConversionInstance.STATUS_CREATING
        db_session.commit()


@celery.task(name="ic_initiate_pending_instance_deletion", queue="image_conversion_queue")
def initiate_pending_instance_deletion(instance_id):
    """
    Task to initiate instance deletion on Softlayer for STATUS_DELETE_PENDING instances
    :param instance_id: <string> ImageConversionInstance ID
    """
    with get_db_session() as db_session:
        instance = db_session.query(ImageConversionInstance).filter_by(id=instance_id).first()
        if not instance or instance.status != ImageConversionInstance.STATUS_DELETE_PENDING or not \
                instance.softlayer_id:
            return

        try:
            ic_softlayer_manager = ICSoftlayerManager()
            ic_softlayer_manager.delete_instance(instance.softlayer_id)
        except (SLAuthException, UnexpectedSLError, SoftLayerAPIError) as ex:
            LOGGER.fail(ex)
            return
        except SLResourceNotFoundException:
            db_session.delete(instance)
            db_session.commit()
            return

        instance.status = ImageConversionInstance.STATUS_DELETING
        db_session.commit()


@celery.task(name="ic_get_update_creating_instance", queue="image_conversion_queue")
def get_update_creating_instance(instance_id):
    """
    Task to get a creating instance from Softlayer and update info in db if complete information is acquired
    Also, update the task (if exists) status to STATUS_RUNNING if instance is successfully created and credentials
    are acquired
    :param instance_id: <string> ImageConversionInstance ID
    """
    with get_db_session() as db_session:
        instance = db_session.query(ImageConversionInstance).filter_by(id=instance_id).first()
        if not instance or instance.status != ImageConversionInstance.STATUS_CREATING or not instance.softlayer_id:
            return

        try:
            ic_softlayer_manager = ICSoftlayerManager()
            response = ic_softlayer_manager.get_instance(instance.softlayer_id)
        except (SLAuthException, SLResourceNotFoundException, UnexpectedSLError) as ex:
            LOGGER.info(ex)
            if instance.task:
                instance.task.status = ImageConversionTask.STATUS_FAILED
                instance.task.message = str(ex)
                db_session.commit()
            return

        try:
            validate(response, instance_response_schema)
        except ValidationError:
            return

        if response["status"]["keyName"] == ImageConversionInstance.STATUS_ACTIVE \
                and response["powerState"]["keyName"] == "RUNNING":
            instance.status = ImageConversionInstance.STATUS_ACTIVE
            instance.update_create_time()

            instance.ip_address = response["primaryIpAddress"]
            instance.username = response["operatingSystem"]["passwords"][0]["username"]
            instance.password = response["operatingSystem"]["passwords"][0]["password"]

            if instance.task:
                instance.task.status = ImageConversionTask.STATUS_RUNNING
            db_session.commit()


@celery.task(name="ic_get_delete_deleting_instance", queue="image_conversion_queue")
def get_delete_deleting_instance(instance_id):
    """
    Task to get a deleting instance from Softlayer. If not found, delete from database
    :param instance_id: <string> ImageConversionInstance ID
    """
    with get_db_session() as db_session:
        instance = db_session.query(ImageConversionInstance).filter_by(id=instance_id).first()
        if not instance or instance.status != ImageConversionInstance.STATUS_DELETING or not instance.softlayer_id:
            return

        try:
            ic_softlayer_manager = ICSoftlayerManager()
            ic_softlayer_manager.get_instance(instance.softlayer_id)
        except (SLAuthException, UnexpectedSLError) as ex:
            LOGGER.fail(ex)
            return
        except SLResourceNotFoundException:
            db_session.delete(instance)
            db_session.commit()


@celery.task(name="ic_pending_task_executor", queue="image_conversion_queue")
def image_conversion_pending_task_executor():
    """
    Scheduled function that handles execution of pending image conversion tasks
    """
    with get_db_session() as db_session:
        tasks = db_session.query(ImageConversionTask).filter(
            ImageConversionTask.status == ImageConversionTask.STATUS_RUNNING,
            ImageConversionTask.step.in_(
                [
                    ImageConversionTask.STEP_PENDING_PROCESS_START,
                    ImageConversionTask.STEP_PENDING_CLEANUP,
                    ImageConversionTask.STEP_FILES_UPLOADING_RETRY,
                    ImageConversionTask.STEP_IMAGE_DOWNLOADING_RETRY
                ]
            )
        ).all()
        for task in tasks:
            if task.step in [
                ImageConversionTask.STEP_PENDING_PROCESS_START, ImageConversionTask.STEP_FILES_UPLOADING_RETRY,
                ImageConversionTask.STEP_IMAGE_DOWNLOADING_RETRY
            ]:
                initiate_image_conversion.delay(task.id)
            elif task.step == ImageConversionTask.STEP_PENDING_CLEANUP:
                initiate_image_conversion_janitor.delay(task.id)


@celery.task(name="initiate_image_conversion", queue="image_conversion_queue")
def initiate_image_conversion(task_id):
    """
    Task to initiate image conversion on the remote instance. Uploads files and then runs image conversion script in
    background
    :param task_id: <string> id of the ImageConversionTask to be initiated
    """
    with get_db_session() as db_session:
        task = db_session.query(ImageConversionTask).filter_by(id=task_id).first()
        if not task or not task.instance:
            return
        bucket = db_session.query(IBMCOSBucket).filter_by(name=task.cos_bucket_name).first()
        if not bucket:
            return
        ssh_manager = None
        try:
            ssh_manager = SSHManager(task.instance.ip_address, password=task.instance.password)

            if task.step in [
                ImageConversionTask.STEP_PENDING_PROCESS_START, ImageConversionTask.STEP_FILES_UPLOADING_RETRY
            ]:
                task.step = ImageConversionTask.STEP_FILES_UPLOADING
                db_session.commit()

                ssh_manager.write_file("/mnt/image_conversion/", "config.json",
                                       task.generate_config_file_contents(crn=bucket.cloud_object_storage.crn))
                ssh_manager.send_file_sftp("/vpcplus-ibm-be/ibm/common/image_conversion/conversion_script.py",
                                           "/mnt/image_conversion/conversion_script.py")

            task.step = ImageConversionTask.STEP_IMAGE_DOWNLOADING
            db_session.commit()
            ssh_manager.run_command(
                "nohup python3 -u /mnt/image_conversion/conversion_script.py {} > /mnt/image_conversion/imc.log "
                "&".format(
                    task.webhook_url
                )
            )
        except Exception as ex:
            # Catching general exceptions here as Paramiko documentation is a little inconsistent with the exceptions
            # they
            # generate. We can not let this task fail as it can cost us a dangling instance
            if task.retries:
                task.retries -= 1
                if task.step == ImageConversionTask.STEP_FILES_UPLOADING:
                    task.step = ImageConversionTask.STEP_FILES_UPLOADING_RETRY
                elif task.step == ImageConversionTask.STEP_IMAGE_DOWNLOADING:
                    task.step = ImageConversionTask.STEP_IMAGE_DOWNLOADING_RETRY
                db_session.commit()
                return

            task.status = ImageConversionTask.STATUS_FAILED
            task.message = str(ex)
            db_session.commit()
        finally:
            if ssh_manager:
                ssh_manager.close_ssh_connection()


@celery.task(name="initiate_image_conversion_janitor", queue="image_conversion_queue")
def initiate_image_conversion_janitor(task_id):
    """
    Task to cleanup the image conversion files after the task ends
    :param task_id: <string> id of the task to be cleaned up
    """
    with get_db_session() as db_session:
        task = db_session.query(ImageConversionTask).filter_by(id=task_id).first()
        if not task or not task.instance:
            return

        task.step = ImageConversionTask.STEP_CLEANING_UP
        db_session.commit()

        ssh_manager = None
        try:
            ssh_manager = SSHManager(task.instance.ip_address, password=task.instance.password)
            ssh_manager.run_command("rm -rf /mnt/image_conversion/*")
        except Exception as ex:
            # Catching general exceptions here as Paramiko documentation is a little inconsistent with the exceptions
            # they
            # generate. We can not let this task fail as it can cost us a dangling instance
            task.status = ImageConversionTask.STATUS_SUCCESSFUL
            task.message = str(ex)
            db_session.add(ImageConversionTaskLog(task))
            db_session.commit()
            return
        finally:
            if ssh_manager:
                ssh_manager.close_ssh_connection()

        task.status = ImageConversionTask.STATUS_SUCCESSFUL
        task.step = ImageConversionTask.STEP_PROCESS_COMPLETED
        db_session.add(ImageConversionTaskLog(task))
        db_session.commit()


@celery.task(name="ic_get_image_size", queue="image_conversion_queue")
def get_image_size(cloud_id, region, bucket_dict, image_name, image_format):
    """
    Get the size of image to convert. This task will get the size using object's HEAD data using S3 APIs
    :param cloud_id: <string> cloud ID for which the image is being converted (for credentials)
    :param region: <string> region in which the COS bucket resides
    :param bucket_dict: <string> bucket_dict in which the image resides
    :param image_name: <string> Name of the image
    :param image_format: <string> format of the image
    :return: <int> Image size in MBs
    """
    with get_db_session() as db_session:
        cloud = db_session.query(IBMCloud).filter_by(id=cloud_id).first()
        bucket = db_session.query(IBMCOSBucket).filter_by(**bucket_dict).first()
        if not (cloud and bucket):
            return
        api_key = cloud.api_key
        bucket_name = bucket.name
        cos_crn = bucket.cloud_object_storage.crn
    client = ibm_boto3.client(
        service_name='s3', ibm_api_key_id=api_key,
        ibm_service_instance_id=cos_crn,
        ibm_auth_endpoint=AUTH_URL,
        config=Config(signature_version="oauth"),
        endpoint_url=BUCKETS_BASE_URL.format(region=region))

    response = client.head_object(
        Bucket=bucket_name, Key=f"{image_name}.{image_format}"
    )
    if not response.get("ResponseMetadata") or not response["ResponseMetadata"].get("HTTPHeaders") \
            or not response["ResponseMetadata"]["HTTPHeaders"].get("content-length"):
        return

    return int(int(response["ResponseMetadata"]["HTTPHeaders"]["content-length"]) / 1000000)
