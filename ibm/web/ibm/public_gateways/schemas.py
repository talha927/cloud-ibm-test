from apiflask import Schema
from apiflask.fields import DateTime, Nested, String
from apiflask.validators import Length, OneOf, Regexp

from ibm.common.req_resp_schemas.consts import DATE_TIME_FORMAT, IBM_HREF_PATTERN, IBM_RESOURCE_NAME_PATTERN, \
    IBM_UUID_PATTERN
from ibm.models import IBMFloatingIP, IBMPublicGateway, IBMResourceGroup, IBMVpcNetwork, IBMZone


class IBMPublicGatewayResourceSchema(Schema):
    REF_KEY_TO_RESOURCE_TYPE_MAPPER = {
        "vpc": IBMVpcNetwork,
        "zone": IBMZone,
        "floating_ip": IBMFloatingIP,
        "resource_group": IBMResourceGroup,
    }

    vpc = Nested("OptionalIDNameSchema", required=True, description="specify name or id of the IBM VPC Network")
    zone = Nested("OptionalIDNameSchema", required=True, description="specify name or id of the zone")
    floating_ip = Nested("OptionalIDNameSchema", description="[Optional] specify name or id of the floating IP")
    name = \
        String(
            required=True, allow_none=False, validate=(Regexp(IBM_RESOURCE_NAME_PATTERN), Length(min=1, max=63)),
            description="The name for the public gateway."
        )
    resource_group = Nested(
        "OptionalIDNameSchemaWithoutValidation",
        description="[Optional] specify the name or id of the Resource Group. "
                    "Default resource group is used if the key is not provided"
    )


class IBMPublicGatewayInSchema(Schema):
    REF_KEY_TO_RESOURCE_TYPE_MAPPER = {}

    resource_json = Nested("IBMPublicGatewayResourceSchema", required=True)
    ibm_cloud = Nested("OptionalIDNameSchemaWithoutValidation", required=True)
    region = Nested("OptionalIDNameSchema", required=True)


class UpdateIBMPublicGatewaySchema(Schema):
    name = String(required=True, allow_none=False, validate=(Regexp(IBM_RESOURCE_NAME_PATTERN), Length(min=1, max=63)))


class IBMPublicGatewayOutSchema(Schema):
    id = String(validate=Length(equal=32), required=True, description="The unique uuid of the public gateway.")
    resource_id = String(required=True, allow_none=False, description="Unique ID on IBM Cloud")
    name = \
        String(
            required=True, allow_none=False, validate=[Regexp(IBM_RESOURCE_NAME_PATTERN), Length(min=1, max=63)],
            description="The user-defined name for this public gateway.", example="public-gateway-1"
        )
    created_at = DateTime(format=DATE_TIME_FORMAT, required=True)
    crn = String(validate=Length(max=255), required=True)
    href = String(validate=(Regexp(IBM_HREF_PATTERN)), required=True)
    resource_type = \
        String(
            required=True, validate=OneOf([IBMPublicGateway.DEFAULT_RESOURCE_TYPE]), description="The resource type."
        )
    status = String(required=True, validate=OneOf(IBMPublicGateway.STATUSES_LIST),
                    description="The status of the public gateway on IBM Cloud")
    ibm_cloud = Nested("IBMCloudRefOutSchema", required=True)
    resource_group = Nested("IBMResourceGroupRefOutSchema", required=True)
    region = Nested("IBMRegionRefOutSchema", required=True)
    zone = Nested("IBMZoneRefOutSchema", description="The zone this resource resides in", required=True)

    associated_resources = Nested("IBMPublicGatewayAssociatedResourcesOutSchema", required=True)


class IBMPublicGatewayAssociatedResourcesOutSchema(Schema):
    vpc = Nested("IBMVpcNetworkRefOutSchema", required=True)
    subnets = Nested("IBMSubnetRefOutSchema", required=True)
    floating_ip = Nested("IBMFloatingIpRefOutSchema", required=True)


class IBMPublicGatewayRefOutSchema(IBMPublicGatewayOutSchema):
    class Meta:
        fields = ("id", "name", "zone", "floating_ip", "subnets",)


class IBMPublicGatewayValidateJsonResourceSchema(Schema):
    class Meta:
        fields = ("name", "zone", "floating_ip")


class IBMPublicGatewayValidateJsonOutSchema(Schema):
    id = String(
        required=True, allow_none=False, validate=[Length(equal=32), Regexp(IBM_UUID_PATTERN)],
        description="Unique ID of the IBM Public Gateway"
    )
    resource_json = Nested(IBMPublicGatewayValidateJsonResourceSchema, required=True)
