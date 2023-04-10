from apiflask import Schema
from apiflask.fields import Boolean, DateTime, Dict, Integer, Nested, String
from apiflask.validators import Equal, Length, OneOf, Regexp

from ibm.common.req_resp_schemas.consts import DATE_TIME_FORMAT, IBM_HREF_PATTERN, IBM_RESOURCE_NAME_PATTERN
from ibm.models import IBMDedicatedHostDisk


class IBMDedicatedHostDiskOutSchema(Schema):
    id = String(validate=Length(equal=32), required=True, description="The unique uuid of the dh disk.")
    resource_id = String(required=True, allow_none=False, description="Unique ID on IBM Cloud")
    available = Integer(required=True, description="The remaining space left for instance placement in GB (gigabytes)")
    created_at = \
        DateTime(
            required=True, format=DATE_TIME_FORMAT, allow_none=False,
            description="The date and time that the disk was created"
        )
    href = String(validate=(Regexp(IBM_HREF_PATTERN)), required=True, description="The URL for this disk")
    interface_type = \
        String(
            required=True, allow_none=False,
            validate=(Length(min=1), OneOf(IBMDedicatedHostDisk.ALL_INTERFACE_TYPE_CONSTS)),
            description="The disk interface used for attaching the disk"
        )
    name = \
        String(
            required=True, validate=(Regexp(IBM_RESOURCE_NAME_PATTERN), Length(min=1, max=63)),
            description="The user-defined or system-provided name for this disk"
        )
    provisionable = \
        Boolean(
            required=True,
            description="Indicates whether this dedicated host disk is available for instance disk creation"
        )
    resource_type = \
        String(
            required=True, validate=Equal(IBMDedicatedHostDisk.RESOURCE_TYPE_DEDICATED_HOST_DISK),
            description="The type of resource referenced"
        )
    size = Integer(required=True, description="The size of the disk in GB (gigabytes)")
    supported_instance_interface_types = \
        Dict(
            required=True, allow_none=True,
            description="The instance disk interfaces supported for this dedicated host disk"
        )
    lifecycle_state = \
        String(
            required=True, allow_none=False,
            validate=(Length(min=1), OneOf(IBMDedicatedHostDisk.ALL_LIFECYCLE_STATE_CONSTS)),
            description="The lifecycle state of this dedicated host disk"
        )
    ibm_cloud = Nested("IBMCloudRefOutSchema", required=True)
    region = Nested("IBMRegionRefOutSchema", required=True)
    dedicated_host = Nested("IBMDedicatedHostRefOutSchema", required=True)
    associated_resources = Nested("IBMDedicatedHostDiskAssociatedResourcesOutSchema", required=True)


class IBMDedicatedHostDiskAssociatedResourcesOutSchema(Schema):
    instance_disks = Nested("IBMInstanceDiskRefOutSchema", required=True, many=True)


class IBMDedicatedHostDiskRefOutSchema(IBMDedicatedHostDiskOutSchema):
    class Meta:
        fields = ("id", "name")


class IBMUpdateDedicatedHostDiskSchema(Schema):
    name = String(allow_none=False, validate=(Regexp(IBM_RESOURCE_NAME_PATTERN), Length(min=1, max=63)),
                  description="The user-defined or system-provided name for this disk")
