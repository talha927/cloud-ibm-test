import logging
from datetime import datetime

from ibm.discovery import get_db_session
from ibm.discovery.common.utils import discovery_locked_resource
from ibm.models import IBMRegion, IBMResourceGroup, IBMResourceLog, IBMVolume, IBMVolumeProfile, IBMZone

LOGGER = logging.getLogger(__name__)


def update_volume_profiles(cloud_id, region_name, m_volume_profiles):
    if not m_volume_profiles:
        return

    start_time = datetime.utcnow()

    volume_profiles = list()
    volume_profiles_names = list()

    for m_volume_profile_list in m_volume_profiles:
        for m_volume_profile in m_volume_profile_list.get("response", []):
            volume_profile = IBMVolumeProfile.from_ibm_json_body(json_body=m_volume_profile)
            volume_profiles.append(volume_profile)
            volume_profiles_names.append(volume_profile.name)

    with get_db_session() as session:
        with session.no_autoflush:

            db_region = session.query(IBMRegion).filter_by(name=region_name, cloud_id=cloud_id).first()
            if not db_region:
                LOGGER.info(f"IBMRegion {region_name} not found")
                return
            region_id = db_region.id

            db_volume_profiles = session.query(IBMVolumeProfile).filter_by(cloud_id=cloud_id, region_id=region_id).all()

            for db_volume_profile in db_volume_profiles:
                if db_volume_profile.name not in volume_profiles_names:
                    session.delete(db_volume_profile)

            session.commit()

            db_volume_profiles = session.query(IBMVolumeProfile).filter_by(cloud_id=cloud_id, region_id=region_id).all()

            for volume_profile in volume_profiles:
                volume_profile.dis_add_update_db(
                    session=session, db_volume_profiles=db_volume_profiles, cloud_id=cloud_id, db_region=db_region
                )

            session.commit()
    LOGGER.info("** Volume Profiles synced in:{}".format((datetime.utcnow() - start_time).total_seconds()))


def update_volumes(cloud_id, region_name, m_volumes):
    if not m_volumes:
        return

    start_time = datetime.utcnow()

    volumes = list()
    volumes_ids = list()
    volume_id_rgid_dict = dict()
    volumes_id_volume_profile_name_dict = dict()
    volume_id_zone_name_dict = dict()
    locked_rid_status = dict()
    for m_volume_list in m_volumes:
        for m_volume in m_volume_list.get("response", []):
            volume = IBMVolume.from_ibm_json_body(json_body=m_volume)
            volumes_id_volume_profile_name_dict[volume.resource_id] = m_volume["profile"]["name"]
            volume_id_zone_name_dict[volume.resource_id] = m_volume["zone"]["name"]
            volume_id_rgid_dict[volume.resource_id] = m_volume["resource_group"]["id"]
            volumes.append(volume)
            volumes_ids.append(volume.resource_id)

        with get_db_session() as session:
            db_region = session.query(IBMRegion).filter_by(name=region_name, cloud_id=cloud_id).first()
            if not db_region:
                LOGGER.info(f"IBMRegion {region_name} not found")
                return

            last_synced_at = m_volume_list["last_synced_at"]
            logged_resource = discovery_locked_resource(
                session=session, resource_type=IBMVolume.__name__, cloud_id=cloud_id,
                sync_start=last_synced_at, region=db_region)
            locked_rid_status.update(logged_resource)

    with get_db_session() as session:
        with session.no_autoflush:

            db_region = session.query(IBMRegion).filter_by(name=region_name, cloud_id=cloud_id).first()
            if not db_region:
                LOGGER.info(f"IBMRegion {region_name} not found")
                return
            region_id = db_region.id

            db_volumes = session.query(IBMVolume).filter_by(cloud_id=cloud_id, region_id=region_id).all()

            for db_volume in db_volumes:
                if locked_rid_status.get(db_volume.resource_id) in [IBMResourceLog.STATUS_ADDED,
                                                                    IBMResourceLog.STATUS_UPDATED]:
                    continue
                if db_volume.resource_id not in volumes_ids:
                    session.delete(db_volume)

            session.commit()

            db_resource_groups = session.query(IBMResourceGroup).filter_by(cloud_id=cloud_id).all()
            db_resource_group_id_obj_dict = {
                db_resource_group.resource_id: db_resource_group for db_resource_group in db_resource_groups
            }

            db_zones = session.query(IBMZone).filter_by(cloud_id=cloud_id).all()
            db_zone_name_obj_dict = {
                db_zone.name: db_zone for db_zone in db_zones
            }
            db_volumes = session.query(IBMVolume).filter_by(cloud_id=cloud_id, region_id=region_id).all()

            for volume in volumes:
                if locked_rid_status.get(volume.resource_id) in [IBMResourceLog.STATUS_DELETED,
                                                                 IBMResourceLog.STATUS_UPDATED]:
                    continue
                volume.dis_add_update_db(
                    session=session, db_volumes=db_volumes, cloud_id=cloud_id,
                    volume_profile_name=volumes_id_volume_profile_name_dict.get(volume.resource_id),
                    db_zone=db_zone_name_obj_dict[volume_id_zone_name_dict[volume.resource_id]],
                    db_resource_group=db_resource_group_id_obj_dict.get(volume_id_rgid_dict[volume.resource_id])
                )

            session.commit()
    LOGGER.info("** Volumes synced in:{}".format((datetime.utcnow() - start_time).total_seconds()))
