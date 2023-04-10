import logging

from apiflask import abort, APIBlueprint, input, output

from ibm.auth import authenticate
from ibm.common.req_resp_schemas.schemas import get_pagination_schema, IBMInstanceQuerySchema, PaginationQuerySchema, \
    WorkflowRootOutSchema
from ibm.models import IBMCloud, IBMInstance, IBMVolumeAttachment
from ibm.web import db as ibmdb
from ibm.web.common.utils import authorize_and_get_ibm_cloud, compose_ibm_resource_deletion_workflow, \
    create_ibm_resource_creation_workflow, get_paginated_response_json, verify_and_get_region, verify_references
from .schemas import IBMVolumeAttachmentInSchema, IBMVolumeAttachmentOutSchema, IBMVolumeAttachmentResourceSchema, \
    IBMVolumeAttachmentUpdateSchema

LOGGER = logging.getLogger(__name__)

ibm_volume_attachments = APIBlueprint('ibm_volume_attachments', __name__, tag="IBM Volume Attachments")


@ibm_volume_attachments.post('/volume_attachments')
@authenticate
@input(IBMVolumeAttachmentInSchema)
@output(WorkflowRootOutSchema, status_code=202)
def create_ibm_volume_attachment(data, user):
    """
    Create IBM Volume Attachment
    This request create a volume on IBM Cloud
    """
    cloud_id = data["ibm_cloud"]["id"]
    region_id = data["region"]["id"]
    instance_id = data["instance"]["id"]
    ibm_cloud = authorize_and_get_ibm_cloud(cloud_id=cloud_id, user=user)
    verify_and_get_region(ibm_cloud=ibm_cloud, region_id=region_id)
    instance = ibmdb.session.query(IBMInstance).filter_by(
        id=instance_id, region_id=region_id, cloud_id=cloud_id
    ).first()
    if not instance:
        message = f"IBM Instance {instance_id} not found"
        LOGGER.debug(message)
        abort(404, message)

    verify_references(
        cloud_id=cloud_id, body_schema=IBMVolumeAttachmentInSchema, resource_schema=IBMVolumeAttachmentResourceSchema,
        data=data
    )
    workflow_root = create_ibm_resource_creation_workflow(
        user=user, resource_type=IBMVolumeAttachment, data=data, validate=False
    )
    return workflow_root.to_json()


@ibm_volume_attachments.get('/volume_attachments/<volume_attachment_id>')
@authenticate
@output(IBMVolumeAttachmentOutSchema, status_code=200)
def get_ibm_volume_attachment(volume_attachment_id, user):
    """
    Get IBM Volume Attachment
    This request will fetch Volume Attachments from IBM Cloud
    """
    volume_attachment = ibmdb.session.query(IBMVolumeAttachment).filter_by(
        id=volume_attachment_id
    ).join(IBMVolumeAttachment.ibm_cloud).filter_by(
        user_id=user["id"], project_id=user["project_id"], deleted=False, status=IBMCloud.STATUS_VALID
    ).first()
    if not volume_attachment:
        message = f"IBM Volume Attachment {volume_attachment_id} does not exist"
        LOGGER.debug(message)
        abort(404, message)
    return volume_attachment.to_json()


@ibm_volume_attachments.get('/volume_attachments')
@authenticate
@input(IBMInstanceQuerySchema, location='query')
@input(PaginationQuerySchema, location='query')
@output(get_pagination_schema(IBMVolumeAttachmentOutSchema))
def list_ibm_volume_attachments(instance_id_query_params, pagination_query_params, user):
    """
    List IBM Volume Attachments
    This request fetches all volumes from IBM Cloud
    """
    cloud_id = instance_id_query_params["cloud_id"]
    region_id = instance_id_query_params.get("region_id")
    instance_id = instance_id_query_params.get("instance_id")

    ibm_cloud = authorize_and_get_ibm_cloud(cloud_id=cloud_id, user=user)

    filters = {"cloud_id": cloud_id}

    if region_id:
        region = ibm_cloud.regions.filter_by(id=region_id).first()
        if not region:
            message = f"IBM Region {region_id} does not exist"
            LOGGER.debug(message)
            abort(404, message)
        filters["region_id"] = region_id

    if instance_id:
        instance = ibm_cloud.instances.filter_by(id=instance_id).first()
        if not instance:
            message = f"IBM Instance {instance} does not exist"
            LOGGER.debug(message)
            abort(404, message)

        filters["instance_id"] = instance_id

    volume_attachment_query = ibmdb.session.query(IBMVolumeAttachment).filter_by(**filters)

    volume_attachments_page = volume_attachment_query.paginate(
        page=pagination_query_params["page"], per_page=pagination_query_params["per_page"], error_out=False
    )
    if not volume_attachments_page.items:
        return '', 204

    return get_paginated_response_json(
        items=[item.to_json() for item in volume_attachments_page.items],
        pagination_obj=volume_attachments_page
    )


@ibm_volume_attachments.patch('/volume_attachments/<volume_attachment_id>')
@authenticate
@input(IBMVolumeAttachmentUpdateSchema)
@output(WorkflowRootOutSchema, status_code=202)
def update_ibm_volume(volume_attachment_id, data, user):
    """
    Update IBM Volume Attachment
    This request updates an Volume Attachment
    """
    abort(404)


@ibm_volume_attachments.delete('/volume_attachments/<volume_attachment_id>')
@authenticate
@output(WorkflowRootOutSchema, status_code=202)
def delete_ibm_volume_attachment(volume_attachment_id, user):
    """
    Delete IBM Volume Attachment
    This request deletes an IBM Volume Attachment provided its ID.
    """
    volume_attachment = ibmdb.session.query(IBMVolumeAttachment).filter_by(
        id=volume_attachment_id
    ).join(IBMVolumeAttachment.ibm_cloud).filter_by(
        user_id=user["id"], project_id=user["project_id"], deleted=False
    ).first()
    if not volume_attachment:
        message = f"IBM Volume Attachment {volume_attachment} does not exist"
        LOGGER.debug(message)
        abort(404, message)

    return compose_ibm_resource_deletion_workflow(
        user=user, resource_type=IBMVolumeAttachment, resource_id=volume_attachment_id
    ).to_json(metadata=True)
