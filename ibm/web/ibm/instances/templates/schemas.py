from marshmallow import Schema, validates_schema, ValidationError
from marshmallow.fields import Boolean, DateTime, Integer, Nested, String
from marshmallow.validate import Length, Regexp

from ibm.common.req_resp_schemas.consts import DATE_TIME_FORMAT, IBM_RESOURCE_NAME_PATTERN
from ibm.models import IBMDedicatedHost, IBMDedicatedHostGroup, IBMImage, IBMInstanceProfile, IBMPlacementGroup, \
    IBMResourceGroup, IBMSshKey, IBMVpcNetwork, IBMZone
from ibm.web.ibm.instances.templates.prototypes import IBMVolumeAttachmentPrototypeInstanceContext


class IBMInstanceTemplatePlacementTargetInSchema(Schema):
    REF_KEY_TO_RESOURCE_TYPE_MAPPER = {
        "dedicated_host": IBMDedicatedHost,
        "dedicated_host_group": IBMDedicatedHostGroup,
        "placement_group": IBMPlacementGroup
    }

    dedicated_host = Nested(
        "OptionalIDNameSchema", description="Either both or one of '['id', 'name']' should be provided."
    )
    dedicated_host_group = Nested(
        "OptionalIDNameSchema", description="Either both or one of '['id', 'name']' should be provided."
    )
    placement_group = Nested(
        "OptionalIDNameSchema", description="Either both or one of '['id', 'name']' should be provided."
    )

    @validates_schema
    def validate_oneof(self, data, **kwargs):
        if not (data.get("dedicated_host") or data.get("dedicated_host_group") or data.get("placement_group")):
            raise ValidationError(
                "Either 'dedicated_host' or 'dedicated_host_group' or 'placement_group' should be provided")


class IBMInstanceTemplatePlacementTargetRefOutSchema(Schema):
    id = String(required=True)
    name = String(required=True)
    zone = String()


class IBMInstanceTemplateResourceSchema(Schema):
    REF_KEY_TO_RESOURCE_TYPE_MAPPER = {
        "zone": IBMZone,
        "profile": IBMInstanceProfile,
        "vpc": IBMVpcNetwork,
        "resource_group": IBMResourceGroup,
        "image": IBMImage,
        "keys": IBMSshKey
    }

    keys = Nested(
        "OptionalIDNameSchema", required=True,
        unique=True, many=True, validate=Length(max=10),
        description="Ssh Keys"
    )
    name = String(required=True, validate=(Length(min=1, max=63), Regexp(IBM_RESOURCE_NAME_PATTERN)))
    network_interfaces = Nested(
        "IBMInstanceNetworkInterfaceResourceSchema", many=True,
        validate=Length(min=0)
    )
    placement_target = Nested(
        "IBMInstanceTemplatePlacementTargetInSchema",
        description="The placement restrictions to use for the virtual server instance."
    )
    profile = Nested(
        "OptionalIDNameSchema", required=True, description="Either both or one of '['id', 'name']' should be provided."
    )
    resource_group = Nested(
        "OptionalIDNameSchemaWithoutValidation",
        description="Either both or one of '['id', 'name']' should be provided."
    )
    bandwidth = Integer(
        example=1000,
        description="The amount of bandwidth (in megabits per second) allocated exclusively to instance storage volumes"
                    ". An increase in this value will result in a corresponding decrease to total_network_bandwidth")
    user_data = String(description="User data to be made available when setting up the virtual server instance")
    volume_attachments = Nested(
        IBMVolumeAttachmentPrototypeInstanceContext, many=True, validate=Length(min=0)
    )
    vpc = Nested(
        "OptionalIDNameSchema",
        description="Either both or one of '['id', 'name']' should be provided."
    )
    instance_by_image = Nested("IBMInstanceByImagePrototypeSchema")
    instance_by_volume = Nested("IBMInstanceByVolumePrototypeSchema")
    instance_by_source_template = Nested("IBMInstanceBySourceTemplatePrototypeSchema")

    @validates_schema
    def validate_oneof(self, data, **kwargs):
        REQUIRED_FIELDS = ["instance_by_image", "instance_by_volume", "instance_by_source_template"]
        available_data = map(lambda field: data.get(field), REQUIRED_FIELDS)

        if not any(available_data):
            raise ValidationError(
                "Either 'instance_by_image' or 'instance_by_volume' or 'instance_by_source_template' should be "
                "provided")


class IBMInstanceTemplateInSchema(Schema):
    REF_KEY_TO_RESOURCE_TYPE_MAPPER = {}

    resource_json = Nested("IBMInstanceTemplateResourceSchema", required=True)
    ibm_cloud = Nested("OptionalIDNameSchemaWithoutValidation", required=True)
    region = Nested("OptionalIDNameSchema", required=True)


class IBMInstanceTemplateOutSchema(Schema):
    id = String(required=True)
    resource_id = String(required=True, allow_none=False)
    name = String(required=True)
    created_at = DateTime(required=True, allow_none=False, format=DATE_TIME_FORMAT)
    resource_group = Nested("IBMResourceGroupRefOutSchema", required=True)
    crn = String(required=True, allow_none=False)
    status = String(required=True)
    href = String(required=True, allow_none=False)
    user_data = String()
    bandwidth = Integer()
    placement_target = Nested("IBMInstanceTemplatePlacementTargetRefOutSchema")
    profile = Nested("IBMInstanceProfileRefOutSchema", required=True)
    ibm_cloud = Nested("IBMCloudRefOutSchema", required=True)
    region = Nested("IBMRegionRefOutSchema", required=True)
    zone = Nested("IBMZoneRefOutSchema")
    vpc = Nested("IBMVpcNetworkRefOutSchema")
    image = Nested("IBMImageRefOutSchema")
    associated_resources = Nested("IBMInstanceTemplateAssociatedResourcesOutSchema", required=True)


class IBMInstanceTemplateAssociatedResourcesOutSchema(Schema):
    network_interfaces = Nested("IBMInstanceNetworkInterfaceRefOutSchema", many=True, required=True)
    keys = Nested("IBMSshKeyRefOutSchema", many=True, required=True)
    dedicated_host_group = Nested("IBMDedicatedHostGroupRefOutSchema")
    dedicated_host = Nested("IBMDedicatedHostRefOutSchema")
    placement_group = Nested("IBMPlacementGroupRefOutSchema")
    volume_attachments = Nested("IBMVolumeAttachmentRefOutSchema", many=True, required=True)


class IBMInstanceTemplateRefOutSchema(IBMInstanceTemplateOutSchema):
    class Meta:
        fields = ("id", "name", "zone")


class IBMInstanceTemplateUpdateSchema(Schema):
    pass


class IBMInstanceTemplateListQuerySchema(Schema):
    it_for_ig = Boolean(allow_none=False,
                        description="if true then listing instance templates will be used for instance groups")
