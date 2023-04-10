class Region:
    ID_KEY = "id"
    NAME_KEY = "name"

    def __init__(self, id_, name, cloud, zones):
        self.id = id_
        self.name = name
        self.cloud = cloud
        self.zones = zones

    def to_json(self):
        return {
            self.ID_KEY: self.id,
            self.NAME_KEY: self.name
        }

    def to_reference_json(self):
        return {
            self.ID_KEY: self.id,
            self.NAME_KEY: self.name
        }

    @property
    def cloud(self):
        return self.__cloud

    @cloud.setter
    def cloud(self, cloud):
        from ibm.web.cloud_translations.vpc_construct import Cloud

        assert isinstance(cloud, Cloud)

        self.__cloud = cloud

        if self not in cloud.regions:
            cloud.regions.append(self)
