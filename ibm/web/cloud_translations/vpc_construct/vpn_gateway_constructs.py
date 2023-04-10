class VpnGateway:
    ID_KEY = "id"
    TYPE = "type"
    STATE = "state"
    IBM_CLOUD_KEY = "ibm_cloud"
    RESOURCE_ID = "resource_id"
    REGION_KEY = "region"
    NAME = "name"
    SUBNET_KEY = "subnet"
    MODE_KEY = "mode"
    RESOURCE_GROUP_KEY = "resource_group"
    RESOURCE_JSON_KEY = "resource_json"
    CONNECTIONS_KEY = "connections"
    ZONE_KEY = "zone"

    def __init__(self, id_, name, region, resource_id, resource_group, mode="route", subnet=None):
        self.id = id_
        self.name = name
        self.resource_id = resource_id
        self.mode = mode
        self.region = region
        self.subnet = subnet
        self.zone = subnet.zone if subnet else {}
        self.resource_group = resource_group
        self.connections = []

    def to_json(self):
        return {
            self.ID_KEY: self.id,
            self.RESOURCE_JSON_KEY: {
                self.SUBNET_KEY: self.subnet.to_reference_json(),
                self.NAME: self.name,
                self.RESOURCE_GROUP_KEY: self.resource_group.to_reference_json(),
                self.CONNECTIONS_KEY: [connection.to_reference_json() for connection in
                                       self.connections],
                self.MODE_KEY: self.mode,
            },
            self.ZONE_KEY: self.zone,
            self.IBM_CLOUD_KEY: self.region.cloud.to_reference_json(),
            self.REGION_KEY: self.region.to_reference_json()
        }

    def to_reference_json(self):
        return {
            self.ID_KEY: self.id,
            self.NAME: self.name
        }

    @property
    def region(self):
        return self.__region

    @region.setter
    def region(self, region):
        from ibm.web.cloud_translations.vpc_construct import Region

        assert isinstance(region, Region)

        self.__region = region
        if self not in region.cloud.vpn_gateways:
            region.cloud.vpn_gateways.append(self)
            region.cloud.translated_resources[self.id] = self
