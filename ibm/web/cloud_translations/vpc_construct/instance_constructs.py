class Instance:
    ID_KEY = "id"
    NAME_KEY = "name"
    NETWORK_INTERFACES_KEY = "network_interfaces"
    PROFILE_KEY = "profile"
    VOLUME_ATTACHMENTS_KEY = "volume_attachments"
    VPC_KEY = "vpc"
    PRIMARY_NETWORK_INTERFACE_KEY = "primary_network_interface"
    BOOT_VOLUME_ATTACHMENT_KEY = "boot_volume_attachment"
    IMAGE_KEY = "image"
    IBM_CLOUD_KEY = "ibm_cloud"
    REGION_KEY = "region"
    ZONE_KEY = "zone"
    RESOURCE_GROUP_KEY = "resource_group"
    RESOURCE_JSON_KEY = "resource_json"

    def __init__(self, id_, name, region, profile, image, resource_group, vpc, zone=None):
        self.id = id_
        self.name = name
        self.region = region
        self.zone = zone
        self.vpc = vpc
        self.profile = profile
        self.network_interfaces = []
        self.volume_attachments = []
        self.primary_network_interface = None
        self.boot_volume_attachment = None
        self.image = image
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
            self.ZONE_KEY: self.zone,
            self.PROFILE_KEY: self.profile,
            self.VPC_KEY: self.vpc.to_reference_json(),
            self.NETWORK_INTERFACES_KEY: [network_interface.to_resource_json() for network_interface in
                                          self.network_interfaces],
            self.VOLUME_ATTACHMENTS_KEY: [volume_attachment.to_resource_json() for volume_attachment in
                                          self.volume_attachments],
            self.PRIMARY_NETWORK_INTERFACE_KEY:
                self.primary_network_interface.to_resource_json() if self.primary_network_interface else {},
            self.BOOT_VOLUME_ATTACHMENT_KEY: self.boot_volume_attachment.to_resource_json(),
            self.IMAGE_KEY: self.image,
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
        if self not in region.cloud.instances:
            region.cloud.instances.append(self)
            region.cloud.translated_resources[self.id] = self
