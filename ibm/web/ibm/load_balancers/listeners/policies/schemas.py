import logging
import uuid

from marshmallow import INCLUDE, post_load, Schema, validates_schema, ValidationError
from marshmallow.fields import DateTime, Integer, Nested, String
from marshmallow.validate import Length, OneOf, Range, Regexp

from ibm.common.req_resp_schemas.consts import IBM_RESOURCE_NAME_PATTERN, IBM_UUID_PATTERN
from ibm.common.req_resp_schemas.schemas import IBMResourceQuerySchema
from ibm.models.ibm.load_balancer_models import IBMListener, IBMListenerPolicy, IBMLoadBalancer, LBCommonConsts

LOGGER = logging.getLogger(__name__)


class PolicyTargetsSchema(Schema):
    pool_identity = Nested(
        "IBMResourceRefSchema"
    )
    policy_redirect_url = Nested(
        "IBMListenerHTTPSRedirectSchema", only=["http_status_code", "url"],
    )
    https_redirect_url = Nested(
        "IBMListenerHTTPSRedirectSchema", exclude=["url"],
    )


class IBMListenerPolicyResourceSchema(Schema):
    REF_KEY_TO_RESOURCE_TYPE_MAPPER = {}

    name = String(
        required=True, allow_none=False,
        validate=[
            Regexp(IBM_RESOURCE_NAME_PATTERN), Length(min=1, max=63)
        ],
        example="policy-test-1",
        description="The user-defined name for this policy"
                    "listener the policy resides in."
    )
    action = String(
        required=True, allow_none=False,
        validate=OneOf(IBMListenerPolicy.ALL_ACTIONS_LIST),
        description="The policy action.\n\n"
                    "The enumerated values for this property are expected to expand in the future. When processing "
                    "this property, check for and log unknown values. Optionally halt processing and surface the error,"
                    " or bypass the policy on which the unexpected property value was encountered."
    )
    priority = Integer(
        required=True, allow_none=False,
        validate=Range(min=1, max=10), example=5,
        description="Priority of the policy. Lower value indicates higher priority."

    )
    rules = Nested(
        "IBMListenerPolicyRuleResourceSchema", many=True, title="IBMListenerPolicyRule", unknown=INCLUDE,
        description="The rule prototype objects for this policy."
    )
    target = Nested(
        PolicyTargetsSchema,
        description="- If action is `forward`, specify a `pool_identity`. \n\n"
                    "- If action is `redirect`, specify a `policy_redirect_url`. \n\n"
                    "- If action is `https_redirect`, specify a `https_redirect_url`."
    )

    @validates_schema
    def validate_one_of_targets(self, data, **kwargs):
        if data.get("target"):
            available_targets = ["pool_identity", "policy_redirect_url", "https_redirect_url"]
            provided_targets = [target for target in available_targets if target in data.get("target")]
            targets = any(provided_targets)

            if not targets:
                raise ValidationError(f"You should provide at least one of these targets: {available_targets}")
            if len(provided_targets) > 1:
                raise ValidationError(f"Only one target is allowed. You provided: {provided_targets}")

            target = data.get("target")
            if data.get("action") == "forward" and not target.get("pool_identity"):
                raise ValidationError("'pool_identity' is required when action is 'forward'")
            elif data.get("action") == "redirect" and not target.get("policy_redirect_url"):
                raise ValidationError("'policy_redirect_url' is required when action is 'redirect'")
            elif data.get("action") == "https_redirect" and not target.get("https_redirect_url"):
                raise ValidationError("'https_redirect_url' is required when action is 'https_redirect'")

    @post_load
    def ibm_compatible_target(self, data, **kwargs):
        if data.get("target"):
            target_key = list(data["target"].keys())[0]
            target = data["target"].get(target_key)
            if "http_status_code" in target:
                target["http_status_code"] = int(target["http_status_code"])

            data["target"] = target
        return data


class IBMListenerPolicyInSchema(Schema):
    REF_KEY_TO_RESOURCE_TYPE_MAPPER = {
        "listener": IBMListener,
        "load_balancer": IBMLoadBalancer
    }

    resource_json = Nested(IBMListenerPolicyResourceSchema, required=True)
    ibm_cloud = Nested("OptionalIDNameSchemaWithoutValidation", required=True)
    region = Nested("OptionalIDNameSchema", required=True)
    listener = Nested("OptionalIDNameSchema", required=True)


class IBMListenerPolicyOutSchema(Schema):
    id = String(
        required=True, allow_none=False, example=uuid.uuid4().hex,
        validate=(Regexp(IBM_UUID_PATTERN), Length(equal=32)),
        description="The policy's unique identifier."
    )
    created_at = DateTime(
        required=True, allow_none=False, description="The date and time that the policy was created."
    )
    provisioning_status = String(
        required=True, allow_none=False, validate=OneOf(LBCommonConsts.ALL_STATUSES_LIST),
        description="The provisioning status of this policy.", data_key="status"
    )
    name = String(
        required=True, allow_none=False,
        validate=[
            Regexp(IBM_RESOURCE_NAME_PATTERN), Length(min=1, max=63)
        ],
        example="policy-test-1",
        description="The user-defined name for this policy"
                    "listener the policy resides in."
    )
    action = String(
        required=True, allow_none=False,
        validate=OneOf(IBMListenerPolicy.ALL_ACTIONS_LIST)
    )
    priority = Integer(
        required=True, allow_none=False,
        validate=Range(min=1, max=10), example=5,
        description="Priority of the policy. Lower value indicates higher priority."

    )
    rules = Nested(
        "IBMListenerPolicyRuleOutSchema", many=True, title="IBMListenerPolicyRule",
        description="The rule prototype objects for this policy."
    )
    target = Nested(PolicyTargetsSchema, required=True)

    listener = Nested("IBMLoadBalancerListenerRefOutSchema")


class IBMListenerPolicyRefOutSchema(IBMListenerPolicyOutSchema):
    class Meta:
        fields = ("id", "name")


class UpdateIBMListenerPolicySchema(Schema):
    name = String(
        required=True, allow_none=False,
        validate=[
            Regexp(IBM_RESOURCE_NAME_PATTERN), Range(min=1, max=63)
        ],
        example="lb-test-1",
        description="The user-defined name for this policy. Names must be unique within the load balancer "
                    "listener the policy resides in."
    )
    priority = Integer(
        required=True, allow_none=False,
        validate=Range(min=1, max=10), example=5,
        description="Priority of the policy. Lower value indicates higher priority."

    )
    target = Nested(
        PolicyTargetsSchema, required=True,
        description="- If action is `forward`, specify a `pool_identity`. \n\n"
                    "- If action is `redirect`, specify a `policy_redirect_url`. \n\n"
                    "- If action is `https_redirect`, specify a `https_redirect_url`."
    )


class IBMListenerQuerySchema(Schema):
    listener_id = String(required=True, allow_none=False, validate=(Regexp(IBM_UUID_PATTERN), Length(equal=32)))


class IBMPolicyRuleListQuerySchema(IBMResourceQuerySchema):
    policy_id = String(required=True, allow_none=False, validate=(Regexp(IBM_UUID_PATTERN), Length(equal=32)))
