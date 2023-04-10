import uuid

from apiflask import Schema
from apiflask.fields import DateTime, List, Nested, String, Dict
from apiflask.validators import OneOf
from marshmallow.validate import Length, Regexp

from ibm.common.req_resp_schemas.consts import DATE_TIME_FORMAT, IBM_RESOURCE_NAME_PATTERN, IBM_UUID_PATTERN
from ibm.models import WorkflowRoot, IBMActivityTracking


class IBMActivityTrackingOutSchema(Schema):
    id = String(
        required=True, allow_none=False,
        validate=[
            Length(equal=32),
        ],
        example=uuid.uuid4().hex,
        format="uuid",
        description="The unique identifier for this activity."
    )
    user = String(required=True, allow_none=False, description="Email of the user performing the activity")
    resource_name = String(
        required=True, allow_none=False, validate=(Regexp(IBM_RESOURCE_NAME_PATTERN), Length(min=1, max=63)),
        description="The user-defined name for this resource. Must be unique"
    )
    resource_type = String(required=True, allow_none=False, description="Type of resource on IBM Cloud")
    activity_type = String(required=True, allow_none=False, description="Type of activity performed on resource")
    started_at = DateTime(format=DATE_TIME_FORMAT, required=True)
    summary = String(required=True, allow_none=False, description="Summary for type of activity performed on resource")
    detailed_summary = Nested("DetailedSummaryOutSchema", required=True)


class DetailedSummaryOutSchema(Schema):
    id = String(required=True, validate=Length(equal=32))
    workflow_name = String(required=True, allow_none=True, validate=Length(max=128))
    resource_type = String(required=True, allow_none=True, validate=Length(max=128))
    workflow_nature = String(required=True, allow_none=True, validate=Length(max=128))
    fe_request_data = Dict(required=True, allow_none=True)
    status = String(required=True, validate=OneOf(WorkflowRoot.ALL_STATUSES_LIST))
    created_at = String(required=True)
    completed_at = String(required=True, allow_none=True)
    previous_root_ids = List(String(validate=Length(equal=32)), required=True, default=[])
    next_root_ids = List(String(validate=Length(equal=32)), required=True, default=[])


class IBMActivityTrackingSearchSchema(Schema):
    cloud_id = String(allow_none=True, validate=(Regexp(IBM_UUID_PATTERN), Length(equal=32)))
    activity_type = String(allow_none=True, validate=OneOf(IBMActivityTracking.ALL_ACTIVITY_TYPES))
    resource_type = String(allow_none=True)
    user = String(allow_none=True)
