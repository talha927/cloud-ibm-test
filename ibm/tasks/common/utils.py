import logging

from ibm.models import IBMAddressPrefix, IBMDedicatedHost, IBMPublicGateway, IBMVpcNetwork, IBMPlacementGroup
from ibm.models.softlayer.resources_models import SoftLayerSshKey

LOGGER = logging.getLogger(__name__)


def get_softlayer_schema(vpc_data):
    """
    This method generates an equivalent json schema for softlayer objects
    """
    return {
        "subnets": [subnet.to_json() for subnet in vpc_data.get('subnets', [])],
        "security_groups": [security_group.to_json() for security_group in vpc_data.get("security_groups", [])],
        "firewalls": [firewall.to_firewall_json() for firewall in vpc_data.get('firewalls', [])],
        "vpns": [vpn.to_json() for vpn in vpc_data.get('vpns', [])],
        "instances": [instance.to_json() for instance in vpc_data.get('instances', [])],
        "load_balancers": [load_balancer.to_json() for load_balancer in vpc_data.get("load_balancers", [])],
        "dedicated_hosts": [dedicated_host.to_json() for dedicated_host in vpc_data.get("dedicated_hosts", [])],
    }


def generate_ibm_vpc_schema(data, vyatta_client=None, softlayer_cloud=None):
    """
    This method generates an equivalent VPC schema for IBM, the following assumptions are made when migrating:
    1) {name, region, zone} are defined as 'dummy'
    2) Only one Public Gateways can be attached to a given zone in IBM
    3) One Vyatta is treated as a single VPC in IBM
    :return:
    """
    if not data.get("subnets", []):
        return

    ibm_vpc_network = IBMVpcNetwork(name="wip-template", href=None, crn=None, status=None,
                                    resource_id=None, created_at=None)
    ibm_public_gateway = IBMPublicGateway(name="dummy-zone-pbgw", crn=None, href=None, status=None,
                                          resource_id=None)
    address_prefixes_list = list()
    subnets_list = list()

    for subnet in data['subnets']:
        ibm_subnet = subnet.to_ibm(vyatta=vyatta_client)
        if ibm_subnet.ipv4_cidr_block in [subnet.ipv4_cidr_block for subnet in ibm_vpc_network.subnets.all()]:
            continue

        for address_prefix in address_prefixes_list:
            if subnet.address == address_prefix.cidr:
                ibm_subnet.address_prefix = address_prefix
                break

        if not ibm_subnet.address_prefix:
            ibm_address_prefix = IBMAddressPrefix(
                name="address-prefix-{}".format(subnet.name), cidr=subnet.address, href=None, has_subnets=True)
            ibm_subnet.address_prefix = ibm_address_prefix
            address_prefixes_list.append(ibm_address_prefix)

        if subnet.public_gateway:
            ibm_subnet.ibm_public_gateway = ibm_public_gateway
            if not ibm_vpc_network.public_gateways.all():
                ibm_vpc_network.public_gateways.append(ibm_public_gateway)

        ibm_vpc_network.subnets.append(ibm_subnet)
        ibm_vpc_network.address_prefixes.append(ibm_subnet.address_prefix)

        subnets_list.append(ibm_subnet)

    pg_gen2_id_to_classical_id = {}
    pg_classical_id_to_gen2_id = {}
    ibm_placement_groups_list = []
    for placement_group in data.get("placement_groups", []):
        ibm_placement_group = IBMPlacementGroup(name=placement_group.name)
        pg_gen2_id_to_classical_id[ibm_placement_group.id] = placement_group.id
        pg_classical_id_to_gen2_id[placement_group.id] = ibm_placement_group.id
        ibm_placement_groups_list.append(ibm_placement_group)

    dh_gen2_id_to_classical_id = {}
    dh_classical_id_to_gen2_id = {}
    ibm_dedicated_hosts = list()
    for dedicated_host in data.get("dedicated_hosts", []):
        ibm_dedicated_host = IBMDedicatedHost(name=dedicated_host.name)
        dh_gen2_id_to_classical_id[ibm_dedicated_host.id] = dedicated_host.id
        dh_classical_id_to_gen2_id[dedicated_host.id] = ibm_dedicated_host.id
        ibm_dedicated_hosts.append(ibm_dedicated_host)

    for security_group in data.get("security_groups", []):
        ibm_vpc_network.security_groups.append(security_group.to_ibm())

    ike_policies_to_add, ipsec_policies_to_add = list(), list()
    for vpn in data.get('vpn_gateways', []):
        ibm_vpn = vpn.to_ibm()
        subnet = [ibm_subnet for ibm_subnet in subnets_list if ibm_subnet.name == vpn.subnet]
        for connection in ibm_vpn.vpn_connections.all():
            if connection.ike_policy:
                found = False
                for ike_policy in ike_policies_to_add:
                    if connection.ike_policy.name == ike_policy.name:
                        connection.ike_policy = ike_policy
                        found = True
                        break

                if not found:
                    ike_policies_to_add.append(connection.ike_policy)

            if connection.ipsec_policy:
                found = False
                for ipsec_policy in ipsec_policies_to_add:
                    if connection.ipsec_policy.name == ipsec_policy.name:
                        connection.ipsec_policy = ipsec_policy
                        found = True
                        break

                if not found:
                    ipsec_policies_to_add.append(connection.ipsec_policy)
        if subnet:
            ibm_vpn.subnet = subnet[0]

        ibm_vpc_network.vpn_gateways.append(ibm_vpn)

    ibm_vpc_network.address_prefixes = address_prefixes_list
    ibm_ssh_keys = list()
    ssh_keys_id_obj_dict = {}
    for ssh_key in data.get("ssh_keys", []):
        key = SoftLayerSshKey.from_softlayer_json(ssh_key).to_ibm()
        ssh_keys_id_obj_dict[key.name] = key
        key = key.from_softlayer_to_ibm()
        ibm_ssh_keys.append(key)

    instances_list = []
    network_interfaces_list = []
    instance_id_to_obj_dict = {}
    for instance in data.get('instances', []):
        ibm_instance = instance.to_ibm()
        for ssh_key_ in ibm_instance.ssh_keys.all():
            ssh_key_.id = ssh_keys_id_obj_dict[ssh_key_.name].id
        instance_id_to_obj_dict[ibm_instance.id] = ibm_instance
        if instance.dedicated_host:
            for ibm_dedicated_host in ibm_dedicated_hosts:
                if ibm_dedicated_host.id == dh_classical_id_to_gen2_id[instance.dedicated_host["id"]]:
                    ibm_instance.ibm_dedicated_host = ibm_dedicated_host
                    ibm_dedicated_host.instances.append(ibm_instance)
        elif instance.placement_group:
            for ibm_placement_group in ibm_placement_groups_list:
                if ibm_placement_group.id == pg_classical_id_to_gen2_id.get(instance.placement_group["id"]):
                    ibm_instance.ibm_dedicated_host = ibm_placement_group
                    instance.placement_group["id"] = ibm_placement_group.id
                    instance.placement_group["name"] = ibm_placement_group.name
                    ibm_placement_group.placement_instances.append(ibm_instance)

        for interface in ibm_instance.network_interfaces.all():
            interface.ibm_subnet = \
                [subnet for subnet in ibm_vpc_network.subnets.all() if subnet.name == interface.ibm_subnet.name][0]

            interface_security_groups = interface.security_groups.all()
            interface.security_groups = list()
            for security_group in interface_security_groups:
                interface.security_groups.append(
                    [security_group_ for security_group_ in ibm_vpc_network.security_groups.all() if
                     security_group.name == security_group_.name][0])
            network_interfaces_list.append(interface)
        instances_list.append(ibm_instance.from_softlayer_to_ibm_json(instance, vpc_id=ibm_vpc_network.id,
                                                                      softlayer_cloud=softlayer_cloud))
    load_balancers_list = []
    for lb in data.get('load_balancers', []):
        ibm_load_balancer = lb.to_ibm()
        subnets_to_add = list()
        for subnet in ibm_load_balancer.subnets.all():
            subnets_to_add.append(
                [subnet_ for subnet_ in ibm_vpc_network.subnets.all() if subnet_.name == subnet.name][0])

        for pool in ibm_load_balancer.pools.all():
            for pool_mem in pool.members.all():
                pool_mem._network_interface = \
                    [interf for interf in network_interfaces_list if pool_mem._network_interface.name == interf.name
                     and pool_mem._network_interface.primary_ipv4_address == interf.primary_ipv4_address
                     ][0]

                pool_mem._subnet = \
                    [subnet for subnet in ibm_vpc_network.subnets.all() if subnet.name ==
                     pool_mem._subnet.name][0]

        ibm_load_balancer.subnets = subnets_to_add
        load_balancers_list.append(ibm_load_balancer.from_softlayer_to_ibm_json())

    vpns = ibm_vpc_network.vpn_gateways.all()
    ike_policies = dict()
    ipsec_policies = dict()
    for vpn in vpns:
        for connection in vpn.vpn_connections.all():
            if connection.ipsec_policy.id not in ipsec_policies:
                ipsec_policies[connection.ipsec_policy.id] = connection.ipsec_policy.from_softlayer_to_ibm()

            if connection.ike_policy.id not in ike_policies:
                ike_policies[connection.ike_policy.id] = connection.ike_policy.from_softlayer_to_ibm()

    vpc_json = {
        "vpc_networks": [ibm_vpc_network.from_softlayer_to_ibm()],
        "subnets": [subnet.from_softlayer_to_ibm() for subnet in ibm_vpc_network.subnets.all()],
        "address_prefixes": [address_prefix.from_softlayer_to_ibm() for address_prefix in address_prefixes_list],
        "security_groups": [security_group.from_softlayer_to_ibm() for security_group in
                            ibm_vpc_network.security_groups.all()],
        "public_gateways": [public_gateway.from_softlayer_to_ibm() for public_gateway in
                            ibm_vpc_network.public_gateways.all()],
        "instances": instances_list,
        "load_balancers": load_balancers_list,
        "ssh_keys": ibm_ssh_keys,
        "placement_groups": [placement_group.from_softlayer_to_ibm() for placement_group in ibm_placement_groups_list],
        "dedicated_hosts": [dedicated_host.from_softlayer_to_ibm() for dedicated_host in ibm_dedicated_hosts],
        "vpn_gateways": [vpn.from_softlayer_to_ibm() for vpn in vpns],
        "ike_policies": [ike_policies[policy_id] for policy_id in ike_policies],
        "ipsec_policies": [ipsec_policies[policy_id] for policy_id in ipsec_policies],
        "network_acls": [subnet.network_acl.from_softlayer_to_ibm() for subnet in ibm_vpc_network.subnets.all()
                         if subnet.network_acl],
    }

    return vpc_json
