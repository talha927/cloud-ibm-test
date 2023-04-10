import uuid

from apiflask import Schema
from apiflask.fields import Dict, Integer, List, Nested, String
from apiflask.validators import Length, Regexp
from marshmallow.validate import OneOf

from ibm.common.req_resp_schemas.consts import IBM_HREF_PATTERN, IBM_UUID_PATTERN
from ibm.common.req_resp_schemas.schemas import IBMRegionalResourceListQuerySchema
from ibm.models import IBMInstanceProfile


def get_type_value_schema(value_type):
    assert value_type in [String, Integer]

    class IBMInstanceProfileUtilSchema(Schema):
        type = String(required=True, description="The type for this profile field")
        value = value_type(description="The value for this profile field")

    return IBMInstanceProfileUtilSchema


class AddDefaultSchema(get_type_value_schema(value_type=String)):
    default = String(required=True)


class ProfileDiskSchema(Schema):
    class SupportedInterfaceTypesSchema(Schema):
        type_ = String(data_key="type", required=True)
        values = List(String(required=True), required=True)
        default = String(required=True)

    quantity = Dict(required=True)
    size = Dict(required=True)
    supported_interface_types = Nested("SupportedInterfaceTypesSchema", required=True)


class IBMInstanceProfileOutSchema(Schema):
    class VCPUArchitectureSchema(Schema):
        type_ = String(data_key="type", required=True)
        value = String(required=True)
        default = String(required=True)

    class OSArchitectureSchema(Schema):
        type_ = String(data_key="type", required=True)
        values = List(String(required=True), required=True)
        default = String(required=True)

    class GPUModelSchema(Schema):
        type_ = String(data_key="type", required=True)
        values = List(String(required=True), required=True)

    class GPUManufacturerSchema(Schema):
        type_ = String(data_key="type", required=True)
        values = List(String(required=True), required=True)

    id = \
        String(
            required=True, allow_none=False, example=uuid.uuid4().hex,
            validate=(Regexp(IBM_UUID_PATTERN), Length(equal=32))
        )
    name = \
        String(
            required=True, allow_none=False,
            validate=(Regexp("^([a-z]|[a-z][-a-z0-9]*[a-z0-9]|[0-9][-a-z0-9]*([a-z]|[-a-z][-a-z0-9]*[a-z0-9]))$")),
            description="Unique name of the Instance Profile", example="bc1-4x16"
        )
    family = String(example="balanced")
    # TODO: This will fail in case of bandwidth if it is not fixed type. Changing it to Dict for now until we can
    #  figure out OneOf Schemas
    # bandwidth = Nested(get_type_value_schema(value_type=Integer), required=True)
    bandwidth = \
        Dict(
            required=True,
            description="For now this will mostly have `type` and `value` key where `type` will be `fixed` and `value` "
                        "will be an integer"
        )
    vcpu_architecture = Nested("VCPUArchitectureSchema", required=True)
    # TODO: This will fail in case of vcpu_count if it is not fixed type. Changing it to Dict for now until we can
    #  figure out OneOf Schemas
    # vcpu_count = Nested(get_type_value_schema(value_type=Integer), required=True)
    vcpu_count = \
        Dict(
            required=True,
            description="For now this will mostly have `type` and `value` key where `type` will be `fixed` and `value` "
                        "will be an integer"
        )
    href = String(required=True, validate=Regexp(IBM_HREF_PATTERN))
    # TODO: This will fail in case of memory if it is not fixed type. Changing it to Dict for now until we can
    #  figure out OneOf Schemas
    # memory = Nested(get_type_value_schema(value_type=Integer), required=True)
    memory = \
        Dict(
            required=True,
            description="For now this will mostly have `type` and `value` key where `type` will be `fixed` and `value` "
                        "will be an integer"
        )
    os_architecture = Nested("OSArchitectureSchema", required=True)
    # TODO: This will fail in case of port_speed if it is not fixed type. Changing it to Dict for now until we can
    #  figure out OneOf Schemas
    # port_speed = Nested(get_type_value_schema(value_type=Integer), required=True)
    port_speed = \
        Dict(
            required=True,
            description="For now this will mostly have `type` and `value` key where `type` will be `fixed` and `value` "
                        "will be an integer"
        )
    disks = Nested("ProfileDiskSchema", required=True, many=True)
    gpu_model = Nested("GPUModelSchema")
    # TODO: This will fail in case of gpu_count if it is not fixed type. Changing it to Dict for now until we can
    #  figure out OneOf Schemas
    # gpu_count = Nested(get_type_value_schema(value_type=String))
    gpu_count = \
        Dict(
            description="For now this will mostly have `type` and `value` key where `type` will be `fixed` and `value` "
                        "will be an integer"
        )
    # TODO: This will fail in case of gpu_memory if it is not fixed type. Changing it to Dict for now until we can
    #  figure out OneOf Schemas
    # gpu_memory = Nested(get_type_value_schema(value_type=String))
    gpu_memory = \
        Dict(
            description="For now this will mostly have `type` and `value` key where `type` will be `fixed` and `value` "
                        "will be an integer"
        )
    gpu_manufacturer = Nested("GPUManufacturerSchema")
    # TODO: This will fail in case of total_volume_bandwidth if it is not fixed type. Changing it to Dict for now until
    #  we can figure out OneOf Schemas
    # total_volume_bandwidth = Nested(get_type_value_schema(value_type=Integer), required=True)
    total_volume_bandwidth = \
        Dict(
            description="For now this will mostly have `type` and `value` key where `type` will be `fixed` and `value` "
                        "will be an integer"
        )
    ibm_cloud = Nested("IBMCloudRefOutSchema", required=True)
    region = Nested("IBMRegionRefOutSchema", required=True)


class IBMInstanceProfileRefOutSchema(IBMInstanceProfileOutSchema):
    class Meta:
        fields = ("id", "name")


class IBMInstanceProfileValidateJsonResourceSchema(IBMInstanceProfileOutSchema):
    class Meta:
        fields = ("name", "family", "os_architecture")


class IBMInstanceProfileValidateJsonOutSchema(Schema):
    id = String(
        required=True, allow_none=False, validate=[Length(equal=32), Regexp(IBM_UUID_PATTERN)],
        description="Unique ID of the IBM Instance Profile"
    )
    resource_json = Nested(IBMInstanceProfileValidateJsonResourceSchema, required=True)


class IBMInstanceProfileQuerySchema(IBMRegionalResourceListQuerySchema):
    family = String(required=False, example="balanced", validate=OneOf(IBMInstanceProfile.ALL_FAMILIES))
    os_architecture = String(required=False, example="amd64")


class IBMInstanceProfileFamilyOutSchema(Schema):
    families = List(
        String(required=True, example="balanced", validate=OneOf(IBMInstanceProfile.ALL_FAMILIES)),
        required=True
    )
