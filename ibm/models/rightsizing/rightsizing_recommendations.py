from datetime import datetime
import logging
import uuid

from sqlalchemy import Column, Float, ForeignKey, JSON, String, DateTime

from config import PaginationConfig
from ibm.models.base import Base
from ibm.models.ibm.mixins import IBMCloudResourceMixin
from ibm.web import db as ibmdb

LOGGER = logging.getLogger(__name__)


class IBMRightSizingRecommendation(IBMCloudResourceMixin, Base):
    ID_KEY = "id"
    REGION_KEY = "region"
    REGION_ID_KEY = "region_id"
    CURRENT_INSTANCE_TYPE_KEY = "current_instance_type"
    CURRENT_INSTANCE_RESOURCE_DETAILS_KEY = "current_instance_resource_details"
    MONTHLY_COST_KEY = "monthly_cost"
    RESOURCE_ID_KEY = "resource_id"
    CURRENCY_CODE_KEY = "currency_code"
    ESTIMATED_MONTHLY_COST_KEY = "estimated_monthly_cost"
    ESTIMATED_MONTHLY_SAVINGS_KEY = "estimated_monthly_savings"
    RECOMMENDED_INSTANCE_TYPE_KEY = "recommended_instance_type"
    RECOMMENDED_INSTANCE_RESOURCE_DETAILS_KEY = "recommended_instance_resource_details"
    RIGHTSIZING_REASON_KEY = "rightsizing_reason"
    MEMORY_KEY = "memory"
    VCPU_KEY = "vcpu"
    INSTANCE_ID_KEY = "instance_id"
    INSTANCE_KEY = "instance"
    CLOUD_ID_KEY = "cloud_id"
    RESOURCE_TYPE_KEY = "resource_type"
    REASON_KEY = "reason"

    # Right Sizing Type
    TERMINATE = "Terminate"
    MODIFY = "Modify"

    # Recommendations Type
    RECOMMENDATION_TYPE_KEY = "recommendation_type"
    RIGHTSIZING_TYPE_KEY = "Rightsizing"

    CRZ_BACKREF_NAME = "ibm_right_sizing_recommendations"

    __tablename__ = "ibm_right_sizing_recommendations"

    id = Column(String(32), primary_key=True)
    region = Column(String(32), nullable=False)
    current_instance_type = Column(String(512))
    current_instance_resource_details = Column(JSON)
    monthly_cost = Column(Float, nullable=False)
    resource_id = Column(String(256), nullable=False)
    estimated_monthly_cost = Column(Float)
    estimated_monthly_savings = Column(Float)
    recommended_instance_type = Column(String(512))
    recommended_instance_resource_details = Column(JSON)
    rightsizing_reason = Column(JSON)
    created_at = Column(DateTime, nullable=False)

    instance_id = Column(String(32), ForeignKey("ibm_instances.id", ondelete="CASCADE"))

    def __init__(self, region, current_instance_type, current_instance_resource_details, monthly_cost, resource_id,
                 estimated_monthly_cost, estimated_monthly_savings, recommended_instance_type,
                 recommended_instance_resource_details, rightsizing_reason=None):
        self.id = str(uuid.uuid4().hex)
        self.region = region
        self.current_instance_type = current_instance_type
        self.current_instance_resource_details = current_instance_resource_details
        self.monthly_cost = monthly_cost
        self.resource_id = resource_id
        self.estimated_monthly_cost = estimated_monthly_cost
        self.estimated_monthly_savings = estimated_monthly_savings
        self.recommended_instance_type = recommended_instance_type
        self.recommended_instance_resource_details = recommended_instance_resource_details
        self.rightsizing_reason = rightsizing_reason or "Underutilized"
        self.created_at = datetime.utcnow()

    def to_json(self):
        return {
            self.ID_KEY: self.id,
            self.REGION_KEY: self.ibm_instance.region.to_reference_json(),
            self.CURRENT_INSTANCE_TYPE_KEY: self.current_instance_type,
            self.CURRENT_INSTANCE_RESOURCE_DETAILS_KEY: {
                self.MEMORY_KEY: self.current_instance_resource_details["memory"] if
                self.current_instance_resource_details else None,
                self.VCPU_KEY: self.current_instance_resource_details["vcpu"] if
                self.current_instance_resource_details else None,
            },
            self.MONTHLY_COST_KEY: self.monthly_cost or "NA",
            self.RESOURCE_ID_KEY: self.resource_id,
            self.CURRENCY_CODE_KEY: None,
            self.ESTIMATED_MONTHLY_COST_KEY: self.estimated_monthly_cost or "NA",
            self.ESTIMATED_MONTHLY_SAVINGS_KEY: self.estimated_monthly_savings or "NA",
            self.RECOMMENDED_INSTANCE_TYPE_KEY: self.recommended_instance_type,
            self.RECOMMENDED_INSTANCE_RESOURCE_DETAILS_KEY: {
                self.MEMORY_KEY: self.recommended_instance_resource_details["memory"] if
                self.recommended_instance_resource_details else None,
                self.VCPU_KEY: self.recommended_instance_resource_details["vcpu"] if
                self.recommended_instance_resource_details else None,
            },
            self.RIGHTSIZING_REASON_KEY: self.rightsizing_reason,
            self.INSTANCE_ID_KEY: self.instance_id,
            self.INSTANCE_KEY: self.ibm_instance.to_reference_json(),
            self.CLOUD_ID_KEY: self.cloud_id
        }

    def to_reporting_json(self):
        return {
            self.ID_KEY: self.id,
            self.REGION_KEY: self.ibm_instance.region.name,
            self.ESTIMATED_MONTHLY_SAVINGS_KEY: self.estimated_monthly_savings or "NA",
            self.RESOURCE_ID_KEY: self.resource_id,
            self.CLOUD_ID_KEY: self.cloud_id,
            self.RESOURCE_TYPE_KEY: "Instance",
            self.REASON_KEY: self.rightsizing_reason,
            self.RECOMMENDATION_TYPE_KEY: self.RIGHTSIZING_TYPE_KEY
        }

    @classmethod
    def validate_search_params(cls, params):
        kwargs = {}
        vpc_kwargs = {}
        if params.get("resource_id"):
            kwargs["resource_id"] = params["resource_id"]

        if params.get("right_sizing_type"):
            kwargs["right_sizing_type"] = params["right_sizing_type"]

        if params.get("recommended_instance_type"):
            kwargs["recommended_instance_type"] = params["recommended_instance_type"]

        if params.get("vpc_id"):
            vpc_kwargs["id"] = params["vpc_id"]

        return vpc_kwargs, kwargs

    @classmethod
    def search_and_filter(cls, params, cloud_id):
        from ibm.models import IBMInstance, IBMVpcNetwork

        start = params.get('start', 1, type=int)
        limit = params.get('limit', PaginationConfig.DEFAULT_ITEMS_PER_PAGE, type=int)

        vpc_kwargs, kwargs = IBMRightSizingRecommendation.validate_search_params(params)
        if vpc_kwargs:
            return ibmdb.session.query(IBMRightSizingRecommendation).filter_by(**kwargs) \
                .join(IBMInstance).join(IBMVpcNetwork).filter_by(**vpc_kwargs).paginate(
                start, limit, False, PaginationConfig.MAX_ITEMS_PER_PAGE)

        return ibmdb.session.query(IBMRightSizingRecommendation).filter_by(**kwargs).filter_by(
            cloud_id=cloud_id).paginate(start, limit, False, PaginationConfig.MAX_ITEMS_PER_PAGE)

    def update_db(self, obj):
        self.recommended_instance_type = obj.recommended_instance_type
        self.recommended_instance_resource_details = obj.recommended_instance_resource_details
        self.rightsizing_reason = obj.rightsizing_reason
