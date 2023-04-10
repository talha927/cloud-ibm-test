import uuid

from apiflask import Schema
from apiflask.fields import Boolean, DateTime, Float, Nested, String
from apiflask.validators import Length, Regexp

from ibm.common.req_resp_schemas.consts import IBM_UUID_PATTERN


class IBMCostOutSchema(Schema):
    id = String(
        required=True, allow_none=False,
        validate=[
            Length(equal=32),
        ],
        example=uuid.uuid4().hex,
        format="uuid",
        description="The unique identifier for the cost."
    )
    account_id = String(required=True, allow_none=False, description="The ID of the account.")
    billing_month = DateTime(required=True, validate=(Regexp(r"^\d{4}\-(0?[1-9]|1[012])$")),
                             description="The billing month for which the usage report is requested."
                                         " Format is yyyy-mm.")
    billing_country_code = String(required=True, allow_none=False, description="Country.")
    billing_currency_code = String(required=True, allow_none=False, description="The currency in which the account "
                                                                                "is billed.")
    billable_cost = Float(required=True, description="The billable charges for all cloud resources used in the"
                                                     " account.")
    non_billable_cost = Float(required=True, description="Non-billable charges for all cloud resources used in the"
                                                         " account.")
    details = Nested("IBMIndividualResourceCostOutSchema", many=True)
    ibm_cloud = Nested("IBMCloudRefOutSchema", required=True)


class IBMCostRefOutSchema(IBMCostOutSchema):
    class Meta:
        fields = ("id",)


class IBMIndividualResourceCostOutSchema(Schema):
    id = String(
        required=True, allow_none=False,
        validate=[
            Length(equal=32),
        ],
        example=uuid.uuid4().hex,
        format="uuid",
        description="The unique identifier for the individual cost."
    )
    resource_id = String(required=True, allow_none=False)
    billable_cost = Float(required=True, description="The billable charges for all cloud resources used in the"
                                                     " account.")
    non_billable_cost = Float(required=True, description="Non-billable charges for all cloud resources used in the"
                                                         " account.")
    resource_name = String(required=True, allow_none=False, description="name for this resource.")

    cost_id = Nested("IBMCostRefOutSchema", required=True)


class IBMCloudQuerySchema(Schema):
    cloud_id = String(validate=(Regexp(IBM_UUID_PATTERN), Length(equal=32)))


class IBMCostSchema(Schema):
    cloud_id = String(validate=(Regexp(IBM_UUID_PATTERN), Length(equal=32)))
    cost_per_tags = Boolean(allow_none=False, description="This param will filter out Cost per Tags in-case of 'True'")
