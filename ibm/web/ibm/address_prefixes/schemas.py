import uuid

from apiflask import Schema
from apiflask.fields import Boolean, DateTime, Nested, String
from marshmallow.validate import Length, Regexp

from ibm.common.req_resp_schemas.consts import DATE_TIME_FORMAT, IBM_HREF_PATTERN, IBM_RESOURCE_NAME_PATTERN, \
    IBM_UUID_PATTERN
from ibm.common.req_resp_schemas.fields import IPv4CIDR
from ibm.common.req_resp_schemas.schemas import IBMZonalResourceListQuerySchema
from ibm.models import IBMVpcNetwork, IBMZone


class IBMVpcResourceListQuerySchema(IBMZonalResourceListQuerySchema):
    vpc_id = String(validate=(Regexp(IBM_UUID_PATTERN), Length(equal=32)), description="ID of the IBM VPC.")


class IBMAddressPrefixResourceSchema(Schema):
    REF_KEY_TO_RESOURCE_TYPE_MAPPER = {
        "zone": IBMZone
    }

    cidr = IPv4CIDR(required=True, description="The CIDR block for this prefix.")
    zone = Nested("OptionalIDNameSchema", required=True)
    is_default = Boolean(
        missing=False,
        description="Indicates whether this is the default prefix for this zone in this VPC."
    )
    name = String(
        required=True, allow_none=False, validate=(Regexp(IBM_RESOURCE_NAME_PATTERN), Length(min=1, max=63)),
        description="The user-defined name for this address prefix. Names must be unique within the VPC the address "
                    "prefix resides in."
    )


class IBMAddressPrefixInSchema(Schema):
    REF_KEY_TO_RESOURCE_TYPE_MAPPER = {
        "vpc": IBMVpcNetwork
    }

    resource_json = Nested("IBMAddressPrefixResourceSchema", required=True)
    ibm_cloud = Nested("OptionalIDNameSchemaWithoutValidation", required=True)
    region = Nested("OptionalIDNameSchema", required=True)
    vpc = Nested("OptionalIDNameSchema", required=True)


class UpdateIBMAddressPrefixesSchema(Schema):
    is_default = Boolean(allow_none=False, default=False,
                         description="Indicates whether this is the default prefix for this zone in this VPC.")
    name = String(required=True, allow_none=False, validate=(Regexp(IBM_RESOURCE_NAME_PATTERN), Length(min=1, max=63)),
                  description="The user-defined name for this address prefix. Names must be unique within the VPC the"
                              " address prefix resides in.")


class IBMAddressPrefixOutSchema(Schema):
    id = String(
        required=True, allow_none=False,
        validate=[
            Length(equal=32),
        ],
        example=uuid.uuid4().hex,
        format="uuid",
        description="The unique identifier for this address prefix."
    )
    resource_id = String(required=True, allow_none=False, description="Unique ID on IBM Cloud")
    cidr = IPv4CIDR(required=True, description="The CIDR block for this prefix.")
    created_at = DateTime(format=DATE_TIME_FORMAT, required=True)
    has_subnets = Boolean(required=True, description="Indicates whether subnets exist with addresses from this prefix.")
    href = String(validate=(Regexp(IBM_HREF_PATTERN)), required=True, description="The URL for this address prefix.")
    is_default = Boolean(required=True, description="Indicates whether this address prefix is default for VPC.")
    name = String(required=True, allow_none=False, validate=[Regexp(IBM_RESOURCE_NAME_PATTERN), Length(min=1, max=63)],
                  example="my-address-prefix-2",
                  description="The user-defined name for this address prefix.")
    status = String(required=True)
    ibm_cloud = Nested("IBMCloudRefOutSchema", required=True)
    region = Nested("IBMRegionRefOutSchema", required=True)
    zone = Nested("IBMZoneRefOutSchema", description="The zone this subnet resides in", required=True)
    associated_resources = Nested("IBMAddressPrefixAssociatedResourcesOutSchema", required=True)


class IBMAddressPrefixAssociatedResourcesOutSchema(Schema):
    vpc = Nested("IBMVpcNetworkRefOutSchema", required=True)
    subnets = Nested("IBMSubnetRefOutSchema", many=True, required=True)


class IBMAddressPrefixRefOutSchema(IBMAddressPrefixOutSchema):
    class Meta:
        fields = ("id", "name", "zone", "cidr", "is_default")
