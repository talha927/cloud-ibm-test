import uuid


class FloatingIP:
    ID_KEY = "id"
    NAME_KEY = "name"
    TARGET_KEY = "target"
    IBM_CLOUD_KEY = "ibm_cloud"
    REGION_KEY = "region"
    RESOURCE_GROUP_KEY = "resource_group"
    RESOURCE_JSON_KEY = "resource_json"

    def __init__(self, name, region, network_interface, resource_group):
        self.id = str(uuid.uuid4().hex)
        self.name = name
        self.region = region
        self.target = network_interface
        self.resource_group = resource_group

    def to_json(self):
        return {
            self.ID_KEY: self.id,
            self.RESOURCE_JSON_KEY: {
                self.NAME_KEY: self.name,
                self.TARGET_KEY: self.target.to_reference_json(),
                self.RESOURCE_GROUP_KEY: self.resource_group
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
        if self not in region.cloud.floating_ips:
            region.cloud.floating_ips.append(self)
