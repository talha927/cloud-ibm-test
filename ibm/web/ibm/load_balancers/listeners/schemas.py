import uuid

from marshmallow import INCLUDE, Schema
from marshmallow.fields import Boolean, DateTime, Integer, Nested, String
from marshmallow.validate import Length, OneOf, Range, Regexp

from ibm.common.req_resp_schemas.consts import DATE_TIME_FORMAT, IBM_UUID_PATTERN
from ibm.common.req_resp_schemas.schemas import IBMRegionalResourceListQuerySchema
from ibm.models.ibm.load_balancer_models import IBMLoadBalancer, IBMPool, LBCommonConsts
from ibm.web.ibm.load_balancers.common.schemas import IBMListenerHTTPSRedirectSchema


class IBMLoadBalancerListenerBaseSchema(Schema):
    port = Integer(
        required=True, allow_none=False,
        validate=Range(min=1, max=65535), example=443,
        description="The listener port number. Each listener in the load balancer must "
                    "have a unique `port` and `protocol` combination.\n\n"
                    "Not supported for load balancers operating with route mode enabled."
    )
    protocol = String(
        required=True, allow_none=False,
        validate=OneOf(LBCommonConsts.ALL_PROTOCOLS_LIST),
        description="The listener protocol. Load balancers in the `network` family support `tcp`. "
                    "Load balancers in the `application` family support `tcp`, `http`, and `https`. "
                    "Each listener in the load balancer must have a unique `port` and `protocol` "
                    "combination."
    )
    # Todo: add certificate_instance
    connection_limit = Integer(
        validate=Range(min=1, max=15000), default=15000, example=2000,
        description="The connection limit of the listener."
    )
    accept_proxy_protocol = Boolean(
        default=False,
        description="If set to `true`, this listener will accept and forward PROXY protocol information. "
                    "Supported by load balancers in the `application` family (otherwise always `false`). "
                    "Additional restrictions:\n\n"
                    "- If this listener has `https_redirect` specified, its `accept_proxy_protocol` value must match "
                    "the `accept_proxy_protocol` value of the `https_redirect` listener. \n\n"
                    "- If this listener is the target of another listener's `https_redirect`, "
                    "its `accept_proxy_protocol` value must match that listener's `accept_proxy_protocol` value."
    )
    default_pool = Nested(
        "OptionalIDNameSchema",
        description="The default pool associated with the listener. The specified pool must:\n\n"
                    "- Belong to this load balancer\n\n"
                    "- Have the same `protocol` as this listener\n\n"
                    "- Not already be the default pool for another listener"
    )
    port_max = Integer(
        validate=Range(min=1, max=65535), example=499,
        description="The inclusive upper bound of the range of ports used by this listener. "
                    "Must not be less than `port_min`.\n\n"
                    "At present, only load balancers operating with route mode enabled support "
                    "different values for `port_min` and `port_max`. When route mode is enabled, "
                    "only a value of `65535` is supported for `port_max`."
    )
    port_min = Integer(
        validate=Range(min=1, max=65535), example=443,
        description="The inclusive lower bound of the range of ports used by this listener."
                    "Must not be greater than `port_max`.\n\n"
                    "At present, only load balancers operating with route mode enabled support different values for "
                    "`port_min` and `port_max`. When route mode is enabled, "
                    "only a value of `1` is supported for `port_min`."
    )
    https_redirect = Nested(
        IBMListenerHTTPSRedirectSchema,
        description="The target listener that requests will be redirected to. This listener must have a "
                    "`protocol` of `http`, and the target listener must have a `protocol` of `https`."
    )


class IBMLoadBalancerListenerResourceSchema(IBMLoadBalancerListenerBaseSchema):
    REF_KEY_TO_RESOURCE_TYPE_MAPPER = {
        "default_pool": IBMPool
    }

    policies = Nested(
        "IBMListenerPolicyInSchema", many=True, unknown=INCLUDE,
        description="The policy prototype objects for this listener."
    )


class IBMLoadBalancerListenerInSchema(Schema):
    REF_KEY_TO_RESOURCE_TYPE_MAPPER = {
        "load_balancer": IBMLoadBalancer
    }

    resource_json = Nested(IBMLoadBalancerListenerResourceSchema, required=True)
    ibm_cloud = Nested("OptionalIDNameSchemaWithoutValidation", required=True)
    region = Nested("OptionalIDNameSchema", required=True)
    load_balancer = Nested("OptionalIDNameSchema", required=True)


class IBMLoadBalancerListenerOutSchema(IBMLoadBalancerListenerBaseSchema):
    id = String(
        required=True, allow_none=False,
        validate=[Length(equal=32)],
        example=uuid.uuid4().hex,
        format="uuid",
        description="The unique identifier for this load balancer listener."
    )
    created_at = DateTime(required=True, allow_none=False, format=DATE_TIME_FORMAT)
    provisioning_status = String(required=True, allow_none=False, validate=OneOf(LBCommonConsts.ALL_STATUSES_LIST),
                                 data_key="status")
    policies = Nested("IBMListenerPolicyOutSchema", many=True, description="Policies for this listener.")


class IBMLoadBalancerListenerRefOutSchema(IBMLoadBalancerListenerOutSchema):
    class Meta:
        fields = ("id",)


class IBMUpdateListenerSchema(IBMLoadBalancerListenerBaseSchema):
    protocol = String(
        validate=OneOf(LBCommonConsts.ALL_PROTOCOLS_LIST),
        description="The listener protocol. Load balancers in the `network` family support `tcp`. "
                    "Load balancers in the `application` family support `tcp`, `http`, and `https`. "
                    "Each listener in the load balancer must have a unique `port` and `protocol` "
                    "combination."
    )


class IBMLoadBalancerListenerListQuerySchema(IBMRegionalResourceListQuerySchema):
    load_balancer_id = String(required=False, allow_none=False, validate=(Regexp(IBM_UUID_PATTERN), Length(equal=32)))
