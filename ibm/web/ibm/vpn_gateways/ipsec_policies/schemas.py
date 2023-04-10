from apiflask import Schema
from apiflask.fields import DateTime, String
from apiflask.validators import OneOf, Range, Regexp
from marshmallow.fields import Integer, Nested
from marshmallow.validate import Length

from ibm.common.req_resp_schemas.consts import DATE_TIME_FORMAT, IBM_HREF_PATTERN, IBM_RESOURCE_NAME_PATTERN, \
    IBM_UUID_PATTERN
from ibm.models import IBMIPSecPolicy, IBMResourceGroup


class IBMIPSecPoliciesResourceSchema(Schema):
    REF_KEY_TO_RESOURCE_TYPE_MAPPER = {
        "resource_group": IBMResourceGroup,
    }
    authentication_algorithm = String(required=True, validate=OneOf(IBMIPSecPolicy.ALL_AUTHENTICATION_ALGORITHMS_LIST),
                                      description="The Authentication algorithm.")
    encryption_algorithm = String(required=True, validate=OneOf(IBMIPSecPolicy.ALL_ENCRYPTION_ALGORITHMS_LIST),
                                  description="The encryption algorithm.")
    pfs = String(required=True, validate=OneOf(IBMIPSecPolicy.ALL_PFS_LIST),
                 description="Perfect Forward Secrecy.")
    key_lifetime = Integer(validate=Range(min=1800, max=86400),
                           description="The key lifetime in seconds")
    name = String(required=True, allow_none=False, validate=(Regexp(IBM_RESOURCE_NAME_PATTERN), Length(min=1, max=63)),
                  description="The user-defined name for this IPsec policy.")
    resource_group = Nested("OptionalIDNameSchemaWithoutValidation")


class IBMIPSecPoliciesInSchema(Schema):
    REF_KEY_TO_RESOURCE_TYPE_MAPPER = {}

    resource_json = Nested(IBMIPSecPoliciesResourceSchema, required=True)
    ibm_cloud = Nested("OptionalIDNameSchemaWithoutValidation", required=True)
    region = Nested("OptionalIDNameSchema", required=True)


class UpdateIBMIPSecPoliciesSchema(Schema):
    authentication_algorithm = String(validate=OneOf(IBMIPSecPolicy.ALL_AUTHENTICATION_ALGORITHMS_LIST),
                                      description="The Authentication algorithm.")
    encryption_algorithm = String(validate=OneOf(IBMIPSecPolicy.ALL_ENCRYPTION_ALGORITHMS_LIST),
                                  description="The encryption algorithm.")
    key_lifetime = Integer(validate=Range(min=1800, max=86400),
                           description="The key lifetime in seconds")
    pfs = String(validate=OneOf(IBMIPSecPolicy.ALL_PFS_LIST),
                 description="Perfect Forward Secrecy.")
    name = String(required=True, allow_none=False, validate=(Regexp(IBM_RESOURCE_NAME_PATTERN), Length(min=1, max=63)),
                  description="The user-defined name for this IPsec policy.")
    ibm_cloud = Nested("IBMCloudOutSchema", only=("id",), required=True)


class IBMIPSecPolicyOutSchema(Schema):
    id = String(validate=Length(equal=32), required=True, description="The unique uuid of the IpSec Policy.")
    authentication_algorithm = String(required=True, validate=OneOf(IBMIPSecPolicy.ALL_AUTHENTICATION_ALGORITHMS_LIST),
                                      description="The Authentication algorithm.")
    encryption_algorithm = String(required=True, validate=OneOf(IBMIPSecPolicy.ALL_ENCRYPTION_ALGORITHMS_LIST),
                                  description="The encryption algorithm.")
    pfs = String(required=True, validate=OneOf(IBMIPSecPolicy.ALL_PFS_LIST),
                 description="Perfect Forward Secrecy.")
    key_lifetime = Integer(validate=Range(min=1800, max=86400),
                           description="The key lifetime in seconds")
    name = String(required=True, allow_none=False, validate=(Regexp(IBM_RESOURCE_NAME_PATTERN), Length(min=1, max=63)),
                  description="The user-defined name for this IPsec policy.")
    href = String(validate=(Regexp(IBM_HREF_PATTERN)), required=True)
    created_at = DateTime(format=DATE_TIME_FORMAT)
    resource_type = String(required=True, validate=OneOf(IBMIPSecPolicy.ALL_RESOURCE_TYPES_LIST),
                           description="The resource type.")
    transform_protocol = String(required=True, validate=OneOf(IBMIPSecPolicy.ALL_TRANSFORM_PROTOCOLS_LIST),
                                description="The transform protocol used. Only esp is supported.")
    resource_group = Nested("IBMResourceGroupRefOutSchema", required=True)
    status = String(required=True)


class IBMIPSecPolicyRefOutSchema(IBMIPSecPolicyOutSchema):
    class Meta:
        fields = ("id", "name")


class IBMIPSecPolicyValidateJsonResourceSchema(Schema):
    class Meta:
        fields = ("name",)


class IBMIPSecPolicyValidateJsonOutSchema(Schema):
    id = String(
        required=True, allow_none=False, validate=[Length(equal=32), Regexp(IBM_UUID_PATTERN)],
        description="Unique ID of the IBM IPSec Policy"
    )
    resource_json = Nested(IBMIPSecPolicyValidateJsonResourceSchema, required=True)
