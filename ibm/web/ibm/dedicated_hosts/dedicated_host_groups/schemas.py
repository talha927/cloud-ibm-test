from apiflask import Schema
from apiflask.fields import DateTime, Nested, String
from apiflask.validators import Length, OneOf, Regexp

from ibm.common.req_resp_schemas.consts import DATE_TIME_FORMAT, IBM_HREF_PATTERN, IBM_RESOURCE_NAME_PATTERN
from ibm.models import IBMDedicatedHostGroup, IBMDedicatedHostProfile, IBMResourceGroup, IBMZone


class IBMDedicatedHostGroupResourceSchema(Schema):
    REF_KEY_TO_RESOURCE_TYPE_MAPPER = {
        "resource_group": IBMResourceGroup,
        "profile": IBMDedicatedHostProfile,
        "zone": IBMZone
    }
    profile = Nested("OptionalIDNameSchema", many=False, required=True)
    name = String(allow_none=False, validate=(Regexp(IBM_RESOURCE_NAME_PATTERN), Length(min=1, max=63)),
                  description="The unique user-defined name for this dedicated host group")
    resource_group = Nested("OptionalIDNameSchemaWithoutValidation", required=True)
    zone = Nested("OptionalIDNameSchema", required=True)


class IBMDedicatedHostGroupInSchema(Schema):
    REF_KEY_TO_RESOURCE_TYPE_MAPPER = {}

    resource_json = Nested(IBMDedicatedHostGroupResourceSchema, required=True)
    ibm_cloud = Nested("OptionalIDNameSchemaWithoutValidation", required=True)
    region = Nested("OptionalIDNameSchema", required=True)


class IBMUpdateDedicatedHostGroupSchema(Schema):
    name = String(allow_none=False, validate=(Regexp(IBM_RESOURCE_NAME_PATTERN), Length(min=1, max=63)),
                  description="The unique user-defined name for this dedicated host group")


class IBMDedicatedHostGroupOutSchema(Schema):
    id = String(validate=Length(equal=32), required=True, description="UUID of the IBMDedicatedHostGroup")
    resource_id = String(required=True, allow_none=False, description="UUID of the IBMDedicatedHostGroup on IBM Cloud")
    class_ = \
        String(
            data_key="class", required=True, allow_none=False, validate=Length(equal=32),
            description="The dedicated host profile class for hosts in this group"
        )
    created_at = DateTime(format=DATE_TIME_FORMAT, required=True)
    crn = String(validate=Length(max=255), required=True, description="The CRN for this dedicated host group")
    family = \
        String(
            required=True, allow_none=False, validate=(Length(min=1), OneOf(IBMDedicatedHostGroup.ALL_FAMILY_CONSTS)),
            description="The dedicated host profile family for hosts in this group"
        )
    href = String(validate=(Regexp(IBM_HREF_PATTERN)), required=True)
    name = \
        String(
            allow_none=False, validate=(Regexp(IBM_RESOURCE_NAME_PATTERN), Length(min=1, max=63)),
            description="The unique user-defined name for this dedicated host group."
        )
    resource_type = \
        String(
            required=True, validate=OneOf([IBMDedicatedHostGroup.RESOURCE_TYPE_DEDICATED_HOST_GROUP]),
            description="The type of resource referenced"
        )
    supported_instance_profiles = Nested("IBMInstanceProfileRefOutSchema", required=True, many=True)
    ibm_cloud = Nested("IBMCloudRefOutSchema", required=True)
    resource_group = Nested("IBMResourceGroupRefOutSchema", required=True)
    region = Nested("IBMRegionRefOutSchema", required=True)
    zone = Nested("IBMZoneRefOutSchema", required=True)
    status = String(required=True)
    associated_resources = Nested("IBMDedicatedHostGroupAssociatedResourcesOutSchema", required=True)


class IBMDedicatedHostGroupAssociatedResourcesOutSchema(Schema):
    dedicated_hosts = Nested("IBMDedicatedHostRefOutSchema", required=True, many=True)


class IBMDedicatedHostGroupRefOutSchema(IBMDedicatedHostGroupOutSchema):
    class Meta:
        fields = ("id", "name")
