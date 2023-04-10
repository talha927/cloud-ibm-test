import logging
from datetime import datetime

from ibm.discovery import get_db_session
from ibm.discovery.common.utils import discovery_locked_resource
from ibm.models import IBMCloud, IBMRegion, IBMResourceGroup, IBMResourceLog, IBMSshKey

LOGGER = logging.getLogger(__name__)


def update_ssh_keys(cloud_id, region_name, m_ssh_keys):
    if not m_ssh_keys:
        return

    start_time = datetime.utcnow()
    ssh_keys = list()
    ssh_keys_ids = list()
    ssh_keys_id_rgid_dict = dict()
    locked_rid_status = dict()
    for m_ssh_key_list in m_ssh_keys:
        for m_ssh_key in m_ssh_key_list.get("response", []):
            ssh_key = IBMSshKey.from_ibm_json_body(json_body=m_ssh_key)
            ssh_keys_id_rgid_dict[ssh_key.resource_id] = m_ssh_key["resource_group"]["id"]

            ssh_keys.append(ssh_key)
            ssh_keys_ids.append(ssh_key.resource_id)

        last_synced_at = m_ssh_key_list["last_synced_at"]
        with get_db_session() as session:
            db_region = session.query(IBMRegion).filter_by(name=region_name, cloud_id=cloud_id).first()
            if not db_region:
                LOGGER.info(f"IBMRegion {region_name} not found")
                return

            logged_resource = discovery_locked_resource(
                session=session, resource_type=IBMSshKey.__name__, cloud_id=cloud_id,
                sync_start=last_synced_at, region=db_region)
            locked_rid_status.update(logged_resource)

    with get_db_session() as session:
        with session.no_autoflush:

            db_region = session.query(IBMRegion).filter_by(name=region_name, cloud_id=cloud_id).first()
            if not db_region:
                LOGGER.info(f"IBMRegion {region_name} not found")
                return
            region_id = db_region.id

            db_ssh_keys = session.query(IBMSshKey).filter_by(cloud_id=cloud_id, region_id=region_id).all()
            for db_ssh_key in db_ssh_keys:
                if locked_rid_status.get(db_ssh_key.resource_id) in [IBMResourceLog.STATUS_ADDED,
                                                                     IBMResourceLog.STATUS_UPDATED]:
                    continue
                if db_ssh_key.resource_id not in ssh_keys_ids:
                    session.delete(db_ssh_key)

            session.commit()
            db_cloud = session.query(IBMCloud).get(cloud_id)
            assert db_cloud

            for ssh_key in ssh_keys:
                if locked_rid_status.get(ssh_key.resource_id) in [IBMResourceLog.STATUS_DELETED,
                                                                  IBMResourceLog.STATUS_UPDATED]:
                    continue

                db_ssh_key = session.query(IBMSshKey).filter_by(cloud_id=cloud_id, region_id=region_id,
                                                                resource_id=ssh_key.resource_id).first()
                db_resource_group = session.query(IBMResourceGroup).filter_by(cloud_id=cloud_id,
                                                                              resource_id=ssh_keys_id_rgid_dict[
                                                                                  ssh_key.resource_id]).first()
                if not db_resource_group:
                    continue

                ssh_key.dis_add_update_db(
                    session=session, db_ssh_key=db_ssh_key, db_cloud=db_cloud,
                    db_resource_group=db_resource_group,
                    db_region=db_region
                )

            session.commit()

    LOGGER.info("** SSH Keys synced in: {}".format((datetime.utcnow() - start_time).total_seconds()))
