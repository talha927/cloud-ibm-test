import uuid
from datetime import datetime

from sqlalchemy import Column, Date, DateTime, Float, ForeignKey, String
from sqlalchemy.orm import relationship

from ibm.web import db as ibmdb
from ibm.common.consts import BILLING_MONTH_FORMAT
from ibm.models.base import Base
from ibm.models.ibm.mixins import IBMCloudResourceMixin


class IBMCost(IBMCloudResourceMixin, Base):
    ID_KEY = "id"
    ACCOUNT_ID_KEY = "account_id"
    BILLING_MONTH_KEY = "billing_month"
    BILLABLE_COST_KEY = "billable_cost"
    NON_BILLABLE_COST_KEY = "non_billable_cost"
    BILLING_COUNTRY_CODE_KEY = "billing_country_code"
    BILLING_CURRENCY_CODE_KEY = "billing_currency_code"
    RESOURCES_KEY = "resources"

    CRZ_BACKREF_NAME = "costs"

    __tablename__ = "ibm_costs"

    id = Column(String(32), primary_key=True)
    account_id = Column(String(255), nullable=False)
    billing_month = Column(DateTime, nullable=False)
    billable_cost = Column(Float, nullable=False)
    non_billable_cost = Column(Float, nullable=False)
    billing_country_code = Column(String(255), nullable=False)
    billing_currency_code = Column(String(255), nullable=False)

    resources = relationship("IBMResourcesCost", backref="ibm_cost", cascade="all, delete-orphan",
                             passive_deletes=True, lazy="dynamic", )
    resource_instances = relationship("IBMResourceInstancesCost", backref="ibm_cost", cascade="all, delete-orphan",
                                      passive_deletes=True, lazy="dynamic", )
    resource_instances_daily = relationship("IBMResourceInstancesDailyCost", backref="ibm_cost",
                                            passive_deletes=True, cascade="all, delete-orphan", lazy="dynamic", )

    def __init__(self, account_id, billing_month, billable_cost, non_billable_cost, billing_country_code,
                 billing_currency_code):
        self.id = str(uuid.uuid4().hex)
        self.account_id = account_id
        self.billing_month = billing_month
        self.billable_cost = billable_cost
        self.non_billable_cost = non_billable_cost
        self.billing_country_code = billing_country_code
        self.billing_currency_code = billing_currency_code

    def to_reference_json(self):
        return {
            self.ID_KEY: self.id,
        }

    def to_json(self):
        return {
            self.ID_KEY: self.id,
            self.ACCOUNT_ID_KEY: self.account_id,
            self.BILLING_MONTH_KEY: self.billing_month,
            self.BILLABLE_COST_KEY: round(self.billable_cost) if self.billable_cost else 0.0,
            self.NON_BILLABLE_COST_KEY: round(self.non_billable_cost) if self.non_billable_cost else 0.0,
            self.BILLING_COUNTRY_CODE_KEY: self.billing_country_code,
            self.BILLING_CURRENCY_CODE_KEY: self.billing_currency_code,
            self.RESOURCES_KEY: [resource.to_json() for resource in self.resources.all()],
        }

    @classmethod
    def from_ibm_json_body(cls, json_body, cloud_id):
        """Parse ibm response
        :params json_body:
            "{
            "month": "2022-12",
            "resources": {
                "billable_cost": 4273.715969839175,
                "non_billable_cost": 0
                },
            "account_resources": [{
                "resource_id": "is.endpoint-gateway",
                "billable_cost": 0,
                "resource_name": "Virtual Private Endpoint for VPC",
                "non_billable_cost": 0,
                "billable_rated_cost": 0,
                "non_billable_rated_cost": 0}]
        """

        ibm_cost = cls(
            account_id=json_body['account_id'],
            billing_month=datetime.strptime(json_body["month"], BILLING_MONTH_FORMAT),
            billable_cost=json_body["resources"]["billable_cost"],
            non_billable_cost=json_body["resources"]["non_billable_cost"],
            billing_country_code=json_body["billing_country_code"],
            billing_currency_code=json_body["billing_currency_code"]
        )

        for resource in json_body.get("account_resources", []):
            individual_resource_cost = IBMResourcesCost.from_ibm_json_body(resource)
            individual_resource_cost.cloud_id = cloud_id
            ibm_cost.resources.append(individual_resource_cost)

        return ibm_cost

    def update_from_obj(self, other):
        """
        Update an existing object of the class from an updated one
        """
        assert isinstance(other, self.__class__)

        self.account_id = other.account_id
        self.billing_month = other.billing_month
        self.billable_cost = other.billable_cost
        self.non_billable_cost = other.non_billable_cost
        self.billing_country_code = other.billing_country_code
        self.billing_currency_code = other.billing_currency_code

    def dis_params_eq(self, other):
        assert isinstance(other, self.__class__)

        return (self.account_id == other.account_id and self.billing_month == other.billing_month and
                self.billable_cost == other.billable_cost and self.non_billable_cost == other.non_billable_cost and
                self.billing_country_code == other.billing_country_code and
                self.billing_currency_code == other.billing_currency_code)

    def dis_add_update_db(self, db_session, db_costs, cloud_id):
        from ibm.models import IBMCloud

        db_costs_billing_date_obj_dict = dict()
        for db_cost in db_costs:
            db_costs_billing_date_obj_dict[db_cost.billing_month] = db_cost

        if self.billing_month in db_costs_billing_date_obj_dict:
            existing = db_costs_billing_date_obj_dict[self.billing_month]
        else:
            existing = None

        if not existing:
            cloud = db_session.query(IBMCloud).get(cloud_id)
            assert cloud

            self.ibm_cloud = cloud
            db_session.commit()
            return

        if not self.dis_params_eq(existing):
            existing.update_from_obj(self)

        db_session.commit()


class IBMResourcesCost(IBMCloudResourceMixin, Base):
    ID_KEY = "id"
    RESOURCE_ID_KEY = "resource_id"
    BILLABLE_COST_KEY = "billable_cost"
    NON_BILLABLE_COST_KEY = "non_billable_cost"
    RESOURCE_NAME_KEY = "resource_name"

    CRZ_BACKREF_NAME = "individual_resource_cost"

    __tablename__ = "ibm_resources_cost"

    id = Column(String(32), primary_key=True)
    resource_id = Column(String(255), nullable=False)
    billable_cost = Column(Float, nullable=False)
    non_billable_cost = Column(Float, nullable=False)
    resource_name = Column(String(255))

    cost_id = Column(String(32), ForeignKey("ibm_costs.id", ondelete="CASCADE"))

    def __init__(self, resource_id, billable_cost, non_billable_cost, resource_name):
        self.id = str(uuid.uuid4().hex)
        self.resource_id = resource_id
        self.billable_cost = billable_cost
        self.non_billable_cost = non_billable_cost
        self.resource_name = resource_name

    def to_reference_json(self):
        return {
            self.ID_KEY: self.id,
            self.RESOURCE_NAME_KEY: self.resource_name
        }

    def to_json(self):
        return {
            self.ID_KEY: self.id,
            self.RESOURCE_ID_KEY: self.resource_id,
            self.BILLABLE_COST_KEY: round(self.billable_cost) if self.billable_cost else 0,
            self.NON_BILLABLE_COST_KEY: round(self.non_billable_cost) if self.non_billable_cost else 0,
            self.RESOURCE_NAME_KEY: self.resource_name,
        }

    @classmethod
    def from_ibm_json_body(cls, json_body):
        return cls(
            resource_id=json_body["resource_id"], billable_cost=json_body["billable_cost"],
            non_billable_cost=json_body["non_billable_cost"], resource_name=json_body["resource_name"]
        )

    @staticmethod
    def get_cost(crn, cloud_id, session=None):
        """
        Get a resource cost through provide resource id and cloud_id
        """

        if not session:
            session = ibmdb.session
        cost_obj = session.query(IBMCost).filter_by(cloud_id=cloud_id).order_by(IBMCost.billing_month.desc()).first()
        if not cost_obj:
            return

        kwargs = {
            "crn": crn,
            "cloud_id": cloud_id,
            "cost_id": cost_obj.id
        }
        return session.query(IBMResourceInstancesCost).filter_by(**kwargs).first()


class IBMResourceInstancesCost(IBMCloudResourceMixin, Base):
    # IBM resource_id mapper to our DB tables
    from ibm.models.ibm.floating_ip_models import IBMFloatingIP
    from ibm.models.ibm.instance_models import IBMInstance
    from ibm.models.ibm.volume_models import IBMVolume

    resource_id_mapper = {
        "is.floating-ip":  IBMFloatingIP,
        "is.instance": IBMInstance,
        "is.volume": IBMVolume,
    }

    # for frontend
    resource_id_resource_type_mapper = {
        "is.floating-ip": "Floating IPs",
        "is.instance": "Virtual Server Instances",
        "is.volume": "Volumes",
        "is.load-balancer": "Load Balancers",
        "is.snapshot": "Snapshots",
        "is.vpn-server": "VPNs",
        "containers-kubernetes": "Kubernetes"
    }

    COST_KEY = "cost"
    CRZ_BACKREF_NAME = "resource_instances_cost"
    ESTIMATED_COST = "estimated_cost"
    UNIT_COST = "unit_cost"

    __tablename__ = "ibm_resource_instances_cost"

    id = Column(String(32), primary_key=True)
    resource_id = Column(String(512), nullable=False)  # resource_id is service name
    crn = Column(String(512), nullable=False)
    cost = Column(Float, nullable=False)
    estimated_cost = Column(Float, nullable=False)

    cost_id = Column(String(32), ForeignKey("ibm_costs.id", ondelete="CASCADE"))

    def __init__(self, resource_id, cost, crn, estimated_cost):
        self.id = str(uuid.uuid4().hex)
        self.resource_id = resource_id
        self.cost = cost
        self.estimated_cost = estimated_cost
        self.crn = crn

    def update_from_obj(self, other):
        """
        Update an existing object of the class from an updated one
        """
        assert isinstance(other, self.__class__)

        self.cost = other.cost
        self.estimated_cost = other.estimated_cost

    @staticmethod
    def get_cost(crn, cloud_id, session=None):
        """
        Get a resource cost through provide resource id and cloud_id
        """
        if not session:
            session = ibmdb.session

        cost_obj = session.query(IBMCost).filter_by(cloud_id=cloud_id).order_by(IBMCost.billing_month.desc()).first()
        if not cost_obj:
            return

        kwargs = {
            "crn": crn,
            "cloud_id": cloud_id,
            "cost_id": cost_obj.id
        }
        return session.query(IBMResourceInstancesCost).filter_by(**kwargs).first()


class IBMResourceInstancesDailyCost(IBMCloudResourceMixin, Base):
    COST_KEY = "cost"
    CRZ_BACKREF_NAME = "resource_daily_cost"
    ESTIMATED_COST = "estimated_cost"
    UNIT_COST = "unit_cost"

    __tablename__ = "ibm_resource_instances_daily_cost"
    id = Column(String(32), primary_key=True)
    resource_id = Column(String(512), nullable=False)    # resource_id is service name
    crn = Column(String(512), nullable=False)
    daily_cost = Column(Float, nullable=False)
    date = Column(Date, nullable=False, index=True)
    created_at = Column(DateTime, nullable=False)

    cost_id = Column(String(32), ForeignKey("ibm_costs.id", ondelete="CASCADE"))

    def __init__(self, resource_id, daily_cost, crn, date):
        self.id = str(uuid.uuid4().hex)
        self.resource_id = resource_id
        self.daily_cost = daily_cost
        self.crn = crn
        self.created_at = datetime.utcnow()
        self.date = date


class IBMCostPerTag(IBMCloudResourceMixin, Base):
    ID_KEY = "id"
    COST_KEY = "cost"
    NAME_KEY = "name"
    DATE_KEY = "date"

    CRZ_BACKREF_NAME = "ibm_cost_per_tag"

    __tablename__ = "ibm_cost_per_tags"

    id = Column(String(32), primary_key=True)
    name = Column(String(512), nullable=False)
    cost = Column(Float, nullable=False)
    date = Column(DateTime, nullable=False)

    def __init__(self, name, cost, date):
        self.id = str(uuid.uuid4().hex)
        self.name = name
        self.cost = cost
        self.date = date

    def to_reference_json(self):
        return {
            self.NAME_KEY: self.name,
            self.COST_KEY: self.cost,
        }

    def to_json(self):
        return {
            self.ID_KEY: self.ID_KEY,
            self.NAME_KEY: self.name,
            self.COST_KEY: self.cost,
            self.DATE_KEY: str(self.date)
        }
