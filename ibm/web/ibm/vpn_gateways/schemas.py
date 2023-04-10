from apiflask import Schema
from apiflask.fields import Boolean, DateTime, List, String
from apiflask.validators import OneOf, Range, Regexp
from marshmallow import INCLUDE, validates_schema, ValidationError
from marshmallow.fields import Integer, Nested
from marshmallow.validate import Length

from ibm.common.req_resp_schemas.consts import DATE_TIME_FORMAT, IBM_HREF_PATTERN, IBM_RESOURCE_NAME_PATTERN, \
    IBM_UUID_PATTERN
from ibm.common.req_resp_schemas.fields import IPv4, IPv4CIDR
from ibm.common.req_resp_schemas.schemas import IBMResourceQuerySchema
from ibm.models import IBMIKEPolicy, IBMIPSecPolicy, IBMResourceGroup, IBMSubnet, IBMVpnConnection, IBMVpnGateway, \
    IBMVPNGatewayMember


class PublicPrivateIpSchema(Schema):
    address = IPv4(required=True, description="The IP address.")


class IBMVpnGatewaysResourceSchema(Schema):
    REF_KEY_TO_RESOURCE_TYPE_MAPPER = {
        "resource_group": IBMResourceGroup,
        "subnet": IBMSubnet
    }
    subnet = Nested("OptionalIDNameSchema", required=True)
    name = String(required=True, allow_none=False, validate=(Regexp(IBM_RESOURCE_NAME_PATTERN), Length(min=1, max=63)),
                  description="The user-defined name for this IPsec policy.")
    resource_group = Nested("OptionalIDNameSchemaWithoutValidation")
    mode = String(required=True, validate=OneOf(IBMVpnGateway.ALL_MODES_LIST),
                  description="The Authentication algorithm.")
    connections = Nested("IBMVpnGatewayConnectionsResourceSchema", many=True, unknown=INCLUDE)


class IBMVpnGatewayInSchema(Schema):
    REF_KEY_TO_RESOURCE_TYPE_MAPPER = {}

    resource_json = Nested("IBMVpnGatewaysResourceSchema", required=True)
    ibm_cloud = Nested("OptionalIDNameSchemaWithoutValidation", required=True)
    region = Nested("OptionalIDNameSchema", required=True)


class UpdateIBMVpnGatewaysResourceSchema(IBMVpnGatewaysResourceSchema):
    pass


class IBMVpnGatewayOutSchema(Schema):
    id = String(validate=Length(equal=32), required=True,
                description="The unique uuid of the VPN Gateway.")
    name = String(required=True, allow_none=False, validate=(Regexp(IBM_RESOURCE_NAME_PATTERN), Length(min=1, max=63)))
    resource_group = Nested("IBMResourceGroupRefOutSchema", required=True)
    mode = String(required=True, validate=OneOf(IBMVpnGateway.ALL_MODES_LIST))
    crn = String(required=True, allow_none=False, description="The CRN for this VPN Gateway",
                 example="crn:v1:bluemix:public:is:us-south-1:a/123456::subnet:7ec86020-1c6e-4889-b3f0-a15f2e50f87e")
    href = String(validate=(Regexp(IBM_HREF_PATTERN)), required=True)
    created_at = DateTime(format=DATE_TIME_FORMAT)
    region = Nested("IBMRegionRefOutSchema", required=True)
    associated_resources = Nested("IBMVpnGatewayAssociatedResourcesOutSchema", required=True)
    connections = Nested("IBMVpnGatewayConnectionOutSchema", exclude=("vpn_gateway",), many=True, required=True)
    status = String(required=True, validate=OneOf(IBMVpnGateway.ALL_STATUSES_LIST),
                    description="The Status of the vpn gateways. ")


class IBMVpnGatewayAssociatedResourcesOutSchema(Schema):
    subnet = Nested("IBMSubnetRefOutSchema", required=True)
    vpc = Nested("IBMVpcNetworkRefOutSchema", required=True)


class IBMVpnGatewayRefOutSchema(IBMVpnGatewayOutSchema):
    class Meta:
        fields = ("id", "name", "resource_group", "subnet")


class IBMVpnGatewayValidateJsonResourceSchema(Schema):
    class Meta:
        fields = ("name", "resource_group", "subnet")


class IBMVpnGatewayValidateJsonOutSchema(Schema):
    id = String(
        required=True, allow_none=False, validate=[Length(equal=32), Regexp(IBM_UUID_PATTERN)],
        description="Unique ID of the IBM VPN Gateway"
    )
    resource_json = Nested(IBMVpnGatewayValidateJsonResourceSchema, required=True)


class DeadPeerDetectionSchema(Schema):
    action = String(validate=OneOf(["clear", "hold", "none", "restart"]),
                    description="Dead Peer Detection actions.")
    interval = Integer(validate=Range(min=1, max=86399),
                       description="Dead Peer Detection interval in seconds.")
    timeout = Integer(validate=Range(min=2, max=86399),
                      description="Dead Peer Detection timeout in seconds. Must be at least the interval.")

    @validates_schema
    def validate_action_none(self, data, **kwargs):
        if data.get("action") == "none" and (data.get("interval") or data.get("timeout")):
            raise ValidationError("No 'interval' and 'timeout' should be sent if action is 'none'")


class IBMVpnGatewayConnectionsResourceSchema(Schema):
    REF_KEY_TO_RESOURCE_TYPE_MAPPER = {
        "ike_policy": IBMIKEPolicy,
        "ipsec_policy": IBMIPSecPolicy
    }
    peer_address = String(required=True, allow_none=False, validate=(
        Regexp(r"^(([0-9]|[1-9][0-9]|1[0-9]{2}|2[0-4][0-9]|25[0-5])\.)"
               "{3}([0-9]|[1-9][0-9]|1[0-9]{2}|2[0-4][0-9]|25[0-5])$"),),
                          description="The IP address of the peer VPN gateway.")
    psk = String(required=True, allow_none=False, validate=(
        Regexp(r"^(?=[\-\+\&\!\@\#\$\%\^\*\(\)\,\.\:\_a-zA-Z0-9]{6,128}$)(?:(?!^0[xs]).).*$"), Length(min=1)),
                 description="The preshared key.")
    admin_state_up = Boolean(default=True, description="If set to false, the VPN gateway connection is shut down.")
    dead_peer_detection = Nested("DeadPeerDetectionSchema", description="The Dead Peer Detection settings.")
    ike_policy = Nested(
        "OptionalIDNameSchema",
        description="Either both or one of '['id', 'name']' should be provided."
    )
    ipsec_policy = Nested(
        "OptionalIDNameSchema",
        description="Either both or one of '['id', 'name']' should be provided."
    )
    name = String(required=True, allow_none=False, validate=(Regexp(IBM_RESOURCE_NAME_PATTERN), Length(min=1, max=63)),
                  description="The user-defined name for this VPN gateway connection.")
    routing_protocol = String(validate=OneOf(IBMVpnConnection.ALL_ROUTING_PROTOCOLS_LIST),
                              description="Routing protocols are disabled for this VPN gateway connection.")
    local_cidrs = List(IPv4CIDR(description="The local CIDRs for this resource."))
    peer_cidrs = List(IPv4CIDR(description="The peer CIDRs for this resource."))

    @validates_schema
    def validate_routing_protocol_or_local_cidrs_and_peer_cidrs(self, data, **kwargs):
        if (data.get("routing_protocol") and (data.get("local_cidrs") or data.get("peer_cidrs"))) or not \
                (data.get("routing_protocol") or data.get("local_cidrs") or data.get("peer_cidrs")):
            raise ValidationError("Either provide 'routing_protocol' or 'local_cidrs' and 'peer_cidrs'")
        if data.get("local_cidrs") and not data.get("peer_cidrs"):
            raise ValidationError("provide peer_cidrs with local_cidrs")
        if data.get("peer_cidrs") and not data.get("local_cidrs"):
            raise ValidationError("provide local_cidrs with peer_cidrs")


class IBMVpnGatewayConnectionInSchema(Schema):
    REF_KEY_TO_RESOURCE_TYPE_MAPPER = {
        "vpn_gateway": IBMVpnGateway
    }

    resource_json = Nested("IBMVpnGatewayConnectionsResourceSchema", required=True)
    ibm_cloud = Nested("OptionalIDNameSchemaWithoutValidation", required=True)
    region = Nested("OptionalIDNameSchema", required=True)
    vpn_gateway = Nested("OptionalIDNameSchema", required=True)


class TunnelsSchema(Schema):
    public_ip = Nested(PublicPrivateIpSchema,
                       description="The IP address of the VPN gateway member in which the tunnel resides.")
    status = String(required=True, validate=OneOf(IBMVpnConnection.ALL_STATUSES_LIST),
                    description="The status of the VPN Tunnel.")


class UpdateIBMVpnGatewayConnectionsResourceSchema(IBMVpnGatewayConnectionsResourceSchema):
    pass


class IBMVpnGatewayConnectionOutSchema(Schema):
    id = String(validate=Length(equal=32), required=True,
                description="The unique uuid of the IpSec Policy.")
    peer_address = String(required=True, allow_none=False, validate=(
        Regexp(r"^(([0-9]|[1-9][0-9]|1[0-9]{2}|2[0-4][0-9]|25[0-5])\.)"
               "{3}([0-9]|[1-9][0-9]|1[0-9]{2}|2[0-4][0-9]|25[0-5])$"),),
                          description="The IP address of the peer VPN gateway.")
    psk = String(required=True, allow_none=False, validate=(
        Regexp(r"^(?=[\-\+\&\!\@\#\$\%\^\*\(\)\,\.\:\_a-zA-Z0-9]{6,128}$)(?:(?!^0[xs]).).*$"), Length(min=1)),
                 description="The preshared key.")
    admin_state_up = Boolean(default=True, description="If set to false, the VPN gateway connection is shut down.")
    dead_peer_detection = Nested(DeadPeerDetectionSchema, description="The Dead Peer Detection settings.")
    ike_policy = Nested("IBMIKEPolicyRefOutSchema", required=True)
    ipsec_policy = Nested("IBMIPSecPolicyRefOutSchema", required=True)
    name = String(required=True, allow_none=False, validate=(Regexp(IBM_RESOURCE_NAME_PATTERN), Length(min=1, max=63)),
                  description="The user-defined name for this VPN gateway connection.")
    routing_protocol = String(validate=OneOf(IBMVpnConnection.ALL_ROUTING_PROTOCOLS_LIST),
                              description="Routing protocols are disabled for this VPN gateway connection.")
    local_cidrs = List(IPv4CIDR(description="The local CIDRs for this resource."))
    peer_cidrs = List(IPv4CIDR(description="The peer CIDRs for this resource."))
    created_at = DateTime(format=DATE_TIME_FORMAT)
    authentication_mode = String(required=True, validate=OneOf(IBMVpnConnection.ALL_AUTHENTICATION_MODES_LIST),
                                 description="Routing protocols are disabled for this VPN gateway connection.")
    href = String(validate=(Regexp(IBM_HREF_PATTERN)), required=True)
    mode = String(required=True, validate=OneOf(IBMVpnConnection.ALL_MODES_LIST),
                  description="Routing protocols are disabled for this VPN gateway connection.")
    resource_type = String(required=True, validate=OneOf(IBMVpnConnection.ALL_RESOURCE_TYPES_LIST),
                           description="Routing protocols are disabled for this VPN gateway connection.")
    tunnels = Nested(TunnelsSchema(many=True),
                     description="The VPN tunnel configuration for this VPN gateway connection (in static route mode.")
    status = String(required=True, validate=OneOf(IBMVpnConnection.ALL_STATUSES_LIST),
                    description="The status of a VPN gateway connection.")
    vpn_gateway = Nested("IBMVpnGatewayRefOutSchema", required=True)


class IBMVpnGatewayConnectionRefOutSchema(IBMVpnGatewayConnectionOutSchema):
    class Meta:
        fields = ("id", "name")


class IBMVpnGatewayMembersResourceSchema(Schema):
    public_ip = Nested(PublicPrivateIpSchema, required=True,
                       description="The public IP address assigned to the VPN gateway member.")
    role = String(required=True, validate=OneOf(IBMVPNGatewayMember.ALL_ROLES_LIST),
                  description="The high availability role assigned to the VPN gateway member.")
    ibm_status = String(required=True, validate=OneOf(IBMVPNGatewayMember.ALL_IBM_STATUSES_LIST),
                        description="The status of the VPN gateway member.")
    private_ip = Nested(PublicPrivateIpSchema, required=True,
                        description="The private IP address assigned to the VPN gateway member. This property will be"
                                    " present only when the VPN gateway status is available..")


class IBMVpnGatewayMemberOutSchema(Schema):
    id = String(validate=Length(equal=32), required=True,
                description="The unique uuid of the Vpn Gateway member.")
    public_ip = Nested(PublicPrivateIpSchema, required=True,
                       description="The public IP address assigned to the VPN gateway member.")
    role = String(required=True, validate=OneOf(IBMVPNGatewayMember.ALL_ROLES_LIST),
                  description="The high availability role assigned to the VPN gateway member.")
    ibm_status = String(required=True, validate=OneOf(IBMVPNGatewayMember.ALL_IBM_STATUSES_LIST),
                        description="The status of the VPN gateway member.")
    private_ip = Nested(PublicPrivateIpSchema, required=True,
                        description="The private IP address assigned to the VPN gateway member. This property will be"
                                    " present only when the VPN gateway status is available..")


class IBMVpnQuerySchema(IBMResourceQuerySchema):
    vpn_id = String(required=True, allow_none=False, validate=(Regexp(IBM_UUID_PATTERN), Length(equal=32)))
