from apiflask import Schema
from apiflask.fields import Raw, String
from apiflask.validators import Regexp

from ibm.common.req_resp_schemas.consts import IBM_NESTED_ID_STRING_PATTERN


class IBMMigrationInSchema(Schema):
    REF_KEY_TO_RESOURCE_TYPE_MAPPER = {}

    softlayer_cloud = String(required=True, validate=Regexp(IBM_NESTED_ID_STRING_PATTERN),
                             description='This is a nested field. Due to limitation of using form data this data '
                                         'type string. The format for this field will be "{"id"": "uuid"}"')


class IBMMigrationFileInSchema(Schema):
    config_file = Raw(type='file', description="Vyatta file. Format supported '.txt'")
