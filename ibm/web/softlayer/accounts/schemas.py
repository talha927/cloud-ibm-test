from apiflask import Schema
from apiflask.fields import String
from apiflask.validators import Length, OneOf
from marshmallow import validates_schema, ValidationError

from ibm.models import SoftlayerCloud


class SoftLayerAccountInSchema(Schema):
    name = String(required=True, description="User defined name for his/her account identification")
    username = String(required=True, description="API username provided by Softlayer")
    api_key = String(
        required=True, validate=Length(min=10),
        description="api key for softlayer apis authentication"
    )


class SoftLayerAccountUpdateSchema(Schema):
    name = String(description="User defined name for his/her account identification")
    username = String(description="API username provided by Softlayer")
    api_key = String(
        validate=Length(min=10),
        description="api key for softlayer apis authentication"
    )

    @validates_schema
    def validate_schema(self, in_data, **kwargs):
        if not any([in_data.get("api_key"), in_data.get("name"), in_data.get("username")]):
            raise ValidationError("One of the field must be provided for update")


class SoftLayerAccountOutSchema(Schema):
    id = String(validate=Length(equal=32), required=True, description="The unique identifier for this cloud")
    name = String(required=True, description="User defined name for his/her account identification")
    username = String(required=True, description="API username provided by Softlayer")
    status = String(required=True, validate=OneOf(SoftlayerCloud.ALL_STATUSES))


class SoftLayerAccountRefOutSchema(SoftLayerAccountOutSchema):
    class Meta:
        fields = ("id", "name")


class SoftLayerAccountQuerySchema(Schema):
    status = String(validate=OneOf(SoftlayerCloud.ALL_STATUSES))
