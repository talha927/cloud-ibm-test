import uuid

from apiflask.fields import DateTime, Integer, Nested, String
from apiflask.schemas import Schema
from apiflask.validators import Length, OneOf, Regexp
from marshmallow import validates_schema, ValidationError
from marshmallow.validate import Range

from ibm.common.req_resp_schemas.consts import IBM_RESOURCE_NAME_PATTERN, IBM_UUID_PATTERN
from ibm.common.req_resp_schemas.schemas import IBMResourceQuerySchema
from ibm.models import IBMInstanceGroup, IBMInstanceTemplate, \
    IBMLoadBalancer, IBMPool, IBMResourceGroup, IBMSubnet


class IBMInstanceGroupResourceSchema(Schema):
    REF_KEY_TO_RESOURCE_TYPE_MAPPER = {
        "instance_template": IBMInstanceTemplate,
        "load_balancer": IBMLoadBalancer,
        "load_balancer_pool": IBMPool,
        "resource_group": IBMResourceGroup,
        "subnets": IBMSubnet
    }
    name = String(required=True, allow_none=False, validate=(Regexp(IBM_RESOURCE_NAME_PATTERN)),
                  description="User defined name of the instance Group")
    application_port = Integer(validate=Range(min=1, max=65535), example=22,
                               description="Required if specifying a load balancer pool only. Used by the "
                                           "instance group when scaling up instances to supply the port for the"
                                           " load balancer pool member.")
    membership_count = Integer(validate=Range(min=0, max=1000), default=0, example=10,
                               description="The number of instances in the instance group.")
    instance_template = Nested("OptionalIDNameSchema",
                               description="Either ID or Name of the `instance_group` is required.",
                               required=True)
    subnets = Nested("OptionalIDNameSchema", many=True, description="The subnets to use when creating new instances.")
    load_balancer = Nested(
        "OptionalIDNameSchema",
        description="Either both or one of '['id', 'name']' should be provided."
    )
    load_balancer_pool = Nested(
        "OptionalIDNameSchema",
        description="Either both or one of '['id', 'name']' should be provided."
    )
    resource_group = Nested(
        "OptionalIDNameSchemaWithoutValidation", required=True,
        description="Either both or one of '['id', 'name']' should be provided."
    )
    instance_group_managers = Nested("IBMInstanceGroupManagerResourceSchema")
    instance_group_manager_policies = Nested("IBMInstanceGroupManagerPolicyResourceSchema")

    @validates_schema
    def validate_lb_application_port_requirements(self, data, **kwargs):
        if (data.get("load_balancer") and data.get("load_balancer_pool")) and not data.get("application_port"):
            raise ValidationError(
                "'application_port' is mandatory with 'load_balancer'")
        if data.get("load_balancer") and not data.get("load_balancer_pool"):
            raise ValidationError(
                "'load_balancer_pool' is mandatory with 'load_balancer'")


class IBMInstanceGroupInSchema(Schema):
    REF_KEY_TO_RESOURCE_TYPE_MAPPER = {}

    resource_json = Nested(IBMInstanceGroupResourceSchema, required=True)
    ibm_cloud = Nested("OptionalIDNameSchemaWithoutValidation", required=True)
    region = Nested("OptionalIDNameSchema", only=("id",), required=True)


class IBMInstanceGroupOutSchema(Schema):
    id = String(required=True, allow_none=False, example=uuid.uuid4().hex,
                validate=(Regexp(IBM_UUID_PATTERN), Length(equal=32)))
    name = String(required=True, allow_none=False, validate=(Regexp(IBM_RESOURCE_NAME_PATTERN)),
                  description="User defined name of the instance group")
    resource_id = String(required=True, allow_none=False)
    created_at = DateTime(required=True, allow_none=False)
    href = String(required=True, allow_none=False)
    crn = String(required=True, allow_none=False)
    status = String(required=True, validate=OneOf(IBMInstanceGroup.ALL_STATUSES_LIST),
                    description="The status of the instance group. ")
    updated_at = DateTime(required=True, allow_none=False)
    application_port = Integer(validate=Range(min=1, max=65535), example=22,
                               description="Required if specifying a load balancer pool only. Used by the "
                                           "instance group when scaling up instances to supply the port for the"
                                           " load balancer pool member.")
    membership_count = Integer(validate=Range(min=0, max=1000), example=10,
                               description="The number of instances in the instance group.")
    region = Nested("IBMRegionRefOutSchema", description="Region reference of the instance group", required=True)
    managers = \
        Nested(
            "IBMInstanceGroupManagerOutSchema", many=True, required=True,
            description="The managers for the instance group."
        )
    memberships = Nested("IBMInstanceGroupMembershipOutSchema", many=True)
    ibm_cloud = Nested("IBMCloudRefOutSchema", description="IBM Cloud reference of the instance group", required=True)
    resource_group = Nested("IBMResourceGroupRefOutSchema", required=True)
    associated_resources = Nested("IBMInstanceGroupAssociatedResourcesOutSchema", required=True)


class IBMInstanceGroupAssociatedResourcesOutSchema(Schema):
    vpc = Nested(
        "IBMVpcNetworkRefOutSchema", required=True,
        description="Either ID or Name of the`VPC` is required."
    )
    instance_template = Nested(
        "IBMInstanceTemplateRefOutSchema", required=True,
        description="The template used to create new instances for this group."
    )
    ibm_pool = Nested(
        "IBMLoadBalancerPoolRefOutSchema",
        description="The load balancer pool managed by this group. Instances "
                    "created by this group will have a new load balancer pool member"
                    " in that pool created."
    )
    load_balancer = Nested(
        "IBMLoadBalancerRefOutSchema",
        description="The load balancer that the load balancer pool used by this group is in. Required when using a"
                    " load balancer pool."
    )
    subnets = Nested("IBMSubnetRefOutSchema", many=True, required=True, description="The subnets to use when creating "
                                                                                    "new instances.")


class IBMInstanceGroupRefOutSchema(IBMInstanceGroupOutSchema):
    class Meta:
        fields = ("id", "name")


class IBMInstanceGroupUpdateSchema(Schema):
    application_port = Integer(validate=Range(min=1, max=65535), example=22,
                               description="Required if specifying a load balancer pool only. Used by the "
                                           "instance group when scaling up instances to supply the port for the"
                                           " load balancer pool member.")
    instance_template = Nested(
        "IBMInstanceTemplateRefOutSchema", description="The template used to create new instances for this group.")
    load_balancer = Nested("OptionalIDNameSchema",
                           description="Either ID or Name of the `load_balancer`.")
    ibm_pool = Nested(
        "IBMLoadBalancerPoolRefOutSchema", description="The load balancer pool managed by this group. Instances "
                                                       "created by this group will have a new load balancer pool member"
                                                       " in that pool created."
    )
    membership_count = Integer(validate=Range(min=0, max=1000), example=10,
                               description="The number of instances in the instance group.")
    name = String(required=True, allow_none=False, validate=(Regexp(IBM_RESOURCE_NAME_PATTERN)),
                  description="User defined name of the instance group")
    subnets = Nested("IBMSubnetRefOutSchema", many=True, description="The subnets to use when creating "
                                                                     "new instances.")
    ibm_cloud = Nested("IBMCloudRefOutSchema", description="IBM Cloud reference of the instance group", required=True)


class IBMInstanceGroupListQuerySchema(IBMResourceQuerySchema):
    instance_group_manager_id = String(required=True, allow_none=False, validate=(Regexp(IBM_UUID_PATTERN),
                                                                                  Length(equal=32)))
