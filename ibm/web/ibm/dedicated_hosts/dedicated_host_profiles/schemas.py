from apiflask import Schema
from apiflask.fields import Dict, Nested, String
from apiflask.validators import Length, OneOf, Regexp
from marshmallow.fields import List

from ibm.common.req_resp_schemas.consts import IBM_HREF_PATTERN, IBM_RESOURCE_NAME_PATTERN
from ibm.models import IBMDedicatedHostProfile


class IBMDedicatedHostProfileOutSchema(Schema):
    id = String(validate=Length(equal=32), required=True, description="UUID of the IBMDedicatedHostProfile")
    class_ = \
        String(
            data_key="class", required=True, allow_none=False, validate=Length(min=1),
            description="The product class this dedicated host profile belongs to"
        )
    disks = List(Dict(required=True, allow_none=True, description="Collection of the dedicated host profile's disks"))
    family = \
        String(
            required=True, allow_none=False, validate=(Length(min=1), OneOf(IBMDedicatedHostProfile.ALL_FAMILY_CONSTS)),
            description="The product family this dedicated host profile belongs to"
        )
    href = String(validate=(Regexp(IBM_HREF_PATTERN)), required=True, description="The URL for this dedicated host")
    memory = Dict(required=True, allow_none=True, description="The memory for a dedicated host with this profile")
    name = \
        String(
            allow_none=False, validate=(Regexp(IBM_RESOURCE_NAME_PATTERN), Length(min=1, max=63)),
            description="The globally unique name for this dedicated host profile"
        )
    socket_count = \
        Dict(required=True, allow_none=True, description="The CPU socket count for a dedicated host with this profile")
    vcpu_architecture = \
        Dict(required=True, allow_none=True, description="The VCPU architecture for a dedicated host with this profile")
    vcpu_count = \
        Dict(required=True, allow_none=True, description="The VCPU count for a dedicated host with this profile")
    supported_instance_profiles = Nested("IBMInstanceProfileRefOutSchema", required=True, many=True)
    ibm_cloud = Nested("IBMCloudRefOutSchema", required=True)
    region = Nested("IBMRegionRefOutSchema", required=True)
    associated_resources = Nested("IBMDedicatedHostProfileAssociatedResourcesOutSchema", required=True)


class IBMDedicatedHostProfileAssociatedResourcesOutSchema(Schema):
    dedicated_hosts = Nested("IBMDedicatedHostRefOutSchema", required=True, many=True)


class IBMDedicatedHostProfileRefOutSchema(IBMDedicatedHostProfileOutSchema):
    class Meta:
        fields = ("id", "name")
