from apiflask import Schema
from apiflask.fields import Boolean, DateTime, Dict, List, Nested, Raw, String
from apiflask.validators import Length, OneOf
from marshmallow import validates_schema, ValidationError
from webargs.fields import DelimitedList

from ibm.common.req_resp_schemas.consts import DATE_TIME_FORMAT
from ibm.common.req_resp_schemas.schemas import WorkflowRootOutSchema
from ibm.models import WorkflowTask


class WorkflowRootListQuerySchema(Schema):
    filter = Boolean(
        truthy={"True", "true"}, falsy={"False", "false"}, missing=False,
        description="Whether or not any of the filters should be applied."
    )
    statuses = DelimitedList(
        String(validate=OneOf(["PENDING", "COMPLETED_SUCCESSFULLY", "COMPLETED_WITH_FAILURE"])),
        description="Comma separated WorkflowRoot statuses",
    )
    natures = DelimitedList(String(), description="Comma separated WorkflowRoot natures")
    created_after = DateTime(format=DATE_TIME_FORMAT)
    created_before = DateTime(format=DATE_TIME_FORMAT)
    name_like = String(validate=Length(min=1, max=64))

    @validates_schema
    def validate_created_before_and_after(self, data, **kwargs):
        if not data.get("created_after") or not data.get("created_before"):
            return

        if data["created_before"] >= data["created_after"]:
            raise ValidationError("'created_before' must be greater than 'created_after'")


class WorkflowTaskOutSchema(Schema):
    id = String(required=True, validate=Length(equal=32))
    status = String(required=True, validate=OneOf(WorkflowTask.ALL_STATUSES_LIST))
    message = String(required=True, allow_none=True, validate=Length(max=1024))
    resource_id = String(required=True, allow_none=True, validate=Length(max=32))
    resource_type = String(required=True, validate=Length(max=512))
    task_type = String(required=True, validate=Length(max=512))
    previous_task_ids = List(String(validate=Length(equal=32)), required=True, default=[])
    next_task_ids = List(String(validate=Length(equal=32)), required=True, default=[])
    result = Raw(required=True, description="This is a JSON")
    task_metadata = Raw(required=False, allow_none=False)

    @validates_schema
    def validate_result(self, data, **kwargs):
        if not isinstance(data["result"], (list, dict)):
            return ValidationError("'result' is not valid JSON.")


class WorkflowRootWithTasksOutSchema(WorkflowRootOutSchema):
    resource_json = Dict(required=True, allow_none=True)
    associated_tasks = List(Nested("WorkflowTaskOutSchema"), validate=Length(min=1))
    message = String(validate=Length(min=1, max=1000), default='')


class WorkflowRootInfocusTasksOutOutSchema(WorkflowRootOutSchema):
    in_focus_tasks = List(Nested("WorkflowTaskOutSchema"), validate=Length(min=1))
