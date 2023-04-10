import uuid

from apiflask.fields import Boolean, DateTime, Integer, Nested, String
from apiflask.schemas import Schema
from apiflask.validators import Length, OneOf, Regexp
from marshmallow import validates_schema, ValidationError
from marshmallow.validate import Range

from ibm.common.req_resp_schemas.consts import CRON_SPEC_PATTERN, IBM_RESOURCE_NAME_PATTERN, IBM_UUID_PATTERN
from ibm.models import IBMInstanceGroup, IBMInstanceGroupManager, IBMInstanceGroupManagerAction


class IBMInstanceGroupManagerActionResourceSchema(Schema):
    REF_KEY_TO_RESOURCE_TYPE_MAPPER = {}
    name = String(required=True, allow_none=False, validate=(Regexp(IBM_RESOURCE_NAME_PATTERN)),
                  description="User defined name of the instance Group Manager Action.")
    run_at = String(validate=(Regexp("^((19|20)[0-9][0-9])[-](0[1-9]|1[012])[-](0[1-9]|[12][0-9]|3[01])[T](0[1-9]|1"
                                     "[012]|[2][0-3])[:]([0-5][0-9])[:]([0-5][0-9])[.]([0-9]){0,6}Z$")),
                    description="The date and time the scheduled action will run.")
    cron_spec = String(validate=(Regexp(CRON_SPEC_PATTERN), Length(min=9, max=63)), example="*/5 1,2,3 * * *",
                       description="User defined name of the instance Group Manager Action.")
    group = Nested("IBMInstanceGroupOutSchema", only=("membership_count",))
    manager = Nested("IBMInstanceGroupManagerOutSchema", only=("max_membership_count", "min_membership_count", "id",))

    @validates_schema
    def validate_scheduled_action_requirements(self, data, **kwargs):
        if data.get("group") and data.get("manager"):
            raise ValidationError(
                "'group', and 'manager' both should not be sent at the same time")
        if data.get("run_at") and data.get("cron_spec"):
            raise ValidationError(
                "'run_at', and 'cron_spec' both should not be sent at the same time")


class IBMInstanceGroupManagerActionInSchema(Schema):
    REF_KEY_TO_RESOURCE_TYPE_MAPPER = {
        "instance_group": IBMInstanceGroup,
        "instance_group_manager": IBMInstanceGroupManager
    }

    resource_json = Nested(IBMInstanceGroupManagerActionResourceSchema, required=True)
    ibm_cloud = Nested("OptionalIDNameSchemaWithoutValidation", required=True)
    instance_group = Nested("OptionalIDNameSchema", required=True)
    instance_group_manager = Nested("OptionalIDNameSchema", required=True)


class IBMInstanceGroupManagerActionOutSchema(Schema):
    id = String(required=True, allow_none=False, example=uuid.uuid4().hex,
                validate=(Regexp(IBM_UUID_PATTERN), Length(equal=32)))
    name = String(required=True, allow_none=False, validate=(Regexp(IBM_RESOURCE_NAME_PATTERN)),
                  description="User defined name of the instance group manager action")
    resource_id = String(required=True, allow_none=False)
    created_at = DateTime(required=True, allow_none=False)
    href = String(required=True, allow_none=False)
    auto_delete = Boolean(required=True, description="Indicates whether this scheduled action will be automatically"
                                                     " deleted after it has completed and auto_delete_timeout hours"
                                                     " have passed. At present, this is always true, but may be "
                                                     "modifiable in the future.")
    auto_delete_timeout = Integer(validate=Range(min=0, max=744), example=24,
                                  description="If auto_delete is true, and this scheduled action has finished, the "
                                              "hours after which it will be automatically deleted. If the value is 0, "
                                              "the action will be deleted once it has finished. This value may be "
                                              "modifiable in the future.")
    resource_type = String(required=True, validate=OneOf(IBMInstanceGroupManagerAction.ALL_RESOURCE_TYPES_LIST),
                           description="The resource type.")
    status = String(required=True, validate=OneOf(IBMInstanceGroupManagerAction.ALL_STATUSES_LIST),
                    description="The status of the instance group action.")
    updated_at = DateTime(required=True, allow_none=False)
    action_type = String(required=True, validate=OneOf(IBMInstanceGroupManagerAction.ALL_ACTION_TYPES_LIST),
                         description="The type of action for the instance group.")
    cron_spec = String(validate=(Regexp(CRON_SPEC_PATTERN), Length(min=9, max=63)),
                       description="The cron specification for a recurring scheduled action. Actions can be applied "
                                   "a maximum of one time within a 5 min period.")
    last_applied_at = DateTime(
        description="The date and time the scheduled action was last applied. If absent, the action has never"
                    " been applied.")
    next_run_at = DateTime(
        description="The date and time the scheduled action will next run. If absent, the system is currently "
                    "calculating the next run time.")
    group_membership_count = Integer(required=True, validate=Range(min=0, max=100), example=10,
                                     description="The number of members the instance group should have at the"
                                                 " scheduled time.")
    max_membership_count = Integer(validate=Range(min=1, max=1000), example=10,
                                   description="The maximum number of members the instance group should have at the "
                                               "scheduled time.")
    min_membership_count = Integer(validate=Range(min=1, max=1000), example=10,
                                   description="The minimum number of members the instance group should have at the"
                                               " scheduled time.")
    instance_group_manager = Nested("IBMInstanceGroupManagerRefOutSchema")
    instance_group = Nested("IBMInstanceGroupRefOutSchema")


class IBMInstanceGroupManagerActionRefOutSchema(IBMInstanceGroupManagerActionOutSchema):
    class Meta:
        fields = ("id", "name")


class IBMInstanceGroupManagerActionUpdateSchema(Schema):
    cron_spec = String(validate=(Regexp(CRON_SPEC_PATTERN), Length(min=9, max=63)),
                       description="The cron specification for a recurring scheduled action. Actions can be applied "
                                   "a maximum of one time within a 5 min period.")
    group_membership_count = Integer(validate=Range(min=0, max=100), example=10,
                                     description="The number of members the instance group should have at the"
                                                 " scheduled time.")
    max_membership_count = Integer(validate=Range(min=1, max=1000), example=10,
                                   description="The maximum number of members the instance group should have at the "
                                               "scheduled time.")
    min_membership_count = Integer(validate=Range(min=1, max=1000), example=10,
                                   description="The minimum number of members the instance group should have at the"
                                               " scheduled time.")
    name = String(required=True, allow_none=False, validate=(Regexp(IBM_RESOURCE_NAME_PATTERN)),
                  description="User defined name of the instance group manager action")
    run_at = DateTime(description="The date and time the scheduled action will run.")
