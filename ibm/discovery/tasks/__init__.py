from .acls_tasks import set_default_network_acls_and_security_groups, update_network_acls
from .address_prefixes_tasks import update_address_prefixes
from .cos_tasks import update_cloud_object_storages, update_cos_access_keys, update_cos_buckets
from .cost_tasks import update_cost
from .dedicated_host_tasks import update_dedicated_host_disks, update_dedicated_host_groups, \
    update_dedicated_host_profiles, update_dedicated_hosts
from .endpoint_gateways_tasks import update_endpoint_gateways
from .floating_ips_tasks import update_floating_ips
from .geography_tasks import update_regions, update_zones
from .idle_resource_tasks import update_idle_resources
from .images_tasks import update_images, update_operating_systems
from .instance_group_tasks import update_instance_group_manager_actions, update_instance_group_manager_policies, \
    update_instance_group_managers, update_instance_group_memberships, update_instance_groups, update_instance_templates
from .instances_tasks import update_instance_disks, update_instance_profiles, update_instance_volume_attachments, \
    update_instances, update_instances_network_interfaces, update_instances_ssh_keys
from .kubernetes_clusters_tasks import update_cluster_worker_pools, update_cluster_workloads, update_clusters
from .load_balancers_tasks import update_lb_pool_members, update_load_balancer_listeners, update_load_balancer_pools, \
    update_load_balancer_profiles, update_load_balancers, update_load_balancers_listeners_default_pool
from .placement_groups_tasks import update_placement_groups
from .public_gateways_tasks import update_public_gateways
from .resource_groups_tasks import update_resource_groups
from .satellite_clusters_tasks import update_satellite_clusters, update_satellite_cluster_kube_configs
from .security_groups_tasks import update_security_groups
from .snapshots_tasks import update_snapshots
from .ssh_keys_tasks import update_ssh_keys
from .subnets_tasks import update_subnet_reserved_ips, update_subnets
from .tags_tasks import update_tags
from .transit_gateways_tasks import update_transit_gateways, update_transit_gateway_connections
from .volumes_tasks import update_volume_profiles, update_volumes
from .vpc_network_tasks import update_vpc_networks, update_vpc_routes
from .vpns_tasks import update_ike_policies, update_ipsec_policies, update_vpn_connections, update_vpn_gateways

__all__ = [
    "set_default_network_acls_and_security_groups", "update_network_acls",

    "update_address_prefixes",

    "update_tags",

    "update_cost",

    "update_cloud_object_storages", "update_cos_buckets", "update_cos_access_keys",

    "update_dedicated_host_disks", "update_dedicated_host_groups", "update_dedicated_host_profiles",
    "update_dedicated_hosts",

    "update_endpoint_gateways",

    "update_floating_ips",

    "update_images", "update_operating_systems",

    "update_instance_disks", "update_instance_group_manager_actions", "update_instance_group_manager_policies",
    "update_instance_group_managers", "update_instance_group_memberships", "update_instance_groups",
    "update_instance_profiles", "update_instance_templates", "update_instance_volume_attachments",
    "update_instances", "update_instances_network_interfaces", "update_instances_ssh_keys",

    "update_cluster_worker_pools", "update_clusters", "update_cluster_workloads",

    "update_lb_pool_members", "update_load_balancer_listeners", "update_load_balancer_pools",

    "update_load_balancer_profiles", "update_load_balancers", "update_load_balancers_listeners_default_pool",

    "update_placement_groups",

    "update_public_gateways",

    "update_resource_groups",

    "update_security_groups",

    "update_snapshots",

    "update_ssh_keys",

    "update_subnet_reserved_ips", "update_subnets",

    "update_transit_gateways", "update_transit_gateway_connections",

    "update_volume_profiles", "update_volumes",

    "update_vpc_networks", "update_vpc_routes",

    "update_ike_policies", "update_ipsec_policies", "update_vpn_connections", "update_vpn_gateways",

    "update_idle_resources",

    "update_regions", "update_zones",

    "update_satellite_clusters", "update_satellite_cluster_kube_configs"
]
