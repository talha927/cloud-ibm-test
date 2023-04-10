import logging
from datetime import datetime

from ibm.discovery import get_db_session
from ibm.discovery.common.utils import discovery_locked_resource
from ibm.models import IBMCloud, IBMImage, IBMOperatingSystem, IBMRegion, IBMResourceGroup, IBMResourceLog, \
    IBMSnapshot, IBMVolume

LOGGER = logging.getLogger(__name__)


def update_snapshots(cloud_id, region_name, m_snapshots):
    if not m_snapshots:
        return

    start_time = datetime.utcnow()

    snapshots = list()
    snapshots_ids = list()
    snapshots_id_rgid_dict = dict()
    snapshots_id_image_id_dict = dict()
    snapshots_id_volume_id_dict = dict()
    snapshots_id_os_name_dict = dict()
    locked_rid_status = dict()
    with get_db_session() as db_session:
        with db_session.no_autoflush:
            for m_snapshot_list in m_snapshots:
                for m_snapshot in m_snapshot_list.get("response", []):
                    snapshot = IBMSnapshot.from_ibm_json_body(json_body=m_snapshot)
                    m_source_image = m_snapshot.get("source_image")
                    m_operating_system = m_snapshot.get("operating_system")
                    snapshots_id_rgid_dict[snapshot.resource_id] = m_snapshot["resource_group"]["id"]
                    snapshots_id_volume_id_dict[snapshot.resource_id] = m_snapshot["source_volume"]["id"]
                    snapshots_id_image_id_dict[snapshot.resource_id] = m_source_image["id"] if m_source_image else None
                    snapshots_id_os_name_dict[snapshot.resource_id] = db_session.query(IBMOperatingSystem).filter_by(
                        name=m_operating_system["name"]).first() if m_operating_system else None

                    snapshots.append(snapshot)
                    snapshots_ids.append(snapshot.resource_id)

                with get_db_session() as session:
                    db_region = session.query(IBMRegion).filter_by(name=region_name, cloud_id=cloud_id).first()
                    if not db_region:
                        LOGGER.info(f"IBMRegion {region_name} not found")
                        return

                    last_synced_at = m_snapshot_list["last_synced_at"]
                    logged_resource = discovery_locked_resource(
                        session=session, resource_type=IBMSnapshot.__name__, cloud_id=cloud_id,
                        sync_start=last_synced_at, region=db_region)
                    locked_rid_status.update(logged_resource)

            db_region = db_session.query(IBMRegion).filter_by(name=region_name, cloud_id=cloud_id).first()
            if not db_region:
                LOGGER.info(f"IBMRegion {region_name} not found")
                return
            region_id = db_region.id

            db_snapshots = db_session.query(IBMSnapshot).filter_by(cloud_id=cloud_id, region_id=region_id).all()
            for db_snapshot in db_snapshots:
                if locked_rid_status.get(db_snapshot.resource_id) in [IBMResourceLog.STATUS_ADDED,
                                                                      IBMResourceLog.STATUS_UPDATED]:
                    continue

                if db_snapshot.resource_id not in snapshots_ids:
                    db_session.delete(db_snapshot)

            db_session.commit()

            db_snapshots = db_session.query(IBMSnapshot).filter_by(cloud_id=cloud_id, region_id=region_id).all()
            db_cloud = db_session.query(IBMCloud).get(cloud_id)
            assert db_cloud

            db_resource_groups = db_session.query(IBMResourceGroup).filter_by(cloud_id=cloud_id).all()
            db_resource_group_id_obj_dict = {
                db_resource_group.resource_id: db_resource_group for db_resource_group in db_resource_groups
            }
            db_images = db_session.query(IBMImage).filter_by(cloud_id=cloud_id, region_id=region_id).all()
            db_image_id_obj_dict = {
                db_image.resource_id: db_image for db_image in db_images
            }
            db_volumes = db_session.query(IBMVolume).filter_by(cloud_id=cloud_id, region_id=region_id).all()
            db_volume_id_obj_dict = {
                db_volume.resource_id: db_volume for db_volume in db_volumes
            }

            for snapshot in snapshots:
                if locked_rid_status.get(snapshot.resource_id) in [IBMResourceLog.STATUS_DELETED,
                                                                   IBMResourceLog.STATUS_UPDATED]:
                    continue
                snapshot.dis_add_update_db(
                    db_session=db_session, db_snapshots=db_snapshots, db_cloud=db_cloud,
                    db_resource_group=db_resource_group_id_obj_dict.get(snapshots_id_rgid_dict[snapshot.resource_id]),
                    db_region=db_region,
                    db_image=db_image_id_obj_dict.get(snapshots_id_image_id_dict[snapshot.resource_id]),
                    db_volume=db_volume_id_obj_dict.get(snapshots_id_volume_id_dict[snapshot.resource_id]),
                    db_operating_system=snapshots_id_os_name_dict.get(snapshot.resource_id)
                )

            db_session.commit()

    LOGGER.info("** Snapshots synced in:{}".format((datetime.utcnow() - start_time).total_seconds()))
