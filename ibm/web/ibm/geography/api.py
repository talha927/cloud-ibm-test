import logging

from apiflask import abort, APIBlueprint, input, output
from flask import Response

from ibm.auth import authenticate
from ibm.models import IBMCloud, IBMRegion, IBMZone
from ibm.web import db as ibmdb
from .schemas import IBMRegionGetQueryParams, IBMRegionListQueryParams, IBMRegionOutSchema, IBMZoneListQueryParams, \
    IBMZoneOutSchema

LOGGER = logging.getLogger(__name__)

ibm_geography = APIBlueprint('ibm_geography', __name__, tag="IBM Geography")


@ibm_geography.route('/geography/regions', methods=['GET'])
@authenticate
@input(IBMRegionListQueryParams, location='query')
@output(IBMRegionOutSchema(many=True))
def list_regions(list_query_params, user):
    """
    List IBM Regions
    This request lists all IBM Regions for the cloud specified. Also lists zones for the regions if 'with_zones' query
    param is sent
    """
    cloud_id = list_query_params["cloud_id"]
    cloud = ibmdb.session.query(IBMCloud).filter_by(
        id=cloud_id, user_id=user["id"], project_id=user["project_id"], deleted=False
    ).first()
    if not cloud:
        message = f"IBM Cloud {cloud_id} not found"
        LOGGER.debug(message)
        abort(404, message)

    regions = ibmdb.session.query(IBMRegion).filter_by(cloud_id=cloud_id).all()
    if not regions:
        return Response(status=204)

    return [region.to_json(with_zones=list_query_params.get("with_zones")) for region in regions]


@ibm_geography.route('/geography/regions/<region_id>', methods=['GET'])
@authenticate
@input(IBMRegionGetQueryParams, location='query')
@output(IBMRegionOutSchema)
def get_region(region_id, query_params, user):
    """
    Get IBM Region
    This request returns an IBM Region provided its ID. Also lists zones for the region if 'with_zones' query param is
    sent
    """
    region = ibmdb.session.query(IBMRegion).filter_by(
        id=region_id
    ).join(IBMRegion.ibm_cloud).filter_by(
        user_id=user["id"], project_id=user["project_id"], deleted=False
    ).first()
    if not region:
        message = f"IBM Region {region_id} does not exist"
        LOGGER.debug(message)
        abort(404, message)

    return region.to_json(with_zones=query_params.get("with_zones"))


@ibm_geography.route('/geography/zones', methods=['GET'])
@authenticate
@input(IBMZoneListQueryParams, location='query')
@output(IBMZoneOutSchema(many=True, exclude=("region",)))
def list_zones(list_query_params, user):
    """
    List IBM Zones
    This request lists all IBM Zones for the cloud specified.
    """
    cloud_id = list_query_params["cloud_id"]
    region_id = list_query_params.get("region_id")

    cloud = ibmdb.session.query(IBMCloud).filter_by(
        id=cloud_id, user_id=user["id"], project_id=user["project_id"], deleted=False
    ).first()
    if not cloud:
        message = f"IBM Cloud {cloud_id} not found"
        LOGGER.debug(message)
        abort(404, message)

    zones_query = ibmdb.session.query(IBMZone).filter_by(cloud_id=cloud_id)
    if region_id:
        region = ibmdb.session.query(IBMRegion).filter_by(id=region_id, cloud_id=cloud_id).first()
        if not region:
            message = f"IBM Region {region_id} not found"
            LOGGER.debug(message)
            abort(404, message)

        zones_query = zones_query.filter_by(region_id=region_id)

    zones = zones_query.all()
    if not zones:
        return Response(status=204)

    return [zone.to_json() for zone in zones]


@ibm_geography.route('/geography/zones/<zone_id>', methods=['GET'])
@authenticate
@output(IBMZoneOutSchema)
def get_zone(zone_id, user):
    """
    Get IBM Zone
    This request returns an IBM Zone provided its ID.
    """
    zone = ibmdb.session.query(IBMZone).filter_by(
        id=zone_id
    ).join(IBMZone.ibm_cloud).filter_by(
        user_id=user["id"], project_id=user["project_id"], deleted=False
    ).first()
    if not zone:
        message = f"IBM Zone {zone_id} does not exist"
        LOGGER.debug(message)
        abort(404, message)

    return zone.to_json()
