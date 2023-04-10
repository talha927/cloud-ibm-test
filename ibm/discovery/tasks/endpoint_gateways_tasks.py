import logging
from datetime import datetime

from ibm.discovery import get_db_session
from ibm.discovery.common.utils import discovery_locked_resource
from ibm.models import IBMCloud, IBMEndpointGateway, IBMRegion, IBMResourceGroup, IBMResourceLog, IBMSecurityGroup, \
    IBMSubnetReservedIp, IBMVpcNetwork

LOGGER = logging.getLogger(__name__)


def update_endpoint_gateways(cloud_id, region_name, m_endpoint_gateways):
    if not m_endpoint_gateways:
        return

    start_time = datetime.utcnow()

    endpoint_gateways = list()
    endpoint_gateway_ids = list()
    endpoint_gateway_id_rgid_dict = dict()
    endpoint_gateway_id_vpcid_dict = dict()
    endpoint_gateway_id_sg_ids_dict = dict()
    endpoint_gateway_id_ip_ids_dict = dict()
    locked_rid_status = dict()

    with get_db_session() as db_session:
        with db_session.no_autoflush:
            for m_endpoint_gateway_list in m_endpoint_gateways:
                for m_endpoint_gateway in m_endpoint_gateway_list.get("response", []):
                    # if m_endpoint_gateway['lifecycle_state'] != 'stable':
                    #     continue
                    endpoint_gateway = IBMEndpointGateway.from_ibm_json_body(json_body=m_endpoint_gateway)
                    endpoint_gateway_id_rgid_dict[endpoint_gateway.resource_id] = m_endpoint_gateway["resource_group"][
                        "id"]
                    db_vpc = db_session.query(IBMVpcNetwork).filter_by(
                        cloud_id=cloud_id, resource_id=m_endpoint_gateway["vpc"]["id"]).first()
                    endpoint_gateway_id_vpcid_dict[endpoint_gateway.resource_id] = db_vpc

                    security_group_list = list()
                    for m_security_group in m_endpoint_gateway.get("security_groups", []):
                        security_group = db_session.query(IBMSecurityGroup).filter_by(
                            resource_id=m_security_group["id"], cloud_id=cloud_id).first()
                        if not security_group:
                            continue
                        security_group_list.append(security_group)

                    endpoint_gateway_id_sg_ids_dict[endpoint_gateway.resource_id] = security_group_list

                    reserved_ip_list = list()
                    for m_ip in m_endpoint_gateway.get("ips", []):
                        reserved_ip_resource_id = m_ip["href"].split("/")[-3]
                        reserved_ip = db_session.query(IBMSubnetReservedIp).filter_by(
                            resource_id=reserved_ip_resource_id).first()
                        if not reserved_ip:
                            continue
                        reserved_ip_list.append(reserved_ip)

                    endpoint_gateway_id_ip_ids_dict[endpoint_gateway.resource_id] = reserved_ip_list

                    endpoint_gateways.append(endpoint_gateway)
                    endpoint_gateway_ids.append(endpoint_gateway.resource_id)

                with get_db_session() as session:
                    db_region = session.query(IBMRegion).filter_by(name=region_name, cloud_id=cloud_id).first()
                    if not db_region:
                        LOGGER.info(f"IBMRegion {region_name} not found")
                        return

                    last_synced_at = m_endpoint_gateway_list["last_synced_at"]
                    logged_resource = discovery_locked_resource(
                        session=session, resource_type=IBMEndpointGateway.__name__, cloud_id=cloud_id,
                        sync_start=last_synced_at, region=db_region)
                    locked_rid_status.update(logged_resource)

            db_region = db_session.query(IBMRegion).filter_by(name=region_name, cloud_id=cloud_id).first()
            if not db_region:
                LOGGER.info(f"IBMRegion {region_name} not found")
                return
            region_id = db_region.id

            db_endpoint_gateways = db_session.query(IBMEndpointGateway).filter_by(cloud_id=cloud_id,
                                                                                  region_id=region_id).all()

            for db_endpoint_gateway in db_endpoint_gateways:
                if locked_rid_status.get(db_endpoint_gateway.resource_id) in [IBMResourceLog.STATUS_ADDED,
                                                                              IBMResourceLog.STATUS_UPDATED]:
                    continue

                if db_endpoint_gateway.resource_id not in endpoint_gateway_ids:
                    db_session.delete(db_endpoint_gateway)

            db_session.commit()

            db_cloud = db_session.query(IBMCloud).get(cloud_id)
            assert db_cloud

            for endpoint_gateway in endpoint_gateways:
                if locked_rid_status.get(endpoint_gateway.resource_id) in [IBMResourceLog.STATUS_DELETED,
                                                                           IBMResourceLog.STATUS_UPDATED]:
                    continue

                db_resource_group = db_session.query(IBMResourceGroup). \
                    filter_by(cloud_id=cloud_id,
                              resource_id=endpoint_gateway_id_rgid_dict.get(endpoint_gateway.resource_id)).first()
                if not db_resource_group:
                    continue
                db_endpoint_gateway = db_session.query(IBMEndpointGateway). \
                    filter_by(cloud_id=cloud_id, region_id=region_id, resource_id=endpoint_gateway.resource_id).first()

                endpoint_gateway.dis_add_update_db(
                    db_session=db_session, db_endpoint_gateway=db_endpoint_gateway, db_cloud=db_cloud,
                    db_resource_group=db_resource_group,
                    db_region=db_region,
                    db_vpc=endpoint_gateway_id_vpcid_dict.get(endpoint_gateway.resource_id),
                    db_security_groups=endpoint_gateway_id_sg_ids_dict.get(endpoint_gateway.resource_id),
                    db_reserved_ips=endpoint_gateway_id_ip_ids_dict.get(endpoint_gateway.resource_id)
                )

            db_session.commit()

    LOGGER.info("** Endpoint Gateways synced in:{}".format((datetime.utcnow() - start_time).total_seconds()))
