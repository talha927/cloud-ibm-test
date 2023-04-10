from marshmallow import Schema
from marshmallow.fields import Nested

from ibm.models import IBMImage, IBMInstanceTemplate, IBMZone


class IBMInstanceByImagePrototypeSchema(Schema):
    REF_KEY_TO_RESOURCE_TYPE_MAPPER = {
        "zone": IBMZone,
        "image": IBMImage
    }

    image = Nested(
        "OptionalIDNameSchema", required=True,
        description="The 'id' or 'name' of image to use when provisioning the virtual server instance."
    )
    zone = Nested(
        "OptionalIDNameSchema", required=True,
        description="The 'id' or 'name' of the zone this virtual server instance will reside in."
    )
    primary_network_interface = Nested(
        "IBMInstanceNetworkInterfaceResourceSchema", required=True,
        description="Primary Network Interface"
    )
    boot_volume_attachment = Nested(
        "IBMVolumeAttachmentPrototypeInstanceByImageContext",
        description="The boot volume attachment for the virtual server instance"
    )


class IBMInstanceByVolumePrototypeSchema(Schema):
    REF_KEY_TO_RESOURCE_TYPE_MAPPER = {
        "zone": IBMZone,
    }

    zone = Nested(
        "OptionalIDNameSchema", required=True,
        description="The 'id' or 'name' of the zone this virtual server instance will reside in."
    )
    primary_network_interface = Nested(
        "IBMInstanceNetworkInterfaceResourceSchema", required=True,
        description="Primary Network Interface"
    )
    boot_volume_attachment = Nested(
        "IBMVolumeAttachmentPrototypeInstanceByVolumeContext", required=True,
        description="The boot volume attachment for the virtual server instance"
    )


class IBMInstanceBySourceTemplatePrototypeSchema(Schema):
    REF_KEY_TO_RESOURCE_TYPE_MAPPER = {
        "zone": IBMZone,
        "image": IBMImage,
        "source_template": IBMInstanceTemplate
    }

    image = Nested(
        "OptionalIDNameSchema", required=True,
        description="The 'id' or 'name' of image to use when provisioning the virtual server instance."
    )
    source_template = Nested(
        "OptionalIDNameSchema", required=True,
        description="The 'id' or 'name' template to create this virtual server instance from."
    )
    zone = Nested(
        "OptionalIDNameSchema",
        description="The 'id' or 'name' of the zone this virtual server instance will reside in."
    )
    primary_network_interface = Nested(
        "IBMInstanceNetworkInterfaceResourceSchema",
        description="Primary Network Interface"
    )
    boot_volume_attachment = Nested(
        "IBMVolumeAttachmentPrototypeInstanceByImageContext",
        description="The boot volume attachment for the virtual server instance"
    )
