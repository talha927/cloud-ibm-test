from apiflask import Schema
from apiflask.fields import String
from apiflask.validators import Length, Regexp
from marshmallow.fields import DateTime

from ibm.common.req_resp_schemas.consts import DATE_TIME_FORMAT, IBM_RESOURCE_NAME_PATTERN, IBM_UUID_PATTERN


class IBMResourceControllerDataQueryParams(Schema):
    cloud_id = String(validate=(Regexp(IBM_UUID_PATTERN), Length(equal=32)), required=False,
                      description="ID of the IBM Cloud.")
    idle_resource_id = String(
        required=True, allow_none=False, validate=[Length(equal=32), Regexp(IBM_UUID_PATTERN)],
        description="Unique ID of the Idle_resource"
    )


class IBMResourceControllerDataOutSchema(Schema):
    crn = String(
        required=True, allow_none=False, description="Unique crn of the Resource"
    )
    created_by = String(
        required=True, allow_none=False, validate=Length(max=255),
        description="Name of resource creator"
    )
    created_at = DateTime(format=DATE_TIME_FORMAT, required=True)
    updated_at = DateTime(format=DATE_TIME_FORMAT, required=True)
    restored_at = DateTime(format=DATE_TIME_FORMAT, required=True)
    name = String(allow_none=False, required=True, validate=(Regexp(IBM_RESOURCE_NAME_PATTERN), Length(min=1, max=63)),
                  description="The unique user-defined name for this resource")
    state = String(required=True, description="State of the key on ibm resource.")
    last_operation = String(required=True, description="State of the key on ibm resource.")
