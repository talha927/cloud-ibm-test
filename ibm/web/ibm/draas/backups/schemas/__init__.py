from apiflask import Schema
from apiflask.fields import Nested, String
from apiflask.validators import Length, OneOf, Regexp
from marshmallow import ValidationError, post_load, validates_schema
from marshmallow.fields import Boolean, DateTime, Dict, List

from ibm.common.req_resp_schemas.consts import DATE_TIME_FORMAT, IBM_UUID_PATTERN
from ibm.common.req_resp_schemas.schemas import IBMResourceQuerySchema
from ibm.models import DisasterRecoveryBackup, IBMKubernetesCluster, IBMVpcNetwork
from ibm.web.ibm.draas.backups.schemas.iks.schemas import DisasterRecoveryIKSBackupInSchema
from ibm.web.ibm.draas.backups.schemas.vpc.schemas import DisasterRecoveryIBMVpcNetworkBackupInSchema
from ibm.web.ibm.draas.policies import DisasterRecoveryPolicyInSchema


class DisasterRecoveryBackupQuerySchema(IBMResourceQuerySchema):
    resource_id = String(
        required=True, allow_none=False, validate=[Length(equal=32), Regexp(IBM_UUID_PATTERN)])


class DisasterRecoveryBlueprintQuerySchema(IBMResourceQuerySchema):
    resource_type = String(required=True, allow_none=False, validate=OneOf(["IBMVpcNetwork", "IKS"]))


class ResourceInformationOutSchema(Schema):
    identifier = String(required=True, allow_none=False, description="Identifier of the backup resource")
    type = String(
        required=True, allow_none=False,
        validate=OneOf([IBMKubernetesCluster.__name__, IBMVpcNetwork.__name__])
    )


class DisasterRecoveryBlueprintOutSchema(Schema):
    id = String(required=True, allow_none=False, validate=[Length(equal=32), Regexp(IBM_UUID_PATTERN)],
                description="unique ID of the BluePrint")
    name = String(required=True, allow_none=False, validate=[Length(min=1, max=255)],
                  description="Name of the Draas backup"
                  )

    resource_type = String(required=True, allow_none=False, validate=OneOf(["IBMVpcNetwork", "IKS"]))
    resource_metadata = Nested("DRaaSIKSRestoreInSchema", required=True, allow_none=False)
    description = String(description="Description for the Backup", default="")
    started_at = String(required=True, allow_none=False)
    created_at = String(required=True, allow_none=False)
    backups = List(Nested("DisasterRecoveryBackupOutSchema", required=True, allow_none=False))
    ibm_cloud = Nested("OptionalIDNameSchemaWithoutValidation", required=True)


class DisasterRecoveryBackupOutSchema(Schema):
    id = String(required=True, allow_none=False, description="Unique ID of the Draas backup")
    name = String(required=True, allow_none=False, description="Name of the Draas Backup")
    status = String(
        required=True, allow_none=False,
        description=f"Backup status will be one of {DisasterRecoveryBackup.DRAAS_BACKUP_STATUSES_LIST}"
    )
    scheduled = Boolean(required=True, allow_none=False)
    started_at = DateTime(required=True, allow_none=False, format=DATE_TIME_FORMAT)
    completed_at = DateTime(required=True, allow_none=False, format=DATE_TIME_FORMAT)
    backup_metadata = Dict(description="Backup Metadata")
    draas_blueprint = Nested("DisasterRecoveryBlueprintOutSchema", required=True)
    is_volume = Boolean(required=True, allow_none=False)


class DisasterRecoveryBackupInSchema(Schema):
    resource_type = String(required=True, allow_none=False, validate=OneOf(["IBMVpcNetwork", "IKS"]))
    description = String(description="Description for the Backup", default="")
    scheduled_policy = Nested(DisasterRecoveryPolicyInSchema, required=False)
    vpc_backup_schema = Nested("DisasterRecoveryIBMVpcNetworkBackupInSchema")
    iks_backup_schema = Nested("DisasterRecoveryIKSBackupInSchema")

    @validates_schema
    def validate_schema(self, data, **kwargs):
        if "vpc_backup_schema" in data and "iks_backup_schema" in data:
            raise ValidationError("Please provide only one schema from ['vpc_backup_schema', 'iks_backup_schema']")
        if not ("vpc_backup_schema" in data or "iks_backup_schema" in data):
            raise ValidationError("Please provide at least one schema from ['vpc_backup_schema', 'iks_backup_schema']")

        if data["resource_type"] == "IKS" and "iks_backup_schema" not in data:
            raise ValidationError("You must provide 'iks_backup_schema' with resource_type 'IKS'")
        elif data["resource_type"] == "IBMVpcNetwork" and "vpc_backup_schema" not in data:
            raise ValidationError("You must provide 'vpc_backup_schema' with resource_type 'IBMVpcNetwork'")

    @post_load
    def combine_data(self, data, **kwargs):
        """
        This method is intended only to combine data in a single object;
        removing `iks_restore_schema` or `vpc_restore_schema` from the data
        and updating the values of the removed keys i.e [`iks_restore_schema`,`vpc_restore_schema`].
        """
        if "iks_backup_schema" in data:
            iks_backup_schema = data["iks_backup_schema"]
            del data["iks_backup_schema"]
            data.update(**iks_backup_schema)

        if "vpc_backup_schema" in data:
            vpc_backup_schema = data["vpc_backup_schema"]
            del data["vpc_backup_schema"]
            data.update(**vpc_backup_schema)

        return data


__all__ = [
    "DisasterRecoveryIKSBackupInSchema", "DisasterRecoveryBackupInSchema", "DisasterRecoveryBackupOutSchema",
    "DisasterRecoveryBlueprintOutSchema", "DisasterRecoveryBlueprintQuerySchema",
    "DisasterRecoveryBackupQuerySchema", "DisasterRecoveryIBMVpcNetworkBackupInSchema"
]
