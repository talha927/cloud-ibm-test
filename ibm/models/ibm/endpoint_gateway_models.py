import uuid
from datetime import datetime

from sqlalchemy import Column, DateTime, Enum, ForeignKey, JSON, PrimaryKeyConstraint, String, Table, Text
from sqlalchemy.orm import backref, relationship

from ibm.common.utils import return_datetime_object
from ibm.models.base import Base
from ibm.models.ibm.mixins import IBMRegionalResourceMixin
from ibm.models.ibm.subnet_models import IBMSubnetReservedIp

ibm_endpoint_gateways_security_groups = Table(
    "ibm_endpoint_gateways_security_groups", Base.metadata,
    Column("security_group_id", String(32), ForeignKey("ibm_security_groups.id", ondelete="CASCADE")),
    Column("endpoint_gateway_id", String(32), ForeignKey("ibm_endpoint_gateways.id", ondelete="CASCADE")),
    PrimaryKeyConstraint("security_group_id", "endpoint_gateway_id"),
)


class IBMEndpointGateway(IBMRegionalResourceMixin, Base):
    ID_KEY = "id"
    NAME_KEY = "name"
    HREF_KEY = "href"
    CRN_KEY = "crn"
    CREATED_AT_KEY = "created_at"
    HEALTH_STATE_KEY = "health_state"
    LIFECYCLE_STATE_KEY = "lifecycle_state"
    RESOURCE_TYPE_KEY = "resource_type"
    VPC_KEY = "vpc"
    RESOURCE_GROUP_KEY = "resource_group"
    SERVICE_ENDPOINTS_KEY = "service_endpoints"
    RESERVED_IPS_KEY = "reserved_ips"
    SECURITY_GROUPS_KEY = "security_groups"
    TARGET_KEY = "target"

    # health state consts
    HEALTH_STATE_OK = "ok"
    HEALTH_STATE_DEGRADED = "degraded"
    HEALTH_STATE_FAULTED = "faulted"
    HEALTH_STATE_INAPPLICABLE = "inapplicable"

    HEALTH_STATES_LIST = [HEALTH_STATE_OK, HEALTH_STATE_DEGRADED, HEALTH_STATE_FAULTED, HEALTH_STATE_INAPPLICABLE]

    # lifecycle state consts
    STATE_DELETING = "deleting"
    STATE_FAILED = "failed"
    STATE_PENDING = "pending"
    STATE_STABLE = "stable"
    STATE_UPDATING = "updating"
    STATE_WAITING = "waiting"
    STATE_SUSPENDED = "suspended"
    LIFECYCLE_STATES_LIST = [
        STATE_DELETING, STATE_FAILED, STATE_PENDING, STATE_STABLE, STATE_UPDATING, STATE_WAITING, STATE_SUSPENDED]

    CRZ_BACKREF_NAME = "endpoint_gateways"

    # resource type
    RESOURCE_TYPE_ENDPOINT_GATEWAY = "endpoint_gateway"

    __tablename__ = "ibm_endpoint_gateways"

    id = Column(String(32), primary_key=True)
    created_at = Column(DateTime, default=datetime.utcnow(), nullable=False)
    crn = Column(Text, nullable=False)
    health_state = Column(String(50), nullable=False)
    href = Column(Text, nullable=False)
    resource_id = Column(String(64), nullable=False)
    lifecycle_state = Column(String(50), nullable=False)
    name = Column(String(255), nullable=False)
    resource_type = Column(Enum(RESOURCE_TYPE_ENDPOINT_GATEWAY), nullable=False)
    service_endpoints = Column(JSON, nullable=False)

    resource_group_id = Column(String(32), ForeignKey("ibm_resource_groups.id", ondelete="CASCADE"))
    vpc_id = Column(String(32), ForeignKey("ibm_vpc_networks.id", ondelete="CASCADE"))

    target = relationship('IBMEndpointGatewayTarget', backref='endpoint_gateway', uselist=False,
                          cascade="all, delete-orphan", passive_deletes=True)

    reserved_ips = relationship('IBMSubnetReservedIp', backref='endpoint_gateway', cascade="all, delete-orphan",
                                lazy="dynamic", passive_deletes=True)

    security_groups = relationship(
        "IBMSecurityGroup", secondary=ibm_endpoint_gateways_security_groups, lazy="dynamic",
        backref=backref("endpoint_gateways", lazy="dynamic", cascade="all,delete", passive_deletes=True)
    )

    def __init__(self, created_at, crn, health_state, href, resource_id, lifecycle_state, name,
                 resource_type, service_endpoints):
        self.id = str(uuid.uuid4().hex)
        self.created_at = created_at
        self.crn = crn
        self.health_state = health_state
        self.href = href
        self.resource_id = resource_id
        self.lifecycle_state = lifecycle_state
        self.name = name
        self.resource_type = resource_type
        self.service_endpoints = service_endpoints

    def to_reference_json(self):
        return {
            self.ID_KEY: self.id,
            self.NAME_KEY: self.name,
        }

    def to_json(self):
        return {
            self.ID_KEY: self.id,
            self.NAME_KEY: self.name,
            self.HREF_KEY: self.href,
            self.CRN_KEY: self.crn,
            self.CREATED_AT_KEY: self.created_at,
            self.HEALTH_STATE_KEY: self.health_state,
            self.LIFECYCLE_STATE_KEY: self.lifecycle_state,
            self.RESOURCE_TYPE_KEY: self.resource_type,
            self.VPC_KEY: self.vpc_network.to_reference_json(),
            self.REGION_KEY: self.region.to_reference_json(),
            self.IBM_CLOUD_KEY: self.ibm_cloud.to_reference_json(),
            self.RESOURCE_GROUP_KEY: self.resource_group.to_reference_json(),
            self.RESERVED_IPS_KEY: [reserved_ip.to_reference_json() for reserved_ip in self.reserved_ips.all()],
            self.TARGET_KEY: self.target.to_json() if self.target else {},
            self.SECURITY_GROUPS_KEY:
                [security_group.to_reference_json() for security_group in self.security_groups.all()],
        }

    @classmethod
    def from_ibm_json_body(cls, json_body):
        endpoint_gateway = cls(
            lifecycle_state=json_body["lifecycle_state"], health_state=json_body["health_state"],
            name=json_body["name"], crn=json_body.get("crn"), href=json_body["href"],
            resource_id=json_body["id"], resource_type=json_body["resource_type"],
            created_at=return_datetime_object(json_body["created_at"]),
            service_endpoints=json_body["service_endpoints"]
        )
        endpoint_gateway.target = IBMEndpointGatewayTarget.from_ibm_json_body(json_body["target"])
        for ip in json_body.get("ips"):
            endpoint_gateway_reserved_ip = IBMSubnetReservedIp.from_ibm_json_body(ip)
            endpoint_gateway.reserved_ips.append(endpoint_gateway_reserved_ip)

        return endpoint_gateway

    def dis_params_eq(self, other):
        assert isinstance(other, self.__class__)

        return (self.crn == other.crn and self.health_state == other.health_state and self.href == other.href and
                self.resource_id == other.resource_id and self.lifecycle_state == other.lifecycle_state and
                self.name == other.name and self.service_endpoints == other.service_endpoints)

    def dis_add_update_db(self, db_session, db_endpoint_gateway, db_cloud, db_resource_group, db_region, db_vpc,
                          db_security_groups, db_reserved_ips):
        if not (db_resource_group and db_vpc and db_security_groups):
            return

        existing = db_endpoint_gateway or None

        if not existing:
            self.ibm_cloud = db_cloud
            self.resource_group = db_resource_group
            self.vpc_network = db_vpc
            self.security_groups = db_security_groups
            self.reserved_ips = db_reserved_ips
            self.region = db_region
            db_session.add(self)
            db_session.commit()
            return

        if not self.dis_params_eq(existing):
            existing.update_from_object(self)
            existing.resource_group = db_resource_group
            existing.vpc_network = db_vpc
            existing.security_groups = db_security_groups
            existing.reserved_ips = db_reserved_ips
            existing.region = db_region

        db_session.commit()

    def update_from_object(self, other):
        assert isinstance(other, self.__class__)

        self.crn = other.crn
        self.health_state = other.health_state
        self.href = other.href
        self.resource_id = other.resource_id
        self.lifecycle_state = other.lifecycle_state
        self.name = other.name
        self.service_endpoints = other.service_endpoints


class IBMEndpointGatewayTarget(Base):
    ID_KEY = "id"
    NAME_KEY = "name"
    CRN_KEY = "crn"
    RESOURCE_TYPE_KEY = "crn"

    RESOURCE_TYPE_PROVIDER_INFRASTRUCTURE_SERVICE = "provider_infrastructure_service"
    RESOURCE_TYPE_PROVIDER_CLOUD_SERVICE = "provider_cloud_service"
    RESOURCE_TYPES_LIST = [RESOURCE_TYPE_PROVIDER_INFRASTRUCTURE_SERVICE, RESOURCE_TYPE_PROVIDER_CLOUD_SERVICE]

    __tablename__ = "ibm_endpoint_gateway_targets"

    id = Column(String(32), primary_key=True)
    resource_type = Column(Enum(*RESOURCE_TYPES_LIST), nullable=False)
    name = Column(String(255))
    crn = Column(Text)

    endpoint_gateway_id = Column(String(32), ForeignKey("ibm_endpoint_gateways.id", ondelete="CASCADE"))

    def __init__(self, resource_type, name=None, crn=None):
        self.id = str(uuid.uuid4().hex)
        self.resource_type = resource_type
        self.crn = crn
        self.name = name

    def to_json(self):
        return {
            self.ID_KEY: self.id,
            self.NAME_KEY: self.name,
            self.CRN_KEY: self.crn,
            self.RESOURCE_TYPE_KEY: self.resource_type,
        }

    @classmethod
    def from_ibm_json_body(cls, json_body):
        return IBMEndpointGatewayTarget(
            name=json_body.get("name"), crn=json_body.get("crn"),
            resource_type=json_body["resource_type"]
        )
