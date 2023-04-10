import logging

from apiflask import abort, APIBlueprint, input, output
from flask import Response

from ibm.auth import authenticate, authenticate_api_key
from ibm.common.req_resp_schemas.schemas import get_pagination_schema, IBMResourceQuerySchema, PaginationQuerySchema, \
    WorkflowRootOutSchema
from ibm.middleware import log_activity
from ibm.models import IBMCloud, IBMImage, IBMOperatingSystem, IBMRegion, ImageConversionTask, WorkflowRoot, \
    WorkflowTask
from ibm.web import db as ibmdb
from ibm.web.common.utils import authorize_and_get_ibm_cloud, compose_ibm_resource_deletion_workflow, \
    create_ibm_resource_creation_workflow, get_paginated_response_json, verify_and_get_region, verify_references
from ibm.web.ibm.images.consts import ALL_VENDORS_DICT
from ibm.web.ibm.images.schemas import IBMCustomImageInSchema, IBMImageInSchema, \
    IBMImageMigrationUpdateSchema, \
    IBMImageOutSchema, \
    IBMImageResourceSchema, IBMImageUpdateSchema, IBMImageVisibilitySchema, IBMOperatingSystemMappingInSchema, \
    IBMOperatingSystemMappingOutSchema, IBMOperatingSystemOutSchema, IBMOperatingSystemProvidersSchema, \
    IBMOperatingSystemQuerySchema
from ibm.web.softlayer.instances.utils import return_operating_system_objects

LOGGER = logging.getLogger(__name__)

ibm_images = APIBlueprint('ibm_images', __name__, tag="IBM Images")


@ibm_images.post("/images")
@authenticate
@log_activity
@input(IBMImageInSchema)
@output(WorkflowRootOutSchema, status_code=202)
def create_ibm_image(data, user):
    """
    Create IBM Images
    This request creates an IBM Image
    """
    cloud_id = data["ibm_cloud"]["id"]
    region_id = data["region"]["id"]

    ibm_cloud = authorize_and_get_ibm_cloud(cloud_id=cloud_id, user=user)
    verify_and_get_region(ibm_cloud=ibm_cloud, region_id=region_id)

    verify_references(
        cloud_id=cloud_id, body_schema=IBMImageInSchema, resource_schema=IBMImageResourceSchema, data=data
    )

    workflow_root = create_ibm_resource_creation_workflow(
        user=user, resource_type=IBMImage, data=data, validate=False
    )
    return workflow_root.to_json()


@ibm_images.get('/images')
@authenticate
@input(IBMImageVisibilitySchema, location='query')
@input(PaginationQuerySchema, location='query')
@output(get_pagination_schema(IBMImageOutSchema))
def list_ibm_images(regional_res_query_params, pagination_query_params, user):
    """
    List IBM Images
    This requests list all IBM Images for a given cloud
    """
    cloud_id = regional_res_query_params["cloud_id"]
    region_id = regional_res_query_params.get("region_id")
    visibility = regional_res_query_params.get("visibility")
    vendor = regional_res_query_params.get("vendor")

    ibm_cloud = authorize_and_get_ibm_cloud(cloud_id=cloud_id, user=user)
    filters = {"cloud_id": cloud_id}

    if region_id:
        verify_and_get_region(ibm_cloud=ibm_cloud, region_id=region_id)
        filters["region_id"] = region_id
    if visibility:
        filters["visibility"] = visibility

    images_query = ibmdb.session.query(IBMImage).filter_by(**filters)
    if vendor:
        vendor = ALL_VENDORS_DICT[vendor]
        images_query = images_query.join(IBMImage.operating_system).filter_by(vendor=vendor)
    images_page = images_query.paginate(
        page=pagination_query_params["page"], per_page=pagination_query_params["per_page"], error_out=False
    )
    if not images_page.items:
        return '', 204

    return get_paginated_response_json(
        items=[item.to_json() for item in images_page.items],
        pagination_obj=images_page
    )


@ibm_images.get('/images/<image_id>')
@authenticate
@output(IBMImageOutSchema)
def get_ibm_image(image_id, user):
    """
    Get IBM Image
    This request returns an IBM Image its ID
    """
    image = ibmdb.session.query(IBMImage).filter_by(
        id=image_id
    ).join(IBMImage.ibm_cloud).filter_by(
        user_id=user["id"], project_id=user["project_id"], deleted=False
    ).first()
    if not image:
        message = f"IBM Image {image_id} does not exist"
        LOGGER.debug(message)
        abort(404, message)

    return image.to_json()


@ibm_images.delete('/images/<image_id>')
@authenticate
@log_activity
@output(WorkflowRootOutSchema, status_code=202)
def delete_ibm_image(image_id, user):
    """
    Delete IBM Image
    This request deletes an IBM Image
    """
    image = ibmdb.session.query(IBMImage).filter_by(
        id=image_id
    ).join(IBMImage.ibm_cloud).filter_by(
        user_id=user["id"], project_id=user["project_id"], deleted=False
    ).first()
    if not image:
        message = f"IBM Image {image} does not exist"
        LOGGER.debug(message)
        abort(404, message)

    return compose_ibm_resource_deletion_workflow(
        user=user, resource_type=IBMImage, resource_id=image_id
    ).to_json(metadata=True)


@ibm_images.patch('/images/<image_id>')
@authenticate
@input(IBMImageUpdateSchema, location='json')
@output(WorkflowRootOutSchema, status_code=202)
def update_ibm_image(image_id, data, user):
    """
    Update IBM Image
    This request updates an IBM Image
    """
    abort(404)


@ibm_images.get('/operating_systems')
@authenticate
@input(PaginationQuerySchema, location='query')
@input(IBMOperatingSystemQuerySchema, location='query')
@output(get_pagination_schema(IBMOperatingSystemOutSchema))
def list_ibm_operating_systems(pagination_query_params, regional_res_query_params, user):
    """
    List IBM Operating Systems
    This requests list all IBM Operating Systems for a given cloud
    """
    cloud_id = regional_res_query_params["cloud_id"]
    region_id = regional_res_query_params.get("region_id")
    family = regional_res_query_params.get("family")
    vendor = regional_res_query_params.get("vendor")
    architecture = regional_res_query_params.get("architecture")
    dedicated_host_only = regional_res_query_params.get("dedicated_host_only")

    ibm_cloud = authorize_and_get_ibm_cloud(cloud_id=cloud_id, user=user)
    filters = {"cloud_id": cloud_id}

    if region_id:
        verify_and_get_region(ibm_cloud=ibm_cloud, region_id=region_id)
        filters["region_id"] = region_id

    if family:
        assert family in IBMOperatingSystem.ALL_FAMILIES
        filters["family"] = family
    if vendor:
        vendor = ALL_VENDORS_DICT[vendor]
        assert vendor in IBMOperatingSystem.ALL_VENDORS
        filters["vendor"] = vendor
    if architecture:
        assert architecture in IBMOperatingSystem.ALL_ARCHITECTURES
        filters["architecture"] = architecture
    if dedicated_host_only:
        filters["dedicated_host_only"] = dedicated_host_only

    operating_systems_query = ibmdb.session.query(IBMOperatingSystem).filter_by(**filters).order_by(
        IBMOperatingSystem.vendor)
    oss_page = operating_systems_query.paginate(
        page=pagination_query_params["page"], per_page=pagination_query_params["per_page"], error_out=False
    )
    if not oss_page.items:
        return '', 204

    return get_paginated_response_json(
        items=[item.to_json() for item in oss_page.items],
        pagination_obj=oss_page
    )


@ibm_images.get('/operating_systems/<operating_system_id>')
@authenticate
@output(IBMOperatingSystemOutSchema)
def get_ibm_operating_system(operating_system_id, user):
    """
    Get IBM Operating System
    This request returns an IBM Operating System its ID
    """
    operating_system = ibmdb.session.query(IBMOperatingSystem).filter_by(
        id=operating_system_id
    ).join(IBMOperatingSystem.ibm_cloud).filter_by(
        user_id=user["id"], project_id=user["project_id"], deleted=False
    ).first()
    if not operating_system:
        message = f"IBM Operating System {operating_system_id} does not exist"
        LOGGER.debug(message)
        abort(404, message)

    return operating_system.to_json()


@ibm_images.route('/image_conversion/<task_id>', methods=['PATCH'])
@input(IBMImageMigrationUpdateSchema)
def update_image_conversion_task(task_id, data):
    """
    Webhook for image conversion script to update statuses
    :param task_id: <string> id of the ImageConversionTask to be updated

    :return: requests.Response object
    """
    LOGGER.info(data)
    LOGGER.info(task_id)
    task = ibmdb.session.query(ImageConversionTask).filter_by(id=task_id).first()
    if not task:
        return '', 204

    if data["status"] == ImageConversionTask.STATUS_FAILED:
        task.status = ImageConversionTask.STATUS_FAILED
        task.message = data["message"]
        ibmdb.session.commit()
        return '', 200

    if data["step"] == "DOWNLOAD":
        task.step = ImageConversionTask.STEP_IMAGE_CONVERTING
    elif data["step"] == "CONVERT":
        task.step = ImageConversionTask.STEP_IMAGE_VALIDATING
    elif data["step"] == "VALIDATE":
        task.step = ImageConversionTask.STEP_IMAGE_UPLOADING
    elif data["step"] == "UPLOAD":
        task.step = ImageConversionTask.STEP_PENDING_CLEANUP
    ibmdb.session.commit()

    return '', 200


@ibm_images.get('/operating_systems/providers')
@authenticate
@input(IBMResourceQuerySchema, location='query')
@output(IBMOperatingSystemProvidersSchema)
def list_operating_system_vendors(regional_res_query_params, user):
    """
    List IBM Operating System Vendors and Families
    This request returns IBM Operating System Vendors and Families
    """
    cloud_id = regional_res_query_params["cloud_id"]

    authorize_and_get_ibm_cloud(cloud_id=cloud_id, user=user)
    operating_systems = ibmdb.session.query(IBMOperatingSystem.vendor, IBMOperatingSystem.family).join(
        IBMOperatingSystem.ibm_cloud
    ).filter_by(
        user_id=user["id"], project_id=user["project_id"], deleted=False
    ).distinct().all()
    return {
        "vendors": [vendor.vendor for vendor in operating_systems],
        "families": [family.family for family in operating_systems]
    }


@ibm_images.post('/operating_systems/mapping')
@authenticate
@input(IBMOperatingSystemMappingInSchema)
@output(IBMOperatingSystemMappingOutSchema)
def list_operating_system_mapping(data, user):
    """
    List IBM Operating System Mapping
    This request returns IBM Operating System and Images mapped value from softlayer to VPC Gen2
    """
    operating_systems = []
    region_id = data["region_id"]
    for os in set(data["names"]):
        operating_systems.append({"name": os, "values": return_operating_system_objects(
            region_id=region_id, image_name=os, architecture=True
        )})
    return {"items": operating_systems}


@ibm_images.post('/custom-image')
@authenticate_api_key
@input(IBMCustomImageInSchema)
@output(WorkflowRootOutSchema, status_code=202)
def store_ibm_custom_image(data):
    """
    Store Custom Image
    This request stores a custom image on IBM Cloud
    """
    cloud_id = data["cloud_id"]
    region = data["region"]
    image_name = data["image_name"]

    ibm_cloud = ibmdb.session.query(IBMCloud).filter_by(id=cloud_id).first()
    if not ibm_cloud:
        LOGGER.info(f"No IBM Cloud found with id {cloud_id}")
        return

    project_id = ibm_cloud.project_id
    user_id = ibm_cloud.user_id

    region = ibmdb.session.query(IBMRegion).filter_by(cloud_id=cloud_id, name=region).first()
    if not region:
        LOGGER.info(f"No IBM Region found with name {region} and cloud id {cloud_id}")
        return

    image = ibmdb.session.query(IBMImage).filter_by(
        name=image_name, visibility=IBMImage.TYPE_VISIBLE_PRIVATE, cloud_id=cloud_id
    ).first()

    if image:
        message = f"IBM Image with name '{image_name}' already exists in DB"
        return Response(message, status=200)

    workflow_root = WorkflowRoot(
        user_id=user_id,
        project_id=project_id,
        workflow_name=IBMImage.__name__,
        workflow_nature="DISCOVERY"
    )
    workflow_task = WorkflowTask(
        task_type=WorkflowTask.TYPE_DISCOVERY,
        resource_type=IBMImage.__name__,
        task_metadata={"resource_data": data}
    )
    workflow_root.add_next_task(workflow_task)
    ibmdb.session.add(workflow_root)
    ibmdb.session.commit()
    return workflow_root.to_json(metadata=True)
