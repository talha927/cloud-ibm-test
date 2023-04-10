from marshmallow import INCLUDE, Schema
from marshmallow.fields import Boolean, DateTime, List, Nested, String
from marshmallow.validate import Length, OneOf, Range, Regexp

from ibm.common.req_resp_schemas.consts import DATE_TIME_FORMAT, IBM_HREF_PATTERN, IBM_RESOURCE_NAME_PATTERN, \
    IBM_UUID_PATTERN
from ibm.common.req_resp_schemas.fields import IPv4
from ibm.models import IBMLoadBalancer, IBMLoadBalancerProfile, IBMResourceGroup, IBMSecurityGroup, IBMSubnet


class IBMIPAddressSchema(Schema):
    address = IPv4(required=True, allow_none=False, type="IPv4", example="192.168.3.4")


class IBMLoadBalancerResourceSchema(Schema):
    REF_KEY_TO_RESOURCE_TYPE_MAPPER = {
        "resource_group": IBMResourceGroup,
        "profile": IBMLoadBalancerProfile,
        "subnets": IBMSubnet,
        "security_groups": IBMSecurityGroup
    }

    name = String(required=True, validate=(Length(min=1, max=63), Regexp(IBM_RESOURCE_NAME_PATTERN)))
    is_public = Boolean(required=True)
    resource_group = Nested(
        "OptionalIDNameSchemaWithoutValidation",
        description="Either both or one of '['id', 'name']' should be provided."
    )
    profile = Nested(
        "OptionalIDNameSchema", required=True,
        description="The profile to use for this load balancer"
    )
    route_mode = Boolean(default=False, description="Indicates whether route mode is enabled for this load balancer.")
    logging_datapath_active = Boolean(default=False)
    security_groups = Nested("OptionalIDNameSchema", many=True, minimum=1, uniqueItems=True)
    subnets = Nested("OptionalIDNameSchema", many=True, required=True, minimum=1)
    # Todo: exclude `certificate_instance` when added to `LBListenerInSchema`
    listeners = \
        Nested(
            "IBMLoadBalancerListenerResourceSchema", many=True,
            exclude=['https_redirect', 'policies'], unknown=INCLUDE
        )
    pools = Nested("IBMLoadBalancerPoolResourceSchema", many=True, unknown=INCLUDE)


class IBMLoadBalancerInSchema(Schema):
    REF_KEY_TO_RESOURCE_TYPE_MAPPER = {}

    resource_json = Nested(IBMLoadBalancerResourceSchema, required=True)
    ibm_cloud = Nested("OptionalIDNameSchemaWithoutValidation", required=True)
    region = Nested("OptionalIDNameSchema", required=True)


class IBMLoadBalancerOutSchema(Schema):
    id = String(
        required=True, allow_none=False, validate=[Length(equal=32), Regexp(IBM_UUID_PATTERN)],
        description="Unique ID of the IBM Load Balancer."
    )
    created_at = DateTime(required=True, allow_none=False, format=DATE_TIME_FORMAT)
    name = String(
        required=True, allow_none=False, validate=Length(max=255),
        description="The user-defined name for this load balancer."
    )
    is_public = Boolean(required=True)
    resource_id = String(required=True, allow_none=False, description="UUID of the IBM Load Balancer on IBM Cloud")
    hostname = String(required=True, allow_none=False, example="my-load-balancer-123456-us-south-1.lb.bluemix.net")
    private_ips = Nested("IBMIPAddressSchema", many=True, required=True)
    public_ips = Nested("IBMIPAddressSchema", many=True, required=True)
    href = String(validate=(Regexp(IBM_HREF_PATTERN)), required=True)
    crn = String(validate=Length(max=255), required=True)
    logging_datapath_active = Boolean(required=True)
    route_mode = Boolean(required=True)
    operating_status = String(
        required=True, validate=OneOf(IBMLoadBalancer.ALL_OPERATING_STATUSES),
        description="The operating status of this load balancer"
    )
    security_groups_supported = Boolean(required=True)
    provisioning_status = String(required=True, allow_none=False, validate=OneOf(IBMLoadBalancer.ALL_LB_STATUSES_LIST),
                                 data_key="status")
    profile = Nested("IBMLoadBalancerProfileRefOutSchema", required=True, allow_none=False)
    listeners = \
        Nested(
            "IBMLoadBalancerListenerOutSchema", many=True, required=True,
            description="The listener references of load balancer"
        )
    pools = \
        Nested(
            "IBMLoadBalancerPoolOutSchema", many=True, required=True, description="The pools of this load balancer."
        )
    ibm_cloud = Nested("IBMCloudRefOutSchema", required=True)
    resource_group = Nested("IBMResourceGroupRefOutSchema", required=True)
    region = Nested("IBMRegionRefOutSchema", required=True)
    associated_resources = Nested("IBMLoadBalancerAssociatedResourcesOutSchema", required=True)


class IBMLoadBalancerAssociatedResourcesOutSchema(Schema):
    vpc = Nested("IBMVpcNetworkRefOutSchema", required=True)
    subnets = Nested("IBMSubnetRefOutSchema", many=True, required=True)
    security_groups = Nested("IBMSecurityGroupRefOutSchema", many=True, required=True)


class IBMLoadBalancerRefOutSchema(IBMLoadBalancerOutSchema):
    class Meta:
        fields = ("id", "name", "hostname")


class IBMLoadBalancerValidateJsonResourceSchema(Schema):
    class Meta:
        fields = ("name", "hostname")


class IBMLoadBalancerValidateJsonOutSchema(Schema):
    id = String(
        required=True, allow_none=False, validate=[Length(equal=32), Regexp(IBM_UUID_PATTERN)],
        description="Unique ID of the IBM Load Balancer"
    )
    resource_json = Nested(IBMLoadBalancerValidateJsonResourceSchema, required=True)


class UpdateIBMLoadBalancerSchema(Schema):
    logging_datapath_active = Boolean()
    name = String(
        required=True, allow_none=False,
        validate=[
            Regexp(IBM_RESOURCE_NAME_PATTERN), Range(min=1, max=63)
        ],
        example="lb-test-1",
        description="The user-defined name for this load balancer."
    )


class IBMLoadBalancerProfileOutSchema(Schema):
    class TypeValueOutSchema(Schema):
        type = String(required=True)
        value = Boolean(missing=True)

    class LoggingSupportedOutSchema(TypeValueOutSchema):
        value = List(String(required=True))

    id = String(
        required=True, allow_none=False,
        validate=[Length(equal=32)],
        description="Unique ID of the IBM Load Balancer Profile."
    )
    name = String(required=True, description="The globally unique name for this load balancer profile")
    ibm_cloud = Nested("IBMCloudRefOutSchema", required=True)
    family = String(required=True)
    href = String(validate=(Regexp(IBM_HREF_PATTERN)), required=True)
    route_mode_supported = Nested(
        "TypeValueOutSchema", required=True,
        description="The route mode support for a load balancer with this profile"
    )
    security_groups_supported = Nested(
        "TypeValueOutSchema", missing=True,
        description="The security group support for a load balancer with this profile"
    )
    logging_supported = Nested(
        "LoggingSupportedOutSchema", required=True,
        description="Indicates which logging type(s) are supported for a load balancer with this profile"
    )


class IBMLoadBalancerProfileRefOutSchema(IBMLoadBalancerProfileOutSchema):
    class Meta:
        fields = ("id", "name", "family")


class IBMLoadBalancerProfileListQuerySchema(Schema):
    minimal = Boolean(default=False, load_default=False)


class IBMInstanceGroupAttachedListQuerySchema(Schema):
    is_ig_attached = Boolean(allow_none=False,
                             description="Return load balancers that are either attached to a Instance Group "
                                         "(in case True) or available for attachment (in case False).")
