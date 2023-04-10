from apiflask import Schema
from apiflask.fields import Boolean, DateTime, Integer, Nested, String
from apiflask.validators import Length, OneOf, Range, Regexp
from marshmallow import INCLUDE, validates_schema, ValidationError

from ibm.common.req_resp_schemas.consts import DATE_TIME_FORMAT, IBM_HREF_PATTERN, IBM_RESOURCE_NAME_PATTERN, \
    IBM_UUID_PATTERN
from ibm.common.req_resp_schemas.fields import IPv4, IPv4CIDR
from ibm.common.req_resp_schemas.schemas import IBMRegionalResourceListQuerySchema, IBMResourceQuerySchema
from ibm.models import IBMEndpointGateway, IBMLoadBalancer, IBMNetworkInterface, IBMRegion, IBMResourceGroup, \
    IBMSecurityGroup, IBMSecurityGroupRule, IBMVpcNetwork


class IBMSecurityGroupRuleResourceListQuerySchema(IBMResourceQuerySchema):
    security_group_id = String(
        allow_none=False, validate=(Regexp(IBM_UUID_PATTERN), Length(equal=32)), required=True,
        description="ID of the IBM Security Group."
    )


class IBMSecurityGroupResourceListQuerySchema(IBMRegionalResourceListQuerySchema):
    vpc_id = String(allow_none=False, validate=(Regexp(IBM_UUID_PATTERN), Length(equal=32)))
    default = Boolean(allow_none=False)


class SecurityGroupRuleRemoteSchema(Schema):
    REF_KEY_TO_RESOURCE_TYPE_MAPPER = {
        "security_group": IBMSecurityGroup
    }

    address = IPv4(description="The address of security group.")
    cidr_block = IPv4CIDR()
    security_group = Nested("OptionalIDNameSchema")

    @validates_schema
    def validate_one_of_remote_security_group(self, data, **kwargs):
        if data.get("address") and not (data.get("cidr_block") or data.get("security_group")):
            return
        elif data.get("cidr_block") and not (data.get("address") or data.get("security_group")):
            return
        elif data.get("security_group") and not (data.get("address") or data.get("cidr_block")):
            return
        else:
            raise ValidationError("One of fields 'address', 'cidr_block' and 'security_group' is required.")


class SecurityGroupRuleRemoteOutSchema(Schema):
    address = IPv4(description="The address of security group.")
    cidr_block = IPv4CIDR()
    security_group = Nested("IBMSecurityGroupRefOutSchema")


class IBMSecurityGroupRuleResourceSchema(Schema):
    REF_KEY_TO_RESOURCE_TYPE_MAPPER = {}

    direction = String(required=True, validate=OneOf(IBMSecurityGroupRule.DIRECTIONS_LIST),
                       description="The direction of security group.")
    ip_version = String(required=True, validate=OneOf([IBMSecurityGroupRule.IP_VERSION_IPV4]),
                        description="The ip version of security group.")
    protocol = String(required=True, validate=OneOf(IBMSecurityGroupRule.PROTOCOLS_LIST),
                      description="The protocol of security group.")
    remote = Nested("SecurityGroupRuleRemoteSchema",
                    description="The remote security group reference. Only in-case of 'Any' this field is not "
                                "required.")
    port_min = Integer(validate=Range(min=1, max=65535), description="The minimum port number")
    port_max = Integer(validate=Range(min=1, max=65535), description="The maximum port number")
    code = Integer(validate=Range(min=0, max=255), description="The icmp code.")
    type = Integer(validate=Range(min=0, max=254), description="The icmp type.")

    @validates_schema
    def validate_prototype_requirements(self, data, **kwargs):
        if (data.get("protocol") == IBMSecurityGroupRule.PROTOCOL_UDP or
            data.get("protocol") == IBMSecurityGroupRule.PROTOCOL_TCP) \
                and not (data.get("port_min") and data.get("port_max")):
            raise ValidationError("'port_min' and 'port_max' are required properties with tcp/udp prototypes.")
        elif data.get("protocol") == IBMSecurityGroupRule.PROTOCOL_ALL and \
                (data.get("code") or data.get("type") or data.get("port_min") or data.get("port_max")):
            raise ValidationError("'port_min', 'port_max', 'code' and 'type' are not required with protocol 'All'")
        else:
            return


class IBMSecurityGroupRuleInSchema(Schema):
    REF_KEY_TO_RESOURCE_TYPE_MAPPER = {
        "security_group": IBMSecurityGroup
    }

    resource_json = Nested("IBMSecurityGroupRuleResourceSchema", required=True)
    ibm_cloud = Nested("OptionalIDNameSchemaWithoutValidation", required=True)
    security_group = Nested("OptionalIDNameSchema", required=True)


class UpdateIBMSecurityGroupRuleSchema(Schema):
    direction = String(required=True, validate=OneOf(IBMSecurityGroupRule.DIRECTIONS_LIST),
                       description="The direction of security group.")
    ip_version = String(required=True, validate=OneOf([IBMSecurityGroupRule.IP_VERSION_IPV4]),
                        description="The ip version of security group.")
    protocol = String(required=True, validate=OneOf(IBMSecurityGroupRule.PROTOCOLS_LIST),
                      description="The protocol of security group.")
    remote = Nested("SecurityGroupRuleRemoteSchema", required=True,
                    description="The remote security group reference.")
    port_min = Integer(validate=Range(min=1, max=65535), description="The minimum port number")
    port_max = Integer(validate=Range(min=1, max=65535), description="The maximum port number")
    code = Integer(validate=Range(min=0, max=255), description="The icmp code.")
    type = Integer(validate=Range(min=0, max=254), description="The icmp type.")


class IBMSecurityGroupRuleOutSchema(Schema):
    id = String(validate=Length(equal=32), required=True, description="The unique uuid of the security group rule.")
    resource_id = String(required=True, allow_none=False, description="UUID on IBM Cloud")
    direction = \
        String(
            required=True, validate=OneOf(IBMSecurityGroupRule.DIRECTIONS_LIST),
            description="The security group rule direction"
        )
    href = String(validate=(Regexp(IBM_HREF_PATTERN)), required=True)
    rule_type = \
        String(
            required=True, validate=OneOf(IBMSecurityGroupRule.RULE_TYPES_LIST),
            description="The security group rule type"
        )
    protocol = \
        String(
            required=True, validate=OneOf(IBMSecurityGroupRule.PROTOCOLS_LIST),
            description="The protocol of security group."
        )

    ip_version = \
        String(
            required=True, validate=OneOf([IBMSecurityGroupRule.IP_VERSION_IPV4]),
            description="The ip version of security group."
        )

    port_min = Integer(validate=Range(min=1, max=65535), description="The minimum port number")
    port_max = Integer(validate=Range(min=1, max=65535), description="The maximum port number")
    code = Integer(validate=Range(min=0, max=255), description="The icmp code.")
    type = Integer(validate=Range(min=0, max=254), description="The icmp type.")
    status = String(required=True)
    remote = \
        Nested("SecurityGroupRuleRemoteOutSchema", required=True)
    security_group = Nested("IBMSecurityGroupRefOutSchema", required=True)


class IBMSecurityGroupRuleRefOutSchema(IBMSecurityGroupRuleOutSchema):
    class Meta:
        fields = ("id",)


class SecurityGroupTargetSchema(Schema):
    REF_KEY_TO_RESOURCE_TYPE_MAPPER = {
        "endpoint_gateways": IBMEndpointGateway,
        "load_balancers": IBMLoadBalancer,
        "network_interfaces": IBMNetworkInterface,
    }

    endpoint_gateways = Nested("OptionalIDNameSchema", many=True)
    load_balancers = Nested("OptionalIDNameSchema", many=True)
    network_interfaces = Nested("OptionalIDNameSchema", many=True)


class IBMInstanceWithNetworkInterfaceOutSchema(Schema):
    id = String(required=True, description="UUID of the instance.")
    network_interfaces = Nested("IBMInstanceNetworkInterfaceRefOutSchema", required=True, many=True)


class SecurityGroupTargetOutSchema(Schema):
    endpoint_gateways = Nested("IBMEndpointGatewayRefOutSchema", many=True)
    load_balancer = Nested("IBMLoadBalancerRefOutSchema", many=True)
    instances = Nested("IBMInstanceWithNetworkInterfaceOutSchema", many=True)


class IBMSecurityGroupResourceSchema(Schema):
    REF_KEY_TO_RESOURCE_TYPE_MAPPER = {
        "resource_group": IBMResourceGroup,
        "region": IBMRegion,
        "vpc": IBMVpcNetwork
    }

    name = String(required=True, allow_none=False, validate=(Regexp(IBM_RESOURCE_NAME_PATTERN), Length(min=1, max=63)),
                  description="The name of the security group.")
    region = Nested("OptionalIDNameSchema", only=("id", "name"), required=True)
    resource_group = Nested("OptionalIDNameSchemaWithoutValidation", required=True)
    vpc = Nested("OptionalIDNameSchema", required=True,
                 description="The unique uuid of the vpc or vpc name in-case of bulk creation.")
    rules = Nested("IBMSecurityGroupRuleResourceSchema", many=True, unknown=INCLUDE)
    target = Nested("SecurityGroupTargetSchema")


class IBMSecurityGroupInSchema(Schema):
    REF_KEY_TO_RESOURCE_TYPE_MAPPER = {}

    resource_json = Nested("IBMSecurityGroupResourceSchema", required=True)
    ibm_cloud = Nested("OptionalIDNameSchemaWithoutValidation", required=True)
    region = Nested("OptionalIDNameSchema", required=True)


class UpdateIBMSecurityGroupSchema(Schema):
    name = String(required=True, allow_none=False, validate=(Regexp(IBM_RESOURCE_NAME_PATTERN), Length(min=1, max=63)),
                  description="The name of the security group.")


class IBMSecurityGroupOutSchema(Schema):
    id = String(validate=Length(equal=32), required=True, description="UUID of the security group.")
    resource_id = String(required=True, allow_none=False, description="UUID on IBM Cloud")
    name = \
        String(
            required=True, allow_none=False, validate=(Regexp(IBM_RESOURCE_NAME_PATTERN), Length(min=1, max=63)),
            description="The name of the security group."
        )
    is_default = Boolean(required=True)
    crn = String(validate=Length(max=255), required=True)
    href = String(validate=(Regexp(IBM_HREF_PATTERN)), required=True)
    created_at = DateTime(format=DATE_TIME_FORMAT)
    rules = Nested("IBMSecurityGroupRuleOutSchema", many=True, required=True)
    ibm_cloud = Nested("IBMCloudRefOutSchema", required=True)
    resource_group = Nested("IBMResourceGroupRefOutSchema", required=True)
    status = String(required=True)
    target = Nested("SecurityGroupTargetOutSchema")
    region = Nested("IBMRegionRefOutSchema", required=True)
    associated_resources = Nested("IBMSecurityGroupAssociatedResourcesOutSchema", required=True)


class IBMSecurityGroupAssociatedResourcesOutSchema(Schema):
    vpc = Nested("IBMVpcNetworkRefOutSchema", required=True)


class IBMSecurityGroupRefOutSchema(IBMSecurityGroupOutSchema):
    class Meta:
        fields = ("id", "name", "resource_group")


class IBMSecurityGroupValidateJsonResourceSchema(Schema):
    class Meta:
        fields = ("name", "resource_group")


class IBMSecurityGroupValidateJsonOutSchema(Schema):
    id = String(
        required=True, allow_none=False, validate=[Length(equal=32), Regexp(IBM_UUID_PATTERN)],
        description="Unique ID of the IBM Security Group"
    )
    resource_json = Nested(IBMSecurityGroupValidateJsonResourceSchema, required=True)
