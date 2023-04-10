import uuid

from apiflask import Schema
from apiflask.fields import Boolean, DateTime, String
from apiflask.validators import OneOf, Regexp
from marshmallow import validates_schema, ValidationError
from marshmallow.fields import Integer, Nested, List
from marshmallow.validate import Length, Range

from ibm.common.req_resp_schemas.consts import IBM_RESOURCE_NAME_PATTERN, IBM_UUID_PATTERN
from ibm.common.req_resp_schemas.fields import IPv4, IPv4CIDR
from ibm.common.req_resp_schemas.schemas import IBMResourceQuerySchema, IBMResourceRefSchema, \
    IBMZonalResourceListQuerySchema
from ibm.models import IBMNetworkAcl, IBMPublicGateway, IBMResourceGroup, IBMRoutingTable, IBMSubnet, IBMVpcNetwork, \
    IBMZone


class IBMVpcListQuerySchema(IBMZonalResourceListQuerySchema):
    vpc_id = String(allow_none=False, validate=(Regexp(IBM_UUID_PATTERN), Length(equal=32)))


class IBMReservedIpListQuerySchema(IBMResourceQuerySchema):
    subnet_id = String(validate=(Regexp(IBM_UUID_PATTERN)), allow_none=False)
    endpoint_gateway_id = String(validate=(Regexp(IBM_UUID_PATTERN)), allow_none=False)
    is_vpe = Boolean(allow_none=False,
                     description="Return reserved ips that are either attached to a VPE (in case True) "
                                 "or available for attachment (in case False).")

    @validates_schema
    def validate_one_of_params(self, data, **kwargs):
        if not (data.get("endpoint_gateway_id") or data.get("subnet_id")):
            raise ValidationError("Either provide one or both of 'subnet_id' and 'endpoint_gateway_id'.")


class IBMSubnetResourceSchema(Schema):
    REF_KEY_TO_RESOURCE_TYPE_MAPPER = {
        "vpc": IBMVpcNetwork,
        "network_acl": IBMNetworkAcl,
        "public_gateway": IBMPublicGateway,
        "resource_group": IBMResourceGroup,
        "routing_table": IBMRoutingTable,
        "zone": IBMZone
    }

    vpc = Nested("OptionalIDNameSchema", required=True, description="The VPC the subnet is to be a part of")
    ip_version = String(
        validate=OneOf(["ipv4"]), default="ipv4", description="The IP version(s) to support for this subnet."
    )
    name = String(
        required=True, allow_none=False, validate=[Regexp(IBM_RESOURCE_NAME_PATTERN), Length(min=1, max=63)],
        description="The user-defined name for this subnet.", example="subnet-1"
    )
    network_acl = Nested(
        "OptionalIDNameSchema",
        description="The network ACL to use for this subnet. If unspecified, the default network ACL for the VPC is "
                    "used.\n\n**Default**: ` default network ACL`"
    )
    public_gateway = Nested(
        "OptionalIDNameSchema",
        description="The public gateway to handle internet bound traffic for this subnet."
    )
    resource_group = Nested(
        "OptionalIDNameSchemaWithoutValidation",
        description="The resource group to use. If unspecified, the account's "
                    "[default resource group](https://cloud.ibm.com/apidocs/resource-manager#introduction) is used."
    )
    routing_table = Nested(
        "OptionalIDNameSchema",
        description="The routing table to use for this subnet. If unspecified, the default routing table for the VPC "
                    "is used. The routing table properties `route_direct_link_ingress`, `route_transit_gateway_ingress`"
                    ", and `route_vpc_zone_ingress` must be `false`"
    )
    ipv4_cidr_block = IPv4CIDR(
        example="10.0.0.0/24", type='CIDR',
        description="The IPv4 range of the subnet, expressed in CIDR format\n\n"
                    "OneOf `target_available_ipv4_address_count` or `target_ipv4_cidr_block` is required."
    )
    total_ipv4_address_count = Integer(
        example=16,
        validate=Range(min=8, max=8388608),
        description="The total number of IPv4 addresses required. Must be a power of 2. The VPC must have a default "
                    "address prefix in the specified zone, and that prefix must have a free CIDR range with at least "
                    "this number of addresses.\n\n"
                    "OneOf `target_available_ipv4_address_count` or `target_ipv4_cidr_block` is required."
    )
    zone = Nested(
        "OptionalIDNameSchema",
        description="If `target_total_ipv4_address_count` is present, `zone` is required. Otherwise, DO NOT send it."
    )

    @validates_schema
    def validate_zone_or_cidr_block(self, data, **kwargs):
        if (data.get("ipv4_cidr_block") and data.get("total_ipv4_address_count")) or not \
                (data.get("ipv4_cidr_block") or data.get("total_ipv4_address_count")):
            raise ValidationError("Either provide 'ipv4_cidr_block' or 'total_ipv4_address_count'")

        if data.get("total_ipv4_address_count") and not data.get("zone"):
            raise ValidationError("'zone' is mandatory if 'total_ipv4_address_count' is provided")

    @validates_schema
    def validate_address_count_power_of_2(self, data, **kwargs):
        if data.get("total_ipv4_address_count"):
            addr_count = int(data["total_ipv4_address_count"])
            if addr_count & (addr_count - 1):
                raise ValidationError("'total_ipv4_address_count' should be a power of 2")


class IBMSubnetInSchema(Schema):
    REF_KEY_TO_RESOURCE_TYPE_MAPPER = {}

    resource_json = Nested("IBMSubnetResourceSchema", required=True)
    ibm_cloud = Nested("OptionalIDNameSchemaWithoutValidation", required=True)
    region = Nested("OptionalIDNameSchema", required=True)


class UpdateIBMSubnetSchema(Schema):
    name = String(validate=[Regexp(IBM_RESOURCE_NAME_PATTERN), Length(min=1, max=63)],
                  description="The user-defined name for this subnet.", example="subnet-1")
    network_acl = Nested("IBMAclOutSchema", only=("id", "name"),
                         description="The network ACL to use for this subnet."
                                     "If unspecified, the default network ACL for the VPC is used.\n\n"
                                     "**Default**: ` default network ACL`")
    public_gateway = Nested("IBMPublicGatewayOutSchema", only=("id",),
                            description="The public gateway to handle internet bound traffic for this subnet.")
    routing_table = Nested(IBMResourceRefSchema, title="IBMResourceRefSchema",
                           description="The routing table to use for this subnet. If unspecified, the default "
                                       "routing table for the VPC is used. The routing table properties "
                                       "`route_direct_link_ingress`, `route_transit_gateway_ingress`, and "
                                       "`route_vpc_zone_ingress` must be `false`")


class IBMSubnetOutSchema(Schema):
    id = String(
        required=True,
        example=uuid.uuid4().hex, format="uuid",
        description="The unique identifier for this subnet")
    name = \
        String(
            required=True, allow_none=False, validate=[Regexp(IBM_RESOURCE_NAME_PATTERN), Length(min=1, max=63)],
            description="The user-defined name for this subnet.", example="subnet-1"
        )
    ip_version = \
        String(
            validate=OneOf(["ipv4"]), default="ipv4", required=True,
            description="The IP version(s) to support for this subnet."
        )
    total_ipv4_address_count = \
        Integer(
            required=True, allow_none=False,
            description="The total number of IPv4 addresses in this subnet.\n\n**Note**: This is calculated as "
                        "2<sup>(32 − prefix length)</sup>. For example, the prefix length `/24` gives: \n\n"
                        "2<sup>(32 − 24)</sup> = 2<sup>8</sup> = 256 addresses."
        )
    available_ipv4_address_count = \
        Integer(
            required=True, allow_none=False, example=15,
            description="The number of IPv4 addresses in this subnet that are not in-use, and have not been reserved "
                        "by the user or the provider."
        )

    created_at = DateTime(required=True, allow_none=False, description="The date and time that the subnet was created")
    ipv4_cidr_block = \
        IPv4CIDR(
            required=True, allow_none=False, example="10.0.0.0/24", type='CIDR',
            description="The IPv4 range of the subnet, expressed in CIDR format"
        )
    status = String(required=True, validate=OneOf(IBMSubnet.ALL_STATUSES_LIST), description="The status of the subnet")
    ibm_cloud = Nested("IBMCloudRefOutSchema", required=True)
    resource_group = Nested("IBMResourceGroupRefOutSchema", required=True)
    region = Nested("IBMRegionRefOutSchema", required=True)
    zone = Nested("IBMZoneRefOutSchema", description="The zone this subnet resides in", required=True)
    routing_table = \
        Nested(
            IBMResourceRefSchema, title="IBMResourceRefSchema", required=True,
            description="The routing table to use for this subnet. If unspecified, the default routing table for "
                        "the VPC is used. The routing table properties `route_direct_link_ingress`, "
                        "`route_transit_gateway_ingress`, and `route_vpc_zone_ingress` must be `false`"
        )
    associated_resources = Nested("IBMSubnetAssociatedResourcesOutSchema", required=True)


class IBMSubnetQuerySchema(IBMResourceQuerySchema):
    subnet_id = String(required=True, allow_none=False, validate=(Regexp(IBM_UUID_PATTERN), Length(equal=32)))


class IBMSubnetAssociatedResourcesOutSchema(Schema):
    vpc = Nested("IBMVpcNetworkRefOutSchema", required=True)
    address_prefix = Nested("IBMAddressPrefixRefOutSchema", required=True)
    public_gateway = Nested("IBMPublicGatewayRefOutSchema", description="The public gateway reference", required=True)
    network_acl = Nested("IBMAclRefOutSchema", description="The network ACL for this subnet", required=True)
    vpn_gateways = Nested("IBMVpnGatewayRefOutSchema", many=True, required=True)
    network_interfaces = Nested("IBMInstanceNetworkInterfaceRefOutSchema", many=True, required=True)
    load_balancers = Nested("IBMLoadBalancerRefOutSchema", many=True, required=True)


class IBMReservedIpResourceSchema(Schema):
    REF_KEY_TO_RESOURCE_TYPE_MAPPER = {
        "subnet": IBMSubnet
    }

    subnet = Nested("OptionalIDNameSchema", required=True)
    name = \
        String(
            required=True, allow_none=False, validate=[Regexp(IBM_RESOURCE_NAME_PATTERN), Length(min=1, max=63)],
            description="The user-defined name for this Reserved Ip.", example="reserved-ip-1"
        )
    auto_delete = Boolean(required=True)


class IBMReservedIpInSchema(Schema):
    REF_KEY_TO_RESOURCE_TYPE_MAPPER = {}

    resource_json = Nested("IBMReservedIpResourceSchema", required=True)
    ibm_cloud = Nested("IBMCloudOutSchema", only=("id",), required=True)
    region = Nested("IBMRegionOutSchema", only=("id",), required=True)


class IBMReservedIpOutSchema(Schema):
    id = \
        String(required=True, example=uuid.uuid4().hex, format="uuid", description="The unique identifier for this ip")
    subnet = Nested("OptionalIDNameSchema", required=True)
    name = \
        String(
            required=True, allow_none=False, validate=[Regexp(IBM_RESOURCE_NAME_PATTERN), Length(min=1, max=63)],
            description="The user-defined name for this Reserved Ip.", example="subnet-1"
        )
    auto_delete = Boolean(required=True)
    address = IPv4(required=True)
    status = String(required=True)


class SubnetAvailableIPsOutSchema(Schema):
    available_ips = List(IPv4(example="192.168.1.29"))


class IBMSubnetRefOutSchema(IBMSubnetOutSchema):
    class Meta:
        fields = ("id", "name", "zone", "ipv4_cidr_block", "address_prefix")


class IBMSubnetValidateJsonResourceSchema(Schema):
    class Meta:
        fields = ("name", "zone", "ipv4_cidr_block", "address_prefix")


class IBMSubnetValidateJsonOutSchema(Schema):
    id = String(
        required=True, allow_none=False, validate=[Length(equal=32), Regexp(IBM_UUID_PATTERN)],
        description="Unique ID of the IBM Subnet"
    )
    resource_json = Nested(IBMSubnetValidateJsonResourceSchema, required=True)


class SubnetTargetSchema(Schema):
    REF_KEY_TO_RESOURCE_TYPE_MAPPER = {
        "public_gateway": IBMPublicGateway
    }

    public_gateway = Nested("OptionalIDNameSchema", required=True)


class IBMReservedIpRefOutSchema(IBMReservedIpOutSchema):
    class Meta:
        fields = ("id", "name")


class SubnetRoutingTableTargetSchema(Schema):
    REF_KEY_TO_RESOURCE_TYPE_MAPPER = {
        "routing_table": IBMRoutingTable
    }

    routing_table = Nested("OptionalIDNameSchema", required=True)


class IBMSubnetAvailableIp4ListQuerySchema(Schema):
    number_of_ips = Integer(allow_none=False)
