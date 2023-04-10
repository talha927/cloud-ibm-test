from apiflask import Schema
from apiflask.fields import Boolean, Nested, String
from apiflask.validators import Length, OneOf, Regexp

from ibm.common.req_resp_schemas.consts import IBM_UUID_PATTERN
from ibm.common.req_resp_schemas.schemas import IBMResourceQuerySchema
from ibm.models import IBMRegion, IBMZone


class IBMRegionListQueryParams(IBMResourceQuerySchema):
    with_zones = Boolean(
        truthy={"True", "true"}, falsy={"False", "false"},
        description="Whether or not to return zones with regions"
    )


class IBMRegionGetQueryParams(Schema):
    with_zones = Boolean(
        truthy={"True", "true"}, falsy={"False", "false"},
        description="Whether or not to return zones with regions"
    )


class IBMRegionOutSchema(Schema):
    id = String(
        required=True, allow_none=False, validate=[Length(equal=32), Regexp(IBM_UUID_PATTERN)],
        description="Unique ID of the Region"
    )
    name = String(
        required=True, allow_none=False, validate=Length(max=255),
        description="Unique name of the Region"
    )
    status = String(
        required=True, allow_none=False, validate=OneOf(IBMRegion.ALL_STATUSES_LIST),
        description="Current status of the Region"
    )
    zones = Nested(
        "IBMZoneOutSchema", only=("id", "name", "status"), many=True,
        description="Key not returned in response if query param `with_zones` is not sent or is set to False"
    )


class IBMRegionRefOutSchema(IBMRegionOutSchema):
    class Meta:
        fields = ("id", "name")


class IBMZoneListQueryParams(IBMResourceQuerySchema):
    region_id = String(
        allow_none=False, validate=[Length(equal=32), Regexp(IBM_UUID_PATTERN)],
        description="Unique ID of the Region"
    )


class IBMZoneOutSchema(Schema):
    id = String(
        required=True, allow_none=False, validate=[Length(equal=32), Regexp(IBM_UUID_PATTERN)],
        description="Unique ID of the Zone"
    )
    name = String(
        required=True, allow_none=False, validate=Length(max=255),
        description="Unique name of the Zone"
    )
    status = String(
        required=True, allow_none=False, validate=OneOf(IBMZone.ALL_STATUSES_LIST),
        description="Current status of the Zone"
    )
    region = Nested("IBMRegionRefOutSchema", required=True)


class IBMZoneRefOutSchema(IBMZoneOutSchema):
    class Meta:
        fields = ("id", "name")
