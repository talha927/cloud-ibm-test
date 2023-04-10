class SecurityGroupRule:
    ID_KEY = "id"
    NAME_KEY = "name"
    IBM_CLOUD_KEY = "ibm_cloud"
    RESOURCE_JSON_KEY = "resource_json"
    SECURITY_GROUP_KEY = "security_group"
    ACTION_KEY = "action"
    DIRECTION_KEY = "direction"
    IP_VERSION_KEY = "ip_version"
    PROTOCOL_KEY = "protocol"
    PORT_MAX_KEY = "port_max"
    PORT_MIN_KEY = "port_max"
    PROTOCOL_TYPE_ALL = "all"
    PROTOCOL_TYPE_ICMP = "icmp"
    PROTOCOL_TYPE_UDP = "udp"
    PROTOCOL_TYPE_TCP = "tcp"
    DIRECTION_INBOUND = "inbound"
    DIRECTION_OUTBOUND = "outbound"

    def __init__(self, id_, security_group, ip_version, direction, protocol, from_port, to_port):
        self.id = id_
        self.security_group = security_group
        self.ip_version = ip_version
        self.direction = direction
        self.protocol = protocol
        self.port_max = to_port
        self.port_min = from_port

    def to_json(self):
        return {
            self.ID_KEY: self.id,
            self.RESOURCE_JSON_KEY: {
                self.DIRECTION_KEY: self.direction,
                self.PROTOCOL_KEY: self.protocol,
                self.IP_VERSION_KEY: self.ip_version,
                self.PORT_MAX_KEY: self.port_max,
                self.PORT_MIN_KEY: self.port_min,
            },
            self.IBM_CLOUD_KEY: self.security_group.region.cloud.to_reference_json(),
            self.SECURITY_GROUP_KEY: self.security_group.to_reference_json(),
        }

    def to_resource_json(self):
        return {
            self.DIRECTION_KEY: self.direction,
            self.PROTOCOL_KEY: self.protocol,
            self.IP_VERSION_KEY: self.ip_version,
            self.PORT_MAX_KEY: self.port_max,
            self.PORT_MIN_KEY: self.port_min,
        }

    def to_reference_json(self):
        return {
            self.ID_KEY: self.id,
            self.NAME_KEY: self.name
        }

    @property
    def security_group(self):
        return self.__security_group

    @security_group.setter
    def security_group(self, security_group):
        from ibm.web.cloud_translations.vpc_construct.security_group_constructs import SecurityGroup

        assert isinstance(security_group, SecurityGroup)

        self.__security_group = security_group
        if self not in security_group.rules:
            security_group.rules.append(self)
