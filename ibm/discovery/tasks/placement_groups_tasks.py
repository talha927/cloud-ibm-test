import logging
from datetime import datetime

from ibm.discovery import get_db_session
from ibm.discovery.common.utils import discovery_locked_resource
from ibm.models import IBMCloud, IBMPlacementGroup, IBMRegion, IBMResourceGroup, IBMResourceLog

LOGGER = logging.getLogger(__name__)


def update_placement_groups(cloud_id, region_name, m_placement_groups):
    if not m_placement_groups:
        return

    start_time = datetime.utcnow()

    placement_groups = list()
    placement_group_ids = list()
    placement_group_id_rgid_dict = dict()
    locked_rid_status = dict()

    for m_placement_group_list in m_placement_groups:
        for m_placement_group in m_placement_group_list.get("response", []):
            # if m_placement_group['lifecycle_state'] != 'stable':
            #     continue
            placement_group = IBMPlacementGroup.from_ibm_json_body(json_body=m_placement_group)
            placement_group_id_rgid_dict[placement_group.resource_id] = m_placement_group["resource_group"]["id"]

            placement_groups.append(placement_group)
            placement_group_ids.append(placement_group.resource_id)

        with get_db_session() as session:
            db_region = session.query(IBMRegion).filter_by(name=region_name, cloud_id=cloud_id).first()
            if not db_region:
                LOGGER.info(f"IBMRegion {region_name} not found")
                return

            last_synced_at = m_placement_group_list["last_synced_at"]
            logged_resource = discovery_locked_resource(
                session=session, resource_type=IBMPlacementGroup.__name__, cloud_id=cloud_id,
                sync_start=last_synced_at, region=db_region)
            locked_rid_status.update(logged_resource)

    with get_db_session() as db_session:
        with db_session.no_autoflush:

            db_region = db_session.query(IBMRegion).filter_by(name=region_name, cloud_id=cloud_id).first()
            if not db_region:
                LOGGER.info(f"IBMRegion {region_name} not found")
                return
            region_id = db_region.id

            db_placement_groups = db_session.query(IBMPlacementGroup).filter_by(cloud_id=cloud_id, region_id=region_id)\
                .all()
            for db_placement_group in db_placement_groups:
                if locked_rid_status.get(db_placement_group.resource_id) in [IBMResourceLog.STATUS_ADDED,
                                                                             IBMResourceLog.STATUS_UPDATED]:
                    continue

                if db_placement_group.resource_id not in placement_group_ids:
                    db_session.delete(db_placement_group)

            db_session.commit()

            db_placement_groups = db_session.query(IBMPlacementGroup).filter_by(cloud_id=cloud_id,
                                                                                region_id=region_id).all()
            db_cloud = db_session.query(IBMCloud).get(cloud_id)
            assert db_cloud

            db_resource_groups = db_session.query(IBMResourceGroup).filter_by(cloud_id=cloud_id).all()
            db_resource_group_id_obj_dict = {
                db_resource_group.resource_id: db_resource_group for db_resource_group in db_resource_groups
            }

            for placement_group in placement_groups:
                if locked_rid_status.get(placement_group.resource_id) in [IBMResourceLog.STATUS_DELETED,
                                                                          IBMResourceLog.STATUS_UPDATED]:
                    continue
                placement_group.dis_add_update_db(
                    db_session=db_session, db_placement_groups=db_placement_groups, db_cloud=db_cloud,
                    db_resource_group=db_resource_group_id_obj_dict.get(
                        placement_group_id_rgid_dict[placement_group.resource_id]),
                    db_region=db_region
                )

            db_session.commit()

    LOGGER.info("** Placement Groups synced in:{}".format((datetime.utcnow() - start_time).total_seconds()))
