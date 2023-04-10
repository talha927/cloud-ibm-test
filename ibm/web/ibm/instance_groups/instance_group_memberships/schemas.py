import uuid

from apiflask.fields import Boolean, DateTime, Nested, String
from apiflask.schemas import Schema
from apiflask.validators import Length, OneOf, Regexp

from ibm.common.req_resp_schemas.consts import IBM_RESOURCE_NAME_PATTERN, IBM_UUID_PATTERN
from ibm.common.req_resp_schemas.schemas import IBMResourceQuerySchema
from ibm.models import IBMInstanceGroupMembership


class IBMInstanceGroupMembershipOutSchema(Schema):
    id = String(required=True, allow_none=False, example=uuid.uuid4().hex,
                validate=(Regexp(IBM_UUID_PATTERN), Length(equal=32)))
    name = String(required=True, allow_none=False, validate=(Regexp(IBM_RESOURCE_NAME_PATTERN)),
                  description="User defined name of the instance group membership")
    resource_id = String(required=True, allow_none=False)
    created_at = DateTime(required=True, allow_none=False)
    href = String(required=True, allow_none=False)
    delete_instance_on_membership_delete = \
        Boolean(
            required=True,
            description="If set to true, when deleting the membership the instance will also be deleted."
        )
    status = String(required=True, validate=OneOf(IBMInstanceGroupMembership.ALL_STATUSES_LIST),
                    description="The status of the instance group membership.")
    updated_at = DateTime(required=True, allow_none=False)
    associated_resources = Nested("IBMInstanceGroupMembershipAssociatedResourcesOutSchema", required=True)


class IBMInstanceGroupMembershipAssociatedResourcesOutSchema(Schema):
    instance = Nested(
        "IBMInstanceRefOutSchema", required=True
    )
    instance_template = Nested(
        "IBMInstanceTemplateRefOutSchema", required=True,
    )
    pool_member = Nested(
        "IBMLoadBalancerPoolMemberRefOutSchema", required=True
    )


class IBMInstanceGroupMembershipRefOutSchema(IBMInstanceGroupMembershipOutSchema):
    class Meta:
        fields = ("id", "name")


class IBMInstanceGroupMembershipUpdateSchema(Schema):
    name = String(required=True, allow_none=False, validate=(Regexp(IBM_RESOURCE_NAME_PATTERN)),
                  description="User defined name of the instance group membership")


class IBMInstanceGroupMembershipListQuerySchema(IBMResourceQuerySchema):
    instance_group_id = String(required=True, allow_none=False, validate=(Regexp(IBM_UUID_PATTERN), Length(equal=32)))
