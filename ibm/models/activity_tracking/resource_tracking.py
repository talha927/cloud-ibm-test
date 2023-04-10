import logging
import uuid
from datetime import datetime

from sqlalchemy import Column, DateTime, ForeignKey, JSON, String, Float

from config import PaginationConfig
from ibm.models.base import Base
from ibm.models.ibm.mixins import IBMCloudResourceMixin
from ibm.web import db as ibmdb

LOGGER = logging.getLogger(__name__)


class IBMResourceTracking(IBMCloudResourceMixin, Base):
    ID_KEY = "id"
    REGION_KEY = "region"
    RESOURCE_TYPE_KEY = "resource_type"
    ACTION_TYPE = "action_type"
    ACTION_TAKEN_AT_KEY = "action_taken_at"
    RESOURCE_JSON_KEY = "resource_json"
    CLOUD_ID_KEY = "cloud_id"
    ESTIMATED_SAVINGS_KEY = "estimated_savings"

    # Action Types
    DELETED = "DELETED"
    RIGHT_SIZED = "RIGHT_SIZED"

    # Global Region
    GLOBAL = "global"

    # Resource Types for resource tracked
    FLOATING_IP = "FLOATING_IP"
    PUBLIC_GATEWAY = "PUBLIC_GATEWAY"
    CUSTOM_IMAGE = "CUSTOM_IMAGE"
    DEDICATED_HOST = "DEDICATED_HOST"
    UNATTACHED_VPE = "UNATTACHED_VPE"
    LOAD_BALANCER = "LOAD_BALANCER"
    VOLUME = "VOLUME"
    VPN = "VPN"
    SNAPSHOT = "SNAPSHOT"
    INSTANCE = "INSTANCE"

    # Resource Types for Individual resources
    FLOATING_IPS = "Floating Ips"
    PUBLIC_GATEWAYS = "Public Gateways"
    CUSTOM_IMAGES = "Custom Images"
    DEDICATED_HOSTS = "Dedicated Hosts"
    UNATTACHED_VPES = "End Point Gateways"
    LOAD_BALANCERS = "Load Balancers"
    VOLUMES = "Volumes"
    VPNS = "Virtual Private Networks"
    SNAPSHOTS = "Snapshots"
    INSTANCES = "Instances"

    CRZ_BACKREF_NAME = "ibm_resource_tracking"

    __tablename__ = "ibm_resource_tracking"

    id = Column(String(32), primary_key=True)
    resource_type = Column(String(256), nullable=False)
    estimated_savings = Column(Float, nullable=False)
    action_type = Column(String(50), nullable=False)
    action_taken_at = Column(DateTime, default=datetime.utcnow(), nullable=False, onupdate=datetime.utcnow())
    resource_json = Column(JSON, nullable=False)

    region_id = Column(String(32), ForeignKey('ibm_regions.id', ondelete="SET NULL"), nullable=True)

    def __init__(self, resource_type, estimated_savings, action_type, resource_json):
        self.id = str(uuid.uuid4().hex)
        self.estimated_savings = estimated_savings
        self.resource_type = resource_type
        self.action_type = action_type
        self.resource_json = resource_json

    def update_db(self, obj):
        self.region_id = obj.region_id
        self.action_type = obj.action_type
        self.estimated_savings = obj.estimated_savings
        self.action_taken_at = obj.action_taken_at
        self.resource_json = obj.resource_json

    @classmethod
    def validate_search_params(cls, params):
        kwargs = {}

        if params.get("resource_type"):
            kwargs["resource_type"] = params["resource_type"]

        if params.get("action_type"):
            kwargs["action_type"] = params["action_type"]

        return kwargs

    @classmethod
    def search_and_filter(cls, params, cloud_id):
        from ibm.common.utils import get_month_interval

        start = params.get('start', 1, type=int)
        limit = params.get('limit', PaginationConfig.DEFAULT_ITEMS_PER_PAGE, type=int)

        start_m, end = get_month_interval(month_name=params.get('month'))
        kwargs = IBMResourceTracking.validate_search_params(params)
        return ibmdb.session.query(IBMResourceTracking).filter_by(**kwargs).filter_by(cloud_id=cloud_id).order_by(
            IBMResourceTracking.action_taken_at.desc()).filter(
            IBMResourceTracking.action_taken_at >= start_m, IBMResourceTracking.action_taken_at < end).paginate(
            start, limit, False, PaginationConfig.DEFAULT_ITEMS_PER_PAGE)

    def to_json(self):
        return {
            self.ID_KEY: self.id,
            self.REGION_KEY: self.region_id,
            self.ACTION_TYPE: self.action_type,
            self.ESTIMATED_SAVINGS_KEY: self.estimated_savings,
            self.RESOURCE_TYPE_KEY: self.resource_type,
            self.ACTION_TAKEN_AT_KEY: str(self.action_taken_at),
            self.RESOURCE_JSON_KEY: self.resource_json,
            self.CLOUD_ID_KEY: self.cloud_id
        }

    def to_reporting_json(self):
        resource_json = self.resource_json
        recommendation_type = "idle_resource" if self.action_type == IBMResourceTracking.DELETED else "rightsizing"
        return {
            self.ID_KEY: self.id,
            self.REGION_KEY: self.region.id if self.region else None,
            self.ESTIMATED_SAVINGS_KEY: self.estimated_savings,
            self.RESOURCE_ID_KEY: resource_json.get('resource_id'),
            self.IBM_CLOUD_KEY: self.cloud_id,
            self.RECOMMENDATION_TYPE_KEY: recommendation_type
        }
