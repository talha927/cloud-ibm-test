class VPNConnection:
    ID_KEY = 'id'
    IBM_CLOUD_KEY = 'ibm_cloud'
    NAME_KEY = 'name'
    PEER_ADDRESS_KEY = 'peer_address'
    PRE_SHARED_KEY = 'psk'
    RESOURCE_JSON_KEY = 'resource_json'
    REGION_KEY = 'region'
    VPN_GATEWAY_KEY = 'vpn_gateway'
    IKE_POLICY_KEY = "ike_policy"
    IPSEC_POLICY_KEY = "ipsec_policy"
    LOCAL_CIDRS_KEYS = "local_cidrs"
    PEER_CIDRS_KEYS = "peer_cidrs"
    ROUTING_PROTOCOL_KEY = "routing_protocol"

    def __init__(self, id_, name, peer_address, key, routing_protocol="none"):
        self.id = id_
        self.name = name
        self.peer_address = peer_address
        self.key = key
        self.routing_protocol = routing_protocol
        self.peer_cidrs = []
        self.local_cidrs = []

    def to_json(self):
        return {
            self.IBM_CLOUD_KEY: self.region.cloud.to_reference_json(),
            self.REGION_KEY: self.region.to_reference_json(),
            self.RESOURCE_JSON_KEY: {
                self.NAME_KEY: self.name,
                self.PEER_ADDRESS_KEY: self.peer_address,
                self.PRE_SHARED_KEY: self.key
            },
            self.VPN_GATEWAY_KEY: {
                self.ID_KEY: self.id,
                self.NAME_KEY: self.name,
            }
        }

    def to_reference_json(self):
        return {
            self.NAME_KEY: self.name,
            self.PEER_ADDRESS_KEY: self.peer_address,
            self.PRE_SHARED_KEY: self.key,
            self.ROUTING_PROTOCOL_KEY: self.routing_protocol,
            self.PEER_CIDRS_KEYS: self.peer_cidrs,
            self.LOCAL_CIDRS_KEYS: self.local_cidrs,
        }

    @property
    def region(self):
        return self.__region

    @region.setter
    def region(self, region):
        from ibm.web.cloud_translations.vpc_construct import Region

        assert isinstance(region, Region)

        self.__region = region
