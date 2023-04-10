from marshmallow import EXCLUDE
from marshmallow.fields import Boolean, Nested, String
from marshmallow.validate import Length, Regexp

from ibm.web.cloud_translations.aws_translator.schemas.base import BaseSchema
from ibm.web.cloud_translations.aws_translator.schemas.consts import AWS_UUID_PATTERN


class AWSInstanceSchema(BaseSchema):
    id = String(required=True, allow_none=False, validate=[Length(equal=32), Regexp(AWS_UUID_PATTERN)],
                description="Unique ID of the Instance")
    vpc_id = String(required=True, allow_none=False, validate=[Length(equal=32), Regexp(AWS_UUID_PATTERN)],
                    description="Unique VPC ID of the Instance")
    resource_id = String(required=True, allow_none=False, description="Resource id of the Instance")
    instance_type = String(required=True, allow_none=False)
    root_device_name = String(required=True, allow_none=False)
    network_interfaces = Nested("AWSNetworkInterfaceSchema", required=True, unknown=EXCLUDE, many=True)
    block_device_mappings = Nested("AWSBlockDeviceMapping", required=True, unknown=EXCLUDE, many=True)

    class Meta:
        unknown = EXCLUDE


class AWSBlockDeviceMapping(BaseSchema):
    id = String(required=True, allow_none=False, validate=[Length(equal=32), Regexp(AWS_UUID_PATTERN)],
                description="Unique ID of the Block Device")
    volume_id = String(required=True, allow_none=False, validate=[Length(equal=32), Regexp(AWS_UUID_PATTERN)],
                       description="Volume ID of the Block Device")
    device_name = String(required=True, allow_none=False)
    delete_on_termination = Boolean()
