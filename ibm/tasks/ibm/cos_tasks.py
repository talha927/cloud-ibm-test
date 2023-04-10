from copy import deepcopy
from ibm_cloud_sdk_core import ApiException

import boto3 as boto3

from ibm import get_db_session, LOGGER
from ibm.common.clients.ibm_clients import COSClient, GlobalCatalogsClient, ResourceInstancesClient
from ibm.common.clients.ibm_clients.exceptions import IBMAuthError, IBMConnectError, IBMExecuteError, \
    IBMInvalidRequestError
from ibm.common.consts import BUCKET_CROSS_REGION_TO_REGIONS_MAPPER, BUCKET_DATA_CENTER_TO_REGION_MAPPER
from ibm.common.utils import initialize_cos_client
from ibm.models import ibm_bucket_regions, IBMCloud, IBMCloudObjectStorage, IBMCOSBucket, IBMRegion, \
    IBMResourceLog, WorkflowTask
from ibm.tasks.celery_app import celery_app as celery
from ibm.tasks.common.tasks_base import IBMWorkflowTasksBase
from ibm.tasks.other.consts import COS_SERVICE_QUERY_PARAM, LANGUAGE


@celery.task(name="sync_cos", base=IBMWorkflowTasksBase)
def sync_cos(workflow_task_id):
    """
    Sync cloud object storage with IBM.
    """
    with get_db_session() as db_session:
        workflow_task = db_session.query(WorkflowTask).filter_by(id=workflow_task_id).first()
        if not workflow_task:
            return

        workflow_task.status = WorkflowTask.STATUS_RUNNING
        db_session.commit()

        resource_data = deepcopy(workflow_task.task_metadata["resource_data"])
        cloud_id = resource_data["cloud_id"]
        ibm_cloud = db_session.query(IBMCloud).filter_by(id=cloud_id).first()
        if not ibm_cloud:
            workflow_task.status = WorkflowTask.STATUS_FAILED
            workflow_task.message = f"IBMCloud '{cloud_id}' not found"
            db_session.commit()
            LOGGER.error(workflow_task.message)
            return

    try:
        client = GlobalCatalogsClient(cloud_id=cloud_id)
        global_storage_catalog = \
            client.return_parent_catalog_entries(keywords=COS_SERVICE_QUERY_PARAM, languages=LANGUAGE)
        if not global_storage_catalog:
            with get_db_session() as db_session:
                workflow_task = db_session.query(WorkflowTask).filter_by(id=workflow_task_id).first()
                if not workflow_task:
                    return

                workflow_task.status = WorkflowTask.STATUS_FAILED
                workflow_task.message = "No Global Catalog for cloud storage objects"
                db_session.commit()
                LOGGER.error(workflow_task.message)
                return

        offering_id = global_storage_catalog[0]["metadata"]["ui"]["primary_offering_id"]
        client = ResourceInstancesClient(cloud_id=cloud_id)
        fetched_cloud_object_storages_dicts_list = client.list_resource_instances(resource_id=offering_id)

        updated_cos_names = [cos_dict["name"] for cos_dict in fetched_cloud_object_storages_dicts_list]

    except ApiException as ex:
        with get_db_session() as db_session:
            workflow_task = db_session.query(WorkflowTask).filter_by(id=workflow_task_id).first()
            if not workflow_task:
                return

            workflow_task.status = WorkflowTask.STATUS_FAILED
            workflow_task.message = f"Method Failed. Reason: {str(ex.message)}"
            db_session.commit()
            LOGGER.fail(workflow_task.message)
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

        deletable_cos = db_session.query(IBMCloudObjectStorage).filter(
            IBMCloudObjectStorage.cloud_id == cloud_id, IBMCloudObjectStorage.name.not_in(updated_cos_names)
        ).all()
        for cos in deletable_cos:
            db_session.delete(cos)
            db_session.commit()

        db_cos_objects = db_session.query(IBMCloudObjectStorage).filter_by(cloud_id=cloud_id).all()
        db_cos_name_cos_obj_dict = {db_cos_object.name: db_cos_object for db_cos_object in db_cos_objects}

        for cos_dict in fetched_cloud_object_storages_dicts_list:
            parsed_cos = IBMCloudObjectStorage.from_ibm_json_body(cos_dict)
            if parsed_cos.name in db_cos_name_cos_obj_dict:
                db_cos = db_cos_name_cos_obj_dict[parsed_cos.name]
                db_cos.update_from_object(parsed_cos)
            else:
                parsed_cos.ibm_cloud = ibm_cloud

            db_session.commit()

        workflow_task.status = WorkflowTask.STATUS_SUCCESSFUL
        db_session.commit()

        db_cos = db_session.query(IBMCloudObjectStorage).filter_by(cloud_id=cloud_id).all()
        workflow_task.result = {"resource_json": [cos.to_json() for cos in db_cos]}
        db_session.commit()

    LOGGER.success(f"IBM Cloud Storage Objects for cloud {cloud_id} updated successfully.")


@celery.task(name="initiate_cos_buckets_sync", base=IBMWorkflowTasksBase)
def initiate_cos_buckets_sync(workflow_task_id):
    """
    Create Cos Bucket Sync tasks for a Region.
    """
    with get_db_session() as db_session:
        workflow_task = db_session.query(WorkflowTask).filter_by(id=workflow_task_id).first()
        if not workflow_task:
            return

        workflow_task.status = WorkflowTask.STATUS_RUNNING
        db_session.commit()

        cloud_id = workflow_task.task_metadata["cloud_id"]
        ibm_cloud = db_session.query(IBMCloud).filter_by(id=cloud_id).first()
        if not ibm_cloud:
            workflow_task.status = WorkflowTask.STATUS_FAILED
            workflow_task.message = f"IBMCloud '{cloud_id}' not found"
            db_session.commit()
            LOGGER.error(workflow_task.message)
            return

        region = db_session.query(IBMRegion).filter_by(cloud_id=cloud_id, ibm_status=IBMRegion.IBM_STATUS_AVAILABLE) \
            .first()
        if not region:
            workflow_task.status = WorkflowTask.STATUS_FAILED
            workflow_task.message = f"No available regions found for cloud {cloud_id}."
            db_session.commit()
            LOGGER.error(workflow_task.message)
            return

        cloud_storage_objects = db_session.query(IBMCloudObjectStorage).filter_by(cloud_id=cloud_id).all()
        for cos in cloud_storage_objects:
            sync_task = WorkflowTask(
                task_type=WorkflowTask.TYPE_SYNC, resource_type=IBMCOSBucket.__name__,
                task_metadata={
                    "resource_data": {
                        "cloud_object_storage_id": cos.id,
                        "cloud_id": cloud_id,
                        "region_id": region.id
                    }
                }
            )
            workflow_task.add_next_task(sync_task)
            db_session.commit()

        workflow_task.status = WorkflowTask.STATUS_SUCCESSFUL
        db_session.commit()
        LOGGER.success(f"COS Buckets synced successfully for IBM Cloud '{cloud_id}'")


@celery.task(name="sync_cos_buckets", base=IBMWorkflowTasksBase)
def sync_cos_buckets(workflow_task_id):
    """
    Sync IBM COS Buckets with IBM.
    """
    with get_db_session() as db_session:
        workflow_task = db_session.query(WorkflowTask).filter_by(id=workflow_task_id).first()
        if not workflow_task:
            return

        workflow_task.status = WorkflowTask.STATUS_RUNNING
        db_session.commit()

        resource_data = deepcopy(workflow_task.task_metadata["resource_data"])
        cloud_id = resource_data["cloud_id"]
        cloud_object_storage_id = resource_data["cloud_object_storage_id"]
        region_id = resource_data["region_id"]

        ibm_cloud = db_session.query(IBMCloud).filter_by(id=cloud_id).first()
        if not ibm_cloud:
            workflow_task.status = WorkflowTask.STATUS_FAILED
            workflow_task.message = f"IBMCloud '{cloud_id}' not found"
            db_session.commit()
            LOGGER.error(workflow_task.message)
            return

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

        cos = db_session.query(IBMCloudObjectStorage).filter_by(id=cloud_object_storage_id).first()
        if not cos:
            workflow_task.status = WorkflowTask.STATUS_FAILED
            workflow_task.message = f"IBM Cloud Object Storage '{cloud_object_storage_id}' not found"
            db_session.commit()
            LOGGER.error(workflow_task.message)
            return

        cos_crn = cos.crn
        region_name = region.name

    try:
        client = COSClient(cloud_id=cloud_id)
        fetched_bucket_dicts_list = client.list_cos_buckets(region=region_name, ibm_service_instance_id=cos_crn,
                                                            extended=True)
        updated_cos_bucket_names = [cos_bucket_dict["Name"] for cos_bucket_dict in fetched_bucket_dicts_list]

    except (IBMAuthError, IBMConnectError, IBMExecuteError, IBMInvalidRequestError) as ex:
        with get_db_session() as db_session:
            workflow_task = db_session.query(WorkflowTask).filter_by(id=workflow_task_id).first()
            if not workflow_task:
                return

            workflow_task.status = WorkflowTask.STATUS_FAILED
            workflow_task.message = "Method failed with error: " + str(ex)
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

        cos = db_session.query(IBMCloudObjectStorage).filter_by(id=cloud_object_storage_id).first()
        if not cos:
            workflow_task.status = WorkflowTask.STATUS_FAILED
            workflow_task.message = f"IBM Cloud Object Storage '{cloud_object_storage_id}' not found"
            db_session.commit()
            LOGGER.error(workflow_task.message)
            return

        deletable_buckets = db_session.query(IBMCOSBucket).filter(
            IBMCOSBucket.cloud_id == cloud_id, IBMCOSBucket.name.not_in(updated_cos_bucket_names),
            IBMCOSBucket.cloud_object_storage_id == cloud_object_storage_id).all()

        for bucket in deletable_buckets:
            db_session.delete(bucket)
            db_session.commit()

        db_cos_bucket_objs = db_session.query(IBMCOSBucket).filter_by(
            cloud_id=cloud_id, cloud_object_storage_id=cloud_object_storage_id).all()

        db_cos_bucket_name_cos_bucket_obj_dict = {db_cos_bucket_object.name: db_cos_bucket_object
                                                  for db_cos_bucket_object in db_cos_bucket_objs}

        for cos_bucket_dict in fetched_bucket_dicts_list:
            parsed_bucket = IBMCOSBucket.from_ibm_json_body(cos_bucket_dict)

            bucket_regions = list()
            if parsed_bucket.location_constraint in BUCKET_CROSS_REGION_TO_REGIONS_MAPPER:
                bucket_regions.extend(BUCKET_CROSS_REGION_TO_REGIONS_MAPPER[parsed_bucket.location_constraint])
            elif parsed_bucket.location_constraint in BUCKET_DATA_CENTER_TO_REGION_MAPPER:
                bucket_regions.extend(BUCKET_DATA_CENTER_TO_REGION_MAPPER[parsed_bucket.location_constraint])
            else:
                bucket_regions.append(parsed_bucket.location_constraint)

            regions = \
                db_session.query(IBMRegion).filter(
                    IBMRegion.name.in_(bucket_regions), IBMRegion.cloud_id == cloud_id
                ).all()
            if not regions:
                workflow_task.status = WorkflowTask.STATUS_FAILED
                workflow_task.message = f"Regions for location '{parsed_bucket.location_constraint}' not found"
                db_session.commit()
                LOGGER.error(workflow_task.message)
                return

            if parsed_bucket.name in db_cos_bucket_name_cos_bucket_obj_dict:
                db_cos_bucket = db_cos_bucket_name_cos_bucket_obj_dict[parsed_bucket.name]
                db_cos_bucket.update_from_obj(parsed_bucket)
                db_cos_bucket.regions = list()
                db_cos_bucket.regions = [region for region in regions]
            else:
                parsed_bucket.ibm_cloud = ibm_cloud
                parsed_bucket.cloud_object_storage = cos
                parsed_bucket.regions = [region for region in regions]

            db_session.commit()

        WorkflowTask.resource_id = cos.id
        workflow_task.status = WorkflowTask.STATUS_SUCCESSFUL
        db_session.commit()

        db_cos_buckets = db_session.query(IBMCOSBucket).filter_by(cloud_id=cloud_id).all()
        workflow_task.result = {"resource_json": [cos_bucket.to_json() for cos_bucket in db_cos_buckets]}
        db_session.commit()

    LOGGER.success(
        f"IBM COS Buckets for Storage Object {cloud_object_storage_id} synced successfully for region {region_name}."
    )


@celery.task(name="sync_cos_bucket_objects", base=IBMWorkflowTasksBase)
def sync_cos_bucket_objects(workflow_task_id):
    """
    Sync IBM COS Buckets objects from ibm.
    """
    with get_db_session() as db_session:
        workflow_task = db_session.query(WorkflowTask).filter_by(id=workflow_task_id).first()
        if not workflow_task:
            return

        workflow_task.status = WorkflowTask.STATUS_RUNNING
        db_session.commit()

        resource_data = deepcopy(workflow_task.task_metadata["resource_data"])
        bucket_id = resource_data["bucket_id"]

        bucket: IBMCOSBucket = db_session.query(IBMCOSBucket).filter_by(id=bucket_id).first()
        if not bucket:
            workflow_task.status = WorkflowTask.STATUS_FAILED
            workflow_task.message = f"IBMBucket '{bucket_id}' not found"
            db_session.commit()
            LOGGER.error(workflow_task.message)
            return

        region_name = bucket.location_constraint
        bucket_name = bucket.name
        cloud_id = bucket.ibm_cloud.id

    try:
        client = COSClient(cloud_id=cloud_id)
        bucket_objects = client.list_cos_bucket_objects(
            region=region_name, bucket=bucket_name
        )

    except (IBMAuthError, IBMConnectError, IBMExecuteError, IBMInvalidRequestError) as ex:
        with get_db_session() as db_session:
            workflow_task = db_session.query(WorkflowTask).filter_by(id=workflow_task_id).first()
            if not workflow_task:
                return

            workflow_task.status = WorkflowTask.STATUS_FAILED
            workflow_task.message = "Method failed with error: " + str(ex)
            db_session.commit()
            LOGGER.error(workflow_task.message)
        return

    with get_db_session() as db_session:
        workflow_task = db_session.query(WorkflowTask).filter_by(id=workflow_task_id).first()
        if not workflow_task:
            return

        workflow_task.status = WorkflowTask.STATUS_SUCCESSFUL
        workflow_task.resource_id = bucket_id
        workflow_task.result = {"resource_json": bucket_objects}
        db_session.commit()

    LOGGER.success(f"IBMBucket Objects synced for bucket {bucket_id} successfully.")


@celery.task(name="create_cos_bucket", base=IBMWorkflowTasksBase)
def create_cos_bucket(workflow_task_id):
    """
    Create An IBM COS Buckets.
    """
    with get_db_session() as db_session:
        workflow_task = db_session.query(WorkflowTask).filter_by(id=workflow_task_id).first()
        if not workflow_task:
            return

        workflow_task.status = WorkflowTask.STATUS_RUNNING
        db_session.commit()

        resource_data = deepcopy(workflow_task.task_metadata["resource_data"])
        cloud_id = resource_data["ibm_cloud"]["id"]
        region_id = resource_data["region"]["id"]
        bucket_name = resource_data["resource_json"]["name"]

        cloud = db_session.query(IBMCloud).filter_by(id=cloud_id).first()
        if not cloud:
            workflow_task.status = WorkflowTask.STATUS_FAILED
            workflow_task.message = f"IBMCloud {resource_data['cloud']} not found"
            db_session.commit()
            LOGGER.error(workflow_task.message)
            return
        cloud_id = cloud.id

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

        cloud_object_storage = db_session.query(IBMCloudObjectStorage).filter_by(
            **resource_data["resource_json"]["cloud_object_storage"]).first()
        if not cloud_object_storage:
            workflow_task.status = WorkflowTask.STATUS_FAILED
            workflow_task.message = f"IBMCloudObjectStorage {resource_data['cloud_object_storage']} not found"
            db_session.commit()
            LOGGER.error(workflow_task.message)
            return
        region_name = region.name
        crn = cloud_object_storage.crn
    try:
        client = COSClient(cloud_id=cloud_id)
        client.create_cos_bucket(
            region=region_name, bucket_name=bucket_name, ibm_service_instance_id=crn
        )
        bucket_response = client.list_cos_buckets(region=region_name, ibm_service_instance_id=crn, extended=True)
        for bucket in bucket_response:
            if bucket["Name"] == bucket_name:
                break

    except (IBMAuthError, IBMConnectError, IBMInvalidRequestError) as ex:
        with get_db_session() as db_session:
            workflow_task = db_session.query(WorkflowTask).filter_by(id=workflow_task_id).first()
            if not workflow_task:
                return

            workflow_task.status = WorkflowTask.STATUS_FAILED
            workflow_task.message = f"Creation Failed. Reason: {str(ex)}"
            db_session.commit()

        LOGGER.info(ex)
        return

    except IBMExecuteError as ex:
        with get_db_session() as db_session:
            workflow_task: WorkflowTask = db_session.get(WorkflowTask, workflow_task_id)
            if not workflow_task:
                return

            if ex.status_code == 409:
                workflow_task.status = WorkflowTask.STATUS_FAILED
                workflow_task.message = f"IBM COS Bucket with name {bucket_name} already exists on IBM Cloud."
                db_session.commit()
                return

    with get_db_session() as db_session:
        workflow_task = db_session.query(WorkflowTask).filter_by(id=workflow_task_id).first()
        if not workflow_task:
            return
        ibm_cloud = db_session.query(IBMCloud).filter_by(id=cloud_id).first()
        if not ibm_cloud:
            workflow_task.status = WorkflowTask.STATUS_FAILED
            workflow_task.message = \
                f"IBMCloud '{cloud_id}' not found"
            db_session.commit()
            LOGGER.info(workflow_task.message)
            return
        region = db_session.query(IBMRegion).filter_by(id=region_id, cloud_id=cloud_id).first()
        if not region:
            workflow_task.status = WorkflowTask.STATUS_FAILED
            workflow_task.message = f"IBMRegion '{region_id}' not found"
            db_session.commit()
            LOGGER.error(workflow_task.message)
            return
        cloud_object_storage = db_session.query(IBMCloudObjectStorage).filter_by(
            **resource_data["resource_json"]["cloud_object_storage"]).first()
        if not cloud_object_storage:
            workflow_task.status = WorkflowTask.STATUS_FAILED
            workflow_task.message = f"IBMCloudObjectStorage {resource_data['cloud_object_storage']} not found"
            db_session.commit()
            LOGGER.error(workflow_task.message)
            return

        with db_session.no_autoflush:
            bucket_obj = IBMCOSBucket.from_ibm_json_body(json_body=bucket)
            bucket_obj.ibm_cloud = ibm_cloud
            bucket_obj.cloud_object_storage = cloud_object_storage
            bucket_obj.regions.append(region)
            bucket_obj_json = bucket_obj.to_json()
            cos_bucket_name = f"{cloud_object_storage.crn}/{bucket_obj.name}"
            IBMResourceLog(
                resource_id=cos_bucket_name, region=region,
                status=IBMResourceLog.STATUS_ADDED, resource_type=IBMCOSBucket.__name__,
                data=bucket_obj_json)
            db_session.commit()

        workflow_task.resource_id = bucket_obj.id
        workflow_task.status = WorkflowTask.STATUS_SUCCESSFUL
        message = f"IBMBucket {bucket_name} created successfully."
        db_session.commit()

    LOGGER.success(message)


@celery.task(name="delete_cos_bucket", base=IBMWorkflowTasksBase)
def delete_cos_bucket(workflow_task_id):
    """
    DELETE An IBM COS Buckets.
    """
    with get_db_session() as db_session:
        workflow_task: WorkflowTask = db_session.get(WorkflowTask, workflow_task_id)
        if not workflow_task:
            return

        workflow_task.status = WorkflowTask.STATUS_RUNNING
        db_session.commit()

        cos_bucket_id = workflow_task.resource_id
        cos_bucket = db_session.query(IBMCOSBucket).filter_by(
            id=cos_bucket_id).first()
        if not cos_bucket:
            workflow_task.status = WorkflowTask.STATUS_FAILED
            workflow_task.message = \
                f"IBMCosBucket '{cos_bucket_id}' not found"
            db_session.commit()
            LOGGER.info(workflow_task.message)
            return
        bucket_name = cos_bucket.name
        bucket_id = cos_bucket.id
        api_key = cos_bucket.ibm_cloud.api_key

        # TODO we have to handle cross regional buckets as well
        cos_bucket_region = db_session.query(ibm_bucket_regions).filter_by(
            bucket_id=cos_bucket_id).first()
        if not cos_bucket_region:
            workflow_task.status = WorkflowTask.STATUS_FAILED
            workflow_task.message = \
                f"IBMCosBucketRegion '{cos_bucket_id}' not found"
            db_session.commit()
            LOGGER.info(workflow_task.message)
            return

        cos_bucket_region_id = cos_bucket_region.region_id

        region = db_session.query(IBMRegion).filter_by(id=cos_bucket_region_id).first()
        if not region:
            workflow_task.status = WorkflowTask.STATUS_FAILED
            workflow_task.message = f"IBMRegion '{cos_bucket_region_id}' not found"
            db_session.commit()
            LOGGER.error(workflow_task.message)
            return

        region_name = region.name
        crn = cos_bucket.cloud_object_storage.crn
    try:
        client = initialize_cos_client(ibm_api_key_id=api_key, ibm_service_instance_id=crn, region=region_name)
        # List all objects in the COS bucket
        objects = client.list_objects_v2(Bucket=bucket_name)

        # Delete all objects in the COS bucket
        if "Contents" in objects:
            delete_objects = {"Objects": [{"Key": obj["Key"]} for obj in objects["Contents"]]}
            client.delete_objects(Bucket=bucket_name, Delete=delete_objects)

        # Delete the COS bucket
        client.delete_bucket(Bucket=bucket_name)

    except boto3.exceptions.botocore.exceptions.ClientError as ex:
        with get_db_session() as db_session:
            workflow_task: WorkflowTask = db_session.query(WorkflowTask).get(workflow_task_id)
            if not workflow_task:
                return

            workflow_task.status = WorkflowTask.STATUS_FAILED
            workflow_task.message = f"Deletion Failed. Reason: {str(ex)}"
            db_session.commit()

            LOGGER.error(str(ex))
            return

    except Exception as ex:
        error_code = ex.response["Error"]["Code"]

        with get_db_session() as db_session:
            workflow_task: WorkflowTask = db_session.query(WorkflowTask).get(workflow_task_id)
            if not workflow_task:
                return
            region = db_session.query(IBMRegion).filter_by(id=cos_bucket_region_id).first()
            if not region:
                workflow_task.status = WorkflowTask.STATUS_FAILED
                workflow_task.message = f"IBMRegion '{cos_bucket_region_id}' not found"
                db_session.commit()
                LOGGER.error(workflow_task.message)
                return

            if error_code == "NoSuchBucket":
                cos_bucket = db_session.query(IBMCOSBucket).get(workflow_task.resource_id)
                if cos_bucket:
                    cos_bucket_json = cos_bucket.to_json()
                    cos_bucket_json["created_at"] = str(cos_bucket_json["created_at"])
                    cos_bucket_name = f"{cos_bucket.cloud_object_storage.crn}/{cos_bucket.name}"
                    IBMResourceLog(
                        resource_id=cos_bucket_name, region=region,
                        status=IBMResourceLog.STATUS_DELETED, resource_type=IBMCOSBucket.__name__,
                        data=cos_bucket_json)

                    db_session.delete(cos_bucket)

                workflow_task.status = WorkflowTask.STATUS_SUCCESSFUL
                LOGGER.success(
                    f"IBM COS BUCKET {workflow_task.resource_id} deletion successful.")
                db_session.commit()
                return
            else:
                workflow_task.status = WorkflowTask.STATUS_FAILED
                message = f"Cannot delete COS BUCKET {workflow_task.resource_id} due to reason: {str(ex)}"
                workflow_task.message = message
                db_session.commit()
                LOGGER.error(message)
                return
    with get_db_session() as db_session:
        workflow_task = db_session.query(WorkflowTask).filter_by(id=workflow_task_id).first()
        if not workflow_task:
            return

        cos_bucket = db_session.query(IBMCOSBucket).filter_by(id=bucket_id).first()
        cos_bucket_name = ""
        if cos_bucket:
            cos_bucket_name = f"{cos_bucket.cloud_object_storage.crn}/{cos_bucket.name}"

        region = db_session.query(IBMRegion).filter_by(id=cos_bucket_region_id).first()
        if not region:
            workflow_task.status = WorkflowTask.STATUS_FAILED
            workflow_task.message = f"IBMRegion '{cos_bucket_region_id}' not found"
            db_session.commit()
            LOGGER.error(workflow_task.message)
            return

        IBMResourceLog(
            resource_id=cos_bucket_name, region=region,
            status=IBMResourceLog.STATUS_DELETED, resource_type=IBMCOSBucket.__name__,
            data=cos_bucket.to_json())
        db_session.delete(cos_bucket)
        workflow_task.status = WorkflowTask.STATUS_SUCCESSFUL
        db_session.commit()

    LOGGER.success(f"IBMBucket {bucket_name} DELETED successfully.")
