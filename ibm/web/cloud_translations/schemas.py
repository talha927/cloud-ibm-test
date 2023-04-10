from apiflask import Schema
from marshmallow.fields import Nested, String
from marshmallow.validate import Length, OneOf


class TranslationInSchema(Schema):
    REF_KEY_TO_RESOURCE_TYPE_MAPPER = {}

    # Information about Source.
    resource = Nested("TranslationResourceInSchema", required=True)
    source_cloud = Nested("TranslationSourceCloudInSchema", required=True)

    # Target Information
    resource_group = Nested("OptionalIDNameSchemaWithoutValidation", required=True,
                            description="Resource Group of IBM Cloud")
    ibm_cloud = Nested("OptionalIDNameSchemaWithoutValidation", required=True, description="ID/Name of IBM Cloud")
    region = Nested("OptionalIDNameSchema", required=True, description="Region of IBM Cloud")


class TranslationResourceInSchema(Schema):
    id = String(required=True, allow_none=False,
                validate=[Length(equal=32)], description="ID of resource to Translate, i.e. vpc_id")
    type = String(required=True, allow_none=False,
                  validate=OneOf(["vpc"]), description="Either the resource(VPC) is backed up or not")


class TranslationSourceCloudInSchema(Schema):
    id = String(required=True, allow_none=False, validate=[Length(equal=32)], description="ID of cloud")
    type = String(required=True, allow_none=False, validate=OneOf(["AWS"]),
                  description="Type of cloud (AWS, GCP, Azure, etc)")
