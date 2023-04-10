import logging
import uuid
from datetime import datetime

from sqlalchemy import BigInteger, Boolean, Column, DateTime, Enum, Float, ForeignKey, Integer, JSON, \
    PrimaryKeyConstraint, String, Table, Text
from sqlalchemy.orm import backref, relationship
from sqlalchemy.schema import UniqueConstraint

from ibm.common.consts import (
    DUMMY_CLOUD_ID, DUMMY_CLOUD_NAME, DUMMY_REGION_ID,
    DUMMY_REGION_NAME, DUMMY_RESOURCE_GROUP_ID, DUMMY_RESOURCE_GROUP_NAME
)
from ibm.common.utils import return_datetime_object
from ibm.models.base import Base
from ibm.models.ibm.mixins import IBMRegionalResourceMixin

ibm_load_balancer_subnets = Table(
    "ibm_load_balancer_subnets", Base.metadata,
    Column("load_balancer_id", String(32), ForeignKey("ibm_load_balancers.id", ondelete="CASCADE")),
    Column("subnets_id", String(32), ForeignKey("ibm_subnets.id", ondelete="CASCADE")),
    PrimaryKeyConstraint("load_balancer_id", "subnets_id"),
)


class LBCommonConsts:
    # PROVISIONING_STATUSES
    PROVISIONING_STATUS_ACTIVE = "active"
    PROVISIONING_STATUS_CREATE_PENDING = "create_pending"
    PROVISIONING_STATUS_DELETE_PENDING = "delete_pending"
    PROVISIONING_STATUS_FAILED = "failed"
    PROVISIONING_STATUS_UPDATE_PENDING = "update_pending"

    # PROTOCOL_TYPES
    PROTOCOL_HTTPS = "https"
    PROTOCOL_HTTP = "http"
    PROTOCOL_TCP = "tcp"

    ALL_STATUSES_LIST = [
        PROVISIONING_STATUS_ACTIVE, PROVISIONING_STATUS_CREATE_PENDING, PROVISIONING_STATUS_DELETE_PENDING,
        PROVISIONING_STATUS_FAILED, PROVISIONING_STATUS_UPDATE_PENDING]

    ALL_PROTOCOLS_LIST = [PROTOCOL_HTTPS, PROTOCOL_HTTP, PROTOCOL_TCP]


ibm_load_balancers_security_groups = Table(
    "ibm_load_balancers_security_groups", Base.metadata,
    Column("load_balancer_id", String(32), ForeignKey("ibm_load_balancers.id", ondelete="CASCADE")),
    Column("security_group_id", String(32), ForeignKey("ibm_security_groups.id", ondelete="CASCADE")),
    PrimaryKeyConstraint("load_balancer_id", "security_group_id")
)


class IBMLoadBalancer(IBMRegionalResourceMixin, Base):
    ID_KEY = "id"
    CREATED_AT_KEY = "created_at"
    NAME_KEY = "name"
    IS_PUBLIC_KEY = "is_public"
    RESOURCE_ID_KEY = "resource_id"
    HOSTNAME_KEY = "hostname"
    PRIVATE_IPS_KEY = "private_ips"
    PUBLIC_IPS_KEY = "public_ips"
    HREF_KEY = "href"
    CRN_KEY = "crn"
    LOGGING_DATAPATH_ACTIVE_KEY = "logging_datapath_active"
    ROUTE_MODE_KEY = "route_mode"
    OPERATING_STATUS_KEY = "operating_status"
    SECURITY_GROUPS_SUPPORTED_KEY = "security_groups_supported"
    PROVISIONING_STATUS_KEY = "provisioning_status"
    RESOURCE_GROUP_KEY = "resource_group"
    PROFILE_KEY = "profile"
    FAMILY_KEY = "family"
    SECURITY_GROUPS_KEY = "security_groups"
    LISTENERS_KEY = "listeners"
    POOLS_KEY = "pools"
    SUBNETS_KEY = "subnets"
    STATISTICS_KEY = "statistics"
    VPC_KEY = "vpc"
    ASSOCIATED_RESOURCES_KEY = "associated_resources"
    INSTANCE_GROUPS_KEY = "instance_groups"
    RESOURCE_JSON_KEY = "resource_json"
    RESOURCE_TYPE_LOAD_BALANCER_KEY = "Load Balancer"

    CRZ_BACKREF_NAME = "load_balancers"

    RESOURCE_TYPE_LOAD_BALANCER = "load_balancer"

    PROVISIONING_STATUS_ACTIVE = "active"
    PROVISIONING_STATUS_CREATE_PENDING = "create_pending"
    PROVISIONING_STATUS_DELETE_PENDING = "delete_pending"
    PROVISIONING_STATUS_FAILED = "failed"
    PROVISIONING_STATUS_MAINTENANCE_PENDING = "maintenance_pending"
    PROVISIONING_STATUS_UPDATE_PENDING = "update_pending"
    PROVISIONING_STATUS_MIGRATE_PENDING = "migrate_pending"
    ALL_LB_STATUSES_LIST = [
        PROVISIONING_STATUS_ACTIVE, PROVISIONING_STATUS_CREATE_PENDING, PROVISIONING_STATUS_DELETE_PENDING,
        PROVISIONING_STATUS_FAILED, PROVISIONING_STATUS_MAINTENANCE_PENDING, PROVISIONING_STATUS_UPDATE_PENDING,
        PROVISIONING_STATUS_MIGRATE_PENDING
    ]

    # OPERATING_STATUSES
    OPERATING_STATUS_OFFLINE = "offline"
    OPERATING_STATUS_ONLINE = "online"
    ALL_OPERATING_STATUSES = [OPERATING_STATUS_ONLINE, OPERATING_STATUS_OFFLINE]

    __tablename__ = "ibm_load_balancers"

    id = Column(String(32), primary_key=True)
    created_at = Column(DateTime, default=datetime.utcnow(), nullable=False)
    name = Column(String(255), nullable=False)
    is_public = Column(Boolean, nullable=False)
    resource_id = Column(String(64), nullable=False)
    hostname = Column(String(64), nullable=False)
    private_ips = Column(JSON, nullable=False)
    public_ips = Column(JSON, nullable=False)
    href = Column(Text, nullable=False)
    crn = Column(String(500), nullable=False)
    logging_datapath_active = Column(Boolean, nullable=False)
    route_mode = Column(Boolean, nullable=False)
    operating_status = Column(Enum(*ALL_OPERATING_STATUSES), nullable=False)
    security_groups_supported = Column(Boolean, nullable=False)
    provisioning_status = Column(String(50), nullable=False)

    resource_group_id = Column(String(32), ForeignKey("ibm_resource_groups.id", ondelete="CASCADE"))
    load_balancer_profile_id = Column(String(32), ForeignKey("ibm_load_balancer_profiles.id", ondelete="CASCADE"))

    security_groups = relationship(
        "IBMSecurityGroup", secondary=ibm_load_balancers_security_groups, lazy="dynamic",
        backref=backref("load_balancers", lazy="dynamic")
    )
    listeners = relationship("IBMListener", backref="load_balancer", cascade="all, delete-orphan", passive_deletes=True,
                             lazy="dynamic")
    pools = relationship("IBMPool", backref="load_balancer", cascade="all, delete-orphan", passive_deletes=True,
                         lazy="dynamic")
    subnets = relationship(
        "IBMSubnet", secondary=ibm_load_balancer_subnets, lazy="dynamic",
        backref=backref("load_balancers", lazy="dynamic")
    )
    statistics = relationship(
        "IBMLoadBalancerStatistics", backref="load_balancer", cascade="all, delete-orphan", passive_deletes=True,
        uselist=False
    )
    instance_groups = relationship(
        "IBMInstanceGroup",
        backref="load_balancer",
        cascade="all, delete-orphan",
        passive_deletes=True,
        lazy="dynamic"
    )

    __table_args__ = (
        UniqueConstraint(name, "cloud_id", "region_id", name="uix_ibm_lb_name_cloud_id_region_id"),
    )

    def __init__(
            self, name, is_public, resource_id, host_name, private_ips, public_ips, href, crn,
            logging_datapath_active, route_mode, operating_status, security_groups_supported, provisioning_status,
            created_at, cloud_id=None, resource_group_id=None
    ):
        self.id = str(uuid.uuid4().hex)
        self.created_at = created_at
        self.name = name
        self.is_public = is_public
        self.resource_id = resource_id
        self.hostname = host_name
        self.private_ips = private_ips
        self.public_ips = public_ips
        self.href = href
        self.crn = crn
        self.logging_datapath_active = logging_datapath_active
        self.route_mode = route_mode
        self.operating_status = operating_status
        self.security_groups_supported = security_groups_supported
        self.provisioning_status = provisioning_status
        self.cloud_id = cloud_id
        self.resource_group_id = resource_group_id

    def to_reference_json(self):
        return {
            self.ID_KEY: self.id,
            self.NAME_KEY: self.name,
            self.HOSTNAME_KEY: self.hostname,
        }

    def validate_json_for_schema(self):
        return {
            self.ID_KEY: self.id,
            self.RESOURCE_JSON_KEY: {
                self.NAME_KEY: self.name,
                self.HOSTNAME_KEY: self.hostname,
            }
        }

    @property
    def family(self):
        return self.load_balancer_profile.family

    @property
    def associated_resources(self):
        subnet_or_sec_group = self.subnets.first() or self.security_groups.first()
        json_data = {
            self.VPC_KEY: {},
            self.SUBNETS_KEY: [subnet.to_reference_json() for subnet in self.subnets.all()],
            self.SECURITY_GROUPS_KEY: [sec_grp.to_reference_json() for sec_grp in self.security_groups.all()]
        }
        if subnet_or_sec_group:
            json_data[self.VPC_KEY] = subnet_or_sec_group.vpc_network.to_reference_json()

        return json_data

    def to_json(self):
        return {
            self.ID_KEY: self.id,
            self.CREATED_AT_KEY: self.created_at,
            self.NAME_KEY: self.name,
            self.IS_PUBLIC_KEY: self.is_public,
            self.RESOURCE_ID_KEY: self.resource_id,
            self.HOSTNAME_KEY: self.hostname,
            self.PRIVATE_IPS_KEY: self.private_ips,
            self.PUBLIC_IPS_KEY: self.public_ips,
            self.HREF_KEY: self.href,
            self.CRN_KEY: self.crn,
            self.LOGGING_DATAPATH_ACTIVE_KEY: self.logging_datapath_active,
            self.ROUTE_MODE_KEY: self.route_mode,
            self.OPERATING_STATUS_KEY: self.operating_status,
            self.SECURITY_GROUPS_SUPPORTED_KEY: self.security_groups_supported,
            self.PROVISIONING_STATUS_KEY: self.provisioning_status,
            self.PROFILE_KEY: self.load_balancer_profile.to_reference_json(),
            self.LISTENERS_KEY: [listener.to_json() for listener in self.listeners.all()],
            self.POOLS_KEY: [pool.to_json() for pool in self.pools.all()],
            self.INSTANCE_GROUPS_KEY: [instance_group.to_json() for instance_group in self.instance_groups.all()],
            # self.STATISTICS_KEY: self.statistics.to_json(),
            self.IBM_CLOUD_KEY: self.ibm_cloud.to_reference_json(),
            self.RESOURCE_GROUP_KEY: self.resource_group.to_reference_json(),
            self.REGION_KEY: self.region.to_reference_json(),
            self.ASSOCIATED_RESOURCES_KEY: self.associated_resources,
        }

    @property
    def __application_profile(self):
        from ibm import get_db_session
        from ibm.models import IBMLoadBalancerProfile
        with get_db_session() as db_session:
            profile = db_session.query(IBMLoadBalancerProfile).filter_by(family="Application").first()
            if not profile:
                logging.warning("""
                Please sync the load_balancer profiles first.
                1. POST SERVER_URL/v1/ibm/load_balancer/profiles/sync
                2. GET SERVER_URL/v1/ibm/load_balancer/profiles
                """)
            return profile

    def from_softlayer_to_ibm_json(self):
        return {
            self.IBM_CLOUD_KEY: {
                self.ID_KEY: DUMMY_CLOUD_ID,
                self.NAME_KEY: DUMMY_CLOUD_NAME
            },
            self.REGION_KEY: {
                self.ID_KEY: DUMMY_REGION_ID,
                self.NAME_KEY: DUMMY_REGION_NAME
            },
            self.ID_KEY: self.id,
            "resource_json": {
                self.IS_PUBLIC_KEY: self.is_public,
                self.HOSTNAME_KEY: self.hostname,
                self.NAME_KEY: self.name,
                self.LISTENERS_KEY: [listener.from_softlayer_to_ibm_json() for listener in self.listeners.all()],
                self.POOLS_KEY: [pool.from_softlayer_to_ibm_json() for pool in self.pools.all()],
                self.PROFILE_KEY: {
                    self.ID_KEY: self.__application_profile.id,
                    self.NAME_KEY: self.__application_profile.name,
                    self.FAMILY_KEY: self.__application_profile.family,
                },
                self.RESOURCE_GROUP_KEY: {
                    self.ID_KEY: DUMMY_RESOURCE_GROUP_ID,
                    self.NAME_KEY: DUMMY_RESOURCE_GROUP_NAME
                },
                self.SECURITY_GROUPS_KEY: [s_grp.to_reference_json() for s_grp in self.security_groups.all()],
                self.SUBNETS_KEY: [{"id": subnet.id, "name": subnet.name} for subnet in self.subnets.all()]
            }
        }

    def to_json_body(self):
        return {
            "resource_group": {
                "id": self.ibm_resource_group.resource_id if self.ibm_resource_group else ""
            },
            "name": self.name,
            "is_public": self.is_public,
            "profile": {"name": self.load_balancer_profile.name} if self.load_balancer_profile else "",
            "subnets": [subnet.to_reference_json() for subnet in self.subnets.all()],
            "listeners": [listener.to_json_body() for listener in self.listeners.all()],
            "pools": [pool.to_json_body() for pool in self.pools.all()],
        }

    @classmethod
    def from_ibm_json_body(cls, json_body):
        logging_datapath_active = \
            json_body["logging"]["datapath"]["active"] if json_body["logging"].get("datapath") else False
        ibm_load_balancer = cls(
            name=json_body["name"],
            is_public=json_body["is_public"],
            resource_id=json_body["id"],
            host_name=json_body["hostname"],
            route_mode=json_body["route_mode"],
            private_ips=json_body["private_ips"],
            public_ips=json_body["public_ips"],
            href=json_body["href"],
            crn=json_body["crn"],
            logging_datapath_active=logging_datapath_active,
            operating_status=json_body["operating_status"],
            security_groups_supported=json_body["security_group_supported"],
            provisioning_status=json_body["provisioning_status"],
            created_at=return_datetime_object(json_body["created_at"])
        )

        return ibm_load_balancer

    def dis_params_eq(self, other):
        assert isinstance(other, self.__class__)

        return (
                self.name == other.name
                and self.is_public == other.is_public
                and self.resource_id == other.resource_id
                and self.hostname == other.hostname
                and self.private_ips == other.private_ips
                and self.public_ips == other.public_ips
                and self.href == other.href
                and self.crn == other.crn
                and self.logging_datapath_active == other.logging_datapath_active
                and self.route_mode == other.route_mode
                and self.operating_status == other.operating_status
                and self.security_groups_supported == other.security_groups_supported
                and self.provisioning_status == other.provisioning_status
        )

    def dis_add_update_db(self, session, db_load_balancers, db_cloud, db_resource_group, db_vpc_network, db_subnets,
                          db_region, db_lb_profile):
        if not (db_resource_group and db_lb_profile):
            return

        db_load_balancers_id_obj_dict = dict()
        db_load_balancers_name_obj_dict = dict()
        for db_load_balancer in db_load_balancers:
            db_load_balancers_id_obj_dict[db_load_balancer.resource_id] = db_load_balancer
            db_load_balancers_name_obj_dict[db_load_balancer.name] = db_load_balancer

        if self.resource_id not in db_load_balancers_id_obj_dict and self.name in db_load_balancers_name_obj_dict:
            # Creation Pending / Creating
            existing = db_load_balancers_name_obj_dict[self.name]
        elif self.resource_id in db_load_balancers_id_obj_dict:
            # Created. Update everything including name
            existing = db_load_balancers_id_obj_dict[self.resource_id]
        else:
            existing = None

        if not existing:
            self.ibm_cloud = db_cloud
            self.resource_group = db_resource_group
            self.vpc_network = db_vpc_network
            self.load_balancer_profile = db_lb_profile
            self.region = db_region
            for db_subnet in db_subnets:
                self.subnets.append(db_subnet)
            session.add(self)
            session.commit()
            return

        if not self.dis_params_eq(existing):
            existing.update_from_object(self)

            existing.resource_group = db_resource_group
            existing.vpc_network = db_vpc_network
            existing.load_balancer_profile = db_lb_profile
            existing.region = db_region

            associated_subnet_ids = [associated_subnet.resource_id for associated_subnet in existing.subnets.all()]
            for db_subnet in db_subnets:
                if db_subnet.resource_id not in associated_subnet_ids:
                    existing.subnets.append(db_subnet)

        session.commit()

    def update_from_object(self, other):
        assert isinstance(other, self.__class__)

        self.name = other.name
        self.is_public = other.is_public
        self.resource_id = other.resource_id
        self.hostname = other.hostname
        self.private_ips = other.private_ips
        self.public_ips = other.public_ips
        self.href = other.href
        self.crn = other.crn
        self.logging_datapath_active = other.logging_datapath_active
        self.route_mode = other.route_mode
        self.operating_status = other.operating_status
        self.security_groups_supported = other.security_groups_supported
        self.provisioning_status = other.provisioning_status


class IBMLoadBalancerStatistics(Base):
    ID_KEY = "id"
    ACTIVE_CONNECTIONS_KEY = "active_connections"
    CONNECTION_RATE_KEY = "connection_rate"
    DATA_PROCESSED_THIS_MONTH_KEY = "data_processed_this_month"
    THROUGHPUT_KEY = "throughput"

    __tablename__ = "ibm_load_balancer_statistics"

    id = Column(String(32), primary_key=True)
    active_connections = Column(BigInteger, nullable=False)
    connection_rate = Column(Float, nullable=False)
    data_processed_this_month = Column(BigInteger, nullable=False)
    throughput = Column(Float, nullable=False)

    load_balancer_id = Column(String(32), ForeignKey("ibm_load_balancers.id", ondelete="CASCADE"))

    def __init__(self, active_connections, connection_rate, data_processed_this_month, throughput):
        self.id = str(uuid.uuid4().hex)
        self.active_connections = active_connections
        self.connection_rate = connection_rate
        self.data_processed_this_month = data_processed_this_month
        self.throughput = throughput

    def to_json(self):
        return {
            self.ID_KEY: self.id,
            self.ACTIVE_CONNECTIONS_KEY: self.active_connections,
            self.CONNECTION_RATE_KEY: self.connection_rate,
            self.DATA_PROCESSED_THIS_MONTH_KEY: self.data_processed_this_month,
            self.THROUGHPUT_KEY: self.throughput
        }

    @classmethod
    def from_ibm_json_body(cls, json_body):
        return cls(
            active_connections=json_body["active_connections"], connection_rate=json_body["connection_rate"],
            data_processed_this_month=json_body["data_processed_this_month"], throughput=json_body["throughput"]
        )


class IBMLoadBalancerProfile(Base):
    ID_KEY = "id"
    NAME_KEY = "name"
    HREF_KEY = "href"
    REGION_KEY = "region"
    TYPE_KEY = "type"
    VALUE_KEY = "value"
    LOGGING_SUPPORTED_KEY = "logging_supported"
    FAMILY_KEY = "family"
    ROUTE_MODE_SUPPORTED_KEY = "route_mode_supported"
    SECURITY_GROUPS_SUPPORTED_KEY = "security_groups_supported"
    LOAD_BALANCERS_KEY = "load_balancers"

    # SUPPORTED CONSTANTS
    SUPPORTED_TYPE_FIXED = "fixed"
    SUPPORTED_TYPE_DEPENDENT = "dependent"

    __tablename__ = "ibm_load_balancer_profiles"

    id = Column(String(32), primary_key=True)
    name = Column(String(255), nullable=False, unique=True)
    href = Column(Text, nullable=False)
    family = Column(String(255), nullable=False)
    logging_supported_type = Column(Enum(SUPPORTED_TYPE_FIXED), default=SUPPORTED_TYPE_FIXED, nullable=False)
    logging_supported_value = Column(JSON, nullable=False)
    route_mode_supported_type = Column(Enum(SUPPORTED_TYPE_FIXED, SUPPORTED_TYPE_DEPENDENT), nullable=False)
    route_mode_supported_value = Column(Boolean)
    security_groups_supported_type = Column(Enum(SUPPORTED_TYPE_FIXED, SUPPORTED_TYPE_DEPENDENT), nullable=True)
    security_groups_supported_value = Column(Boolean)

    load_balancers = relationship(
        "IBMLoadBalancer", backref="load_balancer_profile", cascade="all, delete-orphan", passive_deletes=True,
        lazy="dynamic"
    )

    def __init__(
            self, name, href, family, logging_supported, route_mode_supported, security_groups_supported=None):
        self.id = str(uuid.uuid4().hex)
        self.name = name
        self.href = href
        self.family = family
        self.logging_supported = logging_supported
        self.route_mode_supported = route_mode_supported
        self.security_groups_supported = security_groups_supported

    @property
    def logging_supported(self):
        return {
            self.TYPE_KEY: self.logging_supported_type,
            self.VALUE_KEY: self.logging_supported_value,
        }

    @logging_supported.setter
    def logging_supported(self, new_logging_supported):
        self.logging_supported_type = new_logging_supported['type'].lower()
        self.logging_supported_value = new_logging_supported['value']

    @property
    def route_mode_supported(self):
        return {
            self.TYPE_KEY: self.route_mode_supported_type,
            self.VALUE_KEY: self.route_mode_supported_value,
        }

    @route_mode_supported.setter
    def route_mode_supported(self, new_route_mode_supported):
        self.route_mode_supported_type = new_route_mode_supported['type'].lower()
        self.route_mode_supported_value = new_route_mode_supported.get("value", None)

    @property
    def security_groups_supported(self):
        return {
            self.TYPE_KEY: self.security_groups_supported_type,
            self.VALUE_KEY: self.security_groups_supported_value,
        }

    @security_groups_supported.setter
    def security_groups_supported(self, new_security_groups_supported):
        if new_security_groups_supported:
            self.security_groups_supported_type = new_security_groups_supported['type']
            self.security_groups_supported_value = new_security_groups_supported.get("value", None)

    def to_reference_json(self):
        return {
            self.ID_KEY: self.id,
            self.NAME_KEY: self.name,
            self.FAMILY_KEY: self.family
        }

    def to_json(self):
        return {
            self.ID_KEY: self.id,
            self.NAME_KEY: self.name,
            self.HREF_KEY: self.href,
            self.FAMILY_KEY: self.family,
            self.LOGGING_SUPPORTED_KEY: self.logging_supported,
            self.ROUTE_MODE_SUPPORTED_KEY: self.route_mode_supported,
            self.SECURITY_GROUPS_SUPPORTED_KEY: self.security_groups_supported
        }

    @classmethod
    def from_ibm_json_body(cls, json_body):
        return cls(
            name=json_body["name"], href=json_body["href"], family=json_body["family"],
            logging_supported=json_body["logging_supported"],
            route_mode_supported=json_body["route_mode_supported"],
            security_groups_supported=json_body.get("security_groups_supported"),
        )

    def dis_params_eq(self, other):
        assert isinstance(other, self.__class__)

        return (self.name == other.name and self.href == other.href and
                self.family == other.family and self.logging_supported == other.logging_supported and
                self.route_mode_supported == other.route_mode_supported and
                self.security_groups_supported == other.security_groups_supported)

    def dis_add_update_db(self, db_session, db_load_balancer_profiles):
        db_load_balancer_profiles_name_obj_dict = dict()
        for db_load_balancer_profile in db_load_balancer_profiles:
            db_load_balancer_profiles_name_obj_dict[db_load_balancer_profile.name] = db_load_balancer_profile

        if self.name in db_load_balancer_profiles_name_obj_dict:
            # Creation Pending / Creating
            existing = db_load_balancer_profiles_name_obj_dict[self.name]
        else:
            existing = None

        if not existing:
            db_session.add(self)
            db_session.commit()
            return

        if not self.dis_params_eq(existing):
            existing.update_from_obj(self)

        db_session.commit()

    def update_from_obj(self, updated_obj):
        self.name = updated_obj.name
        self.href = updated_obj.href
        self.family = updated_obj.family
        self.logging_supported = updated_obj.logging_supported
        self.route_mode_supported = updated_obj.route_mode_supported
        self.security_groups_supported = updated_obj.security_groups_supported


class IBMListener(IBMRegionalResourceMixin, Base, LBCommonConsts):
    ID_KEY = "id"
    RESOURCE_ID_KEY = "resource_id"
    PORT_KEY = "port"
    PROTOCOL_KEY = "protocol"
    CERTIFICATE_INSTANCE_CRN_KEY = "certificate_instance_crn"
    PROVISIONING_STATUS_KEY = "provisioning_status"
    ACCEPT_PROXY_PROTOCOL_KEY = "accept_proxy_protocol"
    CONNECTION_LIMIT_KEY = "connection_limit"
    HREF_KEY = "href"
    DEFAULT_POOL_KEY = "default_pool"
    POLICIES_KEY = "policies"
    LOAD_BALANCER_KEY = "load_balancer"

    CRZ_BACKREF_NAME = "listeners"

    __tablename__ = "ibm_listeners"
    id = Column(String(32), primary_key=True)
    resource_id = Column(String(64), nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow(), nullable=False)
    href = Column(Text, nullable=False)
    port = Column(Integer, nullable=False)
    accept_proxy_protocol = Column(Boolean, nullable=False)
    protocol = Column(
        Enum(LBCommonConsts.PROTOCOL_HTTPS, LBCommonConsts.PROTOCOL_HTTP, LBCommonConsts.PROTOCOL_TCP),
        nullable=False
    )
    provisioning_status = Column(String(50), nullable=False)
    # TODO: This field may change to a relationship
    certificate_instance_crn = Column(String(300))
    connection_limit = Column(Integer)

    load_balancer_id = Column(String(32), ForeignKey("ibm_load_balancers.id", ondelete="CASCADE"))
    pool_id = Column(String(32), ForeignKey("ibm_pools.id", ondelete="SET NULL"), nullable=True)

    https_redirect = relationship(
        "IBMListenerAndPolicyCommon", backref="listener", cascade="all, delete-orphan", passive_deletes=True,
        uselist=False
    )
    policies = relationship("IBMListenerPolicy", backref="listener", cascade="all, delete-orphan", passive_deletes=True,
                            lazy="dynamic")

    def __init__(self, resource_id, port, protocol, href, connection_limit=None, certificate_instance_crn=None,
                 provisioning_status=None, accept_proxy_protocol=None, created_at=None):
        self.id = str(uuid.uuid4().hex)
        self.resource_id = resource_id
        self.port = port
        self.protocol = protocol
        self.href = href
        self.connection_limit = connection_limit
        self.certificate_instance_crn = certificate_instance_crn
        self.provisioning_status = provisioning_status
        self.accept_proxy_protocol = accept_proxy_protocol
        self.created_at = created_at

    def to_reference_json(self):
        return {
            self.ID_KEY: self.id,
            self.PROTOCOL_KEY: self.protocol,
            self.PORT_KEY: self.port,
        }

    def from_softlayer_to_ibm_json(self):
        json_data = {
            self.DEFAULT_POOL_KEY: self.default_pool.to_reference_json() if self.default_pool else None,
            self.PORT_KEY: self.port,
            self.PROTOCOL_KEY: self.protocol
        }

        return json_data

    def to_json(self, parent_reference=True):
        json_data = {
            self.ID_KEY: self.id,
            self.PORT_KEY: self.port,
            self.PROTOCOL_KEY: self.protocol,
            self.PROVISIONING_STATUS_KEY: self.provisioning_status,
            self.CERTIFICATE_INSTANCE_CRN_KEY: self.certificate_instance_crn if self.certificate_instance_crn else "",
            self.CONNECTION_LIMIT_KEY: self.connection_limit,
            self.HREF_KEY: self.href,
            self.ACCEPT_PROXY_PROTOCOL_KEY: self.accept_proxy_protocol,
            self.DEFAULT_POOL_KEY: self.default_pool.to_json() if self.default_pool else "",
            self.POLICIES_KEY: [policy.to_json() for policy in self.policies.all()]
        }
        if parent_reference:
            json_data[self.LOAD_BALANCER_KEY] = self.load_balancer.to_reference_json()

        return json_data

    def to_json_body(self):
        return {
            "protocol": self.protocol,
            "port": self.port,
            "connection_limit": self.connection_limit,
            "certificate_instance": {"crn": self.certificate_instance_crn} if self.certificate_instance_crn else {},
            "accept_proxy_protocol": self.accept_proxy_protocol if self.accept_proxy_protocol else "",
            "default_pool": {"name": self.default_pool.name if self.default_pool else ""},
            "policies": [policy.to_json_body() for policy in self.policies.all()]
        }

    @classmethod
    def from_ibm_json_body(cls, json_body, db_session):
        certificate_instance_crn = \
            json_body["certificate_instance"]["crn"] if "certificate_instance" in json_body else None
        listener = cls(
            resource_id=json_body["id"],
            port=json_body["port"],
            protocol=json_body["protocol"],
            href=json_body["href"],
            connection_limit=json_body.get("connection_limit"),
            certificate_instance_crn=certificate_instance_crn,
            provisioning_status=json_body["provisioning_status"],
            accept_proxy_protocol=json_body["accept_proxy_protocol"],
            created_at=return_datetime_object(json_body["created_at"])
        )
        if json_body.get("https_redirect"):
            listener.https_redirect = IBMListenerAndPolicyCommon.from_ibm_json_body(
                type_="LISTENER", json_body=json_body["https_redirect"], db_session=db_session
            )
        return listener

    @classmethod
    def from_ibm_discovery_json_body(cls, json_body):
        certificate_instance_crn = \
            json_body["certificate_instance"]["crn"] if "certificate_instance" in json_body else None
        return cls(
            resource_id=json_body["id"],
            port=json_body["port"],
            protocol=json_body["protocol"],
            href=json_body["href"],
            connection_limit=json_body.get("connection_limit"),
            certificate_instance_crn=certificate_instance_crn,
            # provisioning_status="active",
            provisioning_status=json_body["provisioning_status"],
            accept_proxy_protocol=json_body["accept_proxy_protocol"],
            created_at=return_datetime_object(json_body["created_at"])
        )

    def dis_params_eq(self, other):
        assert isinstance(other, self.__class__)
        return (self.resource_id == other.resource_id and self.port == other.port and
                self.protocol == other.protocol and self.provisioning_status == other.provisioning_status)

    def dis_add_update_db(self, db_session, db_load_balancer_listeners, db_load_balancer, db_region, db_listener=None,
                          db_pool=None):
        if not db_load_balancer:
            return

        existing = None
        for db_load_balancer_listener in db_load_balancer_listeners:
            assert isinstance(db_load_balancer_listener, self.__class__)
            params_eq = (db_load_balancer_listener.port == self.port and
                         db_load_balancer_listener.protocol == self.protocol and
                         db_load_balancer_listener.connection_limit == self.connection_limit)
            if self.resource_id == db_load_balancer_listener.resource_id:
                existing = db_load_balancer_listener
                break

            elif params_eq:
                existing = db_load_balancer_listener
                break

        if not existing:
            self.load_balancer = db_load_balancer
            self.region = db_region
            if self.https_redirect:
                if db_listener:
                    self.https_redirect.listener = db_listener
                if db_pool:
                    self.https_redirect.pool = db_pool

            db_session.add(self)
            db_session.commit()
            return

        if not self.dis_params_eq(existing):
            existing.update_from_object(self)

            existing.load_balancer = db_load_balancer
            existing.region = db_region

            if existing.https_redirect:
                if db_listener:
                    existing.https_redirect.listener = db_listener
                if db_pool:
                    existing.https_redirect.pool = db_pool

        db_session.commit()

    def update_from_object(self, other):
        assert isinstance(other, self.__class__)

        self.resource_id = other.resource_id
        self.port = other.port
        self.protocol = other.protocol
        self.href = other.href
        self.connection_limit = other.connection_limit
        self.certificate_instance_crn = other.certificate_instance_crn
        self.provisioning_status = other.provisioning_status
        self.accept_proxy_protocol = other.accept_proxy_protocol


class IBMListenerAndPolicyCommon(Base):
    """
    This Class is a common class for both IBMListener and IBMListenerPolicy
    """
    ID_KEY = "id"
    TYPE_KEY = "type"
    HTTP_STATUS_CODE_KEY = "http_status_code"
    URL_KEY = "url"
    URI_KEY = "uri"
    LISTENER_KEY = "listener"
    POLICY_KEY = "policy"
    POOL_KEY = "pool"

    STATUS_CODE_301 = "301"
    STATUS_CODE_302 = "302"
    STATUS_CODE_303 = "303"
    STATUS_CODE_307 = "307"
    STATUS_CODE_308 = "308"

    ALL_STATUS_CODES_LIST = [
        STATUS_CODE_301, STATUS_CODE_302, STATUS_CODE_303, STATUS_CODE_307, STATUS_CODE_308
    ]

    __tablename__ = "ibm_listener_and_policy_common"

    id = Column(String(32), primary_key=True)
    type_ = Column('type', Enum("LISTENER", "POLICY"), nullable=False)
    http_status_code = Column(Enum(*ALL_STATUS_CODES_LIST, nullable=True))
    url = Column(String(1024), nullable=True)
    uri = Column(String(1024), nullable=True)

    listener_id = Column(String(32), ForeignKey("ibm_listeners.id", ondelete="CASCADE"))
    policy_id = Column(String(32), ForeignKey("ibm_lb_listener_policies.id", ondelete="CASCADE"))
    pool_id = Column(String(32), ForeignKey("ibm_pools.id", ondelete="CASCADE"))

    def __init__(self, type_, http_status_code=None, url=None, uri=None):
        self.id = str(uuid.uuid4().hex)
        self.type_ = type_
        self.http_status_code = http_status_code
        self.url = url
        self.uri = uri

    def to_reference_json(self):
        return {
            self.ID_KEY: self.id
        }

    def to_json(self):
        return {
            self.ID_KEY: self.id,
            self.TYPE_KEY: self.type_,
            self.HTTP_STATUS_CODE_KEY: self.http_status_code,
            self.URI_KEY: self.uri,
            self.URL_KEY: self.url
        }

    @classmethod
    def from_ibm_json_body(cls, type_, json_body, db_session):
        assert type_ in ["LISTENER", "POLICY"]
        http_status_code = str(json_body["http_status_code"]) if json_body.get("http_status_code") else None
        obj = cls(
            type_=type_, http_status_code=http_status_code, uri=json_body.get("uri"),
            url=json_body.get("url")
        )
        if "id" in json_body:  # pool_target
            obj.pool = db_session.query(IBMPool).filter_by(resource_id=json_body["id"]).first()
        if "listener" in json_body:  # listener_target
            obj.listener = db_session.query(IBMListener).filter_by(resource_id=json_body["listener"]["id"]).first()

        return obj

    @classmethod
    def from_ibm_discovery_json_body(cls, type_, json_body):
        assert type_ in ["LISTENER", "POLICY"]
        http_status_code = str(json_body["http_status_code"]) if json_body.get("http_status_code") else None
        obj = cls(
            type_=type_, http_status_code=http_status_code, uri=json_body.get("uri"),
            url=json_body.get("url")
        )

        return obj


class IBMListenerPolicy(Base):
    ID_KEY = "id"
    NAME_KEY = "name"
    RESOURCE_ID_KEY = "resource_id"
    PRIORITY_KEY = "priority"
    ACTION_KEY = "action"
    PROVISIONING_STATUS_KEY = "provisioning_status"
    HREF_KEY = "href"
    RULES_KEY = "rules"
    TARGET_KEY = "target"
    LISTENER_KEY = "listener"

    __tablename__ = "ibm_lb_listener_policies"

    # POLICY ACTIONS
    ACTION_FORWARD = "forward"
    ACTION_REDIRECT = "redirect"
    ACTION_REJECT = "reject"
    ACTION_HTTPS_REDIRECT = "https_redirect"

    ALL_ACTIONS_LIST = [
        ACTION_FORWARD, ACTION_REDIRECT, ACTION_REJECT, ACTION_HTTPS_REDIRECT
    ]

    id = Column(String(32), primary_key=True)
    name = Column(String(255), nullable=False)
    resource_id = Column(String(64), nullable=False)
    href = Column(Text, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow(), nullable=False)
    priority = Column(Integer, nullable=False)
    action = Column(Enum(*ALL_ACTIONS_LIST), nullable=False)
    provisioning_status = Column(String(50), nullable=False)

    lb_listener_id = Column(String(32), ForeignKey("ibm_listeners.id", ondelete="CASCADE"))

    rules = relationship("IBMListenerPolicyRule", backref="lb_listener_policy", cascade="all, delete-orphan",
                         passive_deletes=True, lazy="dynamic")
    target = relationship("IBMListenerAndPolicyCommon", backref="policy", cascade="all, delete-orphan",
                          passive_deletes=True, uselist=False)

    def __init__(self, name, action, priority, provisioning_status=None, resource_id=None,
                 created_at=None, href=None):
        self.id = str(uuid.uuid4().hex)
        self.resource_id = resource_id
        self.name = name
        self.action = action
        self.href = href
        self.priority = priority
        self.provisioning_status = provisioning_status
        self.created_at = created_at

    def to_reference_json(self):
        return {
            self.ID_KEY: self.id,
            self.NAME_KEY: self.name
        }

    def to_json_body(self):
        return {
            self.NAME_KEY: self.name,
            self.ACTION_KEY: self.action,
            self.PRIORITY_KEY: self.priority,
            self.RULES_KEY: [rule.to_json_body() for rule in self.rules.all()]
        }

    def to_json(self, parent_reference=True):
        json_data = {
            self.ID_KEY: self.id,
            self.NAME_KEY: self.name,
            self.ACTION_KEY: self.action,
            self.HREF_KEY: self.href,
            self.PRIORITY_KEY: self.priority,
            self.PROVISIONING_STATUS_KEY: self.provisioning_status,
            self.RULES_KEY: [rule.to_json() for rule in self.rules.all()],
            self.TARGET_KEY: self.target.to_json() if self.target else {},
        }
        if parent_reference:
            json_data[self.LISTENER_KEY] = self.listener.to_reference_json()

        return json_data

    @classmethod
    def from_ibm_json_body(cls, json_body, db_session):
        listener_policy = cls(
            name=json_body["name"],
            action=json_body["action"],
            priority=json_body["priority"],
            provisioning_status=json_body["provisioning_status"],
            resource_id=json_body["id"],
            created_at=return_datetime_object(json_body["created_at"]),
            href=json_body["href"],
        )
        if json_body.get("target"):
            listener_policy.target = IBMListenerAndPolicyCommon.from_ibm_json_body(
                type_="POLICY", json_body=json_body["target"], db_session=db_session
            )
        return listener_policy


class IBMListenerPolicyRule(Base, LBCommonConsts):
    """
    URL: https://cloud.ibm.com/apidocs/vpc#create-load-balancer-listener-policy-rule
    """

    ID_KEY = "id"
    NAME_KEY = "name"
    RESOURCE_ID_KEY = "resource_id"
    # STATUS_KEY = "status"
    PROVISIONING_STATUS_KEY = "provisioning_status"
    CONDITION_KEY = "condition"
    CONDITION_VALUE_KEY = "value"
    TYPE_KEY = "type"
    FIELD_KEY = "field"
    HREF_KEY = "href"
    POLICY_KEY = "policy"

    # RULE CONDITIONS
    CONDITION_CONTAINS = "contains"
    CONDITION_EQUALS = "equals"
    CONDITION_MATCHES_REGEX = "matches_regex"

    ALL_CONDITIONS_LIST = [
        CONDITION_CONTAINS, CONDITION_EQUALS, CONDITION_MATCHES_REGEX
    ]

    # RULE TYPES
    TYPE_HEADER = "header"
    TYPE_HOSTNAME = "hostname"
    TYPE_PATH = "path"
    TYPE_QUERY = "query"
    TYPE_BODY = "body"

    ALL_TYPES_LIST = [
        TYPE_HEADER, TYPE_HOSTNAME, TYPE_PATH, TYPE_QUERY, TYPE_BODY
    ]

    __tablename__ = "ibm_lb_listener_policy_rules"

    id = Column(String(32), primary_key=True)
    resource_id = Column(String(64), nullable=False)
    href = Column(Text, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow(), nullable=False)
    provisioning_status = Column(String(50), nullable=False)
    condition = Column(Enum(*ALL_CONDITIONS_LIST), nullable=False)
    value = Column(String(150), nullable=False)
    type_ = Column("type", Enum(*ALL_TYPES_LIST), nullable=False)
    field = Column(String(255))

    lb_listener_policy_id = Column(String(32), ForeignKey("ibm_lb_listener_policies.id", ondelete="CASCADE"))

    def __init__(
            self, resource_id, href, created_at, provisioning_status, condition, type_, value, field=None,
    ):
        self.id = str(uuid.uuid4().hex)
        self.resource_id = resource_id
        self.href = href
        self.created_at = created_at
        self.provisioning_status = provisioning_status
        self.condition = condition
        self.value = value
        self.field = field
        self.type_ = type_

    def to_reference_json(self):
        return {
            self.ID_KEY: self.id,
        }

    def to_json_body(self):
        from urllib.parse import quote
        json_data = {
            self.FIELD_KEY: self.field,
            self.CONDITION_KEY: self.condition,
            self.TYPE_KEY: self.type_,
        }

        if self.field == self.TYPE_QUERY and self.condition != self.CONDITION_MATCHES_REGEX:
            json_data[self.CONDITION_VALUE_KEY] = quote(self.value, safe='')

        return json_data

    def to_json(self, parent_reference=True):
        json_data = {
            self.ID_KEY: self.id,
            self.RESOURCE_ID_KEY: self.resource_id,
            self.PROVISIONING_STATUS_KEY: self.provisioning_status,
            self.CONDITION_KEY: self.condition,
            self.TYPE_KEY: self.type_,
            self.CONDITION_VALUE_KEY: self.value,
            self.FIELD_KEY: self.field
        }
        if parent_reference:
            json_data[self.POLICY_KEY] = self.lb_listener_policy.to_reference_json()

        return json_data

    @classmethod
    def from_ibm_json_body(cls, json_body):
        return cls(
            resource_id=json_body["id"],
            href=json_body["href"],
            created_at=return_datetime_object(json_body["created_at"]),
            provisioning_status=json_body["provisioning_status"],
            condition=json_body["condition"],
            value=json_body["value"],
            type_=json_body["type"],
            field=json_body.get("field"),
        )


class IBMPool(IBMRegionalResourceMixin, Base, LBCommonConsts):
    ID_KEY = "id"
    NAME_KEY = "name"
    CREATED_AT_KEY = "created_at"
    PROVISIONING_STATUS_KEY = "provisioning_status"
    RESOURCE_ID_KEY = "resource_id"
    ALGORITHM_KEY = "algorithm"
    PROTOCOL_KEY = "protocol"
    PROXY_PROTOCOL_KEY = "proxy_protocol"
    SESSION_PERSISTENCE_KEY = "session_persistence"
    HEALTH_MONITOR_KEY = "health_monitor"
    MEMBER_KEY = "members"
    HREF_KEY = "href"
    LOAD_BALANCER_KEY = "load_balancer"
    MEMBERS_KEY = "members"

    CRZ_BACKREF_NAME = "pools"

    __tablename__ = "ibm_pools"

    # ALGORITHM TYPES
    ALGO_LEAST_CONNECTIONS = "least_connections"
    ALGO_ROUND_ROBIN = "round_robin"
    ALGO_WEIGHTED_ROUND_ROBIN = "weighted_round_robin"

    ALL_ALGORITHMS_LIST = [ALGO_LEAST_CONNECTIONS, ALGO_ROUND_ROBIN, ALGO_WEIGHTED_ROUND_ROBIN]

    # PROXY PROTOCOL SETTING
    PROXY_PROTOCOL_V1 = "v1"
    PROXY_PROTOCOL_V2 = "v2"
    PROXY_PROTOCOL_DISABLED = "disabled"

    ALL_PROXY_PROTOCOLS_LIST = [PROXY_PROTOCOL_V1, PROXY_PROTOCOL_V2, PROXY_PROTOCOL_DISABLED]

    id = Column(String(32), primary_key=True)
    created_at = Column(DateTime, default=datetime.utcnow(), nullable=False)
    href = Column(Text, nullable=False)
    name = Column(String(255), nullable=False)
    resource_id = Column(String(64), nullable=False)
    algorithm = Column(Enum(*ALL_ALGORITHMS_LIST), nullable=False)
    protocol = Column(Enum(*LBCommonConsts.ALL_PROTOCOLS_LIST), nullable=False)
    provisioning_status = Column(String(50), nullable=False)
    proxy_protocol = Column(Enum(*ALL_PROXY_PROTOCOLS_LIST), nullable=False)

    load_balancer_id = Column(String(32), ForeignKey("ibm_load_balancers.id", ondelete="CASCADE"))

    # TODO: INSTANCE GROUP RELATIONSHIP
    session_persistence = relationship("IBMPoolSessionPersistence", backref="pool", cascade="all, delete-orphan",
                                       passive_deletes=True, uselist=False)
    health_monitor = relationship("IBMPoolHealthMonitor", backref="pool", cascade="all, delete-orphan",
                                  passive_deletes=True, uselist=False)
    listeners = relationship("IBMListener", backref="default_pool", cascade="all, delete-orphan", passive_deletes=True,
                             lazy="dynamic")
    members = relationship("IBMPoolMember", backref="pool", cascade="all, delete-orphan", passive_deletes=True,
                           lazy="dynamic")
    target = relationship("IBMListenerAndPolicyCommon", backref="pool", cascade="all, delete-orphan",
                          passive_deletes=True, uselist=False)
    instance_groups = relationship(
        "IBMInstanceGroup",
        backref="ibm_pool",
        cascade="all, delete-orphan",
        passive_deletes=True,
        lazy="dynamic"
    )

    __table_args__ = (UniqueConstraint(name, load_balancer_id, name="uix_ibm_pool_name_load_balancer_id"),)

    def __init__(self, name, algorithm, protocol, provisioning_status=None, proxy_protocol=PROXY_PROTOCOL_DISABLED,
                 resource_id=None, created_at=None, href=None):
        self.id = str(uuid.uuid4().hex)
        self.name = name
        self.algorithm = algorithm
        self.protocol = protocol
        self.provisioning_status = provisioning_status
        self.proxy_protocol = proxy_protocol
        self.resource_id = resource_id
        self.created_at = created_at
        self.href = href

    def to_reference_json(self):
        return {
            self.ID_KEY: self.id,
            self.NAME_KEY: self.name
        }

    def to_json(self, parent_reference=True):
        json_data = {
            self.ID_KEY: self.id,
            self.PROVISIONING_STATUS_KEY: self.provisioning_status,
            self.RESOURCE_ID_KEY: self.resource_id,
            self.CREATED_AT_KEY: self.created_at,
            self.NAME_KEY: self.name,
            self.PROTOCOL_KEY: self.protocol,
            self.ALGORITHM_KEY: self.algorithm,
            self.HEALTH_MONITOR_KEY: self.health_monitor.to_json(),
            self.MEMBER_KEY: [member.to_json(parent_reference=False) for member in self.members.all()],
        }
        if self.session_persistence:
            json_data[self.SESSION_PERSISTENCE_KEY] = self.session_persistence.to_json()

        if parent_reference:
            json_data[self.LOAD_BALANCER_KEY] = self.load_balancer.to_reference_json()

        return json_data

    def from_softlayer_to_ibm_json(self):
        json_data = {
            self.ID_KEY: self.id,
            self.ALGORITHM_KEY: self.algorithm,
            self.PROXY_PROTOCOL_KEY: self.proxy_protocol,
            self.HEALTH_MONITOR_KEY: self.health_monitor.to_json_body(),
            self.MEMBERS_KEY: [member.from_softlayer_to_ibm_json() for member in self.members.all()],
            self.NAME_KEY: self.name,
            self.PROTOCOL_KEY: self.protocol,
            self.PROXY_PROTOCOL_KEY: self.proxy_protocol,
        }

        if self.session_persistence:
            json_data[self.SESSION_PERSISTENCE_KEY] = self.session_persistence.to_json()

        return json_data

    def to_json_body(self):
        json_data = {
            "name": self.name,
            "protocol": self.protocol,
            "algorithm": self.algorithm,
            "health_monitor": self.health_monitor.to_json_body() if self.health_monitor else "",
            "members": [pool_mem.to_json_body() for pool_mem in self.members.all()],
        }

        if self.session_persistence:
            json_data["session_persistence"] = {"type": self.session_persistence}

        return json_data

    @classmethod
    def from_ibm_json_body(cls, json_body):
        ibm_pool = cls(
            name=json_body["name"],
            algorithm=json_body["algorithm"],
            protocol=json_body["protocol"],
            provisioning_status=json_body["provisioning_status"],
            proxy_protocol=json_body["proxy_protocol"],
            resource_id=json_body["id"],
            created_at=return_datetime_object(json_body["created_at"]),
            href=json_body["href"]
        )

        if "session_persistence" in json_body:
            ibm_pool.session_persistence = \
                IBMPoolSessionPersistence.from_ibm_json_body(json_body["session_persistence"])
        ibm_pool.health_monitor = IBMPoolHealthMonitor.from_ibm_json_body(json_body["health_monitor"])
        return ibm_pool

    def dis_params_eq(self, other):
        assert isinstance(other, self.__class__)
        return (self.name == other.name and self.resource_id == other.resource_id and
                self.algorithm == other.algorithm and self.protocol == other.protocol and
                self.session_persistence == other.session_persistence and
                self.provisioning_status == other.provisioning_status)

    def dis_add_update_db(self, session, db_load_balancer_pools, db_load_balancer, db_region):
        if not db_load_balancer:
            return
        db_load_balancer_pools_id_obj_dict = dict()
        db_load_balancer_pools_name_obj_dict = dict()
        for db_load_balancer_pool in db_load_balancer_pools:
            db_load_balancer_pools_id_obj_dict[db_load_balancer_pool.resource_id] = db_load_balancer_pool
            db_load_balancer_pools_name_obj_dict[db_load_balancer_pool.name] = db_load_balancer_pool

        if not db_load_balancer_pools_id_obj_dict.get(self.resource_id) and db_load_balancer_pools_name_obj_dict.get(
                self.name):
            # Creation Pending / Creating
            existing = db_load_balancer_pools_name_obj_dict[self.name]
        elif self.resource_id in db_load_balancer_pools_id_obj_dict:
            # Created. Update everything including name
            existing = db_load_balancer_pools_id_obj_dict[self.resource_id]
        else:
            existing = None

        if not existing:
            self.load_balancer = db_load_balancer
            self.region = db_region
            session.add(self)
            session.commit()
            return

        if not self.dis_params_eq(existing):
            existing.update_from_object(self)

        session.commit()

    def update_from_object(self, other):
        assert isinstance(other, self.__class__)

        self.name = other.name
        self.algorithm = other.algorithm
        self.protocol = other.protocol
        self.provisioning_status = other.provisioning_status
        self.proxy_protocol = other.proxy_protocol
        self.resource_id = other.resource_id
        self.href = other.href


class IBMPoolSessionPersistence(Base):
    ID_KEY = "id"
    TYPE_KEY = "type"
    COOKIE_NAME_KEY = "cookie_name"

    # POOL SESSION PERSISTENCE TYPES
    SESSION_PERSISTENCE_SOURCE_IP = "source_ip"
    SESSION_PERSISTENCE_APP_COOKIE = "app_cookie"
    SESSION_PERSISTENCE_HTTP_COOKIE = "http_cookie"

    ALL_SESSION_PERSISTENCE_TYPES_LIST = [
        SESSION_PERSISTENCE_SOURCE_IP, SESSION_PERSISTENCE_APP_COOKIE, SESSION_PERSISTENCE_HTTP_COOKIE
    ]

    __tablename__ = "ibm_lb_pool_session_persistence"

    id = Column(String(32), primary_key=True)
    type_ = Column(
        'type', Enum(SESSION_PERSISTENCE_SOURCE_IP, SESSION_PERSISTENCE_APP_COOKIE, SESSION_PERSISTENCE_HTTP_COOKIE),
        nullable=False
    )
    cookie_name = Column(String(255))

    lb_pool_id = Column(String(32), ForeignKey("ibm_pools.id", ondelete="SET NULL"), nullable=True)

    def __init__(self, type_, cookie_name=None):
        self.id = str(uuid.uuid4().hex)
        self.type_ = type_
        self.cookie_name = cookie_name

    def to_json(self):
        return {
            self.TYPE_KEY: self.type_,
            self.COOKIE_NAME_KEY: self.cookie_name,
        }

    @classmethod
    def from_ibm_json_body(cls, json_body):
        return cls(type_=json_body["type"], cookie_name=json_body.get("cookie_name"))


class IBMPoolHealthMonitor(Base, LBCommonConsts):
    ID_KEY = "id"
    PORT_KEY = "port"
    TYPE_KEY = "type"
    DELAY_KEY = "delay"
    TIMEOUT_KEY = "timeout"
    MAX_RETRIES_KEY = "max_retries"
    URL_PATH_KEY = "url_path"
    POOL_KEY = "pool"

    __tablename__ = "ibm_pool_health_monitors"

    id = Column(String(32), primary_key=True)
    port = Column(Integer)
    type_ = Column(
        'type',
        Enum(LBCommonConsts.PROTOCOL_HTTPS, LBCommonConsts.PROTOCOL_HTTP, LBCommonConsts.PROTOCOL_TCP),
        nullable=False
    )
    delay = Column(Integer, nullable=False)
    timeout = Column(Integer, nullable=False)
    max_retries = Column(Integer, nullable=False)
    url_path = Column(String(2048))

    lb_pool_id = Column(String(32), ForeignKey("ibm_pools.id", ondelete="CASCADE"))

    def __init__(self, type_, delay, max_retries, timeout, port=None, url_path=None):
        self.id = str(uuid.uuid4().hex)
        self.type_ = type_
        self.delay = delay
        self.max_retries = max_retries
        self.timeout = timeout
        self.port = port
        self.url_path = url_path

    def to_json_body(self):
        json_data = {
            self.DELAY_KEY: self.delay,
            self.MAX_RETRIES_KEY: self.max_retries,
            self.TIMEOUT_KEY: self.timeout,
            self.TYPE_KEY: self.type_,
            self.URL_PATH_KEY: self.url_path,
        }
        if self.port:
            json_data[self.PORT_KEY] = self.port

        return json_data

    def to_reference_json(self):
        return {
            self.ID_KEY: self.id,
        }

    def to_json(self, parent_reference=True):
        json_data = {
            self.ID_KEY: self.id,
            self.TYPE_KEY: self.type_,
            self.DELAY_KEY: self.delay,
            self.TIMEOUT_KEY: self.timeout,
            self.MAX_RETRIES_KEY: self.max_retries,
            self.URL_PATH_KEY: self.url_path,
            self.PORT_KEY: self.port
        }
        if parent_reference:
            json_data[self.POOL_KEY] = self.pool.to_reference_json()

        return json_data

    @classmethod
    def from_ibm_json_body(cls, json_body):
        return cls(
            type_=json_body["type"],
            delay=json_body["delay"],
            max_retries=json_body["max_retries"],
            timeout=json_body["timeout"],
            port=json_body.get("port"),
            url_path=json_body.get("url_path")
        )


class IBMPoolMember(Base, LBCommonConsts):
    ID_KEY = "id"
    PORT_KEY = "port"
    NAME_KEY = "name"
    INSTANCE_KEY = "instance"
    INSTANCE_ID_KEY = "instance_id"
    HEALTH_KEY = "health"
    ADDRESS_KEY = "address"
    HREF_KEY = "href"
    WEIGHT_KEY = "weight"
    CREATED_AT_KEY = "created_at"
    RESOURCE_ID_KEY = "resource_id"
    SUBNET_KEY = "subnet"
    NETWORK_INTERFACE_KEY = "network_interface"
    TARGET_KEY = "target"
    PROVISIONING_STATUS_KEY = "provisioning_status"
    POOL_KEY = "pool"
    TYPE_KEY = "type"

    TARGET_TYPE_INSTANCE = "instance"
    TARGET_TYPE_NETWORK_INTERFACE = "network_interface"

    # MEMBERS' HEALTH
    HEALTH_OK = "ok"
    HEALTH_FAULTED = "faulted"
    HEALTH_UNKNOWN = "unknown"

    ALL_HEALTH_STATUS_LIST = [HEALTH_OK, HEALTH_FAULTED, HEALTH_UNKNOWN]

    __tablename__ = "ibm_pool_members"

    id = Column(String(32), primary_key=True)
    resource_id = Column(String(64), nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow(), nullable=False)
    href = Column(Text, nullable=False)
    provisioning_status = Column(String(50), nullable=False)
    port = Column(Integer, nullable=False)
    health = Column(Enum(*ALL_HEALTH_STATUS_LIST), nullable=False)
    weight = Column(Integer)
    target_ip_address = Column(String(16))
    subnet_id = Column(String(32), nullable=True)

    pool_id = Column(String(32), ForeignKey("ibm_pools.id", ondelete="CASCADE"))
    target_instance_id = Column(String(32), ForeignKey("ibm_instances.id", ondelete="SET NULL"), nullable=True)

    instance_group_memberships = relationship(
        "IBMInstanceGroupMembership",
        backref="pool_member",
        cascade="all, delete-orphan",
        lazy="dynamic"
    )

    def __init__(self, port, weight=None, resource_id=None, status=None, created_at=None, health=None,
                 provisioning_status=None, href=None, target_ip_address=None):
        self.id = str(uuid.uuid4().hex)
        self.port = port
        self.weight = weight
        self.resource_id = resource_id
        self.created_at = created_at
        self.health = health
        self.provisioning_status = provisioning_status
        self.href = href
        self.target_ip_address = target_ip_address

    @property
    def subnet(self):
        from ibm.models import IBMSubnet
        from ibm import get_db_session
        with get_db_session() as db_session:
            return db_session.query(IBMSubnet).filter_by(id=self.subnet_id).first()

    @property
    def network_interface(self):
        from ibm.models import IBMNetworkInterface
        from ibm import get_db_session

        with get_db_session() as db_session:
            return db_session.query(IBMNetworkInterface).filter_by(primary_ipv4_address=self.target_ip_address).first()

    @property
    def __target_type_instance(self):
        json_data = {
            self.ID_KEY: self.instance.id,
            self.NAME_KEY: self.instance.name,
            self.TYPE_KEY: self.TARGET_TYPE_INSTANCE,
        }
        if self.subnet:
            json_data[self.SUBNET_KEY] = {
                self.ID_KEY: self.subnet.id,
                self.NAME_KEY: self.subnet.name,
            }
        return json_data

    @property
    def __target_type_network_interface(self):
        json_data = {
            self.ADDRESS_KEY: self.target_ip_address,
            self.ID_KEY: "",
            self.NAME_KEY: "",
        }

        if self.network_interface:
            json_data[self.ID_KEY] = self.network_interface.id
            json_data[self.NAME_KEY] = self.network_interface.name
            json_data[self.TYPE_KEY] = self.TARGET_TYPE_NETWORK_INTERFACE

        if self.subnet:
            json_data[self.SUBNET_KEY] = {
                self.ID_KEY: self.subnet.id,
                self.NAME_KEY: self.subnet.name,
            }

        if hasattr(self, "_network_interface") and self._network_interface:
            json_data[self.ID_KEY] = self._network_interface.id
            json_data[self.NAME_KEY] = self._network_interface.name
            json_data[self.TYPE_KEY] = self.TARGET_TYPE_NETWORK_INTERFACE

        if hasattr(self, "_subnet") and self._subnet:
            json_data[self.SUBNET_KEY] = {
                self.ID_KEY: self._subnet.id,
                self.NAME_KEY: self._subnet.name,
            }
        return json_data

    @property
    def target(self):
        if self.instance:
            return self.__target_type_instance

        elif self.__target_type_network_interface:
            return self.__target_type_network_interface

    def from_softlayer_to_ibm_json(self):
        return {
            self.PORT_KEY: self.port,
            self.TARGET_KEY: self.target
        }

    def to_reference_json(self):
        return {
            self.ID_KEY: self.id
        }

    def to_json(self, parent_reference=True):
        json_data = {
            self.ID_KEY: self.id,
            self.RESOURCE_ID_KEY: self.resource_id,
            self.PORT_KEY: self.port,
            self.HEALTH_KEY: self.health,
            self.TARGET_KEY: self.target,
            self.WEIGHT_KEY: self.weight,
            self.PROVISIONING_STATUS_KEY: self.provisioning_status,
            self.CREATED_AT_KEY: self.created_at,
        }
        if parent_reference:
            json_data[self.POOL_KEY] = self.pool.to_reference_json()

        return json_data

    def to_json_body(self):
        return {
            "target": self.target,
            "port": self.port,
            "weight": self.weight,
        }

    @classmethod
    def from_ibm_json_body(cls, json_body):
        return cls(
            port=json_body["port"],
            weight=json_body["weight"],
            resource_id=json_body["id"],
            created_at=return_datetime_object(json_body["created_at"]),
            health=json_body["health"],
            provisioning_status=json_body["provisioning_status"],
            href=json_body["href"],
            target_ip_address=json_body["target"].get("address")
        )

    def dis_params_eq(self, other):
        assert isinstance(other, self.__class__)
        return (self.port == other.port and self.weight == other.weight and
                self.provisioning_status == other.provisioning_status and self.resource_id == other.resource_id)

    def dis_add_update_db(self, session, db_lb_pool_members, db_lb_pool):
        if not db_lb_pool:
            return
        existing = None
        for db_lb_pool_member in db_lb_pool_members:
            if db_lb_pool_member.resource_id == self.resource_id:
                # TODO: enhance existing logic for CREATION_PENDING/CREATING resources with target after discussing
                existing = db_lb_pool_member
                break

        if not existing:
            self.pool = db_lb_pool
            session.add(self)
            session.commit()
            return

        if not self.dis_params_eq(existing):
            existing.update_from_object(self)
            existing.pool = db_lb_pool

        session.commit()

    def update_from_object(self, other):
        assert isinstance(other, self.__class__)

        self.weight = other.weight
        self.port = other.port
        self.resource_id = other.resource_id
        self.provisioning_status = other.provisioning_status
