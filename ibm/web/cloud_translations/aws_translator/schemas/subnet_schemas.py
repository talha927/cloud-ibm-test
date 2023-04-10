from marshmallow import EXCLUDE
from marshmallow.fields import String
from marshmallow.validate import Length, Regexp

from ibm.web.cloud_translations.aws_translator.schemas.base import BaseSchema
from ibm.web.cloud_translations.aws_translator.schemas.consts import AWS_UUID_PATTERN, IPV4_CIDR_PATTERN


class AWSSubnetSchema(BaseSchema):
    id = String(required=True, allow_none=False, validate=[Length(equal=32), Regexp(AWS_UUID_PATTERN)],
                description="Unique ID of the subnet")
    vpc_id = String(required=True, allow_none=False, validate=[Length(equal=32), Regexp(AWS_UUID_PATTERN)],
                    description="Unique ID of the Vpc")
    resource_id = String(required=True, allow_none=False, description="Resource id of the subnet")
    zone = String(required=True, allow_none=False, description="Zone of the subnet")
    ipv4_cidr_block = String(required=True, allow_none=False, validate=[Regexp(IPV4_CIDR_PATTERN)],
                             description="ipv4 cidr block")

    class Meta:
        unknown = EXCLUDE
