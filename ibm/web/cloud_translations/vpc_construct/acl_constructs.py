class Acl:
    ID_KEY = "id"
    NAME_KEY = "name"
    IBM_CLOUD_KEY = "ibm_cloud"
    REGION_KEY = "region"
    VPC_KEY = "vpc"
    RULES_KEY = "rules"
    RESOURCE_JSON_KEY = "resource_json"

    def __init__(self, id_, name, region, vpc):
        self.id = id_
        self.name = name
        self.region = region
        self.vpc = vpc
        self.rules = []

    def to_json(self):
        return {
            self.ID_KEY: self.id,
            self.RESOURCE_JSON_KEY: {
                self.NAME_KEY: self.name,
                self.VPC_KEY: self.vpc.to_reference_json(),
                self.RULES_KEY: [rule.to_resource_json() for rule in self.rules]
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
        if self not in region.cloud.acls:
            region.cloud.acls.append(self)
            region.cloud.translated_resources[self.id] = self
