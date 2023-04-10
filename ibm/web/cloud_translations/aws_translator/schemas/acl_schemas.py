from marshmallow import EXCLUDE, Schema
from marshmallow.fields import Boolean, Integer, Nested, String
from marshmallow.validate import Length, Regexp

from ibm.web.cloud_translations.aws_translator.schemas.base import BaseSchema
from ibm.web.cloud_translations.aws_translator.schemas.consts import AWS_UUID_PATTERN, IPV4_CIDR_PATTERN


class AWSAclSchema(BaseSchema):
    id = String(required=True, allow_none=False, validate=[Length(equal=32), Regexp(AWS_UUID_PATTERN)])
    vpc_id = String(required=True, allow_none=False, description="Resource id of the vpc")
    resource_id = String(required=True, allow_none=False)
    entries = Nested("AWSAclEntrySchema", required=False, many=True, unknown=EXCLUDE)
    associations = Nested("AWSAclAssociationSchema", required=False, many=True, unknown=EXCLUDE)

    class Meta:
        unknown = EXCLUDE


class AWSAclEntrySchema(Schema):
    id = String(required=True, allow_none=False, validate=[Length(equal=32), Regexp(AWS_UUID_PATTERN)])
    protocol = String(required=True, allow_none=False)
    rule_action = String(required=True, allow_none=False)
    rule_number = Integer(required=True, allow_none=False)
    ipv4_cidr_block = String(required=True, allow_none=False, validate=[Regexp(IPV4_CIDR_PATTERN)])
    is_egress = Boolean(required=True, allow_none=False)
    port_range = Nested("AWSAclEntryPortRangeSchema", required=False, unknown=EXCLUDE)

    class Meta:
        unknown = EXCLUDE


class AWSAclEntryPortRangeSchema(Schema):
    from_port = Integer(required=True, allow_none=False)
    to_port = Integer(required=True, allow_none=False)

    class Meta:
        unknown = EXCLUDE


class AWSAclAssociationSchema(Schema):
    subnet_id = String(required=True, allow_none=False, validate=[Length(equal=32), Regexp(AWS_UUID_PATTERN)])

    class Meta:
        unknown = EXCLUDE
