import logging
import uuid
from datetime import datetime

from sqlalchemy import Boolean, Column, DateTime, Enum, ForeignKey, Integer, JSON, orm, String, Text
from sqlalchemy.orm import backref, relationship
from sqlalchemy.schema import UniqueConstraint

from ibm import get_db_session as db
from ibm.common.utils import return_datetime_object
from ibm.models.base import Base
from ibm.models.ibm.mixins import IBMRegionalResourceMixin, IBMZonalResourceMixin

LOGGER = logging.getLogger(__name__)


class IBMVolumeProfile(IBMRegionalResourceMixin, Base):
    ID_KEY = "id"
    NAME_KEY = "name"
    FAMILY_KEY = "family"
    GENERATION_KEY = "generation"
    REGION_KEY = "region"
    HREF_KEY = "href"
    ALL_FAMILIES = ["tiered", "custom"]
    CRZ_BACKREF_NAME = "volume_profiles"

    __tablename__ = "ibm_volume_profiles"

    id = Column(String(32), primary_key=True)
    name = Column(String(255), nullable=False)
    family = Column(Enum(*ALL_FAMILIES), nullable=False)
    href = Column(String(255), nullable=False)

    __table_args__ = (
        UniqueConstraint(name, "region_id", "cloud_id", name="uix_ibm_volume_profile_name_region_id_cloud_id"),
    )

    def __init__(self, name=None, href=None, family=None, cloud_id=None):
        self.id = str(uuid.uuid4().hex)
        self.name = name
        self.family = family
        self.href = href
        self.cloud_id = cloud_id

    def to_reference_json(self):
        return {
            self.ID_KEY: self.id,
            self.NAME_KEY: self.name
        }

    def to_json(self):
        return {
            self.ID_KEY: self.id,
            self.NAME_KEY: self.name,
            self.FAMILY_KEY: self.family,
            # self.REGION_KEY: self.region,
            self.HREF_KEY: self.href
        }

    @classmethod
    def from_ibm_json_body(cls, json_body):
        return cls(
            name=json_body["name"], href=json_body["href"], family=json_body.get("family")
        )

    def dis_params_eq(self, other):
        assert isinstance(other, self.__class__)

        return self.name == other.name and self.family == other.family

    def dis_add_update_db(self, session, db_volume_profiles, cloud_id, db_region):
        from ibm.models import IBMCloud

        db_volume_profiles_name_obj_dict = dict()
        for db_volume_profile in db_volume_profiles:
            db_volume_profiles_name_obj_dict[db_volume_profile.name] = db_volume_profile

        if self.name in db_volume_profiles_name_obj_dict:
            existing = db_volume_profiles_name_obj_dict[self.name]
        else:
            existing = None

        if not existing:
            cloud = session.query(IBMCloud).get(cloud_id)
            assert cloud

            cloud.volume_profiles.append(self)
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


class IBMVolume(IBMZonalResourceMixin, Base):
    ID_KEY = "id"
    NAME_KEY = "name"
    RESOURCE_ID_KEY = "resource_id"
    ACTIVE_KEY = "active"
    CREATED_AT_KEY = "created_at"
    CRN_KEY = "crn"
    HREF_KEY = "href"
    BUSY_KEY = "busy"
    CAPACITY_KEY = "capacity"
    ENCRYPTION_KEY = "encryption"
    IOPS_KEY = "iops"
    STATUS_KEY = "status"
    IBM_STATUS_REASONS_KEY = "ibm_status_reasons"
    ENCRYPTION_KEY_CRN_KEY = "encryption_key_crn"
    RESOURCE_GROUP_KEY = "resource_group"
    PROFILE_KEY = "profile"
    OPERATING_SYSTEM_KEY = "operating_system"
    SOURCE_IMAGE_KEY = "source_image"
    SOURCE_SNAPSHOT_KEY = "source_snapshot"
    VOLUME_ATTACHMENTS_KEY = "volume_attachments"
    RESOURCE_JSON_KEY = "resource_json"
    RESOURCE_TYPE_VOLUME_KEY = "Volume"
    RESOURCE_TYPE_KEY = "resource_type"
    ESTIMATED_SAVINGS = "estimated_savings"
    COST_KEY = "cost"

    CRZ_BACKREF_NAME = "volumes"

    # encryption consts
    ENCRYPTION_PROVIDER_MANAGED = "provider_managed"
    ENCRYPTION_USER_MANAGED = "user_managed"
    ALL_ENCRYPTION_VALUES = [ENCRYPTION_PROVIDER_MANAGED, ENCRYPTION_USER_MANAGED]
    # status consts
    STATUS_AVAILABLE = "available"
    STATUS_FAILED = "failed"
    STATUS_PENDING = "pending"
    STATUS_UPDATING = "updating"
    STATUS_PENDING_DELETION = "pending_deletion"
    STATUS_UNUSABLE = "unusable"
    ALL_STATUSES_LIST = [STATUS_AVAILABLE, STATUS_FAILED, STATUS_PENDING, STATUS_PENDING_DELETION, STATUS_UNUSABLE,
                         STATUS_UPDATING]

    __tablename__ = "ibm_volumes"

    id = Column(String(32), primary_key=True)
    name = Column(String(255), nullable=False)
    resource_id = Column(String(64), nullable=False)
    active = Column(Boolean, nullable=False)
    created_at = Column(DateTime, nullable=False)
    crn = Column(String(255), nullable=False)
    href = Column(String(255), nullable=False)
    busy = Column(Boolean, nullable=False)
    capacity = Column(Integer, nullable=False)
    volume_index = Column(Integer, nullable=False)
    encryption = Column(Enum(*ALL_ENCRYPTION_VALUES), nullable=False)
    iops = Column(Integer, nullable=False)
    status = Column(String(50), nullable=False)
    ibm_status_reasons = Column(JSON, nullable=False)
    encryption_key_crn = Column(String(255))

    resource_group_id = Column(String(32), ForeignKey("ibm_resource_groups.id", ondelete="CASCADE"))
    volume_profile_id = Column(String(32), ForeignKey("ibm_volume_profiles.id", ondelete="CASCADE"))
    operating_system_id = Column(String(32), ForeignKey("ibm_operating_systems.id", ondelete="SET NULL"), nullable=True)
    source_image_id = Column(String(32), ForeignKey("ibm_images.id", ondelete="SET NULL"), nullable=True)
    source_snapshot_id = Column(String(32), ForeignKey("ibm_snapshots.id", ondelete="SET NULL"), nullable=True)

    resource_group = relationship(
        "IBMResourceGroup", backref=backref("volumes", cascade="all, delete-orphan", passive_deletes=True,
                                            lazy="dynamic")
    )
    volume_attachments = relationship("IBMVolumeAttachment", cascade="all, delete-orphan", passive_deletes=True,
                                      lazy="dynamic")
    volume_profile = relationship(
        "IBMVolumeProfile", backref=backref("volumes", cascade="all, delete-orphan", passive_deletes=True,
                                            lazy="dynamic")
    )
    operating_system = relationship("IBMOperatingSystem", backref="volumes", foreign_keys=[operating_system_id])
    # TODO: Is this and IBMImage's source volume the same thing?
    source_image = relationship("IBMImage", backref="sourced_volumes", foreign_keys=[source_image_id])
    source_snapshot = relationship("IBMSnapshot", backref="sourced_volumes", foreign_keys=[source_snapshot_id])

    __table_args__ = (UniqueConstraint(resource_id, "cloud_id", name="uix_ibm_volumes_resource_id_cloud_id"),)

    def __init__(
            self, name=None, resource_id=None, active=None, created_at=None, crn=None, href=None,
            busy=None, capacity=None, encryption=None, iops=None, status=None, ibm_status_reasons=None,
            encryption_key_crn=None, volume_index=0
    ):
        self.id = str(uuid.uuid4().hex)
        self.name = name
        self.resource_id = resource_id
        self.active = active
        self.created_at = created_at
        self.crn = crn
        self.href = href
        self.busy = busy
        self.capacity = capacity
        self.encryption = encryption
        self.iops = iops
        self.status = status
        self.ibm_status_reasons = ibm_status_reasons
        self.encryption_key_crn = encryption_key_crn
        self.volume_index = volume_index

    def to_reference_json(self):
        return {
            self.ID_KEY: self.id,
            self.NAME_KEY: self.name,
            self.CAPACITY_KEY: self.capacity,
            self.IOPS_KEY: self.iops,
            self.ZONE_KEY: self.zone.to_reference_json(),
            self.PROFILE_KEY: self.volume_profile.to_json()
        }

    def to_json(self):
        return {
            self.ID_KEY: self.id,
            self.NAME_KEY: self.name,
            self.RESOURCE_ID_KEY: self.resource_id,
            self.ACTIVE_KEY: self.active,
            self.CREATED_AT_KEY: self.created_at,
            self.CRN_KEY: self.crn,
            self.HREF_KEY: self.href,
            self.BUSY_KEY: self.busy,
            self.CAPACITY_KEY: self.capacity,
            self.ENCRYPTION_KEY: self.encryption,
            self.IOPS_KEY: self.iops,
            self.STATUS_KEY: self.status,
            self.IBM_STATUS_REASONS_KEY: self.ibm_status_reasons,
            self.ENCRYPTION_KEY_CRN_KEY: self.encryption_key_crn,
            self.PROFILE_KEY: self.volume_profile.to_reference_json(),
            self.OPERATING_SYSTEM_KEY: self.operating_system.to_reference_json() if self.operating_system else {},
            self.SOURCE_IMAGE_KEY: self.source_image.to_reference_json() if self.source_image else {},
            self.SOURCE_SNAPSHOT_KEY: self.source_snapshot.to_reference_json() if self.source_snapshot else {},
            self.VOLUME_ATTACHMENTS_KEY:
                [volume_attachment.to_json() for volume_attachment in self.volume_attachments.all()],
            self.IBM_CLOUD_KEY: self.ibm_cloud.to_reference_json(),
            self.RESOURCE_GROUP_KEY: self.resource_group.to_reference_json(),
            self.REGION_KEY: self.region.to_reference_json(),
            self.ZONE_KEY: self.zone.to_reference_json(),
        }

    def to_idle_json(self, session=None):
        from ibm.models.ibm.cost_models import IBMResourceInstancesCost

        session = session if session else db.session
        cost_obj = IBMResourceInstancesCost.get_cost(self.crn, self.cloud_id, session)
        return {
            self.ACTIVE_KEY: self.active,
            self.CRN_KEY: self.crn,
            self.BUSY_KEY: self.busy,
            self.CAPACITY_KEY: self.capacity,
            self.ENCRYPTION_KEY: self.encryption,
            self.IOPS_KEY: self.iops,
            self.STATUS_KEY: self.status,
            self.REGION_KEY: self.region.name,
            self.HREF_KEY: self.href,
            self.RESOURCE_TYPE_KEY: self.RESOURCE_TYPE_VOLUME_KEY,
            self.RESOURCE_ID_KEY: self.resource_id,
            self.IBM_CLOUD_KEY: self.cloud_id,
            self.ESTIMATED_SAVINGS: cost_obj.estimated_cost if cost_obj else None,
            self.COST_KEY: cost_obj.estimated_cost if cost_obj else None
        }

    @property
    def is_deletable(self):
        return not self.volume_attachments.count()

    def to_template_json(self):
        from random import randrange
        res = {
            self.NAME_KEY: f"{self.name}-{randrange(9999)}"[:62],
            self.CAPACITY_KEY: self.capacity,
            self.PROFILE_KEY: {
                self.NAME_KEY: self.volume_profile.name
            }
        }
        if self.source_snapshot:
            res[self.SOURCE_SNAPSHOT_KEY] = self.source_snapshot.to_reference_json()
        return res

    def to_json_body(self):
        return {
            "name": self.name,
            "capacity": self.capacity,
            "volume_index": self.volume_index,
            "profile": {"name": self.volume_profile.name}
            if self.volume_profile else {"name": "10iops-tier"}
        }

    def validate_json_for_schema(self):
        return {
            self.ID_KEY: self.id,
            self.RESOURCE_JSON_KEY: {
                self.NAME_KEY: self.name,
            }
        }

    @classmethod
    def from_ibm_json_body(cls, json_body):
        return cls(
            name=json_body["name"],
            resource_id=json_body["id"],
            active=json_body["active"],
            created_at=return_datetime_object(json_body["created_at"]),
            crn=json_body["crn"],
            href=json_body["href"],
            busy=json_body["busy"],
            capacity=json_body["capacity"],
            encryption=json_body["encryption"],
            iops=json_body["iops"],
            status=json_body["status"],
            ibm_status_reasons=json_body["status_reasons"],
            encryption_key_crn=json_body["encryption_key"]["crn"] if "encryption_key" in json_body else None
        )

    def dis_params_eq(self, other):
        assert isinstance(other, self.__class__)

        return (self.name == other.name and self.resource_id == other.resource_id and
                self.capacity == other.capacity and self.encryption == other.encryption and self.iops == other.iops and
                self.status == other.status and self.region != other.region)

    def dis_add_update_db(self, session, db_volumes, cloud_id, volume_profile_name, db_zone, db_resource_group):
        from ibm.models import IBMCloud

        volume_profile = \
            session.query(IBMVolumeProfile).filter_by(
                name=volume_profile_name, cloud_id=cloud_id, region_id=db_zone.region.id
            ).first()
        if not (db_resource_group and volume_profile):
            return

        db_volumes_name_obj_dict = dict()
        db_volumes_id_obj_dict = dict()
        for db_volume in db_volumes:
            try:
                db_volumes_name_obj_dict[db_volume.name] = db_volume
                db_volumes_id_obj_dict[db_volume.resource_id] = db_volume
            except orm.exc.ObjectDeletedError as ex:
                LOGGER.warning(ex)

        if self.resource_id not in db_volumes_id_obj_dict and self.name in db_volumes_name_obj_dict:
            # Creation Pending / Creating
            existing = db_volumes_name_obj_dict[self.name]
        elif self.resource_id in db_volumes_id_obj_dict:
            # Created. Update everything including name
            existing = db_volumes_id_obj_dict[self.resource_id]
        else:
            existing = None

        try:
            if not existing:
                cloud = session.query(IBMCloud).get(cloud_id)
                assert cloud

                self.volume_profile = volume_profile
                cloud.volumes.append(self)
                self.resource_group = db_resource_group
                self.zone = db_zone
                session.commit()
                return
        except orm.exc.ObjectDeletedError as ex:
            LOGGER.warning(ex)
            return

        try:
            if not self.dis_params_eq(existing):
                existing.update_from_object(self)
                existing.volume_profile = volume_profile
                existing.resource_group = db_resource_group
                existing.zone = db_zone
        except orm.exc.ObjectDeletedError as ex:
            LOGGER.warning(ex)

        session.commit()

    def update_from_object(self, other):
        assert isinstance(other, self.__class__)

        self.name = other.name
        self.resource_id = other.resource_id
        self.capacity = other.capacity
        self.encryption = other.encryption
        self.iops = other.iops
        self.status = other.status


class IBMVolumeAttachment(IBMZonalResourceMixin, Base):
    ID_KEY = "id"
    NAME_KEY = "name"
    RESOURCE_ID_KEY = "resource_id"
    TYPE_KEY = "type"
    DELETE_VOLUME_ON_INSTANCE_DELETE_KEY = "delete_volume_on_instance_delete"
    HREF_KEY = "href"
    CREATED_AT_KEY = "created_at"
    VOLUME_KEY = "volume"
    INSTANCE_KEY = "instance"
    STATUS_KEY = "status"
    RESOURCE_TYPE_KEY = "resource_type"
    RESOURCE_TYPE_VOLUME_KEY = "Volume"

    # type of volume attachments
    VOLUME_ATTACHMENT_TYPE_BOOT = "boot"
    VOLUME_ATTACHMENT_TYPE_DATA = "data"
    ALL_ATTACHMENT_TYPE = [VOLUME_ATTACHMENT_TYPE_BOOT, VOLUME_ATTACHMENT_TYPE_DATA]

    # status consts
    STATUS_ATTACHED = "attached"
    STATUS_ATTACHING = "attaching"
    STATUS_DELETING = "deleting"
    STATUS_DETACHING = "detaching"
    ALL_STATUSES_LIST = [STATUS_ATTACHED, STATUS_ATTACHING, STATUS_DELETING, STATUS_DETACHING]

    CRZ_BACKREF_NAME = "volume_attachments"
    __tablename__ = "ibm_volume_attachments"

    id = Column(String(32), unique=True)
    name = Column(String(255), nullable=False)
    status = Column(String(50), nullable=False)
    resource_id = Column(String(64), nullable=False)
    type_ = Column("type", Enum(*ALL_ATTACHMENT_TYPE), nullable=False)
    delete_volume_on_instance_delete = Column(Boolean, default=False, nullable=False)
    href = Column(Text, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow(), nullable=False)
    # TODO: Monitor "device" field in the docs: https://cloud.ibm.com/apidocs/vpc#list-instance-volume-attachments.
    #  Currently there is no model or details available related to this field other than an id, but there could be
    #  enhancements in the future. so it should be updated accordingly.
    #  device = Column(JSON)

    instance_id = Column(String(32), ForeignKey("ibm_instances.id", ondelete="CASCADE"), primary_key=True)
    volume_id = Column(String(32), ForeignKey("ibm_volumes.id", ondelete="CASCADE"), primary_key=True)

    volume = relationship("IBMVolume", back_populates="volume_attachments")
    instance = relationship("IBMInstance", back_populates="volume_attachments")

    __table_args__ = (UniqueConstraint(name, resource_id, instance_id,
                                       name="uix_ibm_volume_name_resource_id_instance_id"),)

    def __init__(
            self, name=None, resource_id=None, type_=None, delete_volume_on_instance_delete=None, href=None,
            created_at=None, status=None
    ):
        self.id = str(uuid.uuid4().hex)
        self.name = name
        self.resource_id = resource_id
        self.type_ = type_
        self.delete_volume_on_instance_delete = delete_volume_on_instance_delete
        self.href = href
        self.created_at = created_at
        self.status = status

    def to_reference_json(self):
        return {
            self.ID_KEY: self.id,
            self.NAME_KEY: self.name,
            self.TYPE_KEY: self.type_,
            self.DELETE_VOLUME_ON_INSTANCE_DELETE_KEY: self.delete_volume_on_instance_delete,
            self.VOLUME_KEY: self.volume.to_reference_json()
        }

    def to_json(self):
        return {
            self.ID_KEY: self.id,
            self.NAME_KEY: self.name,
            self.RESOURCE_ID_KEY: self.resource_id,
            self.TYPE_KEY: self.type_,
            self.DELETE_VOLUME_ON_INSTANCE_DELETE_KEY: self.delete_volume_on_instance_delete,
            self.HREF_KEY: self.href,
            self.CREATED_AT_KEY: self.created_at,
            self.VOLUME_KEY: self.volume.to_reference_json(),
            self.INSTANCE_KEY: self.instance.to_reference_json(),
            self.STATUS_KEY: self.status
        }

    def to_template_json(self):
        if self.volume:
            return {
                self.DELETE_VOLUME_ON_INSTANCE_DELETE_KEY: self.delete_volume_on_instance_delete,
                self.VOLUME_KEY: self.volume.to_template_json()
            }

    # TODO: Verify/fix while writing tasks
    # TODO: Only needed for softlayer discovery
    def to_json_body(self):
        if self.volume:
            return {
                self.NAME_KEY: self.name,
                self.DELETE_VOLUME_ON_INSTANCE_DELETE_KEY: self.delete_volume_on_instance_delete,
                self.VOLUME_KEY: self.volume.to_json_body()
            }

    def to_idle_json(self, session=None):
        return {
            self.TYPE_KEY: self.type_,
            self.DELETE_VOLUME_ON_INSTANCE_DELETE_KEY: self.delete_volume_on_instance_delete,
            self.STATUS_KEY: self.status,
            self.REGION_KEY: self.region.name,
            self.HREF_KEY: self.href,
            self.RESOURCE_TYPE_KEY: self.RESOURCE_TYPE_VOLUME_KEY,
            self.RESOURCE_ID_KEY: self.resource_id,
            self.IBM_CLOUD_KEY: self.cloud_id,

        }

    @classmethod
    def from_ibm_json_body(cls, json_body):
        return cls(
            name=json_body["name"],
            resource_id=json_body["id"],
            type_=json_body["type"],
            delete_volume_on_instance_delete=json_body["delete_volume_on_instance_delete"],
            href=json_body["href"],
            created_at=return_datetime_object(json_body["created_at"]),
            status=json_body["status"]
        )

    def dis_params_eq(self, other):
        assert isinstance(other, self.__class__)

        return self.name == other.name and self.resource_id == other.resource_id and self.type_ == other.type_

    def dis_add_update_db(self, session, db_volume_attachments, db_cloud, db_instance, db_volume):
        if not db_instance:
            return

        db_volume_attachments_id_obj_dict = dict()
        db_volume_attachments_name_obj_dict = dict()
        for db_volume_attachment in db_volume_attachments:
            try:
                db_volume_attachments_id_obj_dict[db_volume_attachment.resource_id] = db_volume_attachment
                db_volume_attachments_name_obj_dict[db_volume_attachment.name] = db_volume_attachment
            except orm.exc.ObjectDeletedError as ex:
                LOGGER.warning(ex)

        if not db_volume_attachments_id_obj_dict.get(self.resource_id) and db_volume_attachments_name_obj_dict.get(
                self.name):
            # Creation Pending / Creating
            existing = db_volume_attachments_name_obj_dict[self.name]
        elif self.resource_id in db_volume_attachments_id_obj_dict:
            # Created. Update everything including name
            existing = db_volume_attachments_id_obj_dict[self.resource_id]
        else:
            existing = None

        try:
            if not existing:
                self.cloud = db_cloud
                self.instance = db_instance
                self.volume = db_volume
                self.zone = db_volume.zone
                session.add(self)
                session.commit()
                return
        except orm.exc.ObjectDeletedError as ex:
            LOGGER.warning(ex)
            return

        try:
            if not self.dis_params_eq(existing):
                existing.update_from_object(self)
                existing.instance = db_instance
                existing.volume = db_volume
                existing.zone = db_volume.zone
        except orm.exc.ObjectDeletedError as ex:
            LOGGER.warning(ex)

        session.commit()

    def update_from_object(self, other):
        assert isinstance(other, self.__class__)

        self.name = other.name
        self.resource_id = other.resource_id
        self.type_ = other.type_
        self.delete_volume_on_instance_delete = other.delete_volume_on_instance_delete
