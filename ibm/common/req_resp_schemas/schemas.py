import uuid

from apiflask import Schema
from apiflask.fields import Boolean, Dict, Integer, List, Nested, String
from apiflask.validators import Length, OneOf, Range, Regexp
from marshmallow import EXCLUDE, validates_schema, ValidationError

from config import PaginationConfig
from ibm.models import IBMDedicatedHostProfile, WorkflowRoot
from .consts import IBM_RESOURCE_NAME_PATTERN, IBM_UUID_PATTERN


class PaginationQuerySchema(Schema):
    page = Integer(missing=1)
    per_page = Integer(
        missing=PaginationConfig.DEFAULT_ITEMS_PER_PAGE, validate=Range(1, PaginationConfig.MAX_ITEMS_PER_PAGE)
    )


def get_pagination_schema(schema):
    class PaginatedResponseSchema(Schema):
        items = Nested(schema, many=True, dump_only=True, required=True)
        previous_page = Integer(required=True, description="Previous page number")
        next_page = Integer(required=True, description="Next page number")
        total_pages = Integer(required=True, description="Total pages")

    return PaginatedResponseSchema


class WorkflowRootOutSchema(Schema):
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


class IBMResourceRefSchema(Schema):
    id = String(required=True, allow_none=False, example=uuid.uuid4().hex,
                validate=(Regexp(IBM_UUID_PATTERN), Length(equal=32)))


class IBMResourceOptionalRefSchema(Schema):
    id = String(allow_none=False, example=uuid.uuid4().hex, validate=(Regexp(IBM_UUID_PATTERN), Length(equal=32)))


class IBMResourceQuerySchema(Schema):
    cloud_id = String(required=True, allow_none=False, validate=(Regexp(IBM_UUID_PATTERN), Length(equal=32)))


class IBMVpcQuerySchema(Schema):
    vpc_id = String(allow_none=False, validate=(Regexp(IBM_UUID_PATTERN), Length(equal=32)))


class IBMVpnQueryParamSchema(Schema):
    connection_id = String(required=False, allow_none=False, validate=(Regexp(IBM_UUID_PATTERN), Length(equal=32)))
    vpn_gateway_id = String(required=False, allow_none=False, validate=(Regexp(IBM_UUID_PATTERN), Length(equal=32)))
    ike_policy_id = String(required=False, allow_none=False, validate=(Regexp(IBM_UUID_PATTERN), Length(equal=32)))
    ipsec_policy_id = String(required=False, allow_none=False, validate=(Regexp(IBM_UUID_PATTERN), Length(equal=32)))


class IBMResourceRegionOptionalQuerySchema(Schema):
    region = String(required=False, allow_none=False, description="Name of the region IBM is supporting",
                    example="eu-de")


class IBMRegionalResourceListQuerySchema(IBMResourceQuerySchema):
    region_id = String(
        allow_none=False, validate=(Regexp(IBM_UUID_PATTERN), Length(equal=32)),
        description="ID of the IBM Region on VPC+."
    )


class IBMRegionalResourceRequiredListQuerySchema(IBMResourceQuerySchema):
    region_id = String(
        allow_none=False, required=True, validate=(Regexp(IBM_UUID_PATTERN), Length(equal=32)),
        description="ID of the IBM Region on VPC+."
    )


class IBMInstanceQuerySchema(IBMRegionalResourceListQuerySchema):
    instance_id = String(required=False, allow_none=False, validate=(Regexp(IBM_UUID_PATTERN), Length(equal=32)))


class IBMInstanceResourceQuerySchema(IBMResourceQuerySchema):
    subnet_id = String(required=False, allow_none=False, validate=(Regexp(IBM_UUID_PATTERN), Length(equal=32)))
    instance_id = String(required=False, allow_none=False, validate=(Regexp(IBM_UUID_PATTERN), Length(equal=32)))


class IBMZonalResourceListQuerySchema(IBMRegionalResourceListQuerySchema):
    zone_id = String(
        allow_none=False, validate=(Regexp(IBM_UUID_PATTERN), Length(equal=32)),
        description="ID of the IBM Zone on VPC+."
    )


class IBMResourceRegionQuerySchema(Schema):
    region = String(required=True, allow_none=False, description="Name of the region IBM is supporting",
                    example="eu-de")


class OptionalIDNameSchema(Schema):
    id = String(
        allow_none=False, validate=(Regexp(IBM_UUID_PATTERN), Length(equal=32)),
        description="ID of the resource on VPC+."
    )
    name = String(
        validate=(Length(min=1, max=63), Regexp(IBM_RESOURCE_NAME_PATTERN)),
        description="Name of the resource on IBM Cloud."
    )
    zones = Nested("IBMZoneOutSchema", only=("id", "name", "status"), many=True)

    class Meta:
        unknown = EXCLUDE

    @validates_schema
    def validate_oneof(self, data, **kwargs):
        if not (data.get("id") or data.get("name")):
            raise ValidationError("Either both or one of '['id', 'name']' should be provided.")


class OptionalIDNameSchemaWithoutValidation(Schema):
    id = String(
        allow_none=False, validate=(Regexp(IBM_UUID_PATTERN), Length(equal=32)),
        description="ID of the resource on VPC+."
    )
    name = String(
        description="Name of the resource on IBM Cloud."
    )


class IBMVPCRegionalResourceListQuerySchema(IBMRegionalResourceListQuerySchema):
    vpc_id = String(
        allow_none=False, validate=(Regexp(IBM_UUID_PATTERN), Length(equal=32)),
        description="ID of the VPC on VPC+."
    )


class IBMSubnetZonalResourceListQuerySchema(IBMZonalResourceListQuerySchema):
    vpc_id = String(
        allow_none=False, validate=(Regexp(IBM_UUID_PATTERN), Length(equal=32)),
        description="ID of the VPC on VPC+."
    )
    subnet_id = String(
        allow_none=False, validate=(Regexp(IBM_UUID_PATTERN), Length(equal=32)),
        description="ID of the Subnet on VPC+."
    )


class IBMDedicatedHostProfileListQuerySchema(IBMRegionalResourceListQuerySchema):
    family = \
        String(
            allow_none=False, validate=(Length(min=1), OneOf(IBMDedicatedHostProfile.ALL_FAMILY_CONSTS)),
            description="The product family this dedicated host profile belongs to"
        )
    memory = \
        String(
            allow_none=False, validate=(Length(min=1)),
            description="The memory of this dedicated host profile"
        )


class IBMDedicatedHostGroupListQuerySchema(IBMZonalResourceListQuerySchema):
    dh_profile_id = String(
        allow_none=False, validate=(Regexp(IBM_UUID_PATTERN), Length(equal=32)),
        description="The ID for the Dedicated Host Profile"
    )


class IBMVolumesListQuerySchema(IBMZonalResourceListQuerySchema):
    images_source_volume = Boolean(description="To filter out the source volumes which can be used for image creation")
    instance_attached = Boolean(description="To filter out the source volumes which can be attached to an instance")
