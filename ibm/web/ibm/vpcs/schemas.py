from marshmallow import INCLUDE, Schema, validates_schema, ValidationError
from marshmallow.fields import Boolean, DateTime, Dict, List, Nested, String
from marshmallow.validate import Length, OneOf, Regexp

from ibm.common.req_resp_schemas.consts import DATE_TIME_FORMAT, IBM_RESOURCE_NAME_PATTERN, IBM_UUID_PATTERN
from ibm.models import IBMResourceGroup, IBMVpcNetwork


class IBMVpcNetworkResourceSchema(Schema):
    REF_KEY_TO_RESOURCE_TYPE_MAPPER = {
        "resource_group": IBMResourceGroup,
    }

    address_prefix_management = String(validate=OneOf(IBMVpcNetwork.ALL_APM_MODES))
    classic_access = Boolean()
    name = String(required=True, validate=(Length(min=1, max=63), Regexp(IBM_RESOURCE_NAME_PATTERN)))
    resource_group = Nested(
        "OptionalIDNameSchemaWithoutValidation",
        description="Either both or one of '['id', 'name']' should be provided."
    )


class IBMVpcNetworkInSchema(Schema):
    REF_KEY_TO_RESOURCE_TYPE_MAPPER = {}

    resource_json = Nested(IBMVpcNetworkResourceSchema, required=True)
    ibm_cloud = Nested("OptionalIDNameSchemaWithoutValidation", required=True)
    region = Nested("OptionalIDNameSchema", required=True)
    error_already_exists = Boolean(missing=True, description="Raise an error if the VPC is already created")
    tags = Nested("IBMTagInSchema", many=True, unknown=INCLUDE, exclude=['ibm_cloud'])
    ttl = Nested(
        "TTLInterval", description="Time to Live Interval for VPC, and it will be deleted after expiry time",
        exclude=['id'])


class TTLInterval(Schema):
    id = String(
        required=True, allow_none=False, validate=[Length(equal=32), Regexp(IBM_UUID_PATTERN)],
        description="Unique ID of the Time to Live (TTL) interval"
    )
    expires_at = String(required=True, allow_none=False)


class IBMVpcNetworkOutSchema(Schema):
    id = String(
        required=True, allow_none=False, validate=[Length(equal=32), Regexp(IBM_UUID_PATTERN)],
        description="Unique ID of the IBM VPC Network"
    )
    resource_id = String(
        required=True, allow_none=False, description="Unique ID of the IBM VPC Network on IBM Cloud"
    )
    name = String(
        required=True, allow_none=False, validate=Length(max=255),
        description="Unique name of the IBM VPC Network"
    )
    created_at = DateTime(required=True, allow_none=False, format=DATE_TIME_FORMAT)
    status = String(required=True, validate=OneOf(IBMVpcNetwork.ALL_STATUSES_LIST))
    classic_access = Boolean(
        required=True, description="Whether or not classic access is enabled for the IBM VPC Network"
    )
    resource_group = Nested("IBMResourceGroupRefOutSchema", required=True)
    region = Nested("IBMRegionRefOutSchema", required=True)
    ibm_cloud = Nested("IBMCloudRefOutSchema", required=True)
    associated_resources = Nested("IBMVpcNetworkAssociatedResourcesOutSchema", required=True)
    recommendations = Dict(required=False, allow_none=False)
    ttl = Nested("TTLInterval", required=True)


class IBMVpcNetworkAssociatedResourcesOutSchema(Schema):
    address_prefixes = Nested("IBMAddressPrefixRefOutSchema", many=True, required=True)
    subnets = Nested("IBMSubnetRefOutSchema", many=True, required=True)
    kubernetes_clusters = Nested("IBMKubernetesClusterRefOutSchema", many=True, required=True)
    public_gateways = Nested("IBMPublicGatewayRefOutSchema", many=True, required=True)
    instances = Nested("IBMInstanceRefOutSchema", many=True, required=True)
    security_groups = Nested("IBMSecurityGroupRefOutSchema", many=True, required=True)
    load_balancers = Nested("IBMLoadBalancerRefOutSchema", many=True, required=True)
    network_acls = Nested("IBMAclRefOutSchema", many=True, required=True)
    vpn_gateways = Nested("IBMVpnGatewayRefOutSchema", many=True, required=True)
    acls = Nested("IBMAclRefOutSchema", many=True, required=True)
    instance_groups = Nested("IBMInstanceGroupRefOutSchema", many=True, required=True)
    routing_tables = Nested("IBMRoutingTableRefOutSchema", many=True, required=True)
    tags = Nested("IBMTagRefOutSchema", many=True, required=True)


class IBMVpcNetworkRefOutSchema(IBMVpcNetworkOutSchema):
    class Meta:
        fields = ("id", "name", "address_prefixes")


class IBMVpcNetworkValidateJsonResourceSchema(Schema):
    class Meta:
        fields = ("name", "address_prefixes")


class IBMVpcNetworkValidateJsonOutSchema(Schema):
    id = String(
        required=True, allow_none=False, validate=[Length(equal=32), Regexp(IBM_UUID_PATTERN)],
        description="Unique ID of the IBM VPC Network"
    )
    resource_json = Nested(IBMVpcNetworkValidateJsonResourceSchema, required=True)


class IBMVpcNetworkSearchSchema(Schema):
    untag_vpc = Boolean(
        truthy={"True", "true"}, falsy={"False", "false"}, missing=False,
        description="Whether or not any of the VPC should be tagged."
    )


class IBMVpcActionInSchema(Schema):
    action = String(required=True, allow_none=False, validate=OneOf(["start", "stop"]),
                    description="Action for VPC i.e. start or stop")
    vpc_ids = List(String(validate=Length(equal=32)), default=[])
    tag_ids = List(String(validate=Length(equal=32)), default=[])
    instance_ids = List(String(validate=Length(equal=32)), default=[])

    @validates_schema
    def validate_oneof(self, data, **kwargs):
        if not (data.get("vpc_ids") or data.get("tag_ids") or data.get("instance_ids")):
            raise ValidationError("Either both or one of '['vpc_ids', 'tag_ids', 'instance_ids']' should be provided.")
