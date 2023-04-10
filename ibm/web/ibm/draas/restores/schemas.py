from apiflask import Schema
from apiflask.fields import Nested, String
from apiflask.validators import Length, Regexp
from marshmallow import post_load, validates_schema, ValidationError
from marshmallow.fields import List
from marshmallow.validate import OneOf

from ibm.common.req_resp_schemas.consts import IBM_UUID_PATTERN
from ibm.common.req_resp_schemas.schemas import IBMResourceQuerySchema
from ibm.models import IBMKubernetesCluster
from ibm.web.ibm.vpcs.schemas import IBMVpcNetworkResourceSchema


class DisasterRecoveryRestoreQuerySchema(IBMResourceQuerySchema):
    resource_id = String(
        required=True, allow_none=False, validate=[Length(equal=32), Regexp(IBM_UUID_PATTERN)])


class RestoreTypeExistingIKS(Schema):
    REF_KEY_TO_RESOURCE_TYPE_MAPPER = {}

    ibm_cloud = Nested("OptionalIDNameSchemaWithoutValidation", required=True)
    ibm_cluster_source = Nested("OptionalIDNameSchemaWithoutValidation", required=False)
    ibm_cluster_target = Nested("OptionalIDNameSchemaWithoutValidation", required=True)


class RestoreTypeNewIKS(Schema):
    REF_KEY_TO_RESOURCE_TYPE_MAPPER = {}

    resource_json = Nested("IBMKubernetesClusterResourceSchema", required=True)
    region = Nested("OptionalIDNameSchemaWithoutValidation", required=True)


class RestoreTypeNewVpc(IBMVpcNetworkResourceSchema):
    REF_KEY_TO_RESOURCE_TYPE_MAPPER = {}

    target_cluster = Nested("IBMKubernetesClusterInSchema")
    address_prefixes = List(Nested("IBMAddressPrefixInSchema"))
    subnets = List(Nested("IBMSubnetInSchema"))
    public_gateways = List(Nested("IBMPublicGatewayInSchema"))
    acls = List(Nested("IBMAclInSchema"))
    security_groups = List(Nested("IBMSecurityGroupInSchema"))


class DisasterRecoveryIKSRestoreInSchema(Schema):
    REF_KEY_TO_RESOURCE_TYPE_MAPPER = {}

    restore_type = String(required=True, validate=OneOf(["TYPE_EXISTING_VPC_NEW_IKS", "TYPE_NEW_VPC_NEW_IKS",
                                                         "TYPE_EXISTING_IKS"]))
    restore_type_existing_iks = Nested("RestoreTypeExistingIKS")
    restore_type_new_iks = Nested("IBMKubernetesClusterInSchema")
    restore_type_new_vpc = Nested("RestoreTypeNewVpc")

    @validates_schema
    def validate_schema(self, data, **kwargs):
        if data["restore_type"] == "TYPE_EXISTING_VPC_NEW_IKS" and "restore_type_new_iks" not in data:
            raise ValidationError("Provide this restore_type_new_iks")

        if data["restore_type"] == "TYPE_EXISTING_IKS" and "restore_type_existing_iks" not in data:
            raise ValidationError("Provide this restore_type_existing_iks")

        if data["restore_type"] == "TYPE_NEW_VPC_NEW_IKS" and "restore_type_new_vpc" not in data:
            raise ValidationError("Provide this restore_type_new_vpc")


class DRaaSIKSRestoreInSchema(Schema):
    REF_KEY_TO_RESOURCE_TYPE_MAPPER = {}

    ibm_cloud = Nested("OptionalIDNameSchemaWithoutValidation", required=True)
    region = Nested("OptionalIDNameSchemaWithoutValidation", required=True)
    vpc = Nested("OptionalIDNameSchemaWithoutValidation")
    resource_group = Nested("OptionalIDNameSchemaWithoutValidation")
    master_kube_version = \
        String(
            description="Kube version of Cluster."
        )
    cluster_type = String(validate=(OneOf(IBMKubernetesCluster.ALL_CLUSTER_TYPES_LIST)),
                          description="Type of cluster on IBM.")
    cos_bucket_id = String(allow_none=False, validate=(Regexp(IBM_UUID_PATTERN), Length(equal=32)),
                           description="ID of the IBM COS Bucket.")
    cloud_object_storage_id = String(allow_none=False, validate=(Regexp(IBM_UUID_PATTERN), Length(equal=32)),
                                     description="ID of the IBM COS.")
    cos_access_keys_id = String(
        allow_none=False, validate=(Regexp(IBM_UUID_PATTERN), Length(equal=32)),
        description="ID of the IBM COS Access Keys."
    )
    resource_json = Nested("IBMKubernetesClusterResourceSchema", required=True)
    backup_id = String(
        allow_none=False, validate=(Regexp(IBM_UUID_PATTERN), Length(equal=32)),
        description="ID of the DRaaS Backup"
    )
    backup_name = String(required=True, description="Backup of Resource")
    draas_restore_type_iks = String(required=True, validate=OneOf(["TYPE_EXISTING_VPC_NEW_IKS", "TYPE_NEW_VPC_NEW_IKS",
                                                                   "TYPE_EXISTING_IKS"]))


class DRaaSClusterValidateJsonOutSchema(Schema):
    id = String(
        required=True, allow_none=False, validate=[Length(equal=32), Regexp(IBM_UUID_PATTERN)],
        description="Unique ID of the IBM IKS"
    )
    resource_json = Nested("IBMKubernetesClusterValidateJsonResourceSchema", required=True)


class DisasterRecoveryIBMVpcNetworkRestoreInSchema(Schema):
    ibm_cloud = Nested("OptionalIDNameSchemaWithoutValidation", required=True)
    region = Nested("OptionalIDNameSchema", required=True)


class DisasterRecoveryRestoreInSchema(Schema):
    resource_type = String(required=True, allow_none=False, validate=OneOf(["IBMVpcNetwork", "IKS"]))

    vpc_restore_schema = Nested(DisasterRecoveryIBMVpcNetworkRestoreInSchema)
    iks_restore_schema = Nested(DisasterRecoveryIKSRestoreInSchema)

    @validates_schema
    def validate_schema(self, data, **kwargs):
        if "iks_restore_schema" in data and "vpc_restore_schema" in data:
            raise ValidationError("Please provide only one schema from ['iks_restore_schema', 'vpc_restore_schema']")
        if not ("iks_restore_schema" in data or "vpc_restore_schema" in data):
            raise ValidationError(
                "Please provide at least one schema from ['iks_restore_schema', 'vpc_restore_schema']")

        if data["resource_type"] == "IKS" and "iks_restore_schema" not in data:
            raise ValidationError("You must provide 'iks_restore_schema' with resource_type 'IKS'")
        elif data["resource_type"] == "IBMVpcNetwork" and "vpc_restore_schema" not in data:
            raise ValidationError("You must provide 'vpc_restore_schema' with resource_type 'IBMVpcNetwork'")

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
            del data["vpc_restore_schema"]
            data.update(**vpc_restore_schema)

        return data


class DisasterRecoverySourceCloudInSchema(Schema):
    cloud_type = String(required=True, allow_none=False, validate=OneOf(["AWS"]))
    id = String(required=True, allow_none=False, validate=[Length(equal=32), Regexp(IBM_UUID_PATTERN)])


class DisasterRecoveryBackupRestoreInSchema(Schema):
    id = String(required=True, allow_none=False, validate=[Length(equal=32), Regexp(IBM_UUID_PATTERN)])


class DisasterRecoverySourceInSchema(Schema):
    cloud = Nested("DisasterRecoverySourceCloudInSchema", required=True)
    backup = Nested("DisasterRecoveryBackupRestoreInSchema", required=True)


class ClusterRestoreInSchema(Schema):
    source = Nested("DisasterRecoverySourceInSchema", required=True)
    ibm_cloud = Nested("OptionalIDNameSchemaWithoutValidation", required=True)
    cluster = Nested("OptionalIDNameSchemaWithoutValidation", required=True)


class AgentClusterRestoreInSchema(Schema):
    source = Nested("DisasterRecoverySourceInSchema", required=True)
    ibm_cloud = Nested("OptionalIDNameSchemaWithoutValidation", required=True)
    cluster = Nested("OptionalIDNameSchemaWithoutValidation", required=True)
    agent_id = String(description="Agent id of the cluster.", required=True)
