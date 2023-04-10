import uuid

from marshmallow import Schema
from marshmallow.fields import DateTime, Integer, Nested, String
from marshmallow.validate import Length, OneOf, Range, Regexp

from ibm.common.req_resp_schemas.consts import DATE_TIME_FORMAT, IBM_HREF_PATTERN, IBM_RESOURCE_NAME_PATTERN
from ibm.models import IBMInstanceDisk


class IBMInstanceDiskOutSchema(Schema):
    id = \
        String(required=True, example=uuid.uuid4().hex, format="uuid", description="The unique identifier for this key")
    name = \
        String(
            required=True, allow_none=False, validate=[Regexp(IBM_RESOURCE_NAME_PATTERN), Length(min=1, max=63)],
            example="instance-disk-1", description="The unique user-defined name for this disk."
        )
    resource_id = String(required=True, allow_none=False, description="Unique ID on IBM Cloud")
    interface_type = String(required=True, validate=OneOf(IBMInstanceDisk.ALL_INTERFACE_TYPES_LIST))
    created_at = \
        DateTime(
            required=True, allow_none=False, validate=Regexp(DATE_TIME_FORMAT),
            description="The date and time this disk was created"
        )
    size = \
        Integer(
            required=True, allow_none=False, validate=Range(min=1, max=100000),
            description="The size of the disk in GB (gigabytes)"
        )
    href = \
        String(required=True, allow_none=False, description="The URL for this disk", validate=Regexp(IBM_HREF_PATTERN))
    resource_type = String(required=True, validate=OneOf(IBMInstanceDisk.ALL_RESOURCE_TYPES_LIST))
    dedicated_host_disk = Nested("IBMDedicatedHostDiskRefOutSchema", required=True)
    instance = Nested("IBMInstanceRefOutSchema", required=True)


class IBMInstanceDiskRefOutSchema(IBMInstanceDiskOutSchema):
    class Meta:
        fields = ("id", "name")


class IBMInstanceDiskUpdateSchema(Schema):
    name = String(required=True, allow_none=False,
                  validate=[Regexp(IBM_RESOURCE_NAME_PATTERN), Length(min=1, max=63)],
                  example="disk-1",
                  description="The unique user-defined name for disk.")
