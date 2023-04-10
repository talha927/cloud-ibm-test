import ipaddress

from ibm.common.clients.ibm_clients import SubnetsClient


def get_available_ip_list_from_cidr(cloud_id, region_name, subnet_resource_id, cidr):
    """
    Returns a list of available IP addresses in a subnet, given its CIDR notation and a list of reserved IPs.

    Args:
    cloud_id (str): The ID of the cloud where the subnet exists.
    region_name (str): The name of the region where the subnet exists.
    subnet_resource_id (str): The ID of the subnet for which to retrieve the list of available IPs.
    cidr (str): The CIDR notation of the subnet.

    Returns:
    list: A list of available IP addresses in the subnet, as strings.
    """
    sub_client = SubnetsClient(cloud_id=cloud_id, region=region_name)
    network = ipaddress.ip_network(cidr)
    reserved_ips = [
        str(ip["address"]) for ip in
        sub_client.list_reserved_ips_in_subnet(subnet_id=subnet_resource_id)
    ]
    ip_list = [str(ip) for ip in network.hosts()]
    return [x for x in ip_list if x not in reserved_ips]
