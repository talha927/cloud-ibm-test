import logging

from apiflask import abort, APIBlueprint, input, output

from ibm.auth import authenticate
from ibm.common.req_resp_schemas.schemas import get_pagination_schema, IBMRegionalResourceListQuerySchema, \
    IBMVolumesListQuerySchema, PaginationQuerySchema, WorkflowRootOutSchema
from ibm.models import IBMInstance, IBMVolume, IBMVolumeAttachment, IBMVolumeProfile
from ibm.web import db as ibmdb
from ibm.web.common.utils import authorize_and_get_ibm_cloud, compose_ibm_resource_deletion_workflow, \
    create_ibm_resource_creation_workflow, get_paginated_response_json, verify_and_get_region, verify_and_get_zone, \
    verify_references
from .schemas import IBMVolumeInSchema, IBMVolumeOutSchema, IBMVolumeProfileOutSchema, IBMVolumeResourceSchema, \
    IBMVolumeUpdateSchema

LOGGER = logging.getLogger(__name__)

ibm_volumes = APIBlueprint('ibm_volumes', __name__, tag="IBM Block Storage Volumes")


@ibm_volumes.post('/volumes')
@authenticate
@input(IBMVolumeInSchema)
@output(WorkflowRootOutSchema, status_code=202)
def create_ibm_volume(data, user):
    """
    Create IBM Volume
    This request create a volume on IBM Cloud
    """
    cloud_id = data["ibm_cloud"]["id"]
    region_id = data["region"]["id"]

    ibm_cloud = authorize_and_get_ibm_cloud(cloud_id=cloud_id, user=user)
    verify_and_get_region(ibm_cloud=ibm_cloud, region_id=region_id)
    # TODO check if zone is in this region as well or not
    verify_references(
        cloud_id=cloud_id, body_schema=IBMVolumeInSchema, resource_schema=IBMVolumeResourceSchema, data=data
    )

    workflow_root = create_ibm_resource_creation_workflow(
        user=user, resource_type=IBMVolume, data=data, validate=False
    )
    return workflow_root.to_json()


@ibm_volumes.get('/volumes/<volume_id>')
@authenticate
@output(IBMVolumeOutSchema, status_code=202)
def get_ibm_volume(volume_id, user):
    """
    Get IBM Volume
    This request will fetch IBM Volume from IBM Cloud
    """
    volume = ibmdb.session.query(IBMVolume).filter_by(
        id=volume_id
    ).join(IBMVolume.ibm_cloud).filter_by(
        user_id=user["id"], project_id=user["project_id"], deleted=False
    ).first()
    if not volume:
        message = f"IBM Volume {volume_id} does not exist"
        LOGGER.debug(message)
        abort(404, message)

    return volume.to_json()


@ibm_volumes.get('/volumes')
@authenticate
@input(IBMVolumesListQuerySchema, location='query')
@input(PaginationQuerySchema, location='query')
@output(get_pagination_schema(IBMVolumeOutSchema))
def list_ibm_volumes(zonal_res_query_params, pagination_query_params, user):
    """
    List IBM Volumes
    This request fetches all volumes from IBM Cloud
    """

    cloud_id = zonal_res_query_params["cloud_id"]
    region_id = zonal_res_query_params.get("region_id")
    zone_id = zonal_res_query_params.get("zone_id")
    images_source_volume = zonal_res_query_params.get("images_source_volume")
    instance_attached = zonal_res_query_params.get("instance_attached")

    ibm_cloud = authorize_and_get_ibm_cloud(cloud_id=cloud_id, user=user)
    volumes_query = ibmdb.session.query(IBMVolume).filter_by(cloud_id=cloud_id)

    if region_id:
        verify_and_get_region(ibm_cloud=ibm_cloud, region_id=region_id)
        volumes_query = volumes_query.filter_by(region_id=region_id)

    if zone_id:
        verify_and_get_zone(cloud_id=cloud_id, zone_id=zone_id)
        volumes_query = volumes_query.filter_by(zone_id=zone_id)

    if images_source_volume:
        volumes_query = volumes_query.join(IBMVolumeAttachment).filter_by(type_="boot").join(IBMInstance).filter_by(
            status="stopped")

    if instance_attached in [True, False]:
        if instance_attached:
            volumes_query = volumes_query.filter(IBMVolume.volume_attachments.any())
        else:
            volumes_query = volumes_query.filter(~IBMVolume.volume_attachments.any())

    volumes_page = volumes_query.paginate(
        page=pagination_query_params["page"], per_page=pagination_query_params["per_page"], error_out=False
    )
    if not volumes_page.items:
        return '', 204

    return get_paginated_response_json(
        items=[item.to_json() for item in volumes_page.items],
        pagination_obj=volumes_page
    )


@ibm_volumes.patch('/volumes/<volume_id>')
@authenticate
@input(IBMVolumeUpdateSchema)
@output(WorkflowRootOutSchema, status_code=202)
def update_ibm_volume(volume_id, data, user):
    """
    Update IBM Volume
    This request updates an IBM Volume
    """
    abort(404)


@ibm_volumes.delete('/volumes/<volume_id>')
@authenticate
@output(WorkflowRootOutSchema, status_code=202)
def delete_ibm_volume(volume_id, user):
    """
    Delete IBM Volume
    This request deletes an IBM Volume provided its ID.
    """
    volume = ibmdb.session.query(IBMVolume).filter_by(
        id=volume_id
    ).join(IBMVolume.ibm_cloud).filter_by(
        user_id=user["id"], project_id=user["project_id"], deleted=False
    ).first()
    if not volume:
        message = f"IBM Volume {volume_id} does not exist"
        LOGGER.debug(message)
        abort(404, message)

    # TODO: Uncomment when we have update api calls.
    # if not volume.is_deletable:
    #     message = f"IBM Volume {volume_id} cannot be deleted because it's in use."
    #     LOGGER.debug(message)
    #     abort(409, message)

    return compose_ibm_resource_deletion_workflow(
        user=user, resource_type=IBMVolume, resource_id=volume_id
    ).to_json(metadata=True)


@ibm_volumes.get('/volume/profiles/<profile_id>')
@authenticate
@output(IBMVolumeProfileOutSchema, status_code=202)
def get_ibm_volume_profile(profile_id, user):
    """
    Get IBM Volume Profile
    This request will fetch IBM Volume Profile from IBM Cloud
    """
    volume_profile = ibmdb.session.query(IBMVolumeProfile).filter_by(
        id=profile_id
    ).join(IBMVolumeProfile.ibm_cloud).filter_by(
        user_id=user["id"], project_id=user["project_id"], deleted=False
    ).first()
    if not volume_profile:
        message = f"IBM Volume Profile {profile_id} does not exist"
        LOGGER.debug(message)
        abort(404, message)

    return volume_profile.to_json()


@ibm_volumes.get('/volume/profiles')
@authenticate
@input(IBMRegionalResourceListQuerySchema, location='query')
@input(PaginationQuerySchema, location='query')
@output(get_pagination_schema(IBMVolumeProfileOutSchema))
def list_ibm_volume_profiles(regional_res_query_params, pagination_query_params, user):
    """
    List IBM Volumes Profiles
    This request fetches all volume profiles from IBM Cloud
    """
    cloud_id = regional_res_query_params["cloud_id"]
    region_id = regional_res_query_params.get("region_id")

    ibm_cloud = authorize_and_get_ibm_cloud(cloud_id=cloud_id, user=user)

    region = None
    if region_id:
        region = ibm_cloud.regions.filter_by(id=region_id).first()
        if not region:
            message = f"IBM Region {region_id} does not exist"
            LOGGER.debug(message)
            abort(404, message)

    volume_profiles_query = ibmdb.session.query(IBMVolumeProfile).filter_by(cloud_id=cloud_id)
    if region:
        volume_profiles_query = volume_profiles_query.filter_by(region_id=region_id)

    volume_profiles_page = volume_profiles_query.paginate(
        page=pagination_query_params["page"], per_page=pagination_query_params["per_page"], error_out=False
    )
    if not volume_profiles_page.items:
        return '', 204

    return get_paginated_response_json(
        items=[item.to_json() for item in volume_profiles_page.items],
        pagination_obj=volume_profiles_page
    )
