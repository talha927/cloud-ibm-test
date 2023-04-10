import uuid

from apiflask import Schema
from apiflask.fields import Boolean, DateTime, Integer, Nested, String
from apiflask.validators import Length, OneOf, Regexp

from ibm.common.req_resp_schemas.consts import DATE_TIME_FORMAT, IBM_HREF_PATTERN, IBM_RESOURCE_NAME_PATTERN, \
    IBM_UUID_PATTERN
from ibm.models import IBMResourceGroup, IBMSnapshot, IBMVolume
from ibm.common.req_resp_schemas.schemas import IBMRegionalResourceListQuerySchema


class UpdateIBMSnapshotSchema(Schema):
    name = String(required=True, allow_none=False, validate=(Regexp(IBM_RESOURCE_NAME_PATTERN), Length(min=1, max=63)),
                  description="The name of the snapshot.")


class IBMSnapshotResourceSchema(UpdateIBMSnapshotSchema):
    REF_KEY_TO_RESOURCE_TYPE_MAPPER = {
        "resource_group": IBMResourceGroup,
        "source_volume": IBMVolume
    }
    name = String(allow_none=False, validate=(Regexp(IBM_RESOURCE_NAME_PATTERN), Length(min=1, max=63)),
                  description="The name of the snapshot.")
    resource_group = Nested("OptionalIDNameSchemaWithoutValidation", required=True)
    source_volume = Nested("OptionalIDNameSchema", required=True,
                           description="A boot or data volume that is attached to an instance.")


class IBMSnapshotOutSchema(Schema):
    id = String(required=True, allow_none=False, example=uuid.uuid4().hex,
                validate=(Regexp(IBM_UUID_PATTERN), Length(equal=32)))
    name = String(required=True, allow_none=False, validate=(Regexp(IBM_RESOURCE_NAME_PATTERN), Length(min=1, max=63)))
    resource_group = Nested("IBMResourceGroupOutSchema", only=("id", "name"), required=True)
    href = String(validate=(Regexp(IBM_HREF_PATTERN)), required=True)
    crn = String(validate=Length(max=255), required=True)
    created_at = DateTime(format=DATE_TIME_FORMAT)
    bootable = Boolean(required=True)
    encryption = String(required=True, validate=OneOf(IBMSnapshot.ALL_ENCRYPTION_LIST))
    lifecycle_state = String(required=True, validate=OneOf(IBMSnapshot.LIFECYCLE_STATES_LIST), data_key="status")
    minimum_capacity = Integer(required=True)
    size = Integer(required=True)
    region = Nested("IBMRegionRefOutSchema", required=True)
    resource_type = String(required=True, validate=OneOf([IBMSnapshot.RESOURCE_TYPE_SNAPSHOT]))
    encryption_key_crn = String()
    source_image = Nested("IBMImageRefOutSchema", required=True)
    operating_system = Nested("IBMOperatingSystemRefOutSchema", required=True)
    source_volume = Nested("IBMVolumeRefOutSchema", required=True)


class IBMSnapshotRefOutSchema(IBMSnapshotOutSchema):
    class Meta:
        fields = ("id", "name")


class IBMSnapshotInSchema(Schema):
    REF_KEY_TO_RESOURCE_TYPE_MAPPER = {}

    resource_json = Nested("IBMSnapshotResourceSchema", required=True)
    ibm_cloud = Nested("OptionalIDNameSchemaWithoutValidation", required=True)
    region = Nested("OptionalIDNameSchema", required=True)


class IBMVolumeQuerySchema(IBMRegionalResourceListQuerySchema):
    source_volume_id = String(example=uuid.uuid4().hex, validate=(Regexp(IBM_UUID_PATTERN), Length(equal=32)))
    bootable = Boolean(description="Boolean flag true or false indicating whether bootable or non bootable snapshots "
                                   "will be listed")
