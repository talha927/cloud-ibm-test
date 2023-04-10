from marshmallow import EXCLUDE, Schema, validates_schema
from marshmallow.fields import Boolean, Integer, Nested, String
from marshmallow.validate import Length, Regexp

from ibm.web.cloud_translations.aws_translator.schemas.base import BaseSchema
from ibm.web.cloud_translations.aws_translator.schemas.consts import AWS_UUID_PATTERN


class AWSSecurityGroupSchema(BaseSchema):
    id = String(required=True, allow_none=False, validate=[Length(equal=32), Regexp(AWS_UUID_PATTERN)],
                description="Unique ID of the security group")
    vpc_id = String(required=True, allow_none=False, validate=[Length(equal=32), Regexp(AWS_UUID_PATTERN)],
                    description="Unique ID of the Vpc")
    group_name = String(required=True, allow_none=False, description="group_name of the security group")
    resource_id = String(required=True, allow_none=False)
    ip_permissions = Nested("AWSSecurityGroupIpPermissionSchema", required=False, many=True, unknown=EXCLUDE)

    @validates_schema
    def modify_group_name(self, data, **kwargs):
        if not (2 <= len(data['group_name']) <= 64) or " " in data['group_name']:
            data['group_name'] = data['resource_id'] if 2 <= len(data['resource_id']) <= 64 else data['id']

        return data

    class Meta:
        unknown = EXCLUDE


class AWSSecurityGroupIpPermissionSchema(Schema):
    id = String(required=True, allow_none=False, validate=[Length(equal=32), Regexp(AWS_UUID_PATTERN)])
    ip_protocol = String(required=True, allow_none=False)
    is_egress = Boolean(required=True, allow_none=False)
    from_port = Integer(required=False, allow_none=False)
    to_port = Integer(required=False, allow_none=False)
    ip_ranges = Nested("AWSSecurityGroupIpPermissionIpRangesSchema", required=False, many=True, unknown=EXCLUDE)

    class Meta:
        unknown = EXCLUDE


class AWSSecurityGroupIpPermissionIpRangesSchema(Schema):
    id = String(required=True, allow_none=False, validate=[Length(equal=32), Regexp(AWS_UUID_PATTERN)])
    cidr_ip = String(required=True, allow_none=False)
    type = String(required=True, allow_none=False)

    class Meta:
        unknown = EXCLUDE
