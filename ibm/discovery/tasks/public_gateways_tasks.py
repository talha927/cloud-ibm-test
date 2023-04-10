import logging
from datetime import datetime

from ibm.discovery import get_db_session
from ibm.discovery.common.utils import discovery_locked_resource
from ibm.models import IBMPublicGateway, IBMRegion, IBMResourceLog, IBMZone

LOGGER = logging.getLogger(__name__)


def update_public_gateways(cloud_id, region_name, m_public_gateways):
    if not m_public_gateways:
        return

    start_time = datetime.utcnow()

    public_gateways = list()
    public_gateways_ids = list()
    public_gateways_id_vpcid_dict = dict()
    public_gateways_id_rgid_dict = dict()
    public_gateways_id_zone_name_dict = dict()
    locked_rid_status = dict()

    for m_public_gateway_list in m_public_gateways:
        for m_public_gateway in m_public_gateway_list.get("response", []):
            # if m_public_gateway['status'] != 'available':
            #     continue
            public_gateway = IBMPublicGateway.from_ibm_json_body(json_body=m_public_gateway)
            public_gateways_id_vpcid_dict[public_gateway.resource_id] = m_public_gateway["vpc"]["id"]
            public_gateways_id_rgid_dict[public_gateway.resource_id] = m_public_gateway["resource_group"]["id"]
            public_gateways_id_zone_name_dict[public_gateway.resource_id] = m_public_gateway["zone"]["name"]

            public_gateways.append(public_gateway)
            public_gateways_ids.append(public_gateway.resource_id)

        with get_db_session() as session:
            db_region = session.query(IBMRegion).filter_by(name=region_name, cloud_id=cloud_id).first()
            if not db_region:
                LOGGER.info(f"IBMRegion {region_name} not found")
                return

            last_synced_at = m_public_gateway_list["last_synced_at"]
            logged_resource = discovery_locked_resource(
                session=session, resource_type=IBMPublicGateway.__name__, cloud_id=cloud_id,
                sync_start=last_synced_at, region=db_region)
            locked_rid_status.update(logged_resource)

    with get_db_session() as db_session:
        with db_session.no_autoflush:

            db_region = db_session.query(IBMRegion).filter_by(name=region_name, cloud_id=cloud_id).first()
            if not db_region:
                LOGGER.info(f"IBMRegion {region_name} not found")
                return
            region_id = db_region.id

            db_public_gateways = \
                db_session.query(IBMPublicGateway).filter_by(cloud_id=cloud_id, region_id=region_id).all()

            for db_public_gateway in db_public_gateways:
                if locked_rid_status.get(db_public_gateway.resource_id) in [IBMResourceLog.STATUS_ADDED,
                                                                            IBMResourceLog.STATUS_UPDATED]:
                    continue
                if db_public_gateway.resource_id not in public_gateways_ids:
                    db_session.delete(db_public_gateway)

            db_session.commit()

            db_public_gateways = db_session.query(IBMPublicGateway).filter_by(cloud_id=cloud_id,
                                                                              region_id=region_id).all()
            db_zones = db_session.query(IBMZone).filter_by(cloud_id=cloud_id).all()
            db_zone_name_obj_dict = {
                db_zone.name: db_zone for db_zone in db_zones
            }

            for public_gateway in public_gateways:
                if locked_rid_status.get(public_gateway.resource_id) in [IBMResourceLog.STATUS_DELETED,
                                                                         IBMResourceLog.STATUS_UPDATED]:
                    continue
                public_gateway.dis_add_update_db(
                    db_session=db_session, db_public_gateways=db_public_gateways, cloud_id=cloud_id,
                    vpc_network_id=public_gateways_id_vpcid_dict.get(public_gateway.resource_id),
                    resource_group_id=public_gateways_id_rgid_dict.get(public_gateway.resource_id),
                    db_zone=db_zone_name_obj_dict[public_gateways_id_zone_name_dict[public_gateway.resource_id]]
                )

            db_session.commit()

    LOGGER.info("** Public Gateways synced in:{}".format((datetime.utcnow() - start_time).total_seconds()))
