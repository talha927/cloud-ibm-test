from ibm.models import IBMDedicatedHost, IBMFloatingIP, IBMImage, IBMLoadBalancer, IBMPublicGateway, IBMVolume, \
    IBMVpnGateway, IBMSnapshot
from ibm.tasks.ibm.load_balancers import delete_load_balancer
from ibm.web.ibm.dedicated_hosts.utils import delete_ibm_dedicated_host_workflow
from ibm.web.ibm.floating_ips.utils import delete_ibm_floating_ip_workflow
from ibm.web.ibm.images.utils import delete_ibm_image_workflow
from ibm.web.ibm.public_gateways.utils import delete_ibm_public_gateway_workflow
from ibm.web.ibm.volumes.utils import delete_ibm_volume_workflow
from ibm.web.ibm.vpn_gateways.utils import delete_ibm_vpn_gateway_workflow
from ibm.web.ibm.snapshots.utils import delete_ibm_snapshot_workflow

IDLE_RESOURCE_TYPE_MODLE_MAPPER = {
    IBMVolume.RESOURCE_TYPE_VOLUME_KEY: IBMVolume,
    IBMDedicatedHost.RESOURCE_TYPE_DEDICATED_HOST_KEY: IBMDedicatedHost,
    IBMFloatingIP.RESOURCE_TYPE_FLOATING_IP_KEY: IBMFloatingIP,
    IBMLoadBalancer.RESOURCE_TYPE_LOAD_BALANCER_KEY: IBMLoadBalancer,
    IBMPublicGateway.RESOURCE_TYPE_PUBLIC_GATEWAY_KEY: IBMPublicGateway,
    IBMVpnGateway.RESOURCE_TYPE_VPN_KEY: IBMVpnGateway,
    IBMImage.RESOURCE_TYPE_IMAGE_KEY: IBMImage,
    IBMSnapshot.RESOURCE_TYPE_SNAPSHOT_KEY: IBMSnapshot

}

IDLE_RESOURCE_TYPE_DELETE_WORKFLOW_MAPPER = {
    IBMVolume.RESOURCE_TYPE_VOLUME_KEY: delete_ibm_volume_workflow,
    IBMDedicatedHost.RESOURCE_TYPE_DEDICATED_HOST_KEY: delete_ibm_dedicated_host_workflow,
    IBMFloatingIP.RESOURCE_TYPE_FLOATING_IP_KEY: delete_ibm_floating_ip_workflow,
    IBMLoadBalancer.RESOURCE_TYPE_LOAD_BALANCER_KEY: delete_load_balancer,
    IBMPublicGateway.RESOURCE_TYPE_PUBLIC_GATEWAY_KEY: delete_ibm_public_gateway_workflow,
    IBMVpnGateway.RESOURCE_TYPE_VPN_KEY: delete_ibm_vpn_gateway_workflow,
    IBMImage.RESOURCE_TYPE_IMAGE_KEY: delete_ibm_image_workflow,
    IBMSnapshot.RESOURCE_TYPE_SNAPSHOT_KEY: delete_ibm_snapshot_workflow
}
