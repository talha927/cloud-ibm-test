import logging
from datetime import datetime

from ibm.discovery import get_db_session
from ibm.discovery.common.utils import discovery_locked_resource
from ibm.models import IBMCloud, IBMFloatingIP, IBMInstance, IBMPublicGateway, IBMRegion, IBMResourceGroup, \
    IBMResourceLog, IBMZone

LOGGER = logging.getLogger(__name__)


def update_floating_ips(cloud_id, region_name, m_floating_ips):
    if not m_floating_ips:
        return

    start_time = datetime.utcnow()

    floating_ips = list()
    floating_ips_ids = list()
    floating_ips_id_rgid_dict = dict()
    floating_ips_id_target_interface_id_dict = dict()
    floating_ips_id_target_public_gateway_id_dict = dict()
    floating_ips_id_zone_name_dict = dict()
    locked_rid_status = dict()

    for m_floating_ip_list in m_floating_ips:
        for m_floating_ip in m_floating_ip_list.get("response", []):
            # if m_floating_ip['status'] != 'available':
            #     continue
            floating_ip = IBMFloatingIP.from_ibm_json_body(json_body=m_floating_ip)
            floating_ips_id_rgid_dict[floating_ip.resource_id] = m_floating_ip["resource_group"]["id"]
            floating_ips_id_zone_name_dict[floating_ip.resource_id] = m_floating_ip["zone"]["name"]

            if "target" in m_floating_ip and m_floating_ip["target"]["resource_type"] == "network_interface":
                floating_ips_id_target_interface_id_dict[floating_ip.resource_id] = m_floating_ip["target"]["id"]
            elif "target" in m_floating_ip and m_floating_ip["target"]["resource_type"] == "public_gateway":
                floating_ips_id_target_public_gateway_id_dict[floating_ip.resource_id] = m_floating_ip["target"]["id"]

            floating_ips.append(floating_ip)
            floating_ips_ids.append(floating_ip.resource_id)

        with get_db_session() as session:
            db_region = session.query(IBMRegion).filter_by(name=region_name, cloud_id=cloud_id).first()
            if not db_region:
                LOGGER.info(f"IBMRegion {region_name} not found")
                return

            last_synced_at = m_floating_ip_list["last_synced_at"]
            logged_resource = discovery_locked_resource(
                session=session, resource_type=IBMFloatingIP.__name__, cloud_id=cloud_id,
                sync_start=last_synced_at, region=db_region)
            locked_rid_status.update(logged_resource)

    with get_db_session() as db_session:
        with db_session.no_autoflush:
            db_region = db_session.query(IBMRegion).filter_by(name=region_name, cloud_id=cloud_id).first()
            if not db_region:
                LOGGER.info(f"IBMRegion {region_name} not found")
                return
            region_id = db_region.id

            db_floating_ips = \
                db_session.query(IBMFloatingIP).filter_by(cloud_id=cloud_id, region_id=region_id).all()

            for db_floating_ip in db_floating_ips:
                if locked_rid_status.get(db_floating_ip.resource_id) in [IBMResourceLog.STATUS_ADDED,
                                                                         IBMResourceLog.STATUS_UPDATED]:
                    continue

                if db_floating_ip.resource_id not in floating_ips_ids:
                    db_session.delete(db_floating_ip)

            db_session.commit()

            db_cloud = db_session.query(IBMCloud).get(cloud_id)
            assert db_cloud

            db_floating_ips = db_session.query(IBMFloatingIP).filter_by(cloud_id=cloud_id, region_id=region_id).all()

            db_resource_groups = db_session.query(IBMResourceGroup).filter_by(cloud_id=cloud_id).all()
            db_resource_group_id_obj_dict = {
                db_resource_group.resource_id: db_resource_group for db_resource_group in db_resource_groups
            }

            db_instances = \
                db_session.query(IBMInstance).filter_by(cloud_id=cloud_id, region_id=region_id).all()

            db_network_interfaces_id_obj_dict = dict()
            for db_instance in db_instances:
                for db_network_interface in db_instance.network_interfaces.all():
                    db_network_interfaces_id_obj_dict[db_network_interface.resource_id] = db_network_interface

            db_public_gateways = db_session.query(IBMPublicGateway).filter_by(cloud_id=cloud_id,
                                                                              region_id=region_id).all()
            db_public_gateways_id_obj_dict = {
                db_public_gateway.resource_id: db_public_gateway for db_public_gateway in db_public_gateways
            }

            db_zones = db_session.query(IBMZone).filter_by(cloud_id=cloud_id).all()
            db_zone_name_obj_dict = {
                db_zone.name: db_zone for db_zone in db_zones
            }

            for floating_ip in floating_ips:
                if locked_rid_status.get(floating_ip.resource_id) in [IBMResourceLog.STATUS_DELETED,
                                                                      IBMResourceLog.STATUS_UPDATED]:
                    continue
                floating_ip.dis_add_update_db(
                    db_session=db_session, db_floating_ips=db_floating_ips, db_cloud=db_cloud,
                    db_resource_group=db_resource_group_id_obj_dict.get(
                        floating_ips_id_rgid_dict[floating_ip.resource_id]),
                    db_network_interface=db_network_interfaces_id_obj_dict.get(
                        floating_ips_id_target_interface_id_dict.get(floating_ip.resource_id)),
                    db_public_gateway=db_public_gateways_id_obj_dict.get(
                        floating_ips_id_target_public_gateway_id_dict.get(floating_ip.resource_id)),
                    db_zone=db_zone_name_obj_dict[floating_ips_id_zone_name_dict[floating_ip.resource_id]]
                )

            db_session.commit()
    LOGGER.info("** Floating IPs synced in:{}".format((datetime.utcnow() - start_time).total_seconds()))
