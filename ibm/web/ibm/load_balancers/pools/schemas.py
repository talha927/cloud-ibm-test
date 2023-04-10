import uuid

from marshmallow import INCLUDE, Schema
from marshmallow.fields import DateTime, Integer, Nested, String
from marshmallow.validate import Length, OneOf, Range, Regexp

from ibm.common.req_resp_schemas.consts import DATE_TIME_FORMAT, IBM_POOL_SESSION_PERSISTENCE_COOKIE_NAME_PATTERN, \
    IBM_RESOURCE_NAME_PATTERN, IBM_URL_PATH_PATTERN, IBM_UUID_PATTERN
from ibm.common.req_resp_schemas.schemas import IBMRegionalResourceListQuerySchema
from ibm.models import IBMPool, IBMPoolSessionPersistence
from ibm.models.ibm.load_balancer_models import LBCommonConsts


class IBMLoadBalancerPoolHealthMonitorInSchema(Schema):
    delay = Integer(
        required=True, allow_none=False,
        validate=Range(2, 60),
        description="The health check interval in seconds. Interval must be greater than timeout value.",
        example=5
    )
    max_retries = Integer(
        required=True,
        allow_none=False,
        validate=Range(1, 10),
        description="The health check max retries.",
        example=2
    )
    timeout = Integer(
        required=True, allow_none=False,
        validate=Range(1, 59),
        description="The health check timeout in seconds.",
        example=2
    )
    type = String(
        required=True, allow_none=False,
        validate=OneOf(IBMPool.ALL_PROTOCOLS_LIST),
        description="The protocol type of this load balancer pool health monitor."
    )
    port = Integer(
        type="TCPUDPPort",
        validate=Range(1, 65535),
        description="The health check port number. If specified, this overrides the ports specified "
                    "in the server member resources.",
        example=22
    )
    url_path = String(
        validate=Regexp(IBM_URL_PATH_PATTERN),
        description="The health check URL path. Applicable only if the health monitor `type` is `http` or `https`. "
                    "This value must be in the format of an "
                    "[origin-form request target](https://tools.ietf.org/html/rfc7230#section-5.3.1.)"
    )


class IBMLoadBalancerPoolHealthMonitorOutSchema(Schema):
    id = String(required=True, allow_none=False)
    delay = Integer(required=True, allow_none=False)
    max_retries = Integer(required=True, allow_none=False)
    timeout = Integer(required=True, allow_none=False)
    type = String(required=True, allow_none=False)
    port = Integer(type="TCPUDPPort", allow_none=True)
    url_path = String(allow_none=True)


class IBMLoadBalancerPoolMonitorRefSchema(IBMLoadBalancerPoolHealthMonitorOutSchema):
    class Meta:
        fields = ("id",)


class IBMLoadBalancerPoolSessionPersistenceSchema(Schema):
    type = String(
        required=True, allow_none=False,
        validate=OneOf(IBMPoolSessionPersistence.ALL_SESSION_PERSISTENCE_TYPES_LIST),
        description="The session persistence type. The `http_cookie` and `app_cookie` types are applicable only "
                    "to the `http` and `https` protocols."
    )
    cookie_name = String(
        validate=Regexp(IBM_POOL_SESSION_PERSISTENCE_COOKIE_NAME_PATTERN),
        description="The session persistence cookie name. Applicable only for type `app_cookie`. "
                    "Names starting with `IBM` are not allowed.",
        example="my-cookie-name"
    )


class IBMLoadBalancerPoolResourceSchema(Schema):
    REF_KEY_TO_RESOURCE_TYPE_MAPPER = {}

    algorithm = String(
        required=True, allow_none=False,
        validate=OneOf(IBMPool.ALL_ALGORITHMS_LIST),
        description="The pool algorithm."
    )
    protocol = String(
        required=True, allow_none=False,
        validate=OneOf(LBCommonConsts.ALL_PROTOCOLS_LIST),
        description="The protocol used for this load balancer pool. Load balancers in the `network` family "
                    "support `tcp`. Load balancers in the `application` family support `tcp`, `http`, and `https`."
    )
    name = String(
        required=True, allow_none=False,
        validate=[Regexp(IBM_RESOURCE_NAME_PATTERN), Length(min=1, max=63)],
        example="my-load-balancer-pool",
        description="The user-defined name for this load balancer pool."
    )
    proxy_protocol = String(
        validate=OneOf(IBMPool.ALL_PROXY_PROTOCOLS_LIST),
        description="The PROXY protocol setting for this pool:\n"
                    "- `v1`: Enabled with version 1 (human-readable header format)\n"
                    "- `v2`: Enabled with version 2 (binary header format)\n"
                    "- `disabled`: Disabled\n\n"
                    "Supported by load balancers in the application family (otherwise always disabled)."
    )
    health_monitor = Nested(
        "IBMLoadBalancerPoolHealthMonitorInSchema", required=True, allow_none=False
    )
    session_persistence = Nested(
        "IBMLoadBalancerPoolSessionPersistenceSchema",
        title="IBMLoadBalancerPoolSessionPersistenceSchema",
        description="The session persistence of this pool."
    )
    members = Nested(
        "IBMLoadBalancerPoolMemberResourceSchema", many=True, unknown=INCLUDE,
        description="The members for this load balancer pool. For load balancers in the `network` family, "
                    "the same ``port`` and target tuple cannot be shared by a pool member of any other "
                    "load balancer in the same VPC."
    )


class IBMLoadBalancerPoolInSchema(Schema):
    REF_KEY_TO_RESOURCE_TYPE_MAPPER = {}

    resource_json = Nested(IBMLoadBalancerPoolResourceSchema, required=True)
    region = Nested("OptionalIDNameSchema", required=True)
    ibm_cloud = Nested("OptionalIDNameSchemaWithoutValidation", required=True)
    load_balancer = Nested("OptionalIDNameSchema", required=True)


class IBMLoadBalancerPoolOutSchema(Schema):
    id = String(
        validate=[Length(equal=32)],
        example=uuid.uuid4().hex,
        format="uuid",
        description="The unique identifier of the pool."
    )
    resource_id = String(
        required=True, allow_none=False, description="Unique ID of the IBM Load Balancer Pool on IBM Cloud"
    )
    created_at = DateTime(required=True, allow_none=False, format=DATE_TIME_FORMAT)
    provisioning_status = String(required=True, allow_none=False, validate=OneOf(LBCommonConsts.ALL_STATUSES_LIST),
                                 data_key="status")
    # Todo: Add instance_groups schema
    algorithm = String(required=True, allow_none=False, description="The pool algorithm.")
    protocol = String(required=True, allow_none=False)
    name = String(required=True, allow_none=False)
    proxy_protocol = String(validate=OneOf(IBMPool.ALL_PROXY_PROTOCOLS_LIST))
    health_monitor = Nested("IBMLoadBalancerPoolHealthMonitorOutSchema", required=True, allow_none=False)
    session_persistence = Nested("IBMLoadBalancerPoolSessionPersistenceSchema")
    members = Nested("IBMLoadBalancerPoolMemberOutSchema", many=True)


class IBMLoadBalancerPoolRefOutSchema(IBMLoadBalancerPoolOutSchema):
    class Meta:
        fields = ("id", "name")


class IBMLoadBalancerPoolUpdateSchema(Schema):
    algorithm = String(
        required=True, allow_none=False,
        validate=OneOf(IBMPool.ALL_ALGORITHMS_LIST),
        description="The pool algorithm."
    )
    protocol = String(
        required=True, allow_none=False,
        validate=OneOf(LBCommonConsts.ALL_PROTOCOLS_LIST),
        description="The protocol used for this load balancer pool. Load balancers in the `network` family "
                    "support `tcp`. Load balancers in the `application` family support `tcp`, `http`, and `https`."
    )
    name = String(
        required=True, allow_none=False,
        validate=[Regexp(IBM_RESOURCE_NAME_PATTERN), Length(min=1, max=63)],
        example="my-load-balancer-pool",
        description="The user-defined name for this load balancer pool."
    )
    proxy_protocol = String(
        validate=OneOf(IBMPool.ALL_PROXY_PROTOCOLS_LIST),
        description="The PROXY protocol setting for this pool:\n"
                    "- `v1`: Enabled with version 1 (human-readable header format)\n"
                    "- `v2`: Enabled with version 2 (binary header format)\n"
                    "- `disabled`: Disabled\n\n"
                    "Supported by load balancers in the application family (otherwise always disabled)."
    )
    health_monitor = Nested(
        "IBMLoadBalancerPoolHealthMonitorInSchema", required=True, allow_none=False
    )
    session_persistence = Nested(
        "IBMLoadBalancerPoolSessionPersistenceSchema",
        title="IBMLoadBalancerPoolSessionPersistenceSchema",
        description="The session persistence of this pool."
    )
    members = Nested(
        "IBMLoadBalancerPoolMemberResourceSchema", many=True,
        description="The members for this load balancer pool. For load balancers in the `network` family, "
                    "the same ``port`` and target tuple cannot be shared by a pool member of any other "
                    "load balancer in the same VPC."
    )


class IBMLoadBalancerPoolListQuerySchema(IBMRegionalResourceListQuerySchema):
    load_balancer_id = String(required=False, allow_none=False, validate=(Regexp(IBM_UUID_PATTERN), Length(equal=32)))
    protocol = String(allow_none=False, validate=OneOf(LBCommonConsts.ALL_PROTOCOLS_LIST))
