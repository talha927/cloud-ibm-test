import uuid

from marshmallow import Schema
from marshmallow.fields import DateTime, Integer, Nested, String
from marshmallow.validate import Length, OneOf, Range, Regexp

from ibm.common.req_resp_schemas.consts import DATE_TIME_FORMAT, IBM_UUID_PATTERN
from ibm.common.req_resp_schemas.fields import IPv4
from ibm.common.req_resp_schemas.schemas import IBMResourceQuerySchema
from ibm.models import IBMPool, LBCommonConsts

TARGET_TYPES_LIST = ["network_interface", "instance"]


class IBMLoadBalancerPoolMemberTargetInSchema(Schema):
    id = String(
        required=True,
        validate=[Length(equal=32)],
        example=uuid.uuid4().hex,
        format="uuid",
        description="The unique identifier. This can be one of the following: \n"
                    "- `Instance ID` in case of `Network` Load Balancer\n"
                    "- `Network Interface ID` in case of `Application Load Balancer`"
    )
    type = String(required=True, validate=OneOf(TARGET_TYPES_LIST))
    subnet = Nested("OptionalIDNameSchema", required=True)


class IBMLoadBalancerPoolMemberTargetOutSchema(Schema):
    id = String(
        required=True,
        validate=[Length(equal=32)],
        example=uuid.uuid4().hex,
        format="uuid",
        description="The unique identifier."
    )
    name = String(
        required=True, allow_none=False, validate=Length(max=255),
        description="The user-defined name of either network_interface or instance."
    )
    address = IPv4(description="Address for the network_interface")
    type = String(required=True, validate=OneOf(TARGET_TYPES_LIST))
    subnet = Nested("OptionalIDNameSchema", required=True)


class IBMLoadBalancerPoolMemberResourceSchema(Schema):
    REF_KEY_TO_RESOURCE_TYPE_MAPPER = {}
    port = Integer(
        required=True, allow_none=False,
        validate=Range(1, 65535),
        description="The port number of the application running in the server member.",
        example=80
    )
    target = Nested(
        "IBMLoadBalancerPoolMemberTargetInSchema", required=True, allow_none=False,
        description="The pool member target. Load balancers in the `network` family support "
                    "virtual server instances. Load balancers in the `application` family support "
                    "IP addresses(Network Interface).\n\n"
    )
    weight = Integer(
        validate=Range(0, 100),
        description="Weight of the server member. Applicable only if the pool algorithm is `weighted_round_robin`.",
        example=50
    )


class IBMLoadBalancerPoolMemberInSchema(Schema):
    REF_KEY_TO_RESOURCE_TYPE_MAPPER = {
        "load_balancer_pool": IBMPool
    }

    resource_json = Nested(IBMLoadBalancerPoolMemberResourceSchema, required=True)
    ibm_cloud = Nested("OptionalIDNameSchemaWithoutValidation", required=True)
    pool = Nested("OptionalIDNameSchema", required=True)


class IBMLoadBalancerPoolMemberOutSchema(Schema):
    id = String(
        validate=[Length(equal=32)],
        example=uuid.uuid4().hex,
        format="uuid",
        description="The unique identifier of the pool member."
    )
    resource_id = String(required=True, allow_none=False)
    port = Integer(required=True, allow_none=False)
    health = String(required=True, allow_none=False)
    target = Nested("IBMLoadBalancerPoolMemberTargetOutSchema", required=True, allow_none=False)
    weight = Integer()
    provisioning_status = String(required=True, allow_none=False, validate=OneOf(LBCommonConsts.ALL_STATUSES_LIST),
                                 data_key="status")
    created_at = DateTime(required=True, allow_none=False, format=DATE_TIME_FORMAT)


class IBMLoadBalancerPoolMemberRefOutSchema(IBMLoadBalancerPoolMemberOutSchema):
    class Meta:
        fields = ("id",)


class IBMLoadBalancerPoolMemberUpdateSchema(Schema):
    port = Integer(
        required=True, allow_none=False,
        validate=Range(1, 65535),
        description="The port number of the application running in the server member.",
        example=80
    )
    target = Nested(
        "IBMLoadBalancerPoolMemberTargetInSchema", required=True, allow_none=False,
        description="The pool member target. Load balancers in the `network` family support "
                    "virtual server instances. Load balancers in the `application` family support "
                    "IP addresses(Network Interface).\n\n"
    )
    weight = Integer(
        validate=Range(0, 100),
        description="Weight of the server member. Applicable only if the pool algorithm is `weighted_round_robin`.",
        example=50
    )


class IBMLoadBalancerPoolQuerySchema(IBMResourceQuerySchema):
    pool_id = String(required=True, allow_none=False, validate=(Regexp(IBM_UUID_PATTERN), Length(equal=32)))
