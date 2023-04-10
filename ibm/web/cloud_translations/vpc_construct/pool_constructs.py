class Pool:
    ID_KEY = "id"
    NAME_KEY = "name"
    ALGORITHM_KEY = "algorithm"
    HEALTH_MONITOR_KEY = "health_monitor"
    DELAY_KEY = "delay"
    MAX_RETRIES_KEY = "max_retries"
    TIME_OUT_KEY = "timeout"
    TYPE_KEY = "type"
    PROTOCOL_KEY = "protocol"
    URL_PATH_KEY = "url_path"
    PROXY_PROTOCOL_KEY = "proxy_protocol"

    def __init__(self, id_, name, algorithm, delay, max_retries, timeout, type_, protocol, url_path='/',
                 proxy_protocol=None):
        self.id = id_
        self.name = name
        self.algorithm = algorithm
        self.delay = delay
        self.max_retries = max_retries
        self.timeout = timeout
        self.type = type_
        self.protocol = protocol
        self.url_path = url_path
        self.proxy_protocol = proxy_protocol

    def to_json(self):
        return {
            self.ID_KEY: self.id,
            self.ALGORITHM_KEY: self.algorithm,
            self.HEALTH_MONITOR_KEY: {
                self.DELAY_KEY: self.delay,
                self.MAX_RETRIES_KEY: self.max_retries,
                self.TIME_OUT_KEY: self.timeout,
                self.TYPE_KEY: self.type,
                self.URL_PATH_KEY: self.url_path
            },
            self.NAME_KEY: self.name,
            self.PROTOCOL_KEY: self.protocol,
            self.PROXY_PROTOCOL_KEY: self.proxy_protocol
        }

    def to_reference_json(self):
        return {
            self.ID_KEY: self.id,
            self.NAME_KEY: self.name,
        }

    @property
    def region(self):
        return self.__region

    @region.setter
    def region(self, region):
        from ibm.web.cloud_translations.vpc_construct import Region

        assert isinstance(region, Region)

        self.__region = region
