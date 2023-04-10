class Subnet:
    ID_KEY = "id"
    NAME_KEY = "name"
    CIDR_KEY = "ipv4_cidr_block"
    IBM_CLOUD_KEY = "ibm_cloud"
    REGION_KEY = "region"
    ZONE_KEY = "zone"
    VPC_KEY = "vpc"
    PUBLIC_GATEWAY_KEY = "public_gateway"
    RESOURCE_JSON_KEY = "resource_json"

    # Keys just for Frontend
    ADDRESS_PREFIX_KEY = "address_prefix"

    def __init__(self, id_, name, region, ipv4_cidr_block, vpc, zone, public_gateway=None):
        self.id = id_
        self.name = name
        self.region = region
        self.ipv4_cidr_block = ipv4_cidr_block
        self.vpc = vpc
        self.zone = zone
        self.network_acl = None
        self.public_gateway = public_gateway

    def to_json(self):
        return {
            self.ID_KEY: self.id,
            self.RESOURCE_JSON_KEY: {
                self.NAME_KEY: self.name,
                self.VPC_KEY: self.vpc.to_reference_json(),
                self.CIDR_KEY: self.ipv4_cidr_block,
                self.PUBLIC_GATEWAY_KEY: self.public_gateway.to_reference_json() if self.public_gateway else {},
                self.ZONE_KEY: self.zone,
            },
            self.IBM_CLOUD_KEY: self.region.cloud.to_reference_json(),
            self.REGION_KEY: self.region.to_reference_json(),
            # just for frontend
            # TODO: Need to handle multiple address prefixes edge case
            self.ADDRESS_PREFIX_KEY: self.region.cloud.address_prefixes[0].to_json()
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
        if self not in region.cloud.subnets:
            region.cloud.subnets.append(self)
            region.cloud.translated_resources[self.id] = self
