from apiflask import Schema
from apiflask.fields import List, Nested, String
from apiflask.validators import Length, OneOf

from ibm.web.ibm.idle_resources.utils import IDLE_RESOURCE_TYPE_MODLE_MAPPER


class IBMIdleResourceSchema(Schema):
    REF_KEY_TO_RESOURCE_TYPE_MAPPER = {
    }
    resource_type = String(validate=OneOf(IDLE_RESOURCE_TYPE_MODLE_MAPPER.keys()))
    id = String(validate=Length(equal=32), required=True)


class IBMIdleResourceInSchema(Schema):
    REF_KEY_TO_RESOURCE_TYPE_MAPPER = {}
    resources = List(Nested("IBMIdleResourceSchema", required=True))
