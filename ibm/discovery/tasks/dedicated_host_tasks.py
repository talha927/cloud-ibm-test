import logging
from datetime import datetime

from ibm.discovery import get_db_session
from ibm.discovery.common.utils import discovery_locked_resource
from ibm.models import IBMDedicatedHost, IBMDedicatedHostDisk, IBMDedicatedHostGroup, IBMDedicatedHostProfile, \
    IBMRegion, IBMResourceLog, IBMZone

LOGGER = logging.getLogger(__name__)


def update_dedicated_host_profiles(cloud_id, region_name, m_dedicated_host_profiles):
    if not m_dedicated_host_profiles:
        return

    start_time = datetime.utcnow()

    locked_rid_status = dict()
    dedicated_host_profiles = list()
    dedicated_host_profiles_names = list()

    for m_dedicated_host_profile_list in m_dedicated_host_profiles:
        for m_dedicated_host_profile in m_dedicated_host_profile_list.get("response", []):
            dedicated_host_profile = IBMDedicatedHostProfile.from_ibm_json_body(json_body=m_dedicated_host_profile)
            dedicated_host_profiles.append(dedicated_host_profile)
            dedicated_host_profiles_names.append(dedicated_host_profile.name)

        with get_db_session() as session:
            db_region = session.query(IBMRegion).filter_by(name=region_name, cloud_id=cloud_id).first()
            if not db_region:
                LOGGER.info(f"IBMRegion {region_name} not found")
                return

            last_synced_at = m_dedicated_host_profile_list["last_synced_at"]
            logged_resource = discovery_locked_resource(
                session=session, resource_type=IBMDedicatedHostProfile.__name__, cloud_id=cloud_id,
                sync_start=last_synced_at, region=db_region)
            locked_rid_status.update(logged_resource)

    with get_db_session() as session:
        with session.no_autoflush:
            db_region = session.query(IBMRegion).filter_by(name=region_name, cloud_id=cloud_id).first()
            if not db_region:
                LOGGER.info(f"IBMRegion {region_name} not found")
                return

            region_id = db_region.id

            db_dedicated_host_profiles = \
                session.query(IBMDedicatedHostProfile).filter_by(cloud_id=cloud_id, region_id=region_id).all()

            for db_dedicated_host_profile in db_dedicated_host_profiles:
                if locked_rid_status.get(db_dedicated_host_profile.name) in [IBMResourceLog.STATUS_ADDED,
                                                                             IBMResourceLog.STATUS_UPDATED]:
                    continue

                if db_dedicated_host_profile.name not in dedicated_host_profiles_names:
                    session.delete(db_dedicated_host_profile)

            session.commit()

            for dedicated_host_profile in dedicated_host_profiles:
                if locked_rid_status.get(dedicated_host_profile.name) in [IBMResourceLog.STATUS_DELETED,
                                                                          IBMResourceLog.STATUS_UPDATED]:
                    continue
                db_dedicated_host_profile = \
                    session.query(IBMDedicatedHostProfile).filter_by(cloud_id=cloud_id, region_id=region_id,
                                                                     name=dedicated_host_profile.name).first()
                dedicated_host_profile.dis_add_update_db(
                    session=session, db_dedicated_host_profile=db_dedicated_host_profile, cloud_id=cloud_id,
                    db_region=db_region
                )

    LOGGER.info("** Dedicated Host Profiles synced in:{}".format((datetime.utcnow() - start_time).total_seconds()))


def update_dedicated_host_groups(cloud_id, region_name, m_dedicated_host_groups):
    if not m_dedicated_host_groups:
        return

    start_time = datetime.utcnow()

    dedicated_host_groups = list()
    dedicated_host_groups_ids = list()
    dedicated_host_groups_id_resource_group_id_dict = dict()
    dh_group_id_zone_name_dict = dict()
    locked_rid_status = dict()

    for m_dedicated_host_group_list in m_dedicated_host_groups:
        for m_dedicated_host_group in m_dedicated_host_group_list.get("response", []):
            dedicated_host_group = IBMDedicatedHostGroup.from_ibm_json_body(json_body=m_dedicated_host_group)
            dedicated_host_groups_id_resource_group_id_dict[dedicated_host_group.resource_id] = \
                m_dedicated_host_group["resource_group"]["id"]
            dh_group_id_zone_name_dict[dedicated_host_group.resource_id] = m_dedicated_host_group["zone"]["name"]

            dedicated_host_groups.append(dedicated_host_group)
            dedicated_host_groups_ids.append(dedicated_host_group.resource_id)

        with get_db_session() as session:
            db_region = session.query(IBMRegion).filter_by(name=region_name, cloud_id=cloud_id).first()
            if not db_region:
                LOGGER.info(f"IBMRegion {region_name} not found")
                return

            last_synced_at = m_dedicated_host_group_list["last_synced_at"]
            logged_resource = discovery_locked_resource(
                session=session, resource_type=IBMDedicatedHostGroup.__name__, cloud_id=cloud_id,
                sync_start=last_synced_at, region=db_region)
            locked_rid_status.update(logged_resource)

    with get_db_session() as session:
        with session.no_autoflush:
            db_region = session.query(IBMRegion).filter_by(name=region_name, cloud_id=cloud_id).first()
            if not db_region:
                LOGGER.info(f"IBMRegion {region_name} not found")
                return
            region_id = db_region.id

            db_dedicated_host_groups = \
                session.query(IBMDedicatedHostGroup).filter_by(cloud_id=cloud_id, region_id=region_id).all()

            for db_dedicated_host_group in db_dedicated_host_groups:
                if locked_rid_status.get(db_dedicated_host_group.resource_id) in [IBMResourceLog.STATUS_ADDED,
                                                                                  IBMResourceLog.STATUS_UPDATED]:
                    continue

                if db_dedicated_host_group.resource_id not in dedicated_host_groups_ids:
                    session.delete(db_dedicated_host_group)

            session.commit()

            db_zones = session.query(IBMZone).filter_by(cloud_id=cloud_id).all()
            db_zone_name_obj_dict = {
                db_zone.name: db_zone for db_zone in db_zones
            }

            for dedicated_host_group in dedicated_host_groups:
                if locked_rid_status.get(dedicated_host_group.resource_id) in [IBMResourceLog.STATUS_DELETED,
                                                                               IBMResourceLog.STATUS_UPDATED]:
                    continue

                db_dedicated_host_group = \
                    session.query(IBMDedicatedHostGroup).filter_by(cloud_id=cloud_id, region_id=region_id,
                                                                   resource_id=dedicated_host_group.resource_id).first()

                dedicated_host_group.dis_add_update_db(
                    session=session, db_dedicated_host_group=db_dedicated_host_group, cloud_id=cloud_id,
                    resource_group_id=dedicated_host_groups_id_resource_group_id_dict.get(
                        dedicated_host_group.resource_id),
                    db_zone=db_zone_name_obj_dict[dh_group_id_zone_name_dict[dedicated_host_group.resource_id]]
                )

    LOGGER.info("** Dedicated Host Groups synced in:{}".format((datetime.utcnow() - start_time).total_seconds()))


def update_dedicated_hosts(cloud_id, region_name, m_dedicated_hosts):
    if not m_dedicated_hosts:
        return

    start_time = datetime.utcnow()

    dedicated_hosts = list()
    dedicated_host_ids = list()
    dedicated_host_id_resource_group_id_dict = dict()
    dedicated_host_id_dh_group_id_dict = dict()
    dedicated_host_id_dh_profile_name_dict = dict()
    dedicated_host_id_zone_name_dict = dict()
    locked_rid_status = dict()

    for m_dedicated_host_list in m_dedicated_hosts:
        for m_dedicated_host in m_dedicated_host_list.get("response", []):
            dedicated_host = IBMDedicatedHost.from_ibm_json_body(json_body=m_dedicated_host)
            dedicated_host_id_resource_group_id_dict[dedicated_host.resource_id] = \
                m_dedicated_host["resource_group"]["id"]

            dedicated_host_id_dh_group_id_dict[dedicated_host.resource_id] = \
                m_dedicated_host["group"]["id"]

            dedicated_host_id_dh_profile_name_dict[dedicated_host.resource_id] = \
                m_dedicated_host["profile"]["name"]

            dedicated_host_id_zone_name_dict[dedicated_host.resource_id] = m_dedicated_host["zone"]["name"]

            dedicated_hosts.append(dedicated_host)
            dedicated_host_ids.append(dedicated_host.resource_id)

        with get_db_session() as session:
            db_region = session.query(IBMRegion).filter_by(name=region_name, cloud_id=cloud_id).first()
            if not db_region:
                LOGGER.info(f"IBMRegion {region_name} not found")
                return

            last_synced_at = m_dedicated_host_list["last_synced_at"]
            logged_resource = discovery_locked_resource(
                session=session, resource_type=IBMDedicatedHost.__name__, cloud_id=cloud_id,
                sync_start=last_synced_at, region=db_region)
            locked_rid_status.update(logged_resource)

    with get_db_session() as session:
        with session.no_autoflush:
            db_region = session.query(IBMRegion).filter_by(name=region_name, cloud_id=cloud_id).first()
            if not db_region:
                LOGGER.info(f"IBMRegion {region_name} not found")
                return
            region_id = db_region.id

            db_dedicated_hosts = \
                session.query(IBMDedicatedHost).filter_by(cloud_id=cloud_id, region_id=region_id).all()

            for db_dedicated_host in db_dedicated_hosts:
                if locked_rid_status.get(db_dedicated_host.resource_id) in [IBMResourceLog.STATUS_ADDED,
                                                                            IBMResourceLog.STATUS_UPDATED]:
                    continue

                if db_dedicated_host.resource_id not in dedicated_host_ids:
                    session.delete(db_dedicated_host)

            session.commit()

            db_zones = session.query(IBMZone).filter_by(cloud_id=cloud_id).all()
            db_zone_name_obj_dict = {
                db_zone.name: db_zone for db_zone in db_zones
            }
            session.commit()

            for dedicated_host in dedicated_hosts:
                if locked_rid_status.get(dedicated_host.resource_id) in [IBMResourceLog.STATUS_DELETED,
                                                                         IBMResourceLog.STATUS_UPDATED]:
                    continue

                db_dedicated_host = \
                    session.query(IBMDedicatedHost).filter_by(cloud_id=cloud_id, region_id=region_id).first()

                dedicated_host.dis_add_update_db(
                    session=session, db_dedicated_host=db_dedicated_host, cloud_id=cloud_id,
                    resource_group_id=dedicated_host_id_resource_group_id_dict.get(dedicated_host.resource_id),
                    dedicated_host_profile_name=dedicated_host_id_dh_profile_name_dict.get(dedicated_host.resource_id),
                    dedicated_host_group_id=dedicated_host_id_dh_group_id_dict.get(dedicated_host.resource_id),
                    db_zone=db_zone_name_obj_dict[dedicated_host_id_zone_name_dict[dedicated_host.resource_id]]
                )

    LOGGER.info("** Dedicated Hosts synced in:{}".format((datetime.utcnow() - start_time).total_seconds()))


def update_dedicated_host_disks(cloud_id, region_name, m_dedicated_host_disks):
    if not m_dedicated_host_disks:
        return

    start_time = datetime.utcnow()

    dedicated_host_disks = list()
    dedicated_host_disk_ids = list()
    dedicated_host_disk_id_dedicated_host_id_dict = dict()
    locked_rid_status = dict()

    for m_dedicated_host_disk_list in m_dedicated_host_disks:
        for m_dedicated_host_disk in m_dedicated_host_disk_list.get("response", []):
            dedicated_host_disk = IBMDedicatedHostDisk.from_ibm_json_body(json_body=m_dedicated_host_disk)
            dedicated_host_disk_id_dedicated_host_id_dict[dedicated_host_disk.resource_id] = \
                m_dedicated_host_disk["href"].split("/")[5]

            dedicated_host_disks.append(dedicated_host_disk)
            dedicated_host_disk_ids.append(dedicated_host_disk.resource_id)

        with get_db_session() as session:
            db_region = session.query(IBMRegion).filter_by(name=region_name, cloud_id=cloud_id).first()
            if not db_region:
                LOGGER.info(f"IBMRegion {region_name} not found")
                return

            last_synced_at = m_dedicated_host_disk_list["last_synced_at"]
            logged_resource = discovery_locked_resource(
                session=session, resource_type=IBMDedicatedHostDisk.__name__, cloud_id=cloud_id,
                sync_start=last_synced_at, region=db_region)
            locked_rid_status.update(logged_resource)

    with get_db_session() as session:
        with session.no_autoflush:

            db_region = session.query(IBMRegion).filter_by(name=region_name, cloud_id=cloud_id).first()
            if not db_region:
                LOGGER.info(f"IBMRegion {region_name} not found")
                return
            region_id = db_region.id

            db_dedicated_host_disks = \
                session.query(IBMDedicatedHostDisk).filter_by(cloud_id=cloud_id, region_id=region_id).all()

            for db_dedicated_host_disk in db_dedicated_host_disks:
                if locked_rid_status.get(db_dedicated_host_disk.resource_id) in [IBMResourceLog.STATUS_DELETED,
                                                                                 IBMResourceLog.STATUS_UPDATED]:
                    continue
                if db_dedicated_host_disk.resource_id not in dedicated_host_disk_ids:
                    session.delete(db_dedicated_host_disk)

            session.commit()

            for dedicated_host_disk in dedicated_host_disks:
                if locked_rid_status.get(dedicated_host_disk.resource_id) in [IBMResourceLog.STATUS_DELETED,
                                                                              IBMResourceLog.STATUS_UPDATED]:
                    continue
                db_dedicated_host_disk = \
                    session.query(IBMDedicatedHostDisk).filter_by(cloud_id=cloud_id, region_id=region_id,
                                                                  resource_id=dedicated_host_disk.resource_id).first()

                dedicated_host_disk.dis_add_update_db(
                    session=session, db_dedicated_host_disk=db_dedicated_host_disk, cloud_id=cloud_id,
                    dedicated_host_id=dedicated_host_disk_id_dedicated_host_id_dict.get(
                        dedicated_host_disk.resource_id),
                    db_region=db_region
                )

    LOGGER.info("** Dedicated Host Disks synced in:{}".format((datetime.utcnow() - start_time).total_seconds()))
