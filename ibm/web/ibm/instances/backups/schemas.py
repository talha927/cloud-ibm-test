from marshmallow import Schema
from marshmallow.fields import Nested

from ibm.models import IBMCloud, IBMInstance, IBMRegion, IBMResourceGroup


class IBMInstanceBackupInSchema(Schema):
    REF_KEY_TO_RESOURCE_TYPE_MAPPER = {
        "instance": IBMInstance,
        "resource_group": IBMResourceGroup,
        "region": IBMRegion,
        "ibm_cloud": IBMCloud
    }
    ibm_cloud = Nested("OptionalIDNameSchemaWithoutValidation", required=True)
    region = Nested("OptionalIDNameSchemaWithoutValidation", required=True)
    instance = Nested("OptionalIDNameSchemaWithoutValidation", required=True)
    resource_group = Nested("OptionalIDNameSchemaWithoutValidation", required=True)
