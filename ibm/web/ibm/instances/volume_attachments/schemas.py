import uuid

from apiflask.fields import Boolean, DateTime, Nested, String
from apiflask.schemas import Schema
from apiflask.validators import Length, OneOf, Regexp
from marshmallow import validates_schema, ValidationError

from ibm.common.req_resp_schemas.consts import DATE_TIME_FORMAT, IBM_HREF_PATTERN, IBM_RESOURCE_NAME_PATTERN, \
    IBM_UUID_PATTERN
from ibm.models import IBMInstance, IBMVolumeAttachment, IBMVolume


class IBMVolumeAttachmentUpdateSchema(Schema):
    name = String(required=True, allow_none=False,
                  validate=[(Regexp(IBM_RESOURCE_NAME_PATTERN)), Length(min=1, max=63)],
                  description="User defined unique name of the ibm volume")
    delete_volume_on_instance_delete = Boolean(
        required=True, description="If set to true, when deleting the instance the volume will also be deleted")


class IBMVolumeAttachmentResourceSchema(Schema):
    REF_KEY_TO_RESOURCE_TYPE_MAPPER = {
        "volume_by_id": IBMVolume
    }
    name = String(allow_none=False,
                  validate=[(Regexp(IBM_RESOURCE_NAME_PATTERN)), Length(min=1, max=63)],
                  description="User defined name of the ibm volume attachment")
    volume = Nested(
        "IBMVolumeResourceSchema",
        description='"name", "profile", "resource_group", "zone", "capacity" Should be provided'
    )
    volume_by_id = Nested("OptionalIDNameSchema")
    delete_volume_on_instance_delete = Boolean(
        default=False, description="If set to true, when deleting the instance the volume will also be deleted"
    )

    @validates_schema
    def validate_one_of_schema(self, data, **kwargs):
        if data.get("volume") and data.get("volume_by_id"):
            raise ValidationError("Provide One of 'volume' or 'volume_by_id'")


class IBMBootVolumeAttachmentResourceSchema(Schema):
    REF_KEY_TO_RESOURCE_TYPE_MAPPER = {}
    volume = Nested(
        "IBMBootVolumeResourceSchema",
        required=True,
        description='"name", "profile", "resource_group", "zone" Should be provided'
    )
    delete_volume_on_instance_delete = Boolean(
        default=False, description="If set to true, when deleting the instance the volume will also be deleted"
    )


class IBMVolumeAttachmentInSchema(Schema):
    REF_KEY_TO_RESOURCE_TYPE_MAPPER = {
        "instance": IBMInstance
    }
    resource_json = Nested(IBMVolumeAttachmentResourceSchema, required=True)
    ibm_cloud = Nested("OptionalIDNameSchemaWithoutValidation", required=True)
    region = Nested("OptionalIDNameSchema", required=True)
    instance = Nested("OptionalIDNameSchema", required=True)


class IBMVolumeAttachmentOutSchema(Schema):
    id = String(required=True, allow_none=False, example=uuid.uuid4().hex,
                validate=(Regexp(IBM_UUID_PATTERN), Length(equal=32)))
    name = String(required=True, validate=[(Regexp(IBM_RESOURCE_NAME_PATTERN)), Length(min=1, max=63)])
    status = String(required=True, validate=OneOf(IBMVolumeAttachment.ALL_STATUSES_LIST))
    resource_id = String(required=True, allow_none=False, description="Unique ID on IBM Cloud")
    type = String(required=True, validate=OneOf(IBMVolumeAttachment.ALL_ATTACHMENT_TYPE))
    delete_volume_on_instance_delete = \
        Boolean(default=False, description="If true, when deleting the instance the volume will also be deleted")
    href = String(required=True, validate=Regexp(IBM_HREF_PATTERN))
    created_at = DateTime(format=DATE_TIME_FORMAT, required=True)
    volume = Nested("IBMVolumeRefOutSchema", required=True)
    instance = Nested("IBMInstanceRefOutSchema", required=True)


class IBMVolumeAttachmentRefOutSchema(IBMVolumeAttachmentOutSchema):
    class Meta:
        fields = ("id", "name", "type", "delete_volume_on_instance_delete", "volume")


class IBMVolumeAttachmentReferenceSchema(Schema):
    name = String(required=True, allow_none=False,
                  validate=[(Regexp(IBM_RESOURCE_NAME_PATTERN)), Length(min=1, max=63)],
                  description="User defined unique name of the ibm volume attachment")
    volume = Nested("IBMVolumeOutSchema", only=("id", "name"), required=True)
