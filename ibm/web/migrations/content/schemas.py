import logging

from marshmallow import Schema, validates_schema, ValidationError
from marshmallow.fields import Boolean, Integer, List, Nested, String
from marshmallow.validate import OneOf, Regexp

LOGGER = logging.getLogger(__name__)


class NetworkAttachStorageDisksBaseSchema(Schema):
    disk_name = String(required=True)
    size = String(required=True)
    fstype = String(required=True)
    has_partitions = Boolean(required=True)
    mountpoint = String()


class NASDiskSubOfSubPartitions(Schema):
    partitions = Nested(NetworkAttachStorageDisksBaseSchema)


class NetworkAttachStorageDisksSubPartitionSchema(NetworkAttachStorageDisksBaseSchema):
    sub_partitions = Boolean()
    parttype = String(validate=OneOf(["Extended", "Linux"]))
    partitions = Nested(NetworkAttachStorageDisksBaseSchema, exclude=["has_partitions"])


class NetworkAttachStorageDisksSchema(NetworkAttachStorageDisksBaseSchema):
    partitions = Nested(NetworkAttachStorageDisksSubPartitionSchema)

    @validates_schema
    def validate_schema(self, in_data, **kwargs):
        if all([in_data.get("mountpoint"), in_data.get("partitions")]):
            raise ValidationError("Only one of mountpoint or partitons should be provided")
        elif not any([in_data.get("mountpoint"), in_data.get("partitions")]):
            raise ValidationError("One of mountpoint or partitions should be provided")


class NASMigrationMetaDataInSchema(Schema):
    user_id = String(required=True)
    ip = String(
        required=True,
        validate=Regexp(
            r"^(([0-9]|[1-9][0-9]|1[0-9]{2}|2[0-4][0-9]|25[0-5])\.){3}([0-9]|[1-9][0-9]|1[0-9]{2}|2[0-4][0-9]|25[0-5])$"
        )
    )
    hostname = String(required=True)
    migrator_name = String()
    disks = Nested(NetworkAttachStorageDisksSchema, required=True, many=True)
    instance_id = Integer()


class NASMigrationMetaDataOutSchema(Schema):
    cm_meta_data = Nested(NASMigrationMetaDataInSchema, required=True)
    softLayer_vsi_id = Integer(required=True)


class NASMigrationStartInSchema(Schema):
    src_migrator = String(required=True)
    trg_migrator = String(required=True)
    locations = List(String(required=True), required=True)
