from marshmallow import Schema, validates_schema, ValidationError
from marshmallow.fields import DateTime, Nested, String
from marshmallow.validate import Length, OneOf, Regexp

from ibm.common.req_resp_schemas.consts import DATE_TIME_FORMAT, IBM_UUID_PATTERN
from ibm.models import IBMListenerPolicyRule
from ibm.models.ibm.load_balancer_models import LBCommonConsts


class IBMListenerPolicyRuleResourceSchema(Schema):
    REF_KEY_TO_RESOURCE_TYPE_MAPPER = {}

    condition = String(
        required=True, allow_none=False,
        validate=OneOf(IBMListenerPolicyRule.ALL_CONDITIONS_LIST),
        description="The condition of the rule."
    )
    type = String(
        required=True, allow_none=False,
        validate=OneOf(IBMListenerPolicyRule.ALL_TYPES_LIST),
        description="The type of the rule.\n\n"
                    "Body rules are applied to form-encoded request bodies using the `UTF-8` character set."
    )
    # Todo: post_load decorator for url_encoding. Maybe
    value = String(
        required=True, allow_none=False,
        validate=Length(min=1, max=128),
        description="If the rule type is `query` and the rule condition is not `matches_regex`, "
                    "the value must be percent-encoded."
    )
    field = String(
        validate=Length(min=1, max=128), example="MY-APP-HEADER",
        description="The field is applicable to `header`, `query`, and `body` rule types.\n\n"
                    "If the rule type is `header`, this property is required.\n\n"
                    "If the rule type is `query`, this is optional. If specified and the rule "
                    "condition is not `matches_regex`, the value must be percent-encoded.\n\n"
                    "If the rule type is `body`, this is optional."
    )

    @validates_schema
    def validate_field(self, data, **kwargs):
        if data.get("type") == "header" and not data.get("field"):
            raise ValidationError("'field' is required with type='header'")

        if data.get("type") in ["hostname", "path"] and data.get("field"):
            raise ValidationError("'field' should not be provided with ['hostname', 'path']")


class IBMListenerPolicyRuleInSchema(Schema):
    REF_KEY_TO_RESOURCE_TYPE_MAPPER = {}

    resource_json = Nested(IBMListenerPolicyRuleResourceSchema, required=True)
    ibm_cloud = Nested("OptionalIDNameSchemaWithoutValidation", required=True)
    region = Nested("OptionalIDNameSchema", required=True)
    policy = Nested("OptionalIDNameSchema", required=True)


class IBMListenerPolicyRuleOutSchema(Schema):
    id = String(
        required=True,
        validate=(Regexp(IBM_UUID_PATTERN), Length(equal=32)),
        description="The rule's unique identifier."
    )
    resource_id = String(required=True, description="UUID of the IBM Policy Rule on IBM Cloud")
    created_at = DateTime(required=True, format=DATE_TIME_FORMAT)
    provisioning_status = String(required=True, validate=OneOf(LBCommonConsts.ALL_STATUSES_LIST), data_key="status")
    condition = String(required=True, validate=OneOf(IBMListenerPolicyRule.ALL_CONDITIONS_LIST))
    type = String(required=True, validate=OneOf(IBMListenerPolicyRule.ALL_TYPES_LIST))
    # Todo: post_load decorator for url_encoding. Maybe
    value = String(required=True, validate=Length(min=1, max=128))
    field = String(validate=Length(min=1, max=128))
    # status = String(required=True)


class IBMListenerPolicyRuleRefOutSchema(IBMListenerPolicyRuleOutSchema):
    class Meta:
        fields = ("id",)


class UpdateIBMListenerPolicyRuleSchema(Schema):
    condition = String(
        validate=OneOf(IBMListenerPolicyRule.ALL_CONDITIONS_LIST),
        description="The condition of the rule."
    )
    type = String(
        validate=OneOf(IBMListenerPolicyRule.ALL_TYPES_LIST),
        description="The type of the rule.\n\n"
                    "Body rules are applied to form-encoded request bodies using the `UTF-8` character set."
    )
    # Todo: post_load decorator for url_encoding. Maybe
    value = String(
        validate=Length(min=1, max=128),
        description="If the rule type is `query` and the rule condition is not `matches_regex`, "
                    "the value must be percent-encoded."
    )
    field = String(
        validate=Length(min=1, max=128), example="MY-APP-HEADER",
        description="The field is applicable to `header`, `query`, and `body` rule types.\n\n"
                    "If the rule type is `header`, this property is required.\n\n"
                    "If the rule type is `query`, this is optional. If specified and the rule "
                    "condition is not `matches_regex`, the value must be percent-encoded.\n\n"
                    "If the rule type is `body`, this is optional."
    )
