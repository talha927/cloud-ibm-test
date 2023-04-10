import logging
from datetime import datetime

from ibm.discovery import get_db_session
from ibm.discovery.common.utils import discovery_locked_resource
from ibm.models import IBMNetworkAcl, IBMRegion, IBMResourceLog, IBMSecurityGroup

LOGGER = logging.getLogger("acls_tasks.py")


def update_network_acls(cloud_id, region_name, m_network_acls):
    if not m_network_acls:
        return

    start_time = datetime.utcnow()

    network_acls = list()
    network_acls_ids = list()
    network_acls_id_rgid_dict = dict()
    network_acls_id_vpc_id_dict = dict()
    locked_rid_status = dict()

    for m_network_acl_list in m_network_acls:
        for m_network_acl in m_network_acl_list.get("response", []):
            network_acl = IBMNetworkAcl.from_ibm_json_body(json_body=m_network_acl)
            network_acls_id_vpc_id_dict[network_acl.resource_id] = m_network_acl["vpc"]["id"]
            network_acls_id_rgid_dict[network_acl.resource_id] = m_network_acl["resource_group"]["id"]
            network_acls.append(network_acl)
            network_acls_ids.append(network_acl.resource_id)

        with get_db_session() as session:
            db_region = session.query(IBMRegion).filter_by(name=region_name, cloud_id=cloud_id).first()
            if not db_region:
                LOGGER.info(f"IBMRegion {region_name} not found")
                return

            last_synced_at = m_network_acl_list["last_synced_at"]
            logged_resource = discovery_locked_resource(
                session=session, resource_type=IBMNetworkAcl.__name__, cloud_id=cloud_id,
                sync_start=last_synced_at, region=db_region)
            locked_rid_status.update(logged_resource)

    with get_db_session() as session:
        with session.no_autoflush:
            db_region = session.query(IBMRegion).filter_by(name=region_name, cloud_id=cloud_id).first()
            if not db_region:
                LOGGER.info(f"IBMRegion {region_name} not found")
                return

            region_id = db_region.id
            db_network_acls = \
                session.query(IBMNetworkAcl).filter_by(cloud_id=cloud_id, region_id=region_id).all()

            for db_network_acl in db_network_acls:
                if locked_rid_status.get(db_network_acl.resource_id) in [IBMResourceLog.STATUS_ADDED,
                                                                         IBMResourceLog.STATUS_UPDATED]:
                    continue

                if db_network_acl.resource_id in network_acls_ids:
                    continue

                session.delete(db_network_acl)

            session.commit()

            for network_acl in network_acls:
                if locked_rid_status.get(network_acl.resource_id) in [IBMResourceLog.STATUS_DELETED,
                                                                      IBMResourceLog.STATUS_UPDATED]:
                    continue
                if not (network_acls_id_vpc_id_dict.get(network_acl.resource_id) and network_acls_id_rgid_dict.get(
                        network_acl.resource_id)):
                    continue

                db_network_acl = \
                    session.query(IBMNetworkAcl).filter_by(cloud_id=cloud_id, region_id=region_id,
                                                           resource_id=network_acl.resource_id).first()
                network_acl.dis_add_update_db(
                    session=session, db_network_acl=db_network_acl, cloud_id=cloud_id,
                    vpc_network_id=network_acls_id_vpc_id_dict[network_acl.resource_id],
                    resource_group_id=network_acls_id_rgid_dict[network_acl.resource_id],
                    db_region=db_region
                )

            session.commit()
    LOGGER.info("** Network Acls synced in:{}".format((datetime.utcnow() - start_time).total_seconds()))


def set_default_network_acls_and_security_groups(cloud_id, region_name, m_vpc_networks):
    if not m_vpc_networks:
        return

    start_time = datetime.utcnow()

    with get_db_session() as session:
        with session.no_autoflush:

            db_region = session.query(IBMRegion).filter_by(name=region_name, cloud_id=cloud_id).first()
            if not db_region:
                LOGGER.info(f"IBMRegion {region_name} not found")
                return
            region_id = db_region.id

            db_network_acls_id_obj_dict = {
                db_network_acl.resource_id: db_network_acl for db_network_acl in
                session.query(IBMNetworkAcl).filter_by(cloud_id=cloud_id, region_id=region_id).all()
            }

            db_security_groups_id_obj_dict = {
                db_network_acl.resource_id: db_network_acl for db_network_acl in
                session.query(IBMSecurityGroup).filter_by(cloud_id=cloud_id, region_id=region_id).all()
            }

            for m_vpc_network_list in m_vpc_networks:
                for m_vpc_network in m_vpc_network_list.get("response", []):
                    if not (db_network_acls_id_obj_dict.get(
                            m_vpc_network["default_network_acl"]["id"]) and db_security_groups_id_obj_dict.get(
                            m_vpc_network["default_security_group"]["id"])):
                        continue

                    db_default_acl = db_network_acls_id_obj_dict[m_vpc_network["default_network_acl"]["id"]]
                    db_default_acl.is_default = True
                    db_default_security_group = db_security_groups_id_obj_dict[
                        m_vpc_network["default_security_group"]["id"]]
                    db_default_security_group.is_default = True
                    session.commit()

            session.commit()
    LOGGER.info("** Default ACL and SG set in:{}".format((datetime.utcnow() - start_time).total_seconds()))
