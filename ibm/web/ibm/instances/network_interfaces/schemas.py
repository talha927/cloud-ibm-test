import uuid

from apiflask.fields import Boolean, DateTime, Integer, Nested, String
from apiflask.schemas import Schema
from apiflask.validators import Length, OneOf, Regexp
from marshmallow.validate import Range

from ibm.common.req_resp_schemas.consts import DATE_TIME_FORMAT, IBM_HREF_PATTERN, IBM_RESOURCE_NAME_PATTERN
from ibm.common.req_resp_schemas.fields import IPv4
from ibm.common.req_resp_schemas.schemas import IBMResourceRefSchema
from ibm.models import IBMInstance, IBMNetworkInterface, IBMSecurityGroup, IBMSubnet


class PrimaryIPSchema(Schema):
    address = IPv4(
        required=True, example="192.23.42.13",
        description="The primary IPv4 address. If specified, it must be an available address on the network "
                    "interface's subnet. If unspecified, an available address on the subnet will be automatically "
                    "selected"
    )

    auto_delete = Boolean(default=False)
    # TODO existing Reserved IP ID should also be provided


class IBMInstanceNetworkInterfaceResourceSchema(Schema):
    REF_KEY_TO_RESOURCE_TYPE_MAPPER = {
        "subnet": IBMSubnet,
        "security_groups": IBMSecurityGroup
    }
    id = String(allow_none=False, example=uuid.uuid4().hex, format="uuid", validate=[Length(equal=32)])
    name = String(required=True, allow_none=False, validate=(Regexp(IBM_RESOURCE_NAME_PATTERN), Length(min=1, max=63)),
                  description="User defined unique name of the network interface")
    allow_ip_spoofing = Boolean(default=False)
    floating_ip = Boolean(default=False)
    primary_ip = Nested(PrimaryIPSchema, required=False)
    subnet = Nested(
        "OptionalIDNameSchema", required=True,
        description="Either both or one of '['id', 'name']' should be provided."
    )
    security_groups = Nested(
        "OptionalIDNameSchema", many=True,
        description="Either both or one of '['id', 'name']' should be provided."
    )


class IBMInstanceNetworkInterfaceInSchema(Schema):
    REF_KEY_TO_RESOURCE_TYPE_MAPPER = {
        "instance": IBMInstance
    }

    resource_json = Nested(IBMInstanceNetworkInterfaceResourceSchema, required=True)
    ibm_cloud = Nested("OptionalIDNameSchemaWithoutValidation", required=True)
    region = Nested("OptionalIDNameSchema", required=True)
    instance = Nested(
        "OptionalIDNameSchema", required=True,
        description="Either both or one of '['id', 'name']' should be provided."
    )


class IBMInstanceNetworkInterfaceOutSchema(Schema):
    id = String(required=True, allow_none=False, example=uuid.uuid4().hex, format="uuid", validate=[Length(equal=32)])
    name = \
        String(
            required=True, allow_none=False, validate=(Regexp(IBM_RESOURCE_NAME_PATTERN), Length(min=1, max=63)),
            description="User defined unique name of the network interface"
        )
    is_primary = Boolean(required=True)
    resource_id = String(required=True, allow_none=False, description="Unique ID on IBM Cloud")
    created_at = DateTime(format=DATE_TIME_FORMAT, required=True)
    allow_ip_spoofing = Boolean(default=False, required=True)
    href = String(required=True, validate=Regexp(IBM_HREF_PATTERN))
    port_speed = Integer(required=True, validate=Range(min=1))
    primary_ipv4_address = IPv4(required=True, example="192.23.42.13", description="The primary IPv4 address")
    resource_type = String(default=IBMNetworkInterface.TYPE_NETWORK_INTERFACE, required=True)
    ibm_status = \
        String(
            required=True, default=IBMNetworkInterface.STATUS_AVAILABLE,
            validate=OneOf(IBMNetworkInterface.ALL_STATUSES_LIST)
        )
    type_ = String(data_key="type", required=True, validate=OneOf(IBMNetworkInterface.ALL_INTERFACES_TYPES))
    ibm_cloud = Nested("IBMCloudRefOutSchema", required=True)
    associated_resources = Nested(
        "IBMInstanceNetworkInterfaceAssociatedResourcesOutSchema", required=True
    )


class IBMInstanceNetworkInterfaceAssociatedResourcesOutSchema(Schema):
    subnet = Nested("IBMSubnetRefOutSchema", required=True)
    instance = Nested("IBMInstanceRefOutSchema", required=True)
    floating_ips = Nested("IBMFloatingIpRefOutSchema", many=True, required=True)
    security_groups = Nested("IBMSecurityGroupRefOutSchema", many=True, required=True)


class IBMInstanceNetworkInterfaceRefOutSchema(IBMInstanceNetworkInterfaceOutSchema):
    class Meta:
        fields = ("id", "name", "primary_ipv4_address", "is_primary", "allow_ip_spoofing", "subnet",
                  "security_groups", "floating_ips")


class IBMInstanceNetworkInterfaceUpdateSchema(Schema):
    ibm_cloud = Nested(IBMResourceRefSchema, required=True)
    name = String(required=True, allow_none=False, validate=Length(min=1, max=63),
                  description="User defined unique name of the cloud account")
    allow_ip_spoofing = Boolean()
