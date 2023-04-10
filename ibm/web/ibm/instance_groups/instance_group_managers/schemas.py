import uuid

from apiflask.fields import Boolean, DateTime, Integer, Nested, String
from apiflask.schemas import Schema
from apiflask.validators import Length, OneOf, Regexp
from marshmallow import validates_schema, ValidationError
from marshmallow.validate import Range

from ibm.common.req_resp_schemas.consts import IBM_RESOURCE_NAME_PATTERN, IBM_UUID_PATTERN
from ibm.common.req_resp_schemas.schemas import IBMResourceQuerySchema
from ibm.models import IBMInstanceGroup, IBMInstanceGroupManager


class IBMInstanceGroupManagerResourceSchema(Schema):
    REF_KEY_TO_RESOURCE_TYPE_MAPPER = {}
    management_enabled = Boolean(default=True, description="Indicates whether this manager will control the instance"
                                                           " group.")

    name = String(validate=(Regexp(IBM_RESOURCE_NAME_PATTERN)),
                  description="User defined name of the instance Group Manager.")
    manager_type = String(required=True, default=IBMInstanceGroupManager.MANAGER_TYPE_SCHEDULED,
                          validate=OneOf(IBMInstanceGroupManager.ALL_MANAGERS_TYPE_LIST),
                          description="The type of instance group manager. ")
    max_membership_count = Integer(validate=Range(min=1, max=1000), example=10,
                                   description="The maximum number of members in a managed instance group.")
    aggregation_window = Integer(validate=Range(min=90, max=600), default=90, example=120,
                                 description="The time window in seconds to aggregate metrics prior to evaluation.")
    cooldown = Integer(validate=Range(min=120, max=3600), default=300, example=210,
                       description="The duration of time in seconds to pause further scale actions after "
                                   "scaling has taken place.")
    min_membership_count = Integer(validate=Range(min=1, max=1000), default=1, example=10,
                                   description="The minimum number of members in a managed instance group.")

    @validates_schema
    def validate_manager_type_requirements(self, data, **kwargs):
        if data.get("manager_type") == IBMInstanceGroupManager.MANAGER_TYPE_AUTOSCALE and not \
                data.get("max_membership_count"):
            raise ValidationError("'max_membership_count' is required property with manager_type autoscale.")
        elif (data.get("manager_type") == IBMInstanceGroupManager.MANAGER_TYPE_SCHEDULED and (
                data.get("max_membership_count") or data.get("aggregation_window") or data.get("cooldown") or
                data.get("min_membership_count"))):
            raise ValidationError("Nothing should be sent if 'manager_type' type is 'scheduled' ")


class IBMInstanceGroupManagerInSchema(Schema):
    REF_KEY_TO_RESOURCE_TYPE_MAPPER = {
        "instance_group": IBMInstanceGroup
    }

    resource_json = Nested(IBMInstanceGroupManagerResourceSchema, required=True)
    ibm_cloud = Nested("OptionalIDNameSchemaWithoutValidation", required=True)
    region = Nested("OptionalIDNameSchema", required=True)
    instance_group = Nested("OptionalIDNameSchema", required=True)


class IBMInstanceGroupManagerOutSchema(Schema):
    id = String(required=True, allow_none=False, example=uuid.uuid4().hex,
                validate=(Regexp(IBM_UUID_PATTERN), Length(equal=32)))
    name = String(required=True, allow_none=False, validate=(Regexp(IBM_RESOURCE_NAME_PATTERN)),
                  description="User defined name of the instance group manager")
    resource_id = String(required=True, allow_none=False)
    created_at = DateTime(required=True, allow_none=False)
    href = String(required=True, allow_none=False)
    management_enabled = Boolean(required=True, description="Indicates whether this manager will control the instance"
                                                            " group.")
    updated_at = DateTime(required=True, allow_none=False)
    aggregation_window = Integer(validate=Range(min=90, max=600), example=120,
                                 description="The time window in seconds to aggregate metrics prior to evaluation.")
    cooldown = Integer(validate=Range(min=120, max=3600), example=210,
                       description="The duration of time in seconds to pause further scale actions after "
                                   "scaling has taken place.")
    manager_type = String(required=True, validate=OneOf(IBMInstanceGroupManager.ALL_MANAGERS_TYPE_LIST),
                          description="The type of instance group manager.")
    max_membership_count = Integer(required=True, validate=Range(min=1, max=1000), example=10,
                                   description="The maximum number of members in a managed instance group.")
    min_membership_count = Integer(validate=Range(min=1, max=1000), example=10,
                                   description="The minimum number of members in a managed instance group.")
    policies = Nested("IBMInstanceGroupManagerPolicyOutSchema", required=True, many=True)
    actions = Nested("IBMInstanceGroupManagerActionRefOutSchema", required=True, many=True)
    status = String(required=True)


class IBMInstanceGroupManagerRefOutSchema(IBMInstanceGroupManagerOutSchema):
    class Meta:
        fields = ("id", "name")


class IBMInstanceGroupManagerUpdateSchema(Schema):
    aggregation_window = Integer(validate=Range(min=90, max=600), example=120,
                                 description="The time window in seconds to aggregate metrics prior to evaluation.")
    cooldown = Integer(validate=Range(min=120, max=3600), example=210,
                       description="The duration of time in seconds to pause further scale actions after "
                                   "scaling has taken place.")
    management_enabled = Boolean(description="Indicates whether this manager will control the instance group.")
    max_membership_count = Integer(validate=Range(min=1, max=1000), example=10,
                                   description="The maximum number of members in a managed instance group.")
    min_membership_count = Integer(validate=Range(min=1, max=1000), example=10,
                                   description="The minimum number of members in a managed instance group.")
    name = String(required=True, allow_none=False, validate=(Regexp(IBM_RESOURCE_NAME_PATTERN)),
                  description="User defined name of the instance group manager")
    ibm_cloud = Nested("IBMCloudOutSchema", only=("id",), required=True)
    instance_group = Nested("OptionalIDNameSchema", required=True)


class IBMInstanceGroupManagerListQuerySchema(IBMResourceQuerySchema):
    instance_group_id = String(required=True, allow_none=False, validate=(Regexp(IBM_UUID_PATTERN), Length(equal=32)))
