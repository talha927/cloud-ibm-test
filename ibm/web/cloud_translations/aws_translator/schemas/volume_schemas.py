from marshmallow import EXCLUDE
from marshmallow.fields import Integer, String
from marshmallow.validate import Length, Regexp

from ibm.web.cloud_translations.aws_translator.schemas.base import BaseSchema
from ibm.web.cloud_translations.aws_translator.schemas.consts import AWS_UUID_PATTERN


class AWSVolumeSchema(BaseSchema):
    id = String(required=True, allow_none=False, validate=[Length(equal=32), Regexp(AWS_UUID_PATTERN)],
                description="Unique ID of the Volume")
    resource_id = String(required=True, allow_none=False, description="Resource id of the Volume")
    zone = String(required=True, allow_none=False, description="Zone of the Volume")
    type = String(required=True, allow_none=False, description="Type of the Volume")
    size = Integer(required=False, allow_none=False, description="Size of the Volume")
    iops = Integer(required=False, allow_none=False, description="IOPs of the Volume")

    class Meta:
        unknown = EXCLUDE
