import logging

from apiflask import abort, APIBlueprint, input, output

from ibm.auth import authenticate
from ibm.common.req_resp_schemas.schemas import get_pagination_schema, IBMResourceQuerySchema, PaginationQuerySchema
from ibm.models import IBMInstanceProfile
from ibm.web import db as ibmdb
from ibm.web.common.utils import authorize_and_get_ibm_cloud, get_paginated_response_json
from .schemas import IBMInstanceProfileFamilyOutSchema, IBMInstanceProfileOutSchema, IBMInstanceProfileQuerySchema

LOGGER = logging.getLogger(__name__)

ibm_instance_profiles = APIBlueprint('ibm_instance_profiles', __name__, tag="IBM Instance Profiles")


@ibm_instance_profiles.get('/instance_profiles/<instance_profile_id>')
@authenticate
@output(IBMInstanceProfileOutSchema)
def get_ibm_instance_profile(instance_profile_id, user):
    """
    Get IBM Instance Profile
    This request will fetch IBM Instance Profile from IBM Cloud
    """
    instance_profile = ibmdb.session.query(IBMInstanceProfile).filter_by(
        id=instance_profile_id
    ).join(IBMInstanceProfile.ibm_cloud).filter_by(
        user_id=user["id"], project_id=user["project_id"], deleted=False
    ).first()
    if not instance_profile:
        message = f"IBM Instance Profile {instance_profile_id} does not exist"
        LOGGER.debug(message)
        abort(404, message)
    return instance_profile.to_json()


@ibm_instance_profiles.get('/instance_profiles')
@authenticate
@input(IBMInstanceProfileQuerySchema, location='query')
@input(PaginationQuerySchema, location='query')
@output(get_pagination_schema(IBMInstanceProfileOutSchema))
def list_ibm_instance_profiles(regional_res_query_params, pagination_query_params, user):
    """
    List IBM Instance Profiles
    This request fetches all Instance Profile from IBM Cloud
    """
    cloud_id = regional_res_query_params["cloud_id"]
    region_id = regional_res_query_params.get("region_id")
    family = regional_res_query_params.get("family")
    os_architecture = regional_res_query_params.get("os_architecture")

    ibm_cloud = authorize_and_get_ibm_cloud(cloud_id=cloud_id, user=user)

    filters = {"cloud_id": cloud_id}

    if region_id:
        region = ibm_cloud.regions.filter_by(id=region_id).first()
        if not region:
            message = f"IBM Region {region_id} does not exist"
            LOGGER.debug(message)
            abort(404, message)
        filters["region_id"] = region_id

    if family:
        filters["family"] = family
    instance_profiles_query = ibmdb.session.query(IBMInstanceProfile).filter_by(**filters)

    if os_architecture:
        instance_profiles_query = instance_profiles_query.filter(
            IBMInstanceProfile.os_architecture['values'].contains(os_architecture))

    instance_profiles_page = instance_profiles_query.paginate(
        page=pagination_query_params["page"], per_page=pagination_query_params["per_page"], error_out=False
    )
    if not instance_profiles_page.items:
        return '', 204

    return get_paginated_response_json(
        items=[item.to_json() for item in instance_profiles_page.items],
        pagination_obj=instance_profiles_page
    )


@ibm_instance_profiles.get('/instance_profiles/families')
@authenticate
@input(IBMResourceQuerySchema, location='query')
@output(IBMInstanceProfileFamilyOutSchema)
def list_ibm_instance_profile_families(regional_res_query_params, user):
    """
    List IBM Instance Profile Families
    This request returns IBM Instance Profile Families
    """
    cloud_id = regional_res_query_params["cloud_id"]

    authorize_and_get_ibm_cloud(cloud_id=cloud_id, user=user)
    instance_profiles = ibmdb.session.query(IBMInstanceProfile.family).join(
        IBMInstanceProfile.ibm_cloud
    ).filter_by(
        user_id=user["id"], project_id=user["project_id"], deleted=False
    ).distinct().all()

    return {
        "families": [family.family for family in instance_profiles]
    }
