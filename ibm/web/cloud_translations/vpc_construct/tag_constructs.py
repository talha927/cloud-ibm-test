class Tag:
    ID_KEY = "id"
    TAG_NAME_KEY = "tag_name"
    TAG_TYPE_KEY = "tag_type"
    RESOURCE_ID_KEY = "resource_id"
    RESOURCE_TYPE_KEY = "resource_type"
    IBM_CLOUD_KEY = "ibm_cloud"
    REGION_KEY = "region"
    RESOURCE_JSON_KEY = "resource_json"

    def __init__(self, id_, region, tag_type, resource_id, resource_type, tag_name=None):
        self.id = id_
        self.tag_name = tag_name
        self.region = region
        self.tag_type = tag_type
        self.resource_id = resource_id
        self.resource_type = resource_type

    def to_json(self):
        return {
            self.ID_KEY: self.id,
            self.RESOURCE_JSON_KEY: self.to_resource_json(),
            self.IBM_CLOUD_KEY: self.region.cloud.to_reference_json(),
            self.REGION_KEY: self.region.to_reference_json(),
        }

    def to_resource_json(self):
        return {
            self.TAG_NAME_KEY: self.tag_name,
            self.TAG_TYPE_KEY: self.tag_type,
            self.RESOURCE_ID_KEY: self.resource_id,
            self.RESOURCE_TYPE_KEY: self.resource_type
        }

    def to_reference_json(self):
        return {
            self.ID_KEY: self.id,
            self.TAG_NAME_KEY: self.tag_name
        }

    @property
    def region(self):
        return self.__region

    @region.setter
    def region(self, region):
        from ibm.web.cloud_translations.vpc_construct import Region

        assert isinstance(region, Region)

        self.__region = region
