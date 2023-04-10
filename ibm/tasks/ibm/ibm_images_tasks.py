from copy import deepcopy

from ibm_botocore.exceptions import ClientError
from ibm_cloud_sdk_core import ApiException

from ibm import get_db_session, LOGGER
from ibm.common.clients.ibm_clients import ImagesClient
from ibm.common.utils import update_id_or_name_references
from ibm.models import IBMCloud, IBMCOSBucket, IBMIdleResource, IBMImage, IBMOperatingSystem, IBMRegion, \
    IBMResourceGroup, IBMResourceLog, IBMResourceTracking, IBMVolume, ImageConversionTask, WorkflowTask
from ibm.tasks.celery_app import celery_app as celery
from ibm.tasks.common.tasks_base import IBMWorkflowTasksBase
from ibm.tasks.ibm.image_conversion_tasks import get_image_size
from ibm.tasks.ibm.task_utils import load_previous_associated_resources
from ibm.web.ibm.images.schemas import IBMImageInSchema, IBMImageResourceSchema
from ibm.web.ibm.images.utils import return_image_name
from ibm.web.ibm.instances.consts import InstanceMigrationConsts
from ibm.web.resource_tracking.utils import create_resource_tracking_object


@celery.task(name="create_image", base=IBMWorkflowTasksBase)
def create_ibm_image(workflow_task_id):
    """
    Create an IBM Image Key on IBM Cloud
    """
    with get_db_session() as db_session:
        workflow_task = db_session.query(WorkflowTask).filter_by(id=workflow_task_id).first()
        if not workflow_task:
            return

        workflow_task.status = WorkflowTask.STATUS_RUNNING
        db_session.commit()

        resource_data = deepcopy(workflow_task.task_metadata["resource_data"])
        resource_json = deepcopy(resource_data["resource_json"])
        migration_json = deepcopy(resource_data.get("migration_json"))
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

        file = resource_json.get("file") or migration_json.get("file") if migration_json else None
        if file:
            if file.get("href"):
                href = file["href"]
            else:
                object_type = file.get('object_type') or "qcow2"
                bucket = db_session.query(IBMCOSBucket).filter_by(**file["bucket"]).first()
                if not bucket:
                    workflow_task.status = WorkflowTask.STATUS_FAILED
                    workflow_task.message = f"IBMCOSBucket '{file['bucket']}' not found"
                    db_session.commit()
                    LOGGER.error(workflow_task.message)
                    return
                bucket_name = bucket.name
                href = f"cos://{region_name}/{bucket_name}/{file['cos_bucket_object']}"
                if not href.endswith(object_type):
                    href = f"{href}-0.{object_type}"
            if migration_json:
                res_json = {"name": resource_json["name"],
                            "operating_system": migration_json["operating_system"]}
                if resource_json.get("resource_group"):
                    res_json["resource_group"] = resource_json["resource_group"]
                del resource_json
                resource_json = deepcopy(res_json)

            resource_json["file"] = {"href": href}

        previous_resources = load_previous_associated_resources(task=workflow_task, session=db_session)
        update_id_or_name_references(
            cloud_id=cloud_id, resource_json=resource_data, resource_schema=IBMImageInSchema,
            db_session=db_session, previous_resources=previous_resources
        )
        update_id_or_name_references(
            cloud_id=cloud_id, resource_json=resource_json, resource_schema=IBMImageResourceSchema,
            db_session=db_session, previous_resources=previous_resources
        )
    try:
        if file and migration_json:  # If migration is enabled then user don't have to provide name for the image
            image_name = return_image_name(cloud_id=cloud_id, region=region_name, image_name=resource_json["name"])
            resource_json["name"] = image_name
        LOGGER.info(f"IBMImage Creation Payload: {resource_json}")
        client = ImagesClient(cloud_id=cloud_id, region=region_name)
        resp_json = client.create_image(image_json=resource_json)
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

        image_status = resp_json["status"]
        image_name = resp_json["name"]
        image_resource_id = resp_json["id"]

        if image_status in [IBMImage.STATUS_AVAILABLE, IBMImage.STATUS_PENDING]:
            task_metadata = deepcopy(workflow_task.task_metadata)
            resource_data = deepcopy(task_metadata["resource_data"])
            resource_json = deepcopy(resource_data["resource_json"])
            if file:
                resource_json["image"] = {"name": image_name}
            task_metadata["ibm_resource_id"] = image_resource_id
            resource_data["resource_json"] = resource_json
            task_metadata["resource_data"] = resource_data
            workflow_task.task_metadata = task_metadata

            workflow_task.status = WorkflowTask.STATUS_RUNNING_WAIT
            message = f"IBM Image {image_name} for cloud {cloud_id} creation waiting"
            workflow_task.message = message
            LOGGER.info(message)
        else:
            message = f"IBM Image {image_name} for cloud {cloud_id} creation failed"
            workflow_task.message = message
            workflow_task.status = WorkflowTask.STATUS_FAILED
            LOGGER.fail(message)

        db_session.commit()


@celery.task(name="create_wait_ibm_image", base=IBMWorkflowTasksBase)
def create_wait_ibm_image(workflow_task_id):
    """
    Wait for an IBM Image creation on IBM Cloud
    """
    with get_db_session() as db_session:
        workflow_task = db_session.query(WorkflowTask).filter_by(id=workflow_task_id).first()
        if not workflow_task:
            return

        workflow_task.status = WorkflowTask.STATUS_RUNNING
        db_session.commit()

        task_metadata = deepcopy(workflow_task.task_metadata)
        resource_data = deepcopy(task_metadata["resource_data"])
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
        resource_id = workflow_task.task_metadata["ibm_resource_id"]

    try:
        client = ImagesClient(cloud_id=cloud_id, region=region_name)
        image_json = client.get_image(image_id=resource_id)
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

        if image_json["status"] == IBMImage.STATUS_FAILED:
            workflow_task.status = WorkflowTask.STATUS_FAILED
            workflow_task.message = f"IBM Image '{image_json['name']}' creation for cloud '{cloud_id}' " \
                                    f"failed on IBM Cloud"
            db_session.commit()
            LOGGER.fail(workflow_task.message)
            return

        elif image_json["status"] == IBMImage.STATUS_PENDING:
            workflow_task.status = WorkflowTask.STATUS_RUNNING_WAIT
            db_session.commit()
            LOGGER.info(f"IBM Image '{image_json['name']}' creation for cloud '{cloud_id}' waiting")
            return

        with db_session.no_autoflush:
            region = db_session.query(IBMRegion).filter_by(id=region_id, cloud_id=cloud_id).first()
            resource_group = db_session.query(IBMResourceGroup).filter_by(
                resource_id=image_json["resource_group"]["id"], cloud_id=cloud_id).first()
            operating_system = db_session.query(IBMOperatingSystem).filter_by(
                name=image_json["operating_system"]["name"], cloud_id=cloud_id).first()
            source_volume = None
            if image_json.get("source_volume"):
                source_volume = db_session.query(IBMVolume).filter_by(
                    resource_id=image_json["source_volume"]["id"], cloud_id=cloud_id).first()

            if not (region and resource_group and operating_system):
                workflow_task.status = WorkflowTask.STATUS_FAILED
                workflow_task.message = \
                    "Creation Successful but record update failed. The records will update next time discovery runs"
                db_session.commit()
                LOGGER.note(workflow_task.message)

            image = IBMImage.from_ibm_json_body(json_body=image_json)
            image.region = region
            image.operating_system = operating_system
            image.resource_group = resource_group
            if source_volume:
                image.source_volume = source_volume

            db_session.commit()
        if resource_data.get("resource_json"):
            resource_data["resource_json"]["image"] = {"id": image.id}
            task_metadata["resource_data"] = resource_data
        for next_task in workflow_task.next_tasks:
            next_task.task_metadata = deepcopy(task_metadata)
        image_json = image.to_json()
        image_json["created_at"] = str(image_json["created_at"])

        IBMResourceLog(
            resource_id=image.resource_id, region=image.region,
            status=IBMResourceLog.STATUS_ADDED, resource_type=IBMImage.__name__,
            data=image_json)

        workflow_task.status = WorkflowTask.STATUS_SUCCESSFUL
        db_session.commit()

    LOGGER.success(f"IBM Image '{image_json['name']}' creation for cloud '{cloud_id}' successful")
    # TODO add delete_object as this is already changing and then test out
    # migration_json = deepcopy(resource_data.get("migration_json"))
    # if migration_json["migrate_from"] in [
    #     InstanceMigrationConsts.CLASSIC_VSI, InstanceMigrationConsts.ONLY_VOLUME_MIGRATION,
    #     InstanceMigrationConsts.CLASSIC_IMAGE
    # ]:
    #     cos_bucket_object = f"{migration_json['cos_bucket_object']}-0.vhd"
    #     cos_client = COSClient(cloud_id=cloud_id)
    #     cos_client.delete_object()


@celery.task(name="delete_image", base=IBMWorkflowTasksBase)
def delete_image(workflow_task_id):
    """
    Delete an IBM Image
    :param workflow_task_id:
    :return:
    """
    with get_db_session() as db_session:
        workflow_task = db_session.query(WorkflowTask).filter_by(id=workflow_task_id).first()
        if not workflow_task:
            return

        workflow_task.status = WorkflowTask.STATUS_RUNNING
        db_session.commit()

        image = db_session.query(IBMImage).filter_by(id=workflow_task.resource_id).first()
        if not image:
            workflow_task.status = WorkflowTask.STATUS_FAILED
            workflow_task.message = f"IBMImage '{workflow_task.resource_id}' not found"
            db_session.commit()
            LOGGER.error(workflow_task.message)
            return

        region_name = image.region.name
        image_resource_id = image.resource_id
        cloud_id = image.cloud_id
        image_name = image.name
    try:
        image_client = ImagesClient(cloud_id, region=region_name)
        image_client.delete_image(image_resource_id)
        image_json = image_client.get_image(image_resource_id)

    except ApiException as ex:
        # IBM Image is deleted from IBM Cloud Console, but we still have it on VPC + side.
        with get_db_session() as db_session:
            workflow_task = db_session.query(WorkflowTask).filter_by(id=workflow_task_id).first()
            if not workflow_task:
                return

            if ex.code == 404:  # 404 means resource is not found on IBM Cloud.
                image = db_session.query(IBMImage).filter_by(id=workflow_task.resource_id).first()
                if image:
                    image_json = image.to_json()
                    image_json["created_at"] = str(image_json["created_at"])

                    IBMResourceLog(
                        resource_id=image.resource_id, region=image.region,
                        status=IBMResourceLog.STATUS_DELETED, resource_type=IBMImage.__name__,
                        data=image_json)

                    db_session.query(IBMIdleResource).filter_by(cloud_id=image.cloud_id,
                                                                db_resource_id=image.id).delete()
                    db_session.delete(image)

                workflow_task.status = WorkflowTask.STATUS_SUCCESSFUL
                LOGGER.success(f"IBM Image {image_name} for cloud {cloud_id} deletion successful.")
                db_session.commit()
                return

            workflow_task.status = WorkflowTask.STATUS_FAILED
            workflow_task.message = f"Deletion Failed. Reason: {str(ex.message)}"
            db_session.commit()
            LOGGER.fail(workflow_task.message)
            return

    image_status = image_json["status"]
    with get_db_session() as db_session:
        workflow_task = db_session.query(WorkflowTask).filter_by(id=workflow_task_id).first()
        if not workflow_task:
            return

        if image_status in [IBMImage.STATUS_UNUSABLE, IBMImage.STATUS_FAILED]:
            message = f"IBM Image {image.name} for cloud {image.cloud_id} deletion failed on IBM Cloud"
            workflow_task.status = WorkflowTask.STATUS_FAILED
            workflow_task.message = message
            LOGGER.fail(message)
        else:
            message = f"IBM Image {image.name} for cloud {image.cloud_id} deletion waiting"
            LOGGER.info(message)
            workflow_task.status = WorkflowTask.STATUS_RUNNING_WAIT

        db_session.commit()


@celery.task(name="delete_wait_image", base=IBMWorkflowTasksBase)
def delete_wait_image(workflow_task_id):
    """
    Wait for an IBM Image deletion on IBM Cloud.
    :param workflow_task_id:
    :return:
    """
    with get_db_session() as db_session:
        workflow_task = db_session.query(WorkflowTask).filter_by(id=workflow_task_id).first()
        if not workflow_task:
            return

        workflow_task.status = WorkflowTask.STATUS_RUNNING
        db_session.commit()

        image = db_session.query(IBMImage).filter_by(id=workflow_task.resource_id).first()
        if not image:
            workflow_task.status = WorkflowTask.STATUS_FAILED
            workflow_task.message = f"IBMImage '{workflow_task.resource_id}' not found"
            db_session.commit()
            LOGGER.error(workflow_task.message)
            return

        region_name = image.region.name
        image_resource_id = image.resource_id
        cloud_id = image.cloud_id
        image_name = image.name
    try:
        image_client = ImagesClient(cloud_id, region=region_name)
        resp_json = image_client.get_image(image_resource_id)

    except ApiException as ex:
        with get_db_session() as db_session:
            workflow_task = db_session.query(WorkflowTask).filter_by(id=workflow_task_id).first()
            if not workflow_task:
                return

            if ex.code == 404:  # 404 means resource is not found on IBM Cloud.
                image = db_session.query(IBMImage).filter_by(id=workflow_task.resource_id).first()
                if image:
                    image_json = image.to_json()
                    image_json["created_at"] = str(image_json["created_at"])

                    IBMResourceLog(
                        resource_id=image.resource_id, region=image.region,
                        status=IBMResourceLog.STATUS_DELETED, resource_type=IBMImage.__name__,
                        data=image_json)

                    # Adding resource to IBMResourceTracking
                    create_resource_tracking_object(db_resource=image, action_type=IBMResourceTracking.DELETED,
                                                    session=db_session)
                    db_session.delete(image)

                workflow_task.status = WorkflowTask.STATUS_SUCCESSFUL
                LOGGER.success(
                    f"IBM Image {image_name} for cloud {cloud_id} deletion successful.")

                db_session.commit()
                return

            workflow_task.status = WorkflowTask.STATUS_FAILED
            workflow_task.message = f"Deletion Failed. Reason: {str(ex.message)}"
            db_session.commit()
            LOGGER.fail(workflow_task.message)
            return

    image_status = resp_json["status"]
    with get_db_session() as db_session:
        workflow_task = db_session.query(WorkflowTask).filter_by(id=workflow_task_id).first()
        if not workflow_task:
            return

        if image_status in [IBMImage.STATUS_UNUSABLE, IBMImage.STATUS_FAILED]:
            message = f"IBM Image {image_name} for cloud {cloud_id} deletion failed on IBM Cloud"
            workflow_task.status = WorkflowTask.STATUS_FAILED
            workflow_task.message = message
            LOGGER.fail(message)
        else:
            message = f"IBM Image {image_name} for cloud {cloud_id} deletion waiting"
            workflow_task.status = WorkflowTask.STATUS_RUNNING_WAIT
            LOGGER.info(message)

        db_session.commit()


@celery.task(name="create_image_conversion", base=IBMWorkflowTasksBase)
def create_image_conversion(workflow_task_id):
    """
    This creates a task for image conversion service after getting its size
    :return:
    """
    with get_db_session() as db_session:
        workflow_task = db_session.query(WorkflowTask).filter_by(id=workflow_task_id).first()
        if not workflow_task:
            return

        workflow_task.status = WorkflowTask.STATUS_RUNNING
        db_session.commit()

        task_metadata = deepcopy(workflow_task.task_metadata)
        resource_data = deepcopy(task_metadata["resource_data"])
        migration_json = deepcopy(resource_data["migration_json"])
        cloud_id = resource_data["ibm_cloud"]["id"]
        region_id = resource_data["region"]["id"]

        ibm_cloud = db_session.query(IBMCloud).filter_by(id=cloud_id, deleted=False).first()
        if not ibm_cloud:
            workflow_task.status = WorkflowTask.STATUS_FAILED
            workflow_task.message = f"IBM Cloud {cloud_id} not found"
            LOGGER.error(workflow_task.message)
            return

        if ibm_cloud.status != IBMCloud.STATUS_VALID:
            workflow_task.status = WorkflowTask.STATUS_FAILED
            workflow_task.message = f"IBM Cloud {ibm_cloud.name} is not in {IBMCloud.STATUS_VALID} status"
            LOGGER.error(workflow_task.message)
            return

        region = ibm_cloud.regions.filter_by(id=region_id).first()
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
        image_format = None
        if migration_json["migrate_from"] in InstanceMigrationConsts.COS_BUCKET_VHD_USE_CASES:
            image_format = "vhd"
        elif migration_json["migrate_from"] == InstanceMigrationConsts.COS_BUCKET_VMDK:
            image_format = "vmdk"

        if image_format not in ["vhd", "vmdk"]:
            msg = f"Unsupported source image format '{image_format}' for Image Conversion"
            workflow_task.message = msg
            workflow_task.status = WorkflowTask.STATUS_FAILED
            db_session.commit()
            LOGGER.error(msg)
            return

    LOGGER.info(f"IMAGE CONVERSION DATA: {migration_json}")
    file = migration_json["file"]
    try:
        if file.get("href"):
            file_details = file["href"].split("/")
            cos_bucket_object = file_details[-1].split(".")[0]
            bucket_dict = {"name": file_details[-2]}
            file["bucket"] = bucket_dict
            file["cos_bucket_object"] = cos_bucket_object
            migration_json["file"] = file
        else:
            bucket_dict = migration_json["file"]["bucket"]
            cos_bucket_object = migration_json["file"]["cos_bucket_object"] + "-0"
        image_size_mb = get_image_size(
            cloud_id=cloud_id, region=region_name, bucket_dict=bucket_dict,
            image_name=cos_bucket_object, image_format=image_format
        )
    except (IndexError, ClientError) as ex:
        with get_db_session() as db_session:
            workflow_task = db_session.query(WorkflowTask).filter_by(id=workflow_task_id).first()
            if not workflow_task:
                return
            msg = f"Could not get proper payload for create Image {cos_bucket_object} in COS bucket {bucket_dict} " \
                  f"for Region {region_name}. Reason: {ex}"
            workflow_task.status = WorkflowTask.STATUS_FAILED
            workflow_task.message = msg
            db_session.commit()
            LOGGER.error(msg)
            return
    with get_db_session() as db_session:
        workflow_task = db_session.query(WorkflowTask).filter_by(id=workflow_task_id).first()
        if not workflow_task:
            return
        if not image_size_mb:
            msg = f"Could not get size of Image {cos_bucket_object} in COS bucket " \
                  f"{bucket_dict} for Region {region_name}"
            workflow_task.status = WorkflowTask.STATUS_FAILED
            workflow_task.message = msg
            db_session.commit()
            LOGGER.error(msg)
            return

        bucket = db_session.query(IBMCOSBucket).filter_by(**bucket_dict).first()
        if not bucket:
            msg = f"Could not find COS bucket {bucket_dict} for Region {region_name}"
            workflow_task.status = WorkflowTask.STATUS_FAILED
            workflow_task.message = msg
            db_session.commit()
            LOGGER.error(msg)
            return

        image_conversion_task = ImageConversionTask(
            region=region_name, cos_bucket_name=bucket.name, image_name=f"{cos_bucket_object}.{image_format}",
            image_size_mb=image_size_mb
        )
        image_conversion_task.ibm_cloud = ibm_cloud
        db_session.add(image_conversion_task)
        db_session.commit()
        # migration_json["file"]["cos_bucket_object"] = f"{cos_bucket_object}.qcow2"
        if migration_json["file"].get("href"):
            migration_json["file"]["href"] = migration_json["file"]["href"].replace(f".{image_format}", ".qcow2")
        else:
            migration_json["file"]["href"] = f"cos://{region_name}/{bucket.name}/{cos_bucket_object}.qcow2"

        migration_json["image_conversion_task_id"] = image_conversion_task.id
        resource_data["migration_json"] = migration_json
        task_metadata["resource_data"] = resource_data
        workflow_task.task_metadata = task_metadata
        workflow_task.status = WorkflowTask.STATUS_RUNNING_WAIT
        db_session.commit()


@celery.task(name="create_wait_image_conversion", base=IBMWorkflowTasksBase)
def create_wait_image_conversion(workflow_task_id):
    """
    This method polls on Image conversion task to make sure conversion is completed
    :return:
    """

    with get_db_session() as db_session:
        workflow_task = db_session.query(WorkflowTask).filter_by(id=workflow_task_id).first()
        if not workflow_task:
            return

        workflow_task.status = WorkflowTask.STATUS_RUNNING
        db_session.commit()

        task_metadata = deepcopy(workflow_task.task_metadata)
        resource_data = deepcopy(task_metadata["resource_data"])
        migration_json = deepcopy(resource_data["migration_json"])
        cloud_id = resource_data["ibm_cloud"]["id"]
        region_id = resource_data["region"]["id"]
        image_conversion_task_id = migration_json["image_conversion_task_id"]

        ibm_cloud = db_session.query(IBMCloud).filter_by(id=cloud_id, deleted=False).first()
        if not ibm_cloud:
            workflow_task.status = WorkflowTask.STATUS_FAILED
            workflow_task.message = f"IBM Cloud {cloud_id} not found"
            LOGGER.error(workflow_task.message)
            return

        if ibm_cloud.status != IBMCloud.STATUS_VALID:
            workflow_task.status = WorkflowTask.STATUS_FAILED
            workflow_task.message = f"IBM Cloud {ibm_cloud.name} is not in {IBMCloud.STATUS_VALID} status"
            LOGGER.error(workflow_task.message)
            return

        region = ibm_cloud.regions.filter_by(id=region_id).first()
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

        image_conversion_task = db_session.query(ImageConversionTask).filter_by(id=image_conversion_task_id).first()
        if not image_conversion_task or image_conversion_task.status == ImageConversionTask.STATUS_FAILED:
            workflow_task.status = WorkflowTask.STATUS_FAILED
            workflow_task.message = image_conversion_task.message if image_conversion_task else \
                f"ImageConversionTask: {image_conversion_task_id} not found"
            LOGGER.fail(workflow_task.message)
        elif image_conversion_task.status == ImageConversionTask.STATUS_SUCCESSFUL:
            workflow_task.status = WorkflowTask.STATUS_SUCCESSFUL
            for next_task in workflow_task.next_tasks:
                next_task.task_metadata = deepcopy(task_metadata)
            db_session.commit()
            LOGGER.success(f"Image Conversion for Image: {migration_json['file']['cos_bucket_object']} Successful "
                           f"for IBM Cloud: {cloud_id}")
        else:
            workflow_task.status = WorkflowTask.STATUS_RUNNING_WAIT
            LOGGER.info(f"Image Conversion for Image: {migration_json['file']['cos_bucket_object']} create waiting "
                        f"for IBM Cloud: {cloud_id}")
        db_session.commit()


@celery.task(name="store_ibm_custom_image", base=IBMWorkflowTasksBase)
def store_ibm_custom_image(workflow_task_id):
    """
    Store IBM Custom Image Created on Cloud
    """
    with get_db_session() as db_session:
        workflow_task = db_session.query(WorkflowTask).filter_by(id=workflow_task_id).first()
        if not workflow_task:
            return

        workflow_task.status = WorkflowTask.STATUS_RUNNING
        db_session.commit()

        task_metadata = deepcopy(workflow_task.task_metadata)
        resource_data = deepcopy(task_metadata["resource_data"])
        cloud_id = resource_data["cloud_id"]
        region_name = resource_data["region"]
        image_name = resource_data["image_name"]

        region = db_session.query(IBMRegion).filter_by(name=region_name, cloud_id=cloud_id).first()
        if not region:
            workflow_task.status = WorkflowTask.STATUS_FAILED
            workflow_task.message = f"IBMRegion '{region_name}' not found"
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

    try:
        client = ImagesClient(cloud_id=cloud_id, region=region_name)
        images = client.list_images(name=image_name, visibility="private")
        if not images:
            with get_db_session() as db_session:
                workflow_task = db_session.query(WorkflowTask).filter_by(id=workflow_task_id).first()
                if not workflow_task:
                    return
                workflow_task.status = WorkflowTask.STATUS_FAILED
                workflow_task.message = f"IBM Image with name '{image_name}' does not exist on ibm cloud"
                db_session.commit()
                LOGGER.fail(workflow_task.message)
                return
        image_id = images[0]['id']
        image_json = client.get_image(image_id=image_id)
    except (ApiException, IndexError, KeyError) as ex:
        with get_db_session() as db_session:
            workflow_task = db_session.query(WorkflowTask).filter_by(id=workflow_task_id).first()
            if not workflow_task:
                return

            workflow_task.status = WorkflowTask.STATUS_FAILED
            workflow_task.message = f"Discovery Failed. Reason: {str(ex)}"
            db_session.commit()
            LOGGER.fail(workflow_task.message)
            return

    with get_db_session() as db_session:
        workflow_task = db_session.query(WorkflowTask).filter_by(id=workflow_task_id).first()
        if not workflow_task:
            return

        if image_json["status"] == IBMImage.STATUS_FAILED:
            workflow_task.status = WorkflowTask.STATUS_FAILED
            workflow_task.message = f"IBM Image '{image_json['name']}' creation for cloud '{cloud_id}' " \
                                    f"failed on IBM Cloud"
            db_session.commit()
            LOGGER.fail(workflow_task.message)
            return

        elif image_json["status"] == IBMImage.STATUS_PENDING:
            workflow_task.status = WorkflowTask.STATUS_RUNNING_WAIT
            db_session.commit()
            LOGGER.info(f"IBM Image '{image_json['name']}' creation for cloud '{cloud_id}' waiting")
            return

        with db_session.no_autoflush:
            region = db_session.query(IBMRegion).filter_by(name=region_name, cloud_id=cloud_id).first()
            resource_group = db_session.query(IBMResourceGroup).filter_by(
                resource_id=image_json["resource_group"]["id"], cloud_id=cloud_id).first()
            operating_system = db_session.query(IBMOperatingSystem).filter_by(
                name=image_json["operating_system"]["name"], cloud_id=cloud_id).first()
            source_volume = None
            if image_json.get("source_volume"):
                source_volume = db_session.query(IBMVolume).filter_by(
                    resource_id=image_json["source_volume"]["id"], cloud_id=cloud_id).first()

            if not (region and resource_group and operating_system):
                workflow_task.status = WorkflowTask.STATUS_FAILED
                workflow_task.message = \
                    "Creation Successful but record update failed. The records will update next time discovery runs"
                db_session.commit()
                LOGGER.note(workflow_task.message)

            image = IBMImage.from_ibm_json_body(json_body=image_json)
            image.region = region
            image.operating_system = operating_system
            image.resource_group = resource_group
            if source_volume:
                image.source_volume = source_volume

            db_session.commit()
        image_json = image.to_json()
        image_json["created_at"] = str(image_json["created_at"])

        IBMResourceLog(
            resource_id=image.resource_id, region=image.region,
            status=IBMResourceLog.STATUS_ADDED, resource_type=IBMImage.__name__,
            data=image_json)

        workflow_task.status = WorkflowTask.STATUS_SUCCESSFUL
        db_session.commit()

    LOGGER.success(f"IBM Image '{image_json['name']}' storing for cloud '{cloud_id}' successful")


@celery.task(name="store_wait_ibm_custom_image", base=IBMWorkflowTasksBase)
def store_wait_ibm_custom_image(workflow_task_id):
    """
    Wait for an IBM Custom Image Created on Cloud
    """
    with get_db_session() as db_session:
        workflow_task = db_session.query(WorkflowTask).filter_by(id=workflow_task_id).first()
        if not workflow_task:
            return

        workflow_task.status = WorkflowTask.STATUS_RUNNING
        db_session.commit()

        task_metadata = deepcopy(workflow_task.task_metadata)
        resource_data = deepcopy(task_metadata["resource_data"])
        cloud_id = resource_data["cloud_id"]
        region_name = resource_data["region"]
        image_name = resource_data["image_name"]

        region = db_session.query(IBMRegion).filter_by(name=region_name, cloud_id=cloud_id).first()
        if not region:
            workflow_task.status = WorkflowTask.STATUS_FAILED
            workflow_task.message = f"IBMRegion '{region_name}' not found"
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

    try:
        client = ImagesClient(cloud_id=cloud_id)
        images = client.list_images(region=region_name, name=image_name, visibility="private")
        if not images:
            with get_db_session() as db_session:
                workflow_task = db_session.query(WorkflowTask).filter_by(id=workflow_task_id).first()
                if not workflow_task:
                    return
                workflow_task.status = WorkflowTask.STATUS_FAILED
                workflow_task.message = f"IBM Image with name '{image_name}' does not exist on ibm cloud"
                db_session.commit()
                LOGGER.fail(workflow_task.message)
                return
        image_id = images[0]['id']
        image_json = client.get_image(image_id=image_id)

    except ApiException as ex:
        with get_db_session() as db_session:
            workflow_task = db_session.query(WorkflowTask).filter_by(id=workflow_task_id).first()
            if not workflow_task:
                return

            workflow_task.status = WorkflowTask.STATUS_FAILED
            workflow_task.message = f"Discovery Failed. Reason: {str(ex.message)}"
            db_session.commit()
            LOGGER.fail(workflow_task.message)
            return

    with get_db_session() as db_session:
        workflow_task = db_session.query(WorkflowTask).filter_by(id=workflow_task_id).first()
        if not workflow_task:
            return

        if image_json["status"] == IBMImage.STATUS_FAILED:
            workflow_task.status = WorkflowTask.STATUS_FAILED
            workflow_task.message = f"IBM Image '{image_json['name']}' creation for cloud '{cloud_id}' " \
                                    f"failed on IBM Cloud"
            db_session.commit()
            LOGGER.fail(workflow_task.message)
            return

        elif image_json["status"] == IBMImage.STATUS_PENDING:
            workflow_task.status = WorkflowTask.STATUS_RUNNING_WAIT
            db_session.commit()
            LOGGER.info(f"IBM Image '{image_json['name']}' creation for cloud '{cloud_id}' waiting")
            return

        with db_session.no_autoflush:
            region = db_session.query(IBMRegion).filter_by(name=region_name, cloud_id=cloud_id).first()
            resource_group = db_session.query(IBMResourceGroup).filter_by(
                resource_id=image_json["resource_group"]["id"], cloud_id=cloud_id).first()
            operating_system = db_session.query(IBMOperatingSystem).filter_by(
                name=image_json["operating_system"]["name"], cloud_id=cloud_id).first()
            source_volume = None
            if image_json.get("source_volume"):
                source_volume = db_session.query(IBMVolume).filter_by(
                    resource_id=image_json["source_volume"]["id"], cloud_id=cloud_id).first()

            if not (region and resource_group and operating_system):
                workflow_task.status = WorkflowTask.STATUS_FAILED
                workflow_task.message = \
                    "Creation Successful but record update failed. The records will update next time discovery runs"
                db_session.commit()
                LOGGER.note(workflow_task.message)

            image = IBMImage.from_ibm_json_body(json_body=image_json)
            image.region = region
            image.operating_system = operating_system
            image.resource_group = resource_group
            if source_volume:
                image.source_volume = source_volume

            db_session.commit()
        image_json = image.to_json()
        image_json["created_at"] = str(image_json["created_at"])

        IBMResourceLog(
            resource_id=image.resource_id, region=image.region,
            status=IBMResourceLog.STATUS_ADDED, resource_type=IBMImage.__name__,
            data=image_json)

        workflow_task.status = WorkflowTask.STATUS_SUCCESSFUL
        db_session.commit()

    LOGGER.success(f"IBM Image '{image_json['name']}' storing for cloud '{cloud_id}' successful")
