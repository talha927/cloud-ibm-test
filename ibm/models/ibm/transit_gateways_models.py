import uuid

from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    ForeignKey,
    Integer,
    String,
    Enum, JSON
)
from sqlalchemy.orm import relationship
from sqlalchemy.schema import UniqueConstraint

from ibm.common.utils import return_datetime_object
from ibm.models.base import Base
from ibm.models.ibm.mixins import IBMRegionalResourceMixin, IBMCloudResourceMixin


class IBMTransitGateway(IBMRegionalResourceMixin, Base):
    ID_KEY = "id"
    NAME_KEY = "name"
    LOCATION_KEY = "location"
    RESOURCE_GROUP_KEY = "resource_group"
    GLOBAL_KEY = "global_"
    STATUS_KEY = "status"
    CRN_KEY = "crn"
    CONNECTIONS_KEY = "connections"
    ROUTE_REPORTS_KEY = "route_reports"
    CREATED_AT_KEY = "created_at"
    UPDATED_AT_KEY = "updated_at"

    # IBM Status consts
    STATUS_AVAILABLE = "available"
    STATUS_FAILED = "failed"
    STATUS_PENDING = "pending"
    STATUS_DELETING = "deleting"
    STATUSES_LIST = [STATUS_AVAILABLE, STATUS_FAILED, STATUS_PENDING, STATUS_DELETING]

    CRZ_BACKREF_NAME = "transit_gateways"

    __tablename__ = "ibm_transit_gateways"

    id = Column(String(32), primary_key=True)
    name = Column(String(64), nullable=False)
    location = Column(String(20), nullable=False)
    resource_id = Column(String(36), nullable=False)
    crn = Column(String(255), nullable=False)
    global_ = Column("global", Boolean, default=False, nullable=False)
    status = Column(String(50), nullable=False)
    created_at = Column(DateTime, nullable=False)
    updated_at = Column(DateTime, nullable=False)

    resource_group_id = Column(String(32), ForeignKey("ibm_resource_groups.id", ondelete="CASCADE"))

    connections = relationship(
        "IBMTransitGatewayConnection",
        backref="transit_gateway",
        cascade="all, delete-orphan",
        lazy="dynamic",
    )

    route_reports = relationship(
        "IBMTransitGatewayRouteReport",
        backref="transit_gateway",
        cascade="all, delete-orphan",
        lazy="dynamic",
    )

    def __init__(self, name, location, crn, resource_id, status=None, global_=False,
                 created_at=None, updated_at=None):
        super().__init__()
        self.id = str(uuid.uuid4().hex)
        self.name = name
        self.location = location
        self.global_ = global_
        self.status = status
        self.crn = crn
        self.resource_id = resource_id
        self.created_at = created_at
        self.updated_at = updated_at

    def to_reference_json(self):
        return {
            self.ID_KEY: self.id,
            self.NAME_KEY: self.name,
            self.CRN_KEY: self.crn
        }

    def to_json(self):
        return {
            self.ID_KEY: self.id,
            self.NAME_KEY: self.name,
            self.LOCATION_KEY: self.location,
            self.GLOBAL_KEY: self.global_,
            self.STATUS_KEY: self.status,
            self.CRN_KEY: self.crn,
            self.CREATED_AT_KEY: self.created_at,
            self.UPDATED_AT_KEY: self.updated_at,
            self.CONNECTIONS_KEY: [connection.to_json() for connection in self.connections.all()],
            self.ROUTE_REPORTS_KEY: [route_report.to_json() for route_report in self.route_reports.all()],
            self.IBM_CLOUD_KEY: self.ibm_cloud.to_reference_json(),
            self.REGION_KEY: self.region.to_reference_json() if self.region else {}
        }

    @classmethod
    def from_ibm_json_body(cls, json_body):
        return cls(
            name=json_body["name"],
            location=json_body["location"],
            global_=json_body["global"],
            status=json_body["status"],
            crn=json_body["crn"],
            resource_id=json_body["id"],
            created_at=return_datetime_object(json_body["created_at"]),
            updated_at=return_datetime_object(json_body["updated_at"]),
        )

    def dis_params_eq(self, other):
        assert isinstance(other, self.__class__)

        return (self.name == other.name and self.location == other.location and self.global_ == other.global_ and
                self.status == other.status and self.created_at == other.created_at and
                self.resource_id == other.resource_id)

    def dis_add_update_db(self, session, db_transit_gateways, db_cloud, db_region, db_resource_group):
        db_transit_gateways_id_obj_dict = dict()
        db_transit_gateways_name_obj_dict = dict()
        for db_transit_gateway in db_transit_gateways:
            db_transit_gateways_id_obj_dict[db_transit_gateway.resource_id] = db_transit_gateway
            db_transit_gateways_name_obj_dict[db_transit_gateway.name] = db_transit_gateway

        if self.resource_id not in db_transit_gateways_id_obj_dict and self.name in db_transit_gateways_name_obj_dict:
            # Creation Pending / Creating
            existing = db_transit_gateways_name_obj_dict[self.name]
        elif self.resource_id in db_transit_gateways_id_obj_dict:
            # Created. Update everything including name
            existing = db_transit_gateways_id_obj_dict[self.resource_id]
        else:
            existing = None

        if not existing:
            self.ibm_cloud = db_cloud
            self.resource_group = db_resource_group
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
        self.location = other.location
        self.global_ = other.global_
        self.status = other.status
        self.crn = other.crn
        self.resource_id = other.resource_id
        self.created_at = other.created_at
        self.updated_at = other.updated_at


class IBMTransitGatewayConnection(IBMCloudResourceMixin, Base):
    ID_KEY = "id"
    NAME_KEY = "name"
    VPC_KEY = "vpc"
    RESOURCE_KEY = "resource_id"
    NETWORK_TYPE_KEY = "network_type"
    STATUS_KEY = "status"
    CONNECTION_STATUS = "connection_status"
    NETWORK_ID_KEY = "network_id"
    NETWORK_ACCOUNT_ID_KEY = "network_account_id"
    TRANSIT_GATEWAY_KEY = "transit_gateway"
    PREFIX_FILTER_ID_KEY = "prefix_filters"
    PREFIX_FILTER_DEFAULT_KEY = "prefix_filters_default"
    CREATED_AT_KEY = "created_at"
    UPDATED_AT_KEY = "updated_at"

    # network type consts
    VPC = "vpc"
    CLASSIC = "classic"
    NETWORK_TYPE_LIST = [VPC, CLASSIC]

    # IBM Status consts
    CONN_STATUS_ATTACHED = "attached"
    CONN_STATUS_FAILED = "failed"
    CONN_STATUS_PENDING = "pending"
    CONN_STATUS_DELETING = "deleting"
    CONN_STATUS_DETACHING = "detaching"
    CONN_STATUS_DETACHED = "detached"
    CONN_STATUSES_LIST = [CONN_STATUS_ATTACHED, CONN_STATUS_FAILED, CONN_STATUS_PENDING, CONN_STATUS_DELETING,
                          CONN_STATUS_DETACHING, CONN_STATUS_DETACHED]

    # Prefix Filter Default consts
    PERMIT = "permit"
    DENY = "deny"
    PREFIX_FILTER_DEFAULT_PERMISSION_LIST = [PERMIT, DENY]

    CRZ_BACKREF_NAME = "transit_gateway_connections"

    __tablename__ = "ibm_transit_gateway_connections"

    id = Column(String(32), primary_key=True)
    resource_id = Column(String(64), nullable=False)
    name = Column(String(255), nullable=False)
    status = Column(String(50), nullable=False)
    network_type = Column(Enum(*NETWORK_TYPE_LIST), nullable=False)
    network_account_id = Column(String(32))
    prefix_filters_default = Column(Enum(*PREFIX_FILTER_DEFAULT_PERMISSION_LIST))
    created_at = Column(DateTime, nullable=False)
    updated_at = Column(DateTime, nullable=False)

    transit_gateway_id = Column(String(32), ForeignKey("ibm_transit_gateways.id", ondelete="CASCADE"))

    __table_args__ = (
        UniqueConstraint(
            name, transit_gateway_id, name="uix_transit_connection_name_transit_gateway_id"
        ),
    )

    vpc = relationship(
        "IBMVpcNetwork",
        backref="transit_gateway_connection",
        uselist=False,
    )

    prefix_filters = relationship(
        "IBMTransitGatewayConnectionPrefixFilter",
        backref="transit_gateway_connection",
        cascade="all, delete-orphan",
        lazy="dynamic",
    )

    def __init__(
            self,
            name,
            network_type=None,
            network_account_id=None,
            status=None,
            prefix_filters_default=None,
            resource_id=None,
            created_at=None,
            updated_at=None
    ):
        self.id = str(uuid.uuid4().hex)
        self.name = name
        self.network_type = network_type
        self.network_account_id = network_account_id
        self.status = status
        self.prefix_filters_default = prefix_filters_default
        self.resource_id = resource_id
        self.created_at = created_at
        self.updated_at = updated_at

    def to_json(self):
        return {
            self.ID_KEY: self.id,
            self.NAME_KEY: self.name,
            self.VPC_KEY: self.vpc.to_reference_json() if self.vpc else None,
            self.NETWORK_TYPE_KEY: self.network_type,
            self.STATUS_KEY: self.status,
            self.TRANSIT_GATEWAY_KEY: self.transit_gateway.to_reference_json() if self.transit_gateway else None,
            self.PREFIX_FILTER_ID_KEY: [prefix_filter.to_json() for prefix_filter in self.prefix_filters.all()],
            self.PREFIX_FILTER_DEFAULT_KEY: self.prefix_filters_default,
            self.RESOURCE_KEY: self.resource_id,
            self.IBM_CLOUD_KEY: self.ibm_cloud.to_reference_json(),
            self.CREATED_AT_KEY: self.created_at,
            self.UPDATED_AT_KEY: self.updated_at,
        }

    @classmethod
    def from_ibm_json_body(cls, json_body):
        return cls(
            name=json_body.get("name"),
            network_type=json_body["network_type"],
            created_at=return_datetime_object(json_body["created_at"]),
            prefix_filters_default=json_body["prefix_filters_default"],
            network_account_id=json_body.get("network_account_id"),
            status=json_body["status"],
            resource_id=json_body["id"],
            updated_at=return_datetime_object(json_body["updated_at"])
        )

    def dis_params_eq(self, other):
        assert isinstance(other, self.__class__)

        return (self.name == other.name and self.network_type == other.network_type and
                self.prefix_filters_default == other.prefix_filters_default and
                self.status == other.status and self.created_at == other.created_at and
                self.resource_id == other.resource_id and self.network_account_id == other.network_account_id and
                self.updated_at == other.updated_at)

    def dis_add_update_db(self, session, db_transit_gateway_connections, db_transit_gateway, db_cloud):
        db_transit_gateway_connections_id_obj_dict = dict()
        db_transit_gateway_connections_id_obj_dict_name_obj_dict = dict()
        for db_transit_gateway_connection in db_transit_gateway_connections:
            db_transit_gateway_connections_id_obj_dict[db_transit_gateway_connection.resource_id] = \
                db_transit_gateway_connection
            db_transit_gateway_connections_id_obj_dict_name_obj_dict[db_transit_gateway_connection.name] = \
                db_transit_gateway_connection

        if self.resource_id not in db_transit_gateway_connections_id_obj_dict and self.name in \
                db_transit_gateway_connections_id_obj_dict_name_obj_dict:
            # Creation Pending / Creating
            existing = db_transit_gateway_connections_id_obj_dict_name_obj_dict[self.name]

        elif self.resource_id in db_transit_gateway_connections_id_obj_dict:
            # Created. Update everything including name
            existing = db_transit_gateway_connections_id_obj_dict[self.resource_id]
        else:
            existing = None

        if not existing:
            self.ibm_cloud = db_cloud
            self.transit_gateway = db_transit_gateway
            session.add(self)
            session.commit()
            return

        if not self.dis_params_eq(existing):
            existing.update_from_object(self)

        session.commit()

    def update_from_object(self, other):
        assert isinstance(other, self.__class__)

        self.name = other.name
        self.network_type = other.network_type
        self.prefix_filters_default = other.prefix_filters_default
        self.status = other.status
        self.network_account_id = other.network_account_id
        self.resource_id = other.resource_id
        self.created_at = other.created_at
        self.updated_at = other.updated_at


class IBMTransitGatewayConnectionPrefixFilter(IBMCloudResourceMixin, Base):
    ID_KEY = "id"
    RESOURCE_ID_KEY = "resource_id"
    ACTION_KEY = "action"
    PREFIX_KEY = "prefix"
    BEFORE_KEY = "before"
    GREATER_THAN_OR_EQUAL_TO_KEY = "ge"
    LESS_THAN_OR_EQUAL_TO_KEY = "le"
    CREATED_AT_KEY = "created_at"
    UPDATED_AT_KEY = "updated_at"

    # Action consts
    PERMIT = "permit"
    DENY = "deny"
    ACTION_LIST = [PERMIT, DENY]

    CRZ_BACKREF_NAME = "transit_gateways_connection_prefix_filter"

    __tablename__ = "ibm_transit_gateway_connection_prefix_filters"

    id = Column(String(32), primary_key=True)
    resource_id = Column(String(64), nullable=False)
    action = Column(Enum(*ACTION_LIST), nullable=False)
    prefix = Column(String(255), nullable=False)
    before = Column(String(50))
    ge = Column(Integer())
    le = Column(Integer())
    created_at = Column(DateTime, nullable=False)
    updated_at = Column(DateTime, nullable=False)

    connection_id = Column(String(32), ForeignKey("ibm_transit_gateway_connections.id", ondelete="CASCADE"))

    def __init__(
            self,
            action=None,
            resource_id=None,
            prefix=None,
            before=None,
            greater_than_or_equal_to=None,
            less_than_or_equal_to=None,
            created_at=None,
            updated_at=None

    ):
        self.id = str(uuid.uuid4().hex)
        self.action = action
        self.resource_id = resource_id
        self.prefix = prefix
        self.before = before
        self.ge = greater_than_or_equal_to
        self.le = less_than_or_equal_to
        self.created_at = created_at
        self.updated_at = updated_at

    def to_json(self):
        return {
            self.ID_KEY: self.id,
            self.ACTION_KEY: self.action,
            self.RESOURCE_ID_KEY: self.resource_id,
            self.PREFIX_KEY: self.prefix,
            self.BEFORE_KEY: self.before,
            self.GREATER_THAN_OR_EQUAL_TO_KEY: self.ge,
            self.LESS_THAN_OR_EQUAL_TO_KEY: self.le,
            self.IBM_CLOUD_KEY: self.ibm_cloud.to_reference_json(),
            self.CREATED_AT_KEY: self.created_at,
            self.UPDATED_AT_KEY: self.updated_at
        }

    @classmethod
    def from_ibm_json_body(cls, json_body):
        return cls(
            resource_id=json_body["id"],
            action=json_body["action"],
            prefix=json_body["prefix"],
            before=json_body.get("before"),
            greater_than_or_equal_to=json_body.get("ge"),
            less_than_or_equal_to=json_body.get("le"),
            created_at=return_datetime_object(json_body["created_at"]),
            updated_at=return_datetime_object(json_body["updated_at"])
        )

    def dis_params_eq(self, other):
        assert isinstance(other, self.__class__)

        return (self.action == other.action and self.prefix == other.prefix and self.ge == other.ge and
                self.le == other.le and self.created_at == other.created_at and self.resource_id == other.resource_id
                and self.updated_at == other.updated_at)

    def dis_add_update_db(self, session, db_transit_gateway_connection_prefix_filters, db_cloud,
                          db_transit_gateway_connection):
        db_transit_gateway_connection_prefix_filters_id_obj_dict = dict()
        for db_transit_gateway_connection_prefix_filter in db_transit_gateway_connection_prefix_filters:
            db_transit_gateway_connection_prefix_filters_id_obj_dict[
                db_transit_gateway_connection_prefix_filter.resource_id] = db_transit_gateway_connection_prefix_filter

        if self.resource_id in db_transit_gateway_connection_prefix_filters_id_obj_dict:
            existing = db_transit_gateway_connection_prefix_filters_id_obj_dict[self.resource_id]
        else:
            existing = None

        if not existing:
            self.ibm_cloud = db_cloud
            self.transit_gateway_connection = db_transit_gateway_connection
            session.commit()
            return self

        if not self.dis_params_eq(existing):
            existing.update_from_object(self)

        session.commit()
        return existing

    def update_from_object(self, other):
        assert isinstance(other, self.__class__)

        self.action = other.action
        self.prefix = other.prefix
        self.ge = other.ge
        self.le = other.le
        self.resource_id = other.resource_id
        self.created_at = other.created_at
        self.updated_at = other.updated_at


class IBMTransitGatewayRouteReport(IBMCloudResourceMixin, Base):
    ID_KEY = "id"
    RESOURCE_ID_KEY = "resource_id"
    STATUS_KEY = "status"
    CONNECTIONS_KEY = "connections"
    OVERLAPPING_ROUTES_KEY = "overlapping_routes"
    CREATED_AT_KEY = "created_at"
    UPDATED_AT_KEY = "updated_at"

    # IBM status consts
    STATUS_PENDING = "pending"
    STATUS_COMPLETE = "complete"
    STATUSES_LIST = [STATUS_PENDING, STATUS_COMPLETE]

    CRZ_BACKREF_NAME = "transit_gateway_route_report"

    __tablename__ = "ibm_transit_gateway_route_reports"

    id = Column(String(32), primary_key=True)
    resource_id = Column(String(64))
    connections = Column(JSON, nullable=False)
    overlapping_routes = Column(JSON, nullable=False)
    status = Column(String(50), nullable=False)
    created_at = Column(DateTime, nullable=False)
    updated_at = Column(DateTime, nullable=False)

    transit_gateway_id = Column(String(32), ForeignKey("ibm_transit_gateways.id", ondelete="CASCADE"))

    def __init__(
            self,
            resource_id=None,
            connections=None,
            overlapping_routes=None,
            status=None,
            created_at=None,
            updated_at=None
    ):
        self.id = str(uuid.uuid4().hex)
        self.resource_id = resource_id
        self.connections = connections
        self.overlapping_routes = overlapping_routes
        self.status = status
        self.created_at = created_at
        self.updated_at = updated_at

    def to_json(self):
        return {
            self.ID_KEY: self.id,
            self.RESOURCE_ID_KEY: self.resource_id,
            self.STATUS_KEY: self.status,
            self.CONNECTIONS_KEY: self.connections,
            self.OVERLAPPING_ROUTES_KEY: self.overlapping_routes,
            self.IBM_CLOUD_KEY: self.ibm_cloud.to_reference_json(),
            self.CREATED_AT_KEY: self.created_at,
            self.UPDATED_AT_KEY: self.updated_at
        }

    @classmethod
    def from_ibm_json_body(cls, json_body):
        return cls(
            resource_id=json_body["id"],
            connections=json_body["connections"],
            overlapping_routes=json_body["overlapping_routes"],
            status=json_body["status"],
            created_at=return_datetime_object(json_body["created_at"]),
            updated_at=return_datetime_object(json_body["updated_at"])
        )
