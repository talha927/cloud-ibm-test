from marshmallow import EXCLUDE, Schema
from marshmallow.fields import Nested, String
from marshmallow.validate import Length, Regexp

from ibm.web.cloud_translations.aws_translator.schemas.base import BaseSchema
from ibm.web.cloud_translations.aws_translator.schemas.consts import AWS_UUID_PATTERN, IPV4_CIDR_PATTERN


class AWSVpcSchema(BaseSchema):
    id = String(required=True, allow_none=False, validate=[Length(equal=32), Regexp(AWS_UUID_PATTERN)],
                description="Unique ID of the vpc")
    resource_id = String(required=True, allow_none=False, description="Resource id of the vpc")
    cidr_block = String(required=True, allow_none=False, validate=[Regexp(IPV4_CIDR_PATTERN)],
                        description="ipv4 cidr block")
    cidr_block_association_sets = Nested("AWSVpcCidrBlockAssociationSet", required=False, many=True)
    tags = Nested("AWSTagSchema", many=True, description="Tags of the VPC")

    class Meta:
        unknown = EXCLUDE


class AWSVpcCidrBlockAssociationSet(Schema):
    id = String(required=True, allow_none=False, validate=[Length(equal=32), Regexp(AWS_UUID_PATTERN)],
                description="Unique ID of the CIDR Block Association set")
    resource_id = String(required=True, allow_none=False, description="Resource id of the CIDR Block Association Set")
    cidr_block = String(required=True, allow_none=False, validate=[Regexp(IPV4_CIDR_PATTERN)],
                        description="ipv4 cidr block")

    class Meta:
        unknown = EXCLUDE
