from apiflask import Schema
from apiflask.fields import Boolean, DateTime, Nested, String
from apiflask.validators import Length, OneOf, Regexp
from marshmallow import INCLUDE, validates_schema, ValidationError

from ibm.common.req_resp_schemas.consts import DATE_TIME_FORMAT, IBM_HREF_PATTERN, IBM_RESOURCE_NAME_PATTERN, \
    IBM_UUID_PATTERN
from ibm.common.req_resp_schemas.fields import IPv4, IPv4CIDR
from ibm.common.req_resp_schemas.schemas import IBMResourceQuerySchema
from ibm.models import IBMRoutingTable, IBMRoutingTableRoute, IBMVpcNetwork, IBMVpnConnection, IBMZone


class IBMRoutingTableResourceSchema(Schema):
    REF_KEY_TO_RESOURCE_TYPE_MAPPER = {
    }

    name = \
        String(
            required=True, allow_none=False, validate=(Regexp(IBM_RESOURCE_NAME_PATTERN), Length(min=1, max=63)),
            description="The name for the Routing Table"
        )
    route_direct_link_ingress = \
        Boolean(
            missing=False,
            description="If set to true, this routing table will be used to route traffic that originates from Direct "
                        "Link"
        )
    route_transit_gateway_ingress = \
        Boolean(
            missing=False,
            description="If set to true, this routing table will be used to route traffic that originates from Transit "
                        "Gateway"
        )
    route_vpc_zone_ingress = \
        Boolean(
            missing=False,
            description="If set to true, this routing table will be used to route traffic that originates from "
                        "subnets in other zones in this VPC"
        )
    routes = \
        Nested(
            "IBMRoutingTableRouteResourceSchema", many=True, unknown=INCLUDE,
            description="Routes to create with the Routing Table"
        )


class IBMRoutingTableInSchema(Schema):
    REF_KEY_TO_RESOURCE_TYPE_MAPPER = {
        "vpc": IBMVpcNetwork
    }

    resource_json = Nested("IBMRoutingTableResourceSchema", required=True)
    ibm_cloud = Nested("OptionalIDNameSchemaWithoutValidation", required=True)
    region = Nested("OptionalIDNameSchema", required=True)
    vpc = Nested("OptionalIDNameSchema", required=True)


class IBMRoutingTableOutSchema(Schema):
    id = \
        String(
            validate=(Regexp(IBM_UUID_PATTERN), Length(equal=32)), required=True,
            description="UUID of the IBM Routing Table"
        )
    resource_id = String(required=True, allow_none=False, description="UUID on IBM Cloud")
    name = \
        String(
            required=True, allow_none=False, validate=(Regexp(IBM_RESOURCE_NAME_PATTERN), Length(min=1, max=63)),
            description="The name of the IBM Routing Table"
        )
    href = String(validate=(Regexp(IBM_HREF_PATTERN)), required=True)
    created_at = DateTime(format=DATE_TIME_FORMAT, required=True)
    is_default = Boolean(required=True, description="Default Routing Table for this VPC or not")
    lifecycle_state = String(required=True, validate=OneOf(IBMRoutingTable.ALL_LIFECYCLE_STATES_LIST),
                             data_key="status")
    resource_type = String(required=True, validate=OneOf("routing_table"))
    route_direct_link_ingress = \
        Boolean(
            required=True,
            description="If set to true, this routing table will be used to route traffic that originates from Direct "
                        "Link"
        )
    route_transit_gateway_ingress = \
        Boolean(
            required=True,
            description="If set to true, this routing table will be used to route traffic that originates from Transit "
                        "Gateway"
        )
    route_vpc_zone_ingress = \
        Boolean(
            required=True,
            description="If set to true, this routing table will be used to route traffic that originates from "
                        "subnets in other zones in this VPC"
        )
    routes = \
        Nested(
            "IBMRoutingTableRouteRefOutSchema", many=True, required=True,
            description="Routes associated with the Routing Table"
        )
    ibm_cloud = Nested("IBMCloudRefOutSchema", required=True)
    region = Nested("IBMRegionRefOutSchema", required=True)
    associated_resources = Nested("IBMRoutingTableAssociatedResourcesOutSchema", required=True)


class IBMRoutingTableAssociatedResourcesOutSchema(Schema):
    vpc = Nested("IBMVpcNetworkRefOutSchema", required=True)
    subnets = Nested("IBMSubnetRefOutSchema", many=True, required=True)


class IBMRoutingTableRefOutSchema(IBMRoutingTableOutSchema):
    class Meta:
        fields = ("id", "name")


class IBMRoutingTableRouteResourceSchema(Schema):
    REF_KEY_TO_RESOURCE_TYPE_MAPPER = {
        "zone": IBMZone,
        "next_hop_vpn_gateway_connection": IBMVpnConnection
    }

    destination = \
        IPv4CIDR(
            required=True,
            description="The destination of the route. At most two routes per zone in a table can have the same "
                        "destination, and only if both routes have an action of deliver and the next_hop is an IP "
                        "address."
        )
    zone = Nested("OptionalIDNameSchema", required=True)
    action = \
        String(
            required=True,
            validate=OneOf(IBMRoutingTableRoute.ALL_ACTIONS_LIST),
            default=IBMRoutingTableRoute.ACTION_DELIVER,
            description="The action to perform with a packet matching the route:"
                        "- delegate: delegate to the system's built-in routes"
                        "- delegate_vpc: delegate to the system's built-in routes, ignoring Internet-bound routes"
                        "- deliver: deliver the packet to the specified next_hop"
                        "- drop: drop the packet"
        )
    name = \
        String(
            required=True, allow_none=False, validate=(Regexp(IBM_RESOURCE_NAME_PATTERN), Length(min=1, max=63)),
            description="Name of the IBM Routing Table Route"
        )
    next_hop_address_ip = \
        IPv4(
            description="If action is deliver, the next hop that packets will be delivered to. For other action values,"
                        " it must be omitted or specified as `0.0.0.0`"
        )
    next_hop_vpn_gateway_connection = \
        Nested("OptionalIDNameSchema", description="VPC+ UUID or name for this VPN gateway connection")

    @validates_schema
    def validate_next_hop(self, data, **kwargs):
        if data.get("next_hop_address_ip") and data.get("next_hop_vpn_gateway_connection"):
            raise ValidationError("Either provide 'next_hop_address_ip' or 'next_hop_vpn_gateway_connection'")

        if data["action"] != IBMRoutingTableRoute.ACTION_DELIVER and \
                (data.get("next_hop_address_ip", "0.0.0.0") != "0.0.0.0" or
                 data.get("next_hop_vpn_gateway_connection")):
            raise ValidationError(
                "If action is not deliver, 'next_hop_address_ip' must be omitted or specified as 0.0.0.0 and "
                "'next_hop_vpn_gateway_connection' must not be provided"
            )


class IBMRoutingTableRouteInSchema(Schema):
    REF_KEY_TO_RESOURCE_TYPE_MAPPER = {
        "routing_table": IBMRoutingTable
    }

    resource_json = Nested("IBMRoutingTableRouteResourceSchema", required=True)
    ibm_cloud = Nested("OptionalIDNameSchemaWithoutValidation", only=("id",), required=True)
    routing_table = Nested("OptionalIDNameSchema", required=True)


class IBMRoutingTableRouteListQuerySchema(IBMResourceQuerySchema):
    routing_table_id = \
        String(
            required=True, validate=(Regexp(IBM_UUID_PATTERN), Length(equal=32)),
            description="ID of the IBM Routing Table"
        )


class IBMRoutingTableRouteOutSchema(Schema):
    id = \
        String(
            validate=(Regexp(IBM_UUID_PATTERN), Length(equal=32)), required=True,
            description="UUID of the IBMRoutingTableRoute"
        )
    resource_id = String(required=True, allow_none=False, description="UUID on IBM Cloud")
    name = \
        String(
            required=True, allow_none=False, validate=(Regexp(IBM_RESOURCE_NAME_PATTERN), Length(min=1, max=63)),
            description="The name of the IBM ACL Rule."
        )
    href = String(validate=(Regexp(IBM_HREF_PATTERN)), required=True)
    created_at = DateTime(format=DATE_TIME_FORMAT, required=True)
    action = \
        String(required=True, validate=OneOf(IBMRoutingTableRoute.ALL_ACTIONS_LIST), description="The action of Route")
    lifecycle_state = String(required=True, validate=OneOf(IBMRoutingTable.ALL_LIFECYCLE_STATES_LIST),
                             data_key="status")
    destination = \
        IPv4CIDR(
            required=True,
            description="The destination of the route. At most two routes per zone in a table can have the same "
                        "destination, and only if both routes have an action of deliver and the next_hop is an IP "
                        "address."
        )
    next_hop_address_ip = IPv4(description="If action is deliver, the next hop that packets will be delivered to")
    next_hop_vpn_gateway_connection = Nested("IBMVpnGatewayConnectionRefOutSchema")
    ibm_cloud = Nested("IBMCloudRefOutSchema", required=True)
    region = Nested("IBMRegionRefOutSchema", required=True)
    zone = Nested("IBMZoneRefOutSchema", required=True)


class IBMRoutingTableRouteRefOutSchema(IBMRoutingTableRouteOutSchema):
    class Meta:
        fields = ("id", "name")
