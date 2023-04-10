from marshmallow import EXCLUDE, Schema
from marshmallow.fields import Dict, List, Nested, String
from marshmallow.validate import Length, Regexp

from ibm.web.cloud_translations.aws_translator.schemas.base import BaseSchema
from ibm.web.cloud_translations.aws_translator.schemas.consts import AWS_UUID_PATTERN


class AWSEksClusterSchema(BaseSchema):
    id = String(required=True, allow_none=False, validate=[Length(equal=32), Regexp(AWS_UUID_PATTERN)],
                description="Unique ID of the Eks cluster")
    name = String(required=True, allow_none=False)
    version = String(required=True, allow_none=False)
    cluster_resource_vpc_config = Dict(required=True, allow_none=False)
    eks_node_groups = Nested("AWSEksNodeGroupSchema", required=False, allow_none=False,
                             many=True, unknown=EXCLUDE)
    kubernetes_network_config = Dict(required=True, allow_none=False)

    class Meta:
        unknown = EXCLUDE


class AWSEksNodeGroupSchema(Schema):
    id = String(required=True, allow_none=False, validate=[Length(equal=32), Regexp(AWS_UUID_PATTERN)])
    node_group_name = String(required=True, allow_none=False)
    node_group_scaling = Dict(required=False, allow_none=False)
    subnet_ids = List(String(required=True, allow_none=False))

    class Meta:
        unknown = EXCLUDE
