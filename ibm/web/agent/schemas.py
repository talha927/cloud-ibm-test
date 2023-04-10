from apiflask import Schema
from apiflask.fields import String, List, Nested
from apiflask.validators import Length, Regexp

from ibm.common.req_resp_schemas.consts import IBM_UUID_PATTERN


class IBMAgentDiscoverClusterInSchema(Schema):
    agent_id = String(allow_none=False, required=True, description="Unique ID of the agent")
    name = String(required=True, allow_none=False, description="The name for the agent.")


class IBMAgentBackupClusterInSchema(Schema):
    ibm_cloud = Nested("OptionalIDNameSchemaWithoutValidation", required=True)
    region = Nested("OptionalIDNameSchemaWithoutValidation", required=True)
    name = String(required=True, allow_none=False, validate=[Length(min=1, max=255)],
                  description="Name of the OnPrem Agent Cluster backup"
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
        allow_none=False, description="list of namespaces on OnPrem Agent Cluster")
    )


class IBMAgentRestoreClusterInSchema(Schema):
    ibm_cloud = Nested("OptionalIDNameSchemaWithoutValidation", required=True)
    on_prem_cluster_target = Nested("OptionalIDNameSchemaWithoutValidation", required=True)
