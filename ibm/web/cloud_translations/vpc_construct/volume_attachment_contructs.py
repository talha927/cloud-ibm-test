class VolumeAttachment:
    ID_KEY = "id"
    NAME_KEY = "name"
    VOLUME_KEY = "volume"
    DELETE_VOLUME_ON_INSTANCE_DELETE_KEY = "delete_volume_on_instance_delete"
    IBM_CLOUD_KEY = "ibm_cloud"
    REGION_KEY = "region"
    INSTANCE_KEY = "instance"
    RESOURCE_JSON_KEY = "resource_json"

    def __init__(self, id_, region, delete_volume_on_instance_delete, volume, instance, name=None):
        self.id = id_
        self.name = name
        self.region = region
        self.delete_volume_on_instance_delete = delete_volume_on_instance_delete
        self.volume = volume
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
            self.NAME_KEY: self.name,
            self.VOLUME_KEY: self.volume.to_resource_json(),
            self.DELETE_VOLUME_ON_INSTANCE_DELETE_KEY: self.delete_volume_on_instance_delete
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
