from apiflask import Schema
from apiflask.fields import Nested, String
from apiflask.validators import Length, Regexp
from marshmallow import validates_schema, ValidationError
from marshmallow.fields import Boolean, DateTime, Integer, List
from marshmallow.validate import OneOf

from ibm.common.consts import COS_FILE_EXTENSIONS
from ibm.common.req_resp_schemas.consts import COS_IMAGE_PATTERN, DATE_TIME_FORMAT, IBM_HREF_PATTERN, \
    IBM_RESOURCE_NAME_PATTERN, IBM_UUID_PATTERN
from ibm.common.req_resp_schemas.schemas import IBMRegionalResourceListQuerySchema
from ibm.models import IBMCOSBucket, IBMImage, IBMOperatingSystem, IBMResourceGroup, IBMVolume, ImageConversionTask
from ibm.web.ibm.images.consts import ALL_VENDORS


class FileSchema(Schema):
    REF_KEY_TO_RESOURCE_TYPE_MAPPER = {
        "bucket": IBMCOSBucket
    }
    cos_bucket_object = String(
        example="abc-image",
        description="The unique user-defined cos object name, This shouldn't include the index decimal with -, "
                    "if cos object name is abc-img-0.qcow2, then abc-img should be provided only"
    )
    object_type = String(validate=OneOf(COS_FILE_EXTENSIONS))
    bucket = Nested("OptionalIDNameSchema",
                    description="OneOf name or uuid of the bucket.")
    href = String(allow_none=False, validate=(Regexp(COS_IMAGE_PATTERN)),
                  descrption="href for the bucket object.")

    @validates_schema
    def validate_one_of_schema(self, data, **kwargs):
        if not (data.get("href") or data.get("bucket")):
            raise ValidationError(
                "OneOf fields `href` or `bucket` should be provided.")


class IBMImageResourceSchema(Schema):
    REF_KEY_TO_RESOURCE_TYPE_MAPPER = {
        "resource_group": IBMResourceGroup,
        "operating_system": IBMOperatingSystem,
        "source_volume": IBMVolume
    }
    name = String(allow_none=False, required=True, validate=(Regexp(IBM_RESOURCE_NAME_PATTERN), Length(min=1, max=63)),
                  description="The unique user-defined name for this image")
    resource_group = Nested("OptionalIDNameSchemaWithoutValidation", required=True)
    encrypted_key = String(validate=(Length(min=1)),
                           description="The key that will be used to encrypt volumes created from this image")
    encrypted_data_key = String(validate=(Length(min=1)),
                                description="A base64-encoded, encrypted representation of the key that was used to "
                                            "encrypt the data for this image.")
    source_volume = Nested(
        "OptionalIDNameSchema",
        description="Only source volume is required. (Don't add file or operating system with source volume)"
    )
    operating_system = Nested(
        "OptionalIDNameSchema", many=False,
        description="File is required along with operating system. (Don't add source volume)"
    )
    file = Nested(
        "FileSchema", many=False,
        description="Operating system is required along with file. (Don't add source volume)."
                    "OneOf `href` or `bucket` key should be provided.")

    @validates_schema
    def validate_one_of_schema(self, data, **kwargs):
        if not (data.get("source_volume") or (data.get("file") and data.get("operating_system"))):
            raise ValidationError(
                "One of fields 'file' with operating_system or 'source_volume' is required.")
        if data.get("source_volume") and (data.get("file") and data.get("operating_system")):
            raise ValidationError(
                "Only one of fields 'file' with operating_system OR 'source_volume' is required.")
        if data.get("file") and not data["file"].get("href"):
            raise ValidationError("href is required in file object")


class IBMImageInSchema(Schema):
    REF_KEY_TO_RESOURCE_TYPE_MAPPER = {}

    resource_json = Nested(IBMImageResourceSchema, required=True)
    ibm_cloud = Nested("OptionalIDNameSchemaWithoutValidation", required=True)
    region = Nested("OptionalIDNameSchema", required=True)


class IBMOperatingSystemOutSchema(Schema):
    id = String(validate=Length(equal=32), required=True,
                description="The unique identifier for this os")
    name = String(allow_none=False, validate=(Regexp(IBM_RESOURCE_NAME_PATTERN), Length(min=1, max=63)),
                  description="The globally unique name for this operating system")
    architecture = String(validate=Length(min=1), required=True, description="The operating system architecture")
    dedicated_host_only = Boolean(required=True,
                                  description="Images with this operating system can only be used on dedicated hosts "
                                              "or dedicated host groups")
    display_name = String(allow_none=False, validate=(Regexp(IBM_RESOURCE_NAME_PATTERN), Length(min=1, max=63)),
                          description="A unique, display-friendly name for the operating system")
    family = String(required=True, allow_none=False, validate=Length(min=1),
                    description="The name of the software family this operating system belongs to")
    href = String(validate=(Regexp(IBM_HREF_PATTERN)), required=True, description="The URL for this operating system")
    vendor = String(validate=Length(min=1), required=True, description="The vendor of the operating system")
    version = String(validate=Length(min=1), required=True,
                     description="The major release version of this operating system")


class IBMOperatingSystemRefOutSchema(IBMOperatingSystemOutSchema):
    class Meta:
        fields = ("id", "name", "architecture", "vendor")


class IBMOperatingSystemValidateJsonResourceSchema(IBMOperatingSystemOutSchema):
    class Meta:
        fields = ("id", "name", "architecture", "vendor")


class IBMOperatingSystemValidateJsonOutSchema(Schema):
    id = String(
        required=True, allow_none=False, validate=[Length(equal=32), Regexp(IBM_UUID_PATTERN)],
        description="Unique ID of the IBM Operating System"
    )
    resource_json = Nested(IBMOperatingSystemValidateJsonResourceSchema, required=True)


class IBMOperatingSystemQuerySchema(IBMRegionalResourceListQuerySchema):
    family = String(required=False, allow_none=False, validate=OneOf(IBMOperatingSystem.ALL_FAMILIES),
                    description="The name of the software family this operating system belongs to")
    vendor = String(required=False, description="The vendor of the operating system",
                    validate=OneOf(ALL_VENDORS))
    architecture = String(required=False, description="The architecture of the operating system",
                          validate=OneOf(IBMOperatingSystem.ALL_ARCHITECTURES))
    dedicated_host_only = Boolean(required=False,
                                  description="Images with this operating system can only be used on dedicated hosts "
                                              "or dedicated host groups")


class IBMImageOutSchema(Schema):
    id = String(validate=Length(equal=32), required=True, description="The unique identifier for this image")
    name = \
        String(
            allow_none=False, validate=(Regexp(IBM_RESOURCE_NAME_PATTERN), Length(min=1, max=63)),
            description="The unique user-defined name for this image"
        )
    crn = String(validate=Length(max=255), required=True, description="The CRN for this image")
    resource_id = String(required=True, allow_none=False, description="Unique ID on IBM Cloud")
    visibility = \
        String(
            required=True, allow_none=False, validate=(Length(min=1), OneOf(IBMImage.All_VISIBLE_CONSTS)),
            description="Whether the image is publicly visible or private to the account"
        )
    href = String(validate=(Regexp(IBM_HREF_PATTERN)), required=True, description="The URL for this image")
    created_at = DateTime(format=DATE_TIME_FORMAT, required=True)
    encryption = \
        String(
            required=True, allow_none=False, validate=(Length(min=1), OneOf(IBMImage.ALL_ENCRYPTION_CONSTS)),
            description="The type of encryption used on the image"
        )
    status = String(required=True, validate=(OneOf(IBMImage.ALL_STATUS_CONSTS)))
    ibm_status_reasons = String(validate=Length(equal=32), description="The reasons for the current status (if any)")
    encryption_key_crn = \
        String(
            required=True, allow_none=False, validate=(Length(min=1)),
            description="The key that will be used to encrypt volumes created from this image"
        )
    minimum_provisioned_size = \
        Integer(
            required=True,
            description="The minimum size (in gigabytes) of a volume onto which this image may be provisioned."
        )
    file_checksums_sha256 = String(required=True, description="Checksum of this image file")
    file_size = Integer(required=True, description="Size of the image")
    operating_system = Nested("IBMOperatingSystemOutSchema", required=True)
    source_volume = Nested("IBMVolumeRefOutSchema", required=True)
    ibm_cloud = Nested("IBMCloudRefOutSchema", required=True)
    resource_group = Nested("IBMResourceGroupRefOutSchema", required=True)
    region = Nested("IBMRegionRefOutSchema", required=True)


class IBMImageRefOutSchema(IBMImageOutSchema):
    class Meta:
        fields = ("id", "name")


class IBMImageValidateJsonResourceSchema(Schema):
    class Meta:
        fields = ("name",)


class IBMImageOperatingSystemMappingSchema(Schema):
    operating_system = Nested(IBMOperatingSystemRefOutSchema)
    image = Nested(IBMImageRefOutSchema)


class IBMImageOperatingSystemMappingOutSchema(Schema):
    name = String(required=True)
    values = Nested(IBMImageOperatingSystemMappingSchema, many=True)


class IBMOperatingSystemMappingOutSchema(Schema):
    items = Nested(IBMImageOperatingSystemMappingOutSchema, many=True, required=True)


class IBMOperatingSystemMappingInSchema(Schema):
    names = List(String(required=True), required=True)
    region_id = String(required=True)


class IBMImageValidateJsonOutSchema(Schema):
    id = String(
        required=True, allow_none=False, validate=[Length(equal=32), Regexp(IBM_UUID_PATTERN)],
        description="Unique ID of the IBM Image"
    )
    resource_json = Nested(IBMImageValidateJsonResourceSchema, required=True)


class IBMImageUpdateSchema(Schema):
    name = String(allow_none=False, required=True, validate=(Regexp(IBM_RESOURCE_NAME_PATTERN), Length(min=1, max=63)),
                  description="The unique user-defined name for this image")


class IBMImageVisibilitySchema(IBMRegionalResourceListQuerySchema):
    visibility = String(allow_none=False, validate=OneOf(IBMImage.All_VISIBLE_CONSTS), example="public")
    vendor = String(required=False, description="The vendor of the operating system",
                    validate=OneOf(ALL_VENDORS))


class IBMImageMigrationUpdateSchema(Schema):
    step = String(required=True, validate=OneOf(["DOWNLOAD", "CONVERT", "VALIDATE", "UPLOAD"]))
    status = String(required=True,
                    validate=OneOf([ImageConversionTask.STATUS_SUCCESSFUL, ImageConversionTask.STATUS_FAILED]))
    message = String()


class IBMOperatingSystemProvidersSchema(Schema):
    vendors = List(
        String(required=True, validate=OneOf(IBMOperatingSystem.ALL_VENDORS), example="Rocky Linux"),
        required=True)
    families = List(
        String(
            required=True, allow_none=False, validate=OneOf(IBMOperatingSystem.ALL_FAMILIES),
            description="The name of the family this operating system belongs to"),
        required=True)


class IBMCustomImageInSchema(Schema):
    REF_KEY_TO_RESOURCE_TYPE_MAPPER = {
        "image_name": IBMImage
    }

    cloud_id = String(validate=(Regexp(IBM_UUID_PATTERN), Length(equal=32)), required=False,
                      description="ID of the IBM Cloud.")
    region = String(
        required=True, allow_none=False, validate=(Regexp(IBM_RESOURCE_NAME_PATTERN),
                                                   Length(min=1, max=255)), description="The name for the Region")
    image_name = String(allow_none=False, required=True, description="Name of the custom image")
