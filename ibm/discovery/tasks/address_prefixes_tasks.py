import logging
from datetime import datetime

from ibm.discovery import get_db_session
from ibm.discovery.common.utils import discovery_locked_resource
from ibm.models import IBMAddressPrefix, IBMCloud, IBMRegion, IBMResourceLog, IBMVpcNetwork, IBMZone

LOGGER = logging.getLogger(__name__)


def update_address_prefixes(cloud_id, region_name, m_address_prefixes):
    if not m_address_prefixes:
        return

    start_time = datetime.utcnow()

    address_prefixes = list()
    address_prefixes_ids = list()
    address_prefixes_id_vpcid_dict = dict()
    address_prefixes_id_zone_name_dict = dict()
    locked_rid_status = dict()

    for m_address_prefix_list in m_address_prefixes:
        for m_address_prefix in m_address_prefix_list.get("response", []):
            address_prefix = IBMAddressPrefix.from_ibm_json_body(json_body=m_address_prefix)
            address_prefixes_id_vpcid_dict[address_prefix.resource_id] = m_address_prefix["href"].split("/")[5]
            address_prefixes_id_zone_name_dict[address_prefix.resource_id] = m_address_prefix["zone"]["name"]
            address_prefixes.append(address_prefix)
            address_prefixes_ids.append(address_prefix.resource_id)

        with get_db_session() as session:
            db_region = session.query(IBMRegion).filter_by(name=region_name, cloud_id=cloud_id).first()
            if not db_region:
                LOGGER.info(f"IBMRegion {region_name} not found")
                return

            last_synced_at = m_address_prefix_list["last_synced_at"]
            logged_resource = discovery_locked_resource(
                session=session, resource_type=IBMAddressPrefix.__name__, cloud_id=cloud_id,
                sync_start=last_synced_at, region=db_region)
            locked_rid_status.update(logged_resource)

    with get_db_session() as session:
        with session.no_autoflush:
            db_cloud = session.query(IBMCloud).filter_by(id=cloud_id).first()
            assert db_cloud

            db_region = session.query(IBMRegion).filter_by(name=region_name, cloud_id=cloud_id).first()
            if not db_region:
                LOGGER.info(f"IBMRegion {region_name} not found")
                return

            region_id = db_region.id

            db_address_prefixes = \
                session.query(IBMAddressPrefix).filter_by(cloud_id=cloud_id, region_id=region_id).all()

            for db_address_prefix in db_address_prefixes:
                if locked_rid_status.get(db_address_prefix.resource_id) in [IBMResourceLog.STATUS_ADDED,
                                                                            IBMResourceLog.STATUS_UPDATED]:
                    continue
                if db_address_prefix.resource_id not in address_prefixes_ids:
                    session.delete(db_address_prefix)

            session.commit()

            db_zones = session.query(IBMZone).filter_by(cloud_id=cloud_id).all()
            db_zone_name_obj_dict = {
                db_zone.name: db_zone for db_zone in db_zones
            }

            for address_prefix in address_prefixes:
                if locked_rid_status.get(address_prefix.resource_id) in [IBMResourceLog.STATUS_DELETED,
                                                                         IBMResourceLog.STATUS_UPDATED]:
                    continue

                db_address_prefix = \
                    session.query(IBMAddressPrefix).filter_by(cloud_id=cloud_id, region_id=region_id,
                                                              resource_id=address_prefix.resource_id).first()
                db_vpc_network = \
                    session.query(IBMVpcNetwork).filter_by(cloud_id=cloud_id, region_id=region_id,
                                                           resource_id=address_prefixes_id_vpcid_dict.get(
                                                               address_prefix.resource_id)).first()
                if not db_vpc_network:
                    continue

                address_prefix.dis_add_update_db(
                    session=session,
                    db_address_prefix=db_address_prefix,
                    db_cloud=db_cloud,
                    db_vpc_network=db_vpc_network,
                    db_zone=db_zone_name_obj_dict[
                        address_prefixes_id_zone_name_dict[address_prefix.resource_id]],
                )

                session.commit()

    LOGGER.info("** Address Prefixes synced in:{}".format((datetime.utcnow() - start_time).total_seconds()))
