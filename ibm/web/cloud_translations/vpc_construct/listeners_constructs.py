class Listener:
    ID_KEY = "id"
    NAME_KEY = "name"
    IBM_CLOUD_KEY = "ibm_cloud"
    REGION_KEY = "region"
    LOAD_BALANCER_KEY = "load_balancer"
    RESOURCE_JSON_KEY = "resource_json"
    PORT_KEY = "port"
    PROTOCOL_KEY = "protocol"
    DEFAULT_POOL_KEY = "default_pool"

    def __init__(self, id_, region, port, protocol, load_balancer, pool_id=None, pool_name=None):
        self.id = id_
        self.region = region
        self.port = port
        self.protocol = protocol
        self.load_balancer = load_balancer
        self.pool_id = pool_id
        self.pool_name = pool_name

    def to_json(self):
        return {
            self.IBM_CLOUD_KEY: self.region.cloud.to_reference_json(),
            self.REGION_KEY: self.region.to_reference_json(),
            self.LOAD_BALANCER_KEY: {
                self.ID_KEY: self.load_balancer
            },
            self.RESOURCE_JSON_KEY: {
                self.DEFAULT_POOL_KEY: {
                    self.ID_KEY: self.pool_id,
                    self.NAME_KEY: self.pool_name
                },
                self.PORT_KEY: self.port,
                self.PROTOCOL_KEY: self.protocol,
            }
        }

    def to_reference_json(self):
        return {
            self.ID_KEY: self.id,
            self.DEFAULT_POOL_KEY: {
                self.ID_KEY: self.pool_id,
                self.NAME_KEY: self.pool_name
            },
            self.PORT_KEY: self.port,
            self.PROTOCOL_KEY: self.protocol
        }

    @property
    def region(self):
        return self.__region

    @region.setter
    def region(self, region):
        from ibm.web.cloud_translations.vpc_construct import Region

        assert isinstance(region, Region)
        self.__region = region
