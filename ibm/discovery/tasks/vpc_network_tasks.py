import logging
from datetime import datetime

from ibm.discovery import get_db_session
from ibm.discovery.common.utils import discovery_locked_resource
from ibm.models import IBMCloud, IBMRegion, IBMResourceGroup, IBMResourceLog, IBMRoutingTable, IBMVpcNetwork

LOGGER = logging.getLogger(__name__)


def update_vpc_networks(cloud_id, region_name, m_vpc_networks):
    if not m_vpc_networks:
        return

    start_time = datetime.utcnow()

    vpc_networks = list()
    vpc_networks_ids = list()
    vpc_networks_id_rgid_dict = dict()
    locked_rid_status = dict()

    for m_vpc_network_list in m_vpc_networks:
        for m_vpc_network in m_vpc_network_list.get("response", []):
            vpc_network = IBMVpcNetwork.from_ibm_json_body(json_body=m_vpc_network)
            vpc_networks_id_rgid_dict[vpc_network.resource_id] = m_vpc_network["resource_group"]["id"]

            vpc_networks.append(vpc_network)
            vpc_networks_ids.append(vpc_network.resource_id)

        with get_db_session() as session:
            db_region = session.query(IBMRegion).filter_by(name=region_name, cloud_id=cloud_id).first()
            if not db_region:
                LOGGER.info(f"IBMRegion {region_name} not found")
                return

            last_synced_at = m_vpc_network_list["last_synced_at"]
            logged_resource = discovery_locked_resource(
                session=session, resource_type=IBMVpcNetwork.__name__, cloud_id=cloud_id,
                sync_start=last_synced_at, region=db_region)
            locked_rid_status.update(logged_resource)

    with get_db_session() as session:
        with session.no_autoflush:
            db_region = session.query(IBMRegion).filter_by(name=region_name, cloud_id=cloud_id).first()
            if not db_region:
                LOGGER.info(f"IBMRegion {region_name} not found")
                return

            region_id = db_region.id
            db_vpc_networks = \
                session.query(IBMVpcNetwork).filter_by(cloud_id=cloud_id, region_id=region_id).all()

            for db_vpc_network in db_vpc_networks:
                if locked_rid_status.get(db_vpc_network.resource_id) in [IBMResourceLog.STATUS_ADDED,
                                                                         IBMResourceLog.STATUS_UPDATED]:
                    continue

                if db_vpc_network.resource_id not in vpc_networks_ids:
                    session.delete(db_vpc_network)

            session.commit()

            db_cloud = session.query(IBMCloud).get(cloud_id)
            assert db_cloud

            for vpc_network in vpc_networks:
                if locked_rid_status.get(vpc_network.resource_id) in [IBMResourceLog.STATUS_DELETED,
                                                                      IBMResourceLog.STATUS_UPDATED]:
                    continue

                db_resource_group = session.query(IBMResourceGroup).filter_by(cloud_id=cloud_id,
                                                                              resource_id=vpc_networks_id_rgid_dict.get(
                                                                                  vpc_network.resource_id)).first()
                if not db_resource_group:
                    continue

                db_vpc_network = session.query(IBMVpcNetwork).filter_by(cloud_id=cloud_id, region_id=region_id,
                                                                        resource_id=vpc_network.resource_id).first()

                vpc_network.dis_add_update_db(
                    session=session,
                    db_vpc_network=db_vpc_network,
                    db_cloud=db_cloud,
                    db_resource_group=db_resource_group,
                    db_region=db_region
                )

            session.commit()

    LOGGER.info("** VPC Networks synced in:{}".format((datetime.utcnow() - start_time).total_seconds()))


def update_vpc_routes(cloud_id, region_name, m_vpc_routes):
    if not m_vpc_routes:
        return

    start_time = datetime.utcnow()

    vpc_routes = list()
    vpc_routes_ids = list()
    vpc_routes_id_vpcid_dict = dict()
    locked_rid_status = dict()

    for m_vpc_route_list in m_vpc_routes:
        for m_vpc_route in m_vpc_route_list.get("response", []):
            vpc_route = IBMRoutingTable.from_ibm_json_body(json_body=m_vpc_route)
            vpc_routes_id_vpcid_dict[vpc_route.resource_id] = m_vpc_route["href"].split("/")[5]
            vpc_routes.append(vpc_route)
            vpc_routes_ids.append(vpc_route.resource_id)

        with get_db_session() as session:
            db_region = session.query(IBMRegion).filter_by(name=region_name, cloud_id=cloud_id).first()
            if not db_region:
                LOGGER.info(f"IBMRegion {region_name} not found")
                return

            last_synced_at = m_vpc_route_list["last_synced_at"]
            logged_resource = discovery_locked_resource(
                session=session, resource_type=IBMRoutingTable.__name__, cloud_id=cloud_id,
                sync_start=last_synced_at, region=db_region)
            locked_rid_status.update(logged_resource)

    with get_db_session() as session:
        with session.no_autoflush:
            db_region = session.query(IBMRegion).filter_by(name=region_name, cloud_id=cloud_id).first()
            if not db_region:
                LOGGER.info(f"IBMRegion {region_name} not found")
                return

            region_id = db_region.id

            db_vpc_networks = \
                session.query(IBMVpcNetwork).filter_by(cloud_id=cloud_id, region_id=region_id).all()

            db_vpc_routes = []
            for db_vpc_network in db_vpc_networks:
                db_vpc_routes.extend(db_vpc_network.routing_tables.all())

            for db_vpc_route in db_vpc_routes:
                if locked_rid_status.get(db_vpc_route.resource_id) in [IBMResourceLog.STATUS_ADDED,
                                                                       IBMResourceLog.STATUS_UPDATED]:
                    continue

                if db_vpc_route.resource_id not in vpc_routes_ids:
                    session.delete(db_vpc_route)

            session.commit()

            db_cloud = session.query(IBMCloud).get(cloud_id)
            assert db_cloud

            for vpc_route in vpc_routes:
                if locked_rid_status.get(vpc_route.resource_id) in [IBMResourceLog.STATUS_DELETED,
                                                                    IBMResourceLog.STATUS_UPDATED]:
                    continue

                db_vpc_network = session.query(IBMVpcNetwork).filter_by(cloud_id=cloud_id, region_id=region_id,
                                                                        resource_id=vpc_routes_id_vpcid_dict.get(
                                                                            vpc_route.resource_id)).first()
                if not db_vpc_network:
                    continue
                db_vpc_route = session.query(IBMRoutingTable).filter_by(cloud_id=cloud_id, region_id=region_id,
                                                                        resource_id=vpc_route.resource_id).first()

                vpc_route.dis_add_update_db(
                    session=session,
                    db_vpc_route=db_vpc_route,
                    db_cloud=db_cloud,
                    db_vpc_network=db_vpc_network,
                    db_region=db_region
                )

                session.commit()

    LOGGER.info("** VPC Routes synced in:{}".format((datetime.utcnow() - start_time).total_seconds()))
