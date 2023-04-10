from apiflask import Schema
from apiflask.fields import Boolean, DateTime, Integer, Nested, String
from apiflask.validators import Length, OneOf, Range, Regexp
from marshmallow import validates_schema, ValidationError

from ibm.common.req_resp_schemas.consts import DATE_TIME_FORMAT, IBM_HREF_PATTERN, IBM_RESOURCE_NAME_PATTERN, \
    IBM_UUID_PATTERN
from ibm.common.req_resp_schemas.fields import IPv4CIDR
from ibm.common.req_resp_schemas.schemas import IBMRegionalResourceListQuerySchema, IBMResourceQuerySchema
from ibm.models import IBMNetworkAcl, IBMNetworkAclRule, IBMResourceGroup, IBMVpcNetwork


class IBMAclListQuerySchema(IBMRegionalResourceListQuerySchema):
    vpc_id = String(validate=(Regexp(IBM_UUID_PATTERN), Length(equal=32)), description="ID of the IBM VPC.")
    subnet_id = String(validate=(Regexp(IBM_UUID_PATTERN), Length(equal=32)), description="ID of the IBM Subnet.")
    is_default = Boolean(allow_none=False)


class IBMAclResourceSchema(Schema):
    REF_KEY_TO_RESOURCE_TYPE_MAPPER = {
        "vpc": IBMVpcNetwork,
        "resource_group": IBMResourceGroup,
        "source_network_acl": IBMNetworkAcl
    }

    vpc = Nested("OptionalIDNameSchema", required=True, description="The VPC this network ACL is to be a part of")
    name = String(required=True, allow_none=False, validate=(Regexp(IBM_RESOURCE_NAME_PATTERN), Length(min=1, max=63)),
                  description="The name for the acl.")
    resource_group = Nested(
        "OptionalIDNameSchemaWithoutValidation",
        description="Either both or one of '['id', 'name']' should be provided."
    )
    rules = Nested("IBMAclRuleResourceSchema", many=True, description="rules associated with acl.")
    source_network_acl = Nested("OptionalIDNameSchema", many=True, description="Network ACL to copy rules from.")
    subnets = Nested(
        "OptionalIDNameSchema", many=True,
        description="The subnets to which this network ACL is attached.")

    @validates_schema
    def validate_rule_or_network_acl(self, data, **kwargs):
        if data.get("rules") and data.get("source_network_acl"):
            raise ValidationError("'source_network_acl' should NOT be sent if 'rules' is provided")
        elif data.get("source_network_acl") and data.get("rules"):
            raise ValidationError("'rules' should NOT be sent if 'source_network_acl' is provided")


class IBMAclInSchema(Schema):
    REF_KEY_TO_RESOURCE_TYPE_MAPPER = {}

    resource_json = Nested("IBMAclResourceSchema", required=True)
    ibm_cloud = Nested("OptionalIDNameSchemaWithoutValidation", required=True)
    region = Nested("OptionalIDNameSchema", required=True)


class UpdateIBMAclSchema(Schema):
    # TODO: This is out of date/not properly defined. Should be fixed while creating a PR for ACL update tasks
    name = String(required=True, allow_none=False, validate=(Regexp(IBM_RESOURCE_NAME_PATTERN), Length(min=1, max=63)),
                  description="The name for the acl.")
    ibm_cloud = Nested("OptionalIDNameSchemaWithoutValidation", required=True,
                       description="Either both or one of '['id', 'name']' should be provided")
    region = Nested("OptionalIDNameSchema", required=True,
                    description="Either both or one of '['id', 'name']' should be provided")


class IBMAclOutSchema(Schema):
    id = String(validate=Length(equal=32), required=True, description="The unique uuid of the IBM ACL.")
    resource_id = String(required=True, allow_none=False, description="Unique ID on IBM Cloud")
    created_at = DateTime(format=DATE_TIME_FORMAT, required=True)
    crn = String(validate=Length(max=255), required=True)
    href = String(validate=(Regexp(IBM_HREF_PATTERN)), required=True)
    name = \
        String(
            required=True, allow_none=False, validate=(Regexp(IBM_RESOURCE_NAME_PATTERN), Length(min=1, max=63)),
            description="The name of the IBM ACL."
        )
    is_default = Boolean(required=True, description="Default ACL for VPC or not")
    rules = \
        Nested(
            "IBMAclRuleOutSchema", exclude=("network_acl",), many=True, required=True,
            description="rules associated with acl."
        )
    ibm_cloud = Nested("IBMCloudRefOutSchema", required=True)
    resource_group = Nested("IBMResourceGroupRefOutSchema", required=True)
    region = Nested("IBMRegionRefOutSchema", required=True)
    status = String(required=True)
    associated_resources = Nested("IBMAclAssociatedResourcesOutSchema", required=True)


class IBMAclAssociatedResourcesOutSchema(Schema):
    vpc = Nested("IBMVpcNetworkRefOutSchema", required=True)
    subnets = Nested("IBMSubnetRefOutSchema", many=True, required=True)


class IBMAclRefOutSchema(IBMAclOutSchema):
    class Meta:
        fields = ("id", "name", "is_default")


class IBMAclValidateJsonResourceSchema(Schema):
    class Meta:
        fields = ("name", "is_default")


class IBMAclValidateJsonOutSchema(Schema):
    id = String(
        required=True, allow_none=False, validate=[Length(equal=32), Regexp(IBM_UUID_PATTERN)],
        description="Unique ID of the IBM VPC Network"
    )
    resource_json = Nested(IBMAclValidateJsonResourceSchema, required=True)


class IBMAclRuleResourceSchema(Schema):
    REF_KEY_TO_RESOURCE_TYPE_MAPPER = {
        "before_network_acl_rule": IBMNetworkAclRule
    }

    action = String(required=True, validate=OneOf(IBMNetworkAclRule.ALL_ACTIONS_LIST),
                    description="The action of acl.")
    destination = IPv4CIDR(required=True, description="The destination CIDR block. The CIDR block 0.0.0.0/0 applies to"
                                                      " all addresses.")
    direction = String(required=True, validate=OneOf(IBMNetworkAclRule.ALL_DIRECTIONS_LIST),
                       description="The direction of acl.")
    protocol = String(required=True, validate=OneOf(IBMNetworkAclRule.ALL_PROTOCOL_LIST),
                      description="The protocol of acl.")
    source = IPv4CIDR(required=True, description="The source CIDR block. The CIDR block 0.0.0.0/0 applies to "
                                                 "all addresses.")
    before_network_acl_rule = Nested(
        "OptionalIDNameSchema",
        description="Either both or one of '['id', 'name']' should be provided."
    )
    name = String(required=True, allow_none=False, validate=(Regexp(IBM_RESOURCE_NAME_PATTERN), Length(min=1, max=63)),
                  description="The name for the acl.")
    destination_port_max = Integer(validate=Range(min=1, max=65535), description="maximum destination ports allowed")
    destination_port_min = Integer(validate=Range(min=1, max=65535), description="minimum destination ports allowed")
    source_port_max = Integer(validate=Range(min=1, max=65535), description="maximum source ports allowed")
    source_port_min = Integer(validate=Range(min=1, max=65535), description="minimum source ports allowed")
    code = Integer(validate=Range(min=0, max=255), description="code of acl")
    type = Integer(validate=Range(min=0, max=254), description="type of acl")

    @validates_schema
    def validate_protocol_requirements(self, data, **kwargs):
        if (data.get("protocol") == IBMNetworkAclRule.PROTOCOL_TYPE_UDP or
            data.get("protocol") == IBMNetworkAclRule.PROTOCOL_TYPE_TCP) \
                and not (data.get("destination_port_min") and data.get("destination_port_max") and
                         data.get("source_port_min") and data.get("source_port_max")):
            raise ValidationError("'destination_port_min' and 'destination_port_max' and 'source_port_min' and "
                                  "'source_port_max' are required properties with tcp/udp prototypes.")
        elif (data.get("protocol") == IBMNetworkAclRule.PROTOCOL_TYPE_ICMP and (
                data.get("destination_port_min") or data.get("destination_port_max") or data.get("source_port_min") or
                data.get("source_port_max"))):
            raise ValidationError("'destination_port_min' and 'destination_port_max' and 'source_port_min' and "
                                  "'source_port_max' should not be sent if protocol type is 'icmp'.")
        elif (data.get("protocol") == IBMNetworkAclRule.PROTOCOL_TYPE_ALL and (
                data.get("destination_port_min") or data.get("destination_port_max") or data.get("source_port_min") or
                data.get("source_port_max") or data.get("code") or data.get("type"))):
            raise ValidationError("Nothing should be sent if 'protocol' type is 'PROTOCOL_TYPE_ALL' except 'source' "
                                  "and 'destination'")


class IBMAclRuleInSchema(Schema):
    REF_KEY_TO_RESOURCE_TYPE_MAPPER = {
        "network_acl": IBMNetworkAcl
    }

    resource_json = Nested("IBMAclRuleResourceSchema", required=True)
    ibm_cloud = Nested("OptionalIDNameSchemaWithoutValidation", required=True)
    network_acl = Nested("OptionalIDNameSchema", required=True)


class UpdateIBMAclRuleSchema(Schema):
    action = String(validate=OneOf(IBMNetworkAclRule.ALL_ACTIONS_LIST),
                    description="The action of acl.")
    before_network_acl_rule = Nested("IBMAclOutSchema", only=("id",))
    code = Integer(validate=Range(min=0, max=255), description="code of acl")
    destination = IPv4CIDR(required=True, description="The destination CIDR block. The CIDR block 0.0.0.0/0 applies to"
                                                      " all addresses.")
    destination_port_max = Integer(validate=Range(min=1, max=65535), description="maximum destination ports allowed")
    destination_port_min = Integer(validate=Range(min=1, max=65535), description="minimum destination ports allowed")
    direction = String(validate=OneOf(IBMNetworkAclRule.ALL_DIRECTIONS_LIST),
                       description="The direction of acl.")
    protocol = String(required=True, validate=OneOf(IBMNetworkAclRule.ALL_PROTOCOL_LIST),
                      description="The protocol of acl.")
    name = String(allow_none=False, validate=(Regexp(IBM_RESOURCE_NAME_PATTERN), Length(min=1, max=63)),
                  description="The name for the acl.")
    source = IPv4CIDR(required=True, description="The source CIDR block. The CIDR block 0.0.0.0/0 applies to "
                                                 "all addresses.")
    source_port_max = Integer(validate=Range(min=1, max=65535), description="maximum source ports allowed")
    source_port_min = Integer(validate=Range(min=1, max=65535), description="minimum source ports allowed")
    type = Integer(validate=Range(min=0, max=254), description="type of acl")
    ibm_cloud = Nested("IBMCloudOutSchema", only=("id",), required=True)


class IBMAclRuleOutSchema(Schema):
    id = String(validate=Length(equal=32), required=True, description="The unique uuid of the IBM ACL Rule.")
    resource_id = String(required=True, allow_none=False, description="Unique ID on IBM Cloud")
    action = String(required=True, validate=OneOf(IBMNetworkAclRule.ALL_ACTIONS_LIST), description="The action of acl.")
    created_at = DateTime(format=DATE_TIME_FORMAT, required=True)
    destination = \
        IPv4CIDR(
            required=True, description="The destination CIDR block. The CIDR block 0.0.0.0/0 applies to all addresses."
        )
    direction = \
        String(
            required=True, validate=OneOf(IBMNetworkAclRule.ALL_DIRECTIONS_LIST), description="The direction of acl."
        )
    href = String(validate=(Regexp(IBM_HREF_PATTERN)), required=True)
    ip_version = String(required=True, validate=OneOf(IBMNetworkAclRule.ALL_IP_VERSIONS_LIST))
    name = \
        String(
            required=True, allow_none=False, validate=(Regexp(IBM_RESOURCE_NAME_PATTERN), Length(min=1, max=63)),
            description="The name of the IBM ACL Rule."
        )
    protocol = \
        String(required=True, validate=OneOf(IBMNetworkAclRule.ALL_PROTOCOL_LIST), description="The protocol of acl.")
    source = \
        IPv4CIDR(required=True, description="The source CIDR block. The CIDR block 0.0.0.0/0 applies to all addresses.")
    tcp_udp_dst_port_max = Integer(validate=Range(min=1, max=65535), description="minimum destination ports allowed")
    tcp_udp_dst_port_min = Integer(validate=Range(min=1, max=65535), description="maximum destination ports allowed")
    tcp_udp_src_port_max = Integer(validate=Range(min=1, max=65535), description="minimum source ports allowed")
    tcp_udp_src_port_min = Integer(validate=Range(min=1, max=65535), description="maximum source ports allowed")
    icmp_code = Integer(validate=Range(min=0, max=255), description="code of acl")
    icmp_type = Integer(validate=Range(min=0, max=254), description="type of acl")
    before_network_acl_rule = Nested("IBMAclRuleRefOutSchema", description="The reference of before_network_acl_rule.")
    network_acl = Nested("IBMAclRefOutSchema", only=("id", "name"), required=True)
    status = String(required=True)


class IBMAclRuleRefOutSchema(IBMAclRuleOutSchema):
    class Meta:
        fields = ("id", "name")


class IBMAclRuleQuerySchema(IBMResourceQuerySchema):
    acl_id = String(required=True, allow_none=False, validate=(Regexp(IBM_UUID_PATTERN), Length(equal=32)))
