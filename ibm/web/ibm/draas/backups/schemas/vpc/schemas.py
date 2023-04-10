from marshmallow import Schema
from marshmallow.fields import Bool, Nested, String
from marshmallow.validate import Length, Regexp

from ibm.common.req_resp_schemas.consts import IBM_UUID_PATTERN


class DisasterRecoveryIBMVpcNetworkBackupInSchema(Schema):
    ibm_cloud = Nested("OptionalIDNameSchemaWithoutValidation", required=True)
    resource_id = String(
        required=True, allow_none=False, validate=[Length(equal=32), Regexp(IBM_UUID_PATTERN)],
        description="Unique ID of the resource to take backup information"
    )
    name = String(
        required=True, allow_none=False, validate=[Length(min=1, max=255)],
        description="Name of the Draas Resource Blueprint"
    )
    instances_data = Bool(description="True/False if instances with data to be restored")
    is_volume = Bool(default=False, description="True/False if we want to add volumes or not")
