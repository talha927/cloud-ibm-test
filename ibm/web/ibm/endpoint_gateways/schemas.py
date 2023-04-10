from apiflask import Schema
from apiflask.fields import DateTime, Nested, String
from apiflask.validators import Length, OneOf, Regexp
from marshmallow import validates_schema, ValidationError

from ibm.common.req_resp_schemas.consts import DATE_TIME_FORMAT, IBM_HREF_PATTERN, IBM_RESOURCE_NAME_PATTERN, \
    IBM_UUID_PATTERN
from ibm.common.req_resp_schemas.schemas import IBMRegionalResourceListQuerySchema
from ibm.models import IBMEndpointGatewayTarget, IBMRegion, IBMResourceGroup, IBMSecurityGroup, IBMSubnetReservedIp, \
    IBMVpcNetwork, IBMEndpointGateway


class IBMEndpointGatewaysListQuerySchema(IBMRegionalResourceListQuerySchema):
    vpc_id = String(validate=(Regexp(IBM_UUID_PATTERN)), allow_none=False)
    security_group_id = String(validate=(Regexp(IBM_UUID_PATTERN)), allow_none=False)


class IBMEndpointGatewayTargetSchema(Schema):
    resource_type = String(required=True, allow_none=False,
                           validate=OneOf(IBMEndpointGatewayTarget.RESOURCE_TYPES_LIST),
                           description="The target resource type. Enum value.")
    crn = String(allow_none=False)
    name = String(allow_none=False, validate=(Regexp(IBM_RESOURCE_NAME_PATTERN)))

    @validates_schema
    def validate_one_of_name_or_crn(self, data, **kwargs):
        if all([data.get("crn"), data.get("name")]):
            raise ValidationError("One of fields 'crn' or 'name' is required. Both are given.")
        elif not any([data.get("crn"), data.get("name")]):
            raise ValidationError("One of fields 'crn' or 'name' is required. None is given.")


class IBMEndpointGatewayIpSchema(Schema):
    REF_KEY_TO_RESOURCE_TYPE_MAPPER = {
        "ip_reference": IBMSubnetReservedIp
    }

    ip_resource_json = Nested("IBMReservedIpResourceSchema",
                              desciption="Payload to reserved an IP for the selected subnet.")
    ip_reference = Nested("OptionalIDNameSchema",
                          description="ID/name of a reserved ip of a subnet of the selected vpc")

    @validates_schema
    def validate_one_of_name_or_crn(self, data, **kwargs):
        if all([data.get("ip_resource_json"), data.get("ip_reference")]):
            raise ValidationError("One of fields 'ip_resource_json' or 'ip_resource_json' is required. Both are given.")
        elif not any([data.get("ip_resource_json"), data.get("ip_reference")]):
            raise ValidationError("One of fields 'ip_resource_json' or 'ip_resource_json' is required. None is given.")


class IBMEndpointGatewayResourceSchema(Schema):
    REF_KEY_TO_RESOURCE_TYPE_MAPPER = {
        "vpc": IBMVpcNetwork,
        "resource_group": IBMResourceGroup,
        "security_groups": IBMSecurityGroup,
        "region": IBMRegion
    }

    name = String(required=True, allow_none=False, validate=(Regexp(IBM_RESOURCE_NAME_PATTERN), Length(min=1, max=63)),
                  description="The name for the floating ip.")
    resource_group = Nested("OptionalIDNameSchemaWithoutValidation", required=True)
    target = Nested("IBMEndpointGatewayTargetSchema", required=True, description="Target resource type and crn/name.")
    vpc = Nested("OptionalIDNameSchema", required=True)
    ips = Nested("IBMEndpointGatewayIpSchema", many=True, description="ONE reserved ip per subnet.")
    region = Nested("OptionalIDNameSchema", required=True)
    security_groups = Nested("OptionalIDNameSchema", required=True, many=True,
                             description="The id/name of the attached security group.")


class IBMEndpointGatewayInSchema(Schema):
    REF_KEY_TO_RESOURCE_TYPE_MAPPER = {}

    resource_json = Nested("IBMEndpointGatewayResourceSchema", required=True)
    ibm_cloud = Nested("OptionalIDNameSchemaWithoutValidation", required=True)
    region = Nested("OptionalIDNameSchema", required=True)


class IBMEndpointGatewayOutSchema(Schema):
    id = String(validate=Length(equal=32), required=True, description="The unique uuid of the Security group.")
    resource_id = String(required=True, allow_none=False, description="Unique ID on IBM Cloud")
    name = String(required=True, allow_none=False, validate=(Regexp(IBM_RESOURCE_NAME_PATTERN), Length(min=1, max=63)),
                  description="The name for the floating ip.")
    resource_group = Nested("OptionalIDNameSchemaWithoutValidation", required=True)
    target = Nested("IBMEndpointGatewayTargetSchema", required=True, description="Target resource type and crn/name.")
    vpc = Nested("OptionalIDNameSchema", required=True)
    reserved_ips = Nested("IBMReservedIpRefOutSchema", many=True)
    region = Nested("IBMRegionRefOutSchema", required=True)
    security_groups = Nested("IBMSecurityGroupRefOutSchema", required=True, many=True,
                             description="The id and name of the attached security group. Must belong to the attached"
                                         "vpc.")
    crn = String(validate=Length(max=255), required=True)
    href = String(validate=(Regexp(IBM_HREF_PATTERN)), required=True)
    created_at = DateTime(format=DATE_TIME_FORMAT, required=True)
    ibm_cloud = Nested("IBMCloudRefOutSchema", required=True)
    lifecycle_state = String(required=True, validate=OneOf(IBMEndpointGateway.LIFECYCLE_STATES_LIST), data_key="status")


class UpdateIBMEndpointGatewaySchema(Schema):
    name = String(required=True, allow_none=False, validate=(Regexp(IBM_RESOURCE_NAME_PATTERN), Length(min=1, max=63)),
                  description="The name for the floating ip.")


class IBMEndpointGatewayRefOutSchema(IBMEndpointGatewayOutSchema):
    class Meta:
        fields = ("id", "name")
