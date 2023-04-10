from marshmallow import Schema, EXCLUDE
from marshmallow.fields import String, Nested
from marshmallow.validate import Length, Regexp

from ibm.web.cloud_translations.aws_translator.schemas.base import BaseSchema
from ibm.web.cloud_translations.aws_translator.schemas.consts import AWS_UUID_PATTERN, PEER_ADDRESS_PATTERN, \
    IPV4_CIDR_PATTERN


class AWSVPNConnectionSchema(BaseSchema):
    id = String(required=True, allow_none=False, validate=[Length(equal=32), Regexp(AWS_UUID_PATTERN)],
                description="Unique ID of the VPN Connection")

    virtual_private_gateway_id = String(required=True, allow_none=False,
                                        validate=[Length(equal=32), Regexp(AWS_UUID_PATTERN)],
                                        description="Unique ID of the VPN Gateway")
    options = Nested("AWSVPNConnectionOptionsSchema", required=False, unknown=EXCLUDE)


class AWSVPNConnectionOptionsSchema(Schema):
    tunnel_options = Nested("AWSVPNConnectionKeySchema", required=False, many=True, unknown=EXCLUDE)
    local_ipv4_network_cidr = String(required=True, allow_none=False, validate=[Regexp(IPV4_CIDR_PATTERN)],
                                     description="ipv4 cidr block")
    remote_ipv4_network_cidr = String(required=True, allow_none=False, validate=[Regexp(IPV4_CIDR_PATTERN)],
                                      description="ipv4 cidr block")


class AWSVPNConnectionKeySchema(Schema):
    pre_shared_key = String(required=True, )
    outside_ip_address = String(required=True, allow_none=False, validate=(Regexp(PEER_ADDRESS_PATTERN),),
                                description="The IP address of the peer VPN gateway.")
