from marshmallow import Schema, EXCLUDE
from marshmallow.fields import String, Integer, Nested
from marshmallow.validate import Length, Regexp

from ibm.web.cloud_translations.aws_translator.schemas.consts import AWS_UUID_PATTERN
from ibm.web.cloud_translations.aws_translator.schemas.base import BaseSchema


class AWSListenerSchema(BaseSchema):
    id = String(required=True, allow_none=False, validate=[Length(equal=32), Regexp(AWS_UUID_PATTERN)],
                description="Unique ID of the Listener")
    port = Integer(required=True, allow_none=False)
    protocol = String(required=True, allow_none=False)
    load_balancer = Nested("AWSListenerLoadBalancerSchema", required=True, unknown=EXCLUDE)


class AWSListenerLoadBalancerSchema(Schema):
    id = String(required=True, allow_none=False, validate=[Length(equal=32), Regexp(AWS_UUID_PATTERN)],
                description="Unique ID of the Listener")
