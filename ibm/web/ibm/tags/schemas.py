import uuid

from marshmallow import Schema
from marshmallow.fields import Nested, String, Float
from marshmallow.validate import Length, OneOf, Regexp

from ibm.common.req_resp_schemas.consts import IBM_UUID_PATTERN


class IBMTagResourceSchema(Schema):
    REF_KEY_TO_RESOURCE_TYPE_MAPPER = {}

    tag_name = String(required=True, description="Label or key value pair for tag on IBM cloud")
    tag_type = String(
        required=True, validate=OneOf(["user", "access", "service"]), default="user",
        description="The Tagging API supports three types of tag: service, user, and access.")
    resource_id = String(description="Resource ID of the resource to attach Tag")
    resource_type = String(required=True, validate=OneOf(["vpc"]), description="Resource Type i.e. vpc, subnet etc")


class IBMTagInSchema(Schema):
    REF_KEY_TO_RESOURCE_TYPE_MAPPER = {}

    resource_json = Nested(IBMTagResourceSchema, required=True)
    ibm_cloud = Nested("OptionalIDNameSchemaWithoutValidation", required=True)


class IBMTagOutSchema(Schema):
    REF_KEY_TO_RESOURCE_TYPE_MAPPER = {}
    id = String(required=True, example=uuid.uuid4().hex, format="uuid",
                description="The unique identifier for this key")
    tag_name = String(required=True, description="Label or key value pair for tag on IBM cloud")
    tag_type = String(
        required=True, validate=OneOf(["user", "access", "service"]), default="user",
        description="The Tagging API supports three types of tag: service, user, and access.")
    resource_id = String(required=True, description="Resource ID of the resource to attach Tag")
    resource_type = String(required=True, validate=OneOf(["vpc"]), description="Resource Type i.e. vpc, subnet etc")
    ibm_cloud = Nested("IBMCloudRefOutSchema", required=True)


class IBMTagRefOutSchema(IBMTagOutSchema):
    class Meta:
        fields = ("id", "tag_name")


class IBMTagsValidateJsonResourceSchema(IBMTagOutSchema):
    class Meta:
        fields = ("tag_name",)


class IBMTagValidateJsonOutSchema(Schema):
    id = String(
        required=True, allow_none=False, validate=[Length(equal=32), Regexp(IBM_UUID_PATTERN)],
        description="Unique ID of the IBM Tag"
    )
    resource_json = Nested(IBMTagsValidateJsonResourceSchema, required=True)


class IBMTagPerCostOutSchema(Schema):
    REF_KEY_TO_RESOURCE_TYPE_MAPPER = {}
    id = String(required=True, example=uuid.uuid4().hex, format="uuid",
                description="The unique identifier for this key")
    name = String(required=True, description="Label or key value pair for tag on IBM cloud")
    cost = Float(required=True, description="The billable charges for all cloud resources used in the account.")
    ibm_cloud = Nested("IBMCloudRefOutSchema", required=True)
