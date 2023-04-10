from apiflask import Schema
from apiflask.fields import Dict, List, Nested, String
from apiflask.validators import Length, OneOf, Regexp
from marshmallow import post_load

from ibm.common.req_resp_schemas.consts import IBM_UUID_PATTERN
from ibm.common.req_resp_schemas.schemas import IBMResourceQuerySchema
from ibm.models.ibm_draas.draas_models import DisasterRecoveryBackup


class DisasterRecoveryBackupQuerySchema(IBMResourceQuerySchema):
    resource_id = String(
        required=True, allow_none=False, validate=[Length(equal=32), Regexp(IBM_UUID_PATTERN)])


class DisasterRecoveryIKSBackupInSchema(Schema):
    REF_KEY_TO_RESOURCE_TYPE_MAPPER = {}

    ibm_cloud = Nested("OptionalIDNameSchemaWithoutValidation", required=True)
    resource_id = String(required=True, description="ID of `IKS`")
    region = Nested("OptionalIDNameSchemaWithoutValidation", required=True)
    name = String(required=True, allow_none=False, validate=[Length(min=1, max=255)],
                  description="Name of the Draas backup"
                  )
    cos_bucket_id = String(
        allow_none=False, validate=(Regexp(IBM_UUID_PATTERN), Length(equal=32)),
        description="ID of the IBM COS Bucket."
    )
    cloud_object_storage_id = String(
        allow_none=False, validate=(Regexp(IBM_UUID_PATTERN), Length(equal=32)),
        description="ID of the IBM COS."
    )
    cos_access_keys_id = String(
        allow_none=False, validate=(Regexp(IBM_UUID_PATTERN), Length(equal=32)),
        description="ID of the IBM COS Access Keys."
    )
    namespaces = List(String(
        allow_none=False, description="list of namespaces on cluster"

    ))


class DisasterRecoveryBackupOutSchema(Schema):
    id = String(required=True, allow_none=False, validate=[Length(equal=32), Regexp(IBM_UUID_PATTERN)],
                description="unique ID of the Draas bakcup")

    completed_at = String(required=True, allow_none=False)

    name = String(required=True, allow_none=False, validate=[Length(min=1, max=255)],
                  description="Name of the Draas backup"
                  )
    status = String(required=True, allow_none=False, validate=OneOf(DisasterRecoveryBackup.DRAAS_BACKUP_STATUS),
                    description=f"Backup status will be one of {DisasterRecoveryBackup.DRAAS_BACKUP_STATUS}")
    backup_metadata = Dict(required=True, allow_none=False)

    disaster_recovery_id = String(required=True, allow_none=False,
                                  validate=[Length(equal=32), Regexp(IBM_UUID_PATTERN)],
                                  description="id of disaster recovery")


class DisasterRecoveryBlueprintQuerySchema(IBMResourceQuerySchema):
    resource_type = String(required=True, allow_none=False, validate=OneOf(["IBMVpcNetwork", "IKS"]))


class DisasterRecoveryBlueprintOutSchema(Schema):
    id = String(required=True, allow_none=False, validate=[Length(equal=32), Regexp(IBM_UUID_PATTERN)],
                description="unique ID of the BluePrint")
    name = String(required=True, allow_none=False, validate=[Length(min=1, max=255)],
                  description="Name of the Draas backup"
                  )

    resource_type = String(required=True, allow_none=False, validate=OneOf(["IBMVpcNetwork", "IKS"]))
    resource_metadata = Nested("DRaaSIKSRestoreInSchema", required=True, allow_none=False)
    started_at = String(required=True, allow_none=False)
    created_at = String(required=True, allow_none=False)
    backups = List(Nested(DisasterRecoveryBackupOutSchema, required=True, allow_none=False))
    ibm_cloud = Nested("OptionalIDNameSchemaWithoutValidation", required=True)


class DisasterRecoveryIksBlueprintListOutSchema(DisasterRecoveryBlueprintOutSchema):
    class Meta:
        exclude = ("backups", "resource_metadata")


class DisasterRecoveryBackupInSchema(Schema):
    resource_type = String(required=True, allow_none=False, validate=OneOf(["IBMVpcNetwork", "IKS"]))

    iks_backup_schema = Nested("DisasterRecoveryIKSBackupInSchema")

    @post_load
    def combine_data(self, data, **kwargs):
        """
        This method is intended only to combine data in a single object;
        removing `iks_restore_schema` or `vpc_restore_schema` from the data
        and updating the values of the removed keys i.e [`iks_restore_schema`,`vpc_restore_schema`].
        """
        if "iks_restore_schema" in data:
            iks_restore_schema = data["iks_restore_schema"]
            del data["iks_restore_schema"]
            data.update(**iks_restore_schema)

        if "vpc_restore_schema" in data:
            vpc_restore_schema = data["vpc_restore_schema"]
            del data["iks_restore_schema"]
            data.update(**vpc_restore_schema)

        return data
