class Volume:
    ID_KEY = "id"
    NAME_KEY = "name"
    PROFILE_KEY = "profile"
    IOPS_KEY = "iops"
    CAPACITY_KEY = "capacity"
    IBM_CLOUD_KEY = "ibm_cloud"
    REGION_KEY = "region"
    ZONE_KEY = "zone"
    RESOURCE_GROUP_KEY = "resource_group"
    RESOURCE_JSON_KEY = "resource_json"

    def __init__(self, id_, name, region, zone, profile, iops, capacity, resource_group):
        self.id = id_
        self.name = name
        self.region = region
        self.zone = zone
        self.profile = profile
        self.iops = iops
        self.capacity = capacity
        self.resource_group = resource_group

    def to_json(self):
        return {
            self.ID_KEY: self.id,
            self.RESOURCE_JSON_KEY: self.to_resource_json(),
            self.IBM_CLOUD_KEY: self.region.cloud.to_reference_json(),
            self.REGION_KEY: self.region.to_reference_json(),
        }

    def to_resource_json(self):
        return {
            self.NAME_KEY: self.name,
            self.PROFILE_KEY: self.profile,
            self.ZONE_KEY: self.zone,
            self.IOPS_KEY: self.iops,
            self.CAPACITY_KEY: self.capacity,
            self.RESOURCE_GROUP_KEY: self.resource_group.to_reference_json()
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
