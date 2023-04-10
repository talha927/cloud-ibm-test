import logging

from apiflask import abort, APIBlueprint, input, output

from ibm.auth import authenticate
from ibm.common.req_resp_schemas.schemas import get_pagination_schema, IBMResourceQuerySchema, PaginationQuerySchema, \
    WorkflowRootOutSchema
from ibm.models import IBMCloudObjectStorage, IBMCOSBucket, IBMRegion, IBMServiceCredentialKey, WorkflowTask
from ibm.web import db as ibmdb
from ibm.web.common.utils import authorize_and_get_ibm_cloud, compose_ibm_sync_resource_workflow, \
    get_paginated_response_json, verify_and_get_region, create_ibm_resource_creation_workflow, \
    compose_ibm_resource_deletion_workflow, verify_references
from .schemas import IBMCosBucketOutSchema, IBMCosBucketResourceSchema, IBMCosBucketsListQuerySchema, \
    IBMCosBucketSyncSchema, \
    IBMCosKeyListQuerySchema, IBMCOSKeyOutSchema, IBMCosOutSchema, IBMCosBucketInSchema

LOGGER = logging.getLogger(__name__)

ibm_cloud_object_storages = APIBlueprint('ibm_cloud_object_storages', __name__, tag="IBM Cloud Object Storage")


@ibm_cloud_object_storages.post('/cloud_object_storages/sync')
@authenticate
@input(IBMResourceQuerySchema, location='query')
@output(WorkflowRootOutSchema, status_code=202)
def sync_cloud_object_storage(cloud_sync_param, user):
    """
    Sync Cloud Object Storage with  IBM.
    This request creates an IBM Cloud Object Storage.
    """
    cloud_id = cloud_sync_param["cloud_id"]
    authorize_and_get_ibm_cloud(cloud_id=cloud_id, user=user)

    workflow_root = compose_ibm_sync_resource_workflow(user=user, resource_type=IBMCloudObjectStorage,
                                                       data=cloud_sync_param)

    initiate_bucket_tasks = WorkflowTask(
        task_type="SYNC-INITIATE", resource_type=IBMCOSBucket.__name__, task_metadata={"cloud_id": cloud_id}
    )
    creation_task = workflow_root.next_tasks[0]
    creation_task.add_next_task(initiate_bucket_tasks)

    ibmdb.session.commit()

    return workflow_root.to_json()


@ibm_cloud_object_storages.get('/cloud_object_storages')
@authenticate
@input(PaginationQuerySchema, location='query')
@input(IBMResourceQuerySchema, location='query')
@output(get_pagination_schema(IBMCosOutSchema))
def list_ibm_cloud_object_storages(pagination_query_params, cloud_res_query_params, user):
    """
    List IBM Cloud Storage Object
    This request lists all IBM  Cloud Storage Object for the given cloud id.
    """
    cloud_id = cloud_res_query_params["cloud_id"]
    authorize_and_get_ibm_cloud(cloud_id=cloud_id, user=user)

    cloud_object_storage_query = ibmdb.session.query(IBMCloudObjectStorage).filter_by(cloud_id=cloud_id)
    cloud_object_storage_page = cloud_object_storage_query.paginate(
        page=pagination_query_params["page"], per_page=pagination_query_params["per_page"], error_out=False
    )
    if not cloud_object_storage_page.items:
        return '', 204

    return get_paginated_response_json(
        items=[item.to_json() for item in cloud_object_storage_page.items],
        pagination_obj=cloud_object_storage_page
    )


@ibm_cloud_object_storages.get('/cloud_object_storages/<cloud_object_storages_id>')
@authenticate
@output(IBMCosOutSchema)
def get_ibm_cloud_object_storage(cloud_object_storages_id, user):
    """
    Get IBM Cloud Storage Object
    This request returns an IBM Cloud Object Storage provided its ID.
    """
    cloud_object_storage = ibmdb.session.query(IBMCloudObjectStorage).filter_by(id=cloud_object_storages_id).first()
    if not cloud_object_storage:
        message = f"IBM Cloud Storage Object with ID {cloud_object_storages_id}, does not exist"
        LOGGER.debug(message)
        abort(404, message)

    authorize_and_get_ibm_cloud(cloud_id=cloud_object_storage.ibm_cloud.id, user=user)

    return cloud_object_storage.to_json()


@ibm_cloud_object_storages.post('/cloud_object_storages/buckets/sync')
@authenticate
@input(IBMCosBucketSyncSchema, location='query')
@output(WorkflowRootOutSchema, status_code=202)
def sync_cos_buckets(cos_resource_schema, user):
    """
    Sync COS Bucket with  IBM.
    This request syncs an IBM COS Buckets.
    """
    cloud_id = cos_resource_schema["cloud_id"]
    region_id = cos_resource_schema["region_id"]
    cloud_object_storage_id = cos_resource_schema["cloud_object_storage_id"]
    ibm_cloud = authorize_and_get_ibm_cloud(cloud_id=cloud_id, user=user)
    verify_and_get_region(ibm_cloud=ibm_cloud, region_id=region_id)

    cloud_object_storage = ibmdb.session.query(IBMCloudObjectStorage).filter_by(id=cloud_object_storage_id).first()
    if not cloud_object_storage:
        message = f"IBM Cloud Object Storage with ID {cloud_object_storage_id}, does not exist"
        LOGGER.debug(message)
        abort(404, message)

    workflow_root = compose_ibm_sync_resource_workflow(user=user, resource_type=IBMCOSBucket,
                                                       data=cos_resource_schema)

    return workflow_root.to_json()


@ibm_cloud_object_storages.get('/cloud_object_storages/buckets')
@authenticate
@input(IBMCosBucketsListQuerySchema, location="query")
@input(PaginationQuerySchema, location='query')
@output(get_pagination_schema(IBMCosBucketOutSchema))
def list_ibm_cos_buckets(cos_res_query_param, pagination_query_params, user):
    """
    List IBM COS Buckets
    This request returns an IBM COS Buckets on a cloud.
    """
    cloud_id = cos_res_query_param["cloud_id"]
    cloud_object_storage_id = cos_res_query_param.get("cloud_object_storage_id")
    region_id = cos_res_query_param.get("region_id")
    resiliency = cos_res_query_param.get("resiliency")
    is_sorted = cos_res_query_param.get("is_sorted")

    ibm_cloud = authorize_and_get_ibm_cloud(cloud_id=cloud_id, user=user)
    cos_bucket_query = ibmdb.session.query(IBMCOSBucket).filter_by(cloud_id=cloud_id)

    if cloud_object_storage_id:
        cos = ibmdb.session.query(IBMCloudObjectStorage).filter_by(id=cloud_object_storage_id).first()
        if not cos:
            message = f"IBM Cloud Object Storage with ID {cloud_object_storage_id}, does not exist"
            LOGGER.debug(message)
            abort(404, message)

        cos_bucket_query = cos_bucket_query.filter_by(cloud_object_storage_id=cloud_object_storage_id)

    if region_id:
        verify_and_get_region(ibm_cloud=ibm_cloud, region_id=region_id)
        cos_bucket_query = cos_bucket_query.filter(IBMCOSBucket.regions.any(IBMRegion.id == region_id))

    if resiliency:
        cos_bucket_query = cos_bucket_query.filter_by(resiliency=resiliency)

    if is_sorted:

        cos_bucket_query = cos_bucket_query.order_by(IBMCOSBucket.created_at.desc())

    cos_buckets = cos_bucket_query.paginate(
        page=pagination_query_params["page"], per_page=pagination_query_params["per_page"], error_out=False
    )

    if not cos_buckets.items:
        return '', 204

    return get_paginated_response_json(
        items=[item.to_json() for item in cos_buckets.items],
        pagination_obj=cos_buckets
    )


@ibm_cloud_object_storages.get('/cloud_object_storages/buckets/<bucket_id>')
@authenticate
@output(IBMCosBucketOutSchema)
def get_ibm_cos_bucket(bucket_id, user):
    """
    Get IBM COS Bucket
    This request returns an IBM COS Bucket provided its ID.
    """
    cos_bucket = ibmdb.session.query(IBMCOSBucket).filter_by(id=bucket_id).first()
    if not cos_bucket:
        message = f"IBM COS Bucket with ID {bucket_id}, does not exist"
        LOGGER.debug(message)
        abort(404, message)

    authorize_and_get_ibm_cloud(cloud_id=cos_bucket.ibm_cloud.id, user=user)
    return cos_bucket.to_json()


@ibm_cloud_object_storages.put('/cloud_object_storages/buckets')
@authenticate
@input(IBMCosBucketInSchema)
@output(WorkflowRootOutSchema)
def create_ibm_cos_bucket(data, user):
    """
    CREATE An IBM COS Bucket
    This request returns an IBM Workflow Root Created ID.
    """

    cloud_id = data["ibm_cloud"]["id"]
    region_id = data["region"]["id"]

    ibm_cloud = authorize_and_get_ibm_cloud(cloud_id=cloud_id, user=user)
    verify_and_get_region(ibm_cloud=ibm_cloud, region_id=region_id)

    verify_references(
        cloud_id=cloud_id, body_schema=IBMCosBucketInSchema, resource_schema=IBMCosBucketResourceSchema,
        data=data
    )

    cloud_object_storage = ibmdb.session.query(
        IBMCloudObjectStorage).filter_by(**data["resource_json"]["cloud_object_storage"]).first()
    if not cloud_object_storage:
        message = f"IBM Cloud Object Storage with {data['cloud_object_storage']} does not exist"
        LOGGER.debug(message)
        abort(404, message)

    workflow_root = create_ibm_resource_creation_workflow(user=user, resource_type=IBMCOSBucket, data=data,
                                                          validate=False)
    return workflow_root.to_json()


@ibm_cloud_object_storages.delete('/cloud_object_storages/buckets/<bucket_id>')
@authenticate
@output(WorkflowRootOutSchema, status_code=202)
def delete_ibm_cos_bucket(bucket_id, user):
    """
    DELETE An IBM COS Bucket
    This request returns an IBM Workflow Root Created ID.
    """
    cos = ibmdb.session.query(IBMCOSBucket).filter_by(
        id=bucket_id
    ).join(IBMCOSBucket.ibm_cloud).filter_by(
        user_id=user["id"], project_id=user["project_id"], deleted=False
    ).first()
    if not cos:
        message = f"IBM COS Bucket with ID: {bucket_id} does not exist"
        LOGGER.debug(message)
        abort(404, message)

    workflow_root = compose_ibm_resource_deletion_workflow(user=user, resource_type=IBMCOSBucket,
                                                           resource_id=bucket_id)
    return workflow_root.to_json()


@ibm_cloud_object_storages.post('/cloud_object_storages/buckets/<bucket_id>/objects/sync')
@authenticate
@output(WorkflowRootOutSchema, status_code=202)
def sync_ibm_cos_bucket_objects(bucket_id, user):
    """
    Sync IBM COS Bucket Objects
    This request returns an IBM COS Bucket provided its ID.
    """
    cos_bucket: IBMCOSBucket = ibmdb.session.query(IBMCOSBucket).filter_by(id=bucket_id).first()
    if not cos_bucket:
        message = f"IBM COS Bucket with ID {bucket_id}, does not exist"
        LOGGER.debug(message)
        abort(404, message)

    authorize_and_get_ibm_cloud(cloud_id=cos_bucket.ibm_cloud.id, user=user)
    if cos_bucket.resiliency != IBMCOSBucket.RESILIENCY_REGIONAL:
        message = f"IBM COS Bucket with ID {bucket_id}, is not a regional bucket."
        LOGGER.debug(message)
        abort(404, message)

    workflow_root = compose_ibm_sync_resource_workflow(
        user=user, resource_type="IBMCOSBucketObject",
        data={"bucket_id": bucket_id})

    return workflow_root.to_json()


@ibm_cloud_object_storages.post('/cloud_object_storages/keys/sync')
@authenticate
@input(IBMResourceQuerySchema, location="query")
@output(WorkflowRootOutSchema, status_code=202)
def sync_ibm_cos_keys(cloud_param, user):
    """
    Sync IBM COS Keys (secret and access keys)
    This request returns an IBM COS Keys.
    """
    cloud_id = cloud_param["cloud_id"]
    authorize_and_get_ibm_cloud(cloud_id=cloud_id, user=user)

    workflow_root = compose_ibm_sync_resource_workflow(
        user=user, resource_type=IBMServiceCredentialKey,
        data=cloud_param)

    return workflow_root.to_json()


@ibm_cloud_object_storages.get('/cloud_object_storages/keys')
@authenticate
@input(IBMCosKeyListQuerySchema, location="query")
@input(PaginationQuerySchema, location='query')
@output(get_pagination_schema(IBMCOSKeyOutSchema))
def list_ibm_cos_keys(cos_res_query_param, pagination_query_params, user):
    """
    List IBM COS Service Credential Keys
    This request returns an IBM COS Service Credential Keys on a cloud.
    """
    cloud_id = cos_res_query_param["cloud_id"]
    cloud_object_storage_id = cos_res_query_param.get("cloud_object_storage_id")
    is_hmac = cos_res_query_param.get("is_hmac")
    role = cos_res_query_param.get("role")

    authorize_and_get_ibm_cloud(cloud_id=cloud_id, user=user)
    cos_key_query = ibmdb.session.query(IBMServiceCredentialKey).filter_by(cloud_id=cloud_id)

    if cloud_object_storage_id:
        cos = ibmdb.session.query(IBMCloudObjectStorage).filter_by(id=cloud_object_storage_id).first()
        if not cos:
            message = f"IBM Cloud Object Storage with ID {cloud_object_storage_id}, does not exist"
            LOGGER.debug(message)
            abort(404, message)

        cos_key_query = cos_key_query.filter_by(cloud_object_storage_id=cloud_object_storage_id)

    if is_hmac is not None:
        cos_key_query = cos_key_query.filter_by(is_hmac=is_hmac)

    if role:
        cos_key_query = cos_key_query.filter_by(role=role)

    cos_keys = cos_key_query.paginate(
        page=pagination_query_params["page"], per_page=pagination_query_params["per_page"], error_out=False
    )

    if not cos_keys.items:
        return '', 204

    return get_paginated_response_json(
        items=[item.to_json() for item in cos_keys.items],
        pagination_obj=cos_keys
    )


@ibm_cloud_object_storages.get('/cloud_object_storages/keys/<key_id>')
@authenticate
@output(IBMCOSKeyOutSchema)
def get_ibm_cos_key(key_id, user):
    """
    Get IBM COS Service Credential Key
    This request returns an IBM COS Service Credential Key provided its ID.
    """
    cos_key = ibmdb.session.query(IBMServiceCredentialKey).filter_by(id=key_id).first()
    if not cos_key:
        message = f"IBM COS Key with ID {key_id}, does not exist"
        LOGGER.debug(message)
        abort(404, message)

    authorize_and_get_ibm_cloud(cloud_id=cos_key.ibm_cloud.id, user=user)
    return cos_key.to_json()
