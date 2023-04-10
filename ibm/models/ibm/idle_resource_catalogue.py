import uuid

from sqlalchemy import Column, DateTime, JSON, String
from ibm.common.utils import return_datetime_object
from ibm.models.base import Base
from ibm.models.ibm.mixins import IBMCloudResourceMixin
from ibm.web import db as ibmdb


class IBMResourceControllerData(IBMCloudResourceMixin, Base):
    ID_KEY = "id"
    CRN_KEY = "crn"
    CREATED_AT_KEY = "created_at"
    CREATED_BY_KEY = "created_by"
    UPDATED_AT_KEY = "updated_at"
    DELETED_AT_KEY = "deleted_at"
    DELETED_BY_KEY = "deleted_by"
    RESTORED_AT_KEY = "restored_at"
    NAME_KEY = "name"
    STATE_KEY = "state"
    LAST_OPERATION_KEY = "last_operation"
    COST_KEY = "cost"
    COST_NOT_APPLICABLE_KEY = "not applicable"

    CRZ_BACKREF_NAME = "idle_resource_catalog"

    RESOURCE_TYPE_LIST = ["is.snapshot",
                          "is.image",
                          "is.volume",
                          "is.public-gateway",
                          "is.floating-ip",
                          "is.dedicated-host",
                          "is.vpn",
                          "is.load-balancer",
                          "is.instance",
                          "containers-kubernetes"]

    __tablename__ = "ibm_resource_controller_data"

    id = Column(String(32), primary_key=True)
    crn = Column(String(255), nullable=False)
    created_at = Column(DateTime, nullable=False)
    created_by = Column(String(255), nullable=False)
    updated_at = Column(DateTime, nullable=True)
    deleted_at = Column(DateTime, nullable=True)
    deleted_by = Column(String(255), nullable=True)
    restored_at = Column(DateTime, nullable=True)
    name = Column(String(255), nullable=False)
    state = Column(String(64), nullable=False)
    last_operation = Column(JSON, nullable=True)

    def __init__(self, crn, created_at, created_by, updated_at, deleted_at, deleted_by, restored_at, name, state,
                 last_operation):
        self.id = str(uuid.uuid4().hex)
        self.crn = crn
        self.created_at = created_at
        self.created_by = created_by
        self.updated_at = updated_at
        self.deleted_at = deleted_at
        self.deleted_by = deleted_by
        self.restored_at = restored_at
        self.name = name
        self.state = state
        self.last_operation = last_operation

    def to_json(self):
        return {
            self.CRN_KEY: self.crn,
            self.CREATED_AT_KEY: self.created_at,
            self.CREATED_BY_KEY: self.created_by,
            self.UPDATED_AT_KEY: self.updated_at,
            self.RESTORED_AT_KEY: self.restored_at,
            self.NAME_KEY: self.name,
            self.STATE_KEY: self.state,
            self.LAST_OPERATION_KEY: self.last_operation.get("description") if self.last_operation else None
        }

    @classmethod
    def from_ibm_json_body(cls, json_body):
        return IBMResourceControllerData(
            crn=json_body["id"],
            created_at=return_datetime_object(json_body["created_at"]),
            created_by=json_body["created_by"],
            updated_at=return_datetime_object(json_body.get("updated_at")) if json_body.get("updated_at") else None,
            state=json_body["state"],
            name=json_body["name"],
            deleted_at=return_datetime_object(json_body["deleted_at"]) if json_body["deleted_at"] else None,
            deleted_by=json_body["deleted_by"],
            restored_at=return_datetime_object(json_body["restored_at"]) if json_body["restored_at"] else None,
            last_operation=json_body["last_operation"]
        )

    def update_from_object(self, other):
        assert isinstance(other, self.__class__)
        self.crn = other.crn
        self.created_at = other.created_at
        self.created_by = other.created_by
        self.updated_at = other.updated_at
        self.deleted_at = other.deleted_at
        self.deleted_by = other.deleted_by
        self.restored_at = other.restored_at
        self.name = other.name
        self.state = other.state
        self.last_operation = other.last_operation

    def dis_add_update_db(self, db_session, db_resource_catalog, db_cloud):
        existing = db_resource_catalog or None
        if not existing:
            self.ibm_cloud = db_cloud
            db_session.commit()
            return

        existing.update_from_object(self)
        db_session.commit()

    def to_reporting_json(self, month):
        from ibm.models import IBMResourceInstancesCost, IBMCost
        session = ibmdb.session
        cost_obj = session.query(IBMCost).filter_by(billing_month=month).first()
        if cost_obj:
            resource_instance_cost = \
                session.query(IBMResourceInstancesCost).filter_by(crn=self.crn, cost_id=cost_obj.id).first()
            cost = resource_instance_cost.cost if resource_instance_cost else \
                IBMResourceControllerData.COST_NOT_APPLICABLE_KEY
        else:
            cost = IBMResourceControllerData.COST_NOT_APPLICABLE_KEY
        return {
            self.CRN_KEY: self.crn,
            self.NAME_KEY: self.name,
            self.CREATED_AT_KEY: str(self.created_at),
            self.CREATED_BY_KEY: self.created_by,
            self.DELETED_AT_KEY: str(self.deleted_at),
            self.DELETED_BY_KEY: self.deleted_by,
            self.COST_KEY: cost
        }
