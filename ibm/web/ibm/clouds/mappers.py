from ibm.models import IBMDedicatedHost, IBMImage, IBMInstance, IBMKubernetesCluster, IBMLoadBalancer, IBMNetworkAcl, \
    IBMPublicGateway, IBMSecurityGroup, IBMSshKey, IBMSubnet, IBMVpcNetwork, IBMVpnGateway

IBM_DASHBOARD_RESOURCE_TYPE_MAPPER = {
    "VPCs": {"resource_type": IBMVpcNetwork, "pin_status": True},
    "Virtual Server Instances": {"resource_type": IBMInstance, "pin_status": True},
    "Kubernetes Clusters": {"resource_type": IBMKubernetesCluster, "pin_status": True},
    "Dedicated Hosts": {"resource_type": IBMDedicatedHost, "pin_status": True},
    "Custom Images": {"resource_type": IBMImage, "pin_status": False},
    "Access Control Lists": {"resource_type": IBMNetworkAcl, "pin_status": True},
    "Security Groups": {"resource_type": IBMSecurityGroup, "pin_status": False},
    "VPNs": {"resource_type": IBMVpnGateway, "pin_status": True},
    "Load Balancers": {"resource_type": IBMLoadBalancer, "pin_status": True},
    "SSH Keys": {"resource_type": IBMSshKey, "pin_status": False},
    "Public Gateways": {"resource_type": IBMPublicGateway, "pin_status": True},
    "Subnets": {"resource_type": IBMSubnet, "pin_status": True}
}
