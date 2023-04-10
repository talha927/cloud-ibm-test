from marshmallow import EXCLUDE, Schema
from marshmallow.fields import String, Integer, Nested
from marshmallow.validate import Length, Regexp

from ibm.web.cloud_translations.aws_translator.schemas.consts import AWS_UUID_PATTERN
from ibm.web.cloud_translations.aws_translator.schemas.base import BaseSchema


class AWSTargetGroupSchema(BaseSchema):
    id = String(required=True, allow_none=False, validate=[Length(equal=32), Regexp(AWS_UUID_PATTERN)],
                description="Unique ID of the Pool")
    name = String(required=True, allow_none=False)
    health_check_timeout_seconds = Integer(allow_none=False)
    load_balancer = Nested("AWSTargetGroupLoadBalancerSchema", required=False, unknown=EXCLUDE)
    port = Integer(required=True, allow_none=False)
    protocol = String(required=True, allow_none=False)


class AWSTargetGroupLoadBalancerSchema(Schema):
    id = String(required=True, allow_none=False, validate=[Length(equal=32), Regexp(AWS_UUID_PATTERN)],
                description="Unique ID of the Pool Load Balancer")
