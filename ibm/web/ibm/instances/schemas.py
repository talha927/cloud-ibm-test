import uuid

from apiflask.fields import Boolean, DateTime, Integer, List, Nested, String
from apiflask.schemas import Schema
from apiflask.validators import Length, OneOf, Regexp
from marshmallow import validates_schema, ValidationError
from marshmallow.fields import Dict
from marshmallow.validate import Range

from ibm.common.consts import FAILED, IN_PROGRESS, PENDING, SUCCESS
from ibm.common.req_resp_schemas.consts import IBM_RESOURCE_NAME_PATTERN, IBM_UUID_PATTERN
from ibm.common.req_resp_schemas.schemas import IBMSubnetZonalResourceListQuerySchema
from ibm.models import IBMDedicatedHost, IBMDedicatedHostGroup, IBMImage, IBMInstance, IBMInstanceProfile, \
    IBMInstanceTemplate, IBMOperatingSystem, IBMPlacementGroup, IBMResourceGroup, IBMSshKey, IBMVpcNetwork, IBMZone
from ibm.web.ibm.instances.consts import InstanceMigrationConsts


class VCPUSchema(Schema):
    architecture = String(required=True, allow_none=False, example="amd64")
    count = Integer(required=True, validate=Range(min=1), example=4)


class PlacementTargetSchema(Schema):
    REF_KEY_TO_RESOURCE_TYPE_MAPPER = {
        "dedicated_host_group": IBMDedicatedHostGroup,
        "dedicated_host": IBMDedicatedHost,
        "placement_group": IBMPlacementGroup
    }
    dedicated_host_group = Nested(
        "OptionalIDNameSchema",
        description="Either both or one of '['id', 'name']' should be provided."
    )
    dedicated_host = Nested(
        "OptionalIDNameSchema",
        description="Either both or one of '['id', 'name']' should be provided."
    )
    placement_group = Nested(
        "OptionalIDNameSchema",
        description="Either both or one of '['id', 'name']' should be provided."
    )

    @validates_schema
    def validate_schema(self, in_data, **kwargs):
        if not in_data.get("dedicated_host_group") and not in_data.get("dedicated_host") and not in_data.get(
                "placement_group"):
            raise ValidationError("One of DedicatedHost or DedicatedHostGroup or PlacementGroup must be provided")
        if in_data.get("dedicated_host_group") and (in_data.get("dedicated_host") or in_data.get(
                "placement_group")):
            raise ValidationError("Only One of DedicatedHost or DedicatedHostGroup or PlacementGroup must be provided")
        if (in_data.get("dedicated_host_group") or (in_data.get("dedicated_host")) and in_data.get(
                "placement_group")):
            raise ValidationError("Only One of DedicatedHost or DedicatedHostGroup or PlacementGroup must be provided")
        if in_data.get("dedicated_host") and (in_data.get("dedicated_host_group") or in_data.get(
                "placement_group")):
            raise ValidationError("Only One of DedicatedHost or DedicatedHostGroup or PlacementGroup must be provided")


class IBMInstanceResourceSchema(Schema):
    REF_KEY_TO_RESOURCE_TYPE_MAPPER = {
        "keys": IBMSshKey,
        "profile": IBMInstanceProfile,
        "resource_group": IBMResourceGroup,
        "vpc": IBMVpcNetwork,
        "zone": IBMZone,
        "image": IBMImage,
        "source_template": IBMInstanceTemplate
    }
    name = String(required=True, allow_none=False, validate=(Regexp(IBM_RESOURCE_NAME_PATTERN)),
                  description="User defined name of the instance")
    keys = Nested(
        "OptionalIDNameSchema", required=True, many=True,
        description="Either both or one of '['id', 'name']' should be provided.")
    network_interfaces = List(Nested("IBMInstanceNetworkInterfaceResourceSchema"), validate=Length(min=0))
    placement_target = Nested(
        "PlacementTargetSchema",
        description="One of ['dedicated host group', 'placement group', 'Dedicated Host'] should be provided."
    )
    profile = Nested(
        "OptionalIDNameSchema", required=True,
        description="Either both or one of '['id', 'name']' should be provided."
    )
    resource_group = Nested(
        "OptionalIDNameSchemaWithoutValidation", required=True,
        description="Either both or one of '['id', 'name']' should be provided."
    )
    total_volume_bandwidth = Integer(
        example=1000,
        description="The amount of bandwidth (in megabits per second) allocated exclusively to instance storage "
                    "volumes. An increase in this value will result in a corresponding decrease to "
                    "total_network_bandwidth"
    )
    user_data = String(
        description="user_data should not be provided with migration_json and user_data to be made available when "
                    "setting up the virtual server instance. More Information can be found [here]("
                    "https://cloud.ibm.com/docs/vpc?topic=vpc-user-data)"
    )
    volume_attachments = Nested("IBMVolumeAttachmentResourceSchema", many=True, validate=Length(min=0, max=4))
    vpc = Nested(
        "OptionalIDNameSchema", required=True,
        description="Either both or one of '['id', 'name']' should be provided."
    )
    zone = Nested(
        "OptionalIDNameSchema", required=True,
        description="Either both or one of '['id', 'name']' should be provided."
    )
    primary_network_interface = Nested("IBMInstanceNetworkInterfaceResourceSchema", required=True)
    boot_volume_attachment = Nested("IBMBootVolumeAttachmentResourceSchema", required=True)
    image = Nested(
        "OptionalIDNameSchema",
        description="Either both or one of '['id', 'name']' should be provided."
    )
    source_template = Nested(
        "OptionalIDNameSchema",
        description="Either both or one of '['id', 'name']' should be provided."
    )


class FEExtrasSecondaryVolumeSchema(Schema):
    bucket_id = String()
    bock_file = Dict()
    volumes = Nested("IBMVolumeResourceSchema", many=True)


class FEExtrasSchema(Schema):
    primary_volume = String()
    cloud_object_storage_for_primary_volume = String()
    cloud_object_storage_for_secondary_volume = String()
    selected_volume_index = List(Integer())
    secondary_volume = Nested(FEExtrasSecondaryVolumeSchema)


class IBMInstanceMigrationSchema(Schema):
    REF_KEY_TO_RESOURCE_TYPE_MAPPER = {
        "operating_system": IBMOperatingSystem
    }
    migrate_from = String(validate=OneOf(InstanceMigrationConsts.ALL_MIGRATION_USE_CASES))
    operating_system = Nested("OptionalIDNameSchemaWithoutValidation")
    # From COS Bucket, COS bucket name is mandatory, while cos bucket object will be set if option is any from classic
    # Instance and classic Image, while should be provided if option is from COS bucket
    file = Nested(
        "FileSchema",
        description=f"Operating system is required along with file. (Don't add source volume),bucket will be provided"
                    f" only if option is any in {InstanceMigrationConsts.CLASSIC_VSI}, "
                    f"{InstanceMigrationConsts.CLASSIC_IMAGE}. While href will be provided if option is from "
                    f"{InstanceMigrationConsts.COS_BUCKET_USE_CASES}"
    )
    classic_account_id = String(
        description=f"'classic_account_id' is required fields for {InstanceMigrationConsts.CLASSIC_VSI}, "
                    f"{InstanceMigrationConsts.CLASSIC_IMAGE} and {InstanceMigrationConsts.ONLY_VOLUME_MIGRATION}"
    )
    classic_instance_id = Integer(
        exmaple=3456546234,
        description=f"'classic_instance_id' is required fields for {InstanceMigrationConsts.CLASSIC_VSI} and "
                    f"{InstanceMigrationConsts.ONLY_VOLUME_MIGRATION}"
    )
    is_volume_migration = Boolean(
        description=f"'is_volume_migration' is required volume migration. It can only be `True/true` for "
                    f"{InstanceMigrationConsts.CLASSIC_VSI} and {InstanceMigrationConsts.ONLY_VOLUME_MIGRATION} "
                    f"otherwise will be `False/false`"
    )
    # Snapshot, If Classic Instance selected for Migration these two should be updated in create_snapshot_task
    classic_image_name = String(validate=(Regexp(IBM_RESOURCE_NAME_PATTERN)))
    classic_image_id = Integer(
        exmaple=3456546234,
        description=f"'classic_instance_id' is required fields for {InstanceMigrationConsts.CLASSIC_IMAGE}"
    )
    # TODO Nas migration Volumes, There should be a schema for this .. but for now FE will have to provide
    #  un-changed json which BE has provided
    nas_migration = List(Dict(description="There isn't any validation for now on this but will be added to make more"
                                          " tightened Schema"))
    auto_scale_group = String(allow_none=True)
    newly_fetched = Boolean(default=False)
    cloud_object_storage_id = String(allow_none=True)
    bucket_id = String(allow_none=True)
    os_vendor = String(allow_none=True)
    data_center = String(allow_none=True)
    create_vpc_allow_all_security_group = Boolean(
        Description="True if an allow all security need to be created for NAS or Secondary Volume Migration"
    )
    volume_attachments = List(Dict(allow_none=True))
    volume_migration = Dict(allow_none=True)
    nas_volume_migration = Dict(allow_none=True)
    image = Dict(allow_none=True)
    instance_type = String(allow_none=True)

    @validates_schema
    def validate_one_of_schema(self, data, **kwargs):
        migrate_from = data.get("migrate_from")
        if migrate_from == InstanceMigrationConsts.CLASSIC_VSI:
            if not (data.get("classic_account_id") and data.get("classic_instance_id")):
                raise ValidationError(f"classic_account_id and classic_instance_id are required "
                                      f"fields for {InstanceMigrationConsts.CLASSIC_VSI}")

        if migrate_from == InstanceMigrationConsts.CLASSIC_IMAGE:
            if not (data.get("classic_account_id") and data["file"].get("bucket") and
                    data.get("classic_image_id")):
                raise ValidationError(
                    f"classic_account_id, classic_image_id and bucket within file are required "
                    f"fields for {InstanceMigrationConsts.CLASSIC_IMAGE}")

        if migrate_from in InstanceMigrationConsts.COS_BUCKET_USE_CASES:
            if not data["file"].get("href"):
                raise ValidationError(
                    f"href in file object is a required field for {data['migrate_from']}")

        # TODO look for a way to validate number of disks attached must be >= 1
        # if data["migrate_from"] == InstanceMigrationConsts.ONLY_VOLUME_MIGRATION:
        if data.get("is_volume_migration") and not (data.get("classic_account_id") and data.get("classic_instance_id")):
            raise ValidationError("classic_account_id, classic_instance_id are required for only Volume migration")


class IBMInstanceInSchema(Schema):
    REF_KEY_TO_RESOURCE_TYPE_MAPPER = {}

    resource_json = Nested(IBMInstanceResourceSchema, required=True)
    ibm_cloud = Nested("OptionalIDNameSchemaWithoutValidation", required=True)
    region = Nested("OptionalIDNameSchema", required=True)
    migration_json = Nested(IBMInstanceMigrationSchema, description="This object depends on migration scenarios")

    @validates_schema
    def validate_one_of_schema(self, data, **kwargs):
        if data["resource_json"].get("user_data") and data.get("migration_json"):
            raise ValidationError("user_data should not be provided with migration_json")


class IBMInstanceStatusQuerySchema(IBMSubnetZonalResourceListQuerySchema):
    status = String(
        validate=OneOf(IBMInstance.ALL_STATUSES_LIST),
        description="The status of an Instance on IBM Cloud."
    )


class IBMInstanceOutSchema(Schema):
    id = String(required=True, allow_none=False, example=uuid.uuid4().hex,
                validate=(Regexp(IBM_UUID_PATTERN), Length(equal=32)))
    resource_id = String(required=True, allow_none=False)
    name = String(required=True, allow_none=False, validate=(Regexp(IBM_RESOURCE_NAME_PATTERN)),
                  description="User defined name of the instance")
    crn = String(required=True, allow_none=False)
    usage = Dict(required=False, allow_none=False)
    created_at = DateTime(required=True, allow_none=False)
    volume_migration_report = Dict()
    status = String(required=True, validate=OneOf(IBMInstance.ALL_STATUSES_LIST))
    href = String(required=True, allow_none=False)
    memory = Integer(required=True, validate=Range(min=1, max=512))
    bandwidth = Integer(required=True, example=1000)
    gpu = Nested(VCPUSchema, allow_none=True)
    status_reasons = List(String(validate=OneOf(IBMInstance.ALL_STATUS_REASONS_LIST), default=[]))
    startable = Boolean(
        required=True,
        description="Indicates whether the state of the virtual server instance permits a start request.")
    vcpu = Nested(VCPUSchema, required=True)

    disks = Nested("IBMInstanceDiskRefOutSchema", required=True, many=True)
    # placement_target = Nested(,description="Either ID or Name of the`dedicated host group` **OR** `placement group`
    # **OR**"
    #                 " `Dedicated Host` is required,")
    region = Nested("IBMRegionRefOutSchema", description="Region reference of the instance", required=True)
    zone = Nested("IBMZoneRefOutSchema", required=True)
    vpc = Nested("IBMVpcNetworkRefOutSchema", required=True)
    ibm_cloud = Nested("IBMCloudRefOutSchema", description="IBM Cloud reference of the instance", required=True)
    profile = Nested("IBMInstanceProfileRefOutSchema", required=True)
    resource_group = Nested("IBMResourceGroupRefOutSchema", required=True)
    image = Nested("IBMImageRefOutSchema", description="Image of the instance")
    # total_volume_bandwidth = Integer(
    #     example=1000,
    #     description="The amount of bandwidth (in megabits per second) allocated exclusively to instance storage "
    #                 "volumes. An increase in this value will result in a corresponding decrease to "
    #                 "total_network_bandwidth")
    # TODO
    # primary_network_interface = Nested("IBMInstanceNetworkInterfaceResourceSchema", required=True)
    # boot_volume_attachment = Nested("IBMVolumeAttachmentResourceSchema", required=True)
    # source_template = Nested(description="Either ID or Name of the`instance_template` is required.")
    associated_resources = Nested("IBMInstanceAssociatedResourcesOutSchema", required=True)


class IBMInstanceAssociatedResourcesOutSchema(Schema):
    network_interfaces = Nested("IBMInstanceNetworkInterfaceRefOutSchema", many=True, required=True)
    primary_network_interface = Nested("IBMInstanceNetworkInterfaceRefOutSchema", required=True)
    keys = List(Nested("IBMSshKeyRefOutSchema", description="SSH Keys references of the instance"))
    dedicated_host_group = Nested("IBMDedicatedHostGroupRefOutSchema")
    dedicated_host = Nested("IBMDedicatedHostRefOutSchema")
    placement_group = Nested("IBMPlacementGroupRefOutSchema")
    volume_attachments = Nested("IBMVolumeAttachmentRefOutSchema", many=True, required=True)
    boot_volume_attachment = Nested("IBMVolumeAttachmentRefOutSchema", required=True)


class IBMInstanceRefOutSchema(IBMInstanceOutSchema):
    class Meta:
        fields = ("id", "name", "zone", "profile", "image", "status", "usage", "primary_network_interface")


class IBMInstanceValidateJsonResourceSchema(Schema):
    class Meta:
        fields = ("name", "zone", "profile", "image")


class IBMInstanceValidateJsonOutSchema(Schema):
    id = String(
        required=True, allow_none=False, validate=[Length(equal=32), Regexp(IBM_UUID_PATTERN)],
        description="Unique ID of the IBM Instance"
    )
    resource_json = Nested(IBMInstanceValidateJsonResourceSchema, required=True)


class IBMInstanceUpdateSchema(Schema):
    name = String(allow_none=False, validate=(Regexp(IBM_RESOURCE_NAME_PATTERN)))
    total_volume_bandwidth = Integer(
        example=1000,
        description="The amount of bandwidth (in megabits per second) allocated exclusively to instance storage volumes"
                    ". An increase in this value will result in a corresponding decrease to total_network_bandwidth"
    )
    profile = Nested(
        "IBMInstanceProfileOutSchema", only=("name",),
        description="The profile to use for this virtual server instance. For the profile to be changed, the instance "
                    "status must be *stopping or stopped*. In addition, the requested profile must have matching "
                    "instance disk support. Any disks associated with the current profile will be deleted, and any "
                    "disks associated with the requested profile will be created. Be compatible with any "
                    "placement_target constraints. For example, if the instance is placed on a dedicated host, the "
                    "requested profile family must be the same as the dedicated host family"
    )


class IBMVolumeMigrationResourceSchema(Schema):
    message = String(required=False)
    name = String(required=False, validate=Length(max=63))
    size = String(required=False, validate=Length(max=32))
    download_speed = String(required=False, validate=Length(max=32))
    start_time = String(required=False, validate=Length(max=32))
    end_time = String(required=False, validate=Length(max=32))
    duration = String(required=False, validate=Length(max=32))
    eta = String(required=False, validate=Length(max=32))
    action = String(required=False, allow_none=False)
    status = String(required=True, validate=OneOf([IN_PROGRESS, FAILED, SUCCESS, PENDING]))
    trace = String(required=False, allow_none=True)


class IBMInstanceVolumeMigrationUpdateSchema(Schema):
    status = String(required=True, validate=OneOf([IN_PROGRESS, FAILED, SUCCESS, PENDING]))
    resources = Nested(IBMVolumeMigrationResourceSchema, required=True, many=True)
    start_time = String(required=False, validate=Length(max=32))
    end_time = String(required=False, validate=Length(max=32))
    duration = String(required=False, validate=Length(max=32))
    action = String(required=False, allow_none=False)
    message = String(required=False)


class IBMRightSizeResourceSchema(Schema):
    REF_KEY_TO_RESOURCE_TYPE_MAPPER = {
        "profile": IBMInstanceProfile
    }

    profile = Nested(
        "OptionalIDNameSchemaWithoutValidation", required=True,
        description="Either both or one of '['id', 'name']' should be provided."
    )
    instance_id = String(required=True, allow_none=False, example=uuid.uuid4().hex,
                         validate=(Regexp(IBM_UUID_PATTERN), Length(equal=32)))


class IBMRightSizeInSchema(Schema):
    REF_KEY_TO_RESOURCE_TYPE_MAPPER = {}

    resource_json = Nested(IBMRightSizeResourceSchema, required=True)
    region = Nested("OptionalIDNameSchema", only=("id",), required=True)


class IBMStartStopSchema(Schema):
    REF_KEY_TO_RESOURCE_TYPE_MAPPER = {}
    ibm_cloud = Nested("OptionalIDNameSchemaWithoutValidation", required=True)
    instance_ids = List(String(required=True, allow_none=False, example=uuid.uuid4().hex,
                               validate=(Regexp(IBM_UUID_PATTERN), Length(equal=32))), validate=Length(min=1))
    action = String(required=True, validate=OneOf(["stop", "start"]))
