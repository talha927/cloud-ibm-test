from apiflask import Schema
from apiflask.fields import String
from apiflask.validators import Length, Regexp

from ibm.common.req_resp_schemas.consts import IBM_UUID_PATTERN


class IBMResourceGroupOutSchema(Schema):
    id = String(
        required=True, allow_none=False, validate=[Length(equal=32), Regexp(IBM_UUID_PATTERN)],
        description="Unique ID of the Resource Group"
    )
    name = String(
        required=True, allow_none=False, validate=Length(max=255),
        description="Unique name of the Resource Group"
    )


class IBMResourceGroupRefOutSchema(IBMResourceGroupOutSchema):
    class Meta:
        fields = ("id", "name")
