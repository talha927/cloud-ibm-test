from apiflask import Schema
from apiflask.fields import Boolean, DateTime, Dict, Integer, Nested, String
from apiflask.validators import Equal, Length, OneOf, Regexp
from marshmallow import validates_schema, ValidationError

from ibm.common.req_resp_schemas.consts import DATE_TIME_FORMAT, IBM_HREF_PATTERN, IBM_RESOURCE_NAME_PATTERN, \
    IBM_UUID_PATTERN
from ibm.common.req_resp_schemas.schemas import IBMZonalResourceListQuerySchema
from ibm.models import IBMDedicatedHost, IBMDedicatedHostGroup, IBMDedicatedHostProfile, IBMResourceGroup, IBMZone


class IBMDedicatedHostResourceListQuerySchema(IBMZonalResourceListQuerySchema):
    dedicated_host_id = String(allow_none=False, validate=(Regexp(IBM_UUID_PATTERN), Length(equal=32)), required=True,
                               description="ID of the IBM Dedicated Host.")


class IBMDedicatedHostResourceSchema(Schema):
    REF_KEY_TO_RESOURCE_TYPE_MAPPER = {
        "resource_group": IBMResourceGroup,
        "profile": IBMDedicatedHostProfile,
        "group": IBMDedicatedHostGroup,
        "zone": IBMZone
    }
    name = String(allow_none=False, validate=(Regexp(IBM_RESOURCE_NAME_PATTERN), Length(min=1, max=63)), required=True,
                  description="The unique user-defined name for this dedicated host. ")
    instance_placement_enabled = Boolean(default=True,
                                         description="If set to true, instances can be placed on this dedicated host")
    group = Nested("OptionalIDNameSchema")
    profile = Nested("OptionalIDNameSchema", required=True)
    resource_group = Nested("OptionalIDNameSchemaWithoutValidation", required=True)
    zone = Nested("OptionalIDNameSchema")

    @validates_schema
    def validate_one_of_schema(self, data, **kwargs):
        if not (data.get("group") or (data.get("zone"))):
            raise ValidationError(
                "One of fields between 'group' or 'zone' is required.")

        if data.get("group") and (data.get("zone")):
            raise ValidationError(
                "Only one of fields between 'group' or 'zone' is required.")


class IBMDedicatedHostInSchema(Schema):
    REF_KEY_TO_RESOURCE_TYPE_MAPPER = {}

    resource_json = Nested(IBMDedicatedHostResourceSchema, required=True)
    ibm_cloud = Nested("OptionalIDNameSchemaWithoutValidation", required=True)
    region = Nested("OptionalIDNameSchema", required=True)


class IBMUpdateDedicatedHostSchema(IBMDedicatedHostInSchema):
    name = String(allow_none=False, validate=(Regexp(IBM_RESOURCE_NAME_PATTERN), Length(min=1, max=63)),
                  description="The unique user-defined name for this dedicated host. ")
    instance_placement_enabled = Boolean(required=True,
                                         description="If set to true, instances can be placed on this dedicated host")


class IBMDedicatedHostOutSchema(Schema):
    id = String(validate=Length(equal=32), required=True, description="UUID for this dedicated host")
    resource_id = String(required=True, allow_none=False, description="Unique ID on IBM Cloud")
    available_memory = Integer(required=True, description="available memory in gibibytes")
    available_vcpu = Dict(required=True, allow_none=True, description="The available VCPU for the dedicated host")
    created_at = DateTime(format=DATE_TIME_FORMAT, required=True)
    crn = String(validate=Length(max=255), required=True, description="The CRN for this dedicated host")
    href = String(validate=(Regexp(IBM_HREF_PATTERN)), required=True, description="The URL for this dedicated host")
    instance_placement_enabled = \
        Boolean(required=True, description="If true, instances can be provisioned on this dedicated host")
    lifecycle_state = \
        String(
            required=True, validate=OneOf(IBMDedicatedHost.ALL_LIFECYCLE_STATE_CONSTS), data_key="status",
            description="The lifecycle state of the dedicated host."
        )
    memory = Integer(required=True, description="The total amount of memory in gibibytes for this host")
    name = String(allow_none=False, validate=(Regexp(IBM_RESOURCE_NAME_PATTERN), Length(min=1, max=63)),
                  description="The unique user-defined name for this dedicated host")
    provisionable = \
        Boolean(required=True, description="Indicates whether this dedicated host is available for instance creation")
    resource_type = \
        String(
            required=True, validate=Equal(IBMDedicatedHost.RESOURCE_TYPE_DEDICATED_HOST),
            description="The type of resource referenced"
        )
    socket_count = Integer(required=True, description="The total number of sockets for this host")
    state = \
        String(
            required=True, allow_none=False, validate=(Length(min=1), OneOf(IBMDedicatedHost.ALL_STATE_CONSTS)),
            description="The administrative state of the dedicated host."
        )
    vcpu = Dict(required=True, allow_none=True, description="The total VCPU of the dedicated host")
    supported_instance_profiles = Nested("IBMInstanceProfileRefOutSchema", required=True, many=True)
    ibm_cloud = Nested("IBMCloudRefOutSchema", required=True)
    resource_group = Nested("IBMResourceGroupRefOutSchema", required=True)
    region = Nested("IBMRegionRefOutSchema", required=True)
    zone = Nested("IBMZoneRefOutSchema", required=True)
    associated_resources = Nested("IBMDedicatedHostAssociatedResourcesOutSchema", required=True)


class IBMDedicatedHostAssociatedResourcesOutSchema(Schema):
    dedicated_host_group = Nested("IBMDedicatedHostGroupRefOutSchema", required=True)
    dedicated_host_profile = Nested("IBMDedicatedHostProfileRefOutSchema", required=True)
    instances = Nested("IBMInstanceRefOutSchema", many=True, required=True)
    dedicated_host_disks = Nested("IBMDedicatedHostDiskRefOutSchema", many=True, required=True)


class IBMDedicatedHostRefOutSchema(IBMDedicatedHostOutSchema):
    class Meta:
        fields = ("id", "name", "zone")


class IBMDedicatedHostValidateJsonResourceSchema(Schema):
    class Meta:
        fields = ("name", "zone")


class IBMDedicatedHostValidateJsonOutSchema(Schema):
    id = String(
        required=True, allow_none=False, validate=[Length(equal=32), Regexp(IBM_UUID_PATTERN)],
        description="Unique ID of the IBM VPC Network"
    )
    resource_json = Nested(IBMDedicatedHostValidateJsonResourceSchema, required=True)
