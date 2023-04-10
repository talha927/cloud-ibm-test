import uuid

from apiflask.fields import Boolean, DateTime, Integer, Nested, String
from apiflask.schemas import Schema
from apiflask.validators import Length, OneOf, Range, Regexp
from marshmallow import validates_schema, ValidationError

from ibm.common.req_resp_schemas.consts import IBM_HREF_PATTERN, IBM_RESOURCE_NAME_PATTERN, IBM_UUID_PATTERN
from ibm.models import IBMResourceGroup, IBMSnapshot, IBMVolume, IBMVolumeProfile, IBMZone


class IBMCRNSchema(Schema):
    crn = String(validate=Length(min=1), required=True, description="The CRN for this Volume",
                 example="crn:v1:bluemix:public:is:us-south-1:a/123456::volume:1a6b7274-678d-4dfb-8981-c71dd9d4daa5")


class IBMVolumeProfileOutSchema(Schema):
    id = String(required=True, allow_none=False, example=uuid.uuid4().hex,
                validate=(Regexp(IBM_UUID_PATTERN), Length(equal=32)))
    name = String(required=True)
    family = String(required=True, validate=OneOf(IBMVolumeProfile.ALL_FAMILIES))
    href = String(required=True, validate=Regexp(IBM_HREF_PATTERN),
                  example="https://us-south.iaas.cloud.ibm.com/v1/volume/profiles/general-purpose")


class IBMVolumeProfileOptionalReferenceSchema(Schema):
    id = String(allow_none=False, example=uuid.uuid4().hex,
                validate=(Regexp(IBM_UUID_PATTERN), Length(equal=32)))
    name = String(Description="Name of the volume profile provided by IBM")

    @validates_schema
    def validate_oneof(self, data, **kwargs):
        if not (data.get("id") or data.get("name")) or (data.get("id") and data.get("name")):
            raise ValidationError("Either 'id' or 'name' should be provided")


class IBMVolumeProfileRefOutSchema(IBMVolumeProfileOutSchema):
    class Meta:
        fields = ("id", "name")


class IBMVolumeCOSBucketMigrationSchema(Schema):
    bucket_id = String(required=True, allow_none=False, example=uuid.uuid4().hex,
                       validate=(Regexp(IBM_UUID_PATTERN), Length(equal=32)))
    object_name = String(required=True, allow_none=False, example="abc-1.vhd",
                         validate=(Length(max=64)))
    format = String(required=True, allow_none=False, example="COS_BUCKET_VHD",
                    validate=(Length(max=16), OneOf(["COS_BUCKET_VHD", "COS_BUCKET_VMDK", "COS_BUCKET_QCOW2"])))


class IBMBootVolumeResourceSchema(Schema):
    REF_KEY_TO_RESOURCE_TYPE_MAPPER = {
        "zone": IBMZone,
        "profile": IBMVolumeProfile,
        "resource_group": IBMResourceGroup,
        "source_snapshot": IBMSnapshot
    }
    name = String(required=True, allow_none=False,
                  validate=[(Regexp(IBM_RESOURCE_NAME_PATTERN)), Length(min=1, max=63)],
                  description="User defined unique name of the ibm volume")
    profile = Nested(
        "IBMVolumeProfileOptionalReferenceSchema",
        description="Either name or ID of `volume profile` is required.",
        required=True)
    iops = Integer(validate=Range(min=100, max=1000),
                   description="IOPs must only be provided if profile is `custom`")
    encryption_key = Nested(IBMCRNSchema)
    resource_group = Nested(
        "OptionalIDNameSchemaWithoutValidation",
        description="Either both or one of '['id', 'name']' should be provided."
    )
    zone = Nested("OptionalIDNameSchema", description="Either both or one of '['id', 'name']' should be provided.")
    source_snapshot = Nested("OptionalIDNameSchema")
    source_cos_object = Nested("IBMVolumeCOSBucketMigrationSchema")
    volume_index = Integer(description="volume index, shall be provided if user want this volume to be migrated.")


class IBMVolumeResourceSchema(IBMBootVolumeResourceSchema):
    capacity = Integer(validate=Range(min=10, max=16000), required=True)


class IBMVolumeInSchema(Schema):
    REF_KEY_TO_RESOURCE_TYPE_MAPPER = {}

    resource_json = Nested(IBMVolumeResourceSchema, required=True)
    ibm_cloud = Nested("OptionalIDNameSchemaWithoutValidation", required=True)
    region = Nested("OptionalIDNameSchema", required=True)


class IBMVolumeUpdateSchema(Schema):
    name = String(required=True, allow_none=False, validate=[Regexp(IBM_RESOURCE_NAME_PATTERN), Length(min=1, max=63)])
    capacity = Integer(validate=Range(min=10, max=16000), required=True)
    iops = Integer(validate=Range(min=1))
    profile = Nested("IBMVolumeProfileOutSchema", only=("id", "name"))


class IBMVolumeStatusReasons(Schema):
    code = String(required=True, validate=(Regexp("^[a-z]+(_[a-z]+)*$"), OneOf(["encryption_key_deleted"])))
    message = String(required=True)
    more_info = String(required=True, validate=Regexp(r"^http(s)?:\/\/([^\/?#]*)([^?#]*)(\?([^#]*))?(#(.*))?$"))


class IBMVolumeOutSchema(Schema):
    id = String(required=True, allow_none=False, example=uuid.uuid4().hex,
                validate=(Regexp(IBM_UUID_PATTERN), Length(equal=32)))
    name = \
        String(
            required=True, allow_none=False, validate=[(Regexp(IBM_RESOURCE_NAME_PATTERN)), Length(min=1, max=63)],
            description="name of the ibm volume"
        )
    profile = Nested("IBMVolumeProfileRefOutSchema", required=True)
    iops = Integer(validate=Range(min=100, max=1000))
    encryption_key = Nested(IBMCRNSchema)
    resource_group = Nested("IBMResourceGroupRefOutSchema", required=True)
    capacity = Integer(validate=Range(min=10, max=16000), required=True)
    status = String(required=True, validate=OneOf(IBMVolume.ALL_STATUSES_LIST))
    status_reason = Nested(IBMVolumeStatusReasons)
    active = Boolean(
        required=True,
        description="Indicates whether a running virtual server instance has an attachment to this volume."
    )
    busy = Boolean(required=True)
    encryption = String(required=True, validate=OneOf(IBMVolume.ALL_ENCRYPTION_VALUES))
    crn = String(required=True,
                 example="crn:v1:bluemix:public:is:us-south-1:a/123456::volume:1a6b7274-678d-4dfb-8981-c71dd9d4daa5")
    bandwidth = Integer(required=True)
    created_at = DateTime(required=True)
    href = String(required=True, validate=Regexp(IBM_HREF_PATTERN))
    volume_attachments = Nested("IBMVolumeAttachmentRefOutSchema", many=True)
    operating_system = Nested("IBMOperatingSystemRefOutSchema")
    source_image = Nested("IBMImageRefOutSchema")
    source_snapshot = Nested("IBMSnapshotRefOutSchema")
    zone = Nested("IBMZoneRefOutSchema", required=True)


class IBMVolumeRefOutSchema(IBMVolumeOutSchema):
    class Meta:
        fields = ("id", "name", "zone", "capacity", "profile", "iops")


class IBMVolumesValidateJsonResourceSchema(IBMVolumeOutSchema):
    class Meta:
        fields = ("name",)


class IBMVolumeValidateJsonOutSchema(Schema):
    id = String(
        required=True, allow_none=False, validate=[Length(equal=32), Regexp(IBM_UUID_PATTERN)],
        description="Unique ID of the IBM Operating System"
    )
    resource_json = Nested(IBMVolumesValidateJsonResourceSchema, required=True)
