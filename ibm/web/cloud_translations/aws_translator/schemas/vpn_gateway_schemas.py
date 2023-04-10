from marshmallow import Schema, EXCLUDE
from marshmallow.fields import String, Nested
from marshmallow.validate import Length, Regexp

from ibm.web.cloud_translations.aws_translator.schemas.base import BaseSchema
from ibm.web.cloud_translations.aws_translator.schemas.consts import AWS_UUID_PATTERN


class AWSVirtualPrivateGatewaySchema(BaseSchema):
    id = String(required=True, allow_none=False, validate=[Length(equal=32), Regexp(AWS_UUID_PATTERN)],
                description="Unique ID of the VPN Gateway")
    resource_id = String(required=True, allow_none=False)
    vpn_connections = Nested('AWSVPNGatewayConnectionSchema', required=False, many=True, allow_none=False,
                             unknown=EXCLUDE)


class AWSVPNGatewayConnectionSchema(Schema):
    id = String(required=True, allow_none=False, validate=[Length(equal=32), Regexp(AWS_UUID_PATTERN)],
                description="Unique ID of the Connection")
