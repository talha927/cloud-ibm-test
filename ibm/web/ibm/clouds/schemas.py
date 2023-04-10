from apiflask import Schema
from apiflask.fields import Integer, String
from apiflask.validators import Length, OneOf, Regexp
from marshmallow import validates_schema, ValidationError
from marshmallow.fields import Boolean, Nested

from ibm.models import IBMCloud, IBMMonitoringToken


class IBMCloudListQuerySchema(Schema):
    status = String(allow_none=False, validate=OneOf([IBMCloud.STATUS_VALID]))


class IBMDashboardListQuerySchema(Schema):
    cloud_id = id = String(
        allow_none=False,
        validate=[
            Length(equal=32),
            Regexp(r"^([a-z]|[a-z][-a-z0-9]*[a-z0-9]|[0-9][-a-z0-9]*([a-z]|[-a-z][-a-z0-9]*[a-z0-9]))$")
        ],
        description="Unique ID of the cloud account"
    )


class IBMMonitoringTokenOutSchema(Schema):
    token = String(
        required=True, allow_none=False,
        description="Monitoring token for a specific region in specific cloud"
    )
    status = String(required=True, allow_none=False, validate=OneOf(IBMMonitoringToken.ALL_STATUSES))
    region = Nested("OptionalIDNameSchema", required=True, description="The Region of this token")


class IBMCloudOutSettings(Schema):
    cost_optimization_enabled = Boolean(required=True, allow_none=False)
    id = String(
        required=True, allow_none=False,
        validate=[
            Length(equal=32),
            Regexp(r"^([a-z]|[a-z][-a-z0-9]*[a-z0-9]|[0-9][-a-z0-9]*([a-z]|[-a-z][-a-z0-9]*[a-z0-9]))$")
        ],
        description="Unique ID"
    )
    cloud_id = String(
        required=True, allow_none=False,
        validate=[
            Length(equal=32),
            Regexp(r"^([a-z]|[a-z][-a-z0-9]*[a-z0-9]|[0-9][-a-z0-9]*([a-z]|[-a-z][-a-z0-9]*[a-z0-9]))$")
        ],
        description="Unique ID of the cloud account"
    )


class IBMCloudOutSchema(Schema):
    id = String(
        required=True, allow_none=False,
        validate=[
            Length(equal=32),
            Regexp(r"^([a-z]|[a-z][-a-z0-9]*[a-z0-9]|[0-9][-a-z0-9]*([a-z]|[-a-z][-a-z0-9]*[a-z0-9]))$")
        ],
        description="Unique ID of the cloud account"
    )
    name = String(
        required=True, allow_none=False, validate=(Length(min=1, max=255), Regexp(r"^[a-zA-Z0-9_]*$")),
        description="User defined unique name of the cloud account"
    )
    status = String(required=True, allow_none=False, validate=OneOf(IBMCloud.ALL_STATUSES))
    total_cost = Integer(required=True)
    monitoring_tokens = Nested(IBMMonitoringTokenOutSchema, many=True, required=False)
    settings = Nested(IBMCloudOutSettings, required=False)


class IBMCloudRefOutSchema(IBMCloudOutSchema):
    class Meta:
        fields = ("id", "name")


class IBMMonitoringTokenInSchema(Schema):
    token = String(
        required=False, allow_none=False,
        description="Monitoring token for a specific region in specific cloud"
    )
    region = Nested("OptionalIDNameSchema", required=True, description="The Region of this token")


class IBMCloudSettings(Schema):
    cost_optimization_enabled = Boolean(required=True, allow_none=False, description="IBM Cloud Settings")


class IBMCloudInSchema(Schema):
    name = String(
        required=True, allow_none=False, validate=(Length(min=1, max=255)),
        description="User defined unique name of the cloud account"
    )
    api_key = String(
        required=True, allow_none=False, validate=Length(min=1, max=500),
        description="API key from the [following documentation]"
                    "(https://cloud.ibm.com/docs/account?topic=account-userapikey&interface=ui)"
    )
    settings = Nested("IBMCloudSettings", required=False, allow_none=False)


class IBMCloudUpdateSchema(Schema):
    name = String(
        allow_none=False,
        validate=(Length(min=1, max=255)),
        description="User defined unique name of the cloud account"
    )
    api_key = String(
        allow_none=False, validate=Length(min=1, max=500),
        description="API key from the [following documentation]"
                    "(https://cloud.ibm.com/docs/account?topic=account-userapikey&interface=ui)"
    )
    monitoring_tokens = Nested(IBMMonitoringTokenInSchema, many=True, required=False)
    settings = Nested("IBMCloudSettings", required=False, allow_none=False)

    @validates_schema
    def validate_one_of_name_or_api_key(self, data, **kwargs):
        if not (data.get("name") and data.get("api_key")):
            return ValidationError("One of 'name' or 'api_key' is required.")


class DashboardUpdateSchema(Schema):
    id = String(required=True)
    pin_status = Boolean(required=True)
    order = Integer(required=False)


class DashboardUpdateListSchema(Schema):
    items = Nested(DashboardUpdateSchema, many=True, required=True, validate=Length(min=1))


class DashboardOutSchema(Schema):
    id = String(
        required=True, allow_none=False,
        validate=[
            Length(equal=32),
            Regexp(r"^([a-z]|[a-z][-a-z0-9]*[a-z0-9]|[0-9][-a-z0-9]*([a-z]|[-a-z][-a-z0-9]*[a-z0-9]))$")
        ],
        description="Unique ID of the service"
    )
    name = String(
        required=True, allow_none=False, validate=(Length(min=1, max=255), Regexp(r"^[a-zA-Z0-9_]*$")),
        description="Unique name of the cloud service"
    )
    pin_status = Boolean(required=True)
    user_id = String(
        required=True, allow_none=False,
        validate=[
            Length(equal=32),
            Regexp(r"^([a-z]|[a-z][-a-z0-9]*[a-z0-9]|[0-9][-a-z0-9]*([a-z]|[-a-z][-a-z0-9]*[a-z0-9]))$")
        ],
        description="Unique ID of the User"
    )
    count = Integer(required=True)
    order = Integer(required=False)


class DashboardOutListSchema(Schema):
    items = Nested(DashboardOutSchema, many=True, required=True)


class CredentialOutSchema(Schema):
    id = String(validate=Length(equal=32), required=True, description="The unique uuid of the IBM Service Credential.")
    api_key = String(validate=Length(max=500), required=True)
    access_key_id = String(validate=Length(max=255), required=True)
    secret_access_key = String(validate=Length(max=255), required=True)
    ibm_service_credentials = String(validate=Length(max=255), required=True)
