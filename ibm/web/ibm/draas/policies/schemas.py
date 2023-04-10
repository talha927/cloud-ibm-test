from apiflask import Schema
from apiflask.fields import Integer, List, Nested, String
from apiflask.validators import Length, Regexp
from marshmallow import validates_schema, ValidationError

from ibm.common.req_resp_schemas.consts import IBM_UUID_PATTERN


class DisasterRecoveryPolicyQuerySchema(Schema):
    cloud_id = String(required=True, allow_none=False, validate=(Regexp(IBM_UUID_PATTERN), Length(equal=32)))


class DisasterRecoveryPolicyOutSchema(Schema):
    id = String(required=True, allow_none=False, validate=[Length(equal=32), Regexp(IBM_UUID_PATTERN)],
                description="Unique ID of the Draas Policy")
    backup_count = Integer(required=True, allow_none=False, description="Number of backups to take per resource")
    description = String(required=False, allow_none=False, description="Description for the Draas policy")
    scheduled_cron_pattern = String(required=False, description="Scheduled pattern for the Draas Policy")
    disaster_recovery_resource_blueprints = List(Nested("DisasterRecoveryBlueprintOutSchema", only=["id", "name"]),
                                                 required=False)


class DisasterRecoveryPolicyInSchema(Schema):
    id = String(required=False, allow_none=False, validate=[Length(equal=32), Regexp(IBM_UUID_PATTERN)],
                description="Unique ID of the Draas Policy")
    backup_count = Integer(required=False, allow_none=False, description="Number of backups to take per resource")
    description = String(required=False, allow_none=False, description="Description for the Draas policy")
    scheduled_cron_pattern = String(required=False, allow_none=False,
                                    description="Scheduled pattern for the Draas Policy")

    @validates_schema
    def validate_schema(self, data, **kwargs):
        if "id" not in data and "scheduled_cron_pattern" not in data:
            raise ValidationError("Please provide id or scheduled_cron_pattern for scheduled_policy")


class DisasterRecoveryDeletePolicyOutSchema(Schema):
    id = String(required=True, allow_none=False, validate=[Length(equal=32), Regexp(IBM_UUID_PATTERN)],
                description="Unique ID of the Draas Policy")
