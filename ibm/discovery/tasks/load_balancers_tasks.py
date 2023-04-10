import logging
from datetime import datetime

from ibm.discovery import get_db_session
from ibm.discovery.common.utils import discovery_locked_resource
from ibm.models import IBMCloud, IBMListener, IBMLoadBalancer, IBMLoadBalancerProfile, IBMPool, IBMPoolMember, \
    IBMRegion, IBMResourceGroup, IBMResourceLog, IBMSubnet
from ibm.models.ibm.load_balancer_models import IBMListenerAndPolicyCommon

LOGGER = logging.getLogger(__name__)


def update_load_balancers(cloud_id, region_name, m_load_balancers):
    if not m_load_balancers:
        return

    start_time = datetime.utcnow()

    load_balancers = list()
    load_balancers_ids = list()
    load_balancers_id_rgid_dict = dict()
    load_balancers_id_subnet_ids_dict = dict()
    load_balancers_id_lb_profile_id_dict = dict()
    locked_rid_status = dict()

    for m_load_balancer_list in m_load_balancers:
        for m_load_balancer in m_load_balancer_list.get("response", []):
            # if m_load_balancer['provisioning_status'] != 'active':
            #     continue
            load_balancer = IBMLoadBalancer.from_ibm_json_body(json_body=m_load_balancer)
            load_balancers_id_rgid_dict[load_balancer.resource_id] = m_load_balancer["resource_group"]["id"]
            load_balancers_id_lb_profile_id_dict[load_balancer.resource_id] = m_load_balancer["profile"]["name"]
            load_balancers_id_subnet_ids_dict[load_balancer.resource_id] = \
                [m_subnet["id"] for m_subnet in m_load_balancer["subnets"]]

            load_balancers.append(load_balancer)
            load_balancers_ids.append(load_balancer.resource_id)

        with get_db_session() as session:
            db_region = session.query(IBMRegion).filter_by(name=region_name, cloud_id=cloud_id).first()
            if not db_region:
                LOGGER.info(f"IBMRegion {region_name} not found")
                return

            last_synced_at = m_load_balancer_list["last_synced_at"]
            logged_resource = discovery_locked_resource(
                session=session, resource_type=IBMLoadBalancer.__name__, cloud_id=cloud_id,
                sync_start=last_synced_at, region=db_region)
            locked_rid_status.update(logged_resource)

    with get_db_session() as session:
        with session.no_autoflush:

            db_region = session.query(IBMRegion).filter_by(name=region_name, cloud_id=cloud_id).first()
            if not db_region:
                LOGGER.info(f"IBMRegion {region_name} not found")
                return
            region_id = db_region.id

            db_load_balancers = \
                session.query(IBMLoadBalancer).filter_by(cloud_id=cloud_id, region_id=region_id).all()

            for db_load_balancer in db_load_balancers:
                if locked_rid_status.get(db_load_balancer.resource_id) in [IBMResourceLog.STATUS_ADDED,
                                                                           IBMResourceLog.STATUS_UPDATED]:
                    continue
                if db_load_balancer.resource_id not in load_balancers_ids:
                    session.delete(db_load_balancer)

            session.commit()

            db_load_balancers = session.query(IBMLoadBalancer).filter_by(cloud_id=cloud_id, region_id=region_id).all()

            db_cloud = session.query(IBMCloud).get(cloud_id)
            assert db_cloud

            db_resource_groups_id_obj_dict = {
                db_resource_group.resource_id: db_resource_group for db_resource_group in
                session.query(IBMResourceGroup).filter_by(cloud_id=cloud_id).all()
            }

            db_lb_profiles_name_obj_dict = {
                db_lb_profile.name: db_lb_profile for db_lb_profile in
                session.query(IBMLoadBalancerProfile).all()
            }

            db_subnets_id_obj_dict = {
                db_subnet.resource_id: db_subnet for db_subnet in
                session.query(IBMSubnet).filter_by(cloud_id=cloud_id, region_id=region_id).all()
            }

            for load_balancer in load_balancers:
                if locked_rid_status.get(load_balancer.resource_id) in [IBMResourceLog.STATUS_DELETED,
                                                                        IBMResourceLog.STATUS_UPDATED]:
                    continue
                lb_db_subnets = [
                    db_subnets_id_obj_dict.get(subnet_id) for subnet_id in
                    load_balancers_id_subnet_ids_dict.get(load_balancer.resource_id) if subnet_id
                ]

                db_vpc_network = None
                for lb_db_subnet in lb_db_subnets:
                    if not lb_db_subnet:
                        continue
                    if lb_db_subnet.vpc_network:
                        db_vpc_network = lb_db_subnet.vpc_network
                        break
                if not db_vpc_network:
                    continue

                load_balancer.dis_add_update_db(
                    session=session,
                    db_load_balancers=db_load_balancers,
                    db_cloud=db_cloud,
                    db_resource_group=db_resource_groups_id_obj_dict.get(
                        load_balancers_id_rgid_dict.get(load_balancer.resource_id)
                    ),
                    db_vpc_network=db_vpc_network,
                    db_lb_profile=db_lb_profiles_name_obj_dict.get(
                        load_balancers_id_lb_profile_id_dict.get(load_balancer.resource_id)),
                    db_subnets=lb_db_subnets,
                    db_region=db_region
                )

            session.commit()

    LOGGER.info("** Load Balancers synced in:{}".format((datetime.utcnow() - start_time).total_seconds()))


def update_load_balancer_listeners(cloud_id, region_name, m_load_balancer_listeners):
    if not m_load_balancer_listeners:
        return

    start_time = datetime.utcnow()

    locked_rid_status = dict()
    load_balancer_listeners = list()
    load_balancer_listeners_ids = list()
    load_balancer_listeners_id_lbid_dict = dict()
    load_balancer_listeners_id_http_redirect_pool_dict = dict()
    load_balancer_listeners_id_http_redirect_listener_dict = dict()

    with get_db_session() as db_session:
        with db_session.no_autoflush:
            for m_load_balancer_listener_list in m_load_balancer_listeners:
                for m_load_balancer_listener in m_load_balancer_listener_list.get("response", []):
                    # if m_load_balancer_listener['provisioning_status'] != 'active':
                    #     continue
                    load_balancer_listener = IBMListener.from_ibm_discovery_json_body(
                        json_body=m_load_balancer_listener)
                    if m_load_balancer_listener.get("https_redirect"):
                        https_redirect = IBMListenerAndPolicyCommon.from_ibm_discovery_json_body(
                            type_="LISTENER", json_body=m_load_balancer_listener["https_redirect"])

                        if "id" in m_load_balancer_listener["https_redirect"]:  # pool_target
                            ibm_pool = db_session.query(IBMPool).filter_by(
                                resource_id=m_load_balancer_listener["https_redirect"]["id"], cloud_id=cloud_id).first()
                            if not ibm_pool:
                                continue

                            load_balancer_listeners_id_http_redirect_pool_dict[
                                load_balancer_listener.resource_id] = ibm_pool
                        if "listener" in m_load_balancer_listener["https_redirect"]:  # listener_target
                            ibm_listener = db_session.query(IBMListener).filter_by(
                                resource_id=m_load_balancer_listener["https_redirect"]["listener"]["id"],
                                cloud_id=cloud_id).first()
                            if not ibm_listener:
                                continue

                            load_balancer_listeners_id_http_redirect_listener_dict[
                                load_balancer_listener.resource_id] = ibm_listener

                        load_balancer_listener.https_redirect = https_redirect

                    load_balancer_listeners_id_lbid_dict[load_balancer_listener.resource_id] = \
                        m_load_balancer_listener["href"].split("/")[5]
                    load_balancer_listeners.append(load_balancer_listener)
                    load_balancer_listeners_ids.append(load_balancer_listener.resource_id)

                db_region = db_session.query(IBMRegion).filter_by(name=region_name, cloud_id=cloud_id).first()
                if not db_region:
                    LOGGER.info(f"IBMRegion {region_name} not found")
                    return
                region_id = db_region.id

                last_synced_at = m_load_balancer_listener_list["last_synced_at"]
                logged_resource = discovery_locked_resource(
                    session=db_session, resource_type=IBMListener.__name__, cloud_id=cloud_id,
                    sync_start=last_synced_at, region=db_region)
                locked_rid_status.update(logged_resource)

                db_load_balancers = \
                    db_session.query(IBMLoadBalancer).filter_by(cloud_id=cloud_id, region_id=region_id).all()

                db_load_balancer_listeners = []
                for db_load_balancer in db_load_balancers:
                    db_load_balancer_listeners.extend(db_load_balancer.listeners.all())

                for db_load_balancer_listener in db_load_balancer_listeners:
                    if locked_rid_status.get(db_load_balancer_listener.resource_id) in [IBMResourceLog.STATUS_ADDED,
                                                                                        IBMResourceLog.STATUS_UPDATED]:
                        continue
                    if db_load_balancer_listener.resource_id not in load_balancer_listeners_ids:
                        db_session.delete(db_load_balancer_listener)

                db_session.commit()

                db_load_balancers = \
                    db_session.query(IBMLoadBalancer).filter_by(cloud_id=cloud_id, region_id=region_id).all()

                db_load_balancers_id_listeners_dict = {}
                db_load_balancers_id_obj_dict = {}
                for db_load_balancer in db_load_balancers:
                    db_load_balancers_id_listeners_dict[db_load_balancer.resource_id] = db_load_balancer.listeners.all()
                    db_load_balancers_id_obj_dict[db_load_balancer.resource_id] = db_load_balancer

                for load_balancer_listener in load_balancer_listeners:
                    if locked_rid_status.get(load_balancer_listener.resource_id) in [IBMResourceLog.STATUS_DELETED,
                                                                                     IBMResourceLog.STATUS_UPDATED]:
                        continue
                    db_load_balancer = db_load_balancers_id_obj_dict.get(
                        load_balancer_listeners_id_lbid_dict.get(load_balancer_listener.resource_id)
                    )
                    if not db_load_balancer:
                        continue
                    load_balancer_listener.dis_add_update_db(
                        db_session=db_session,
                        db_load_balancer_listeners=db_load_balancers_id_listeners_dict.get(
                            db_load_balancer.resource_id),
                        db_load_balancer=db_load_balancer,
                        db_region=db_region,
                        db_pool=load_balancer_listeners_id_http_redirect_pool_dict.get(
                            load_balancer_listener.resource_id),
                        db_listener=load_balancer_listeners_id_http_redirect_listener_dict.get(
                            load_balancer_listener.resource_id)
                    )

                db_session.commit()

    LOGGER.info("** Load Balancer Listeners synced in:{}".format((datetime.utcnow() - start_time).total_seconds()))


def update_load_balancer_pools(cloud_id, region_name, m_load_balancer_pools):
    if not m_load_balancer_pools:
        return

    start_time = datetime.utcnow()

    load_balancer_pools = list()
    load_balancer_pools_ids = list()
    load_balancer_pools_id_lbid_dict = dict()
    locked_rid_status = dict()

    for m_load_balancer_pool_list in m_load_balancer_pools:
        for m_load_balancer_pool in m_load_balancer_pool_list.get("response", []):
            # if m_load_balancer_pool['provisioning_status'] != 'active':
            #     continue
            load_balancer_pool = IBMPool.from_ibm_json_body(json_body=m_load_balancer_pool)
            load_balancer_pools_id_lbid_dict[load_balancer_pool.resource_id] = m_load_balancer_pool["href"].split("/")[
                5]
            load_balancer_pools.append(load_balancer_pool)
            load_balancer_pools_ids.append(load_balancer_pool.resource_id)

        with get_db_session() as session:
            db_region = session.query(IBMRegion).filter_by(name=region_name, cloud_id=cloud_id).first()
            if not db_region:
                LOGGER.info(f"IBMRegion {region_name} not found")
                return

            last_synced_at = m_load_balancer_pool_list["last_synced_at"]
            logged_resource = discovery_locked_resource(
                session=session, resource_type=IBMPool.__name__, cloud_id=cloud_id,
                sync_start=last_synced_at, region=db_region)
            locked_rid_status.update(logged_resource)

    with get_db_session() as session:
        with session.no_autoflush:
            db_region = session.query(IBMRegion).filter_by(name=region_name, cloud_id=cloud_id).first()
            if not db_region:
                LOGGER.info(f"IBMRegion {region_name} not found")
                return
            region_id = db_region.id

            db_load_balancers = \
                session.query(IBMLoadBalancer).filter_by(cloud_id=cloud_id, region_id=region_id).all()

            db_load_balancer_pools = []
            for db_load_balancer in db_load_balancers:
                db_load_balancer_pools.extend(db_load_balancer.pools.all())

            for db_load_balancer_pool in db_load_balancer_pools:
                if locked_rid_status.get(db_load_balancer_pool.resource_id) in [IBMResourceLog.STATUS_ADDED,
                                                                                IBMResourceLog.STATUS_UPDATED]:
                    continue
                if db_load_balancer_pool.resource_id not in load_balancer_pools_ids:
                    session.delete(db_load_balancer_pool)

            session.commit()

            db_load_balancers = \
                session.query(IBMLoadBalancer).filter_by(cloud_id=cloud_id, region_id=region_id).all()

            db_load_balancers_id_pools_dict = {}
            db_load_balancers_id_obj_dict = {}
            for db_load_balancer in db_load_balancers:
                db_load_balancers_id_pools_dict[db_load_balancer.resource_id] = db_load_balancer.pools.all()
                db_load_balancers_id_obj_dict[db_load_balancer.resource_id] = db_load_balancer

            load_balancer_id_obj_dict = {
                db_load_balancer.resource_id: db_load_balancer for db_load_balancer in db_load_balancers
            }
            for load_balancer_pool in load_balancer_pools:
                if locked_rid_status.get(load_balancer_pool.resource_id) in [IBMResourceLog.STATUS_DELETED,
                                                                             IBMResourceLog.STATUS_UPDATED]:
                    continue

                db_load_balancer = db_load_balancers_id_obj_dict.get(
                    load_balancer_pools_id_lbid_dict.get(load_balancer_pool.resource_id)
                )
                if not db_load_balancer:
                    continue
                load_balancer_pool.dis_add_update_db(
                    session=session,
                    db_load_balancer_pools=db_load_balancers_id_pools_dict.get(db_load_balancer.resource_id),
                    db_load_balancer=load_balancer_id_obj_dict.get(
                        load_balancer_pools_id_lbid_dict[load_balancer_pool.resource_id]),
                    db_region=db_region
                )

            session.commit()
    LOGGER.info("** Load Balancer Pools synced in:{}".format((datetime.utcnow() - start_time).total_seconds()))


def update_load_balancers_listeners_default_pool(cloud_id, region_name, m_load_balancers_listeners):
    if not m_load_balancers_listeners:
        return

    with get_db_session() as session:
        with session.no_autoflush:

            db_region = session.query(IBMRegion).filter_by(name=region_name, cloud_id=cloud_id).first()
            if not db_region:
                LOGGER.info(f"IBMRegion {region_name} not found")
                return
            region_id = db_region.id

            db_load_balancers = \
                session.query(IBMLoadBalancer).filter_by(cloud_id=cloud_id, region_id=region_id).all()

            db_lb_listeners_id_obj_dict = dict()
            db_lb_pools_id_obj_dict = dict()
            for db_load_balancer in db_load_balancers:
                for db_lb_listener in db_load_balancer.listeners.all():
                    db_lb_listeners_id_obj_dict[db_lb_listener.resource_id] = db_lb_listener

                for db_lb_pool in db_load_balancer.pools.all():
                    db_lb_pools_id_obj_dict[db_lb_pool.resource_id] = db_lb_pool

            for m_load_balancers_listener_list in m_load_balancers_listeners:
                for m_load_balancers_listener in m_load_balancers_listener_list.get("response", []):
                    if not (db_lb_listeners_id_obj_dict.get(m_load_balancers_listener["id"]) and (
                            m_load_balancers_listener.get("default_pool") and db_lb_pools_id_obj_dict.get(
                            m_load_balancers_listener["default_pool"]["id"]))):
                        continue

                    db_lb_listener = db_lb_listeners_id_obj_dict[m_load_balancers_listener["id"]]
                    db_lb_pool = db_lb_pools_id_obj_dict[m_load_balancers_listener["default_pool"]["id"]]

                    db_lb_listener.ibm_pool = db_lb_pool

            session.commit()


def update_lb_pool_members(cloud_id, region_name, m_lb_pool_members):
    if not m_lb_pool_members:
        return

    start_time = datetime.utcnow()

    lb_pool_members = list()
    lb_pool_members_ids = list()
    lb_pool_members_id_lb_pool_id_dict = dict()
    locked_rid_status = dict()

    for m_lb_pool_member_list in m_lb_pool_members:
        for m_lb_pool_member in m_lb_pool_member_list.get("response", []):
            # if m_lb_pool_member['provisioning_status'] != 'active':
            #     continue
            lb_pool_member = IBMPoolMember.from_ibm_json_body(json_body=m_lb_pool_member)
            lb_pool_members_id_lb_pool_id_dict[lb_pool_member.resource_id] = m_lb_pool_member["href"].split("/")[7]
            lb_pool_members.append(lb_pool_member)
            lb_pool_members_ids.append(lb_pool_member.resource_id)

        with get_db_session() as session:
            db_region = session.query(IBMRegion).filter_by(name=region_name, cloud_id=cloud_id).first()
            if not db_region:
                LOGGER.info(f"IBMRegion {region_name} not found")
                return

            last_synced_at = m_lb_pool_member_list["last_synced_at"]
            logged_resource = discovery_locked_resource(
                session=session, resource_type=IBMPoolMember.__name__, cloud_id=cloud_id,
                sync_start=last_synced_at, region=db_region)
            locked_rid_status.update(logged_resource)

    with get_db_session() as session:
        with session.no_autoflush:

            db_region = session.query(IBMRegion).filter_by(name=region_name, cloud_id=cloud_id).first()
            if not db_region:
                LOGGER.info(f"IBMRegion {region_name} not found")
                return
            region_id = db_region.id

            db_load_balancers = \
                session.query(IBMLoadBalancer).filter_by(cloud_id=cloud_id, region_id=region_id).all()

            db_lb_pool_members = []
            for db_load_balancer in db_load_balancers:
                for db_lb_pool in db_load_balancer.pools.all():
                    db_lb_pool_members.extend(db_lb_pool.members.all())

            for db_lb_pool_member in db_lb_pool_members:
                if locked_rid_status.get(db_lb_pool_member.resource_id) in [IBMResourceLog.STATUS_ADDED,
                                                                            IBMResourceLog.STATUS_UPDATED]:
                    continue
                if db_lb_pool_member.resource_id not in lb_pool_members_ids:
                    session.delete(db_lb_pool_member)

            session.commit()

            db_load_balancers = \
                session.query(IBMLoadBalancer).filter_by(cloud_id=cloud_id, region_id=region_id).all()

            db_lb_pools_id_members_dict = {}
            db_lb_pool_id_obj_dict = {}
            for db_load_balancer in db_load_balancers:
                for db_lb_pool in db_load_balancer.pools.all():
                    db_lb_pool_id_obj_dict[db_lb_pool.resource_id] = db_lb_pool
                    db_lb_pools_id_members_dict[db_lb_pool.resource_id] = db_lb_pool.members.all()

            for lb_pool_member in lb_pool_members:
                if locked_rid_status.get(lb_pool_member.resource_id) in [IBMResourceLog.STATUS_DELETED,
                                                                         IBMResourceLog.STATUS_UPDATED]:
                    continue
                db_lb_pool = db_lb_pool_id_obj_dict.get(
                    lb_pool_members_id_lb_pool_id_dict.get(lb_pool_member.resource_id))
                if not db_lb_pool:
                    continue
                lb_pool_member.dis_add_update_db(
                    session=session,
                    db_lb_pool_members=db_lb_pools_id_members_dict.get(db_lb_pool.resource_id),
                    db_lb_pool=db_lb_pool
                )

            session.commit()

    LOGGER.info("** Load Balancer Pools Members synced in:{}".format((datetime.utcnow() - start_time).total_seconds()))


def update_load_balancer_profiles(m_load_balancer_profiles):
    start_time = datetime.utcnow()

    load_balancer_profiles = list()
    load_balancer_profiles_names = list()

    for m_load_balancer_profile_list in m_load_balancer_profiles:
        for m_load_balancer_profile in m_load_balancer_profile_list.get("response", []):
            load_balancer_profile = IBMLoadBalancerProfile.from_ibm_json_body(json_body=m_load_balancer_profile)

            load_balancer_profiles.append(load_balancer_profile)
            load_balancer_profiles_names.append(load_balancer_profile.name)

    with get_db_session() as db_session:
        with db_session.no_autoflush:
            db_load_balancer_profiles = db_session.query(IBMLoadBalancerProfile).all()

            for load_balancer_profile in load_balancer_profiles:
                load_balancer_profile.dis_add_update_db(
                    db_session=db_session,
                    db_load_balancer_profiles=db_load_balancer_profiles,
                )

            db_session.commit()

    LOGGER.info("** Load Balancer Profiles synced in:{}".format((datetime.utcnow() - start_time).total_seconds()))
