from marshmallow import Schema
from marshmallow.fields import DateTime, Nested, String
from marshmallow.validate import Length, OneOf, Regexp

from ibm.common.req_resp_schemas.consts import DATE_TIME_FORMAT, IBM_RESOURCE_NAME_PATTERN, IBM_UUID_PATTERN
from ibm.models import IBMPlacementGroup, IBMResourceGroup


class IBMPlacementGroupResourceSchema(Schema):
    REF_KEY_TO_RESOURCE_TYPE_MAPPER = {
        "resource_group": IBMResourceGroup,
    }

    strategy = String(
        required=True,
        validate=OneOf(IBMPlacementGroup.ALL_STRATEGY_LIST),
        description="The strategy for this placement group \n\n"
                    "- `host_spread`: place on different compute hosts \n\n"
                    "- `power_spread`: place on compute hosts that use different power sources"
    )
    name = String(required=True, validate=(Length(min=1, max=63), Regexp(IBM_RESOURCE_NAME_PATTERN)))
    resource_group = Nested(
        "OptionalIDNameSchemaWithoutValidation",
        description="Either 'id' or 'name' should be provided."
    )


class IBMPlacementGroupInSchema(Schema):
    REF_KEY_TO_RESOURCE_TYPE_MAPPER = {}

    resource_json = Nested(IBMPlacementGroupResourceSchema, required=True)
    ibm_cloud = Nested("OptionalIDNameSchemaWithoutValidation", required=True)
    region = Nested("OptionalIDNameSchema", required=True)


class IBMPlacementGroupOutSchema(Schema):
    id = String(required=True, description="Unique ID of the IBM Placement Group")
    resource_id = String(required=True, description="Unique ID of the IBM Placement Group on IBM Cloud")
    name = String(required=True, description="Unique name of the IBM Placement Group")
    resource_group = Nested("IBMResourceGroupRefOutSchema", required=True)
    region = Nested("IBMRegionRefOutSchema", required=True)
    ibm_cloud = Nested("IBMCloudRefOutSchema", required=True)
    strategy = String(
        required=True,
        description="The strategy for this placement group \n\n"
                    "- `host_spread`: place on different compute hosts \n\n"
                    "- `power_spread`: place on compute hosts that use different power sources"
    )
    created_at = DateTime(required=True, allow_none=False, format=DATE_TIME_FORMAT)
    lifecycle_state = String(required=True, validate=OneOf(IBMPlacementGroup.ALL_LIFECYCLE_STATE_LIST))
    status = String(required=True)
    resource_type = String(required=True, validate=OneOf(IBMPlacementGroup.ALL_RESOURCE_TYPE_LIST))


class IBMPlacementGroupRefOutSchema(IBMPlacementGroupOutSchema):
    class Meta:
        fields = ("id", "name")


class IBMPlacementGroupValidateJsonResourceSchema(Schema):
    class Meta:
        fields = ("name",)


class IBMPlacementGroupValidateJsonOutSchema(Schema):
    id = String(
        required=True, allow_none=False, validate=[Length(equal=32), Regexp(IBM_UUID_PATTERN)],
        description="Unique ID of the IBM Placement Group"
    )
    resource_json = Nested(IBMPlacementGroupValidateJsonResourceSchema, required=True)
