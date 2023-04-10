import uuid
from datetime import datetime

from sqlalchemy import Boolean, Column, DateTime, Enum, ForeignKey, Integer, JSON, String, Text
from sqlalchemy.orm import backref, relationship

from ibm import get_db_session as db
from ibm.common.consts import CREATED_AT_FORMAT
from ibm.common.utils import LOGGER
from ibm.models.base import Base
from ibm.models.ibm.mixins import IBMRegionalResourceMixin


class IBMImage(IBMRegionalResourceMixin, Base):
    ID_KEY = "id"
    NAME_KEY = "name"
    CRN_KEY = "crn"
    RESOURCE_ID_KEY = "resource_id"
    VISIBILITY_KEY = "visibility"
    STATUS_KEY = "status"
    HREF_KEY = "href"
    CREATED_AT_KEY = "created_at"
    ENCRYPTION_KEY = "encryption"
    IBM_STATUS_REASONS_KEY = "ibm_status_reasons"
    ENCRYPTION_KEY_CRN_KEY = "encryption_key_crn"
    MINIMUM_PROVISIONED_SIZE_KEY = "minimum_provisioned_size"
    FILE_CHECKSUMS_SHA256_KEY = "file_checksums_sha256"
    FILE_SIZE_KEY = "file_size"
    RESOURCE_GROUP_KEY = "resource_group"
    OPERATING_SYSTEM_KEY = "operating_system"
    SOURCE_VOLUME_KEY = "source_volume"
    RESOURCE_JSON_KEY = "resource_json"
    RESOURCE_TYPE_KEY = "resource_type"
    RESOURCE_TYPE_IMAGE_KEY = "Custom Image"
    COST_KEY = "cost"
    ESTIMATED_SAVINGS = "estimated_savings"
    OS_VENDOR_KEY = "os_vendor"
    OS_VERSION_KEY = "os_version"
    OS_NAME_KEY = "os_name"

    CRZ_BACKREF_NAME = "images"

    # encryption type
    ENCRYPTION_TYPE_NONE = "none"
    ENCRYPTION_TYPE_USER_MANAGED = "user_managed"

    ALL_ENCRYPTION_CONSTS = [ENCRYPTION_TYPE_NONE, ENCRYPTION_TYPE_USER_MANAGED]
    # visibility consts
    TYPE_VISIBLE_PRIVATE = "private"
    TYPE_VISIBLE_PUBLIC = "public"

    All_VISIBLE_CONSTS = [TYPE_VISIBLE_PUBLIC, TYPE_VISIBLE_PRIVATE]
    # status consts
    STATUS_AVAILABLE = "available"
    STATUS_DELETING = "deleting"
    STATUS_DEPRECATED = "deprecated"
    STATUS_FAILED = "failed"
    STATUS_PENDING = "pending"
    STATUS_UNUSABLE = "unusable"

    ALL_STATUS_CONSTS = [STATUS_AVAILABLE, STATUS_DELETING, STATUS_DEPRECATED, STATUS_FAILED, STATUS_PENDING,
                         STATUS_UNUSABLE]
    __tablename__ = "ibm_images"

    id = Column(String(32), primary_key=True)
    name = Column(String(255), nullable=False)
    crn = Column(String(255), nullable=False)
    resource_id = Column(String(64), nullable=False)
    visibility = Column(Enum(TYPE_VISIBLE_PRIVATE, TYPE_VISIBLE_PUBLIC), nullable=False)
    status = Column(String(50), nullable=False)
    href = Column(Text, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow(), nullable=False)
    encryption = Column(Enum(ENCRYPTION_TYPE_NONE, ENCRYPTION_TYPE_USER_MANAGED), nullable=False)
    ibm_status_reasons = Column(JSON, nullable=False)
    encryption_key_crn = Column(String(255))
    minimum_provisioned_size = Column(Integer)
    file_checksums_sha256 = Column(String(255))
    file_size = Column(Integer)

    resource_group_id = Column(String(32), ForeignKey("ibm_resource_groups.id", ondelete="SET NULL"), nullable=True)
    operating_system_id = Column(String(32), ForeignKey("ibm_operating_systems.id", ondelete="SET NULL"), nullable=True)
    source_volume_id = Column(String(32), ForeignKey("ibm_volumes.id", ondelete="SET NULL"), nullable=True)

    operating_system = relationship(
        "IBMOperatingSystem", backref=backref("images", cascade="all, delete-orphan", lazy="dynamic",
                                              passive_deletes=True)
    )
    source_volume = relationship("IBMVolume", backref="sourced_images", foreign_keys=[source_volume_id])

    def __init__(
            self, name=None, crn=None, resource_id=None, visibility=None, status=None, href=None,
            created_at=None, encryption=None, ibm_status_reasons=None, ibm_visible=None,
            encryption_key_crn=None, minimum_provisioned_size=None, file_checksums_sha256=None, file_size=None
    ):
        self.id = str(uuid.uuid4().hex)
        self.name = name
        self.crn = crn
        self.resource_id = resource_id
        self.visibility = visibility
        self.status = status
        self.href = href
        self.created_at = created_at
        self.encryption = encryption
        self.ibm_visible = ibm_visible
        self.ibm_status_reasons = ibm_status_reasons
        self.encryption_key_crn = encryption_key_crn
        self.minimum_provisioned_size = minimum_provisioned_size
        self.file_checksums_sha256 = file_checksums_sha256
        self.file_size = file_size

    def to_reference_json(self):
        return {
            self.ID_KEY: self.id,
            self.NAME_KEY: self.name
        }

    def to_translation_reference_json(self):
        return {
            self.ID_KEY: self.id,
            self.NAME_KEY: self.name,
            self.OS_VENDOR_KEY: self.operating_system.vendor if self.operating_system else None,
            self.OS_VERSION_KEY: self.operating_system.version if self.operating_system else None,
            self.OS_NAME_KEY: self.operating_system.display_name if self.operating_system else None
        }

    def validate_json_for_schema(self):
        return {
            self.ID_KEY: self.id,
            self.RESOURCE_JSON_KEY: {
                self.NAME_KEY: self.name
            }
        }

    def to_json(self):
        return {
            self.ID_KEY: self.id,
            self.NAME_KEY: self.name,
            self.CRN_KEY: self.crn,
            self.RESOURCE_ID_KEY: self.resource_id,
            self.VISIBILITY_KEY: self.visibility,
            self.STATUS_KEY: self.status,
            self.HREF_KEY: self.href,
            self.CREATED_AT_KEY: self.created_at,
            self.ENCRYPTION_KEY: self.encryption,
            self.IBM_STATUS_REASONS_KEY: self.ibm_status_reasons,
            self.ENCRYPTION_KEY_CRN_KEY: self.encryption_key_crn,
            self.MINIMUM_PROVISIONED_SIZE_KEY: self.minimum_provisioned_size,
            self.FILE_CHECKSUMS_SHA256_KEY: self.file_checksums_sha256,
            self.FILE_SIZE_KEY: self.file_size,
            self.OPERATING_SYSTEM_KEY: self.operating_system.to_json() if self.operating_system else {},
            self.SOURCE_VOLUME_KEY: self.source_volume.to_reference_json() if self.source_volume else {},
            self.IBM_CLOUD_KEY: self.ibm_cloud.to_reference_json(),
            self.RESOURCE_GROUP_KEY: self.resource_group.to_reference_json() if self.resource_group else {},
            self.REGION_KEY: self.region.to_reference_json(),
        }

    def to_idle_json(self, session=None):
        from ibm.models.ibm.cost_models import IBMResourceInstancesCost

        session = session if session else db.session

        cost_obj = IBMResourceInstancesCost.get_cost(self.crn, self.cloud_id, session)
        return {
            self.CRN_KEY: self.crn,
            self.VISIBILITY_KEY: self.visibility,
            self.HREF_KEY: self.href,
            self.ENCRYPTION_KEY: self.encryption,
            self.STATUS_KEY: self.status,
            self.RESOURCE_TYPE_KEY: self.RESOURCE_TYPE_IMAGE_KEY,
            self.RESOURCE_ID_KEY: self.resource_id,
            self.IBM_CLOUD_KEY: self.cloud_id,
            self.ESTIMATED_SAVINGS: cost_obj.estimated_cost if cost_obj else None,
            self.COST_KEY: cost_obj.estimated_cost if cost_obj else None
        }

    # TODO: Fix when writing tasks
    def to_json_body(self):
        return {
            "name": self.name,
            "operating_system": {
                "name": self.operating_system.name if self.operating_system else ""
            },
            "file": {"href": self.image_template_path},
            "resource_group": {
                "id": self.ibm_resource_group.resource_id
                if self.ibm_resource_group
                else ""
            },
        }

    @classmethod
    def from_ibm_json_body(cls, json_body):
        file_checksums_sha256 = json_body["file"]["checksums"]["sha256"] if "checksums" in json_body["file"] else None
        ibm_image = cls(
            name=json_body["name"],
            crn=json_body["crn"],
            resource_id=json_body["id"],
            visibility=json_body["visibility"],
            status=json_body["status"],
            href=json_body["href"],
            created_at=datetime.strptime(json_body["created_at"], CREATED_AT_FORMAT),
            encryption=json_body["encryption"],
            ibm_visible=json_body["visibility"],
            ibm_status_reasons=json_body["status_reasons"],
            encryption_key_crn=json_body["encryption_key"]["crn"] if "encryption_key" in json_body else None,
            minimum_provisioned_size=json_body.get("minimum_provisioned_size"),
            file_checksums_sha256=file_checksums_sha256,
            file_size=json_body["file"].get("size"),
        )
        if ibm_image.encryption:
            ibm_image.ibm_encryption = IBMImage.ENCRYPTION_TYPE_USER_MANAGED
        else:
            ibm_image.ibm_encryption = IBMImage.ENCRYPTION_TYPE_NONE

        # TODO: Verify if any operating systems returned here from IBM are not listed in the LIST OS API
        # if json_body.get("operating_system"):
        #     ibm_image.operating_system = IBMOperatingSystem.from_ibm_json_body(json_body["operating_system"])

        return ibm_image

    def dis_params_eq(self, other):
        assert isinstance(other, self.__class__)

        return (self.name == other.name and self.crn == other.crn and self.resource_id == other.resource_id and
                self.visibility == other.visibility and self.status == other.status and self.href == other.href and
                self.encryption == other.encryption and
                self.encryption_key_crn == other.encryption_key_crn and
                self.minimum_provisioned_size == other.minimum_provisioned_size and
                self.file_checksums_sha256 == other.file_checksums_sha256 and self.file_size == other.file_size)

    def mangos_params_eq(self, json_body):
        file_checksums_sha256 = json_body["file"]["checksums"]["sha256"] if "checksums" in json_body["file"] else None
        encryption_key_crn = json_body["encryption_key"]["crn"] if "encryption_key" in json_body else None
        return (
                self.visibility == json_body["visibility"] and
                self.status == json_body["status"] and
                self.href == json_body["href"] and
                self.encryption == json_body["encryption"] and
                self.encryption_key_crn == encryption_key_crn and
                self.minimum_provisioned_size == json_body.get("minimum_provisioned_size") and
                self.file_checksums_sha256 == file_checksums_sha256 and
                self.file_size == json_body["file"].get("size")
        )

    def dis_add_update_db(self, session, db_image, db_operating_systems, db_cloud, db_resource_group,
                          operating_system_obj, db_region):
        if operating_system_obj:
            operating_system_obj.dis_add_update_db(
                session=session, db_operating_system=db_operating_systems, cloud_id=db_cloud.id, db_region=db_region
            )
        db_operating_system = \
            session.query(IBMOperatingSystem).filter_by(
                name=operating_system_obj.name, cloud_id=db_cloud.id, region_id=db_region.id).first()

        if not db_operating_system:
            LOGGER.info(
                f"Provided IBMOperatingSystem with name: "
                f"{operating_system_obj.name}, "
                f"Cloud ID: {db_cloud.id} and Region: {db_region.name} while inserting "
                f"IBMImage {self.resource_id} not found in DB.")
            return

        existing = db_image or None

        if not existing:
            self.resource_group = db_resource_group
            self.operating_system = db_operating_system
            self.ibm_cloud = db_cloud
            self.region = db_region
            session.commit()
            return

        if not self.dis_params_eq(existing):
            existing.update_from_object(self)
            existing.resource_group = db_resource_group
            existing.operating_system = db_operating_system
            existing.region = db_region

        session.commit()

    def update_from_object(self, other):
        assert isinstance(other, self.__class__)

        self.name = other.name
        self.crn = other.crn
        self.resource_id = other.resource_id
        self.visibility = other.visibility
        self.status = other.status
        self.href = other.href
        self.encryption = other.encryption
        self.ibm_visible = other.ibm_visible
        self.encryption_key_crn = other.encryption_key_crn
        self.minimum_provisioned_size = other.minimum_provisioned_size
        self.file_checksums_sha256 = other.file_checksums_sha256
        self.file_size = other.file_size


class IBMOperatingSystem(IBMRegionalResourceMixin, Base):
    ID_KEY = "id"
    DISPLAY_NAME_KEY = "display_name"
    NAME_KEY = "name"
    ARCHITECTURE_KEY = "architecture"
    FAMILY_KEY = "family"
    VENDOR_KEY = "vendor"
    VERSION_KEY = "version"
    DEDICATED_HOST_ONLY_KEY = "dedicated_host_only"
    HREF_KEY = "href"
    RESOURCE_JSON_KEY = "resource_json"

    ALL_VENDORS = ['Rocky Linux', 'SUSE', 'Microsoft', 'Fedora', 'Canonical', 'Red Hat', 'Debian', 'CentOS']
    ALL_FAMILIES = ['Ubuntu Linux', 'Rocky Linux', 'Red Hat Enterprise Linux', 'Debian GNU/Linux', 'Fedora Server',
                    'Windows Server', 'SUSE Linux Enterprise Server', 'Fedora CoreOS', 'CentOS']
    ALL_ARCHITECTURES = ['amd64', 's390x']

    CRZ_BACKREF_NAME = "operating_systems"

    __tablename__ = "ibm_operating_systems"

    id = Column(String(32), primary_key=True)
    display_name = Column(String(255), nullable=False)
    name = Column(String(255), nullable=False)
    architecture = Column(String(255), nullable=False)
    family = Column(String(255), nullable=False)
    vendor = Column(String(255), nullable=False)
    version = Column(String(255), nullable=False)
    dedicated_host_only = Column(Boolean, nullable=False)
    href = Column(Text, nullable=False)

    # __table_args__ = (
    #     UniqueConstraint(name, "region_id", "cloud_id", name="uix_ibm_operation_system_name_region_id_cloud_id"),
    # )

    def __init__(
            self, display_name=None, name=None, architecture=None, family=None, vendor=None, version=None,
            dedicated_host_only=None, href=None
    ):
        self.id = str(uuid.uuid4().hex)
        self.display_name = display_name
        self.name = name
        self.architecture = architecture
        self.family = family
        self.vendor = vendor
        self.version = version
        self.dedicated_host_only = dedicated_host_only
        self.href = href

    def to_reference_json(self, architecture=False):
        response = {
            self.ID_KEY: self.id,
            self.NAME_KEY: self.name,
            self.ARCHITECTURE_KEY: self.architecture
        }
        if architecture:
            response[self.VENDOR_KEY] = self.vendor
        return response

    def validate_json_for_schema(self):
        return {
            self.ID_KEY: self.id,
            self.RESOURCE_JSON_KEY: {
                self.NAME_KEY: self.name,
                self.ARCHITECTURE_KEY: self.architecture,
                self.VENDOR_KEY: self.vendor
            }
        }

    def to_json(self):
        return {
            self.ID_KEY: self.id,
            self.DISPLAY_NAME_KEY: self.display_name,
            self.NAME_KEY: self.name,
            self.ARCHITECTURE_KEY: self.architecture,
            self.FAMILY_KEY: self.family,
            self.VENDOR_KEY: self.vendor,
            self.VERSION_KEY: self.version,
            self.DEDICATED_HOST_ONLY_KEY: self.dedicated_host_only,
            self.HREF_KEY: self.href,
        }

    @classmethod
    def from_ibm_json_body(cls, json_body):
        return cls(
            display_name=json_body["display_name"] if json_body.get("display_name") else json_body["name"],
            name=json_body["name"],
            architecture=json_body["architecture"],
            family=json_body["family"],
            vendor=json_body["vendor"],
            version=json_body["version"],
            dedicated_host_only=json_body["dedicated_host_only"],
            href=json_body["href"],
        )

    def dis_params_eq(self, other):
        assert isinstance(other, self.__class__)

        return (self.name == other.name and self.architecture == other.architecture and self.family == other.family and
                self.vendor == other.vendor and self.version == other.version and self.region == other.region)

    def dis_add_update_db(self, session, db_operating_system, cloud_id, db_region):
        from ibm.models import IBMCloud

        existing = db_operating_system or None

        if not existing:
            cloud = session.query(IBMCloud).get(cloud_id)
            assert cloud

            self.ibm_cloud = cloud
            self.region = db_region
            session.commit()
            return

        if not self.dis_params_eq(existing):
            existing.update_from_object(self)
            existing.region = db_region

        session.commit()

    def update_from_object(self, other):
        assert isinstance(other, self.__class__)

        self.name = other.name
        self.architecture = other.architecture
        self.family = other.family
        self.vendor = other.vendor
        self.version = other.version
