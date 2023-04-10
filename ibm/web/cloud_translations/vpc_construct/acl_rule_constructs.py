class AclRule:
    ID_KEY = "id"
    NAME_KEY = "name"
    IBM_CLOUD_KEY = "ibm_cloud"
    VPC_KEY = "vpc"
    RESOURCE_JSON_KEY = "resource_json"
    NETWORK_ACL_KEY = "network_acl"
    ACTION_KEY = "action"
    DESTINATION_KEY = "destination"
    DIRECTION_KEY = "direction"
    PROTOCOL_KEY = "protocol"
    SOURCE_KEY = "source"
    DESTINATION_PORT_MAX_KEY = "destination_port_max"
    DESTINATION_PORT_MIN_KEY = "destination_port_min"
    SOURCE_PORT_MAX_KEY = "source_port_max"
    SOURCE_PORT_MIN_KEY = "source_port_min"
    PROTOCOL_TYPE_ALL = "all"
    PROTOCOL_TYPE_ICMP = "icmp"
    PROTOCOL_TYPE_UDP = "udp"
    PROTOCOL_TYPE_TCP = "tcp"
    DIRECTION_INBOUND = "inbound"
    DIRECTION_OUTBOUND = "outbound"

    def __init__(self, id_, network_acl, action, destination, direction, protocol, source, from_port, to_port, name):
        self.id = id_
        self.name = name
        self.network_acl = network_acl
        self.action = action
        self.destination = destination
        self.direction = direction
        self.protocol = protocol
        self.source = source

        if direction == self.DIRECTION_OUTBOUND:
            self.destination_port_max = to_port
            self.destination_port_min = from_port
            self.source_port_max = None
            self.source_port_min = None

        elif direction == self.DIRECTION_INBOUND:
            self.source_port_max = to_port
            self.source_port_min = from_port
            self.destination_port_max = None
            self.destination_port_min = None

    def to_json(self):
        return {
            self.ID_KEY: self.id,
            self.RESOURCE_JSON_KEY: {
                self.NAME_KEY: self.name,
                self.ACTION_KEY: self.action,
                self.DESTINATION_KEY: self.destination,
                self.DIRECTION_KEY: self.direction,
                self.PROTOCOL_KEY: self.protocol,
                self.SOURCE_KEY: self.source,
                self.DESTINATION_PORT_MAX_KEY: self.destination_port_max if self.destination_port_max else None,
                self.DESTINATION_PORT_MIN_KEY: self.destination_port_min if self.destination_port_min else None,
                self.SOURCE_PORT_MAX_KEY: self.source_port_max if self.source_port_max else None,
                self.SOURCE_PORT_MIN_KEY: self.source_port_min if self.source_port_min else None,
            },
            self.IBM_CLOUD_KEY: self.network_acl.region.cloud.to_reference_json(),
            self.NETWORK_ACL_KEY: self.network_acl.to_reference_json(),
        }

    def to_resource_json(self):
        return {
            self.NAME_KEY: self.name,
            self.ACTION_KEY: self.action,
            self.DESTINATION_KEY: self.destination,
            self.DIRECTION_KEY: self.direction,
            self.PROTOCOL_KEY: self.protocol,
            self.SOURCE_KEY: self.source,
            self.DESTINATION_PORT_MAX_KEY: self.destination_port_max if self.destination_port_max else None,
            self.DESTINATION_PORT_MIN_KEY: self.destination_port_min if self.destination_port_min else None,
            self.SOURCE_PORT_MAX_KEY: self.source_port_max if self.source_port_max else None,
            self.SOURCE_PORT_MIN_KEY: self.source_port_min if self.source_port_min else None,
        }

    def to_reference_json(self):
        return {
            self.ID_KEY: self.id,
            self.NAME_KEY: self.name
        }

    @property
    def network_acl(self):
        return self.__network_acl

    @network_acl.setter
    def network_acl(self, network_acl):
        from ibm.web.cloud_translations.vpc_construct.acl_constructs import Acl

        assert isinstance(network_acl, Acl)

        self.__network_acl = network_acl
        if self not in network_acl.rules:
            network_acl.rules.append(self)
