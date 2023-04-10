"""
Models for Dedicated hosts
"""
import logging
import uuid
from datetime import datetime

from sqlalchemy import (
    Boolean, Column, DateTime, Enum, ForeignKey, Integer, JSON, PrimaryKeyConstraint, String,
    Table, Text,
)
from sqlalchemy.orm import backref, relationship
from sqlalchemy.schema import UniqueConstraint

from ibm import get_db_session as db
from ibm.common.consts import (
    CREATED, CREATED_AT_FORMAT, DUMMY_CLOUD_ID, DUMMY_CLOUD_NAME, DUMMY_REGION_ID,
    DUMMY_REGION_NAME, DUMMY_RESOURCE_GROUP_ID, DUMMY_RESOURCE_GROUP_NAME, DUMMY_ZONE_ID, DUMMY_ZONE_NAME,
)
from ibm.models.base import Base
from ibm.models.ibm.mixins import IBMRegionalResourceMixin, IBMZonalResourceMixin

ibm_dh_supported_instance_profiles = Table(
    "ibm_dh_supported_instance_profiles", Base.metadata,
    Column("dh_id", String(32), ForeignKey("ibm_dedicated_hosts.id", ondelete="CASCADE")),
    Column("instance_profile_id", String(32), ForeignKey("ibm_instance_profiles.id", ondelete="CASCADE")),
    PrimaryKeyConstraint("dh_id", "instance_profile_id"),
)

ibm_dh_group_supported_instance_profiles = Table(
    "ibm_dh_group_supported_instance_profiles", Base.metadata,
    Column("dh_group_id", String(32), ForeignKey("ibm_dedicated_host_groups.id", ondelete="CASCADE")),
    Column("instance_profile_id", String(32), ForeignKey("ibm_instance_profiles.id", ondelete="CASCADE")),
    PrimaryKeyConstraint("dh_group_id", "instance_profile_id"),
)

ibm_dh_profile_supported_instance_profiles = Table(
    "ibm_dh_profile_supported_instance_profiles", Base.metadata,
    Column("dh_profile_id", String(32), ForeignKey("ibm_dedicated_host_profiles.id", ondelete="CASCADE")),
    Column("instance_profile_id", String(32), ForeignKey("ibm_instance_profiles.id", ondelete="CASCADE")),
    PrimaryKeyConstraint("dh_profile_id", "instance_profile_id"),
)


class IBMDedicatedHost(IBMZonalResourceMixin, Base):
    """
    Model for Dedicated host
    """
    ID_KEY = "id"
    RESOURCE_ID_KEY = "resource_id"
    AVAILABLE_MEMORY_KEY = "available_memory"
    AVAILABLE_VCPU_KEY = "available_vcpu"
    CREATED_AT_KEY = "created_at"
    CRN_KEY = "crn"
    HREF_KEY = "href"
    INSTANCE_PLACEMENT_ENABLED_KEY = "instance_placement_enabled"
    LIFECYCLE_STATE_KEY = "lifecycle_state"
    MEMORY_KEY = "memory"
    NAME_KEY = "name"
    PROVISIONABLE_KEY = "provisionable"
    RESOURCE_TYPE_KEY = "resource_type"
    SOCKET_COUNT_KEY = "socket_count"
    STATE_KEY = "state"
    VCPU_KEY = "vcpu"
    SUPPORTED_INSTANCE_PROFILES_KEY = "supported_instance_profiles"
    RESOURCE_GROUP_KEY = "resource_group"
    DEDICATED_HOST_GROUP_KEY = "dedicated_host_group"
    DEDICATED_HOST_PROFILE_KEY = "dedicated_host_profile"
    INSTANCES_KEY = "instances"
    DEDICATED_HOST_DISKS_KEY = "dedicated_host_disks"
    ASSOCIATED_RESOURCES_KEY = "associated_resources"
    RESOURCE_JSON_KEY = "resource_json"
    RESOURCE_TYPE_DEDICATED_HOST_KEY = "Dedicated Host"
    ESTIMATED_SAVINGS = "estimated_savings"
    COST_KEY = "cost"

    CRZ_BACKREF_NAME = "dedicated_hosts"

    # lifecycle_state consts
    LIFECYCLE_STATE_DELETING = "deleting"
    LIFECYCLE_STATE_FAILED = "failed"
    LIFECYCLE_STATE_PENDING = "pending"
    LIFECYCLE_STATE_STABLE = "stable"
    LIFECYCLE_STATE_UPDATING = "updating"
    LIFECYCLE_STATE_WAITING = "waiting"
    LIFECYCLE_STATE_SUSPENDED = "suspended"

    ALL_LIFECYCLE_STATE_CONSTS = [LIFECYCLE_STATE_DELETING, LIFECYCLE_STATE_FAILED, LIFECYCLE_STATE_PENDING,
                                  LIFECYCLE_STATE_STABLE, LIFECYCLE_STATE_UPDATING, LIFECYCLE_STATE_WAITING,
                                  LIFECYCLE_STATE_SUSPENDED]

    # state consts
    STATE_AVAILABLE = "available"
    STATE_DEGRADED = "degraded"
    STATE_MIGRATING = "migrating"
    STATE_UNAVAILABLE = "unavailable"

    ALL_STATE_CONSTS = [STATE_AVAILABLE, STATE_UNAVAILABLE, STATE_DEGRADED, STATE_MIGRATING]

    # ibm status consts
    STATUS_AVAILABLE = "available"
    STATUS_DELETING = "deleting"
    STATUS_FAILED = "failed"
    STATUS_PENDING = "pending"

    STATUSES_LIST = [STATUS_AVAILABLE, STATUS_DELETING, STATUS_FAILED, STATUS_PENDING]

    # resource_type consts
    RESOURCE_TYPE_DEDICATED_HOST = "dedicated_host"

    __tablename__ = "ibm_dedicated_hosts"
    id = Column(String(32), primary_key=True)
    resource_id = Column(String(64), nullable=False)
    available_memory = Column(Integer, nullable=False)
    available_vcpu = Column(JSON, nullable=False)
    created_at = Column(DateTime, nullable=False)
    crn = Column(String(255), nullable=False)
    href = Column(Text, nullable=False)
    instance_placement_enabled = Column(Boolean, nullable=False)
    lifecycle_state = Column(String(50), nullable=False)
    memory = Column(Integer, nullable=False)
    name = Column(String(255), nullable=False)
    provisionable = Column(Boolean, nullable=False)
    resource_type = Column(Enum(RESOURCE_TYPE_DEDICATED_HOST), nullable=False)
    socket_count = Column(Integer, nullable=False)
    state = Column(String(50), nullable=False)
    vcpu = Column(JSON, nullable=False)

    resource_group_id = Column(String(32), ForeignKey("ibm_resource_groups.id", ondelete="SET NULL"), nullable=True)
    dedicated_host_group_id = Column(String(32), ForeignKey("ibm_dedicated_host_groups.id", ondelete="SET NULL"),
                                     nullable=True)
    dedicated_host_profile_id = Column(String(32), ForeignKey("ibm_dedicated_host_profiles.id", ondelete="CASCADE"))

    instances = relationship(
        "IBMInstance", backref="dedicated_host", cascade="all, delete-orphan", passive_deletes=True, lazy="dynamic",
        foreign_keys="[IBMInstance.dedicated_host_id]"
    )
    dedicated_host_disks = relationship(
        "IBMDedicatedHostDisk", backref="dedicated_host", cascade="all, delete-orphan", passive_deletes=True,
        lazy="dynamic"
    )
    supported_instance_profiles = relationship(
        "IBMInstanceProfile", secondary=ibm_dh_supported_instance_profiles, lazy="dynamic",
        backref=backref("dedicated_hosts", lazy="dynamic")
    )

    __table_args__ = (UniqueConstraint(name, "region_id", "cloud_id", name="uix_ibm_dh_name_region_id_cloudid"),)

    def __init__(
            self, name, crn=None, href=None, created_at=None, resource_id=None,
            instance_placement_enabled=True, lifecycle_state=None, available_memory=None, memory=None,
            provisionable=True, resource_type=RESOURCE_TYPE_DEDICATED_HOST, socket_count=None, state=None,
            vcpu=None, available_vcpu=None, cloud_id=None, dedicated_host_profile_id=None
    ):
        self.id = str(uuid.uuid4().hex)
        self.name = name
        self.resource_id = resource_id
        self.crn = crn
        self.href = href
        self.created_at = created_at
        self.resource_type = resource_type
        self.dedicated_host_profile_id = dedicated_host_profile_id
        self.instance_placement_enabled = instance_placement_enabled
        self.lifecycle_state = lifecycle_state
        self.available_memory = available_memory
        self.memory = memory
        self.provisionable = provisionable
        self.socket_count = socket_count
        self.state = state
        self.vcpu = vcpu
        self.available_vcpu = available_vcpu
        self.cloud_id = cloud_id

    def to_reference_json(self):
        return {
            self.ID_KEY: self.id,
            self.NAME_KEY: self.name,
            self.ZONE_KEY: self.zone.to_reference_json(),
        }

    def to_template_json(self):
        resource_json = {
            self.NAME_KEY: self.name,
            self.DEDICATED_HOST_PROFILE_KEY: {self.ID_KEY: self.dedicated_host_profile_id},
            self.RESOURCE_GROUP_KEY: {self.ID_KEY: self.resource_group_id},
            self.ZONE_KEY: {self.ID_KEY: self.zone_id}
        }
        resource_data = {
            self.ID_KEY: self.id,
            self.IBM_CLOUD_KEY: {self.ID_KEY: self.cloud_id},
            self.REGION_KEY: {self.ID_KEY: self.region_id},
            self.RESOURCE_JSON_KEY: resource_json
        }

        return resource_data

    def validate_json_for_schema(self):
        return {
            self.ID_KEY: self.id,
            self.RESOURCE_JSON_KEY: {
                self.NAME_KEY: self.name,
                self.ZONE_KEY: self.zone.to_reference_json(),
            }
        }

    def to_json(self):
        """
        Return a JSON representation of the object
        """
        return {
            self.ID_KEY: self.id,
            self.RESOURCE_ID_KEY: self.resource_id,
            self.AVAILABLE_MEMORY_KEY: self.available_memory,
            self.AVAILABLE_VCPU_KEY: self.available_vcpu,
            self.CREATED_AT_KEY: self.created_at,
            self.CRN_KEY: self.crn,
            self.HREF_KEY: self.href,
            self.INSTANCE_PLACEMENT_ENABLED_KEY: self.instance_placement_enabled,
            self.LIFECYCLE_STATE_KEY: self.lifecycle_state,
            self.MEMORY_KEY: self.memory,
            self.NAME_KEY: self.name,
            self.PROVISIONABLE_KEY: self.provisionable,
            self.RESOURCE_TYPE_KEY: self.resource_type,
            self.SOCKET_COUNT_KEY: self.socket_count,
            self.STATE_KEY: self.state,
            self.VCPU_KEY: self.vcpu,
            self.SUPPORTED_INSTANCE_PROFILES_KEY:
                [sip.to_reference_json() for sip in self.supported_instance_profiles.all()],
            self.IBM_CLOUD_KEY: self.ibm_cloud.to_reference_json(),
            self.RESOURCE_GROUP_KEY: self.resource_group.to_reference_json(),
            self.REGION_KEY: self.region.to_reference_json(),
            self.ZONE_KEY: self.zone.to_reference_json(),
            self.ASSOCIATED_RESOURCES_KEY: {
                self.DEDICATED_HOST_GROUP_KEY: (
                    self.dedicated_host_group.to_reference_json() if self.dedicated_host_group else {}),
                self.DEDICATED_HOST_PROFILE_KEY: self.dedicated_host_profile.to_reference_json(),
                self.INSTANCES_KEY: [instance.to_reference_json() for instance in self.instances.all()],
                self.DEDICATED_HOST_DISKS_KEY: [
                    dedicated_host_disk.to_reference_json() for dedicated_host_disk in self.dedicated_host_disks.all()
                ]}
        }

    def to_idle_json(self, session=None):
        from ibm.models.ibm.cost_models import IBMResourceInstancesCost

        session = session if session else db.session

        cost_obj = IBMResourceInstancesCost.get_cost(self.crn, self.cloud_id, session)
        data = {
            self.STATE_KEY: self.state,
            self.CRN_KEY: self.crn,
            self.REGION_KEY: self.region.name,
            self.HREF_KEY: self.href,
            self.RESOURCE_TYPE_KEY: self.RESOURCE_TYPE_DEDICATED_HOST_KEY,
            self.RESOURCE_ID_KEY: self.resource_id,
            self.IBM_CLOUD_KEY: self.cloud_id,
            self.ESTIMATED_SAVINGS: cost_obj.estimated_cost if cost_obj else None,
            self.COST_KEY: cost_obj.estimated_cost if cost_obj else None
        }

        return data

    def to_json_body(self):
        """
        Return a JSON representation of the object according to IBM's CREATE API Call
        """
        json_data = {
            "profile": {
                "name": self.ibm_dedicated_host_profile.name
            }
        }
        # DO NOT simplify the following expression
        if self.instance_placement_enabled is False:
            json_data["instance_placement_enabled"] = self.instance_placement_enabled,

        if self.name:
            json_data["name"] = self.name

        if self.ibm_resource_group:
            json_data["resource_group"] = {
                "id": self.ibm_resource_group.resource_id
            }

        if self.ibm_dedicated_host_group.resource_id:
            json_data["group"] = {
                "id": self.ibm_dedicated_host_group.resource_id
            }
        else:
            json_data["zone"] = {
                "name": self.zone
            }
            if self.ibm_dedicated_host_group.name:
                json_data["group"] = {
                    "name": self.ibm_dedicated_host_group.name
                }

            if self.ibm_dedicated_host_group.ibm_resource_group:
                json_data["group"] = json_data.get("group") or {}
                json_data["group"]["resource_group"] = {
                    "id": self.ibm_dedicated_host_group.ibm_resource_group.resource_id
                }

        return json_data

    def update_from_obj(self, updated_obj):
        self.name = updated_obj.name
        self.resource_id = updated_obj.resource_id
        self.crn = updated_obj.crn
        self.href = updated_obj.href
        self.instance_placement_enabled = updated_obj.instance_placement_enabled
        self.lifecycle_state = updated_obj.lifecycle_state
        self.available_memory = updated_obj.available_memory
        self.memory = updated_obj.memory
        self.provisionable = updated_obj.provisionable
        self.socket_count = updated_obj.socket_count
        self.state = updated_obj.state
        self.vcpu = updated_obj.vcpu
        self.available_vcpu = updated_obj.available_vcpu

    @classmethod
    def from_ibm_json_body(cls, json_body):
        """
        Return an object of the class created from the provided JSON body
        """
        return cls(
            name=json_body["name"],
            resource_id=json_body["id"],
            crn=json_body["crn"],
            href=json_body["href"],
            instance_placement_enabled=json_body["instance_placement_enabled"],
            lifecycle_state=json_body["lifecycle_state"],
            available_memory=json_body["available_memory"],
            memory=json_body["memory"],
            provisionable=json_body["provisionable"],
            socket_count=json_body["socket_count"],
            state=json_body["state"],
            vcpu=json_body["vcpu"],
            available_vcpu=json_body["available_vcpu"],
            created_at=datetime.strptime(json_body["created_at"], CREATED_AT_FORMAT)
        )

    @property
    def __application_profile(self):
        from ibm import get_db_session
        with get_db_session() as db_session:
            profile = db_session.query(IBMDedicatedHostProfile).first()
            if not profile:
                logging.warning("Please sync the dedicated host profiles first.")
            return profile

    def from_softlayer_to_ibm(self):
        resource_json = {
            self.NAME_KEY: self.name,
            self.DEDICATED_HOST_PROFILE_KEY: {
                self.ID_KEY: self.__application_profile.id,
                self.NAME_KEY: self.__application_profile.name
            } if self.__application_profile else {},
            self.RESOURCE_GROUP_KEY: {
                "id": DUMMY_RESOURCE_GROUP_ID,
                "name": DUMMY_RESOURCE_GROUP_NAME
            },
            self.ZONE_KEY: {
                self.ID_KEY: DUMMY_ZONE_ID,
                self.NAME_KEY: DUMMY_ZONE_NAME
            }
        }
        dedicated_host_schema = {
            self.ID_KEY: self.id,
            "ibm_cloud": {
                "id": DUMMY_CLOUD_ID,
                "name": DUMMY_CLOUD_NAME
            },
            "region": {
                "id": DUMMY_REGION_ID,
                "name": DUMMY_REGION_NAME
            },
            "resource_json": resource_json
        }

        return dedicated_host_schema

    def dis_params_eq(self, other):
        assert isinstance(other, self.__class__)

        return self.name == other.name and self.resource_id == other.resource_id and self.region == other.region

    def dis_add_update_db(
            self, session, db_dedicated_host, cloud_id, resource_group_id, dedicated_host_profile_name,
            dedicated_host_group_id, db_zone
    ):
        from ibm.models import IBMCloud, IBMResourceGroup, IBMDedicatedHostProfile, IBMDedicatedHostGroup

        resource_group = \
            session.query(IBMResourceGroup).filter_by(
                resource_id=resource_group_id, cloud_id=cloud_id
            ).first()
        dedicated_host_profile = \
            session.query(IBMDedicatedHostProfile).filter_by(
                name=dedicated_host_profile_name, cloud_id=cloud_id
            ).first()
        dedicated_host_group = \
            session.query(IBMDedicatedHostGroup).filter_by(
                resource_id=dedicated_host_group_id, cloud_id=cloud_id
            ).first()

        if not (resource_group and dedicated_host_profile and dedicated_host_group):
            return

        existing = db_dedicated_host or None

        if not existing:
            cloud = session.query(IBMCloud).get(cloud_id)
            assert cloud

            self.resource_group = resource_group
            self.dedicated_host_profile = dedicated_host_profile
            self.dedicated_host_group = dedicated_host_group
            self.zone = db_zone
            cloud.dedicated_hosts.append(self)
            session.commit()
            return

        if not self.dis_params_eq(existing):
            existing.update_from_obj(self)
            existing.resource_group = resource_group
            existing.dedicated_host_profile = dedicated_host_profile
            existing.dedicated_host_group = dedicated_host_group
            existing.zone = db_zone

        session.commit()


class IBMDedicatedHostGroup(IBMZonalResourceMixin, Base):
    """
    Model for Dedicated host group
    """
    ID_KEY = "id"
    RESOURCE_ID_KEY = "resource_id"
    CLASS_KEY = "class"
    CREATED_AT_KEY = "created_at"
    CRN_KEY = "crn"
    FAMILY_KEY = "family"
    HREF_KEY = "href"
    NAME_KEY = "name"
    RESOURCE_TYPE_KEY = "resource_type"
    STATUS_KEY = "status"
    PROFILE_KEY = "profile"
    RESOURCE_JSON_KEY = "resource_json"
    RESOURCE_GROUP_KEY = "resource_group"
    DEDICATED_HOSTS_KEY = "dedicated_hosts"
    SUPPORTED_INSTANCE_PROFILES_KEY = "supported_instance_profiles"
    ASSOCIATED_RESOURCES_KEY = "associated_resources"

    CRZ_BACKREF_NAME = "dedicated_host_groups"

    # family consts
    FAMILY_BALANCED = "balanced"
    FAMILY_MEMORY = "memory"
    FAMILY_COMPUTE = "compute"
    FAMILY_HIGH_MEMORY = "high-memory"
    FAMILY_VERY_HIGH_MEMORY = "very-high-memory"

    # ibm status consts
    STATUS_AVAILABLE = "available"
    STATUS_DELETING = "deleting"
    STATUS_FAILED = "failed"
    STATUS_PENDING = "pending"

    STATUSES_LIST = [STATUS_AVAILABLE, STATUS_DELETING, STATUS_FAILED, STATUS_PENDING]

    ALL_FAMILY_CONSTS = [FAMILY_BALANCED, FAMILY_MEMORY, FAMILY_COMPUTE, FAMILY_HIGH_MEMORY, FAMILY_VERY_HIGH_MEMORY]
    # resource_type consts
    RESOURCE_TYPE_DEDICATED_HOST_GROUP = "dedicated_host_group"

    __tablename__ = "ibm_dedicated_host_groups"
    id = Column(String(32), primary_key=True)
    resource_id = Column(String(64), nullable=False)
    class_ = Column("class", String(128), nullable=False)
    created_at = Column(DateTime, nullable=False)
    crn = Column(String(255), nullable=False)
    family = Column(
        Enum(FAMILY_BALANCED, FAMILY_MEMORY, FAMILY_COMPUTE, FAMILY_HIGH_MEMORY, FAMILY_VERY_HIGH_MEMORY),
        nullable=False
    )
    href = Column(String(255), nullable=False)
    name = Column(String(255), nullable=False)
    resource_type = Column(
        Enum(RESOURCE_TYPE_DEDICATED_HOST_GROUP), default=RESOURCE_TYPE_DEDICATED_HOST_GROUP,
        nullable=False
    )
    status = Column(String(50), nullable=False)

    resource_group_id = Column(String(32), ForeignKey("ibm_resource_groups.id", ondelete="CASCADE"), nullable=True)

    dedicated_hosts = relationship(
        "IBMDedicatedHost", backref="dedicated_host_group", cascade="all, delete-orphan", passive_deletes=True,
        lazy="dynamic"
    )
    supported_instance_profiles = relationship(
        "IBMInstanceProfile", secondary=ibm_dh_group_supported_instance_profiles, lazy="dynamic",
        backref=backref("dedicated_host_groups", lazy="dynamic")
    )

    __table_args__ = (UniqueConstraint(name, "region_id", "cloud_id", name="uix_ibm_dh_group_name_region_id_cloudid"),)

    def __init__(
            self, name, crn, href, status=CREATED, created_at=None, resource_id=None,
            family=None, class_=None, cloud_id=None, resource_type=None
    ):
        self.id = str(uuid.uuid4().hex)
        self.name = name
        self.created_at = created_at
        self.resource_type = resource_type
        self.status = status
        self.resource_id = resource_id
        self.crn = crn
        self.href = href
        self.family = family
        self.class_ = class_
        self.cloud_id = cloud_id

    def to_reference_json(self):
        return {
            self.ID_KEY: self.id,
            self.NAME_KEY: self.name,
            self.ZONE_KEY: self.zone.to_reference_json(),
        }

    def to_template_json(self):
        resource_json = {
            self.NAME_KEY: self.name,
            self.PROFILE_KEY: {self.ID_KEY: self.dedicated_host_group.dedicated_host_profile.id},
            self.RESOURCE_GROUP_KEY: {self.ID_KEY: self.resource_group_id},
            self.ZONE_KEY: {self.ID_KEY: self.zone_id}
        }

        resource_data = {
            self.ID_KEY: self.id,
            self.IBM_CLOUD_KEY: {self.ID_KEY: self.cloud_id},
            self.REGION_KEY: {self.ID_KEY: self.region_id},
            self.RESOURCE_JSON_KEY: resource_json
        }

        return resource_data

    def to_json(self):
        """
        Return a JSON representation of the object
        """
        return {
            self.ID_KEY: self.id,
            self.RESOURCE_ID_KEY: self.resource_id,
            self.CLASS_KEY: self.class_,
            self.CREATED_AT_KEY: self.created_at,
            self.CRN_KEY: self.crn,
            self.FAMILY_KEY: self.family,
            self.HREF_KEY: self.href,
            self.NAME_KEY: self.name,
            self.RESOURCE_TYPE_KEY: self.resource_type,
            self.STATUS_KEY: self.status,
            self.SUPPORTED_INSTANCE_PROFILES_KEY:
                [sip.to_reference_json() for sip in self.supported_instance_profiles.all()],
            self.IBM_CLOUD_KEY: self.ibm_cloud.to_reference_json(),
            self.RESOURCE_GROUP_KEY: self.resource_group.to_reference_json() if self.resource_group else {},
            self.REGION_KEY: self.region.to_reference_json(),
            self.ZONE_KEY: self.zone.to_reference_json(),
            self.ASSOCIATED_RESOURCES_KEY: {
                self.DEDICATED_HOSTS_KEY:
                    [dedicated_host.to_reference_json() for dedicated_host in self.dedicated_hosts.all()]},
        }

    def to_json_body(self):
        """
        Return a JSON representation of the object according to IBM's CREATE API Call
        """
        json_data = {
            self.CLASS_KEY: self.class_,
            self.FAMILY_KEY: self.family,
            self.ZONE_KEY: {
                self.NAME_KEY: self.zone
            },
            self.NAME_KEY: self.name
        }
        if self.ibm_resource_group:
            json_data[self.RESOURCE_GROUP_KEY] = {
                self.ID_KEY: self.ibm_resource_group.resource_id
            }

        return json_data

    def update_from_obj(self, updated_obj):
        assert isinstance(updated_obj, self.__class__)

        self.name = updated_obj.name
        self.status = updated_obj.status
        self.resource_id = updated_obj.resource_id
        self.crn = updated_obj.crn
        self.href = updated_obj.href
        self.family = updated_obj.family
        self.class_ = updated_obj.class_

    @classmethod
    def from_ibm_json_body(cls, json_body):
        """
        Return an object of the class created from the provided JSON body
        """
        return cls(
            name=json_body["name"],
            status=CREATED,
            resource_id=json_body["id"],
            crn=json_body["crn"],
            href=json_body["href"],
            family=json_body["family"],
            class_=json_body["class"],
            created_at=datetime.strptime(json_body["created_at"], CREATED_AT_FORMAT)
        )

    def dis_params_eq(self, other):
        assert isinstance(other, self.__class__)

        return self.name == other.name and self.resource_id == other.resource_id and self.region == other.region

    def dis_add_update_db(self, session, db_dedicated_host_group, cloud_id, resource_group_id, db_zone):
        from ibm.models import IBMCloud, IBMResourceGroup

        resource_group = \
            session.query(IBMResourceGroup).filter_by(
                resource_id=resource_group_id, cloud_id=cloud_id
            ).first()
        if not resource_group:
            return

        existing = db_dedicated_host_group or None
        if not existing:
            cloud = session.query(IBMCloud).get(cloud_id)
            assert cloud

            self.resource_group = resource_group
            self.zone = db_zone
            cloud.dedicated_host_groups.append(self)
            session.commit()
            return

        if not self.dis_params_eq(existing):
            existing.update_from_obj(self)
            existing.resource_group = resource_group
            existing.zone = db_zone

        session.commit()


class IBMDedicatedHostProfile(IBMRegionalResourceMixin, Base):
    """
    Model for Dedicated host profile
    """
    ID_KEY = "id"
    CLASS_KEY = "class_"
    DISKS_KEY = "disks"
    FAMILY_KEY = "family"
    HREF_KEY = "href"
    MEMORY_KEY = "memory"
    NAME_KEY = "name"
    SOCKET_COUNT_KEY = "socket_count"
    VCPU_ARCHITECTURE_KEY = "vcpu_architecture"
    VCPU_COUNT_KEY = "vcpu_count"
    DEDICATED_HOSTS_KEY = "dedicated_hosts"
    SUPPORTED_INSTANCE_PROFILES_KEY = "supported_instance_profiles"
    ASSOCIATED_RESOURCES_KEY = "associated_resources"

    CRZ_BACKREF_NAME = "dedicated_host_profiles"

    # family consts
    FAMILY_BALANCED = "balanced"
    FAMILY_MEMORY = "memory"
    FAMILY_COMPUTE = "compute"
    FAMILY_HIGH_MEMORY = "high-memory"
    FAMILY_VERY_HIGH_MEMORY = "very-high-memory"

    NAME_VERY_HIGH_MEMORY = "vx2d-host-176x2464"

    ALL_FAMILY_CONSTS = [FAMILY_BALANCED, FAMILY_MEMORY, FAMILY_COMPUTE, FAMILY_HIGH_MEMORY, FAMILY_VERY_HIGH_MEMORY]

    # ibm status consts
    STATUS_AVAILABLE = "available"
    STATUS_DELETING = "deleting"
    STATUS_FAILED = "failed"
    STATUS_PENDING = "pending"

    STATUSES_LIST = [STATUS_AVAILABLE, STATUS_DELETING, STATUS_FAILED, STATUS_PENDING]

    __tablename__ = "ibm_dedicated_host_profiles"

    id = Column(String(32), primary_key=True)
    class_ = Column('class', String(20), nullable=False)
    disks = Column(JSON, nullable=False)
    family = Column(
        Enum(FAMILY_BALANCED, FAMILY_MEMORY, FAMILY_COMPUTE, FAMILY_HIGH_MEMORY, FAMILY_VERY_HIGH_MEMORY),
        nullable=False
    )
    href = Column(Text, nullable=False)
    memory = Column(JSON, nullable=False)
    name = Column(String(255), nullable=False)
    socket_count = Column(JSON, nullable=False)
    vcpu_architecture = Column(JSON, nullable=False)
    vcpu_count = Column(JSON, nullable=False)

    dedicated_hosts = relationship(
        "IBMDedicatedHost", backref="dedicated_host_profile", cascade="all, delete-orphan", passive_deletes=True,
        lazy="dynamic"
    )
    supported_instance_profiles = relationship(
        "IBMInstanceProfile", secondary=ibm_dh_profile_supported_instance_profiles, lazy="dynamic",
        backref=backref("dedicated_host_profiles", lazy="dynamic")
    )

    __table_args__ = (
        UniqueConstraint(name, "region_id", "cloud_id", name="uix_ibm_dh_profile_name_region_id_cloudid"),)

    def __init__(
            self, name, href, family=None, class_=None, socket_count=None, memory=None,
            vcpu_architecture=None, vcpu_count=None, disks=None, cloud_id=None
    ):
        self.id = str(uuid.uuid4().hex)
        self.name = name
        self.href = href
        self.family = family
        self.class_ = class_
        self.socket_count = socket_count
        self.memory = memory
        self.vcpu_architecture = vcpu_architecture
        self.vcpu_count = vcpu_count
        self.disks = disks
        self.cloud_id = cloud_id

    def to_reference_json(self):
        return {
            self.ID_KEY: self.id,
            self.NAME_KEY: self.name
        }

    def to_json(self):
        """
        Return a JSON representation of the object
        """
        return {
            self.ID_KEY: self.id,
            self.CLASS_KEY: self.class_,
            self.DISKS_KEY: self.disks,
            self.FAMILY_KEY: self.family,
            self.HREF_KEY: self.href,
            self.MEMORY_KEY: self.memory,
            self.NAME_KEY: self.name,
            self.SOCKET_COUNT_KEY: self.socket_count,
            self.VCPU_ARCHITECTURE_KEY: self.vcpu_architecture,
            self.VCPU_COUNT_KEY: self.vcpu_count,
            self.SUPPORTED_INSTANCE_PROFILES_KEY:
                [sip.to_reference_json() for sip in self.supported_instance_profiles.all()],
            self.IBM_CLOUD_KEY: self.ibm_cloud.to_reference_json(),
            self.REGION_KEY: self.region.to_reference_json(),
            self.ASSOCIATED_RESOURCES_KEY: {
                self.DEDICATED_HOSTS_KEY:
                    [dedicated_host.to_reference_json() for dedicated_host in self.dedicated_hosts.all()]},
        }

    @classmethod
    def from_ibm_json_body(cls, json_body):
        """
        Return an object of the class created from the provided JSON body
        """
        return cls(
            name=json_body["name"],
            href=json_body["href"],
            family=json_body["family"],
            class_=json_body["class"],
            socket_count=json_body["socket_count"],
            memory=json_body["memory"],
            vcpu_architecture=json_body["vcpu_architecture"],
            vcpu_count=json_body["vcpu_count"],
            disks=json_body["disks"]
        )

    def update_from_obj(self, updated_obj):
        """
        Update an existing object of the class from an updated one
        """

        assert isinstance(updated_obj, self.__class__)
        self.name = updated_obj.name
        self.href = updated_obj.href
        self.family = updated_obj.family
        self.class_ = updated_obj.class_
        self.memory = updated_obj.memory
        self.socket_count = updated_obj.socket_count
        self.vcpu_architecture = updated_obj.vcpu_architecture
        self.vcpu_count = updated_obj.vcpu_count
        self.disks = updated_obj.disks

    def dis_params_eq(self, other):
        assert isinstance(other, self.__class__)

        return self.name == other.name and self.family == other.family and self.region == other.region

    def dis_add_update_db(self, session, db_dedicated_host_profile, cloud_id, db_region):
        from ibm.models import IBMCloud

        existing = db_dedicated_host_profile or None
        if not existing:
            cloud = session.query(IBMCloud).get(cloud_id)
            assert cloud

            self.ibm_cloud = cloud
            self.region = db_region
            session.commit()
            return

        if not self.dis_params_eq(existing):
            existing.update_from_obj(self)
            existing.region = db_region

        session.commit()


class IBMDedicatedHostDisk(IBMRegionalResourceMixin, Base):
    """
    Model for Dedicated host disk
    """
    ID_KEY = "id"
    RESOURCE_ID_KEY = "resource_id"
    AVAILABLE_KEY = "available"
    CREATED_AT_KEY = "created_at"
    HREF_KEY = "href"
    INTERFACE_TYPE_KEY = "interface_type"
    NAME_KEY = "name"
    PROVISIONABLE_KEY = "provisionable"
    RESOURCE_TYPE_KEY = "resource_type"
    SIZE_KEY = "size"
    SUPPORTED_INSTANCE_INTERFACE_TYPES_KEY = "supported_instance_interface_types"
    LIFECYCLE_STATE_KEY = "lifecycle_state"
    DEDICATED_HOST_KEY = "dedicated_host"
    INSTANCE_DISKS_KEY = "instance_disks"
    ASSOCIATED_RESOURCES_KEY = "associated_resources"

    CRZ_BACKREF_NAME = "dedicated_host_disks"

    # interface_type consts
    INTERFACE_TYPE_NVME = "nvme"

    ALL_INTERFACE_TYPE_CONSTS = [INTERFACE_TYPE_NVME]

    # resource_type consts
    RESOURCE_TYPE_DEDICATED_HOST_DISK = "dedicated_host_disk"

    # lifecycle_state consts
    LIFECYCLE_STATE_DELETING = "deleting"
    LIFECYCLE_STATE_FAILED = "failed"
    LIFECYCLE_STATE_PENDING = "pending"
    LIFECYCLE_STATE_STABLE = "stable"
    LIFECYCLE_STATE_UPDATING = "updating"
    LIFECYCLE_STATE_WAITING = "waiting"
    LIFECYCLE_STATE_SUSPENDED = "suspended"

    ALL_LIFECYCLE_STATE_CONSTS = [LIFECYCLE_STATE_DELETING, LIFECYCLE_STATE_FAILED, LIFECYCLE_STATE_PENDING,
                                  LIFECYCLE_STATE_STABLE, LIFECYCLE_STATE_UPDATING, LIFECYCLE_STATE_WAITING,
                                  LIFECYCLE_STATE_SUSPENDED]

    # ibm status consts
    STATUS_AVAILABLE = "available"
    STATUS_DELETING = "deleting"
    STATUS_FAILED = "failed"
    STATUS_PENDING = "pending"

    STATUSES_LIST = [STATUS_AVAILABLE, STATUS_DELETING, STATUS_FAILED, STATUS_PENDING]

    __tablename__ = "ibm_dedicated_host_disks"

    id = Column(String(32), primary_key=True)
    resource_id = Column(String(64), nullable=False)
    available = Column(Integer, nullable=False)
    created_at = Column(DateTime, nullable=False)
    href = Column(Text, nullable=False)
    interface_type = Column(Enum(INTERFACE_TYPE_NVME), default=INTERFACE_TYPE_NVME, nullable=False)
    name = Column(String(255), nullable=False)
    provisionable = Column(Boolean, nullable=False)
    resource_type = \
        Column(Enum(RESOURCE_TYPE_DEDICATED_HOST_DISK), default=RESOURCE_TYPE_DEDICATED_HOST_DISK, nullable=False)
    size = Column(Integer, nullable=False)
    supported_instance_interface_types = Column(JSON, nullable=False)
    lifecycle_state = Column(
        Enum(
            LIFECYCLE_STATE_DELETING, LIFECYCLE_STATE_FAILED, LIFECYCLE_STATE_PENDING,
            LIFECYCLE_STATE_STABLE, LIFECYCLE_STATE_UPDATING, LIFECYCLE_STATE_WAITING,
            LIFECYCLE_STATE_SUSPENDED
        )
    )

    dedicated_host_id = Column(String(32), ForeignKey("ibm_dedicated_hosts.id",  ondelete="SET NULL"), nullable=True)

    instance_disks = relationship("IBMInstanceDisk", backref="dedicated_host_disk", lazy="dynamic")

    def __init__(
            self, name, resource_id, href, size, available, interface_type, provisionable,
            supported_instance_interface_types, created_at=None, lifecycle_state=None,
            instance_disks=None, resource_type=None
    ):
        self.id = str(uuid.uuid4().hex)
        self.name = name
        self.resource_id = resource_id
        self.href = href
        self.created_at = created_at
        self.size = size
        self.instance_disks = instance_disks or []
        self.resource_type = resource_type
        self.available = available
        self.interface_type = interface_type
        self.provisionable = provisionable
        self.supported_instance_interface_types = supported_instance_interface_types
        self.lifecycle_state = lifecycle_state

    def to_reference_json(self):
        return {
            self.ID_KEY: self.id,
            self.NAME_KEY: self.name
        }

    def to_json(self, parent_reference=True):
        """
        Return a JSON representation of the object
        """
        return {
            self.ID_KEY: self.id,
            self.RESOURCE_ID_KEY: self.resource_id,
            self.AVAILABLE_KEY: self.available,
            self.CREATED_AT_KEY: self.created_at,
            self.HREF_KEY: self.href,
            self.INTERFACE_TYPE_KEY: self.interface_type,
            self.NAME_KEY: self.name,
            self.PROVISIONABLE_KEY: self.provisionable,
            self.RESOURCE_TYPE_KEY: self.resource_type,
            self.SIZE_KEY: self.size,
            self.SUPPORTED_INSTANCE_INTERFACE_TYPES_KEY: self.supported_instance_interface_types,
            self.LIFECYCLE_STATE_KEY: self.lifecycle_state,
            self.IBM_CLOUD_KEY: self.ibm_cloud.to_reference_json(),
            self.REGION_KEY: self.region.to_reference_json(),
            self.DEDICATED_HOST_KEY: self.dedicated_host.to_reference_json(),
            self.ASSOCIATED_RESOURCES_KEY: {
                self.INSTANCE_DISKS_KEY:
                    [instance_disk.to_reference_json() for instance_disk in self.instance_disks.all()],
            },
        }

    @classmethod
    def from_ibm_json_body(cls, json_body):
        """
        Return an object of the class created from the provided JSON body
        """
        return cls(
            name=json_body["name"],
            href=json_body["href"],
            resource_id=json_body["id"],
            created_at=datetime.strptime(json_body["created_at"], CREATED_AT_FORMAT),
            size=json_body["size"],
            available=json_body["available"],
            interface_type=json_body["interface_type"],
            provisionable=json_body["provisionable"],
            supported_instance_interface_types=json_body["supported_instance_interface_types"],
            resource_type=json_body["resource_type"],
            lifecycle_state=json_body.get("lifecycle_state")
        )

    def update_from_obj(self, updated_obj):
        self.name = updated_obj.name
        self.resource_id = updated_obj.resource_id
        self.href = updated_obj.href
        self.size = updated_obj.size
        self.available = updated_obj.available
        self.interface_type = updated_obj.interface_type
        self.provisionable = updated_obj.provisionable
        self.supported_instance_interface_types = updated_obj.supported_instance_interface_types
        self.lifecycle_state = updated_obj.lifecycle_state

    def dis_params_eq(self, other):
        assert isinstance(other, self.__class__)

        return self.name == other.name and self.resource_id == other.resource_id

    def dis_add_update_db(self, session, db_dedicated_host_disk, cloud_id, dedicated_host_id, db_region):
        from ibm.models import IBMCloud, IBMDedicatedHost
        dedicated_host = \
            session.query(IBMDedicatedHost).filter_by(
                resource_id=dedicated_host_id, cloud_id=cloud_id
            ).first()

        if not dedicated_host:
            return

        existing = db_dedicated_host_disk or None

        if not existing:
            cloud = session.query(IBMCloud).get(cloud_id)
            assert cloud

            self.dedicated_host = dedicated_host
            cloud.dedicated_host_disks.append(self)
            self.region = db_region
            session.commit()
            return

        if not self.dis_params_eq(existing):
            existing.update_from_obj(self)
            existing.dedicated_host = dedicated_host
            existing.region = db_region

        session.commit()
