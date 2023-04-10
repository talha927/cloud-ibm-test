import logging
from datetime import datetime

from ibm.discovery import get_db_session
from ibm.models import IBMCloud, IBMRegion, IBMZone

LOGGER = logging.getLogger(__name__)


def update_regions(cloud_id, m_regions):
    """Update Regions"""

    if not m_regions:
        return

    start_time = datetime.utcnow()

    regions = list()
    region_names = set()

    for m_ibm_region in m_regions:
        for ibm_region in m_ibm_region.get("response", []):
            region = IBMRegion.from_ibm_json_body(json_body=ibm_region)
            regions.append(region)
            region_names.add(region.name)

    with get_db_session() as session:
        ibm_cloud = session.query(IBMCloud).filter_by(id=cloud_id).first()
        assert ibm_cloud

        db_regions = ibm_cloud.regions.all()
        db_regions_rid_obj_dict = dict()
        for db_region in db_regions:
            if db_region.name not in region_names:
                session.delete(db_region)
                continue

            db_regions_rid_obj_dict[db_region.name] = db_region

        session.commit()

        for region in regions:
            if region.name in db_regions_rid_obj_dict:
                db_regions_rid_obj_dict[region.name].update_from_obj(region)
                continue

            region.ibm_cloud = ibm_cloud
            session.commit()

        session.commit()

    LOGGER.info(f"** Regions synced in: {(datetime.utcnow() - start_time).total_seconds()}")


def update_zones(cloud_id, region_name, m_zones):
    """Update Regions"""

    if not m_zones:
        return

    start_time = datetime.utcnow()

    zones = list()
    zone_names = set()

    for m_zone_list in m_zones:
        for m_zone in m_zone_list.get("response", []):
            zone = IBMZone.from_ibm_json_body(json_body=m_zone)
            zones.append(zone)
            zone_names.add(zone.name)

    with get_db_session() as session:
        ibm_cloud = session.query(IBMCloud).filter_by(id=cloud_id).first()
        assert ibm_cloud

        ibm_region = session.query(IBMRegion).filter_by(name=region_name, cloud_id=ibm_cloud.id).first()
        assert ibm_region

        db_zones = ibm_region.zones.all()
        db_zones_rid_obj_dict = dict()
        for db_zone in db_zones:
            if db_zone.name not in zone_names:
                session.delete(db_zone)
                continue

            db_zones_rid_obj_dict[db_zone.name] = db_zone

        session.commit()

        for zone in zones:
            if zone.name in db_zones_rid_obj_dict:
                db_zones_rid_obj_dict[zone.name].update_from_obj(zone)
                continue

            zone.region = ibm_region
            session.commit()

        session.commit()

    LOGGER.info(f"** Zones synced in: {(datetime.utcnow() - start_time).total_seconds()}")
