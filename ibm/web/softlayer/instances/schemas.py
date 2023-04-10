from apiflask import Schema
from apiflask.fields import String, Integer
from apiflask.validators import Length, Regexp, Range

from ibm.common.req_resp_schemas.consts import IBM_UUID_PATTERN, IBM_RESOURCE_NAME_PATTERN


class IBMInstancesInSchema(Schema):
    region_id = String(validate=(Regexp(IBM_UUID_PATTERN), Length(equal=32)), required=False,
                       description="ID of the IBM Region.")


class OnlyVMWareSchema(Schema):
    classic_account_id = String(validate=(Regexp(IBM_UUID_PATTERN), Length(equal=32)), required=True,
                                description="ID of the IBM Classic Account")
    classic_instance_id = Integer(required=True,
                                  description="ID of the IBM Classic Instance")
    cos_bucket_name = String(required=True, allow_none=False,
                             validate=(Regexp(IBM_RESOURCE_NAME_PATTERN),
                                       Length(min=1, max=255)),
                             description="The name for the Cos Bucket")
    volume_count = Integer(required=True, validate=Range(min=1))


class OnlyVMWareInSchema(OnlyVMWareSchema):
    cloud_id = String(validate=(Regexp(IBM_UUID_PATTERN), Length(equal=32)), required=False,
                      description="ID of the IBM Cloud.")
    region = String(
        required=True, allow_none=False, validate=(Regexp(IBM_RESOURCE_NAME_PATTERN),
                                                   Length(min=1, max=255)), description="The name for the Region")
