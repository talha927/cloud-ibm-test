class SoftLayerNetworkGateway(object):
    NAME_KEY = "name"
    ID_KEY = "id"
    STATUS_KEY = "status"
    PRIVATE_VLAN_KEY = "private_vlan"
    PUBLIC_VLAN_KEY = "public_vlan"

    def __init__(self, name, id, status, private_vlan=None, public_vlan=None):
        self.name = name
        self.id = id
        self.status = status
        self.private_vlan = private_vlan
        self.public_vlan = public_vlan

    @classmethod
    def from_softlayer_json(cls, json_body):
        obj = cls(
            name=json_body["name"], id=json_body['id'], status=json_body["status"].get("keyName")
        )
        if json_body.get('privateVlan'):
            obj.private_vlan = SoftlayerVlan.from_softlayer_json(json_body['privateVlan'])
        if json_body.get('publicVlan'):
            obj.public_vlan = SoftlayerVlan.from_softlayer_json(json_body['publicVlan'])

        return obj

    def to_json(self):
        return {
            self.ID_KEY: self.id,
            self.NAME_KEY: self.name,
            self.STATUS_KEY: self.status,
            self.PRIVATE_VLAN_KEY: self.private_vlan.to_json() if self.private_vlan else None,
            self.PUBLIC_VLAN_KEY: self.public_vlan.to_json() if self.public_vlan else None
        }


class SoftlayerVlan(object):
    ID_KEY = "id"
    NAME_KEY = "name"

    def __init__(self, name, id):
        self.name = name
        self.id = id

    @classmethod
    def from_softlayer_json(cls, json_body):
        return cls(name=json_body["fullyQualifiedName"], id=json_body['id'])

    def to_json(self):
        return {
            self.ID_KEY: self.id,
            self.NAME_KEY: self.name
        }
