import logging

from ibm.models import IBMVolume, IBMResourceTracking, IBMFloatingIP, IBMPublicGateway, IBMVpnGateway, IBMImage, \
    IBMDedicatedHost, IBMEndpointGateway, IBMLoadBalancer, IBMIdleResource, IBMSnapshot, IBMInstance

LOGGER = logging.getLogger(__name__)

RESOURCE_TRACKING_RESOURCE_TYPE_MAPPER = {
    IBMVolume.__name__: IBMResourceTracking.VOLUME,
    IBMFloatingIP.__name__: IBMResourceTracking.FLOATING_IP,
    IBMPublicGateway.__name__: IBMResourceTracking.PUBLIC_GATEWAY,
    IBMVpnGateway.__name__: IBMResourceTracking.VPN,
    IBMImage.__name__: IBMResourceTracking.CUSTOM_IMAGE,
    IBMDedicatedHost.__name__: IBMResourceTracking.DEDICATED_HOST,
    IBMEndpointGateway.__name__: IBMResourceTracking.UNATTACHED_VPE,
    IBMLoadBalancer.__name__: IBMResourceTracking.LOAD_BALANCER,
    IBMSnapshot.__name__: IBMResourceTracking.SNAPSHOT,
    IBMInstance.__name__: IBMResourceTracking.INSTANCE
}

INDIVIDUAL_RESOURCE_TYPE_MAPPER = {
    IBMVolume.__name__: IBMResourceTracking.VOLUMES,
    IBMFloatingIP.__name__: IBMResourceTracking.FLOATING_IPS,
    IBMPublicGateway.__name__: IBMResourceTracking.PUBLIC_GATEWAYS,
    IBMVpnGateway.__name__: IBMResourceTracking.VPNS,
    IBMImage.__name__: IBMResourceTracking.CUSTOM_IMAGES,
    IBMDedicatedHost.__name__: IBMResourceTracking.DEDICATED_HOSTS,
    IBMEndpointGateway.__name__: IBMResourceTracking.UNATTACHED_VPES,
    IBMLoadBalancer.__name__: IBMResourceTracking.LOAD_BALANCERS,
    IBMSnapshot.__name__: IBMResourceTracking.SNAPSHOTS,
    IBMInstance.__name__: IBMResourceTracking.INSTANCES
}


def create_resource_tracking_object(db_resource, action_type, session=None):
    """
    This Function creates new object for IBMResourceTracking
    """

    idle_resource = session.query(IBMIdleResource).filter_by(cloud_id=db_resource.cloud_id,
                                                             db_resource_id=db_resource.id).first()
    if idle_resource:
        new_resource_tracking_obj = IBMResourceTracking(
            resource_type=RESOURCE_TRACKING_RESOURCE_TYPE_MAPPER[db_resource.__class__.__name__],
            action_type=action_type,
            resource_json=idle_resource.resource_json,
            estimated_savings=idle_resource.resource_json.get("cost") if idle_resource.resource_json.get(
                "cost") else 0.00
        )
        region = db_resource.region if hasattr(db_resource, "region_id") else None
        new_resource_tracking_obj.region = region
        new_resource_tracking_obj.ibm_cloud = db_resource.ibm_cloud
        session.delete(idle_resource)
        session.commit()
