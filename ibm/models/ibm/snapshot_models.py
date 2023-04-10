import uuid
from datetime import datetime

from sqlalchemy import Boolean, Column, DateTime, Enum, ForeignKey, Integer, String, Text
from sqlalchemy.orm import backref, relationship
from sqlalchemy.schema import UniqueConstraint

from ibm import get_db_session as db
from ibm.common.consts import CREATED_AT_FORMAT
from ibm.models.base import Base
from ibm.models.ibm.mixins import IBMRegionalResourceMixin


class IBMSnapshot(IBMRegionalResourceMixin, Base):
    ID_KEY = "id"
    NAME_KEY = "name"
    CRN_KEY = "crn"
    RESOURCE_ID_KEY = "resource_id"
    HREF_KEY = "href"
    DELETABLE_KEY = "deletable"
    CREATED_AT_KEY = "created_at"
    BOOTABLE_KEY = "bootable"
    ENCRYPTION_KEY = "encryption"
    LIFECYCLE_STATE_KEY = "lifecycle_state"
    MINIMUM_CAPACITY_KEY = "minimum_capacity"
    SIZE_KEY = "size"
    RESOURCE_TYPE_KEY = "resource_type"
    ENCRYPTION_KEY_CRN_KEY = "encryption_key_crn"
    REGION_KEY = "region"
    RESOURCE_TYPE_SNAPSHOT_KEY = "Snapshot"
    COST_KEY = "cost"
    ESTIMATED_SAVINGS = "estimated_savings"

    CRZ_BACKREF_NAME = "snapshots"

    # encryption consts
    ENCRYPTION_PROVIDER_MANAGED = "provider_managed"
    ENCRYPTION_USER_MANAGED = "user_managed"
    ALL_ENCRYPTION_LIST = [ENCRYPTION_PROVIDER_MANAGED, ENCRYPTION_USER_MANAGED]

    # lifecycle state consts
    STATE_DELETING = "deleting"
    STATE_FAILED = "failed"
    STATE_PENDING = "pending"
    STATE_STABLE = "stable"
    STATE_UPDATING = "updating"
    STATE_WAITING = "waiting"
    STATE_SUSPENDED = "suspended"
    LIFECYCLE_STATES_LIST = [
        STATE_DELETING, STATE_FAILED, STATE_PENDING, STATE_STABLE, STATE_UPDATING, STATE_WAITING, STATE_SUSPENDED]

    # resource type
    RESOURCE_TYPE_SNAPSHOT = "snapshot"

    __tablename__ = "ibm_snapshots"

    id = Column(String(32), primary_key=True)
    name = Column(String(255), nullable=False)
    crn = Column(String(255), nullable=False)
    resource_id = Column(String(64), nullable=False)
    href = Column(Text, nullable=False)
    deletable = Column(Boolean, nullable=False)
    created_at = Column(DateTime, nullable=False)
    bootable = Column(Boolean, nullable=False)
    encryption = Column(Enum(ENCRYPTION_PROVIDER_MANAGED, ENCRYPTION_USER_MANAGED), nullable=False)
    lifecycle_state = Column(String(50), nullable=False)
    minimum_capacity = Column(Integer, nullable=False)
    size = Column(Integer, nullable=False)
    resource_type = Column(Enum(RESOURCE_TYPE_SNAPSHOT), nullable=False)
    encryption_key_crn = Column(String(255))

    resource_group_id = Column(String(32), ForeignKey("ibm_resource_groups.id", ondelete="CASCADE"))
    source_volume_id = Column(String(32), ForeignKey("ibm_volumes.id", ondelete="SET NULL"),
                              nullable=True)
    operating_system_id = Column(String(32), ForeignKey("ibm_operating_systems.id", ondelete="SET NULL"), nullable=True)
    source_image_id = Column(String(32), ForeignKey("ibm_images.id", ondelete="SET NULL"), nullable=True)

    resource_group = relationship(
        "IBMResourceGroup", backref=backref("snapshots", cascade="all, delete-orphan", passive_deletes=True,
                                            lazy="dynamic")
    )
    source_image = relationship("IBMImage", backref="sourced_snapshots", foreign_keys=[source_image_id])
    source_volume = relationship("IBMVolume", backref="sourced_snapshots", foreign_keys=[source_volume_id])
    operating_system = relationship(
        "IBMOperatingSystem", backref="sourced_snapshots", foreign_keys=[operating_system_id]
    )

    __table_args__ = (
        UniqueConstraint(name, "region_id", "cloud_id", name="uix_ibm_snapshots_name_region_id_cloud_id"),
    )

    def __init__(
            self, name=None, crn=None, resource_id=None, href=None, deletable=None, created_at=None, bootable=None,
            encryption=None, lifecycle_state=None, minimum_capacity=None, size=None, resource_type=None,
            encryption_key_crn=None
    ):
        self.id = str(uuid.uuid4().hex)
        self.name = name
        self.crn = crn
        self.resource_id = resource_id
        self.href = href
        self.deletable = deletable
        self.created_at = created_at
        self.bootable = bootable
        self.encryption = encryption
        self.lifecycle_state = lifecycle_state
        self.minimum_capacity = minimum_capacity
        self.size = size
        self.resource_type = resource_type
        self.encryption_key_crn = encryption_key_crn

    def to_reference_json(self):
        return {
            self.ID_KEY: self.id,
            self.NAME_KEY: self.name
        }

    def to_json(self):
        return {
            self.ID_KEY: self.id,
            self.NAME_KEY: self.name,
            self.CRN_KEY: self.crn,
            self.RESOURCE_ID_KEY: self.resource_id,
            self.HREF_KEY: self.href,
            self.DELETABLE_KEY: self.deletable,
            self.CREATED_AT_KEY: self.created_at,
            self.BOOTABLE_KEY: self.bootable,
            self.ENCRYPTION_KEY: self.encryption,
            self.LIFECYCLE_STATE_KEY: self.lifecycle_state,
            self.MINIMUM_CAPACITY_KEY: self.minimum_capacity,
            self.SIZE_KEY: self.size,
            self.RESOURCE_TYPE_KEY: self.resource_type,
            self.ENCRYPTION_KEY_CRN_KEY: self.encryption_key_crn,
            self.REGION_KEY: self.region.to_reference_json()
        }

    def to_idle_json(self, session=None):
        from ibm.models.ibm.cost_models import IBMResourceInstancesCost

        session = session if session else db.session
        cost_obj = IBMResourceInstancesCost.get_cost(self.crn, self.cloud_id, session)
        return {
            self.CRN_KEY: self.crn,
            self.HREF_KEY: self.href,
            self.DELETABLE_KEY: self.deletable,
            self.BOOTABLE_KEY: self.bootable,
            self.ENCRYPTION_KEY: self.encryption,
            self.LIFECYCLE_STATE_KEY: self.lifecycle_state,
            self.RESOURCE_TYPE_KEY: self.RESOURCE_TYPE_SNAPSHOT_KEY,
            self.RESOURCE_ID_KEY: self.resource_id,
            self.IBM_CLOUD_KEY: self.cloud_id,
            self.COST_KEY: cost_obj.estimated_cost if cost_obj else None,
            self.ESTIMATED_SAVINGS: cost_obj.estimated_cost if cost_obj else None,

        }

    @classmethod
    def from_ibm_json_body(cls, json_body):
        return cls(
            name=json_body["name"],
            crn=json_body["crn"],
            resource_id=json_body["id"],
            href=json_body["href"],
            deletable=json_body["deletable"],
            created_at=datetime.strptime(json_body["created_at"], CREATED_AT_FORMAT),
            bootable=json_body["bootable"],
            encryption=json_body["encryption"],
            lifecycle_state=json_body["lifecycle_state"],
            minimum_capacity=json_body["minimum_capacity"],
            size=json_body["size"],
            resource_type=json_body["resource_type"],
            encryption_key_crn=json_body["encryption_key"]["crn"] if "encryption_key" in json_body else None,
        )

    def dis_params_eq(self, other):
        assert isinstance(other, self.__class__)

        return (self.name == other.name and self.crn == other.crn and self.resource_id == other.resource_id and
                self.href == other.href and self.deletable == other.deletable and self.bootable == other.bootable and
                self.encryption == other.encryption and self.lifecycle_state == other.lifecycle_state and
                self.minimum_capacity == other.minimum_capacity and self.size == other.size and
                self.resource_type == other.resource_type and self.encryption_key_crn == other.encryption_key_crn)

    def dis_add_update_db(self, db_session, db_snapshots, db_cloud, db_resource_group, db_region, db_image=None,
                          db_volume=None, db_operating_system=None):
        if not db_resource_group:
            return
        db_snapshots_id_obj_dict = dict()
        db_snapshots_name_obj_dict = dict()
        for db_snapshot in db_snapshots:
            db_snapshots_id_obj_dict[db_snapshot.resource_id] = db_snapshot
            db_snapshots_name_obj_dict[db_snapshot.name] = db_snapshot
        if self.resource_id not in db_snapshots_id_obj_dict and self.name in db_snapshots_name_obj_dict:
            # Creation Pending / Creating
            existing = db_snapshots_name_obj_dict[self.name]
        elif self.resource_id in db_snapshots_id_obj_dict:
            # Created. Update everything including name
            existing = db_snapshots_id_obj_dict[self.resource_id]
        else:
            existing = None
        if not existing:
            self.ibm_cloud = db_cloud
            self.resource_group = db_resource_group
            if db_volume:
                self.source_volume = db_volume
            if db_volume:
                self.source_image = db_image
            if db_operating_system:
                self.operating_system = db_operating_system

            self.region = db_region
            db_session.add(self)
            db_session.commit()
            return

        if not self.dis_params_eq(existing):
            existing.update_from_object(self)
            existing.resource_group = db_resource_group
            if db_volume:
                existing.source_volume = db_volume
            if db_image:
                existing.source_image = db_image
            if db_operating_system:
                existing.operating_system = db_operating_system

            existing.region = db_region
        db_session.commit()

    def update_from_object(self, other):
        assert isinstance(other, self.__class__)

        self.name = other.name
        self.crn = other.crn
        self.resource_id = other.resource_id
        self.href = other.href
        self.deletable = other.deletable
        self.bootable = other.bootable
        self.encryption = other.encryption
        self.lifecycle_state = other.lifecycle_state
        self.minimum_capacity = other.minimum_capacity
        self.size = other.size
        self.resource_type = other.resource_type
        self.encryption_key_crn = other.encryption_key_crn
