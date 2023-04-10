import uuid

from marshmallow import Schema
from marshmallow.fields import DateTime, Integer, Nested, String
from marshmallow.validate import Length, OneOf, Regexp

from ibm.common.req_resp_schemas.consts import IBM_HREF_PATTERN, IBM_RESOURCE_NAME_PATTERN, IBM_UUID_PATTERN
from ibm.models import IBMResourceGroup


class IBMSshKeyResourceSchema(Schema):
    REF_KEY_TO_RESOURCE_TYPE_MAPPER = {
        "resource_group": IBMResourceGroup,
    }

    name = String(required=True, allow_none=False,
                  validate=[Regexp(IBM_RESOURCE_NAME_PATTERN), Length(min=1, max=63)],
                  example="ssh-key-1",
                  description="The unique user-defined name for this key.")

    public_key = String(required=True, allow_none=False,
                        validate=Regexp("ssh-rsa AAAA[0-9A-Za-z+/]+[=]{0,3} ([^@]+@[^@]+)"),
                        description="The public SSH key",
                        example="AAAAB3NzaC1yc2EAAAADAQABAAABAQDDGe50Bxa5T5NDddrrtbx2Y4/VGbiCgXqnBsYToIUKoFSHTQl"
                                "5IX3PasGnneKanhcLwWz5M5MoCRvhxTp66NKzIfAz7r+FX9rxgR+ZgcM253YAqOVeIpOU408simDZKri"
                                "TlN8kYsXL7P34tsWuAJf4MgZtJAQxous/2byetpdCv8ddnT4X3ltOg9w+LqSCPYfNivqH00Eh7S1Ldz7"
                                "I8aw5WOp5a+sQFP/RbwfpwHp+ny7DfeIOokcuI42tJkoBn7UsLTVpCSmXr2EDRlSWe/1M/iHNRBzaT3C"
                                "K0+SwZWd2AEjePxSnWKNGIEUJDlUYp7hKhiQcgT5ZAnWU121oc5En")

    type_ = String(data_key="type", validate=OneOf(["rsa"]), default="rsa",
                   description="The crypto-system used by this key.")
    resource_group = Nested(
        "OptionalIDNameSchemaWithoutValidation",
        description="Either both or one of '['id', 'name']' should be provided."
    )


class IBMSshKeyInSchema(Schema):
    REF_KEY_TO_RESOURCE_TYPE_MAPPER = {}

    resource_json = Nested(IBMSshKeyResourceSchema, required=True)
    ibm_cloud = Nested("OptionalIDNameSchemaWithoutValidation", required=True)
    region = Nested("OptionalIDNameSchema", required=True)


class IBMSshKeyOutSchema(Schema):
    id = String(required=True, example=uuid.uuid4().hex, format="uuid",
                description="The unique identifier for this key")
    name = String(required=True, allow_none=False,
                  validate=[Regexp(IBM_RESOURCE_NAME_PATTERN), Length(min=1, max=63)],
                  example="ssh-key-1",
                  description="The unique user-defined name for this key.")
    length = Integer(required=True, allow_none=False, validate=OneOf([2048, 4096]),
                     description="The length of this key (in bits)")
    fingerprint = String(required=True, allow_none=False,
                         description="The fingerprint for this key. The value is returned base64-encoded and "
                                     "prefixed with the hash algorithm (always `SHA256`).",
                         example="SHA256:yxavE4CIOL2NlsqcurRO3xGjkP6m/0mp8ugojH5yxlY")
    public_key = String(required=True, allow_none=False,
                        validate=Regexp("ssh-rsa AAAA[0-9A-Za-z+/]+[=]{0,3} ([^@]+@[^@]+)"),
                        description="The public SSH key",
                        example="AAAAB3NzaC1yc2EAAAADAQABAAABAQDDGe50Bxa5T5NDddrrtbx2Y4/VGbiCgXqnBsYToIUKoFSHTQl"
                                "5IX3PasGnneKanhcLwWz5M5MoCRvhxTp66NKzIfAz7r+FX9rxgR+ZgcM253YAqOVeIpOU408simDZKri"
                                "TlN8kYsXL7P34tsWuAJf4MgZtJAQxous/2byetpdCv8ddnT4X3ltOg9w+LqSCPYfNivqH00Eh7S1Ldz7"
                                "I8aw5WOp5a+sQFP/RbwfpwHp+ny7DfeIOokcuI42tJkoBn7UsLTVpCSmXr2EDRlSWe/1M/iHNRBzaT3C"
                                "K0+SwZWd2AEjePxSnWKNGIEUJDlUYp7hKhiQcgT5ZAnWU121oc5En")
    type_ = String(required=True, allow_none=False, data_key="type", validate=OneOf(["rsa"]), default="rsa",
                   description="The crypto-system used by this key.")
    created_at = DateTime(required=True, allow_none=False, description="The date and time that the subnet was created")
    crn = String(required=True, allow_none=False, description="The CRN for this subnet",
                 example="crn:v1:bluemix:public:is:us-south-1:a/123456::subnet:7ec86020-1c6e-4889-b3f0-a15f2e50f87e")
    href = String(required=True, allow_none=False, description="The URL for this subnet",
                  validate=Regexp(IBM_HREF_PATTERN))

    resource_group = Nested("IBMResourceGroupRefOutSchema", required=True)
    status = String(required=True)
    region = Nested("IBMRegionRefOutSchema", required=True)
    ibm_cloud = Nested("IBMCloudRefOutSchema", required=True)


class IBMSshKeyRefOutSchema(IBMSshKeyOutSchema):
    class Meta:
        fields = ("id", "name")


class IBMSshKeyValidateJsonResourceSchema(Schema):
    class Meta:
        fields = ("name", "public_key")


class IBMSshKeyValidateJsonOutSchema(Schema):
    id = String(
        required=True, allow_none=False, validate=[Length(equal=32), Regexp(IBM_UUID_PATTERN)],
        description="Unique ID of the IBM VPC Network"
    )
    resource_json = Nested(IBMSshKeyValidateJsonResourceSchema, required=True)


class UpdateIBMSshKeySchema(Schema):
    name = String(required=True, allow_none=False,
                  validate=[Regexp(IBM_RESOURCE_NAME_PATTERN), Length(min=1, max=63)],
                  example="ssh-key-1",
                  description="The unique user-defined name for this key.")
