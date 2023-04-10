from marshmallow import EXCLUDE, Schema
from marshmallow.fields import Integer, List, Nested, String
from marshmallow.validate import Length, Regexp

from ibm.web.cloud_translations.aws_translator.schemas.base import BaseSchema
from ibm.web.cloud_translations.aws_translator.schemas.consts import AWS_UUID_PATTERN


class AWSNetworkInterfaceSchema(BaseSchema):
    id = String(required=True, allow_none=False, validate=[Length(equal=32), Regexp(AWS_UUID_PATTERN)],
                description="Unique ID of the Network Interface")
    resource_id = String(required=True, allow_none=False, description="Resource id of the Network Interface")
    private_ip_address = String(required=False, allow_none=False,
                                description="Private IP Address of the Network Interface")
    security_groups = List(
        String(required=False, allow_none=False, validate=[Length(equal=32), Regexp(AWS_UUID_PATTERN)],
               description="Unique ID of the security groups"))
    subnet_id = String(required=True, allow_none=False, validate=[Length(equal=32), Regexp(AWS_UUID_PATTERN)],
                       description="Unique ID of the Network Interface")
    network_interface_association = Nested("AWSNetworkInterfaceAssociationSchema", required=False, allow_none=False,
                                           many=False, unknown=EXCLUDE)
    attachment = Nested("AWSNetworkInterfaceAttachmentSchema", required=False, allow_none=False,
                        many=False, unknown=EXCLUDE)

    class Meta:
        unknown = EXCLUDE


class AWSNetworkInterfaceAssociationSchema(Schema):
    elastic_ip_id = String(required=False, allow_none=False, validate=[Length(equal=32), Regexp(AWS_UUID_PATTERN)])

    class Meta:
        unknown = EXCLUDE


class AWSNetworkInterfaceAttachmentSchema(Schema):
    device_index = Integer(required=True, allow_none=False)

    class Meta:
        unknown = EXCLUDE
