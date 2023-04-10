import uuid
from datetime import datetime

from sqlalchemy import Column, DateTime, ForeignKey, String, Text
from sqlalchemy.orm import relationship
from sqlalchemy.schema import UniqueConstraint

from ibm import get_db_session as db
from ibm.common.consts import CREATED, CREATED_AT_FORMAT, DUMMY_CLOUD_ID, DUMMY_CLOUD_NAME, DUMMY_REGION_ID, \
    DUMMY_REGION_NAME, DUMMY_ZONE_ID, DUMMY_ZONE_NAME
from ibm.models.base import Base
from ibm.models.ibm.mixins import IBMZonalResourceMixin


class IBMPublicGateway(IBMZonalResourceMixin, Base):
    ID_KEY = "id"
    RESOURCE_ID_KEY = "resource_id"
    NAME_KEY = "name"
    CREATED_AT_KEY = "created_at"
    CRN_KEY = "crn"
    HREF_KEY = "href"
    STATUS_KEY = "status"
    RESOURCE_TYPE_KEY = "resource_type"
    VPC_KEY = "vpc"
    RESOURCE_GROUP_KEY = "resource_group"
    SUBNETS_KEY = "subnets"
    FLOATING_IP_KEY = "floating_ip"
    ASSOCIATED_RESOURCES_KEY = "associated_resources"
    RESOURCE_JSON_KEY = "resource_json"
    RESOURCE_TYPE_PUBLIC_GATEWAY_KEY = "Public Gateway"
    ESTIMATED_SAVINGS = "estimated_savings"
    COST_KEY = "cost"

    # status consts
    STATUS_AVAILABLE = "available"
    STATUS_DELETING = "deleting"
    STATUS_FAILED = "failed"
    STATUS_PENDING = "pending"
    STATUSES_LIST = [STATUS_AVAILABLE, STATUS_DELETING, STATUS_FAILED, STATUS_PENDING]

    CRZ_BACKREF_NAME = "public_gateways"

    DEFAULT_RESOURCE_TYPE = "public_gateway"

    __tablename__ = "ibm_public_gateways"

    id = Column(String(32), primary_key=True)
    resource_id = Column(String(64), nullable=False)
    name = Column(String(255), nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow(), nullable=False)
    crn = Column(String(255), nullable=False)
    href = Column(Text, nullable=False)
    status = Column(String(50), nullable=False)
    resource_type = Column(String(50), default=DEFAULT_RESOURCE_TYPE, nullable=False)

    vpc_id = Column(String(32), ForeignKey("ibm_vpc_networks.id", ondelete="CASCADE"))
    resource_group_id = Column(String(32), ForeignKey("ibm_resource_groups.id", ondelete="SET NULL"), nullable=True)

    subnets = relationship("IBMSubnet", backref="public_gateway", lazy="dynamic")
    floating_ip = relationship("IBMFloatingIP", backref="public_gateway", uselist=False)

    __table_args__ = (
        UniqueConstraint(
            name, vpc_id, "cloud_id", "region_id", name="uix_ibm_public_gateway_name_vpc_region_id_cloud_id"
        ),
    )

    def __init__(self, name, crn, href, resource_id,
                 created_at=None, status=CREATED, cloud_id=None, resource_type=DEFAULT_RESOURCE_TYPE):
        self.id = str(uuid.uuid4().hex)
        self.name = name
        self.crn = crn
        self.href = href
        self.resource_id = resource_id
        self.created_at = created_at
        self.status = status
        self.cloud_id = cloud_id
        self.resource_type = resource_type

    def to_reference_json(self, subnets=True):
        json_data = {
            self.ID_KEY: self.id,
            self.NAME_KEY: self.name,
            self.ZONE_KEY: self.zone.to_reference_json(),
            self.FLOATING_IP_KEY: self.floating_ip.to_reference_json() if self.floating_ip else {},
        }
        if subnets:
            json_data[self.SUBNETS_KEY] = [subnet.to_reference_json() for subnet in self.subnets.all()]

        return json_data

    def to_template_json(self):
        resource_json = {
            self.NAME_KEY: self.name,
            self.VPC_KEY: {self.ID_KEY: self.vpc_id},
            self.ZONE_KEY: {self.ID_KEY: self.zone_id},
            self.RESOURCE_GROUP_KEY: {
                self.ID_KEY: self.resource_group.id,
                self.NAME_KEY: self.resource_group.name,
            }

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
                self.FLOATING_IP_KEY: self.floating_ip.to_reference_json() if self.floating_ip else {}
            }
        }

    def to_json(self):
        return {
            self.ID_KEY: self.id,
            self.RESOURCE_ID_KEY: self.resource_id,
            self.NAME_KEY: self.name,
            self.CREATED_AT_KEY: self.created_at,
            self.CRN_KEY: self.crn,
            self.HREF_KEY: self.href,
            self.STATUS_KEY: self.status,
            self.RESOURCE_TYPE_KEY: self.resource_type,
            self.IBM_CLOUD_KEY: self.ibm_cloud.to_reference_json(),
            self.RESOURCE_GROUP_KEY: self.resource_group.to_reference_json(),
            self.REGION_KEY: self.region.to_reference_json(),
            self.ZONE_KEY: self.zone.to_reference_json(),
            self.ASSOCIATED_RESOURCES_KEY: {
                self.VPC_KEY: self.vpc_network.to_reference_json(),
                self.SUBNETS_KEY: [subnet.to_reference_json() for subnet in self.subnets.all()],
                self.FLOATING_IP_KEY: self.floating_ip.to_reference_json() if self.floating_ip else {},
            },
        }

    def to_idle_json(self, session=None):
        from ibm.models.ibm.cost_models import IBMResourceInstancesCost

        session = session if session else db.session
        cost_obj = IBMResourceInstancesCost.get_cost(self.crn, self.cloud_id, session)
        return {
            self.STATUS_KEY: self.status,
            self.CRN_KEY: self.crn,
            self.HREF_KEY: self.href,
            self.REGION_KEY: self.region.name,
            self.RESOURCE_TYPE_KEY: self.RESOURCE_TYPE_PUBLIC_GATEWAY_KEY,
            self.RESOURCE_ID_KEY: self.resource_id,
            self.IBM_CLOUD_KEY: self.cloud_id,
            self.ESTIMATED_SAVINGS: cost_obj.estimated_cost if cost_obj else None,
            self.COST_KEY: cost_obj.estimated_cost if cost_obj else None
        }

    def from_softlayer_to_ibm(self):
        resource_json = {
            self.NAME_KEY: self.name,
            self.VPC_KEY: {
                "id": self.vpc_network.id
            },
            self.ZONE_KEY: {
                "id": DUMMY_ZONE_ID,
                "name": DUMMY_ZONE_NAME
            }

        }
        public_gateway_schema = {
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

        return public_gateway_schema

    def to_json_body(self):
        obj = {
            "name": self.name,
            "zone": {"name": self.zone},
            "vpc": {
                "id": self.ibm_vpc_network.resource_id if self.ibm_vpc_network else None
            },
        }
        if self.ibm_resource_group:
            obj["resource_group"] = {"id": self.ibm_resource_group.resource_id}
        return obj

    @classmethod
    def from_ibm_json_body(cls, json_body):
        ibm_public_gateway = cls(
            name=json_body["name"], resource_id=json_body["id"],
            crn=json_body["crn"], href=json_body["href"], status=json_body["status"],
            created_at=datetime.strptime(json_body["created_at"], CREATED_AT_FORMAT)
        )

        return ibm_public_gateway

    def dis_params_eq(self, other):
        assert isinstance(other, self.__class__)

        return (self.name == other.name and self.resource_id == other.resource_id and self.status == other.status and
                self.crn == other.crn and self.href == other.href)

    def dis_add_update_db(self, db_session, db_public_gateways, cloud_id, vpc_network_id, resource_group_id, db_zone):
        from ibm.models import IBMCloud, IBMVpcNetwork, IBMResourceGroup

        resource_group = db_session.query(IBMResourceGroup).filter_by(resource_id=resource_group_id,
                                                                      cloud_id=cloud_id).first()
        cloud = db_session.query(IBMCloud).get(cloud_id)

        vpc_network = db_session.query(IBMVpcNetwork).filter_by(cloud_id=cloud_id, resource_id=vpc_network_id).first()

        if not (cloud and vpc_network):
            return

        db_public_gateways_id_obj_dict = dict()
        db_public_gateways_name_obj_dict = dict()
        for db_public_gateway in db_public_gateways:
            db_public_gateways_id_obj_dict[db_public_gateway.resource_id] = db_public_gateway
            db_public_gateways_name_obj_dict[db_public_gateway.name] = db_public_gateway
        # TODO need to revisit this use case
        # if self.resource_id not in db_public_gateways_id_obj_dict and self.name in db_public_gateways_name_obj_dict:
        #     # Creation Pending / Creating
        #     existing = db_public_gateways_name_obj_dict[self.name]
        if self.resource_id in db_public_gateways_id_obj_dict:
            # Created. Update everything including name
            existing = db_public_gateways_id_obj_dict[self.resource_id]
        else:
            existing = None
        if not existing:
            self.ibm_cloud = cloud
            self.vpc_network = vpc_network
            self.resource_group = resource_group
            self.zone = db_zone
            db_session.commit()
            return

        if not self.dis_params_eq(existing):
            existing.update_from_object(self)
            existing.vpc_network = vpc_network
            existing.resource_group = resource_group
            existing.zone = db_zone

        db_session.commit()

    def update_from_object(self, other):
        assert isinstance(other, self.__class__)

        self.name = other.name
        self.status = other.status
        self.resource_id = other.resource_id
        self.crn = other.crn
        self.href = other.href
