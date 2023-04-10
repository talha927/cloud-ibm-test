from marshmallow import Schema, validates_schema, ValidationError
from marshmallow.fields import Integer, Nested, String
from marshmallow.validate import Length, Range, Regexp

from ibm.common.req_resp_schemas.consts import IBM_RESOURCE_NAME_PATTERN
from ibm.models import IBMSnapshot, IBMVolume, IBMVolumeProfile
from ibm.web.ibm.volumes.schemas import IBMCRNSchema


class IBMVolumePrototypeInstanceByImageAndSourceTemplateContext(Schema):
    REF_KEY_TO_RESOURCE_TYPE_MAPPER = {
        "profile": IBMVolumeProfile,
    }

    name = String(
        required=True, allow_none=False,
        validate=[(Regexp(IBM_RESOURCE_NAME_PATTERN)), Length(min=1, max=63)],
        description="User defined unique name of the ibm volume"
    )
    profile = Nested(
        "OptionalIDNameSchema", required=True,
        description="Either 'name' or 'ID' of `volume profile` is required."
    )
    iops = Integer(
        validate=Range(min=100, max=1000),
        description="IOPs must only be provided if profile is 'custom'"
    )
    encryption_key = Nested(
        IBMCRNSchema,
        description="If unspecified, the `encryption` type for the volume will be `provider_managed`."
    )
    capacity = Integer(validate=Range(min=10, max=16000))


class IBMVolumePrototypeInstanceByVolumeContext(Schema):
    REF_KEY_TO_RESOURCE_TYPE_MAPPER = {
        "profile": IBMVolumeProfile,
        "source_snapshot": IBMSnapshot
    }

    name = String(
        required=True, allow_none=False,
        validate=[(Regexp(IBM_RESOURCE_NAME_PATTERN)), Length(min=1, max=63)],
        description="User defined unique name of the ibm volume"
    )
    profile = Nested(
        "IBMVolumeProfileOptionalReferenceSchema", required=True,
        description="Either 'name' or 'ID' of `volume profile` is required."
    )
    iops = Integer(
        validate=Range(min=100, max=1000),
        description="IOPs must only be provided if profile is 'custom'"
    )
    encryption_key = Nested(
        IBMCRNSchema,
        description="If unspecified, the `encryption` type for the volume will be `provider_managed`."
    )
    capacity = Integer(validate=Range(min=10, max=16000))
    source_snapshot = Nested(
        "OptionalIDNameSchema", required=True,
        description="The 'ID' or 'name' snapshot from which to clone the volume."
    )


class IBMVolumePrototypeInstanceContext(Schema):
    REF_KEY_TO_RESOURCE_TYPE_MAPPER = {
        "id": IBMVolume,
        "profile": IBMVolumeProfile,
    }

    id = Nested(
        "OptionalIDNameSchema",
        description="An existing volume to attach to the instance"
    )
    name = String(
        allow_none=False,
        validate=[(Regexp(IBM_RESOURCE_NAME_PATTERN)), Length(min=1, max=63)],
        description="User defined unique name of the ibm volume"
    )
    profile = Nested(
        "IBMVolumeProfileOptionalReferenceSchema",
        description="Either 'name' or 'ID' of `volume profile` is required."
    )
    iops = Integer(
        validate=Range(min=100, max=1000),
        description="IOPs must only be provided if profile is 'custom'"
    )
    capacity = Integer(validate=Range(min=10, max=16000))
    encryption_key = Nested(
        IBMCRNSchema,
        description="If unspecified, the `encryption` type for the volume will be `provider_managed`."
    )

    # TODO: this ones are not supported.
    # volume_by_capacity = Nested("IBMVolumePrototypeByCapacityOutSchema")
    # volume_by_source_snapshot = Nested("IBMVolumePrototypeBySourceSnapshotOutSchema")

    @validates_schema
    def validate_oneof(self, data, **kwargs):
        REQUIRED_FIELDS = ["name", "profile"]
        available_data = map(lambda field: data.get(field), REQUIRED_FIELDS)

        if not (data.get("id") or all(available_data)):
            raise ValidationError(f"One of 'id', {REQUIRED_FIELDS} should be provided.")
        if any(available_data) and data.get("id"):
            raise ValidationError(f"Either {REQUIRED_FIELDS} or 'id' should be provided. Not both.")


class IBMVolumePrototypeInstanceContextOutSchema(Schema):
    id = String(required=True)
    name = String(
        allow_none=False, required=True,
        description="Name of the ibm volume"
    )
    profile = Nested(
        "IBMVolumeProfileRefOutSchema",
        description="Either 'name' or 'ID' of `volume profile` is required."
    )
    iops = Integer()
    capacity = Integer()
    encryption_key = Nested(IBMCRNSchema)
    source_snapshot = Nested("IBMSnapshotRefOutSchema")
