class AddressPrefix:
    ID_KEY = "id"
    NAME_KEY = "name"
    IBM_CLOUD_KEY = "ibm_cloud"
    REGION_KEY = "region"
    ZONE_KEY = "zone"
    CIDR_KEY = "cidr"
    IS_DEFAULT = "is_default"
    VPC_KEY = "vpc"
    RESOURCE_JSON_KEY = "resource_json"

    def __init__(self, id_, is_default, zone, cidr, region, vpc, name=None):
        self.id = id_
        self.name = name or f"address-prefix-{id_}"
        self.is_default = is_default
        self.zone = zone
        self.cidr = cidr
        self.region = region
        self.vpc = vpc

    def to_json(self):
        return {
            self.ID_KEY: self.id,
            self.RESOURCE_JSON_KEY: {
                self.NAME_KEY: self.name,
                self.IS_DEFAULT: self.is_default,
                self.CIDR_KEY: self.cidr,
                self.ZONE_KEY: self.zone,
            },
            self.IBM_CLOUD_KEY: self.region.cloud.to_reference_json(),
            self.REGION_KEY: self.region.to_reference_json(),
            self.VPC_KEY: self.vpc.to_reference_json(),
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
        if self not in region.cloud.address_prefixes:
            region.cloud.address_prefixes.append(self)
            region.cloud.translated_resources[self.id] = self
