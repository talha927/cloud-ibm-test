from ibm.models import (
    DisasterRecoveryBackup, DisasterRecoveryResourceBlueprint, IBMAddressPrefix, IBMCloud,
    IBMCloudObjectStorage, IBMCOSBucket, IBMCost, IBMDedicatedHost, IBMDedicatedHostGroup,
    IBMEndpointGateway, IBMFloatingIP, IBMIKEPolicy, IBMImage, IBMInstance, IBMInstanceGroup,
    IBMInstanceGroupManager, IBMInstanceGroupManagerAction, IBMInstanceGroupManagerPolicy,
    IBMInstanceGroupMembership, IBMInstanceTemplate, IBMIPSecPolicy, IBMKubernetesCluster,
    IBMListener, IBMListenerPolicy, IBMListenerPolicyRule, IBMLoadBalancer, IBMLoadBalancerProfile,
    IBMMonitoringToken, IBMNetworkAcl, IBMNetworkAclRule, IBMNetworkInterface, IBMPlacementGroup,
    IBMPool, IBMPoolMember, IBMPublicGateway, IBMResourceGroup, IBMRoutingTable, IBMSecurityGroup,
    IBMSecurityGroupRule, IBMServiceCredentialKey, IBMSnapshot, IBMSshKey, IBMSubnet,
    IBMSubnetReservedIp, IBMTag, IBMTransitGateway, IBMVolume, IBMVolumeAttachment, IBMVpcNetwork,
    IBMVpnConnection, IBMVpnGateway, SoftlayerCloud, WorkflowTask, IBMSatelliteCluster
)
from ibm.models import IBMTransitGatewayConnection, IBMTransitGatewayConnectionPrefixFilter, \
    IBMTransitGatewayRouteReport
from ibm.models.agent.agent_models import OnPremCluster
from ibm.tasks.agent_tasks import discover_on_prem_cluster
from ibm.tasks.agent_tasks.agent_tasks import create_draas_backup_onprem, create_onprem_agent_cluster_backup, \
    create_wait_onprem_agent_cluster_backup, create_wait_onprem_cluster_restore, create_onprem_cluster_restore
from ibm.tasks.consumption_tasks import add_cost_consumption_task, add_backup_consumption_task
from ibm.tasks.cost_analyzer.cost_analyzer_tasks import fetch_ibm_cloud_cost
from ibm.tasks.draas_tasks import create_ibm_resource_backup_task, \
    update_vpc_metadata_for_instances_with_snapshot_references
from ibm.tasks.ibm import (add_account_id_to_cloud, add_ibm_monitoring_tokens,
                           attach_floating_ip_with_network_interface, attach_network_acl_to_subnet,
                           attach_public_gateway_to_subnet, attach_routing_table_to_subnet,
                           attach_target_to_security_group, attach_wait_public_gateway_to_subnet,
                           attach_wait_routing_table_to_subnet, create_address_prefix, create_cos_bucket,
                           create_draas_backup_iks, create_endpoint_gateway, create_floating_ip,
                           create_ibm_dedicated_host, create_ibm_dedicated_host_group, create_ibm_image,
                           create_ibm_instance, create_ibm_instance_export_to_cos, create_ibm_instance_snapshot,
                           create_ibm_network_interface, create_ibm_tag, create_ibm_volume, create_ike_policy,
                           create_image_conversion, create_instance_group, create_instance_group_manager,
                           create_instance_group_manager_action, create_instance_group_manager_policy,
                           create_instance_template, create_instance_volume_attachment, create_ipsec_policy,
                           create_kubernetes_cluster, create_kubernetes_cluster_backup,
                           create_kubernetes_cluster_restore, create_listener, create_listener_policy,
                           create_listener_policy_rule, create_load_balancer, create_load_balancer_pool,
                           create_load_balancer_pool_member, create_network_acl, create_network_acl_rule,
                           create_placement_group, create_public_gateway, create_routing_table, create_security_group,
                           create_security_group_rule, create_snapshot, create_softlayer_backup_instance,
                           create_ssh_key, create_subnet, create_transit_gateway, create_transit_gateway_connection,
                           create_transit_gateway_connection_prefix_filter, create_transit_gateway_route_report,
                           create_vpc_network, create_vpn_connection, create_vpn_gateway, create_wait_endpoint_gateway,
                           create_wait_floating_ip, create_wait_ibm_image, create_wait_ibm_instance,
                           create_wait_ibm_instance_export_to_cos, create_wait_ibm_instance_snapshot,
                           create_wait_ibm_network_interface, create_wait_ibm_volume, create_wait_image_conversion,
                           create_wait_instance_group, create_wait_instance_group_manager_action,
                           create_wait_instance_volume_attachment, create_wait_kubernetes_cluster,
                           create_wait_kubernetes_cluster_backup, create_wait_kubernetes_cluster_restore,
                           create_wait_listener, create_wait_listener_policy, create_wait_listener_policy_rule,
                           create_wait_load_balancer, create_wait_load_balancer_pool,
                           create_wait_load_balancer_pool_member, create_wait_placement_group,
                           create_wait_public_gateway, create_wait_routing_table, create_wait_snapshot,
                           create_wait_softlayer_backup_instance, create_wait_subnet, create_wait_transit_gateway,
                           create_wait_transit_gateway_connection, create_wait_transit_gateway_route_report,
                           create_wait_vpc_network, create_wait_vpn_gateway, delete_address_prefix,
                           delete_all_instance_group_memberships, delete_cos_bucket, delete_dedicated_host,
                           delete_dedicated_host_group, delete_draas_backup, delete_draas_blueprint,
                           delete_endpoint_gateway, delete_floating_ip, delete_ibm_cloud, delete_ibm_tag,
                           delete_ike_policy, delete_image, delete_instance, delete_instance_group,
                           delete_instance_group_manager, delete_instance_group_manager_action,
                           delete_instance_group_manager_policy, delete_instance_group_membership,
                           delete_instance_template, delete_instance_volume_attachment, delete_ipsec_policy,
                           delete_kubernetes_cluster, delete_listener, delete_listener_policy,
                           delete_listener_policy_rule, delete_load_balancer, delete_load_balancer_pool,
                           delete_load_balancer_pool_member, delete_network_acl, delete_network_acl_rule,
                           delete_network_interface, delete_placement_group, delete_public_gateway,
                           delete_routing_table, delete_security_group, delete_security_group_rule, delete_snapshot,
                           delete_ssh_key, delete_subnet, delete_transit_gateway, delete_transit_gateway_connection,
                           delete_transit_gateway_connection_prefix_filter, delete_transit_gateway_route_report,
                           delete_volume, delete_volume_attached_snapshots, delete_vpc, delete_vpn_connection,
                           delete_vpn_gateway, delete_wait_all_instance_group_memberships, delete_wait_dedicated_host,
                           delete_wait_endpoint_gateway, delete_wait_floating_ip, delete_wait_image,
                           delete_wait_instance, delete_wait_instance_group, delete_wait_instance_group_manager_action,
                           delete_wait_instance_group_membership, delete_wait_instance_volume_attachment,
                           delete_wait_kubernetes_cluster, delete_wait_listener, delete_wait_listener_policy,
                           delete_wait_listener_policy_rule, delete_wait_load_balancer, delete_wait_load_balancer_pool,
                           delete_wait_load_balancer_pool_member, delete_wait_network_interface,
                           delete_wait_placement_group, delete_wait_public_gateway, delete_wait_routing_table,
                           delete_wait_snapshot, delete_wait_subnet, delete_wait_transit_gateway,
                           delete_wait_transit_gateway_connection, delete_wait_volume, delete_wait_vpc,
                           delete_wait_vpn_connection, delete_wait_vpn_gateway,
                           detach_floating_ip_from_network_interface, detach_public_gateway_from_subnet,
                           detach_target_to_security_group, generate_classic_recommendations_task, get_idle_instances,
                           get_vsi_usage_data, initiate_cos_buckets_sync, release_reserved_ip_for_subnet,
                           reserve_ip_for_subnet, start_ibm_instance_task, start_wait_ibm_instance_task,
                           stop_ibm_instance_task, stop_wait_ibm_instance_task, store_ibm_custom_image,
                           store_wait_ibm_custom_image, sync_classic_kubernetes_task,
                           sync_classic_network_gateways_task, sync_classic_virtual_guest_bandwidth_usage_task,
                           sync_classic_virtual_guest_cpu_usage_task, sync_classic_virtual_guest_memory_usage_task,
                           sync_classic_virtual_guests_usage_task, sync_cluster_workloads, sync_cos,
                           sync_cos_bucket_objects, sync_cos_buckets, sync_credential_keys,
                           sync_endpoint_gateway_targets, sync_load_balancer_profiles, sync_orchestration_versions,
                           sync_softlayer_images, sync_softlayer_instance, sync_softlayer_instances,
                           sync_softlayer_resources_task, sync_workerpool_flavors_for_all_zones_in_region,
                           sync_workerpool_zone_flavors, update_geography, update_ibm_cloud, update_instance,
                           update_instance_group_manager, update_resource_groups, validate_ibm_monitoring_tokens,
                           validate_snapshot, validate_softlayer_account, validate_update_cloud_api_key)
from ibm.tasks.translation_tasks import translate_vpc_construct

MAPPER = {
    DisasterRecoveryResourceBlueprint.__name__: {
        "DELETE": {
            "RUN": delete_draas_blueprint
        },
        "BACKUP": {
            "RUN": create_draas_backup_iks
        },
        "ONPREM_BACKUP": {
            "RUN": create_draas_backup_onprem
        }
    },
    DisasterRecoveryBackup.__name__: {
        "DELETE": {
            "RUN": delete_draas_backup
        }
    },
    "TRANSLATION": {
        "CREATE": {
            "RUN": translate_vpc_construct
        },
    },
    IBMCloud.__name__: {
        "VALIDATE": {
            "RUN": validate_update_cloud_api_key
        },
        "DELETE": {
            "RUN": delete_ibm_cloud
        },
        "SYNC": {
            "RUN": add_account_id_to_cloud
        },
        "UPDATE": {
            "RUN": update_ibm_cloud
        },
        "FETCH_COST": {
            "RUN": fetch_ibm_cloud_cost
        }
    },
    IBMCost.__name__: {
        "CONSUMPTION": {
            "RUN": add_cost_consumption_task
        }
    },
    IBMMonitoringToken.__name__: {
        "ADD": {
            "RUN": add_ibm_monitoring_tokens
        },
        "VALIDATE": {
            "RUN": validate_ibm_monitoring_tokens
        }
    },
    SoftlayerCloud.__name__: {
        "VALIDATE": {
            "RUN": validate_softlayer_account
        },
        "SYNC": {
            "RUN": sync_softlayer_resources_task
        }
    },
    "SoftLayerImage": {
        WorkflowTask.TYPE_SYNC: {
            "RUN": sync_softlayer_images
        },
    },
    "SoftLayerInstances": {
        WorkflowTask.TYPE_SYNC: {
            "RUN": sync_softlayer_instances
        },
    },
    "SoftLayerInstance": {
        WorkflowTask.TYPE_SYNC: {
            "RUN": sync_softlayer_instance
        },
    },
    "SoftLayerVirtualGuest": {
        WorkflowTask.TYPE_SYNC: {
            "RUN": sync_classic_virtual_guests_usage_task
        },
    },
    "SoftLayerNetworkGateway": {
        WorkflowTask.TYPE_SYNC: {
            "RUN": sync_classic_network_gateways_task
        },
    },
    "SoftLayerInstanceMemoryUsage": {
        WorkflowTask.TYPE_SYNC: {
            "RUN": sync_classic_virtual_guest_memory_usage_task
        },
    },
    "SoftLayerInstanceCPUUsage": {
        WorkflowTask.TYPE_SYNC: {
            "RUN": sync_classic_virtual_guest_cpu_usage_task
        },
    },
    "SoftLayerInstanceBandwidthUsage": {
        WorkflowTask.TYPE_SYNC: {
            "RUN": sync_classic_virtual_guest_bandwidth_usage_task
        },
    },
    "SoftLayerRecommendation": {
        WorkflowTask.TYPE_CREATE: {
            "RUN": generate_classic_recommendations_task
        },

    },
    IBMCloudObjectStorage.__name__: {
        "SYNC": {
            "RUN": sync_cos
        }
    },
    IBMServiceCredentialKey.__name__: {
        "SYNC": {
            "RUN": sync_credential_keys
        }
    },
    IBMCOSBucket.__name__: {
        "SYNC-INITIATE": {
            "RUN": initiate_cos_buckets_sync
        },
        "SYNC": {
            "RUN": sync_cos_buckets
        },
        WorkflowTask.TYPE_CREATE: {
            "RUN": create_cos_bucket
        },
        WorkflowTask.TYPE_DELETE: {
            "RUN": delete_cos_bucket
        }
    },
    "IBMCOSBucketObject": {
        "SYNC": {
            "RUN": sync_cos_bucket_objects
        },
    },
    IBMResourceGroup.__name__: {
        "UPDATE": {
            "RUN": update_resource_groups
        },
    },
    "GEOGRAPHY": {
        "UPDATE": {
            "RUN": update_geography
        },
    },
    IBMVpcNetwork.__name__: {
        "CREATE": {
            "RUN": create_vpc_network,
            "WAIT": create_wait_vpc_network
        },
        "DELETE": {
            "RUN": delete_vpc,
            "WAIT": delete_wait_vpc
        },
        "BACKUP": {
            "RUN": create_ibm_resource_backup_task
        },
        "BACKUP_CONSUMPTION": {
            "RUN": add_backup_consumption_task
        },
    },
    IBMVolume.__name__: {
        "CREATE": {
            "RUN": create_ibm_volume,
            "WAIT": create_wait_ibm_volume,
        },
        "DELETE": {
            "RUN": delete_volume,
            "WAIT": delete_wait_volume,
        },
    },
    IBMInstanceGroup.__name__: {
        "CREATE": {
            "RUN": create_instance_group,
            "WAIT": create_wait_instance_group,
        },
        "DELETE": {
            "RUN": delete_instance_group,
            "WAIT": delete_wait_instance_group,
        },
    },
    IBMInstanceGroupMembership.__name__: {
        "DELETE": {
            "RUN": delete_instance_group_membership,
            "WAIT": delete_wait_instance_group_membership,
        },
    },
    f'{IBMInstanceGroupMembership.__name__}-{IBMInstanceGroup.__name__}': {
        "DELETE": {
            "RUN": delete_all_instance_group_memberships,
            "WAIT": delete_wait_all_instance_group_memberships,
        },
    },
    IBMInstanceGroupManager.__name__: {
        "CREATE": {
            "RUN": create_instance_group_manager
        },
        "DELETE": {
            "RUN": delete_instance_group_manager
        },
        "UPDATE": {
            "RUN": update_instance_group_manager,
        },
    },
    IBMInstanceGroupManagerPolicy.__name__: {
        "CREATE": {
            "RUN": create_instance_group_manager_policy
        },
        "DELETE": {
            "RUN": delete_instance_group_manager_policy
        }
    },
    IBMInstanceGroupManagerAction.__name__: {
        "CREATE": {
            "RUN": create_instance_group_manager_action,
            "WAIT": create_wait_instance_group_manager_action,
        },
        "DELETE": {
            "RUN": delete_instance_group_manager_action,
            "WAIT": delete_wait_instance_group_manager_action,
        },
    },
    IBMVolumeAttachment.__name__: {
        "CREATE": {
            "RUN": create_instance_volume_attachment,
            "WAIT": create_wait_instance_volume_attachment,
        },
        "DELETE": {
            "RUN": delete_instance_volume_attachment,
            "WAIT": delete_wait_instance_volume_attachment,
        },
    },
    IBMInstance.__name__: {
        "CREATE": {
            "RUN": create_ibm_instance,
            "WAIT": create_wait_ibm_instance,
        },
        "DELETE": {
            "RUN": delete_instance,
            "WAIT": delete_wait_instance,
        },
        "UPDATE": {
            "RUN": update_instance,
        },
        WorkflowTask.TYPE_SNAPSHOT: {
            "RUN": create_ibm_instance_snapshot,
            "WAIT": create_wait_ibm_instance_snapshot,

        },
        WorkflowTask.TYPE_EXPORT: {
            "RUN": create_ibm_instance_export_to_cos,
            "WAIT": create_wait_ibm_instance_export_to_cos,

        },
        WorkflowTask.TYPE_BACKUP: {
            "RUN": create_softlayer_backup_instance,
            "WAIT": create_wait_softlayer_backup_instance,
        },
        WorkflowTask.TYPE_STOP: {
            "RUN": stop_ibm_instance_task,
            "WAIT": stop_wait_ibm_instance_task
        },
        WorkflowTask.TYPE_START: {
            "RUN": start_ibm_instance_task,
            "WAIT": start_wait_ibm_instance_task
        },
        WorkflowTask.TYPE_UPDATE_METADATA: {
            "RUN": update_vpc_metadata_for_instances_with_snapshot_references
        },
        IBMInstance.TYPE_IDLE: {
            "RUN": get_idle_instances
        }
    },
    IBMInstance.TYPE_MONITORING: {
        IBMInstance.__name__: {
            "RUN": get_vsi_usage_data
        }
    },
    IBMInstanceTemplate.__name__: {
        "CREATE": {
            "RUN": create_instance_template,
        },
        "DELETE": {
            "RUN": delete_instance_template
        }
    },
    IBMAddressPrefix.__name__: {
        "CREATE": {
            "RUN": create_address_prefix,
        },
        "DELETE": {
            "RUN": delete_address_prefix
        }
    },
    IBMSubnet.__name__: {
        "CREATE": {
            "RUN": create_subnet,
            "WAIT": create_wait_subnet
        },
        "DELETE": {
            "RUN": delete_subnet,
            "WAIT": delete_wait_subnet
        }
    },
    # For two different resources having no specific ATTACHMENT/DETACHMENT having both types are defined
    f'{IBMSubnet.__name__}-{IBMPublicGateway.__name__}': {
        "ATTACH": {
            "RUN": attach_public_gateway_to_subnet,
            "WAIT": attach_wait_public_gateway_to_subnet
        },
        "DETACH": {
            "RUN": detach_public_gateway_from_subnet
        }
    },
    f'{IBMSubnet.__name__}-{IBMNetworkAcl.__name__}': {
        "ATTACH": {
            "RUN": attach_network_acl_to_subnet
        }
    },
    f'{IBMSubnet.__name__}-{IBMRoutingTable.__name__}': {
        "ATTACH": {
            "RUN": attach_routing_table_to_subnet,
            "WAIT": attach_wait_routing_table_to_subnet
        }
    },
    f'{IBMFloatingIP.__name__}-{IBMNetworkInterface.__name__}': {
        "ATTACH": {
            "RUN": attach_floating_ip_with_network_interface
        },
        "DETACH": {
            "RUN": detach_floating_ip_from_network_interface
        }
    },
    IBMPublicGateway.__name__: {
        "CREATE": {
            "RUN": create_public_gateway,
            "WAIT": create_wait_public_gateway
        },
        "DELETE": {
            "RUN": delete_public_gateway,
            "WAIT": delete_wait_public_gateway
        }
    },
    IBMPlacementGroup.__name__: {
        "CREATE": {
            "RUN": create_placement_group,
            "WAIT": create_wait_placement_group
        },
        "DELETE": {
            "RUN": delete_placement_group,
            "WAIT": delete_wait_placement_group
        }
    },
    IBMNetworkInterface.__name__: {
        "CREATE": {
            "RUN": create_ibm_network_interface,
            "WAIT": create_wait_ibm_network_interface
        },
        "DELETE": {
            "RUN": delete_network_interface,
            "WAIT": delete_wait_network_interface
        },
    },
    IBMSshKey.__name__: {
        "CREATE": {
            "RUN": create_ssh_key,
        },
        "DELETE": {
            "RUN": delete_ssh_key,
        }
    },
    IBMImage.__name__: {
        "CREATE": {
            "RUN": create_ibm_image,
            "WAIT": create_wait_ibm_image
        },
        "DELETE": {
            "RUN": delete_image,
            "WAIT": delete_wait_image
        },
        WorkflowTask.TYPE_CONVERT: {
            "RUN": create_image_conversion,
            "WAIT": create_wait_image_conversion
        },
        WorkflowTask.TYPE_DISCOVERY: {
            "RUN": store_ibm_custom_image,
            "WAIT": store_wait_ibm_custom_image
        },
    },
    IBMFloatingIP.__name__: {
        "CREATE": {
            "RUN": create_floating_ip,
            "WAIT": create_wait_floating_ip
        },
        "DELETE": {
            "RUN": delete_floating_ip,
            "WAIT": delete_wait_floating_ip
        }
    },
    IBMSecurityGroup.__name__: {
        "CREATE": {
            "RUN": create_security_group,
        },
        "ATTACH": {
            "RUN": attach_target_to_security_group
        },
        "DETACH": {
            "RUN": detach_target_to_security_group
        },
        "DELETE": {
            "RUN": delete_security_group
        }
    },
    IBMSecurityGroupRule.__name__: {
        "CREATE": {
            "RUN": create_security_group_rule
        },
        "DELETE": {
            "RUN": delete_security_group_rule
        },
    },
    IBMNetworkAcl.__name__: {
        "CREATE": {
            "RUN": create_network_acl,
        },
        "DELETE": {
            "RUN": delete_network_acl,
        }
    },
    IBMNetworkAclRule.__name__: {
        "CREATE": {
            "RUN": create_network_acl_rule,
        },
        "DELETE": {
            "RUN": delete_network_acl_rule,
        }
    },
    IBMLoadBalancerProfile.__name__: {
        "SYNC": {
            "RUN": sync_load_balancer_profiles
        }
    },
    IBMLoadBalancer.__name__: {
        "CREATE": {
            "RUN": create_load_balancer,
            "WAIT": create_wait_load_balancer
        },
        "DELETE": {
            "RUN": delete_load_balancer,
            "WAIT": delete_wait_load_balancer
        }
    },
    IBMListener.__name__: {
        "CREATE": {
            "RUN": create_listener,
            "WAIT": create_wait_listener
        },
        "DELETE": {
            "RUN": delete_listener,
            "WAIT": delete_wait_listener
        }
    },
    IBMListenerPolicy.__name__: {
        "CREATE": {
            "RUN": create_listener_policy,
            "WAIT": create_wait_listener_policy
        },
        "DELETE": {
            "RUN": delete_listener_policy,
            "WAIT": delete_wait_listener_policy
        }
    },
    IBMPool.__name__: {
        "CREATE": {
            "RUN": create_load_balancer_pool,
            "WAIT": create_wait_load_balancer_pool
        },
        "DELETE": {
            "RUN": delete_load_balancer_pool,
            "WAIT": delete_wait_load_balancer_pool
        }
    },
    IBMPoolMember.__name__: {
        "CREATE": {
            "RUN": create_load_balancer_pool_member,
            "WAIT": create_wait_load_balancer_pool_member
        },
        "DELETE": {
            "RUN": delete_load_balancer_pool_member,
            "WAIT": delete_wait_load_balancer_pool_member
        }
    },
    IBMListenerPolicyRule.__name__: {
        "CREATE": {
            "RUN": create_listener_policy_rule,
            "WAIT": create_wait_listener_policy_rule
        },
        "DELETE": {
            "RUN": delete_listener_policy_rule,
            "WAIT": delete_wait_listener_policy_rule
        }
    },
    IBMVpnGateway.__name__: {
        "CREATE": {
            "RUN": create_vpn_gateway,
            "WAIT": create_wait_vpn_gateway
        },
        "DELETE": {
            "RUN": delete_vpn_gateway,
            "WAIT": delete_wait_vpn_gateway
        }
    },
    IBMVpnConnection.__name__: {
        "CREATE": {
            "RUN": create_vpn_connection
        },
        "DELETE": {
            "RUN": delete_vpn_connection,
            "WAIT": delete_wait_vpn_connection
        }
    },
    IBMIKEPolicy.__name__: {
        "CREATE": {
            "RUN": create_ike_policy,
        },
        "DELETE": {
            "RUN": delete_ike_policy
        }
    },
    IBMIPSecPolicy.__name__: {
        "CREATE": {
            "RUN": create_ipsec_policy,
        },
        "DELETE": {
            "RUN": delete_ipsec_policy
        }
    },
    IBMSnapshot.__name__: {
        "VALIDATE": {
            "RUN": validate_snapshot
        },
        "CREATE": {
            "RUN": create_snapshot,
            "WAIT": create_wait_snapshot
        },
        "DELETE": {
            "RUN": delete_snapshot,
            "WAIT": delete_wait_snapshot
        }
    },
    "IBMVolumeSnapshot": {
        "DELETE": delete_volume_attached_snapshots
    },
    IBMTransitGateway.__name__: {
        "CREATE": {
            "RUN": create_transit_gateway,
            "WAIT": create_wait_transit_gateway
        },
        "DELETE": {
            "RUN": delete_transit_gateway,
            "WAIT": delete_wait_transit_gateway
        }
    },
    IBMTransitGatewayConnection.__name__: {
        "CREATE": {
            "RUN": create_transit_gateway_connection,
            "WAIT": create_wait_transit_gateway_connection
        },
        "DELETE": {
            "RUN": delete_transit_gateway_connection,
            "WAIT": delete_wait_transit_gateway_connection
        }
    },
    IBMTransitGatewayConnectionPrefixFilter.__name__: {
        "CREATE": {
            "RUN": create_transit_gateway_connection_prefix_filter
        },
        "DELETE": {
            "RUN": delete_transit_gateway_connection_prefix_filter,
        }
    },
    IBMTransitGatewayRouteReport.__name__: {
        "CREATE": {
            "RUN": create_transit_gateway_route_report,
            "WAIT": create_wait_transit_gateway_route_report
        },
        "DELETE": {
            "RUN": delete_transit_gateway_route_report,
        }
    },
    IBMDedicatedHost.__name__: {
        "CREATE": {
            "RUN": create_ibm_dedicated_host,
        },
        "DELETE": {
            "RUN": delete_dedicated_host,
            "DELETE": delete_wait_dedicated_host,
        }
    },
    IBMDedicatedHostGroup.__name__: {
        "CREATE": {
            "RUN": create_ibm_dedicated_host_group,
        },
        "DELETE": {
            "RUN": delete_dedicated_host_group
        }
    },
    "KubeVersions": {
        "SYNC": {
            "RUN": sync_orchestration_versions
        }
    },
    "ZoneFlavors": {
        "SYNC": {
            "RUN": sync_workerpool_zone_flavors
        }
    },
    "RegionalZoneFlavors": {
        "SYNC": {
            "RUN": sync_workerpool_flavors_for_all_zones_in_region
        }
    },
    IBMRoutingTable.__name__: {
        "CREATE": {
            "RUN": create_routing_table,
            "WAIT": create_wait_routing_table
        },
        "DELETE": {
            "RUN": delete_routing_table,
            "WAIT": delete_wait_routing_table
        },
    },
    IBMEndpointGateway.__name__: {
        "CREATE": {
            "RUN": create_endpoint_gateway,
            "WAIT": create_wait_endpoint_gateway
        },
        "DELETE": {
            "RUN": delete_endpoint_gateway,
            "WAIT": delete_wait_endpoint_gateway
        },
        "SYNC": {
            "RUN": sync_endpoint_gateway_targets
        },
    },
    IBMSatelliteCluster.__name__: {
        "RESTORE": {
            "RUN": create_kubernetes_cluster_restore,
            "WAIT": create_wait_kubernetes_cluster_restore
        }
    },
    IBMKubernetesCluster.__name__: {
        "BACKUP": {
            "RUN": create_kubernetes_cluster_backup,
            "WAIT": create_wait_kubernetes_cluster_backup
        },
        "CREATE": {
            "RUN": create_kubernetes_cluster,
            "WAIT": create_wait_kubernetes_cluster
        },
        "RESTORE": {
            "RUN": create_kubernetes_cluster_restore,
            "WAIT": create_wait_kubernetes_cluster_restore
        },
        "DELETE": {
            "RUN": delete_kubernetes_cluster,
            "WAIT": delete_wait_kubernetes_cluster,
        },
        "SYNC_CLASSIC": {
            "RUN": sync_classic_kubernetes_task
        },
        "BACKUP_CONSUMPTION": {
            "RUN": add_backup_consumption_task
        }
    },
    f"{IBMKubernetesCluster.__name__}_workloads": {
        "SYNC": {
            "RUN": sync_cluster_workloads
        }
    },
    IBMSubnetReservedIp.__name__: {
        "CREATE": {
            "RUN": reserve_ip_for_subnet
        },
        "DELETE": {
            "RUN": release_reserved_ip_for_subnet
        }
    },
    IBMTag.__name__: {
        "CREATE": {
            "RUN": create_ibm_tag
        },
        "DELETE": {
            "RUN": delete_ibm_tag
        }
    },
    OnPremCluster.__name__: {
        WorkflowTask.TYPE_DISCOVERY: {
            "RUN": discover_on_prem_cluster,
        },
        WorkflowTask.TYPE_BACKUP: {
            "RUN": create_onprem_agent_cluster_backup,
            "WAIT": create_wait_onprem_agent_cluster_backup
        },
        "BACKUP_CONSUMPTION": {
            "RUN": add_backup_consumption_task
        },
        WorkflowTask.TYPE_RESTORE: {
            "RUN": create_onprem_cluster_restore,
            "WAIT": create_wait_onprem_cluster_restore
        },
    },
}
