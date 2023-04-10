import uuid
from datetime import datetime

from sqlalchemy import Boolean, Column, DateTime, ForeignKey, Integer, PrimaryKeyConstraint, String, Table, Text
from sqlalchemy.orm import backref, relationship
from sqlalchemy.schema import UniqueConstraint

from ibm.common.consts import CREATED
from ibm.common.utils import return_datetime_object
from ibm.models.base import Base
from ibm.models.ibm.mixins import IBMZonalResourceMixin

ibm_network_interface_prototypes_security_groups = Table(
    "ibm_network_interface_protoypes_security_groups", Base.metadata,
    Column(
        "network_interface_prototype_id", String(32), ForeignKey("ibm_network_interface_prototypes.id",
                                                                 ondelete="CASCADE")),
    Column("security_group_id", String(32), ForeignKey("ibm_security_groups.id", ondelete="CASCADE")),
    PrimaryKeyConstraint("network_interface_prototype_id", "security_group_id"),
)

ibm_instance_template_keys = Table(
    "ibm_instance_template_keys", Base.metadata,
    Column("instance_template_id", String(32), ForeignKey("ibm_instance_templates.id", ondelete="CASCADE")),
    Column("key_id", String(32), ForeignKey("ibm_ssh_keys.id", ondelete="CASCADE")),
    PrimaryKeyConstraint("instance_template_id", "key_id"),
)


class IBMInstanceTemplate(IBMZonalResourceMixin, Base):
    ID_KEY = "id"
    NAME_KEY = "name"
    RESOURCE_ID_KEY = "resource_id"
    CREATED_AT_KEY = "created_at"
    HREF_KEY = "href"
    CRN_KEY = "crn"
    ZONE_KEY = "zone"
    USER_DATA_KEY = "user_data"
    REGION_KEY = "region"
    VPC_KEY = "vpc"
    IMAGE_KEY = "image"
    PLACEMENT_TARGET_KEY = "placement_target"
    PRIMARY_NETWORK_INTERFACE_KEY = "primary_network_interface"
    BOOT_VOLUME_ATTACHMENT_KEY = "boot_volume_attachment"
    NETWORK_INTERFACES_KEY = "network_interfaces"
    VOLUME_ATTACHMENTS_KEY = "volume_attachments"
    BANDWIDTH_KEY = "bandwidth"
    STATUS_KEY = "status"
    ASSOCIATED_RESOURCES_KEY = "associated_resources"
    KEYS_KEY = "keys"
    PLACEMENT_GROUP_KEY = "placement_group"
    DEDICATED_HOST_KEY = "dedicated_host"
    DEDICATED_HOST_GROUP_KEY = "dedicated_host_group"
    PROFILE_KEY = "profile"
    RESOURCE_GROUP_KEY = "resource_group"

    CRZ_BACKREF_NAME = "instance_templates"

    __tablename__ = "ibm_instance_templates"

    id = Column(String(32), primary_key=True)
    name = Column(String(64), nullable=False)
    status = Column(String(50), nullable=False)
    resource_id = Column(String(64), nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow(), nullable=False)
    href = Column(Text, nullable=False)
    crn = Column(String(255), nullable=False)
    user_data = Column(Text)
    total_volume_bandwidth = Column(Integer)

    resource_group_id = Column(String(32), ForeignKey("ibm_resource_groups.id", ondelete="CASCADE"))
    vpc_id = Column(String(32), ForeignKey("ibm_vpc_networks.id", ondelete="SET NULL"), nullable=True)
    placement_target_dh_id = Column(String(32), ForeignKey("ibm_dedicated_hosts.id", ondelete="SET NULL"),
                                    nullable=True)
    placement_target_dh_group_id = Column(String(32), ForeignKey("ibm_dedicated_host_groups.id", ondelete="SET NULL"),
                                          nullable=True)
    placement_target_placement_group_id = Column(String(32), ForeignKey("ibm_placement_groups.id", ondelete="SET NULL"),
                                                 nullable=True)
    instance_profile_id = Column(String(32), ForeignKey("ibm_instance_profiles.id", ondelete="SET NULL"), nullable=True)
    image_id = Column(String(32), ForeignKey("ibm_images.id", ondelete="SET NULL"), nullable=True)

    resource_group = relationship(
        "IBMResourceGroup", backref=backref("instance_templates", cascade="all, delete-orphan", passive_deletes=True,
                                            lazy="dynamic")
    )
    vpc_network = relationship(
        "IBMVpcNetwork",
        backref=backref("instance_templates", cascade="all, delete-orphan", passive_deletes=True, lazy="dynamic")
    )
    network_interfaces = relationship(
        "IBMNetworkInterfacePrototype", backref="instance_template", cascade="all, delete-orphan", passive_deletes=True,
        lazy="dynamic"
    )
    keys = relationship(
        "IBMSshKey", secondary=ibm_instance_template_keys, lazy="dynamic",
        backref=backref("instance_templates", lazy="dynamic")
    )
    _placement_target_dh = relationship("IBMDedicatedHost", backref=backref("instance_templates", lazy="dynamic"))
    _placement_target_dh_group = relationship(
        "IBMDedicatedHostGroup", backref=backref("instance_templates", lazy="dynamic")
    )
    _placement_target_placement_group = relationship(
        "IBMPlacementGroup", backref=backref("instance_template", lazy="dynamic")
    )
    instance_profile = relationship(
        "IBMInstanceProfile", backref=backref("instance_templates", lazy="dynamic")
    )
    volume_attachments = relationship(
        "IBMVolumeAttachmentPrototype", backref="instance_template", cascade="all, delete-orphan", passive_deletes=True,
        lazy="dynamic"
    )
    image = relationship("IBMImage", backref=backref("instance_templates", lazy="dynamic"))
    instance_groups = relationship(
        "IBMInstanceGroup",
        backref="instance_template",
        cascade="all, delete-orphan",
        passive_deletes=True,
        lazy="dynamic"
    )
    instance_group_memberships = relationship(
        "IBMInstanceGroupMembership",
        backref="instance_template",
        cascade="all, delete-orphan",
        passive_deletes=True,
        lazy="dynamic"
    )

    __table_args__ = (
        UniqueConstraint(name, "region_id", "cloud_id", name="uix_ibm_instance_template_name_region_id_cloud_id"),
    )

    def __init__(
            self, name=None, resource_id=None, created_at=None, href=None, crn=None, user_data=None,
            total_volume_bandwidth=None, status=CREATED
    ):
        self.id = str(uuid.uuid4().hex)
        self.name = name
        self.resource_id = resource_id
        self.created_at = created_at
        self.href = href
        self.crn = crn
        self.user_data = user_data
        self.total_volume_bandwidth = total_volume_bandwidth
        self.status = status

    @property
    def placement_target(self):
        return self._placement_target_dh or self._placement_target_dh_group or self._placement_target_placement_group

    @placement_target.setter
    def placement_target(self, placement_target):
        from ibm.models import IBMDedicatedHost, IBMDedicatedHostGroup, IBMPlacementGroup
        if isinstance(placement_target, IBMDedicatedHost):
            self._placement_target_dh = placement_target
            self._placement_target_dh_group = None
            self._placement_target_placement_group = None
        elif isinstance(placement_target, IBMDedicatedHostGroup):
            self._placement_target_dh_group = placement_target
            self._placement_target_dh = None
            self._placement_target_placement_group = None
        elif isinstance(placement_target, IBMPlacementGroup):
            self._placement_target_placement_group = placement_target
            self._placement_target_dh = None
            self._placement_target_dh_group = None

    def to_reference_json(self):
        return {
            self.ID_KEY: self.id,
            self.NAME_KEY: self.name,
            self.ZONE_KEY: self.zone.to_reference_json()
        }

    def to_json(self):
        # TODO: References/relations in to_json
        return {
            self.ID_KEY: self.id,
            self.NAME_KEY: self.name,
            self.STATUS_KEY: self.status,
            self.RESOURCE_ID_KEY: self.resource_id,
            self.CREATED_AT_KEY: self.created_at,
            self.RESOURCE_GROUP_KEY: self.resource_group.to_reference_json(),
            self.HREF_KEY: self.href,
            self.CRN_KEY: self.crn,
            self.VPC_KEY: self.vpc_network.to_reference_json() if self.vpc_network else {},
            self.ZONE_KEY: self.zone.to_reference_json(),
            self.USER_DATA_KEY: self.user_data,
            self.PLACEMENT_TARGET_KEY: self.placement_target.to_reference_json() if self.placement_target else {},
            self.REGION_KEY: self.region.to_reference_json(),
            self.BANDWIDTH_KEY: self.total_volume_bandwidth,
            self.IMAGE_KEY: self.image.to_reference_json() if self.image else {},
            self.PROFILE_KEY: self.instance_profile.to_reference_json() if self.instance_profile else {},
            self.ASSOCIATED_RESOURCES_KEY: {
                self.PLACEMENT_GROUP_KEY: self._placement_target_placement_group.to_reference_json() if
                self._placement_target_placement_group else {},
                self.KEYS_KEY: [ssh_key.to_json() for ssh_key in self.keys.all()],
                self.DEDICATED_HOST_KEY: self._placement_target_dh.to_reference_json() if
                self._placement_target_dh else {},
                self.DEDICATED_HOST_GROUP_KEY: self._placement_target_dh_group.to_reference_json() if
                self._placement_target_dh_group else {},
                self.VOLUME_ATTACHMENTS_KEY: [volume_attachment.to_reference_json() for volume_attachment in
                                              self.volume_attachments.all()],
                self.NETWORK_INTERFACES_KEY: [network_interface.to_reference_json() for network_interface in
                                              self.network_interfaces.all()]

            },
        }

    @classmethod
    def from_ibm_json_body(cls, json_body):
        return cls(
            name=json_body["name"],
            resource_id=json_body["id"],
            created_at=return_datetime_object(json_body["created_at"]),
            href=json_body["href"],
            crn=json_body["crn"],
            user_data=json_body.get("user_data"),
            total_volume_bandwidth=json_body.get("total_volume_bandwidth")
        )

    @property
    def primary_network_interface(self):
        return self.network_interfaces.filter_by(is_primary=True).first()

    @property
    def boot_volume_attachment(self):
        return self.volume_attachments.filter_by(is_boot=True).first()


class IBMNetworkInterfacePrototype(Base):
    ID_KEY = "id"
    NAME_KEY = "name"
    ALLOW_IP_SPOOFING_KEY = "allow_ip_spoofing"
    PRIMARY_IPV4_ADDRESS_KEY = "primary_ipv4_address"
    SUBNET_KEY = "subnet"
    SECURITY_GROUPS_KEY = "security_groups"
    IS_PRIMARY_KEY = "is_primary"

    __tablename__ = "ibm_network_interface_prototypes"

    id = Column(String(32), primary_key=True)
    name = Column(String(255))
    allow_ip_spoofing = Column(Boolean, default=False, nullable=False)
    primary_ipv4_address = Column(String(15))
    is_primary = Column(Boolean, default=False, nullable=False)

    instance_template_id = Column(String(32), ForeignKey("ibm_instance_templates.id", ondelete="CASCADE"))
    subnet_id = Column(String(32), ForeignKey("ibm_subnets.id", ondelete="CASCADE"))

    subnet = relationship(
        "IBMSubnet", backref=backref("network_interface_prototypes", cascade="all, delete-orphan", passive_deletes=True,
                                     lazy="dynamic")
    )
    security_groups = relationship(
        "IBMSecurityGroup", secondary=ibm_network_interface_prototypes_security_groups, lazy="dynamic",
        backref=backref("network_interface_prototypes", lazy="dynamic")
    )

    def __init__(self, name=None, allow_ip_spoofing=False, primary_ipv4_address=None, is_primary=False):
        self.id = str(uuid.uuid4().hex)
        self.name = name
        self.allow_ip_spoofing = allow_ip_spoofing
        self.primary_ipv4_address = primary_ipv4_address
        self.is_primary = is_primary

    def to_reference_json(self):
        return {
            self.ID_KEY: self.id,
            self.NAME_KEY: self.name,
            self.PRIMARY_IPV4_ADDRESS_KEY: self.primary_ipv4_address,
            self.ALLOW_IP_SPOOFING_KEY: self.allow_ip_spoofing,
            self.IS_PRIMARY_KEY: self.is_primary,
            self.SUBNET_KEY: self.subnet.to_reference_json() if self.subnet else {},
            self.SECURITY_GROUPS_KEY: [sec_grp.to_reference_json() for sec_grp in self.security_groups.all()]
        }

    def to_json(self):
        return {
            self.ID_KEY: self.id,
            self.NAME_KEY: self.name,
            self.ALLOW_IP_SPOOFING_KEY: self.allow_ip_spoofing,
            self.PRIMARY_IPV4_ADDRESS_KEY: self.primary_ipv4_address,
            self.SUBNET_KEY: self.subnet.to_reference_json(),
            self.SECURITY_GROUPS_KEY: [sec_grp.to_reference_json() for sec_grp in self.security_groups.all()],
            self.IS_PRIMARY_KEY: self.is_primary,
        }

    @classmethod
    def from_ibm_json_body(cls, json_body):
        return cls(
            name=json_body.get("name"),
            allow_ip_spoofing=json_body.get("allow_ip_spoofing"),
            primary_ipv4_address=json_body.get("primary_ipv4_address"),
        )


class IBMVolumeAttachmentPrototype(Base):
    ID_KEY = "id"
    NAME_KEY = "name"
    DELETE_VOLUME_ON_INSTANCE_DELETE_KEY = "delete_volume_on_instance_delete"
    IS_BOOT_KEY = "is_boot"
    VOLUME_KEY = "volume"
    STATUS_KEY = "status"
    TYPE_KEY = "type"

    __tablename__ = "ibm_volume_attachment_prototypes"

    id = Column(String(32), primary_key=True)
    name = Column(String(255))
    status = Column(String(50), nullable=False)
    delete_volume_on_instance_delete = Column(Boolean, default=False)
    is_boot = Column(Boolean, default=False, nullable=False)

    instance_template_id = Column(String(32), ForeignKey("ibm_instance_templates.id", ondelete="SET NULL"),
                                  nullable=True)
    provisioned_volume_id = Column(String(32), ForeignKey("ibm_volumes.id", ondelete="SET NULL"), nullable=True)
    volume_prototype_id = Column(String(32), ForeignKey("ibm_volume_prototypes.id", ondelete="SET NULL"), nullable=True)

    _provisioned_volume = relationship(
        "IBMVolume",
        backref=backref("volume_attachment_prototypes", cascade="all, delete-orphan", passive_deletes=True,
                        lazy="dynamic")
    )
    _volume_prototype = relationship(
        "IBMVolumePrototype",
        backref=backref("volume_attachment_prototypes", cascade="all, delete-orphan", passive_deletes=True,
                        lazy="dynamic")
    )

    def __init__(self, name=None, delete_volume_on_instance_delete=None, is_boot=False, status=CREATED):
        self.id = str(uuid.uuid4().hex)
        self.name = name
        self.delete_volume_on_instance_delete = delete_volume_on_instance_delete
        self.is_boot = is_boot
        self.status = status

    def to_reference_json(self):
        data = {
            self.ID_KEY: self.id,
            self.NAME_KEY: self.name,
            self.DELETE_VOLUME_ON_INSTANCE_DELETE_KEY: self.delete_volume_on_instance_delete,
            self.VOLUME_KEY: self._volume_prototype.to_reference_json()
        }

        if self.is_boot:
            data[self.TYPE_KEY] = "boot"
        else:
            data[self.TYPE_KEY] = "data"

        return data

    def to_json(self):
        return {
            self.ID_KEY: self.id,
            self.NAME_KEY: self.name,
            self.DELETE_VOLUME_ON_INSTANCE_DELETE_KEY: self.delete_volume_on_instance_delete,
            self.IS_BOOT_KEY: self.is_boot,
            self.VOLUME_KEY: self.volume.to_json(),
            self.STATUS_KEY: self.status
        }

    @classmethod
    def from_ibm_json_body(cls, json_body):
        return cls(
            name=json_body.get("name"),
            delete_volume_on_instance_delete=json_body.get("delete_volume_on_instance_delete")
        )

    @property
    def volume(self):
        return self._volume_prototype or self._provisioned_volume

    @volume.setter
    def volume(self, volume_obj):
        from ibm.models import IBMVolume

        if isinstance(volume_obj, IBMVolume):
            self._provisioned_volume = volume_obj
            self._volume_prototype = None
        elif isinstance(volume_obj, IBMVolumePrototype):
            self._volume_prototype = volume_obj
            self._provisioned_volume = None


# TODO: Verify/modify
class IBMVolumePrototype(Base):
    ID_KEY = "id"
    IOPS_KEY = "iops"
    NAME_KEY = "name"
    CAPACITY_KEY = "capacity"
    ENCRYPTION_KEY_CRN_KEY = "encryption_key_crn"
    PROFILE_KEY = "profile"

    __tablename__ = "ibm_volume_prototypes"

    id = Column(String(32), primary_key=True)
    iops = Column(Integer)
    name = Column(String(255))
    capacity = Column(Integer)
    encryption_key_crn = Column(String(255))

    volume_profile_id = Column(String(32), ForeignKey("ibm_volume_profiles.id", ondelete="CASCADE"))
    source_snapshot_id = Column(String(32), ForeignKey("ibm_snapshots.id", ondelete="SET NULL"), nullable=True)

    profile = relationship("IBMVolumeProfile", backref=backref("volume_prototypes", lazy="dynamic"))
    source_snapshot = relationship("IBMSnapshot", backref=backref("volume_prototypes", lazy="dynamic"))

    def __init__(self, iops, name, capacity, encryption_key_crn):
        self.id = str(uuid.uuid4().hex)
        self.iops = iops
        self.name = name
        self.capacity = capacity
        self.encryption_key_crn = encryption_key_crn

    def to_reference_json(self):
        return {
            self.ID_KEY: self.id,
            self.NAME_KEY: self.name,
            self.CAPACITY_KEY: self.capacity,
            self.IOPS_KEY: self.iops,
            self.PROFILE_KEY: self.profile.to_json()
        }

    def to_json(self):
        return {
            self.ID_KEY: self.id,
            self.IOPS_KEY: self.iops,
            self.NAME_KEY: self.name,
            self.CAPACITY_KEY: self.capacity,
            self.ENCRYPTION_KEY_CRN_KEY: self.encryption_key_crn,
        }

    @classmethod
    def from_ibm_json_body(cls, json_body):
        return cls(
            iops=json_body.get("iops"),
            name=json_body.get("name"),
            capacity=json_body.get("capacity"),
            encryption_key_crn=json_body.get("encryption_key")["crn"] if "encryption_key" in json_body else None,
        )
