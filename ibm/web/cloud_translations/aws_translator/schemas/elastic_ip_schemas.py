from marshmallow import EXCLUDE
from marshmallow.fields import String
from marshmallow.validate import Length, Regexp

from ibm.web.cloud_translations.aws_translator.schemas.base import BaseSchema
from ibm.web.cloud_translations.aws_translator.schemas.consts import AWS_UUID_PATTERN


class AWSElasticIpSchema(BaseSchema):
    id = String(required=True, allow_none=False, validate=[Length(equal=32), Regexp(AWS_UUID_PATTERN)],
                description="Unique ID of the Elastic IP")
    resource_id = String(required=True, allow_none=False, description="Resource id of the Elastic IP")

    class Meta:
        unknown = EXCLUDE
