from apiflask import Schema
from apiflask.fields import Boolean, DateTime, Nested, String
from apiflask.validators import Length, OneOf, Regexp
from marshmallow import validates_schema, ValidationError

from ibm.common.req_resp_schemas.consts import DATE_TIME_FORMAT, IBM_HREF_PATTERN, IBM_RESOURCE_NAME_PATTERN, \
    IBM_UUID_PATTERN
from ibm.common.req_resp_schemas.fields import IPv4
from ibm.common.req_resp_schemas.schemas import IBMZonalResourceListQuerySchema
from ibm.models import IBMFloatingIP, IBMNetworkInterface, IBMResourceGroup, IBMZone


class IBMFloatingIpListQuerySchema(IBMZonalResourceListQuerySchema):
    network_interface_id = String(validate=(Regexp(IBM_UUID_PATTERN)), allow_none=False)
    reserved = Boolean(allow_none=False, description="This param will filter out reserved Ips in-case of 'True'"
                                                     "and unreserved ips in-case of 'False'.")


class IBMFloatingIPResourceSchema(Schema):
    REF_KEY_TO_RESOURCE_TYPE_MAPPER = {
        "zone": IBMZone,
        "resource_group": IBMResourceGroup,
        "target": IBMNetworkInterface
    }

    name = String(required=True, allow_none=False, validate=(Regexp(IBM_RESOURCE_NAME_PATTERN), Length(min=1, max=63)),
                  description="The name for the floating ip.")
    resource_group = Nested("OptionalIDNameSchemaWithoutValidation", required=True)
    target = Nested("OptionalIDNameSchema")
    zone = Nested("OptionalIDNameSchema")

    @validates_schema
    def validate_one_of_remote_security_group(self, data, **kwargs):
        if data.get("target") and data.get("zone"):
            return ValidationError("One of 'target' or 'zone' is allowed.")
        elif not (data.get("target") or data.get("zone")):
            return ValidationError("One of 'target' or 'zone' is required.")


class IBMFloatingIPInSchema(Schema):
    REF_KEY_TO_RESOURCE_TYPE_MAPPER = {}

    resource_json = Nested("IBMFloatingIPResourceSchema", required=True)
    ibm_cloud = Nested("OptionalIDNameSchemaWithoutValidation", required=True)
    region = Nested("OptionalIDNameSchema", required=True)


class UpdateIBMFloatingIpSchema(Schema):
    name = String(required=True, allow_none=False, validate=(Regexp(IBM_RESOURCE_NAME_PATTERN), Length(min=1, max=63)),
                  description="The name for the floating ip.")
    target = Nested("IBMInstanceNetworkInterfaceOutSchema", only=("id",))


class IBMFloatingIpTargetOutSchema(Schema):
    id = String(validate=Length(equal=32), required=True,
                description="The unique uuid of the floating ip.")
    name = String(required=True, allow_none=False, validate=(Regexp(IBM_RESOURCE_NAME_PATTERN), Length(min=1, max=63)),
                  description="The name of the floating ip.")
    resource_type = String(required=True, validate=OneOf(["public_gateway", "network_interface"]),
                           description="The type of resource floating ip is attached too.")
    instance = Nested("IBMInstanceOutSchema", only=("id", "name"),
                      description="Instance name and uuid if the connected resource type is 'network_interface'")


class IBMFloatingIpOutSchema(Schema):
    id = String(validate=Length(equal=32), required=True, description="The unique uuid of the floating ip.")
    resource_id = String(required=True, allow_none=False, description="Unique ID on IBM Cloud")
    name = \
        String(
            required=True, allow_none=False, validate=(Regexp(IBM_RESOURCE_NAME_PATTERN), Length(min=1, max=63)),
            description="The name of the floating ip."
        )
    status = String(required=True, validate=OneOf(IBMFloatingIP.STATUSES_LIST))
    address = IPv4(required=True, type="IPv4", example="203.0.113.1")
    crn = String(validate=Length(max=255), required=True)
    href = String(validate=(Regexp(IBM_HREF_PATTERN)), required=True)
    created_at = DateTime(format=DATE_TIME_FORMAT, required=True)
    target = Nested("IBMFloatingIpTargetOutSchema", required=True)
    ibm_cloud = Nested("IBMCloudRefOutSchema", required=True)
    resource_group = Nested("IBMResourceGroupRefOutSchema", required=True)
    region = Nested("IBMRegionRefOutSchema", required=True)
    zone = Nested("IBMZoneRefOutSchema", required=True)


class IBMFloatingIpRefOutSchema(IBMFloatingIpOutSchema):
    class Meta:
        fields = ("id", "name", "zone")
