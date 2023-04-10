import logging
from datetime import datetime

from ibm.discovery import get_db_session
from ibm.discovery.common.utils import discovery_locked_resource
from ibm.models import IBMCloud, IBMIKEPolicy, IBMIPSecPolicy, IBMRegion, IBMResourceGroup, IBMResourceLog, IBMSubnet, \
    IBMVpnConnection, \
    IBMVpnGateway

LOGGER = logging.getLogger(__name__)


def update_ike_policies(cloud_id, region_name, m_ike_policies):
    if not m_ike_policies:
        return

    start_time = datetime.utcnow()

    ike_policies = list()
    ike_policies_ids = list()
    ike_policies_id_rgid_dict = dict()
    locked_rid_status = dict()
    for m_ike_policy_list in m_ike_policies:
        for m_ike_policy in m_ike_policy_list.get("response", []):
            ike_policy = IBMIKEPolicy.from_ibm_json_body(json_body=m_ike_policy)
            ike_policies_id_rgid_dict[ike_policy.resource_id] = m_ike_policy["resource_group"]["id"]
            ike_policies.append(ike_policy)
            ike_policies_ids.append(ike_policy.resource_id)

        with get_db_session() as session:
            db_region = session.query(IBMRegion).filter_by(name=region_name, cloud_id=cloud_id).first()
            if not db_region:
                LOGGER.info(f"IBMRegion {region_name} not found")
                return

            last_synced_at = m_ike_policy_list["last_synced_at"]
            logged_resource = discovery_locked_resource(
                session=session, resource_type=IBMIKEPolicy.__name__, cloud_id=cloud_id,
                sync_start=last_synced_at, region=db_region)
            locked_rid_status.update(logged_resource)

    with get_db_session() as session:
        with session.no_autoflush:
            db_region = session.query(IBMRegion).filter_by(name=region_name, cloud_id=cloud_id).first()
            if not db_region:
                LOGGER.info(f"IBMRegion {region_name} not found")
                return
            region_id = db_region.id

            db_ike_policies = \
                session.query(IBMIKEPolicy).filter_by(cloud_id=cloud_id, region_id=region_id).all()

            for db_ike_policy in db_ike_policies:
                if locked_rid_status.get(db_ike_policy.resource_id) in [IBMResourceLog.STATUS_ADDED,
                                                                        IBMResourceLog.STATUS_UPDATED]:
                    continue
                if db_ike_policy.resource_id and db_ike_policy.resource_id not in ike_policies_ids:
                    session.delete(db_ike_policy)

            session.commit()

            db_cloud = session.query(IBMCloud).get(cloud_id)
            assert db_cloud

            db_ike_policies = session.query(IBMIKEPolicy).filter_by(cloud_id=cloud_id, region_id=region_id).all()

            db_resource_groups = session.query(IBMResourceGroup).filter_by(cloud_id=cloud_id).all()
            db_resource_group_id_obj_dict = {
                db_resource_group.resource_id: db_resource_group for db_resource_group in db_resource_groups
            }

            for ike_policy in ike_policies:
                if locked_rid_status.get(ike_policy.resource_id) in [IBMResourceLog.STATUS_DELETED,
                                                                     IBMResourceLog.STATUS_UPDATED]:
                    continue
                ike_policy.dis_add_update_db(
                    session=session, db_ike_policies=db_ike_policies, db_cloud=db_cloud,
                    db_resource_group=db_resource_group_id_obj_dict.get(
                        ike_policies_id_rgid_dict[ike_policy.resource_id]),
                    db_region=db_region
                )

            session.commit()

    LOGGER.info("** IKE Policies synced in:{}".format((datetime.utcnow() - start_time).total_seconds()))


def update_ipsec_policies(cloud_id, region_name, m_ipsec_policies):
    if not m_ipsec_policies:
        return

    start_time = datetime.utcnow()

    ipsec_policies = list()
    ipsec_policies_ids = list()
    ipsec_policies_id_rgid_dict = dict()
    locked_rid_status = dict()

    for m_ipsec_policy_list in m_ipsec_policies:
        for m_ipsec_policy in m_ipsec_policy_list.get("response", []):
            ipsec_policy = IBMIPSecPolicy.from_ibm_json_body(json_body=m_ipsec_policy)
            ipsec_policies_id_rgid_dict[ipsec_policy.resource_id] = m_ipsec_policy["resource_group"]["id"]
            ipsec_policies.append(ipsec_policy)
            ipsec_policies_ids.append(ipsec_policy.resource_id)

        with get_db_session() as session:
            db_region = session.query(IBMRegion).filter_by(name=region_name, cloud_id=cloud_id).first()
            if not db_region:
                LOGGER.info(f"IBMRegion {region_name} not found")
                return

            last_synced_at = m_ipsec_policy_list["last_synced_at"]
            logged_resource = discovery_locked_resource(
                session=session, resource_type=IBMIPSecPolicy.__name__, cloud_id=cloud_id,
                sync_start=last_synced_at, region=db_region)
            locked_rid_status.update(logged_resource)

    with get_db_session() as session:
        with session.no_autoflush:
            db_region = session.query(IBMRegion).filter_by(name=region_name, cloud_id=cloud_id).first()
            if not db_region:
                LOGGER.info(f"IBMRegion {region_name} not found")
                return
            region_id = db_region.id

            db_ipsec_policies = \
                session.query(IBMIPSecPolicy).filter_by(cloud_id=cloud_id, region_id=region_id).all()
            for db_ipsec_policy in db_ipsec_policies:
                if locked_rid_status.get(db_ipsec_policy.resource_id) in [IBMResourceLog.STATUS_ADDED,
                                                                          IBMResourceLog.STATUS_UPDATED]:
                    continue
                if db_ipsec_policy.resource_id and db_ipsec_policy.resource_id not in ipsec_policies_ids:
                    session.delete(db_ipsec_policy)

            session.commit()

            db_cloud = session.query(IBMCloud).get(cloud_id)
            assert db_cloud

            db_ipsec_policies = session.query(IBMIPSecPolicy).filter_by(cloud_id=cloud_id,
                                                                        region_id=region_id).all()

            db_resource_groups = session.query(IBMResourceGroup).filter_by(cloud_id=cloud_id).all()
            db_resource_group_id_obj_dict = {
                db_resource_group.resource_id: db_resource_group for db_resource_group in db_resource_groups
            }

            for ipsec_policy in ipsec_policies:
                if locked_rid_status.get(ipsec_policy.resource_id) in [IBMResourceLog.STATUS_DELETED,
                                                                       IBMResourceLog.STATUS_UPDATED]:
                    continue
                ipsec_policy.dis_add_update_db(
                    session=session, db_ipsec_policies=db_ipsec_policies, db_cloud=db_cloud,
                    db_resource_group=db_resource_group_id_obj_dict.get(
                        ipsec_policies_id_rgid_dict[ipsec_policy.resource_id]),
                    db_region=db_region
                )

            session.commit()

    LOGGER.info("** IPSec Policies synced in:{}".format((datetime.utcnow() - start_time).total_seconds()))


def update_vpn_gateways(cloud_id, region_name, m_vpn_gateways):
    if not m_vpn_gateways:
        return

    start_time = datetime.utcnow()

    vpn_gateways = list()
    vpn_gateways_ids = list()
    vpn_gateways_id_rgid_dict = dict()
    vpn_gateways_id_subnet_id_dict = dict()
    locked_rid_status = dict()

    for m_vpn_gateway_list in m_vpn_gateways:
        for m_vpn_gateway in m_vpn_gateway_list.get("response", []):
            # if m_vpn_gateway['status'] != 'available':
            #     continue
            vpn_gateway = IBMVpnGateway.from_ibm_json_body(json_body=m_vpn_gateway)
            vpn_gateways_id_rgid_dict[vpn_gateway.resource_id] = m_vpn_gateway["resource_group"]["id"]
            vpn_gateways_id_subnet_id_dict[vpn_gateway.resource_id] = m_vpn_gateway["subnet"]["id"]
            vpn_gateways.append(vpn_gateway)
            vpn_gateways_ids.append(vpn_gateway.resource_id)

        with get_db_session() as session:
            db_region = session.query(IBMRegion).filter_by(name=region_name, cloud_id=cloud_id).first()
            if not db_region:
                LOGGER.info(f"IBMRegion {region_name} not found")
                return

            last_synced_at = m_vpn_gateway_list["last_synced_at"]
            logged_resource = discovery_locked_resource(
                session=session, resource_type=IBMVpnGateway.__name__, cloud_id=cloud_id,
                sync_start=last_synced_at, region=db_region)
            locked_rid_status.update(logged_resource)

    with get_db_session() as session:
        with session.no_autoflush:
            db_region = session.query(IBMRegion).filter_by(name=region_name, cloud_id=cloud_id).first()
            if not db_region:
                LOGGER.info(f"IBMRegion {region_name} not found")
                return
            region_id = db_region.id

            db_vpn_gateways = \
                session.query(IBMVpnGateway).filter_by(cloud_id=cloud_id, region_id=region_id).all()

            for db_vpn_gateway in db_vpn_gateways:
                if locked_rid_status.get(db_vpn_gateway.resource_id) in [IBMResourceLog.STATUS_ADDED,
                                                                         IBMResourceLog.STATUS_UPDATED]:
                    continue
                if db_vpn_gateway.resource_id and db_vpn_gateway.resource_id not in vpn_gateways_ids:
                    session.delete(db_vpn_gateway)

            session.commit()

            db_cloud = session.query(IBMCloud).get(cloud_id)
            assert db_cloud

            db_vpn_gateways = session.query(IBMVpnGateway).filter_by(cloud_id=cloud_id, region_id=region_id).all()

            db_resource_groups = session.query(IBMResourceGroup).filter_by(cloud_id=cloud_id).all()
            db_resource_group_id_obj_dict = {
                db_resource_group.resource_id: db_resource_group for db_resource_group in db_resource_groups
            }

            db_subnets = session.query(IBMSubnet).filter_by(cloud_id=cloud_id, region_id=region_id).all()
            db_subnet_id_obj_dict = {
                db_subnet.resource_id: db_subnet for db_subnet in db_subnets
            }

            for vpn_gateway in vpn_gateways:
                if locked_rid_status.get(vpn_gateway.resource_id) in [IBMResourceLog.STATUS_DELETED,
                                                                      IBMResourceLog.STATUS_UPDATED]:
                    continue
                vpn_gateway.dis_add_update_db(
                    session=session, db_vpn_gateways=db_vpn_gateways, db_cloud=db_cloud,
                    db_resource_group=db_resource_group_id_obj_dict.get(
                        vpn_gateways_id_rgid_dict[vpn_gateway.resource_id]),
                    db_subnet=db_subnet_id_obj_dict.get(vpn_gateways_id_subnet_id_dict[vpn_gateway.resource_id]),
                    db_region=db_region
                )

            session.commit()

    LOGGER.info("** VPN Gateways synced in:{}".format((datetime.utcnow() - start_time).total_seconds()))


def update_vpn_connections(cloud_id, region_name, m_vpn_connections):
    if not m_vpn_connections:
        return

    start_time = datetime.utcnow()

    vpn_connections = list()
    vpn_connections_ids = list()
    vpn_connections_id_vpngwid_dict = dict()
    vpn_connections_id_ike_policy_id_dict = dict()
    vpn_connections_id_ipsec_policy_id_dict = dict()
    locked_rid_status = dict()

    for m_vpn_connection_list in m_vpn_connections:
        for m_vpn_connection in m_vpn_connection_list.get("response", []):
            # if m_vpn_connection['status'] != 'up':
            #     continue
            vpn_connection = IBMVpnConnection.from_ibm_json_body(json_body=m_vpn_connection)
            vpn_connections_id_vpngwid_dict[vpn_connection.resource_id] = m_vpn_connection["href"].split("/")[5]
            if "ike_policy" in m_vpn_connection:
                vpn_connections_id_ike_policy_id_dict[vpn_connection.resource_id] = m_vpn_connection["ike_policy"]["id"]
            if "ipsec_policy" in m_vpn_connection:
                vpn_connections_id_ipsec_policy_id_dict[vpn_connection.resource_id] = m_vpn_connection["ipsec_policy"][
                    "id"]
            vpn_connections.append(vpn_connection)
            vpn_connections_ids.append(vpn_connection.resource_id)

        with get_db_session() as session:
            db_region = session.query(IBMRegion).filter_by(name=region_name, cloud_id=cloud_id).first()
            if not db_region:
                LOGGER.info(f"IBMRegion {region_name} not found")
                return

            last_synced_at = m_vpn_connection_list["last_synced_at"]
            logged_resource = discovery_locked_resource(
                session=session, resource_type=IBMIKEPolicy.__name__, cloud_id=cloud_id,
                sync_start=last_synced_at, region=db_region)
            locked_rid_status.update(logged_resource)

    with get_db_session() as session:
        with session.no_autoflush:
            db_region = session.query(IBMRegion).filter_by(name=region_name, cloud_id=cloud_id).first()
            if not db_region:
                LOGGER.info(f"IBMRegion {region_name} not found")
                return

            region_id = db_region.id
            db_vpn_gateways = \
                session.query(IBMVpnGateway).filter_by(cloud_id=cloud_id, region_id=region_id).all()

            db_vpn_connections = []
            for db_vpn_gateway in db_vpn_gateways:
                for db_vpn_connection in db_vpn_gateway.vpn_connections.all():
                    db_vpn_connections.append(db_vpn_connection)

            for db_vpn_connection in db_vpn_connections:
                if locked_rid_status.get(db_vpn_connection.resource_id) in [IBMResourceLog.STATUS_ADDED,
                                                                            IBMResourceLog.STATUS_UPDATED]:
                    continue
                if db_vpn_connection.resource_id and db_vpn_connection.resource_id not in vpn_connections_ids:
                    session.delete(db_vpn_connection)
            session.commit()

            db_vpn_gateways = \
                session.query(IBMVpnGateway).filter_by(cloud_id=cloud_id, region_id=region_id).all()

            db_vpn_gateways_id_obj_dict = dict()
            db_vpn_gateways_id_connections_dict = dict()
            for db_vpn_gateway in db_vpn_gateways:
                db_vpn_gateways_id_obj_dict[db_vpn_gateway.resource_id] = db_vpn_gateway
                db_vpn_gateways_id_connections_dict[db_vpn_gateway.resource_id] = \
                    db_vpn_gateway.vpn_connections.all()

            db_ike_policies_id_obj_dict = {
                db_ike_policy.resource_id: db_ike_policy for db_ike_policy in
                session.query(IBMIKEPolicy).filter_by(cloud_id=cloud_id).all()
            }

            db_ipsec_policies_id_obj_dict = {
                db_ipsec_policy.resource_id: db_ipsec_policy for db_ipsec_policy in
                session.query(IBMIPSecPolicy).filter_by(cloud_id=cloud_id).all()
            }

            for vpn_connection in vpn_connections:
                if locked_rid_status.get(vpn_connection.resource_id) in [IBMResourceLog.STATUS_DELETED,
                                                                         IBMResourceLog.STATUS_UPDATED]:
                    continue
                vpn_connection.dis_add_update_db(
                    session=session,
                    db_vpn_connections=db_vpn_gateways_id_connections_dict.get(
                        vpn_connections_id_vpngwid_dict[vpn_connection.resource_id]
                    ),
                    db_vpn_gateway=db_vpn_gateways_id_obj_dict.get(
                        vpn_connections_id_vpngwid_dict[vpn_connection.resource_id]),
                    db_ike_policy=db_ike_policies_id_obj_dict.get(
                        vpn_connections_id_ike_policy_id_dict.get(vpn_connection.resource_id)),
                    db_ipsec_policy=db_ipsec_policies_id_obj_dict.get(
                        vpn_connections_id_ipsec_policy_id_dict.get(vpn_connection.resource_id))
                )

            session.commit()

    LOGGER.info("** VPN Gateway Connections synced in:{}".format((datetime.utcnow() - start_time).total_seconds()))
