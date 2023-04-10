import uuid
from datetime import datetime

from sqlalchemy import Column, DateTime, ForeignKey, Float, JSON, String

from config import PaginationConfig
from ibm.models.base import Base
from ibm.models.ibm.mixins import IBMRegionalResourceMixin
from ibm.web import db as ibmdb


# Idle resource's model
class IBMIdleResource(IBMRegionalResourceMixin, Base):
    ID_KEY = "id"
    DB_RESOURCE_ID_KEY = "db_resource_id"
    RESOURCE_ID_KEY = 'resource_id'
    REASON_KEY = "reason"
    SOURCE_TYPE_KEY = "source_type"
    MARKED_AT_KEY = "marked_at"
    RESOURCE_JSON = "resource_json"
    ESTIMATED_MONTHLY_SAVINGS_KEY = "estimated_monthly_savings"
    RESOURCE_TYPE_KEY = "resource_type"

    SOURCE_DISCOVERY = "discovery"

    # Recommendations Type
    RECOMMENDATION_TYPE_KEY = "recommendation_type"
    IDLE_RESOURCE_TYPE_KEY = "Idle Resource"

    CRZ_BACKREF_NAME = "ibm_idle_resources"

    __tablename__ = "ibm_idle_resources"

    id = Column(String(32), primary_key=True)
    db_resource_id = Column(String(32), index=True, nullable=False)
    reason = Column(String(150))
    resource_type = Column(String(50))
    source_type = Column(String(50), nullable=False)
    marked_at = Column(DateTime, default=datetime.utcnow(), nullable=False, onupdate=datetime.utcnow())
    resource_json = Column(JSON, nullable=False)
    estimated_savings = Column(Float)
    created_at = Column(DateTime, nullable=False)

    vpc_id = Column(String(32), ForeignKey("ibm_vpc_networks.id", ondelete="SET NULL"), nullable=True)

    def __init__(self, db_resource_id, source_type, resource_json, resource_type, estimated_savings=None, reason=None):
        self.id = str(uuid.uuid4().hex)
        self.db_resource_id = db_resource_id
        self.reason = reason
        self.source_type = source_type
        self.resource_json = resource_json
        self.resource_type = resource_type
        self.estimated_savings = estimated_savings
        self.created_at = datetime.utcnow()

    def update_db(self, obj, session=None):
        session = session if session else ibmdb.session
        self.resource_json = obj.to_idle_json(session)
        session.commit()

    @classmethod
    def validate_search_params(cls, params):
        kwargs = {}

        if params.get("region"):
            kwargs["region"] = params["region"]

        if params.get("db_resource_id"):
            kwargs["db_resource_id"] = params["db_resource_id"]

        if params.get("source_type"):
            kwargs["source_type"] = params["source_type"]

        if params.get("vpc_id"):
            kwargs["vpc_id"] = params["vpc_id"]

        return kwargs

    @classmethod
    def search_and_filter(cls, params, cloud_id):
        start = params.get('start', 1, type=int)
        limit = params.get('limit', PaginationConfig.DEFAULT_ITEMS_PER_PAGE, type=int)

        kwargs = IBMIdleResource.validate_search_params(params)
        return ibmdb.session.query(IBMIdleResource).filter_by(**kwargs).filter_by(cloud_id=cloud_id).paginate(
            start, limit, False, PaginationConfig.MAX_ITEMS_PER_PAGE)

    def to_json(self):
        idle_resource_json = self.resource_json
        idle_resource_json.update({
            self.ID_KEY: self.id,
            self.REGION_KEY: self.region.name,
            self.DB_RESOURCE_ID_KEY: self.db_resource_id,
            self.REASON_KEY: self.reason,
            self.SOURCE_TYPE_KEY: self.source_type,
            self.MARKED_AT_KEY: str(self.marked_at),
            self.IBM_CLOUD_KEY: self.cloud_id
        })

        return idle_resource_json

    def to_reporting_json(self):
        resource_json = self.resource_json
        idle_resource_json = {
            self.ID_KEY: self.id,
            self.REGION_KEY: self.region.name,
            self.ESTIMATED_MONTHLY_SAVINGS_KEY: resource_json.get('estimated_savings', 0.0),
            self.RESOURCE_ID_KEY: resource_json.get('resource_id'),
            self.IBM_CLOUD_KEY: self.cloud_id,
            self.REASON_KEY: self.reason,
            self.RESOURCE_TYPE_KEY: resource_json.get('resource_type'),
            self.RECOMMENDATION_TYPE_KEY: self.IDLE_RESOURCE_TYPE_KEY,

        }

        return idle_resource_json
