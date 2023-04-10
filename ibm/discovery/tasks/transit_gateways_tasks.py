import logging
from datetime import datetime

from ibm.discovery import get_db_session
from ibm.discovery.common.utils import discovery_locked_resource
from ibm.models import IBMCloud, IBMTransitGateway, IBMResourceGroup, IBMResourceLog, IBMTransitGatewayConnection, \
    IBMTransitGatewayConnectionPrefixFilter, IBMRegion

LOGGER = logging.getLogger("transit_gateways_tasks.py")


def update_transit_gateways(cloud_id, m_transit_gateways):
    if not m_transit_gateways:
        return

    start_time = datetime.utcnow()

    transit_gateways = list()
    transit_gateways_ids = list()
    transit_gateways_id_rgid_dict = dict()
    locked_rid_status = dict()

    for m_transit_gateway_list in m_transit_gateways:
        for m_transit_gateway in m_transit_gateway_list.get('response', []):
            transit_gateway = IBMTransitGateway.from_ibm_json_body(json_body=m_transit_gateway)
            if "resource_group" in m_transit_gateway:
                transit_gateways_id_rgid_dict[transit_gateway.resource_id] = m_transit_gateway["resource_group"]["id"]

            transit_gateways.append(transit_gateway)
            transit_gateways_ids.append(transit_gateway.resource_id)

            with get_db_session() as session:
                last_synced_at = m_transit_gateway_list["last_synced_at"]
                region_name = m_transit_gateway["location"]
                region = session.query(IBMRegion).filter_by(name=region_name, cloud_id=cloud_id).first()

                logged_resource = discovery_locked_resource(
                    session=session, resource_type=IBMTransitGateway.__name__, cloud_id=cloud_id,
                    sync_start=last_synced_at, region=region)
                locked_rid_status.update(logged_resource)
    with get_db_session() as session:
        with session.no_autoflush:
            db_cloud = session.query(IBMCloud).get(cloud_id)
            assert db_cloud

            db_transit_gateways = session.query(IBMTransitGateway).filter_by(cloud_id=cloud_id).all()
            for db_transit_gateway in db_transit_gateways:
                if locked_rid_status.get(db_transit_gateway.resource_id) in [IBMResourceLog.STATUS_ADDED,
                                                                             IBMResourceLog.STATUS_UPDATED]:
                    continue
                if db_transit_gateway.resource_id not in transit_gateways_ids:
                    session.delete(db_transit_gateway)

            session.commit()

            db_transit_gateways = session.query(IBMTransitGateway).filter_by(cloud_id=cloud_id).all()

            db_resource_groups = session.query(IBMResourceGroup).filter_by(cloud_id=cloud_id).all()
            db_resource_group_id_obj_dict = {
                db_resource_group.resource_id: db_resource_group for db_resource_group in db_resource_groups
            }

            for transit_gateway in transit_gateways:
                if locked_rid_status.get(transit_gateway.resource_id) in [IBMResourceLog.STATUS_DELETED,
                                                                          IBMResourceLog.STATUS_UPDATED]:
                    continue
                db_region = session.query(IBMRegion).filter_by(name=transit_gateway.location, cloud_id=cloud_id).first()
                if not db_region:
                    LOGGER.info(f"IBMRegion {region_name} not found")
                    return

                db_resource_group = db_resource_group_id_obj_dict.get(
                    transit_gateways_id_rgid_dict.get(transit_gateway.resource_id))
                if not db_resource_group:
                    db_resource_group: IBMResourceGroup = session.query(IBMResourceGroup).filter_by(
                        name="Default", cloud_id=cloud_id).first()

                transit_gateway.dis_add_update_db(
                    session=session, db_transit_gateways=db_transit_gateways, db_cloud=db_cloud,
                    db_region=db_region, db_resource_group=db_resource_group)

            session.commit()

    LOGGER.info("** Transit Gateways synced in:{}".format((datetime.utcnow() - start_time).total_seconds()))


def update_transit_gateway_connections(cloud_id, m_transit_gateway_connections):
    if not m_transit_gateway_connections:
        return
    start_time = datetime.utcnow()

    transit_gateway_connections = list()
    transit_gateway_connections_ids = list()
    transit_gateway_rid_dict = dict()
    transit_gateway_connection_prefix_filters_dict = dict()
    locked_rid_status = dict()

    for m_transit_gateway_connection_list in m_transit_gateway_connections:
        for m_transit_gateway_connection in m_transit_gateway_connection_list.get('response', []):
            transit_gateway_connection = IBMTransitGatewayConnection.from_ibm_json_body(
                json_body=m_transit_gateway_connection)

            transit_gateway_rid_dict[transit_gateway_connection.resource_id] = \
                m_transit_gateway_connection["transit_gateway_id"]
            transit_gateway_connection_prefix_filters_dict[transit_gateway_connection.resource_id] = \
                m_transit_gateway_connection.get("prefix_filters")

            transit_gateway_connections.append(transit_gateway_connection)
            transit_gateway_connections_ids.append(transit_gateway_connection.resource_id)

            with get_db_session() as session:
                last_synced_at = m_transit_gateway_connection_list["last_synced_at"]
                transit_gateway = session.query(IBMTransitGateway).filter_by(
                    resource_id=transit_gateway_rid_dict[transit_gateway_connection.resource_id], cloud_id=cloud_id
                ).first()
                if transit_gateway:
                    logged_resource = discovery_locked_resource(
                        session=session, resource_type=IBMTransitGatewayConnection.__name__, cloud_id=cloud_id,
                        sync_start=last_synced_at, region=transit_gateway.region)
                    locked_rid_status.update(logged_resource)

    with get_db_session() as session:
        with session.no_autoflush:
            db_cloud = session.query(IBMCloud).get(cloud_id)
            assert db_cloud

            db_transit_gateway_connections = session.query(IBMTransitGatewayConnection).filter_by(
                cloud_id=cloud_id).join(IBMTransitGateway).filter_by(cloud_id=cloud_id).all()

            for db_transit_gateway_connection in db_transit_gateway_connections:
                if locked_rid_status.get(db_transit_gateway_connection.resource_id) in [IBMResourceLog.STATUS_ADDED,
                                                                                        IBMResourceLog.STATUS_UPDATED]:
                    continue

                if db_transit_gateway_connection.resource_id not in transit_gateway_connections_ids:
                    session.delete(db_transit_gateway_connection)

            session.commit()

            db_transit_gateway_connections = session.query(IBMTransitGatewayConnection).filter_by(
                cloud_id=cloud_id).join(IBMTransitGateway).filter_by(cloud_id=cloud_id).all()

            for transit_gateway_connection in transit_gateway_connections:
                if locked_rid_status.get(transit_gateway_connection.resource_id) in [IBMResourceLog.STATUS_DELETED,
                                                                                     IBMResourceLog.STATUS_UPDATED]:
                    continue
                transit_gateway = session.query(IBMTransitGateway).filter_by(
                    resource_id=transit_gateway_rid_dict[transit_gateway_connection.resource_id], cloud_id=cloud_id
                ).first()
                if not transit_gateway:
                    LOGGER.info(
                        f"Transit Gateway with resource id "
                        f"{transit_gateway_rid_dict[transit_gateway_connection.resource_id]} not found in DB")
                    continue

                transit_gateway_connection.dis_add_update_db(
                    session=session, db_transit_gateway_connections=db_transit_gateway_connections, db_cloud=db_cloud,
                    db_transit_gateway=transit_gateway)

                session.commit()

                # Syncing Transit Gateway Connection Prefix Filters
                transit_gateway_connection_prefix_filters = list()
                transit_gateway_connection_prefix_filters_ids = list()
                prefix_filter_locked_rid_status = dict()

                if transit_gateway_connection_prefix_filters_dict[transit_gateway_connection.resource_id]:
                    for transit_gateway_connection_prefix_filter in transit_gateway_connection_prefix_filters_dict.get(
                            transit_gateway_connection.resource_id, []):
                        transit_gateway_connection_prefix_filter_obj = IBMTransitGatewayConnectionPrefixFilter. \
                            from_ibm_json_body(json_body=transit_gateway_connection_prefix_filter)

                        transit_gateway_connection_prefix_filters.append(transit_gateway_connection_prefix_filter_obj)
                        transit_gateway_connection_prefix_filters_ids.append(
                            transit_gateway_connection_prefix_filter_obj.resource_id)

                        logged_resource = discovery_locked_resource(
                            session=session, resource_type=IBMTransitGatewayConnectionPrefixFilter.__name__,
                            cloud_id=cloud_id,
                            sync_start=last_synced_at, region=transit_gateway.region)
                        prefix_filter_locked_rid_status.update(logged_resource)

                        db_connection_prefix_filters = session.query(
                            IBMTransitGatewayConnectionPrefixFilter).filter_by(cloud_id=cloud_id).join(
                            IBMTransitGatewayConnection). \
                            filter_by(resource_id=transit_gateway_connection.resource_id, cloud_id=cloud_id).all()

                        for db_connection_prefix_filter in db_connection_prefix_filters:
                            if prefix_filter_locked_rid_status.get(
                                    db_connection_prefix_filter.resource_id) in [
                                    IBMResourceLog.STATUS_ADDED, IBMResourceLog.STATUS_UPDATED]:
                                continue
                            if db_connection_prefix_filter.resource_id not in \
                                    transit_gateway_connection_prefix_filters_ids:
                                session.delete(db_connection_prefix_filter)

                        session.commit()

                        db_connection_prefix_filters = session.query(
                            IBMTransitGatewayConnectionPrefixFilter).join(IBMTransitGatewayConnection). \
                            filter_by(cloud_id=cloud_id, resource_id=transit_gateway_connection.resource_id).all()

                        for transit_gateway_connection_prefix_filter in transit_gateway_connection_prefix_filters:
                            if prefix_filter_locked_rid_status.get(
                                    transit_gateway_connection_prefix_filter.resource_id) in [
                                    IBMResourceLog.STATUS_DELETED, IBMResourceLog.STATUS_UPDATED]:
                                continue
                            tg_connection = session.query(IBMTransitGatewayConnection).filter_by(
                                resource_id=transit_gateway_connection.resource_id, cloud_id=cloud_id
                            ).first()
                            if not tg_connection:
                                LOGGER.info(
                                    f"Transit Gateway Connection with resource id "
                                    f"{transit_gateway_connection.resource_id} not found in DB")
                                continue

                            transit_gateway_connection_prefix_filter.dis_add_update_db(
                                session=session,
                                db_transit_gateway_connection_prefix_filters=db_connection_prefix_filters,
                                db_cloud=db_cloud,
                                db_transit_gateway_connection=tg_connection)

                            session.commit()

    LOGGER.info("** Transit Gateway Connections synced in:{}".format((datetime.utcnow() - start_time).total_seconds()))
