from marshmallow import EXCLUDE, Schema
from marshmallow.fields import Nested, String
from marshmallow.validate import Length, Regexp

from ibm.common.req_resp_schemas.fields import IPv4CIDR
from ibm.web.cloud_translations.aws_translator.schemas.base import BaseSchema
from ibm.web.cloud_translations.aws_translator.schemas.consts import AWS_UUID_PATTERN


class AWSRouteTableSchema(BaseSchema):
    id = String(required=True, allow_none=False, validate=[Length(equal=32), Regexp(AWS_UUID_PATTERN)],
                description="Unique ID of the Route Table")
    vpc_id = String(required=True, allow_none=False, description="Resource id of the vpc")
    resource_id = String(required=True, allow_none=False, description="Resource id of the Route Table")
    associations = Nested("AWSRouteTableAssociationSchema", required=False, allow_none=False,
                          many=True, unknown=EXCLUDE)
    routes = Nested("AWSRouteTableRouteSchema", required=False, allow_none=False,
                    many=True, unknown=EXCLUDE)

    class Meta:
        unknown = EXCLUDE


class AWSRouteTableAssociationSchema(Schema):
    target_resource_id = String(required=False, allow_none=False, validate=[Length(equal=32), Regexp(AWS_UUID_PATTERN)])
    target_resource_type = String(required=False, allow_none=False)

    class Meta:
        unknown = EXCLUDE


class AWSRouteTableRouteSchema(Schema):
    id = String(required=True, allow_none=False, validate=[Length(equal=32), Regexp(AWS_UUID_PATTERN)],
                description="Unique ID of the Route Table Route")
    destination_ipv4_cidr_block = IPv4CIDR(
        required=False,
        description="The destination of the route. At most two routes per zone in a table can have the same "
                    "destination, and only if both routes have an action of deliver and the next_hop is an IP "
                    "address."
    )
    target_resource_id = String(required=False, allow_none=False, validate=[Length(equal=32), Regexp(AWS_UUID_PATTERN)])
    target_resource_type = String(required=False, allow_none=False)

    class Meta:
        unknown = EXCLUDE
