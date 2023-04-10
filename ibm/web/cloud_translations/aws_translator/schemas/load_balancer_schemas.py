from marshmallow import EXCLUDE, Schema
from marshmallow.fields import String, Nested
from marshmallow.validate import Length, Regexp

from ibm.web.cloud_translations.aws_translator.schemas.consts import AWS_UUID_PATTERN
from ibm.web.cloud_translations.aws_translator.schemas.base import BaseSchema


class AWSLoadBalancerSchema(BaseSchema):
    id = String(required=True, allow_none=False, validate=[Length(equal=32), Regexp(AWS_UUID_PATTERN)],
                description="Unique ID of the Load Balancer")
    name = String(required=True, allow_none=False)
    type = String(required=True, allow_none=False)
    scheme = String(required=True, allow_none=False)
    listeners = Nested("AWSLoadListenerSchema", required=False, many=True, unknown=EXCLUDE)


class AWSLoadListenerSchema(Schema):
    id = String(required=True, allow_none=False, validate=[Length(equal=32), Regexp(AWS_UUID_PATTERN)],
                description="Unique ID of the Listener")
