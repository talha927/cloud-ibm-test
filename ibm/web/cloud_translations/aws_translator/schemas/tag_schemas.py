from marshmallow import EXCLUDE
from marshmallow.fields import String
from marshmallow.validate import Length, Regexp

from ibm.web.cloud_translations.aws_translator.schemas.base import BaseSchema
from ibm.web.cloud_translations.aws_translator.schemas.consts import AWS_UUID_PATTERN


class AWSTagSchema(BaseSchema):
    id = String(required=True, allow_none=False, validate=[Length(equal=32), Regexp(AWS_UUID_PATTERN)],
                description="Unique ID of the tag")
    resource_id = String(required=True, allow_none=False, validate=[Length(equal=32), Regexp(AWS_UUID_PATTERN)],
                         description="Unique Resource ID")
    resource_type = String(required=True, allow_none=False, description="Resource type of tag")
    key = String(required=True, allow_none=False)
    value = String(required=True, allow_none=False)

    class Meta:
        unknown = EXCLUDE
