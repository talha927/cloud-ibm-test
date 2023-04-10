import uuid

from apiflask import Schema
from apiflask.fields import Boolean, DateTime, Nested, String
from apiflask.validators import Length, OneOf, Regexp
from marshmallow import validates_schema, ValidationError
from marshmallow.fields import Integer

from ibm.common.req_resp_schemas.consts import DATE_TIME_FORMAT, IBM_RESOURCE_NAME_PATTERN, \
    IBM_UUID_PATTERN
from ibm.common.req_resp_schemas.fields import IPv4CIDR
from ibm.common.req_resp_schemas.schemas import IBMResourceQuerySchema
from ibm.models import IBMResourceGroup, IBMTransitGateway, IBMTransitGatewayConnection, \
    IBMTransitGatewayConnectionPrefixFilter, IBMTransitGatewayRouteReport


class IBMTransitGatewayResourceSchema(Schema):
    REF_KEY_TO_RESOURCE_TYPE_MAPPER = {
        "resource_group": IBMResourceGroup
    }
    resource_group = Nested("OptionalIDNameSchemaWithoutValidation", required=True)
    location = String(required=True, allow_none=False, description="The location(region) of the Transit Gateway.It "
                                                                   "should be the region name like us-south or eu-gb")
    name = String(required=True, allow_none=False, validate=(Regexp(IBM_RESOURCE_NAME_PATTERN), Length(min=1, max=63)),
                  description="The name of the Transit Gateway.")
    is_global = Boolean(name="global_", default=False, description="Allow global routing for a Transit Gateway. "
                                                                   "If unspecified, the default value is false.")


class IBMTransitGatewayInSchema(Schema):
    REF_KEY_TO_RESOURCE_TYPE_MAPPER = {}

    resource_json = Nested("IBMTransitGatewayResourceSchema", required=True)
    ibm_cloud = Nested("OptionalIDNameSchemaWithoutValidation", required=True)
    connections = Nested("IBMTransitGatewayConnectionInSchema", many=True, required=False)
    prefix_filters = Nested("IBMTransitGatewayConnectionPrefixFilterInSchema", many=True, required=False)
    id = String(required=False, validate=(Regexp(IBM_UUID_PATTERN), Length(equal=32)),
                description="ID of the resource and will be created by FE for Sequential Creation.In Separate API call"
                            " the id from the DB will be used")


class IBMTransitGatewayQuerySchema(IBMResourceQuerySchema):
    transit_gateway_id = String(required=True, allow_none=False, validate=(Regexp(IBM_UUID_PATTERN), Length(equal=32)),
                                description="The ID of the Transit Gateway")


class IBMTransitGatewayOutSchema(Schema):
    id = String(required=True, allow_none=False, example=uuid.uuid4().hex,
                validate=(Regexp(IBM_UUID_PATTERN), Length(equal=32)))
    name = String(required=True, allow_none=False, validate=(Regexp(IBM_RESOURCE_NAME_PATTERN), Length(min=1, max=63)))
    created_at = DateTime(format=DATE_TIME_FORMAT)
    updated_at = DateTime(format=DATE_TIME_FORMAT)
    global_ = Boolean(
        description="Allow global routing for a Transit Gateway. If unspecified, the default value is false.")
    location = String(required=True, allow_none=False, description="The location of the Transit Gateway.")
    status = String(required=True, validate=OneOf(IBMTransitGateway.STATUSES_LIST))
    crn = String(validate=Length(max=255), required=True)
    resource_group = Nested("IBMResourceGroupRefOutSchema", required=True)
    connections = Nested("IBMTransitGatewayConnectionOutSchema", many=True)
    route_reports = Nested("IBMTransitGatewayRouteReportOutSchema", many=True)
    ibm_cloud = Nested("IBMCloudRefOutSchema", required=True)
    region = Nested("IBMRegionRefOutSchema", required=True, description="The region for the Transit Gateway.")


class IBMTransitGatewayListConnectionOutSchema(Schema):
    id = String(required=True, allow_none=False, example=uuid.uuid4().hex,
                validate=(Regexp(IBM_UUID_PATTERN), Length(equal=32)))
    name = String(required=True, allow_none=False, validate=(Regexp(IBM_RESOURCE_NAME_PATTERN), Length(min=1, max=63)))
    crn = String(validate=Length(max=255), required=True)


class IBMTransitGatewayConnectionResourceSchema(Schema):
    REF_KEY_TO_RESOURCE_TYPE_MAPPER = {
        "transit_gateway": IBMTransitGateway
    }
    network_type = String(required=True, allow_none=False,
                          description="The network type of the Transit Gateway Connection.")
    name = String(validate=(Regexp(IBM_RESOURCE_NAME_PATTERN), Length(min=1, max=63)),
                  description="The name of the Transit Gateway.")
    prefix_filters_default = String(description="The prefix which will be allowed or denied",
                                    validate=OneOf(IBMTransitGatewayConnection.PREFIX_FILTER_DEFAULT_PERMISSION_LIST))

    vpc = Nested("OptionalIDNameSchema", required=False, description="The network_type VPC to be used as a "
                                                                     "Connection for communication in the "
                                                                     "same region, different region "
                                                                     "or to your IBM Cloud classic"
                                                                     " infrastructure")

    @validates_schema
    def validate_vpc_schema(self, data, **kwargs):
        for connection in data.get("connections", []):
            if connection.get("network_type") == "vpc":
                if not (data.get("vpc", False)):
                    raise ValidationError(
                        "VPC is required for network type 'vpc'"
                    )


class IBMTransitGatewayConnectionInSchema(Schema):
    REF_KEY_TO_RESOURCE_TYPE_MAPPER = {
        "transit_gateway": IBMTransitGateway
    }
    transit_gateway = Nested("IDSchema", required=True,
                             description="The ID of the Transit Gateway the Connection is to be a part of")
    resource_json = Nested("IBMTransitGatewayConnectionResourceSchema", required=True)
    ibm_cloud = Nested("OptionalIDNameSchemaWithoutValidation", required=True)
    prefix_filters = Nested("IBMTransitGatewayConnectionPrefixFilterInSchema", many=True, required=False)
    id = String(required=False, validate=(Regexp(IBM_UUID_PATTERN), Length(equal=32)),
                description="ID of the resource and will be created by FE for Sequential Creation.In Separate API call"
                            " the id from the DB will be used")


class IDSchema(Schema):
    id = String(allow_none=True, validate=(Regexp(IBM_UUID_PATTERN), Length(equal=32)),
                description="ID of the resource on VPC+.")


class IBMTransitGatewayConnectionQuerySchema(IBMResourceQuerySchema):
    transit_gateway_id = String(required=True, allow_none=False, validate=(Regexp(IBM_UUID_PATTERN), Length(equal=32)),
                                description="The ID of the Transit Gateway")
    transit_gateway_connection_id = String(required=True, allow_none=False, validate=(Regexp(IBM_UUID_PATTERN),
                                                                                      Length(equal=32)),
                                           description="The ID of Transit Gateway Connection")


class IBMTransitGatewayConnectionOutSchema(Schema):
    id = String(required=True, allow_none=False, example=uuid.uuid4().hex,
                validate=(Regexp(IBM_UUID_PATTERN), Length(equal=32)))
    name = String(required=True, allow_none=False, validate=(Regexp(IBM_RESOURCE_NAME_PATTERN), Length(min=1, max=63)))
    network_type = String(required=True, allow_none=False,
                          description="The network type of the Transit Gateway Connection.")
    created_at = DateTime(format=DATE_TIME_FORMAT)
    updated_at = DateTime(format=DATE_TIME_FORMAT)
    status = String(required=True, validate=OneOf(IBMTransitGatewayConnection.CONN_STATUSES_LIST))
    prefix_filters = Nested("IBMTransitGatewayConnectionPrefixFilterResourceSchema", many=True)
    ibm_cloud = Nested("IBMCloudRefOutSchema", required=True)
    vpc = Nested("IBMVpcNetworkOutSchema", description="The VPC attached to the Connection")
    prefix_filters_default = String(description="The prefix which will be allowed or denied",
                                    validate=OneOf(IBMTransitGatewayConnection.PREFIX_FILTER_DEFAULT_PERMISSION_LIST))


class IBMTransitGatewayConnectionPrefixFilterResourceSchema(Schema):
    REF_KEY_TO_RESOURCE_TYPE_MAPPER = {}
    action = String(required=True, validate=OneOf(IBMTransitGatewayConnectionPrefixFilter.ACTION_LIST),
                    description="The prefix filter which will be allowed or denied for external "
                                "connection")
    prefix = IPv4CIDR(required=True, description="The CIDR block for this prefix.")
    before = String(
        description="The identifier(resource_id) of the prefix filter to place this filter in front of. When a filter "
                    "references another filter in it's before field, then the filter making the reference"
                    " is applied before the referenced filter.")
    ge = Integer(description="The IP prefix GE. The GE (greater than or equal to) value sets the minimum "
                             "prefix length on which the filter action is applied")
    le = Integer(description="The IP prefix LE. The LE (less than or equal to) value sets the maximum "
                             "prefix length on which the filter action is applied.")


class IBMTransitGatewayConnectionPrefixFilterInSchema(Schema):
    REF_KEY_TO_RESOURCE_TYPE_MAPPER = {
        "transit_gateway_connection": IBMTransitGatewayConnection
    }
    resource_json = Nested("IBMTransitGatewayConnectionPrefixFilterResourceSchema", required=True)
    ibm_cloud = Nested("OptionalIDNameSchemaWithoutValidation", required=True)
    transit_gateway = Nested("IDSchema", required=True,
                             description="The ID of the Transit Gateway the Connection is to be a part of")
    transit_gateway_connection = Nested("IDSchema", required=True,
                                        description="The Transit Gateway Connection ID")
    id = String(required=False, validate=(Regexp(IBM_UUID_PATTERN), Length(equal=32)),
                description="ID of the resource and will be created by FE for Sequential Creation.In Separate API call"
                            " the id from the DB will be used")


class IBMTransitGatewayConnectionPrefixFilterOutSchema(Schema):
    id = String(required=True, allow_none=False, example=uuid.uuid4().hex,
                validate=(Regexp(IBM_UUID_PATTERN), Length(equal=32)))
    action = String(required=True, description="The prefix filter which will be allowed or denied for external "
                                               "connection")
    prefix = IPv4CIDR(required=True, description="The CIDR block for this prefix.")
    before = String(
        description="The identifier of the prefix filter to place this filter in front of. When a filter "
                    "references another filter in it's before field, then the filter making the reference"
                    " is applied before the referenced filter.")
    ge = Integer(description="The IP prefix GE. The GE (greater than or equal to) value sets the minimum "
                             "prefix length on which the filter action is applied")
    le = Integer(description="The IP prefix LE. The LE (less than or equal to) value sets the maximum "
                             "prefix length on which the filter action is appled.")
    ibm_cloud = Nested("IBMCloudRefOutSchema", required=True)
    created_at = DateTime(format=DATE_TIME_FORMAT)
    updated_at = DateTime(format=DATE_TIME_FORMAT)


class IBMListTransitConnectionOutSchema(Schema):
    id = String(required=True, allow_none=False, example=uuid.uuid4().hex,
                validate=(Regexp(IBM_UUID_PATTERN), Length(equal=32)))
    name = String(required=True, allow_none=False, validate=(Regexp(IBM_RESOURCE_NAME_PATTERN), Length(min=1, max=63)))
    network_type = String(required=True, allow_none=False,
                          description="The network type of the Transit Gateway Connection.")
    created_at = DateTime(format=DATE_TIME_FORMAT)
    updated_at = DateTime(format=DATE_TIME_FORMAT)
    status = String(required=True, validate=OneOf(IBMTransitGatewayConnection.CONN_STATUSES_LIST))
    transit_gateway = Nested("IBMTransitGatewayListConnectionOutSchema", required=True)
    prefix_filters = Nested("IBMTransitGatewayConnectionPrefixFilterResourceSchema", many=True)
    ibm_cloud = Nested("IBMCloudRefOutSchema", required=True)
    vpc = Nested("IBMVpcNetworkOutSchema", description="The VPC attached to the Connection")
    prefix_filters_default = String(description="The prefix which will be allowed or denied",
                                    validate=OneOf("permit", "denied"))


class IBMTransitGatewayRouteReportResourceSchema(Schema):
    REF_KEY_TO_RESOURCE_TYPE_MAPPER = {
        "transit_gateway": IBMTransitGateway
    }
    transit_gateway = Nested("OptionalIDNameSchema", required=True,
                             description="The Transit Gateway ID of which the Routes Report to be Generated")


class IBMTransitGatewayRouteReportInSchema(Schema):
    REF_KEY_TO_RESOURCE_TYPE_MAPPER = {}
    resource_json = Nested("IBMTransitGatewayRouteReportResourceSchema", required=True)
    ibm_cloud = Nested("OptionalIDNameSchemaWithoutValidation", required=True)


class IBMTransitGatewayRouteReportConnectionBGPsSchema(Schema):
    prefix = IPv4CIDR(required=True, description="The CIDR block for this prefix.")
    as_path = String(description="AS path.")
    is_used = Boolean(
        description="Shows either the Connection is Used or Not")
    local_preference = String(description="local preference.")


class IBMTransitGatewayRouteReportRoutesSchema(Schema):
    prefix = IPv4CIDR(required=True, description="The CIDR block for this prefix.")


class IBMTransitGatewayRouteReportConnectionsSchema(Schema):
    id = String(required=True, allow_none=False, example=uuid.uuid4().hex,
                validate=(Regexp(IBM_UUID_PATTERN), Length(equal=36)))
    bgps = Nested("IBMTransitGatewayRouteReportConnectionBGPsSchema", many=True)
    name = String(required=True, allow_none=False, validate=(Regexp(IBM_RESOURCE_NAME_PATTERN), Length(min=1, max=63)))
    type = String(required=True, allow_none=False,
                  description="The network type of the Transit Gateway Connection.")
    routes = Nested("IBMTransitGatewayRouteReportRoutesSchema", many=True)


class IBMTransitGatewayRouteReportOverlappingRoutesResourceSchema(Schema):
    connection_id = String(required=True, allow_none=False, example=uuid.uuid4().hex,
                           validate=(Regexp(IBM_UUID_PATTERN), Length(equal=36)))
    prefix = IPv4CIDR(required=True, description="The CIDR block for this prefix.")


class IBMTransitGatewayRouteReportOverlappingRoutesSchema(Schema):
    routes = Nested("IBMTransitGatewayRouteReportOverlappingRoutesResourceSchema", many=True)


class IBMTransitGatewayRouteReportOutSchema(Schema):
    id = String(required=True, allow_none=False, example=uuid.uuid4().hex,
                validate=(Regexp(IBM_UUID_PATTERN), Length(equal=32)))
    connections = Nested("IBMTransitGatewayRouteReportConnectionsSchema", many=True)
    overlapping_routes = Nested("IBMTransitGatewayRouteReportOverlappingRoutesSchema", many=True)
    status = String(required=True, validate=OneOf(IBMTransitGatewayRouteReport.STATUSES_LIST))
    ibm_cloud = Nested("IBMCloudRefOutSchema", required=True)
    created_at = DateTime(format=DATE_TIME_FORMAT)
    updated_at = DateTime(format=DATE_TIME_FORMAT)
