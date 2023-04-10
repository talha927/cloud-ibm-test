class NetworkInterface:
    ID_KEY = "id"
    NAME_KEY = "name"
    PRIMARY_IPV4_ADDRESS_KEY = "primary_ipv4_address"
    SUBNET_KEY = "subnet"
    SECURITY_GROUPS_KEY = "security_groups"
    INSTANCE_KEY = "instance"
    IBM_CLOUD_KEY = "ibm_cloud"
    REGION_KEY = "region"
    RESOURCE_GROUP_KEY = "resource_group"
    RESOURCE_JSON_KEY = "resource_json"

    def __init__(self, id_, name, region, subnet, security_groups, instance, primary_ipv4_address=None):
        self.id = id_
        self.name = name
        self.region = region
        self.primary_ipv4_address = primary_ipv4_address
        self.subnet = subnet
        self.security_groups = security_groups
        self.instance = instance

    def to_json(self):
        return {
            self.ID_KEY: self.id,
            self.RESOURCE_JSON_KEY: self.to_resource_json(),
            self.IBM_CLOUD_KEY: self.region.cloud.to_reference_json(),
            self.REGION_KEY: self.region.to_reference_json(),
            self.INSTANCE_KEY: self.instance.to_reference_json(),
        }

    def to_resource_json(self):
        return {
            self.ID_KEY: self.id,
            self.NAME_KEY: self.name,
            self.PRIMARY_IPV4_ADDRESS_KEY: self.primary_ipv4_address,
            self.SUBNET_KEY: self.subnet.to_reference_json(),
            self.SECURITY_GROUPS_KEY: [security_group.to_reference_json() for security_group in self.security_groups]
        }

    def to_reference_json(self):
        return {
            self.ID_KEY: self.id,
            self.NAME_KEY: self.name
        }

    @property
    def region(self):
        return self.__region

    @region.setter
    def region(self, region):
        from ibm.web.cloud_translations.vpc_construct import Region

        assert isinstance(region, Region)

        self.__region = region
        region.cloud.translated_resources[self.id] = self
