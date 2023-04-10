from ibm.models import IBMAddressPrefix, IBMCloudObjectStorage, IBMCOSBucket, IBMDedicatedHost, IBMDedicatedHostDisk, \
    IBMDedicatedHostGroup, IBMDedicatedHostProfile, IBMFloatingIP, IBMIKEPolicy, IBMImage, IBMInstance, \
    IBMInstanceDisk, IBMInstanceGroup, IBMInstanceGroupManager, IBMInstanceTemplate, IBMIPSecPolicy, \
    IBMKubernetesCluster, IBMKubernetesClusterWorkerPool, IBMKubernetesClusterWorkerPoolZone, IBMListener, \
    IBMListenerPolicy, IBMListenerPolicyRule, IBMLoadBalancer, IBMNetworkAcl, IBMNetworkAclRule, IBMNetworkInterface, \
    IBMPlacementGroup, IBMPool, IBMPoolMember, IBMPublicGateway, IBMRoutingTable, IBMRoutingTableRoute, \
    IBMSecurityGroup, IBMSecurityGroupRule, IBMSnapshot, IBMSshKey, IBMSubnet, IBMTag, IBMVolume, \
    IBMVolumeAttachment, IBMVpcNetwork, IBMVpnConnection, IBMVpnGateway, IBMVPNGatewayMember, IBMTransitGateway, \
    IBMTransitGatewayConnection, IBMTransitGatewayConnectionPrefixFilter

RESOURCE_TYPE_TO_RESOURCE_CLASS_MAPPER = {
    IBMVpcNetwork.__name__: IBMVpcNetwork,
    IBMInstance.__name__: IBMInstance,
    IBMSshKey.__name__: IBMSshKey,
    IBMFloatingIP.__name__: IBMFloatingIP,
    IBMSubnet.__name__: IBMSubnet,
    IBMSnapshot.__name__: IBMSnapshot,
    IBMSecurityGroup.__name__: IBMSecurityGroup,
    IBMNetworkAcl.__name__: IBMNetworkAcl,
    IBMNetworkAclRule.__name__: IBMNetworkAclRule,
    IBMAddressPrefix.__name__: IBMAddressPrefix,
    IBMCloudObjectStorage.__name__: IBMCloudObjectStorage,
    IBMCOSBucket.__name__: IBMCOSBucket,
    IBMDedicatedHost.__name__: IBMDedicatedHost,
    IBMDedicatedHostDisk.__name__: IBMDedicatedHostDisk,
    IBMDedicatedHostGroup.__name__: IBMDedicatedHostGroup,
    IBMDedicatedHostProfile.__name__: IBMDedicatedHostProfile,
    IBMImage.__name__: IBMImage,
    IBMInstanceGroup.__name__: IBMInstanceGroup,
    IBMInstanceGroupManager.__name__: IBMInstanceGroupManager,
    IBMInstanceDisk.__name__: IBMInstanceDisk,
    IBMNetworkInterface.__name__: IBMNetworkInterface,
    IBMInstanceTemplate.__name__: IBMInstanceTemplate,
    IBMKubernetesCluster.__name__: IBMKubernetesCluster,
    IBMKubernetesClusterWorkerPool.__name__: IBMKubernetesClusterWorkerPool,
    IBMKubernetesClusterWorkerPoolZone.__name__: IBMKubernetesClusterWorkerPoolZone,
    IBMListener.__name__: IBMListener,
    IBMListenerPolicy.__name__: IBMListenerPolicy,
    IBMListenerPolicyRule.__name__: IBMListenerPolicyRule,
    IBMLoadBalancer.__name__: IBMLoadBalancer,
    IBMPool.__name__: IBMPool,
    IBMPoolMember.__name__: IBMPoolMember,
    IBMPlacementGroup.__name__: IBMPlacementGroup,
    IBMPublicGateway.__name__: IBMPublicGateway,
    IBMRoutingTable.__name__: IBMRoutingTable,
    IBMRoutingTableRoute.__name__: IBMRoutingTableRoute,
    IBMSecurityGroupRule.__name__: IBMSecurityGroupRule,
    IBMTag.__name__: IBMTag,
    IBMTransitGateway.__name__: IBMTransitGateway,
    IBMTransitGatewayConnection.__name__: IBMTransitGatewayConnection,
    IBMTransitGatewayConnectionPrefixFilter.__name__: IBMTransitGatewayConnectionPrefixFilter,
    IBMVolume.__name__: IBMVolume,
    IBMVolumeAttachment.__name__: IBMVolumeAttachment,
    IBMIKEPolicy.__name__: IBMIKEPolicy,
    IBMIPSecPolicy.__name__: IBMIPSecPolicy,
    IBMVpnConnection.__name__: IBMVpnConnection,
    IBMVpnGateway.__name__: IBMVpnGateway,
    IBMVPNGatewayMember.__name__: IBMVPNGatewayMember,
}
