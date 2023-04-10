import uuid

from sqlalchemy import Column, DateTime, Enum, ForeignKey, String, Text
from sqlalchemy.orm import backref, relationship
from sqlalchemy.schema import UniqueConstraint

from ibm.common.consts import CREATED, DUMMY_CLOUD_ID, DUMMY_CLOUD_NAME, DUMMY_REGION_ID, DUMMY_REGION_NAME, \
    DUMMY_RESOURCE_GROUP_ID, DUMMY_RESOURCE_GROUP_NAME
from ibm.common.utils import return_datetime_object
from ibm.models.base import Base
from ibm.models.ibm.mixins import IBMRegionalResourceMixin


class IBMPlacementGroup(IBMRegionalResourceMixin, Base):
    ID_KEY = "id"
    CREATED_AT_KEY = "created_at"
    CRN_KEY = "crn"
    HREF_KEY = "href"
    RESOURCE_ID_KEY = "resource_id"
    LIFECYCLE_STATE_KEY = "lifecycle_state"
    NAME_KEY = "name"
    RESOURCE_GROUP_KEY = "resource_group"
    RESOURCE_JSON_KEY = "resource_json"
    RESOURCE_TYPE_KEY = "resource_type"
    STRATEGY_KEY = "strategy"
    REGION_KEY = "region"
    STATUS_KEY = "status"

    CRZ_BACKREF_NAME = "placement_groups"

    LIFECYCLE_STATE_DELETING = "deleting"
    LIFECYCLE_STATE_FAILED = "failed"
    LIFECYCLE_STATE_PENDING = "pending"
    LIFECYCLE_STATE_STABLE = "stable"
    LIFECYCLE_STATE_UPDATING = "updating"
    LIFECYCLE_STATE_WAITING = "waiting"
    LIFECYCLE_STATE_SUSPENDED = "suspended"

    ALL_LIFECYCLE_STATE_LIST = [
        LIFECYCLE_STATE_DELETING, LIFECYCLE_STATE_FAILED, LIFECYCLE_STATE_PENDING, LIFECYCLE_STATE_STABLE,
        LIFECYCLE_STATE_UPDATING, LIFECYCLE_STATE_WAITING, LIFECYCLE_STATE_SUSPENDED
    ]

    RESOURCE_TYPE_PLACEMENT_GROUP = "placement_group"

    ALL_RESOURCE_TYPE_LIST = [RESOURCE_TYPE_PLACEMENT_GROUP]

    STRATEGY_HOST_SPREAD = "host_spread"
    STRATEGY_POWER_SPREAD = "power_spread"

    ALL_STRATEGY_LIST = [STRATEGY_HOST_SPREAD, STRATEGY_POWER_SPREAD]

    __tablename__ = "ibm_placement_groups"

    id = Column(String(32), primary_key=True)
    resource_id = Column(String(255), nullable=False)
    status = Column(String(50), nullable=False)
    crn = Column(String(255), nullable=False)
    href = Column(Text, nullable=False)
    lifecycle_state = Column(Enum(*ALL_LIFECYCLE_STATE_LIST), nullable=False)
    name = Column(String(255), nullable=False)
    resource_type = Column(Enum(RESOURCE_TYPE_PLACEMENT_GROUP), nullable=False)
    strategy = Column(Enum(*ALL_STRATEGY_LIST), nullable=False)
    created_at = Column(DateTime, nullable=False)

    resource_group_id = Column(String(32), ForeignKey("ibm_resource_groups.id", ondelete="CASCADE"))

    resource_group = relationship(
        "IBMResourceGroup", backref=backref("placement_groups", cascade="all, delete-orphan", passive_deletes=True,
                                            lazy="dynamic")
    )

    __table_args__ = (
        UniqueConstraint(name, "region_id", "cloud_id", name="uix_ibm_placement_groups_name_region_id_cloud_id"),
    )

    def __init__(
            self, name, resource_id=None, lifecycle_state=None, strategy=STRATEGY_HOST_SPREAD, crn=None, href=None,
            created_at=None,
            resource_type=RESOURCE_TYPE_PLACEMENT_GROUP, status=CREATED
    ):
        self.id = str(uuid.uuid4().hex)
        self.name = name
        self.resource_id = resource_id
        self.lifecycle_state = lifecycle_state
        self.strategy = strategy
        self.crn = crn
        self.href = href
        self.created_at = created_at
        self.resource_type = resource_type
        self.status = status

    def to_reference_json(self):
        return {
            self.ID_KEY: self.id,
            self.NAME_KEY: self.name
        }

    def to_template_json(self):
        resource_json = {
            self.NAME_KEY: self.name,
            self.RESOURCE_GROUP_KEY: {self.ID_KEY: self.resource_group_id},
            self.STRATEGY_KEY: self.strategy,
        }

        resource_data = {
            self.ID_KEY: self.id,
            self.IBM_CLOUD_KEY: {self.ID_KEY: self.cloud_id},
            self.REGION_KEY: {self.ID_KEY: self.region_id},
            self.RESOURCE_JSON_KEY: resource_json
        }

        return resource_data

    def from_softlayer_to_ibm(self):
        resource_json = {
            self.NAME_KEY: self.name,
            self.RESOURCE_GROUP_KEY: {
                "id": DUMMY_RESOURCE_GROUP_ID,
                "name": DUMMY_RESOURCE_GROUP_NAME
            },
            self.STRATEGY_KEY: self.strategy,
        }
        placement_group_schema = {
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

        return placement_group_schema

    def to_json(self):
        return {
            self.ID_KEY: self.id,
            self.NAME_KEY: self.name,
            self.CREATED_AT_KEY: self.created_at,
            self.RESOURCE_ID_KEY: self.resource_id,
            self.RESOURCE_GROUP_KEY: self.resource_group.to_reference_json(),
            self.LIFECYCLE_STATE_KEY: self.lifecycle_state,
            self.RESOURCE_TYPE_KEY: self.resource_type,
            self.STRATEGY_KEY: self.strategy,
            self.REGION_KEY: self.region.to_reference_json(),
            self.IBM_CLOUD_KEY: self.ibm_cloud.to_reference_json(),
            self.STATUS_KEY: self.status
        }

    def validate_json_for_schema(self):
        return {
            self.ID_KEY: self.id,
            self.RESOURCE_JSON_KEY: {
                self.NAME_KEY: self.name
            }
        }

    @classmethod
    def from_ibm_json_body(cls, json_body):
        return cls(
            created_at=return_datetime_object(json_body["created_at"]),
            crn=json_body["crn"],
            href=json_body["href"],
            resource_id=json_body["id"],
            lifecycle_state=json_body["lifecycle_state"],
            name=json_body["name"],
            resource_type=json_body["resource_type"],
            strategy=json_body["strategy"],
        )

    def update_from_object(self, other):
        assert isinstance(other, self.__class__)

        self.name = other.name
        self.resource_id = other.resource_id
        self.lifecycle_state = other.lifecycle_state
        self.strategy = other.strategy
        self.crn = other.crn
        self.href = other.href
        self.status = other.status

    def dis_params_eq(self, other):
        assert isinstance(other, self.__class__)

        return (self.name == other.name and self.resource_id == other.resource_id and
                self.lifecycle_state == other.lifecycle_state and self.strategy == other.strategy and
                self.crn == other.crn and self.href == other.href and self.status == other.status)

    def dis_add_update_db(self, db_session, db_placement_groups, db_cloud, db_resource_group, db_region):
        if not db_resource_group:
            return
        db_placement_groups_id_obj_dict = dict()
        db_placement_groups_name_obj_dict = dict()
        for db_placement_group in db_placement_groups:
            db_placement_groups_id_obj_dict[db_placement_group.resource_id] = db_placement_group
            db_placement_groups_name_obj_dict[db_placement_group.name] = db_placement_group

        if self.resource_id not in db_placement_groups_id_obj_dict and self.name in db_placement_groups_name_obj_dict:
            # Creation Pending / Creating
            existing = db_placement_groups_name_obj_dict[self.name]
        elif self.resource_id in db_placement_groups_id_obj_dict:
            # Created. Update everything including name
            existing = db_placement_groups_id_obj_dict[self.resource_id]
        else:
            existing = None

        if not existing:
            self.ibm_cloud = db_cloud
            self.resource_group = db_resource_group
            self.region = db_region
            db_session.add(self)
            db_session.commit()
            return

        if not self.dis_params_eq(existing):
            existing.update_from_object(self)
            existing.resource_group = db_resource_group
            existing.region = db_region

        db_session.commit()
