import logging
from datetime import datetime

from sqlalchemy.orm.exc import ObjectDeletedError

from ibm.discovery import get_db_session
from ibm.models import IBMCloud, IBMDedicatedHost, IBMFloatingIP, IBMIdleResource, IBMInstance, IBMPublicGateway, \
    IBMRegion, IBMVolume, IBMVpnConnection, IBMVpnGateway, IBMImage, IBMSnapshot

LOGGER = logging.getLogger(__name__)


def update_idle_resources(cloud_id, region_name):
    """update Idle Resources"""

    start_time = datetime.utcnow()

    idle_resources_rids = dict()

    with get_db_session() as session:
        ibm_cloud = session.query(IBMCloud).filter_by(id=cloud_id).first()
        assert ibm_cloud

        ibm_region = session.query(IBMRegion).filter_by(name=region_name, cloud_id=cloud_id).first()
        assert ibm_region
        region_id = ibm_region.id

        db_idle_resources = session.query(IBMIdleResource).filter_by(cloud_id=cloud_id, region_id=ibm_region.id,
                                                                     source_type=IBMIdleResource.SOURCE_DISCOVERY) \
            .filter(IBMIdleResource.resource_type != IBMInstance.__tablename__).all()
        for db_idle_resource in db_idle_resources:
            idle_resources_rids[db_idle_resource.db_resource_id] = db_idle_resource

        db_resource_list = session.query(IBMFloatingIP).filter(
            IBMFloatingIP.cloud_id == cloud_id, IBMFloatingIP.region_id == region_id,
            ~IBMFloatingIP.public_gateway.has(), ~IBMFloatingIP.network_interface.has()).all()

        db_resource_list.extend(session.query(IBMPublicGateway).filter(
            IBMPublicGateway.cloud_id == cloud_id, IBMPublicGateway.region_id == region_id,
            ~IBMPublicGateway.subnets.any()).all())

        db_resource_list.extend(session.query(IBMDedicatedHost).filter(
            IBMDedicatedHost.cloud_id == cloud_id, IBMDedicatedHost.region_id == region_id,
            ~IBMDedicatedHost.instances.any()).all())

        db_resource_list.extend(session.query(IBMVpnGateway).filter_by(
            cloud_id=cloud_id, region_id=region_id).join(IBMVpnConnection).filter(
            IBMVpnConnection.status == IBMVpnConnection.STATUS_DOWN).all())

        db_resource_list.extend(session.query(IBMVolume).filter(
            IBMVolume.cloud_id == cloud_id, IBMVolume.region_id == region_id,
            ~IBMVolume.volume_attachments.any()).all())

        db_resource_list.extend(session.query(IBMImage).filter(
            IBMImage.cloud_id == cloud_id, IBMImage.region_id == region_id,
            IBMImage.visibility == IBMImage.TYPE_VISIBLE_PRIVATE).all())

        db_resource_list.extend(session.query(IBMSnapshot).filter(
            IBMSnapshot.cloud_id == cloud_id, IBMSnapshot.region_id == region_id).all())

        for db_resource in db_resource_list:
            if db_resource.id not in idle_resources_rids:
                idle_json = db_resource.to_idle_json(session)
                with session.no_autoflush:
                    new_idle_resource = IBMIdleResource(
                        db_resource_id=db_resource.id,
                        source_type=IBMIdleResource.SOURCE_DISCOVERY,
                        resource_json=idle_json,
                        resource_type=db_resource.__tablename__,
                        reason="Not Attached to any resource",
                        estimated_savings=idle_json["estimated_savings"] if idle_json.get("estimated_savings") else 0.0
                    )

                    new_idle_resource.ibm_cloud = ibm_cloud
                    new_idle_resource.region = ibm_region
                    if isinstance(db_resource, IBMVpnGateway):
                        new_idle_resource.vpc_network = db_resource.vpc_network

            else:
                idle_resources_rids[db_resource.id].update_db(db_resource, session)
                del idle_resources_rids[db_resource.id]

        session.commit()

        for idle_resources_rid in idle_resources_rids:
            try:
                session.delete(idle_resources_rids[idle_resources_rid])
                session.commit()
            except ObjectDeletedError as e:
                LOGGER.warning(e)
                continue

        session.commit()

    LOGGER.info(f"** Idle resources for {region_name} and cloud  {cloud_id}identified successfully:"
                f" {(datetime.utcnow() - start_time).total_seconds()}")
