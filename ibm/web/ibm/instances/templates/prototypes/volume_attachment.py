from marshmallow import Schema
from marshmallow.fields import Boolean, Nested, String
from marshmallow.validate import Length, Regexp

from ibm.common.req_resp_schemas.consts import IBM_RESOURCE_NAME_PATTERN


class IBMVolumeAttachmentPrototypeInstanceContext(Schema):
    name = String(
        validate=[(Regexp(IBM_RESOURCE_NAME_PATTERN)), Length(min=1, max=63)],
        description="User defined unique name of the ibm volume attachment"
    )
    volume = Nested(
        "IBMVolumePrototypeInstanceContext", required=True
    )
    delete_volume_on_instance_delete = \
        Boolean(
            default=True,
            description="If set to true, when deleting the instance the volume will also be deleted"
        )


class IBMVolumeAttachmentPrototypeInstanceByImageContext(Schema):
    name = String(
        required=True, allow_none=False,
        validate=[(Regexp(IBM_RESOURCE_NAME_PATTERN)), Length(min=1, max=63)],
        description="User defined unique name of the ibm volume attachment"
    )
    volume = Nested("IBMVolumePrototypeInstanceByImageAndSourceTemplateContext", required=True)
    delete_volume_on_instance_delete = Boolean(
        default=True,
        description="If set to true, when deleting the instance the volume will also be deleted"
    )


class IBMVolumeAttachmentPrototypeInstanceByVolumeContext(Schema):
    name = String(
        required=True, allow_none=False,
        validate=[(Regexp(IBM_RESOURCE_NAME_PATTERN)), Length(min=1, max=63)],
        description="User defined unique name of the ibm volume attachment"
    )
    volume = Nested("IBMVolumePrototypeInstanceByVolumeContext", required=True)
    delete_volume_on_instance_delete = Boolean(
        required=True, default=True,
        description="If set to true, when deleting the instance the volume will also be deleted"
    )


class IBMVolumeAttachmentPrototypeInstanceByImageContextOutSchema(IBMVolumeAttachmentPrototypeInstanceByImageContext):
    id = String(required=True)
    is_boot = Boolean(description="If this volume attachment is a boot attachment.")
