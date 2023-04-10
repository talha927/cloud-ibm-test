import logging
from datetime import datetime

from ibm.discovery import get_db_session
from ibm.discovery.common.utils import discovery_locked_resource
from ibm.models import IBMCloud, IBMRegion, IBMResourceLog, IBMSubnet, IBMSubnetReservedIp, IBMZone

LOGGER = logging.getLogger(__name__)


def update_subnets(cloud_id, region_name, m_subnets):
    if not m_subnets:
        return

    start_time = datetime.utcnow()

    subnets = list()
    subnets_ids = list()
    subnets_id_vpcid_dict = dict()
    subnets_id_public_gateway_id_dict = dict()
    subnets_id_network_acl_id_dict = dict()
    subnets_id_rgid_dict = dict()
    subnets_id_routing_table_id_dict = dict()
    subnet_id_zone_name_dict = dict()
    locked_rid_status = dict()

    for m_subnet_list in m_subnets:
        for m_subnet in m_subnet_list.get("response", []):
            # if m_subnet['status'] != 'available':
            #     continue
            subnet = IBMSubnet.from_ibm_json_body(json_body=m_subnet)
            subnets_id_vpcid_dict[subnet.resource_id] = m_subnet["vpc"]["id"]
            if m_subnet.get("public_gateway"):
                subnets_id_public_gateway_id_dict[subnet.resource_id] = m_subnet["public_gateway"]["id"]
            subnets_id_network_acl_id_dict[subnet.resource_id] = m_subnet["network_acl"]["id"]
            subnets_id_rgid_dict[subnet.resource_id] = m_subnet["resource_group"]["id"]
            subnets_id_routing_table_id_dict[subnet.resource_id] = m_subnet["routing_table"]["id"]
            subnet_id_zone_name_dict[subnet.resource_id] = m_subnet["zone"]["name"]

            subnets.append(subnet)
            subnets_ids.append(subnet.resource_id)

        with get_db_session() as session:
            db_region = session.query(IBMRegion).filter_by(name=region_name, cloud_id=cloud_id).first()
            if not db_region:
                LOGGER.info(f"IBMRegion {region_name} not found")
                return

            last_synced_at = m_subnet_list["last_synced_at"]
            logged_resource = discovery_locked_resource(
                session=session, resource_type=IBMSubnet.__name__, cloud_id=cloud_id,
                sync_start=last_synced_at, region=db_region)
            locked_rid_status.update(logged_resource)

    with get_db_session() as session:
        with session.no_autoflush:

            db_region = session.query(IBMRegion).filter_by(name=region_name, cloud_id=cloud_id).first()
            if not db_region:
                LOGGER.info(f"IBMRegion {region_name} not found")
                return
            region_id = db_region.id

            db_subnets = \
                session.query(IBMSubnet).filter_by(cloud_id=cloud_id, region_id=region_id).all()

            for db_subnet in db_subnets:
                if locked_rid_status.get(db_subnet.resource_id) in [IBMResourceLog.STATUS_ADDED,
                                                                    IBMResourceLog.STATUS_UPDATED]:
                    continue
                if db_subnet.resource_id not in subnets_ids:
                    session.delete(db_subnet)

            session.commit()

            db_subnets = session.query(IBMSubnet).filter_by(cloud_id=cloud_id, region_id=region_id).all()
            db_zones = session.query(IBMZone).filter_by(cloud_id=cloud_id).all()
            db_zone_name_obj_dict = {
                db_zone.name: db_zone for db_zone in db_zones
            }

            for subnet in subnets:
                if locked_rid_status.get(subnet.resource_id) in [IBMResourceLog.STATUS_DELETED,
                                                                 IBMResourceLog.STATUS_UPDATED]:
                    continue

                subnet.dis_add_update_db(
                    session=session, db_subnets=db_subnets, cloud_id=cloud_id,
                    vpc_network_id=subnets_id_vpcid_dict.get(subnet.resource_id),
                    public_gateway_id=subnets_id_public_gateway_id_dict.get(subnet.resource_id),
                    network_acl_id=subnets_id_network_acl_id_dict[subnet.resource_id],
                    resource_group_id=subnets_id_rgid_dict.get(subnet.resource_id),
                    routing_table_id=subnets_id_routing_table_id_dict.get(subnet.resource_id),
                    db_zone=db_zone_name_obj_dict.get(subnet_id_zone_name_dict.get(subnet.resource_id))
                )

            session.commit()
    LOGGER.info("** Subnets synced in:{}".format((datetime.utcnow() - start_time).total_seconds()))


def update_subnet_reserved_ips(cloud_id, region_name, m_subnet_reserved_ips):
    if not m_subnet_reserved_ips:
        return

    start_time = datetime.utcnow()

    subnet_reserved_ips = list()
    subnet_reserved_ips_ids = list()
    subnet_reserved_ips_id_subnet_id_dict = dict()

    for m_subnet_reserved_ip_list in m_subnet_reserved_ips:
        for m_subnet_reserved_ip in m_subnet_reserved_ip_list.get("response", []):
            subnet_reserved_ip = IBMSubnetReservedIp.from_ibm_json_body(json_body=m_subnet_reserved_ip)
            subnet_reserved_ips_id_subnet_id_dict[subnet_reserved_ip.resource_id] = \
                m_subnet_reserved_ip["href"].split("/")[
                    5]

            subnet_reserved_ips.append(subnet_reserved_ip)
            subnet_reserved_ips_ids.append(subnet_reserved_ip.resource_id)

    with get_db_session() as session:
        with session.no_autoflush:
            db_region = session.query(IBMRegion).filter_by(name=region_name, cloud_id=cloud_id).first()
            if not db_region:
                LOGGER.info(f"IBMRegion {region_name} not found")
                return
            region_id = db_region.id

            db_subnet_reserved_ips = session.query(IBMSubnetReservedIp).join(IBMSubnet).filter_by(
                cloud_id=cloud_id, region_id=region_id).all()
            for db_subnet_reserved_ip in db_subnet_reserved_ips:
                if db_subnet_reserved_ip.resource_id not in subnet_reserved_ips_ids:
                    session.delete(db_subnet_reserved_ip)

            session.commit()

            db_cloud = session.query(IBMCloud).get(cloud_id)
            assert db_cloud

            db_subnet_reserved_ips = session.query(IBMSubnetReservedIp).join(IBMSubnet).filter_by(
                cloud_id=cloud_id, region_id=region_id).all()

            db_subnet_reserved_ips_dict = {db_subnet_reserved_ip.resource_id: db_subnet_reserved_ip for
                                           db_subnet_reserved_ip in db_subnet_reserved_ips}
            for subnet_reserved_ip in subnet_reserved_ips:
                subnet_resource_id = subnet_reserved_ips_id_subnet_id_dict.get(subnet_reserved_ip.resource_id)

                db_subnet_reserved_ip = db_subnet_reserved_ips_dict.get(subnet_reserved_ip.resource_id)

                db_subnet = session.query(IBMSubnet).filter_by(cloud_id=cloud_id,
                                                               resource_id=subnet_resource_id).first()
                if not db_subnet:
                    LOGGER.info(
                        f"Provided IBMSubnet with Resource ID: "
                        f"{subnet_resource_id}, "
                        f"Cloud ID: {cloud_id} and Region: {region_name} while inserting "
                        f"IBMSubnetReservedIp {subnet_reserved_ip.resource_id} not found in DB.")
                    continue

                subnet_reserved_ip.dis_add_update_db(
                    session=session, db_subnet_reserved_ip=db_subnet_reserved_ip,
                    db_subnet=db_subnet
                )

            session.commit()

    LOGGER.info("** Subnet Reserved IPs synced in:{}".format((datetime.utcnow() - start_time).total_seconds()))
