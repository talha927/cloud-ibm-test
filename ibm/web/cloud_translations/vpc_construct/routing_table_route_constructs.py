class RoutingTableRoute:
    ID_KEY = "id"
    NAME_KEY = "name"
    IBM_CLOUD_KEY = "ibm_cloud"
    ZONE_KEY = "zone"
    DESTINATION_KEY = "destination"
    ACTION_KEY = "action"
    ROUTING_TABLE_KEY = "routing_table"
    RESOURCE_JSON_KEY = "resource_json"
    ACTION_DELEGATE = "delegate"
    ACTION_DELEGATE_VPC = "delegate_vpc"
    ACTION_DELIVER = "deliver"
    ACTION_DROP = "drop"

    def __init__(self, id_, destination, zone, action, routing_table, name):
        self.id = id_
        self.name = name
        self.destination = destination
        self.zone = zone
        self.action = action
        self.routing_table = routing_table

    def to_json(self):
        return {
            self.ID_KEY: self.id,
            self.RESOURCE_JSON_KEY: {
                self.NAME_KEY: self.name,
                self.DESTINATION_KEY: self.destination,
                self.ZONE_KEY: self.zone,
                self.ACTION_KEY: self.action
            },
            self.IBM_CLOUD_KEY: self.routing_table.region.cloud.to_reference_json(),
            self.ROUTING_TABLE_KEY: self.routing_table.to_reference_json(),
        }

    def to_resource_json(self):
        return {
            self.NAME_KEY: self.name,
            self.DESTINATION_KEY: self.destination,
            self.ZONE_KEY: self.zone,
            self.ACTION_KEY: self.action
        }

    def to_reference_json(self):

        return {
            self.ID_KEY: self.id,
            self.NAME_KEY: self.name
        }

    @property
    def routing_table(self):
        return self.__routing_table

    @routing_table.setter
    def routing_table(self, routing_table):
        from ibm.web.cloud_translations.vpc_construct.routing_table_constructs import RoutingTable

        assert isinstance(routing_table, RoutingTable)

        self.__routing_table = routing_table
        if self not in routing_table.routes:
            routing_table.routes.append(self)
