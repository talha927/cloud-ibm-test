from apiflask import Schema
from apiflask.fields import String
from apiflask.validators import Length, Regexp

from ibm.common.req_resp_schemas.consts import IBM_UUID_PATTERN


class IBMCostReportingQuerySchema(Schema):
    cloud_id = String(validate=(Regexp(IBM_UUID_PATTERN), Length(equal=32)))
    month = String(description="This param will filter out reports on the basis of month if provided")
