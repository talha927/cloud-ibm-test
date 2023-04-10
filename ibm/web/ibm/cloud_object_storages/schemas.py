from apiflask import Schema
from apiflask.fields import Boolean, Nested, String
from apiflask.validators import Length, OneOf, Regexp
from marshmallow import validates_schema, ValidationError

from ibm.common.req_resp_schemas.consts import IBM_RESOURCE_NAME_PATTERN, IBM_UUID_PATTERN
from ibm.common.req_resp_schemas.schemas import IBMRegionalResourceListQuerySchema, IBMResourceQuerySchema
from ibm.models import IBMCOSBucket, IBMServiceCredentialKey, IBMCloudObjectStorage


class IBMCosBucketsListQuerySchema(IBMRegionalResourceListQuerySchema):
    cloud_object_storage_id = String(
        allow_none=False, validate=(Regexp(IBM_UUID_PATTERN), Length(equal=32)),
        description="ID of the IBM COS."
    )
    resiliency = \
        String(validate=OneOf(IBMCOSBucket.ALL_RESILIENCIES), description="Filter on the basis of bucket resiliency")
    is_sorted = Boolean(default=True, descrption="Return data in order with respect to creation date.")


class IBMCosBucketSyncSchema(IBMResourceQuerySchema):
    cloud_object_storage_id = String(
        allow_none=False, validate=(Regexp(IBM_UUID_PATTERN), Length(equal=32)),
        description="ID of the IBM COS."
    )
    region_id = String(
        allow_none=False, required=True, validate=(Regexp(IBM_UUID_PATTERN), Length(equal=32)),
        description="ID of the IBM Region on VPC+."
    )


class IBMCosKeyListQuerySchema(IBMResourceQuerySchema):
    cloud_object_storage_id = String(
        allow_none=False, validate=(Regexp(IBM_UUID_PATTERN), Length(equal=32)),
        description="ID of the IBM COS."
    )
    is_hmac = Boolean(allow_none=False,
                      descrption="Return keys that contain hmac credentials in-case True and vise versa for false.")
    role = String(allow_none=False, validate=OneOf(IBMServiceCredentialKey.ROLES_LIST),
                  descrption="Return keys of the provided role")


class IBMCosOutSchema(Schema):
    id = String(validate=Length(equal=32), required=True, description="The unique uuid of the Storage object.")
    name = String(required=True, allow_none=False, validate=(Regexp(IBM_RESOURCE_NAME_PATTERN), Length(min=1, max=63)),
                  description="The name of the Storage object.")
    crn = String(required=True, description="The crn/id of the Storage object.")
    created_at = String(required=True, description="The creation time of the Storage object")
    updated_at = String(required=True, description="The name of the Storage object")
    migrated = Boolean(required=True)
    locked = Boolean(required=True)
    ibm_cloud = Nested("IBMCloudRefOutSchema", required=True)


class IBMCosBucketOutSchema(Schema):
    id = String(validate=Length(equal=32), required=True, description="The unique uuid of the Storage Bucket.")
    name = String(required=True, allow_none=False, validate=(Regexp(IBM_RESOURCE_NAME_PATTERN), Length(min=1, max=63)),
                  description="The name of the Storage Bucket.")
    created_at = String(required=True, description="The creation time of the Storage Bucket")
    location_constraint = String(required=True)
    type_ = String(data_key="type", required=True, validate=OneOf(IBMCOSBucket.ALL_TYPES))
    resiliency = String(required=True, validate=OneOf(IBMCOSBucket.ALL_RESILIENCIES))
    ibm_cloud = Nested("IBMCloudRefOutSchema", required=True)
    cloud_object_storage = Nested("IBMCosRefOutSchema", required=True)
    regions = Nested("IBMRegionRefOutSchema", many=True, required=True)


class IBMCosBucketResourceSchema(Schema):
    REF_KEY_TO_RESOURCE_TYPE_MAPPER = {
        "cloud_object_storage": IBMCloudObjectStorage,
    }

    name = String(required=True, allow_none=False, validate=(Regexp(IBM_RESOURCE_NAME_PATTERN), Length(min=3, max=63)),
                  description="The name of the COS Bucket, It should not start with cosv1- or account-")
    cloud_object_storage = Nested("OptionalIDNameSchema", required=True)

    @validates_schema
    def validate_one_of_schema(self, data, **kwargs):
        if data["name"].startswith("cosv1-") or data["name"].startswith("account-"):
            raise ValidationError("COS Bucket Name should not start with cosv1- or account-")


class IBMCosBucketInSchema(Schema):
    REF_KEY_TO_RESOURCE_TYPE_MAPPER = {}

    resource_json = Nested("IBMCosBucketResourceSchema", required=True)
    ibm_cloud = Nested("OptionalIDNameSchemaWithoutValidation", required=True)
    region = Nested("OptionalIDNameSchema", required=True)


class IBMCOSKeyOutSchema(Schema):
    id = String(validate=Length(equal=32), required=True, description="The unique uuid of the key.")
    name = String(required=True, allow_none=False, validate=(Regexp(IBM_RESOURCE_NAME_PATTERN), Length(min=1, max=63)),
                  description="The name of the Service Key.")
    created_at = String(required=True, description="The creation time of the COS Key")
    updated_at = String(required=True, description="The updated time of the COS Key")
    is_hmac = Boolean(required=True, description="The key has hmac credentials attached or not.")
    state = String(required=True, description="State of the key on ibm cloud.")
    migrated = Boolean(required=True)
    iam_service_id_crn = String(required=True)
    iam_role_crn = String(required=True)
    role = String(required=True)
    ibm_cloud = Nested("IBMCloudRefOutSchema", required=True)
    cloud_object_storage = Nested("IBMCosRefOutSchema", required=True)


class IBMCosRefOutSchema(IBMCosOutSchema):
    class Meta:
        fields = ("id", "name")


class IBMCosBucketRefOutSchema(IBMCosBucketOutSchema):
    class Meta:
        fields = ("id", "name")


class IBMCosBucketValidateJsonResourceSchema(Schema):
    class Meta:
        fields = ("name",)


class IBMCosBucketValidateJsonOutSchema(Schema):
    id = String(
        required=True, allow_none=False, validate=[Length(equal=32), Regexp(IBM_UUID_PATTERN)],
        description="Unique ID of the IBM COS Bucket"
    )
    resource_json = Nested(IBMCosBucketValidateJsonResourceSchema, required=True)
