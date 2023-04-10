class LoadBalancer:
    ID_KEY = "id"
    IBM_CLOUD_KEY = "ibm_cloud"
    REGION_KEY = "region"
    NAME_KEY = "name"
    RESOURCE_JSON_KEY = "resource_json"
    RESOURCE_GROUP_KEY = "resource_group"
    IS_PUBLIC_KEY = "is_public"
    SECURITY_GROUPS_KEY = "security_groups"
    PROFILE_KEY = "profile"
    SUBNETS_KEY = "subnets"
    LISTENERS_KEY = "listeners"
    POOLS_KEY = "pools"
    FAMILY_KEY = "family"

    def __init__(self, id_, name, region, profile_id, profile_family, is_public, resource_group):
        self.id = id_
        self.name = name
        self.subnets = []
        self.region = region
        self.resource_group = resource_group
        self.profile_id = profile_id
        self.profile_family = profile_family
        self.is_public = is_public
        self.security_groups = []
        self.listeners = []
        self.pools = []

    def to_json(self):
        return {
            self.ID_KEY: self.id,
            self.RESOURCE_JSON_KEY: {
                self.IS_PUBLIC_KEY: self.is_public,
                self.LISTENERS_KEY: [listener.to_reference_json() for listener in self.listeners],
                self.SECURITY_GROUPS_KEY: [security_group.to_reference_json() for security_group in
                                           self.security_groups],
                self.SUBNETS_KEY: [subnet.to_reference_json() for subnet in self.subnets],
                self.PROFILE_KEY: {
                    self.ID_KEY: self.profile_id,
                    self.FAMILY_KEY: self.profile_family
                },
                self.NAME_KEY: self.name,
                self.POOLS_KEY: [pool.to_json() for pool in self.pools],
                self.RESOURCE_GROUP_KEY: self.resource_group.to_reference_json(),
            },
            self.IBM_CLOUD_KEY: self.region.cloud.to_reference_json(),
            self.REGION_KEY: self.region.to_reference_json(),
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
        if self not in region.cloud.load_balancers:
            region.cloud.load_balancers.append(self)
            region.cloud.translated_resources[self.id] = self
