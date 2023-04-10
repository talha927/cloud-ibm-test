from .cloud_object_storages import COSClient
from .cost import CostClient
from .dedicated_hosts import DedicatedHostsClient
from .endpoint_gateways import EndpointGatewaysClient
from .floating_ips import FloatingIPsClient
from .geography import GeographyClient
from .global_catalog import GlobalCatalogsClient
from .global_search import GlobalSearchClient
from .images import ImagesClient
from .instance_groups import InstanceGroupsClient
from .instances import InstancesClient
from .kubernetes import KubernetesClient
from .load_balancers import LoadBalancersClient
from .network_acls import NetworkACLsClient
from .placement_groups import PlacementGroupsClient
from .private_catalogs import PrivateCatalogsClient
from .public_gateways import PublicGatewaysClient
from .resource_groups import ResourceGroupsClient
from .resource_instances import ResourceInstancesClient
from .security_groups import SecurityGroupsClient
from .snapshots import SnapshotsClient
from .ssh_keys import SSHKeysClient
from .subnets import SubnetsClient
from .transit_gateways import TransitGatewaysClient
from .tags import TagsClient
from .volumes import VolumesClient
from .vpcs import VPCsClient
from .vpns import VPNsClient

__all__ = [
    "COSClient",
    "CostClient",
    "DedicatedHostsClient",
    "EndpointGatewaysClient",
    "FloatingIPsClient",
    "GeographyClient",
    "GlobalCatalogsClient",
    "GlobalSearchClient",
    "ImagesClient",
    "InstancesClient",
    "InstanceGroupsClient",
    "KubernetesClient",
    "LoadBalancersClient",
    "NetworkACLsClient",
    "PublicGatewaysClient",
    "PrivateCatalogsClient",
    "ResourceGroupsClient",
    "ResourceInstancesClient",
    "SecurityGroupsClient",
    "SnapshotsClient",
    "SSHKeysClient",
    "SubnetsClient",
    "TransitGatewaysClient",
    "VolumesClient",
    "VPCsClient",
    "VPNsClient",
    "PlacementGroupsClient",
    "TagsClient"
]
