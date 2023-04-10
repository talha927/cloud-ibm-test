import logging

import sqlalchemy
from apiflask import abort, APIBlueprint, input, output

from ibm.auth import authenticate
from ibm.common.req_resp_schemas.schemas import get_pagination_schema, IBMDedicatedHostProfileListQuerySchema, \
    PaginationQuerySchema
from ibm.models import IBMDedicatedHostProfile
from ibm.web import db as ibmdb
from ibm.web.common.utils import authorize_and_get_ibm_cloud, get_paginated_response_json, verify_and_get_region, \
    verify_and_get_zone
from .schemas import IBMDedicatedHostProfileOutSchema

LOGGER = logging.getLogger(__name__)

ibm_dedicated_host_profiles = APIBlueprint('ibm_dedicated_host profiles', __name__, tag="IBM Dedicated Host Profiles")


@ibm_dedicated_host_profiles.get('/dedicated_host/profiles')
@authenticate
@input(IBMDedicatedHostProfileListQuerySchema, location='query')
@input(PaginationQuerySchema, location='query')
@output(get_pagination_schema(IBMDedicatedHostProfileOutSchema))
def list_ibm_dedicated_host_profiles(dh_profile_query_params, pagination_query_params, user):
    """
    List all IBM Dedicated Host Profiles
    This request lists all IBM Dedicated Host Profiles
    """
    cloud_id = dh_profile_query_params["cloud_id"]
    zone_id = dh_profile_query_params.get("zone_id")
    region_id = dh_profile_query_params.get("region_id")
    dh_profile_family = dh_profile_query_params.get("family")
    dh_profile_memory = dh_profile_query_params.get("memory")

    ibm_cloud = authorize_and_get_ibm_cloud(cloud_id=cloud_id, user=user)
    dh_profiles_query = ibmdb.session.query(IBMDedicatedHostProfile).filter_by(cloud_id=cloud_id)

    if region_id:
        verify_and_get_region(ibm_cloud=ibm_cloud, region_id=region_id)
        dh_profiles_query = dh_profiles_query.filter_by(region_id=region_id)

    if zone_id:
        verify_and_get_zone(cloud_id=cloud_id, zone_id=zone_id)
        dh_profiles_query = dh_profiles_query.filter_by(zone_id=zone_id)

    if dh_profile_family:
        dh_profiles_query = dh_profiles_query.filter_by(family=dh_profile_family)

    if dh_profile_memory:
        dh_profiles_query = dh_profiles_query.filter(
            IBMDedicatedHostProfile.memory["value"].cast(sqlalchemy.Text) == dh_profile_memory)

    dh_profiles_page = dh_profiles_query.paginate(
        page=pagination_query_params["page"], per_page=pagination_query_params["per_page"], error_out=False
    )
    if not dh_profiles_page.items:
        return '', 204

    return get_paginated_response_json(
        items=[item.to_json() for item in dh_profiles_page.items],
        pagination_obj=dh_profiles_page
    )


@ibm_dedicated_host_profiles.get('/dedicated_host/profiles/<profile_id>')
@authenticate
@output(IBMDedicatedHostProfileOutSchema)
def get_ibm_dedicated_host_profile(profile_id, user):
    """
    Get IBM Dedicated Hosts Profiles
    This request returns an IBM Dedicated Host Profiles provided its ID
    """
    dh_profile = ibmdb.session.query(IBMDedicatedHostProfile).filter_by(
        id=profile_id
    ).join(IBMDedicatedHostProfile.ibm_cloud).filter_by(
        user_id=user["id"], project_id=user["project_id"], deleted=False
    ).first()
    if not dh_profile:
        message = f"IBM Dedicated Host Profile {profile_id} does not exist"
        LOGGER.debug(message)
        abort(404, message)

    return dh_profile.to_json()
