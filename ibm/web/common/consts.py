from ibm.models import IBMActivityTracking, IBMVpcNetwork, IBMSubnet, IBMSecurityGroup, IBMInstance, IBMCloud, \
    IBMKubernetesCluster, IBMImage, IBMNetworkAcl, IBMVpnGateway, IBMLoadBalancer, IBMSshKey, IBMAddressPrefix, \
    IBMPublicGateway, IBMRoutingTable, IBMPlacementGroup, IBMEndpointGateway, IBMDedicatedHost, IBMInstanceGroup, \
    IBMDedicatedHostGroup

# Aggregated Resources (Which have other related resources in API hierarchy)
DEDICATED_HOST = "dedicated_host"

AGGREGATED_RESOURCE_LIST = [DEDICATED_HOST]

# Draas resource type
RESOURCE_TYPE_IBM_VPC_NETWORK = "IBMVpcNetwork"
RESOURCE_TYPE_IKS = "IKS"

ACTIVITY_TYPE_MAPPER = {
    "POST": IBMActivityTracking.CREATION,
    "DELETE": IBMActivityTracking.DELETION,
}
RESOURCE_TYPE_OBJECT_MAPPER = {
    "vpcs": [IBMVpcNetwork, "VPC Network"],
    "subnets": [IBMSubnet, "Subnet"],
    "security_groups": [IBMSecurityGroup, "Security Group"],
    "instances": [IBMInstance, "Instance"],
    "clouds": [IBMCloud, "Cloud"],
    "kubernetes_clusters": [IBMKubernetesCluster, "Kubernetes Cluster"],
    "images": [IBMImage, "Images"],
    "network_acls": [IBMNetworkAcl, "Network Acl"],
    "vpn_gateways": [IBMVpnGateway, "VPN Gateway"],
    "load_balancers": [IBMLoadBalancer, "Load Balancer"],
    "ssh_keys": [IBMSshKey, "Ssh Key"],
    "address_prefixes": [IBMAddressPrefix, "Address Prefix"],
    "public_gateways": [IBMPublicGateway, "Public Gateway"],
    "routing_tables": [IBMRoutingTable, "Routing Table"],
    "placement_groups": [IBMPlacementGroup, "Placement Group"],
    "endpoint_gateways": [IBMEndpointGateway, "VPE Gateway"],
    "dedicated_hosts": [IBMDedicatedHost, "Dedicated Host"],
    "instance_groups": [IBMInstanceGroup, "Instance Group"]
}

AGGREGATED_TYPE_RESOURCE_OBJECT_MAPPER = {
     "dedicated_host": {
         "groups": [IBMDedicatedHostGroup, "Dedicated Host Group"]
     }
 }

DRAAS_RESOURCE_TYPE_OBJECT_MAPPER = {
    RESOURCE_TYPE_IKS: [IBMKubernetesCluster, "iks_backup_schema", "Kuberenetes Cluster"],
    RESOURCE_TYPE_IBM_VPC_NETWORK: [IBMVpcNetwork, "vpc_backup_schema", "VPC Network"]
}

ACTION_TYPE_MAPPER = {
    IBMActivityTracking.START: "Started",
    IBMActivityTracking.STOP: "Stopped"
}
