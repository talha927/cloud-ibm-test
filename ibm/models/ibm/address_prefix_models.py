import logging
import uuid
from datetime import datetime

from sqlalchemy import Boolean, Column, DateTime, ForeignKey, orm, String
from sqlalchemy.orm import relationship
from sqlalchemy.schema import UniqueConstraint

from ibm.common.consts import CREATED, CREATED_AT_FORMAT, DUMMY_CLOUD_ID, DUMMY_CLOUD_NAME, DUMMY_REGION_ID, \
    DUMMY_REGION_NAME, DUMMY_ZONE_ID, DUMMY_ZONE_NAME
from ibm.models.base import Base
from ibm.models.ibm.mixins import IBMZonalResourceMixin

LOGGER = logging.getLogger(__name__)


class IBMAddressPrefix(IBMZonalResourceMixin, Base):
    ID_KEY = "id"
    RESOURCE_ID_KEY = "resource_id"
    CIDR_KEY = "cidr"
    CREATED_AT_KEY = "created_at"
    HAS_SUBNETS_KEY = "has_subnets"
    HREF_KEY = "href"
    IS_DEFAULT_KEY = "is_default"
    NAME_KEY = "name"
    STATUS_KEY = "status"
    VPC_KEY = "vpc"
    SUBNETS_KEY = "subnets"
    ASSOCIATED_RESOURCES_KEY = "associated_resources"
    RESOURCE_JSON_KEY = "resource_json"

    CRZ_BACKREF_NAME = "address_prefixes"

    __tablename__ = "ibm_address_prefixes"

    id = Column(String(32), primary_key=True)
    resource_id = Column(String(64), nullable=False)
    cidr = Column(String(255), nullable=False)
    created_at = Column(DateTime, nullable=False)
    has_subnets = Column(Boolean, nullable=False)
    href = Column(String(255), nullable=False)
    is_default = Column(Boolean, nullable=False)
    name = Column(String(255), nullable=False)
    status = Column(String(50), nullable=False)

    vpc_id = Column(String(32), ForeignKey("ibm_vpc_networks.id", ondelete="CASCADE"))

    subnets = relationship("IBMSubnet", backref="address_prefix", cascade="all, delete-orphan", passive_deletes=True,
                           lazy="dynamic")

    __table_args__ = (UniqueConstraint(name, vpc_id, name="uix_ibm_address_prefix_name_vpc_id"),)

    def __init__(self, name, cidr, has_subnets, href, created_at=None, resource_id=None,
                 status=CREATED, is_default=None):
        self.id = str(uuid.uuid4().hex)
        self.name = name
        self.cidr = cidr
        self.created_at = created_at
        self.has_subnets = has_subnets
        self.href = href
        self.status = status
        self.is_default = is_default
        self.resource_id = resource_id

    def to_reference_json(self):
        return {
            self.ID_KEY: self.id,
            self.NAME_KEY: self.name,
            self.CIDR_KEY: self.cidr,
            self.ZONE_KEY: self.zone.to_reference_json(),
            self.IS_DEFAULT_KEY: self.is_default
        }

    def to_template_json(self):
        resource_json = {
            self.NAME_KEY: self.name,
            self.CIDR_KEY: self.cidr,
            self.ZONE_KEY: {
                self.ID_KEY: self.zone_id,
            }
        }
        address_prefix_schema = {
            self.RESOURCE_JSON_KEY: resource_json,
            self.ID_KEY: self.id,
            self.IBM_CLOUD_KEY: {
                self.ID_KEY: self.cloud_id,
            },
            self.REGION_KEY: {
                self.ID_KEY: self.region_id,
            },
            self.VPC_KEY: {self.ID_KEY: self.vpc_id},
        }

        return address_prefix_schema

    def to_softlayer_reference_json(self):
        return {
            self.ID_KEY: self.id,
            self.NAME_KEY: self.name,
            self.CIDR_KEY: self.cidr,
        }

    def from_softlayer_to_ibm(self):
        resource_json = {
            self.NAME_KEY: self.name,
            self.CIDR_KEY: self.cidr,
            self.ZONE_KEY: {
                self.ID_KEY: DUMMY_ZONE_ID,
                self.NAME_KEY: DUMMY_ZONE_NAME
            }
        }
        address_prefix_schema = {
            self.ID_KEY: self.id,
            "ibm_cloud": {
                "id": DUMMY_CLOUD_ID,
                "name": DUMMY_CLOUD_NAME
            },
            "region": {
                "id": DUMMY_REGION_ID,
                "name": DUMMY_REGION_NAME
            },
            "vpc": {"id": self.vpc_network.id},
            "resource_json": resource_json
        }

        return address_prefix_schema

    def to_json(self):
        return {
            self.ID_KEY: self.id,
            self.RESOURCE_ID_KEY: self.resource_id,
            self.CIDR_KEY: self.cidr,
            self.CREATED_AT_KEY: self.created_at,
            self.HAS_SUBNETS_KEY: self.has_subnets,
            self.HREF_KEY: self.href,
            self.IS_DEFAULT_KEY: self.is_default,
            self.NAME_KEY: self.name,
            self.STATUS_KEY: self.status,
            self.IBM_CLOUD_KEY: self.ibm_cloud.to_reference_json(),
            self.REGION_KEY: self.region.to_reference_json(),
            self.ZONE_KEY: self.zone.to_reference_json(),
            self.ASSOCIATED_RESOURCES_KEY: {
                self.VPC_KEY: self.vpc_network.to_reference_json(),
                self.SUBNETS_KEY: [subnet.to_reference_json() for subnet in self.subnets.all()]
            }
        }

    def to_json_body(self):
        return {
            "name": self.name,
            "is_default": self.is_default,
            "cidr": self.cidr,
            "zone": {"name": self.zone},
        }

    @classmethod
    def from_ibm_json_body(cls, json_body):
        return cls(
            name=json_body["name"], cidr=json_body["cidr"],
            resource_id=json_body["id"], is_default=json_body["is_default"], href=json_body["href"],
            created_at=datetime.strptime(json_body["created_at"], CREATED_AT_FORMAT),
            has_subnets=json_body["has_subnets"]
        )

    def dis_params_eq(self, other):
        assert isinstance(other, self.__class__)

        return (self.name == other.name and self.resource_id == other.resource_id and
                self.is_default == other.is_default and self.status == other.status)

    def dis_add_update_db(self, session, db_address_prefix, db_cloud, db_vpc_network, db_zone):
        existing = db_address_prefix or None
        try:
            if not existing:
                self.ibm_cloud = db_cloud
                self.vpc_network = db_vpc_network
                self.zone = db_zone
                session.add(self)
                session.commit()
                return
        except orm.exc.ObjectDeletedError as ex:
            LOGGER.warning(ex)
            return

        try:
            if not self.dis_params_eq(existing):
                existing.update_from_object(self)
                existing.vpc_network = db_vpc_network
                existing.zone = db_zone
        except orm.exc.ObjectDeletedError as ex:
            LOGGER.warning(ex)

        session.commit()

    def update_from_object(self, other):
        assert isinstance(other, self.__class__)

        self.name = other.name
        self.status = other.status
        self.is_default = other.is_default
        self.resource_id = other.resource_id
