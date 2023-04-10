import logging
from datetime import datetime

from ibm.discovery import get_db_session
from ibm.discovery.common.utils import discovery_locked_resource
from ibm.models import IBMCloud, IBMEndpointGateway, IBMLoadBalancer, IBMNetworkInterface, IBMRegion, \
    IBMResourceGroup, IBMResourceLog, IBMSecurityGroup, IBMVpcNetwork

LOGGER = logging.getLogger(__name__)


def update_security_groups(cloud_id, region_name, m_security_groups):
    if not m_security_groups:
        return

    start_time = datetime.utcnow()

    security_groups = list()
    security_groups_ids = list()
    security_groups_id_vpc_id_dict = dict()
    security_groups_id_rgid_dict = dict()
    security_groups_id_target_vpe_dict = dict()
    security_groups_id_targets_load_balancar_dict = dict()
    security_groups_id_targets_network_interface_dict = dict()
    locked_rid_status = dict()
    with get_db_session() as db_session:
        with db_session.no_autoflush:
            db_region = db_session.query(IBMRegion).filter_by(cloud_id=cloud_id, name=region_name).first()
            if not db_region:
                LOGGER.info(f"IBMRegion {region_name} not found")
                return

            region_id = db_region.id
            for m_security_group_list in m_security_groups:
                for m_security_group in m_security_group_list.get("response", []):
                    security_group = IBMSecurityGroup.from_ibm_json_body(json_body=m_security_group)

                    db_vpc = db_session.query(IBMVpcNetwork).filter_by(
                        cloud_id=cloud_id, resource_id=m_security_group["vpc"]["id"]).first()

                    security_groups_id_vpc_id_dict[security_group.resource_id] = db_vpc

                    db_resource_group = db_session.query(IBMResourceGroup).filter_by(
                        cloud_id=cloud_id, resource_id=m_security_group["resource_group"]["id"]).first()
                    security_groups_id_rgid_dict[security_group.resource_id] = db_resource_group

                    security_groups_id_target_vpe_list = list()
                    security_groups_id_targets_load_balancar_list = list()
                    security_groups_id_targets_network_interface_list = list()

                    for target in m_security_group.get("targets", []):
                        if target.get(IBMNetworkInterface.TYPE_NETWORK_INTERFACE):
                            db_interface = db_session.query(IBMNetworkInterface).filter_by(
                                cloud_id=cloud_id, resource_id=target["id"]).first()

                            security_groups_id_targets_network_interface_list.append(db_interface)
                        elif target.get(IBMEndpointGateway.RESOURCE_TYPE_ENDPOINT_GATEWAY):
                            db_vpe = db_session.query(IBMEndpointGateway).filter_by(
                                cloud_id=cloud_id, resource_id=target["id"]).first()

                            security_groups_id_target_vpe_list.append(db_vpe)
                        else:
                            db_load_balancer = db_session.query(IBMLoadBalancer).filter_by(
                                cloud_id=cloud_id, resource_id=target["id"]).first()

                            security_groups_id_targets_load_balancar_list.append(db_load_balancer)

                    security_groups_id_target_vpe_dict[security_group.resource_id] = security_groups_id_target_vpe_list
                    security_groups_id_targets_load_balancar_dict[security_group.resource_id] = \
                        security_groups_id_targets_load_balancar_list
                    security_groups_id_targets_network_interface_dict[security_group.resource_id] = \
                        security_groups_id_targets_network_interface_list
                    security_groups.append(security_group)
                    security_groups_ids.append(security_group.resource_id)

                last_synced_at = m_security_group_list["last_synced_at"]
                logged_resource = discovery_locked_resource(
                    session=db_session, resource_type=IBMSecurityGroup.__name__, cloud_id=cloud_id,
                    sync_start=last_synced_at, region=db_region)
                locked_rid_status.update(logged_resource)

            db_security_groups = \
                db_session.query(IBMSecurityGroup).filter_by(cloud_id=cloud_id, region_id=region_id).all()

            for db_security_group in db_security_groups:
                if locked_rid_status.get(db_security_group.resource_id) in [IBMResourceLog.STATUS_ADDED,
                                                                            IBMResourceLog.STATUS_UPDATED]:
                    continue

                if db_security_group.resource_id not in security_groups_ids:
                    LOGGER.info(
                        f"Deleting security group {db_security_group.name} and id: {db_security_group.resource_id}")
                    db_session.delete(db_security_group)

            db_session.commit()

            db_cloud = db_session.query(IBMCloud).filter_by(id=cloud_id, deleted=False, status=IBMCloud.STATUS_VALID) \
                .first()
            assert db_cloud, f"IBMCloud {cloud_id} not found."

            db_security_groups = db_session.query(IBMSecurityGroup).filter_by(cloud_id=cloud_id,
                                                                              region_id=region_id).all()

            for security_group in security_groups:
                if locked_rid_status.get(security_group.resource_id) in [IBMResourceLog.STATUS_DELETED,
                                                                         IBMResourceLog.STATUS_UPDATED]:
                    continue
                security_group.dis_add_update_db(
                    session=db_session, db_security_groups=db_security_groups, db_cloud=db_cloud,
                    db_resource_group=security_groups_id_rgid_dict.get(security_group.resource_id),
                    db_vpc_network=security_groups_id_vpc_id_dict.get(security_group.resource_id),
                    db_region=db_region,
                    db_network_interface=security_groups_id_targets_network_interface_dict.get(
                        security_group.resource_id),
                    db_vpe=security_groups_id_target_vpe_dict.get(security_group.resource_id),
                    db_load_balancer=security_groups_id_targets_load_balancar_dict.get(security_group.resource_id)
                )

            db_session.commit()

    LOGGER.info("** Security Groups synced in:{}".format((datetime.utcnow() - start_time).total_seconds()))
