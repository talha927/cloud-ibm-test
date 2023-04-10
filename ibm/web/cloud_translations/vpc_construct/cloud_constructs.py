import uuid


class Cloud:
    ID_KEY = "id"
    NAME_KEY = "name"
    VPC_NETWORK_KEY = "vpc_networks"
    ADDRESS_PREFIXES_KEY = "address_prefixes"
    SUBNETS_KEY = "subnets"
    ACLS_KEY = "network_acls"
    LOAD_BALANCERS_KEY = "load_balancers"
    PUBLIC_GATEWAYS_KEY = "public_gateways"
    SECURITY_GROUP_KEYS = "security_groups"
    ROUTING_TABLES_KEY = "routing_tables"
    INSTANCES_KEY = "instances"
    FLOATING_IPS_KEY = "floating_ips"
    VPN_GATEWAY_KEYS = "vpn_gateways"
    KUBERNETES_CLUSTERS_KEY = "kubernetes_clusters"

    def __init__(self, id_, name):
        self.id = id_
        self.name = f"{name.title()} translation Workspace ({str(uuid.uuid4().hex)})"
        self.translated_resources = dict()
        self.vpc_networks = []
        self.address_prefixes = []
        self.subnets = []
        self.instances = []
        self.kubernetes_clusters = []
        self.floating_ips = []
        self.acls = []
        self.public_gateways = []
        self.security_groups = []
        self.routing_tables = []
        self.regions = []
        self.load_balancers = []
        self.vpn_gateways = []

    def to_json(self):
        return {
            self.NAME_KEY: self.name,
            self.VPC_NETWORK_KEY: [vpc_network.to_json() for vpc_network in self.vpc_networks],
            self.ADDRESS_PREFIXES_KEY: [address_prefix.to_json() for address_prefix in self.address_prefixes],
            self.SUBNETS_KEY: [subnet.to_json() for subnet in self.subnets],
            self.ACLS_KEY: [acl.to_json() for acl in self.acls],
            self.PUBLIC_GATEWAYS_KEY: [public_gateway.to_json() for public_gateway in self.public_gateways],
            self.SECURITY_GROUP_KEYS: [security_group.to_json() for security_group in self.security_groups],
            self.ROUTING_TABLES_KEY: [routing_table.to_json() for routing_table in self.routing_tables],
            self.INSTANCES_KEY: [instance.to_json() for instance in self.instances],
            self.FLOATING_IPS_KEY: [floating_ip.to_json() for floating_ip in self.floating_ips],
            self.KUBERNETES_CLUSTERS_KEY: [kubernetes_cluster.to_json() for kubernetes_cluster in
                                           self.kubernetes_clusters],
            self.LOAD_BALANCERS_KEY: [load_balancer.to_json()
                                      for load_balancer in self.load_balancers],
            self.VPN_GATEWAY_KEYS: [virtual_private_gateway.to_json()
                                    for virtual_private_gateway in self.vpn_gateways],
        }

    def to_reference_json(self):
        return {
            self.ID_KEY: self.id,
            self.NAME_KEY: self.name
        }

    @property
    def cloud(self):
        return self.__cloud

    @cloud.setter
    def cloud(self, cloud):
        assert isinstance(cloud, Cloud)
        self.__cloud = cloud
