class VPCNetwork:
    ID_KEY = "id"
    NAME_KEY = "name"
    IBM_CLOUD_KEY = "ibm_cloud"
    REGION_KEY = "region"
    TAG_KEY = "tags"
    RESOURCE_GROUP_KEY = "resource_group"
    RESOURCE_JSON_KEY = "resource_json"

    def __init__(self, id_, name, region, resource_group, tags=None):
        self.id = id_
        self.name = name
        self.region = region
        self.resource_group = resource_group
        self.tags = []

    def to_json(self):
        return {
            self.ID_KEY: self.id,
            self.RESOURCE_JSON_KEY: {
                self.NAME_KEY: self.name,
                self.RESOURCE_GROUP_KEY: self.resource_group.to_reference_json()
            },
            self.IBM_CLOUD_KEY: self.region.cloud.to_reference_json(),
            self.REGION_KEY: self.region.to_reference_json(),
            self.TAG_KEY: [tag.to_json() for tag in self.tags]
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
        if self not in region.cloud.vpc_networks:
            region.cloud.vpc_networks.append(self)
            region.cloud.translated_resources[self.id] = self

    @property
    def resource_group(self):
        return self.__resource_group

    @resource_group.setter
    def resource_group(self, resource_group):
        from ibm.web.cloud_translations.vpc_construct import ResourceGroup

        assert isinstance(resource_group, ResourceGroup)

        self.__resource_group = resource_group
