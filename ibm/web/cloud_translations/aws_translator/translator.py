import logging
import uuid

from marshmallow import ValidationError

from ibm.web.cloud_translations.aws_translator.schemas import AWSVpcConstructSchema
from ibm.web.cloud_translations.common import clean_payload
from ibm.web.cloud_translations.common.mappers import PROTOCOL_NUMBER_TO_PROTOCOL_NAME_MAPPER
from ibm.web.cloud_translations.vpc_construct import Acl, AclRule, AddressPrefix, Cloud, FloatingIP, Instance, \
    KubernetesCluster, NetworkInterface, PublicGateway, Region, ResourceGroup, RoutingTable, RoutingTableRoute, \
    SecurityGroup, SecurityGroupRule, Subnet, Tag, Volume, VolumeAttachment, VPCNetwork, WorkerPool, \
    WorkerZone, VpnGateway, LoadBalancer, Pool, Listener, VPNConnection

LOGGER = logging.getLogger(__name__)


class AWSTranslator:
    def __init__(self, ibm_cloud, resource_group, region, source_construct, db_image_name_obj_dict=None,
                 instance_profile=None, volume_profile=None, load_balancer_profiles=None):
        self.source_construct = source_construct
        self.cloud = Cloud(id_=ibm_cloud.id, name=ibm_cloud.name)
        self.region = Region(id_=region.id, name=region.name, cloud=self.cloud,
                             zones=[zone.to_reference_json() for zone in region.zones.all()])
        self.ibm_zones_number_zone_dict = {int(zone["name"][-1]): zone for zone in self.region.zones}
        self.resource_group = ResourceGroup(id_=resource_group.id, name=resource_group.name)
        self.db_image_name_obj_dict = db_image_name_obj_dict or dict()
        self.instance_profile = instance_profile.to_reference_json() if instance_profile else {"name": "bx2-2x8"}
        self.volume_profile = volume_profile or {"name": "custom"}
        self.load_balancer_profiles = load_balancer_profiles or dict()
        self.public_gateway = None

    def to_translated_json(self, metadata=False):
        """
        This method return a translated payload for IBM template provisioning.
        """
        return self.cloud.to_json() if metadata else clean_payload(self.cloud.to_json())

    def validate_translation_json(self):
        """
        This method validates AWS virtual network construct Json and raise error if any.
        """
        try:
            cleaned_json = clean_payload(self.source_construct)
            self.source_construct = AWSVpcConstructSchema().load(cleaned_json)
        except ValidationError as err:
            LOGGER.error(err.messages)
            raise

    def execute_translation(self):
        """
        This method executes the translation for all resource for all vpc contexts.
        """
        for vpc_json in self.source_construct["vpcs"]:
            self.__translate_aws_vpc(vpc_json=vpc_json)

        for internet_gateway_json in self.source_construct.get("internet_gateways", []):
            self.__translate_aws_internet_gateway(internet_gateway_json=internet_gateway_json)

        for subnet_json in self.source_construct.get("subnets", []):
            self.__translate_aws_subnet(subnet_json=subnet_json)

        for acl_json in self.source_construct.get("acls", []):
            self.__translate_aws_acl(acl_json=acl_json)

        for route_table_json in self.source_construct.get("route_tables", []):
            self.__translate_aws_route_table(routing_table_json=route_table_json)

        for security_group_json in self.source_construct.get("security_groups", []):
            self.__translate_aws_security_group(security_group_json=security_group_json)

        for volume_json in self.source_construct.get("volumes", []):
            self.__translate_aws_volume(volume_json=volume_json)

        for instance_json in self.source_construct.get("instances", []):
            self.__translate_aws_instance(instance_json=instance_json)

        for virtual_private_gateway_json in self.source_construct.get("virtual_private_gateways", []):
            self.__translate_aws_vpn(vpn_gateway_json=virtual_private_gateway_json)

        for eks_cluster_json in self.source_construct.get("eks_clusters", []):
            self.__translate_aws_cluster(eks_cluster_json=eks_cluster_json)

        for load_balancer_json in self.source_construct.get("load_balancers", []):
            self.__translate_aws_load_balancer(load_balancer=load_balancer_json)

    def __translate_aws_load_balancer(self, load_balancer):
        """
        This method translates AWS Load Balancer to IBM Load Balancer.
        1.checking the Load Balancer is Public or Private.
        2.checking type of Load Balancer and assigning it according to IBM limitations
        3.passing subnets and security groups(if application type load balancer).
        4.checking target_groups attach to load balancer and then creating payload
        related to IBM Backend End Pool.
        5.checking listener attached to load balancer and assigning it according to IBM Limitations.
        """
        if load_balancer['scheme'] == 'internet-facing':
            self.is_public = True
        else:
            self.is_public = False

        if load_balancer['type'] == 'application':
            self.profile_id = self.load_balancer_profiles['Application']['id']
            self.profile_family = self.load_balancer_profiles['Application']['family']
            self.proxy_protocol = 'disabled'
        else:
            self.profile_id = self.load_balancer_profiles['Network']['id']
            self.profile_family = self.load_balancer_profiles['Network']['family']

        load_balancers = LoadBalancer(
            id_=load_balancer["id"],
            name=load_balancer["name"],
            region=self.region,
            resource_group=self.resource_group,
            is_public=self.is_public,
            profile_id=self.profile_id,
            profile_family=self.profile_family
        )

        for subnet_json in self.source_construct.get("subnets", []):
            subnet = Subnet(
                id_=subnet_json["id"],
                name=subnet_json["resource_id"],
                region=self.region,
                ipv4_cidr_block=subnet_json["ipv4_cidr_block"],
                vpc=self.cloud.translated_resources[subnet_json["vpc_id"]],
                public_gateway=self.public_gateway,
                zone=self.region.zones[0]
            )
            load_balancers.subnets.append(subnet)

        if load_balancer['type'] == 'application':
            for security_group_json in self.source_construct.get("security_groups", []):
                security_group = SecurityGroup(
                    id_=security_group_json["id"],
                    name=security_group_json["resource_id"],
                    region=self.region,
                    vpc=self.cloud.translated_resources[security_group_json["vpc_id"]],
                    resource_group=self.resource_group
                )
                load_balancers.security_groups.append(security_group)

        for pool_json in self.source_construct.get("target_groups", []):
            try:
                if pool_json["load_balancer"]['id'] == load_balancer['id']:
                    self.pool_id = pool_json['id']
                    self.pool_name = pool_json['name']
                    if pool_json['protocol'] == 'HTTP':
                        self.pool_protocol = 'http'
                    elif pool_json['protocol'] == 'HTTPS':
                        self.pool_protocol = 'https'
                    elif pool_json['protocol'] == 'TCP' or pool_json['protocol'] == 'TCP_UDP':
                        self.pool_protocol = 'tcp'
                    else:
                        self.pool_protocol = 'udp'
                    pool = Pool(
                        id_=pool_json["id"],
                        name=pool_json["name"],
                        delay=pool_json['health_check_timeout_seconds'] + 1,
                        max_retries=5,
                        timeout=pool_json['health_check_timeout_seconds'],
                        type_=self.pool_protocol,
                        algorithm='least_connections',
                        protocol=self.pool_protocol,
                        proxy_protocol=self.proxy_protocol,
                    )
                    load_balancers.pools.append(pool)
            except KeyError:
                continue

        for listener_json in self.source_construct.get("listeners", []):
            for listener_id in load_balancer['listeners']:
                if listener_json['id'] == listener_id["id"]:
                    listener = Listener(
                        id_=listener_json['id'],
                        region=self.region,
                        port=listener_json['port'],
                        protocol=self.pool_protocol,
                        load_balancer=load_balancer['id'],
                        pool_id=self.pool_id,
                        pool_name=self.pool_name
                    )
                    load_balancers.listeners.append(listener)

    def __translate_aws_vpn(self, vpn_gateway_json):
        """
        This method translates AWS VPN Gateway to IBM VPN Gateway.
        """
        subnet = self.region.cloud.subnets[0]
        vpn_gateway = VpnGateway(
            id_=vpn_gateway_json["id"],
            name=vpn_gateway_json["resource_id"],
            resource_id=vpn_gateway_json['resource_id'],
            resource_group=self.resource_group,
            region=self.region,
            subnet=subnet,
        )
        for vpn_connection_json in self.source_construct.get("vpn_connections", []):
            if vpn_connection_json['virtual_private_gateway_id'] == vpn_gateway_json['id']:
                for pre_shared_key in vpn_connection_json['options']['tunnel_options']:
                    connection = VPNConnection(id_=vpn_gateway_json['id'], name='vpn-connection',
                                               key=pre_shared_key['pre_shared_key'],
                                               peer_address=pre_shared_key['outside_ip_address'])
                    vpn_gateway.connections.append(connection)
                    break

    def __translate_aws_vpc(self, vpc_json):
        """
        This method translates aws vpc to IBM VPC network.
        """
        vpc_network = VPCNetwork(
            id_=vpc_json["id"],
            name=vpc_json["resource_id"],
            region=self.region,
            resource_group=self.resource_group,
        )

        for tags_json in vpc_json.get("tags", []):
            tag = Tag(
                id_=tags_json["id"],
                tag_name=tags_json["value"],
                tag_type="user",
                region=self.region,
                resource_id=tags_json["resource_id"],
                resource_type=tags_json["resource_type"]
            )
            vpc_network.tags.append(tag)

        AddressPrefix(
            cidr=vpc_json["cidr_block"],
            id_=str(uuid.uuid4().hex),
            is_default=False,
            vpc=vpc_network,
            region=self.region,
            zone=self.region.zones[0]
        )

        for cidr_block_association_set in vpc_json.get("cidr_block_association_sets", []):
            if vpc_json["cidr_block"] == cidr_block_association_set["cidr_block"]:
                continue
            AddressPrefix(
                cidr=cidr_block_association_set["cidr_block"],
                name=cidr_block_association_set["resource_id"],
                id_=cidr_block_association_set["id"],
                is_default=False,
                vpc=vpc_network,
                region=self.region,
                zone=self.region.zones[0]
            )

    def __translate_aws_subnet(self, subnet_json):
        """
        This method translates aws Subnet to IBM Subnet.
        """
        Subnet(
            id_=subnet_json["id"],
            name=subnet_json["resource_id"],
            region=self.region,
            ipv4_cidr_block=subnet_json["ipv4_cidr_block"],
            vpc=self.cloud.translated_resources[subnet_json["vpc_id"]],
            public_gateway=self.public_gateway,
            zone=self.region.zones[0]
        )

    def __translate_aws_acl(self, acl_json):
        """
        This method translates aws ACL to IBM ACL.
        """
        network_acl = Acl(
            id_=acl_json["id"],
            name=acl_json["resource_id"],
            region=self.region,
            vpc=self.cloud.translated_resources[acl_json["vpc_id"]]
        )
        for association in acl_json.get("associations", []):
            subnet = self.cloud.translated_resources[association["subnet_id"]]
            subnet.network_acl = network_acl

        for i, acl_rule_json in enumerate(acl_json.get("entries", [])):
            protocol = PROTOCOL_NUMBER_TO_PROTOCOL_NAME_MAPPER.get(acl_rule_json["protocol"])
            if not protocol:
                continue

            direction = AclRule.DIRECTION_OUTBOUND if acl_rule_json["is_egress"] else AclRule.DIRECTION_INBOUND

            AclRule(
                id_=acl_rule_json["id"],
                name=f"{acl_json['resource_id']}-{i}",
                action=acl_rule_json["rule_action"],
                direction=direction,
                destination=acl_rule_json["ipv4_cidr_block"] if direction == "outbound" else "0.0.0.0/0",
                source=acl_rule_json["ipv4_cidr_block"] if direction == "inbound" else "0.0.0.0/0",
                protocol=protocol,
                to_port=acl_rule_json.get("port_range", {}).get("to_port"),
                from_port=acl_rule_json.get("port_range", {}).get("from_port"),
                network_acl=network_acl
            )

    def __translate_aws_route_table(self, routing_table_json):
        """
        This method translates AWS ACL to IBM ACL.
        """
        routing_table = RoutingTable(
            id_=routing_table_json["id"],
            name=routing_table_json["resource_id"],
            region=self.region,
            vpc=self.cloud.translated_resources[routing_table_json["vpc_id"]]
        )

        for i, route_json in enumerate(routing_table_json.get("routes", [])):
            if route_json["target_resource_type"] not in ["local"]:
                continue

            if not route_json.get('destination_ipv4_cidr_block'):
                continue

            RoutingTableRoute(
                id_=route_json["id"],
                name=f"{routing_table_json['resource_id']}-{i}",
                routing_table=routing_table,
                destination=route_json["destination_ipv4_cidr_block"],
                action=RoutingTableRoute.ACTION_DELEGATE,
                zone=self.region.zones[0]
            )

    def __translate_aws_internet_gateway(self, internet_gateway_json):
        """
        This method translates AWS Internet Gateway to IBM Public Gateway.
        """
        self.public_gateway = PublicGateway(
            id_=internet_gateway_json["id"],
            name=internet_gateway_json["resource_id"],
            region=self.region,
            vpc=self.cloud.translated_resources[internet_gateway_json["vpc_id"]],
            zone=self.region.zones[0]
        )

    def __translate_aws_security_group(self, security_group_json):
        """
        This method translates AWS Security Group to IBM Security Group.
        """
        for security_group in security_group_json.get("security_groups", []):
            if "eks" in security_group["group_name"] or "k8s" in security_group["group_name"]:
                return

        security_group = SecurityGroup(
            id_=security_group_json["id"],
            name=security_group_json["resource_id"],
            region=self.region,
            vpc=self.cloud.translated_resources[security_group_json["vpc_id"]],
            resource_group=self.resource_group
        )

        for security_group_rule_json in security_group_json.get("ip_permissions", []):
            protocol = PROTOCOL_NUMBER_TO_PROTOCOL_NAME_MAPPER.get(security_group_rule_json["ip_protocol"])
            if not protocol:
                continue

            direction = SecurityGroupRule.DIRECTION_OUTBOUND if security_group_rule_json[
                "is_egress"] else SecurityGroupRule.DIRECTION_INBOUND

            for ip_ranges_json in security_group_rule_json.get("ip_ranges", []):
                if ip_ranges_json["type"] != "ipv4":
                    continue

                SecurityGroupRule(
                    id_=security_group_rule_json["id"],
                    direction=direction,
                    protocol=protocol,
                    ip_version=ip_ranges_json["type"],
                    to_port=security_group_rule_json.get("to_port"),
                    from_port=security_group_rule_json.get("from_port"),
                    security_group=security_group,
                )

    def __translate_aws_volume(self, volume_json):
        if volume_json["iops"] < 100:
            iops = 100
        elif volume_json["iops"] > 1000:
            iops = 1000
        else:
            iops = volume_json["iops"]

        if volume_json["size"] < 10:
            capacity = 10
        elif volume_json["size"] > 16000:
            capacity = 16000
        else:
            capacity = volume_json["size"]

        Volume(
            id_=volume_json["id"],
            name=volume_json["resource_id"],
            region=self.region,
            zone=self.region.zones[0],
            profile=self.volume_profile,
            iops=iops,
            capacity=capacity,
            resource_group=self.resource_group
        )

    def __translate_aws_instance(self, instance_json):
        for tag in instance_json.get("tags", []):
            if "eks" in tag["key"]:
                return

        if not self.db_image_name_obj_dict:
            return

        instance = Instance(
            id_=instance_json["id"],
            name=instance_json["resource_id"],
            region=self.region,
            vpc=self.cloud.translated_resources[instance_json["vpc_id"]],
            profile=self.instance_profile,
            image=list(self.db_image_name_obj_dict.values())[0],
            resource_group=self.resource_group
        )

        for network_interface_json in instance_json["network_interfaces"]:
            network_interface = NetworkInterface(
                id_=network_interface_json["id"],
                name=network_interface_json["resource_id"],
                region=self.region,
                instance=instance,
                primary_ipv4_address=network_interface_json.get("private_ip_address"),
                subnet=self.cloud.translated_resources[network_interface_json["subnet_id"]],
                security_groups=[self.cloud.translated_resources[security_group_id] for security_group_id in
                                 network_interface_json["security_groups"]]
            )
            instance.zone = network_interface.subnet.zone
            if network_interface_json.get("network_interface_association"):
                FloatingIP(
                    name=network_interface_json["resource_id"],
                    region=self.region,
                    network_interface=network_interface,
                    resource_group=self.resource_group
                )

            attachment = network_interface_json.get("attachment")
            if attachment and attachment["device_index"] == 0:
                instance.primary_network_interface = network_interface
                continue

            instance.network_interfaces.append(network_interface)

        for block_device_mapping_json in instance_json["block_device_mappings"]:
            volume = self.cloud.translated_resources[block_device_mapping_json["volume_id"]]
            volume_attachment = VolumeAttachment(
                id_=block_device_mapping_json["id"],
                region=self.region,
                delete_volume_on_instance_delete=block_device_mapping_json.get("delete_on_termination", False),
                volume=volume,
                instance=instance,
            )

            boot = True if block_device_mapping_json.get("device_name") == instance_json.get(
                "root_device_name") else False
            if boot:
                volume.capacity = None
                instance.boot_volume_attachment = volume_attachment
                continue

            volume_attachment.name = block_device_mapping_json.get("device_name")
            instance.volume_attachments.append(volume_attachment)

    def __translate_aws_cluster(self, eks_cluster_json):
        if not eks_cluster_json.get("eks_node_groups"):
            return
        cluster = KubernetesCluster(
            id_=eks_cluster_json["id"],
            name=eks_cluster_json["name"],
            region=self.region,
            master_kube_version="1.26.1",
            resource_group=self.resource_group,
            vpc=self.cloud.translated_resources[eks_cluster_json["cluster_resource_vpc_config"]["vpc_id"]],
            disable_public_service_endpoint=False,
        )

        for eks_node_group_json in eks_cluster_json.get("eks_node_groups", []):
            worker_pool = WorkerPool(
                id_=eks_node_group_json["id"],
                name=eks_node_group_json["node_group_name"],
                disk_encryption=True,
                flavor="cx2.4x8",
                worker_count=eks_node_group_json["node_group_scaling"]["desired_size"],
                cluster=cluster
            )
            used_zones = set()
            for subnet_id in eks_node_group_json["subnet_ids"]:
                subnet = self.cloud.translated_resources[subnet_id]
                if subnet.zone["name"] in used_zones:
                    continue

                WorkerZone(
                    subnet=subnet,
                    worker_pool=worker_pool
                )
                used_zones.add(subnet.zone["name"])
