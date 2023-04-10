from apiflask import Schema
from apiflask.fields import DateTime, String
from apiflask.validators import OneOf, Range, Regexp
from marshmallow.fields import Integer, Nested
from marshmallow.validate import Length

from ibm.common.req_resp_schemas.consts import DATE_TIME_FORMAT, IBM_HREF_PATTERN, IBM_RESOURCE_NAME_PATTERN, \
    IBM_UUID_PATTERN
from ibm.models import IBMIKEPolicy, IBMResourceGroup


class IBMIKEPoliciesResourceSchema(Schema):
    REF_KEY_TO_RESOURCE_TYPE_MAPPER = {
        "resource_group": IBMResourceGroup,
    }

    authentication_algorithm = String(required=True, validate=OneOf(IBMIKEPolicy.ALL_AUTHENTICATION_ALGORITHMS_LIST),
                                      description="The authentication algorithm.")
    dh_group = Integer(required=True,
                       validate=OneOf(list(map(lambda dh_group: int(dh_group), IBMIKEPolicy.ALL_DH_GROUPS_LIST))),
                       description="The Diffie-Hellman group.")
    encryption_algorithm = String(required=True, validate=OneOf(IBMIKEPolicy.ALL_ENCRYPTION_ALGORITHMS_LIST),
                                  description="The encryption algorithm.")
    ike_version = Integer(required=True, validate=OneOf([1, 2]),
                          description="The IKE protocol version.")
    key_lifetime = Integer(validate=Range(min=1800, max=86400),
                           description="The key lifetime in seconds.")
    name = String(required=True, allow_none=False, validate=(Regexp(IBM_RESOURCE_NAME_PATTERN), Length(min=1, max=63)),
                  description="The user-defined name for this IKE policy.")
    resource_group = Nested("OptionalIDNameSchemaWithoutValidation")


class IBMIKEPoliciesInSchema(Schema):
    REF_KEY_TO_RESOURCE_TYPE_MAPPER = {}

    resource_json = Nested(IBMIKEPoliciesResourceSchema, required=True)
    ibm_cloud = Nested("OptionalIDNameSchemaWithoutValidation", required=True)
    region = Nested("OptionalIDNameSchema", required=True)


class UpdateIBMIKEPoliciesSchema(Schema):
    authentication_algorithm = String(validate=OneOf(IBMIKEPolicy.ALL_AUTHENTICATION_ALGORITHMS_LIST),
                                      description="The authentication algorithm.")
    dh_group = Integer(required=True,
                       validate=OneOf(list(map(lambda dh_group: int(dh_group), IBMIKEPolicy.ALL_DH_GROUPS_LIST))),
                       description="The Diffie-Hellman group.")
    encryption_algorithm = String(validate=OneOf(IBMIKEPolicy.ALL_ENCRYPTION_ALGORITHMS_LIST),
                                  description="The encryption algorithm.")
    ike_version = Integer(validate=OneOf(IBMIKEPolicy.ALL_IKE_VERSIONS_LIST),
                          description="The IKE protocol version.")
    key_lifetime = Integer(validate=Range(min=1800, max=86400),
                           description="The key lifetime in seconds.")
    name = String(required=True, allow_none=False, validate=(Regexp(IBM_RESOURCE_NAME_PATTERN), Length(min=1, max=63)),
                  description="The user-defined name for this IKE policy.")
    ibm_cloud = Nested("IBMCloudOutSchema", only=("id",), required=True)


class IBMIKEPolicyOutSchema(Schema):
    id = String(validate=Length(equal=32), required=True, description="The unique uuid of the IKE Policy.")
    authentication_algorithm = String(required=True, validate=OneOf(IBMIKEPolicy.ALL_AUTHENTICATION_ALGORITHMS_LIST),
                                      description="The authentication algorithm.")
    dh_group = Integer(required=True,
                       validate=OneOf(list(map(lambda dh_group: int(dh_group), IBMIKEPolicy.ALL_DH_GROUPS_LIST))),
                       description="The Diffie-Hellman group.")
    encryption_algorithm = String(required=True, validate=OneOf(IBMIKEPolicy.ALL_ENCRYPTION_ALGORITHMS_LIST),
                                  description="The encryption algorithm.")
    ike_version = Integer(required=True, validate=OneOf([1, 2]),
                          description="The IKE protocol version.")
    key_lifetime = Integer(validate=Range(min=1800, max=86400),
                           description="The key lifetime in seconds.")
    name = String(required=True, allow_none=False, validate=(Regexp(IBM_RESOURCE_NAME_PATTERN), Length(min=1, max=63)),
                  description="The user-defined name for this IKE policy.")
    href = String(validate=(Regexp(IBM_HREF_PATTERN)), required=True)
    created_at = DateTime(format=DATE_TIME_FORMAT)
    resource_group = Nested("IBMResourceGroupRefOutSchema", required=True)
    status = String(required=True)


class IBMIKEPolicyRefOutSchema(IBMIKEPolicyOutSchema):
    class Meta:
        fields = ("id", "name")


class IBMIKEPolicyValidateJsonResourceSchema(Schema):
    class Meta:
        fields = ("name",)


class IBMIKEPolicyValidateJsonOutSchema(Schema):
    id = String(
        required=True, allow_none=False, validate=[Length(equal=32), Regexp(IBM_UUID_PATTERN)],
        description="Unique ID of the IBM VPC Network"
    )
    resource_json = Nested(IBMIKEPolicyValidateJsonResourceSchema, required=True)
