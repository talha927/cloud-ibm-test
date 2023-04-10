import uuid

from apiflask.fields import DateTime, Integer, Nested, String
from apiflask.schemas import Schema
from apiflask.validators import Length, OneOf, Regexp

from ibm.common.req_resp_schemas.consts import IBM_RESOURCE_NAME_PATTERN, IBM_UUID_PATTERN
from ibm.models import IBMInstanceGroup, IBMInstanceGroupManager, IBMInstanceGroupManagerPolicy


class IBMInstanceGroupManagerPolicyResourceSchema(Schema):
    REF_KEY_TO_RESOURCE_TYPE_MAPPER = {}
    name = String(validate=(Regexp(IBM_RESOURCE_NAME_PATTERN)),
                  description="User defined name of the instance Group Manager Policy.")
    metric_type = String(required=True, validate=OneOf(IBMInstanceGroupManagerPolicy.ALL_METRIC_TYPES_LIST),
                         description="The type of metric to be evaluated.")
    metric_value = Integer(required=True, description="The metric value to be evaluated.")
    policy_type = String(required=True, validate=OneOf(IBMInstanceGroupManagerPolicy.ALL_POLICY_TYPES_LIST),
                         description="The type of policy for the instance group.")


class IBMInstanceGroupManagerPolicyInSchema(Schema):
    REF_KEY_TO_RESOURCE_TYPE_MAPPER = {
        "instance_group": IBMInstanceGroup,
        "instance_group_manager": IBMInstanceGroupManager
    }

    resource_json = Nested(IBMInstanceGroupManagerPolicyResourceSchema, required=True)
    ibm_cloud = Nested("OptionalIDNameSchemaWithoutValidation", required=True)
    instance_group = Nested("OptionalIDNameSchema", required=True)
    instance_group_manager = Nested("OptionalIDNameSchema", required=True)


class IBMInstanceGroupManagerPolicyOutSchema(Schema):
    id = String(required=True, allow_none=False, example=uuid.uuid4().hex,
                validate=(Regexp(IBM_UUID_PATTERN), Length(equal=32)))
    name = String(required=True, allow_none=False, validate=(Regexp(IBM_RESOURCE_NAME_PATTERN)),
                  description="User defined name of the instance group manager policy")
    resource_id = String(required=True, allow_none=False)
    created_at = DateTime(required=True, allow_none=False)
    status = String(required=True)
    href = String(required=True, allow_none=False)
    updated_at = DateTime(required=True, allow_none=False)
    metric_type = String(required=True, validate=OneOf(IBMInstanceGroupManagerPolicy.ALL_METRIC_TYPES_LIST),
                         description="The type of metric to be evaluated.")
    metric_value = Integer(required=True, description="The metric value to be evaluated.")
    policy_type = String(required=True, validate=OneOf(IBMInstanceGroupManagerPolicy.ALL_POLICY_TYPES_LIST),
                         description="The type of policy for the instance group.")
    instance_group_manager = Nested("IBMInstanceGroupManagerRefOutSchema",
                                    description="Either ID or Name of the `instance_group_manager`.")
    instance_group = Nested("IBMInstanceGroupRefOutSchema",
                            description="Either ID or Name of the `instance_group`.")


class IBMInstanceGroupManagerPolicyRefOutSchema(IBMInstanceGroupManagerPolicyOutSchema):
    class Meta:
        fields = ("id", "name")


class IBMInstanceGroupManagerPolicyUpdateSchema(Schema):
    metric_type = String(validate=OneOf(IBMInstanceGroupManagerPolicy.ALL_METRIC_TYPES_LIST),
                         description="The type of metric to be evaluated.")
    metric_value = Integer(description="The metric value to be evaluated.")
    name = String(required=True, allow_none=False, validate=(Regexp(IBM_RESOURCE_NAME_PATTERN)),
                  description="User defined name of the instance group manager policy")
