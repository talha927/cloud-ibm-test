import uuid
from datetime import datetime
from random import randrange

from sqlalchemy import Boolean, Column, DateTime, Enum, ForeignKey, Integer, JSON, PrimaryKeyConstraint, String, \
    Table, Text
from sqlalchemy.orm import backref, relationship
from sqlalchemy.schema import UniqueConstraint

from ibm import get_db_session as db
from ibm.common.consts import CREATED_AT_FORMAT, DUMMY_CLOUD_ID, DUMMY_CLOUD_NAME, DUMMY_REGION_ID, \
    DUMMY_REGION_NAME, DUMMY_RESOURCE_GROUP_ID, DUMMY_RESOURCE_GROUP_NAME, DUMMY_ZONE_ID, DUMMY_ZONE_NAME
from ibm.common.utils import return_datetime_object
from ibm.models.base import Base
from ibm.models.ibm.mixins import IBMCloudResourceMixin, IBMRegionalResourceMixin, IBMZonalResourceMixin

ibm_instance_keys = Table(
    "ibm_instance_keys", Base.metadata,
    Column("instance_id", String(32), ForeignKey("ibm_instances.id", ondelete="CASCADE")),
    Column("key_id", String(32), ForeignKey("ibm_ssh_keys.id", ondelete="CASCADE")),
    PrimaryKeyConstraint("instance_id", "key_id"),
)

ibm_network_interfaces_security_groups = Table(
    "ibm_network_interfaces_security_groups", Base.metadata,
    Column("network_interface_id", String(32), ForeignKey("ibm_network_interfaces.id", ondelete="CASCADE")),
    Column("security_group_id", String(32), ForeignKey("ibm_security_groups.id", ondelete="CASCADE")),
    PrimaryKeyConstraint("network_interface_id", "security_group_id"),
)

ibm_instance_profile_disks = Table(
    "ibm_instance_profile_disks", Base.metadata,
    Column("instance_profile_id", String(32), ForeignKey("ibm_instance_profiles.id", ondelete="CASCADE")),
    Column("disk_id", String(32), ForeignKey("ibm_instance_disks.id", ondelete="CASCADE")),
    PrimaryKeyConstraint("instance_profile_id", "disk_id"),
)


class IBMInstance(IBMZonalResourceMixin, Base):
    # task types
    TYPE_MONITORING = "MONITORING"
    TYPE_IDLE = "IDLE"

    ID_KEY = "id"
    RESOURCE_ID_KEY = "resource_id"
    NAME_KEY = "name"
    REGION_KEY = "region"
    ZONE_KEY = "zone"
    CRN_KEY = "crn"
    CREATED_AT_KEY = "created_at"
    STATUS_KEY = "status"
    HREF_KEY = "href"
    BANDWIDTH_KEY = "bandwidth"
    MEMORY_KEY = "memory"
    STARTABLE_KEY = "startable"
    GPU_KEY = "gpu"
    STATUS_REASONS_KEY = "status_reasons"
    VCPU_KEY = "vcpu"
    VOLUME_ATTACHMENTS_KEY = "volume_attachments"
    BOOT_VOLUME_ATTACHMENT_KEY = "boot_volume_attachment"
    VPC_KEY = "vpc"
    NETWORK_INTERFACES_KEY = "network_interfaces"
    PRIMARY_NETWORK_INTERFACE_KEY = "primary_network_interface"
    KEYS_KEY = "keys"
    IMAGE_KEY = "image"
    PLACEMENT_TARGET_KEY = "placement_target"
    PLACEMENT_GROUP_KEY = "placement_group"
    DEDICATED_HOST_KEY = "dedicated_host"
    DEDICATED_HOST_GROUP_KEY = "dedicated_host_group"
    PROFILE_KEY = "profile"
    RESOURCE_GROUP_KEY = "resource_group"
    RESOURCE_JSON_KEY = "resource_json"
    ASSOCIATED_RESOURCES_KEY = "associated_resources"
    RESOURCE_TYPE_KEY = "resource_type"
    RESOURCE_TYPE_INSTANCE_KEY = "Instance"
    USAGE_KEY = "usage"
    ESTIMATED_SAVINGS = "estimated_savings"
    COST_KEY = "cost"
    VOLUME_MIGRATION_REPORT_KEY = "volume_migration_report"

    CRZ_BACKREF_NAME = "instances"
    # status consts
    STATUS_DELETING = "deleting"
    STATUS_FAILED = "failed"
    STATUS_PENDING = "pending"
    STATUS_RESTARTING = "restarting"
    STATUS_RUNNING = "running"
    STATUS_STARTING = "starting"
    STATUS_STOPPING = "stopping"
    STATUS_STOPPED = "stopped"
    ALL_STATUSES_LIST = [
        STATUS_DELETING, STATUS_FAILED, STATUS_PENDING, STATUS_RESTARTING,
        STATUS_RUNNING, STATUS_STARTING, STATUS_STOPPED, STATUS_STOPPING
    ]
    # status reasons consts
    ALL_STATUS_REASONS_LIST = [
        "cannot_start", "cannot_start_capacity", "cannot_start_compute", "cannot_start_ip_address",
        "cannot_start_network",
        "cannot_start_storage", "encryption_key_deleted", "stopped_for_image_creation"
    ]

    __tablename__ = "ibm_instances"

    id = Column(String(32), primary_key=True)
    resource_id = Column(String(64), nullable=False)
    name = Column(String(255), nullable=False)
    crn = Column(String(255), nullable=False)
    created_at = Column(DateTime, nullable=False)
    status = Column(String(50), nullable=False)
    href = Column(Text, nullable=False)
    bandwidth = Column(Integer, nullable=False)
    memory = Column(Integer, nullable=False)
    startable = Column(Boolean, nullable=False)
    gpu = Column(JSON)
    ibm_status_reasons = Column(JSON, nullable=False)
    volume_migration_report = Column(JSON, nullable=True)
    vcpu = Column(JSON, nullable=False)
    usage = Column(JSON, nullable=True)

    resource_group_id = Column(String(32), ForeignKey("ibm_resource_groups.id", ondelete="CASCADE"))
    vpc_id = Column(String(32), ForeignKey("ibm_vpc_networks.id", ondelete="CASCADE"))
    instance_profile_id = Column(String(32), ForeignKey("ibm_instance_profiles.id", ondelete="CASCADE"))
    # pt stands for Placement target
    pt_dedicated_host_id = Column(String(32), ForeignKey("ibm_dedicated_hosts.id", ondelete="SET NULL"), nullable=True)
    pt_dedicated_host_group_id = Column(String(32), ForeignKey("ibm_dedicated_host_groups.id", ondelete="SET NULL"),
                                        nullable=True)
    pt_placement_group_id = Column(String(32), ForeignKey("ibm_placement_groups.id", ondelete="SET NULL"),
                                   nullable=True)
    # Placement target and the actual dedicated host are two different relations and should be handled that way
    #  for example, if a dedicated_host_group has multiple dedicated hosts and the placement target for an instance is
    #  that dedicated_host_group, then the actual dedicated host would be a dedicated host and the placement target
    #  would be a dedicated host group.
    dedicated_host_id = Column(String(32), ForeignKey("ibm_dedicated_hosts.id", ondelete="SET NULL"), nullable=True)
    image_id = Column(String(32), ForeignKey("ibm_images.id", ondelete="SET NULL"), nullable=True)

    vpc_network = relationship(
        "IBMVpcNetwork",
        backref=backref("instances", cascade="all, delete-orphan", passive_deletes=True, lazy="dynamic")
    )
    volume_attachments = relationship(
        "IBMVolumeAttachment", cascade="all, delete-orphan", passive_deletes=True, lazy="dynamic"
    )
    instance_disks = relationship(
        'IBMInstanceDisk', backref="instance", cascade="all, delete-orphan", passive_deletes=True, lazy="dynamic"
    )
    network_interfaces = relationship(
        "IBMNetworkInterface", backref="instance", cascade="all, delete-orphan", passive_deletes=True, lazy="dynamic"
    )
    instance_profile = relationship(
        "IBMInstanceProfile", backref=backref("instances", cascade="all, delete-orphan", passive_deletes=True,
                                              lazy="dynamic")
    )
    _placement_target_dedicated_host = relationship(
        "IBMDedicatedHost", backref=backref("placement_instances", lazy="dynamic"), foreign_keys=[pt_dedicated_host_id]
    )
    _placement_target_dedicated_host_group = relationship(
        "IBMDedicatedHostGroup", backref=backref("placement_instances", lazy="dynamic"),
        foreign_keys=[pt_dedicated_host_group_id]
    )
    _placement_target_placement_group = relationship(
        "IBMPlacementGroup", backref=backref("placement_instances", lazy="dynamic"),
        foreign_keys=[pt_placement_group_id]
    )
    ssh_keys = relationship(
        "IBMSshKey", secondary=ibm_instance_keys, lazy="dynamic", backref=backref("instances", lazy="dynamic")
    )
    image = relationship("IBMImage", backref=backref("instances", lazy="dynamic"))

    member = relationship("IBMPoolMember", backref="instance", uselist=False)
    instance_group_memberships = relationship(
        "IBMInstanceGroupMembership",
        backref=backref("instances", cascade="all, delete-orphan", passive_deletes=True, single_parent=True)
    )
    right_sizing_recommendations = relationship(
        "IBMRightSizingRecommendation", backref="ibm_instance", cascade="all, delete-orphan", passive_deletes=True)

    __table_args__ = (
        UniqueConstraint(resource_id, "cloud_id", "region_id", name="uix_ibm_resource_id_cloud_id_region_id"),
    )

    def __init__(
            self, resource_id=None, name=None, crn=None, created_at=None, status=None,
            href=None, bandwidth=None, memory=None, startable=None, gpu=None, ibm_status_reasons=None, vcpu=None,
            usage=None
    ):
        self.id = str(uuid.uuid4().hex)
        self.resource_id = resource_id
        self.name = name
        self.crn = crn
        self.created_at = created_at
        self.status = status
        self.href = href
        self.bandwidth = bandwidth
        self.memory = memory
        self.startable = startable
        self.gpu = gpu
        self.ibm_status_reasons = ibm_status_reasons
        self.vcpu = vcpu
        self.usage = usage

    @property
    def placement_target(self):
        return self._placement_target_dedicated_host or self._placement_target_dedicated_host_group or \
            self._placement_target_placement_group

    @placement_target.setter
    def placement_target(self, placement_target):
        from ibm.models import IBMDedicatedHost, IBMDedicatedHostGroup, IBMPlacementGroup
        if isinstance(placement_target, IBMDedicatedHost):
            self._placement_target_dedicated_host = placement_target
        elif isinstance(placement_target, IBMDedicatedHostGroup):
            self._placement_target_dedicated_host_group = placement_target
        elif isinstance(placement_target, IBMPlacementGroup):
            self._placement_target_placement_group = placement_target

    @property
    def is_deletable(self):
        return not any([network_interface.floating_ips.count() for network_interface in self.network_interfaces.all()])

    @property
    def primary_network_interface(self):
        primary_network_interface = self.network_interfaces.filter_by(is_primary=True).first()
        return primary_network_interface.to_reference_json() if primary_network_interface else {}

    @property
    def boot_volume_attachment(self):
        boot_volume_attachment = self.volume_attachments.filter_by(type_="boot").first()
        return boot_volume_attachment.to_reference_json() if boot_volume_attachment else {}

    def to_reference_json(self):
        return {
            self.ID_KEY: self.id,
            self.NAME_KEY: self.name,
            self.ZONE_KEY: self.zone.to_reference_json(),
            self.PROFILE_KEY: self.instance_profile.to_reference_json(),
            self.IMAGE_KEY: self.image.to_reference_json() if self.image else {},
            self.STATUS_KEY: self.status,
            self.PRIMARY_NETWORK_INTERFACE_KEY: self.primary_network_interface,
            self.USAGE_KEY: self.usage or {}
        }

    def to_template_json(self):
        primary_network_interface = self.network_interfaces.filter_by(is_primary=True).first()
        volume_attachments = [v.to_template_json() for v in self.volume_attachments.all() if v.type_ != "boot"]
        network_interfaces = [n.to_json_body() for n in self.network_interfaces.all() if not n.is_primary]
        boot_volume_attachments = \
            [a.to_template_json() for a in self.volume_attachments.all()
             if a.type_ == "boot"][0] if self.volume_attachments.count() else {}

        placement_target_to_type_mapper = {
            "IBMDedicatedHost": "dedicated_host",
            "IBMDedicatedHostGroup": "dedicated_host_group",
            "IBMPlacementGroup": "placement_group",
        }

        placement_target = {}
        if self.placement_target:
            placement_group_type = placement_target_to_type_mapper[self.placement_target.__class__.__name__]
            placement_target = {placement_group_type: self.placement_target.to_reference_json()}

        resource_json = {
            self.NAME_KEY: f"i{self.name}-{randrange(9999)}"[:61],
            self.VPC_KEY: {self.ID_KEY: self.vpc_id},
            self.ZONE_KEY: {self.ID_KEY: self.zone_id},
            self.BOOT_VOLUME_ATTACHMENT_KEY: boot_volume_attachments,
            self.KEYS_KEY: [key.to_reference_json() for key in self.ssh_keys.all()],
            self.PRIMARY_NETWORK_INTERFACE_KEY:
                primary_network_interface.to_json_body() if primary_network_interface else {},
            self.RESOURCE_GROUP_KEY: {self.ID_KEY: self.resource_group_id},
            self.VOLUME_ATTACHMENTS_KEY: volume_attachments,
            self.NETWORK_INTERFACES_KEY: network_interfaces,
        }
        image = {self.NAME_KEY: self.image.name} if self.image else {self.ID_KEY: self.image_id}
        if not boot_volume_attachments.get("volume", {}).get("source_snapshot"):
            resource_json[self.IMAGE_KEY] = image
        profile = {self.NAME_KEY: self.instance_profile.name} if self.instance_profile else {
            self.ID_KEY: self.instance_profile_id}
        resource_json[self.PROFILE_KEY] = profile
        if placement_target:
            resource_json[self.PLACEMENT_TARGET_KEY] = placement_target

        resource_data = {
            self.ID_KEY: self.id,
            self.IBM_CLOUD_KEY: {self.ID_KEY: self.cloud_id},
            self.REGION_KEY: {self.ID_KEY: self.region_id},
            self.RESOURCE_JSON_KEY: resource_json,
        }
        return resource_data

    def validate_json_for_schema(self):
        return {
            self.ID_KEY: self.id,
            self.RESOURCE_JSON_KEY: {
                self.NAME_KEY: self.name,
                self.ZONE_KEY: self.zone.to_reference_json(),
                self.PROFILE_KEY: self.instance_profile.to_reference_json(),
                self.IMAGE_KEY: self.image.to_reference_json() if self.image else {},
            }
        }

    def to_json(self):
        # TODO: relations/references
        json_data = {
            self.ID_KEY: self.id,
            self.RESOURCE_ID_KEY: self.resource_id,
            self.VOLUME_MIGRATION_REPORT_KEY: self.volume_migration_report,
            self.NAME_KEY: self.name,
            self.CRN_KEY: self.crn,
            self.CREATED_AT_KEY: self.created_at,
            self.STATUS_KEY: self.status,
            self.HREF_KEY: self.href,
            self.BANDWIDTH_KEY: self.bandwidth,
            self.MEMORY_KEY: self.memory,
            self.STARTABLE_KEY: self.startable,
            self.GPU_KEY: self.gpu,
            self.STATUS_REASONS_KEY: self.ibm_status_reasons,
            self.VCPU_KEY: self.vcpu,
            self.IMAGE_KEY: self.image.to_reference_json() if self.image else {},
            # self.PLACEMENT_TARGET_KEY: self.placement_target.to_reference_json() if self.placement_target else None,
            self.REGION_KEY: self.region.to_reference_json(),
            self.ZONE_KEY: self.zone.to_reference_json(),
            self.IBM_CLOUD_KEY: self.ibm_cloud.to_reference_json(),
            self.RESOURCE_GROUP_KEY: self.resource_group.to_reference_json(),
            self.PROFILE_KEY: self.instance_profile.to_reference_json(),
            self.VPC_KEY: self.vpc_network.to_reference_json(),
            self.ASSOCIATED_RESOURCES_KEY: {
                self.PLACEMENT_GROUP_KEY: self._placement_target_placement_group.to_reference_json() if
                self._placement_target_placement_group else {},
                self.KEYS_KEY: [ssh_key.to_json() for ssh_key in self.ssh_keys.all()],
                self.DEDICATED_HOST_KEY: self._placement_target_dedicated_host.to_reference_json() if
                self._placement_target_dedicated_host else {},
                self.DEDICATED_HOST_GROUP_KEY: self._placement_target_dedicated_host_group.to_reference_json() if
                self._placement_target_dedicated_host_group else {},
                self.VOLUME_ATTACHMENTS_KEY: [volume_attachment.to_reference_json() for volume_attachment in
                                              self.volume_attachments.all()],
                self.PRIMARY_NETWORK_INTERFACE_KEY: self.primary_network_interface,
                self.BOOT_VOLUME_ATTACHMENT_KEY: self.boot_volume_attachment,
                self.NETWORK_INTERFACES_KEY: [network_interface.to_reference_json() for network_interface in
                                              self.network_interfaces.filter_by(is_primary=False).all()]

            },
            self.USAGE_KEY: self.usage or {}
        }
        return json_data

    def to_idle_json(self, session=None):
        from ibm.models.ibm.cost_models import IBMResourceInstancesCost

        session = session if session else db.session
        cost_obj = IBMResourceInstancesCost.get_cost(self.crn, self.cloud_id, session)

        json_data = {
            self.ID_KEY: self.id,
            self.RESOURCE_ID_KEY: self.resource_id,
            self.NAME_KEY: self.name,
            self.CRN_KEY: self.crn,
            self.STATUS_KEY: self.status,
            self.HREF_KEY: self.href,
            self.REGION_KEY: self.region.to_reference_json(),
            self.RESOURCE_TYPE_KEY: self.RESOURCE_TYPE_INSTANCE_KEY,
            self.ZONE_KEY: self.zone.to_reference_json(),
            self.IBM_CLOUD_KEY: self.ibm_cloud.to_reference_json(),
            self.VPC_KEY: self.vpc_network.to_reference_json(),
            self.USAGE_KEY: self.usage or {},
            self.ESTIMATED_SAVINGS: cost_obj.estimated_cost if cost_obj else None,
            self.COST_KEY: cost_obj.estimated_cost if cost_obj else None
        }
        return json_data

    # TODO: Verify this when writing tasks
    def to_json_body(self):
        json_body = {
            "name": self.name,
            "zone": {"name": self.zone},
            "user_data": self.user_data or "",
            "resource_group": {"id": self.ibm_resource_group.resource_id if self.ibm_resource_group else None},
            "vpc": {"id": self.ibm_vpc_network.resource_id},
            "image": {"id": self.ibm_image.resource_id},
            "profile": {"name": self.ibm_instance_profile.name},
            "keys": [{"id": key.resource_id} for key in self.ssh_keys.all()],
            "primary_network_interface": [
                interface.to_json_body() for interface in self.network_interfaces.all() if interface.is_primary][0],
            "network_interfaces": [
                interface.to_json_body() for interface in self.network_interfaces.all() if not interface.is_primary],
            "volume_attachments": [
                attachment.to_json_body() for attachment in self.volume_attachments.all() if attachment.type == "data"],
            "boot_volume_attachment": [
                attachment.to_json_body() for attachment in self.volume_attachments.all()
                if attachment.type == "boot"][0] if self.volume_attachments.all() else [],
        }
        if self.ibm_dedicated_host:
            json_body["placement_target"] = {
                "id": self.ibm_dedicated_host.resource_id
            }
        elif self.ibm_dedicated_host_group:
            json_body["placement_target"] = {
                "id": self.ibm_dedicated_host_group.resource_id
            }
        return json_body

    def from_softlayer_to_ibm_json(self, softlayer_instance, vpc_id, softlayer_cloud):
        # TODO image and Operating system will be added, it is in pending for other tasks
        placement_target_json = {}
        if softlayer_instance.dedicated_host:
            placement_target_json["dedicated_host"] = {
                self.ID_KEY: softlayer_instance.dedicated_host["id"],
                self.NAME_KEY: softlayer_instance.dedicated_host["name"],
            }
        elif softlayer_instance.placement_group:
            placement_target_json["placement_group"] = {
                self.ID_KEY: softlayer_instance.placement_group["id"],
                self.NAME_KEY: softlayer_instance.placement_group["name"],
            }
        ibm_body = {
            "ibm_cloud": {
                self.ID_KEY: DUMMY_CLOUD_ID,
                self.NAME_KEY: DUMMY_CLOUD_NAME
            },
            self.REGION_KEY: {
                self.ID_KEY: DUMMY_REGION_ID,
                self.NAME_KEY: DUMMY_REGION_NAME
            },
            self.ID_KEY: self.id,
            "resource_json": {
                self.BOOT_VOLUME_ATTACHMENT_KEY: [
                    attachment.to_json_body() for attachment in self.volume_attachments.all()
                    if attachment.type_ == "boot"][0] if self.volume_attachments.all() else {},
                self.IMAGE_KEY: softlayer_instance.image.to_json(),
                self.KEYS_KEY: [key.to_reference_json() for key in softlayer_instance.ssh_keys],
                self.NAME_KEY: self.name,
                self.NETWORK_INTERFACES_KEY: [net_interface.to_json_body() for net_interface in
                                              self.network_interfaces.all() if not net_interface.is_primary],
                self.PLACEMENT_TARGET_KEY: placement_target_json,
                self.PRIMARY_NETWORK_INTERFACE_KEY: [
                    interface.to_json_body() for interface in self.network_interfaces.all() if interface.is_primary][0],
                self.PROFILE_KEY: self.instance_profile or softlayer_instance.instance_profile.to_json(),
                self.RESOURCE_GROUP_KEY: {
                    self.ID_KEY: DUMMY_RESOURCE_GROUP_ID,
                    self.NAME_KEY: DUMMY_RESOURCE_GROUP_NAME
                },
                self.VOLUME_ATTACHMENTS_KEY: [volume_attachment.to_json_body() for volume_attachment in
                                              self.volume_attachments.all() if volume_attachment.type_ != "boot"],
                self.VPC_KEY: {self.ID_KEY: vpc_id},
                self.ZONE_KEY: {
                    self.ID_KEY: DUMMY_ZONE_ID,
                    self.NAME_KEY: DUMMY_ZONE_NAME
                }
            },
            "migration_json": {
                "classic_account_id": softlayer_cloud,
                "classic_instance_id": softlayer_instance.instance_id,
                "data_center": softlayer_instance.data_center,
                "file": {
                    "bucket": {},
                },
                "is_volume_migration": True,
                "migrate_from": "CLASSIC_VSI",
                "nas_migration": softlayer_instance.network_attached_storages,
                "operating_system": {
                    self.ID_KEY: "stringstringstringstringstringst",
                    self.NAME_KEY: "string"
                },
                "instance_type": softlayer_instance.instance_type,
                "auto_scale_group": softlayer_instance.auto_scale_group
            },
        }
        return ibm_body

    @classmethod
    def from_ibm_json_body(cls, json_body):
        return cls(
            resource_id=json_body["id"],
            name=json_body["name"],
            crn=json_body["crn"],
            created_at=datetime.strptime(json_body["created_at"], CREATED_AT_FORMAT),
            status=json_body["status"],
            href=json_body["href"],
            bandwidth=json_body["bandwidth"],
            memory=json_body["memory"],
            startable=json_body["startable"],
            gpu=json_body.get("gpu"),
            ibm_status_reasons=json_body["status_reasons"],
            vcpu=json_body["vcpu"],
        )

    def dis_params_eq(self, other):
        assert isinstance(other, self.__class__)
        return (self.name == other.name and
                self.resource_id == other.resource_id and
                self.status == other.status)

    def dis_add_update_db(self, session, db_instance, cloud_id, db_resource_group, db_instance_profile, db_vpc_network,
                          db_image, db_zone):
        from ibm.models import IBMCloud

        existing = db_instance or None

        if not existing:
            db_cloud = session.query(IBMCloud).get(cloud_id)
            assert db_cloud

            self.resource_group = db_resource_group
            self.instance_profile = db_instance_profile
            self.vpc_network = db_vpc_network
            self.image = db_image
            self.ibm_cloud = db_cloud
            self.zone = db_zone
            session.commit()
            return

        if not self.dis_params_eq(existing):
            existing.update_from_object(self)

        existing.resource_group = db_resource_group
        existing.instance_profile = db_instance_profile
        existing.image = db_image
        existing.vpc_network = db_vpc_network
        existing.zone = db_zone
        session.commit()

    def update_from_object(self, other):
        assert isinstance(other, self.__class__)

        self.name = other.name
        self.status = other.status
        self.resource_id = other.resource_id


class IBMInstanceProfile(IBMRegionalResourceMixin, Base):
    ID_KEY = "id"
    NAME_KEY = "name"
    FAMILY_KEY = "family"
    BANDWIDTH_KEY = "bandwidth"
    VCPU_ARCHITECTURE_KEY = "vcpu_architecture"
    VCPU_COUNT_KEY = "vcpu_count"
    HREF_KEY = "href"
    MEMORY_KEY = "memory"
    OS_ARCHITECTURE_KEY = "os_architecture"
    PORT_SPEED_KEY = "port_speed"
    DISKS_KEY = "disks"
    GPU_MODEL_KEY = "gpu_model"
    GPU_COUNT_KEY = "gpu_count"
    GPU_MEMORY_KEY = "gpu_memory"
    GPU_MANUFACTURER_KEY = "gpu_manufacturer"
    TOTAL_VOLUME_BANDWIDTH_KEY = "total_volume_bandwidth"
    RESOURCE_JSON_KEY = "resource_json"

    CRZ_BACKREF_NAME = "instance_profiles"

    # profile family consts
    FAMILY_TYPE_BALANCED = "balanced"
    FAMILY_TYPE_COMPUTE = "compute"
    FAMILY_TYPE_MEMORY = "memory"
    FAMILY_TYPE_GPU_V100 = "gpu-v100"
    FAMILY_TYPE_HIGH_MEMORY = "high-memory"
    FAMILY_TYPE_VERY_HIGH_MEMORY = "very-high-memory"

    ALL_FAMILIES = [
        FAMILY_TYPE_GPU_V100, FAMILY_TYPE_MEMORY, FAMILY_TYPE_VERY_HIGH_MEMORY, FAMILY_TYPE_COMPUTE,
        FAMILY_TYPE_BALANCED, FAMILY_TYPE_HIGH_MEMORY
    ]

    # architecture consts
    ARCHITECTURE_TYPE_POWER = "power"
    ARCHITECTURE_TYPE_AMD64 = "amd64"

    # memory typees
    MEMORY_TYPE_FIXED = "fixed"
    MEMORY_TYPE_DEPENDENT = "dependent"
    MEMORY_TYPE_ENUM = "enum"
    MEMORY_TYPE_RANGE = "range"

    __tablename__ = "ibm_instance_profiles"

    id = Column(String(32), primary_key=True)
    name = Column(String(255), nullable=False)
    family = Column(String(255))
    bandwidth = Column(JSON, nullable=False)
    vcpu_architecture = Column(JSON, nullable=False)
    vcpu_count = Column(JSON, nullable=False)
    href = Column(Text, nullable=False)
    memory = Column(JSON, nullable=False)
    os_architecture = Column(JSON, nullable=False)
    port_speed = Column(JSON, nullable=False)
    disks = Column(JSON, nullable=False)
    gpu_model = Column(JSON, nullable=True)
    gpu_count = Column(JSON, nullable=True)
    gpu_memory = Column(JSON, nullable=True)
    gpu_manufacturer = Column(JSON, nullable=True)
    total_volume_bandwidth = Column(JSON, nullable=False)

    __table_args__ = (
        UniqueConstraint(name, "region_id", "cloud_id", name="uix_ibm_instance_profile_name_region_id_cloud_id"),
    )

    def __init__(
            self, name=None, family=None, bandwidth=None, vcpu_architecture=None, vcpu_count=None, href=None,
            memory=None, os_architecture=None, port_speed=None, disks=None, gpu_count=None, gpu_memory=None,
            gpu_model=None, gpu_manufacturer=None, total_volume_bandwidth=None
    ):
        self.id = str(uuid.uuid4().hex)
        self.name = name
        self.family = family
        self.bandwidth = bandwidth
        self.vcpu_architecture = vcpu_architecture
        self.vcpu_count = vcpu_count
        self.href = href
        self.memory = memory
        self.os_architecture = os_architecture
        self.port_speed = port_speed
        self.disks = disks
        self.gpu_count = gpu_count
        self.gpu_memory = gpu_memory
        self.gpu_model = gpu_model
        self.gpu_manufacturer = gpu_manufacturer
        self.total_volume_bandwidth = total_volume_bandwidth

    def to_reference_json(self):
        return {
            self.ID_KEY: self.id,
            self.NAME_KEY: self.name
        }

    def validate_json_for_schema(self):
        return {
            self.ID_KEY: self.id,
            self.RESOURCE_JSON_KEY: {
                self.NAME_KEY: self.name,
                self.OS_ARCHITECTURE_KEY: self.os_architecture,
                self.FAMILY_KEY: self.family

            }
        }

    def to_json(self):
        return {
            self.ID_KEY: self.id,
            self.NAME_KEY: self.name,
            self.FAMILY_KEY: self.family,
            self.BANDWIDTH_KEY: self.bandwidth,
            self.VCPU_ARCHITECTURE_KEY: self.vcpu_architecture,
            self.VCPU_COUNT_KEY: self.vcpu_count,
            self.HREF_KEY: self.href,
            self.MEMORY_KEY: self.memory,
            self.OS_ARCHITECTURE_KEY: self.os_architecture,
            self.PORT_SPEED_KEY: self.port_speed,
            self.DISKS_KEY: self.disks,
            self.GPU_MODEL_KEY: self.gpu_model,
            self.GPU_COUNT_KEY: self.gpu_count,
            self.GPU_MEMORY_KEY: self.gpu_memory,
            self.GPU_MANUFACTURER_KEY: self.gpu_manufacturer,
            self.TOTAL_VOLUME_BANDWIDTH_KEY: self.total_volume_bandwidth,
            self.IBM_CLOUD_KEY: self.ibm_cloud.to_reference_json(),
            self.REGION_KEY: self.region.to_reference_json(),
        }

    @classmethod
    def from_ibm_json_body(cls, json_body):
        return cls(
            name=json_body["name"],
            family=json_body.get("family"),
            bandwidth=json_body["bandwidth"],
            vcpu_architecture=json_body["vcpu_architecture"],
            vcpu_count=json_body["vcpu_count"],
            href=json_body["href"],
            memory=json_body["memory"],
            os_architecture=json_body["os_architecture"],
            port_speed=json_body["port_speed"],
            disks=json_body["disks"],
        )

    def dis_params_eq(self, other):
        assert isinstance(other, self.__class__)

        return (self.name == other.name and self.family == other.family and self.vcpu_architecture ==
                other.vcpu_architecture)

    def mangos_params_eq(self, json_body):
        return (self.name == json_body["name"] and self.family == json_body.get("family") and self.vcpu_architecture ==
                json_body["vcpu_architecture"])

    def dis_add_update_db(self, session, db_instance_profiles, cloud_id, db_region):
        from ibm.models import IBMCloud

        db_instance_profiles_name_obj_dict = dict()
        for db_instance_profile in db_instance_profiles:
            db_instance_profiles_name_obj_dict[db_instance_profile.name] = db_instance_profile

        if self.name in db_instance_profiles_name_obj_dict:
            existing = db_instance_profiles_name_obj_dict[self.name]
        else:
            existing = None

        if not existing:
            cloud = session.query(IBMCloud).get(cloud_id)
            assert cloud

            cloud.instance_profiles.append(self)
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
        self.family = other.family
        self.vcpu_architecture = other.vcpu_architecture


class IBMNetworkInterface(IBMCloudResourceMixin, Base):
    ID_KEY = "id"
    NAME_KEY = "name"
    IS_PRIMARY_KEY = "is_primary"
    RESOURCE_ID_KEY = "resource_id"
    CREATED_AT_KEY = "created_at"
    ALLOW_IP_SPOOFING_KEY = "allow_ip_spoofing"
    HREF_KEY = "href"
    PORT_SPEED_KEY = "port_speed"
    PRIMARY_IPV4_ADDRESS_KEY = "primary_ipv4_address"
    RESOURCE_TYPE_KEY = "resource_type"
    IBM_STATUS_KEY = "ibm_status"
    TYPE_KEY = "type"
    SUBNET_KEY = "subnet"
    INSTANCE_KEY = "instance"
    FLOATING_IPS_KEY = "floating_ips"
    SECURITY_GROUPS_KEY = "security_groups"
    ASSOCIATED_RESOURCES_KEY = "associated_resources"

    CRZ_BACKREF_NAME = "network_interfaces"

    # status consts
    STATUS_AVAILABLE = "available"
    STATUS_DELETING = "deleting"
    STATUS_FAILED = "failed"
    STATUS_PENDING = "pending"
    ALL_STATUSES_LIST = [STATUS_AVAILABLE, STATUS_FAILED, STATUS_PENDING, STATUS_DELETING]

    # volume type
    TYPE_SECONDARY = "secondary"
    TYPE_PRIMARY = "primary"
    ALL_INTERFACES_TYPES = [TYPE_PRIMARY, TYPE_SECONDARY]

    # resource type
    TYPE_NETWORK_INTERFACE = "network_interface"

    __tablename__ = "ibm_network_interfaces"

    id = Column(String(32), primary_key=True)
    name = Column(String(255), nullable=False)
    is_primary = Column(Boolean, default=False, nullable=False)
    resource_id = Column(String(64), nullable=False)
    created_at = Column(DateTime, nullable=False)
    allow_ip_spoofing = Column(Boolean, nullable=False)
    href = Column(Text, nullable=False)
    port_speed = Column(Integer, nullable=False)
    primary_ipv4_address = Column(String(255), nullable=False)
    resource_type = Column(Enum(TYPE_NETWORK_INTERFACE), default=TYPE_NETWORK_INTERFACE, nullable=False)
    ibm_status = Column(Enum(*ALL_STATUSES_LIST), nullable=False)
    type_ = Column("type", Enum(*ALL_INTERFACES_TYPES), nullable=False)

    subnet_id = Column(String(32), ForeignKey("ibm_subnets.id", ondelete="SET NULL"), nullable=True)
    instance_id = Column(String(32), ForeignKey("ibm_instances.id", ondelete="CASCADE"))

    floating_ips = relationship("IBMFloatingIP", backref="network_interface", lazy="dynamic")
    security_groups = relationship(
        "IBMSecurityGroup", secondary=ibm_network_interfaces_security_groups, lazy="dynamic",
        backref=backref("network_interfaces", lazy="dynamic")
    )
    subnet = relationship(
        "IBMSubnet", backref=backref("network_interfaces", lazy="dynamic")
    )

    __table_args__ = (UniqueConstraint(name, instance_id, name="uix_ibm_interface_name_instance_id"),)

    def __init__(
            self, name, is_primary=None, resource_id=None, created_at=None, allow_ip_spoofing=None, href=None,
            port_speed=None, primary_ipv4_address=None, resource_type=None, ibm_status=None, type_=None
    ):
        self.id = str(uuid.uuid4().hex)
        self.name = name
        self.is_primary = is_primary
        self.resource_id = resource_id
        self.created_at = created_at
        self.allow_ip_spoofing = allow_ip_spoofing
        self.href = href
        self.port_speed = port_speed
        self.primary_ipv4_address = primary_ipv4_address
        self.resource_type = resource_type
        self.ibm_status = ibm_status
        self.type_ = type_

    @property
    def subnet_uuid(self):
        if self.subnet_id:
            return self.subnet_id
        elif self.ibm_subnet:
            return self.ibm_subnet.id
        return None

    def to_reference_json(self):
        return {
            self.ID_KEY: self.id,
            self.NAME_KEY: self.name,
            self.PRIMARY_IPV4_ADDRESS_KEY: self.primary_ipv4_address,
            self.ALLOW_IP_SPOOFING_KEY: self.allow_ip_spoofing,
            self.IS_PRIMARY_KEY: self.is_primary,
            self.SUBNET_KEY: self.subnet.to_reference_json() if self.subnet else {},
            self.SECURITY_GROUPS_KEY: [sec_grp.to_reference_json() for sec_grp in self.security_groups.all()],
            self.FLOATING_IPS_KEY: [floating_ip.to_reference_json() for floating_ip in self.floating_ips.all()]
        }

    def to_json(self):
        return {
            self.ID_KEY: self.id,
            self.NAME_KEY: self.name,
            self.IS_PRIMARY_KEY: self.is_primary,
            self.RESOURCE_ID_KEY: self.resource_id,
            self.CREATED_AT_KEY: self.created_at,
            self.ALLOW_IP_SPOOFING_KEY: self.allow_ip_spoofing,
            self.HREF_KEY: self.href,
            self.PORT_SPEED_KEY: self.port_speed,
            self.PRIMARY_IPV4_ADDRESS_KEY: self.primary_ipv4_address,
            self.RESOURCE_TYPE_KEY: self.resource_type,
            self.IBM_STATUS_KEY: self.ibm_status,
            self.TYPE_KEY: self.type_,
            self.IBM_CLOUD_KEY: self.ibm_cloud.to_reference_json(),
            self.ASSOCIATED_RESOURCES_KEY: {
                self.SUBNET_KEY: self.subnet.to_reference_json() if self.subnet else {},
                self.INSTANCE_KEY: self.instance.to_reference_json(),
                self.FLOATING_IPS_KEY: [floating_ip.to_reference_json() for floating_ip in self.floating_ips.all()],
                self.SECURITY_GROUPS_KEY: [sec_grp.to_reference_json() for sec_grp in self.security_groups.all()],
            }
        }

    def to_json_body(self):
        return {
            "name": self.name,
            "id": self.id or str(uuid.uuid4().hex),
            "subnet": {"id": self.subnet_uuid},
            "allow_ip_spoofing": self.allow_ip_spoofing,
            "floating_ip": False,
            "security_groups": [
                {
                    self.ID_KEY: security_group.id,
                    self.NAME_KEY: security_group.name
                }
                for security_group in self.security_groups.all()
            ],
        }

    @property
    def is_deletable(self):
        return self.type_ == self.TYPE_SECONDARY

    @classmethod
    def from_ibm_json_body(cls, json_body):
        return cls(
            name=json_body["name"],
            resource_id=json_body["id"],
            created_at=return_datetime_object(json_body["created_at"]),
            allow_ip_spoofing=json_body.get("allow_ip_spoofing"),
            href=json_body["href"],
            port_speed=json_body["port_speed"],
            primary_ipv4_address=json_body.get("primary_ipv4_address") or json_body.get("primary_ip", {}).get(
                "address"),
            resource_type=json_body["resource_type"],
            ibm_status=json_body["status"],
            type_=json_body["type"],
            is_primary=True if json_body["type"] == "primary" else False
        )

    def dis_params_eq(self, other):
        assert isinstance(other, self.__class__)

        return (self.name == other.name and self.is_primary == other.is_primary and
                self.resource_id == other.resource_id and self.allow_ip_spoofing == other.allow_ip_spoofing and
                self.href == other.href and self.port_speed == other.port_speed and
                self.primary_ipv4_address == other.primary_ipv4_address and
                self.resource_type == other.resource_type and self.ibm_status == other.ibm_status and
                self.type_ == other.type_)

    def update_from_object(self, other):
        assert isinstance(other, self.__class__)

        self.name = other.name
        self.is_primary = other.is_primary
        self.resource_id = other.resource_id
        self.allow_ip_spoofing = other.allow_ip_spoofing
        self.href = other.href
        self.port_speed = other.port_speed
        self.primary_ipv4_address = other.primary_ipv4_address
        self.resource_type = other.resource_type
        self.ibm_status = other.ibm_status
        self.type_ = other.type_


class IBMInstanceDisk(Base):
    ID_KEY = "id"
    NAME_KEY = "name"
    RESOURCE_ID_KEY = "resource_id"
    INTERFACE_TYPE_KEY = "interface_type"
    CREATED_AT_KEY = "created_at"
    SIZE_KEY = "size"
    HREF_KEY = "href"
    RESOURCE_TYPE_KEY = "resource_type"
    INSTANCE_KEY = "instance"
    DEDICATED_HOST_DISK_KEY = "dedicated_host_disk"

    # disk interface type consts
    INTERFACE_TYPE_VIRTIO_BLK = "virtio_blk"
    INTERFACE_TYPE_NVME = "nvme"
    ALL_INTERFACE_TYPES_LIST = [INTERFACE_TYPE_VIRTIO_BLK, INTERFACE_TYPE_NVME]
    # resource type
    TYPE_INSTANCE_DISK = "instance_disk"
    ALL_RESOURCE_TYPES_LIST = [TYPE_INSTANCE_DISK]

    __tablename__ = "ibm_instance_disks"

    id = Column(String(32), primary_key=True)
    name = Column(String(255), nullable=False)
    resource_id = Column(String(64), nullable=False)
    interface_type = Column(Enum(*ALL_INTERFACE_TYPES_LIST), nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow(), nullable=False)
    size = Column(Integer, nullable=False)
    href = Column(Text, nullable=False)
    resource_type = Column(Enum(*ALL_RESOURCE_TYPES_LIST), default=TYPE_INSTANCE_DISK, nullable=False)

    instance_id = Column(String(32), ForeignKey("ibm_instances.id", ondelete="CASCADE"))
    dedicated_host_disk_id = Column(String(32), ForeignKey("ibm_dedicated_host_disks.id", ondelete="SET NULL"),
                                    nullable=True)

    __table_args__ = (UniqueConstraint(name, instance_id, name="uix_ibm_disk_name_instance_id"),)

    def __init__(self, name, resource_id, interface_type, created_at, size, href, resource_type, instance_id=None):
        self.id = str(uuid.uuid4().hex)
        self.name = name
        self.resource_id = resource_id
        self.interface_type = interface_type
        self.created_at = created_at
        self.size = size
        self.href = href
        self.resource_type = resource_type
        self.instance_id = instance_id

    def to_reference_json(self):
        return {
            self.ID_KEY: self.id,
            self.NAME_KEY: self.name
        }

    def to_json(self, parent_reference=True):
        json_data = {
            self.ID_KEY: self.id,
            self.NAME_KEY: self.name,
            self.RESOURCE_ID_KEY: self.resource_id,
            self.INTERFACE_TYPE_KEY: self.interface_type,
            self.CREATED_AT_KEY: self.created_at,
            self.SIZE_KEY: self.size,
            self.HREF_KEY: self.href,
            self.RESOURCE_TYPE_KEY: self.resource_type,
            self.DEDICATED_HOST_DISK_KEY:
                self.dedicated_host_disk.to_reference_json() if self.dedicated_host_disk else {},
        }

        if parent_reference:
            json_data[self.INSTANCE_KEY] = self.instance.to_reference_json()

        return json_data

    @classmethod
    def from_ibm_json_body(cls, json_body):
        return cls(
            name=json_body["name"],
            resource_id=json_body["id"],
            interface_type=json_body["interface_type"],
            created_at=datetime.strptime(json_body["created_at"], CREATED_AT_FORMAT),
            size=json_body["size"],
            href=json_body["href"],
            resource_type=json_body["resource_type"],
        )

    def dis_params_eq(self, other):
        assert isinstance(other, self.__class__)

        return (self.name == other.name and self.interface_type == other.interface_type and
                self.created_at == other.created_at and self.size == other.size and self.href == other.href and
                self.resource_id == other.resource_id)

    def dis_add_update_db(self, db_session, db_instance_disks, db_cloud, db_instance):
        if not db_instance:
            return
        db_instance_disks_id_obj_dict = dict()
        db_instance_disks_name_obj_dict = dict()
        for db_instance_disk in db_instance_disks:
            db_instance_disks_id_obj_dict[db_instance_disk.resource_id] = db_instance_disk
            db_instance_disks_name_obj_dict[db_instance_disk.name] = db_instance_disk

        if self.resource_id not in db_instance_disks_id_obj_dict and self.name in db_instance_disks_name_obj_dict:
            # Creation Pending / Creating
            existing = db_instance_disks_name_obj_dict[self.name]
        elif self.resource_id in db_instance_disks_id_obj_dict:
            # Created. Update everything including name
            existing = db_instance_disks_id_obj_dict[self.resource_id]
        else:
            existing = None

        if not existing:
            self.instance = db_instance

            db_session.add(self)
            db_session.commit()
            return

        if not self.dis_params_eq(existing):
            existing.update_from_object(self)
            existing.instance = db_instance

        db_session.commit()

    def update_from_object(self, other):
        assert isinstance(other, self.__class__)

        self.name = other.name
        self.interface_type = other.interface_type
        self.created_at = other.created_at
        self.size = other.size
        self.href = other.href
        self.resource_id = other.resource_id
