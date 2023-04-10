from marshmallow import Schema
from marshmallow.fields import List, Nested, String
from marshmallow.validate import Length, Regexp

from ibm.common.req_resp_schemas.consts import IBM_UUID_PATTERN


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
