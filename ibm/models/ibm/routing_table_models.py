import uuid
from datetime import datetime

from sqlalchemy import Boolean, Column, DateTime, Enum, ForeignKey, String, Text
from sqlalchemy.orm import backref, relationship
from sqlalchemy.schema import UniqueConstraint

from ibm.common.utils import return_datetime_object
from ibm.models.base import Base
from ibm.models.ibm.mixins import IBMRegionalResourceMixin, IBMZonalResourceMixin


class IBMRoutingTable(IBMRegionalResourceMixin, Base):
    ID_KEY = "id"
    RESOURCE_ID_KEY = "resource_id"
    NAME_KEY = "name"
    HREF_KEY = "href"
    CREATED_AT_KEY = "created_at"
    IS_DEFAULT_KEY = "is_default"
    LIFECYCLE_STATE_KEY = "lifecycle_state"
    RESOURCE_TYPE_KEY = "resource_type"
    ROUTE_DIRECT_LINK_INGRESS_KEY = "route_direct_link_ingress"
    ROUTE_TRANSIT_GATEWAY_INGRESS_KEY = "route_transit_gateway_ingress"
    ROUTE_VPC_ZONE_INGRESS_KEY = "route_vpc_zone_ingress"
    VPC_KEY = "vpc"
    SUBNETS_KEY = "subnets"
    ROUTES_KEY = "routes"
    ASSOCIATED_RESOURCES_KEY = "associated_resources"
    RESOURCE_JSON_KEY = "resource_json"

    CRZ_BACKREF_NAME = "routing_tables"

    # lifecycle state consts
    LIFECYCLE_STATE_STABLE = "stable"
    LIFECYCLE_STATE_DELETING = "deleting"
    LIFECYCLE_STATE_FAILED = "failed"
    LIFECYCLE_STATE_PENDING = "pending"
    LIFECYCLE_STATE_WAITING = "waiting"
    LIFECYCLE_STATE_SUSPENDED = "suspended"
    LIFECYCLE_STATE_UPDATING = "updating"
    ALL_LIFECYCLE_STATES_LIST = \
        [
            LIFECYCLE_STATE_STABLE, LIFECYCLE_STATE_DELETING, LIFECYCLE_STATE_FAILED, LIFECYCLE_STATE_PENDING,
            LIFECYCLE_STATE_WAITING, LIFECYCLE_STATE_SUSPENDED, LIFECYCLE_STATE_UPDATING
        ]

    __tablename__ = "ibm_routing_tables"

    id = Column(String(32), primary_key=True)
    resource_id = Column(String(64), nullable=False)
    name = Column(String(255), nullable=False)
    href = Column(Text, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow(), nullable=False)
    is_default = Column(Boolean, nullable=False)
    lifecycle_state = Column(String(50), nullable=False)
    resource_type = Column(String(255), default="routing_table", nullable=False)
    route_direct_link_ingress = Column(Boolean, nullable=False)
    route_transit_gateway_ingress = Column(Boolean, nullable=False)
    route_vpc_zone_ingress = Column(Boolean, nullable=False)

    vpc_id = Column(String(32), ForeignKey("ibm_vpc_networks.id", ondelete="CASCADE"))

    subnets = relationship("IBMSubnet", backref="routing_table", lazy="dynamic")
    routes = relationship("IBMRoutingTableRoute", backref="routing_table", cascade="all, delete-orphan",
                          passive_deletes=True, lazy="dynamic")

    __table_args__ = (UniqueConstraint(name, vpc_id, "region_id", name="uix_ibm_routing_table_name_vpc_id_region_id"),)

    def __init__(
            self, resource_id=None, name=None, href=None, created_at=None, is_default=None, lifecycle_state=None,
            resource_type=None, route_direct_link_ingress=None, route_transit_gateway_ingress=None,
            route_vpc_zone_ingress=None
    ):
        self.id = str(uuid.uuid4().hex)
        self.resource_id = resource_id
        self.name = name
        self.href = href
        self.created_at = created_at
        self.is_default = is_default
        self.lifecycle_state = lifecycle_state
        self.resource_type = resource_type
        self.route_direct_link_ingress = route_direct_link_ingress
        self.route_transit_gateway_ingress = route_transit_gateway_ingress
        self.route_vpc_zone_ingress = route_vpc_zone_ingress

    def to_reference_json(self):
        return {
            self.ID_KEY: self.id,
            self.NAME_KEY: self.name
        }

    def to_template_json(self):
        resource_json = {
            self.NAME_KEY: self.name,
            self.ROUTE_DIRECT_LINK_INGRESS_KEY: self.route_direct_link_ingress,
            self.ROUTE_TRANSIT_GATEWAY_INGRESS_KEY: self.route_transit_gateway_ingress,
            self.ROUTE_VPC_ZONE_INGRESS_KEY: self.route_vpc_zone_ingress,
            self.ROUTES_KEY: [route.to_template_json() for route in self.routes.all()],
        }

        routing_table_schema = {
            self.ID_KEY: self.id,
            self.IBM_CLOUD_KEY: {self.ID_KEY: self.cloud_id},
            self.REGION_KEY: {self.ID_KEY: self.region_id},
            self.VPC_KEY: {self.ID_KEY: self.vpc_id},
            self.RESOURCE_JSON_KEY: resource_json,

        }
        return routing_table_schema

    def to_json(self):
        return {
            self.ID_KEY: self.id,
            self.RESOURCE_ID_KEY: self.resource_id,
            self.NAME_KEY: self.name,
            self.HREF_KEY: self.href,
            self.CREATED_AT_KEY: self.created_at,
            self.IS_DEFAULT_KEY: self.is_default,
            self.LIFECYCLE_STATE_KEY: self.lifecycle_state,
            self.RESOURCE_TYPE_KEY: self.resource_type,
            self.ROUTE_DIRECT_LINK_INGRESS_KEY: self.route_direct_link_ingress,
            self.ROUTE_TRANSIT_GATEWAY_INGRESS_KEY: self.route_transit_gateway_ingress,
            self.ROUTE_VPC_ZONE_INGRESS_KEY: self.route_vpc_zone_ingress,
            self.ROUTES_KEY: [route.to_reference_json() for route in self.routes.all()],
            self.IBM_CLOUD_KEY: self.ibm_cloud.to_reference_json(),
            self.REGION_KEY: self.region.to_reference_json(),
            self.ASSOCIATED_RESOURCES_KEY: {
                self.VPC_KEY: self.vpc_network.to_reference_json(),
                self.SUBNETS_KEY: [subnet.to_reference_json() for subnet in self.subnets.all()],
            }
        }

    @classmethod
    def from_ibm_json_body(cls, json_body):
        return cls(
            resource_id=json_body["id"],
            name=json_body["name"],
            href=json_body["href"],
            created_at=return_datetime_object(json_body["created_at"]),
            is_default=json_body["is_default"],
            lifecycle_state=json_body["lifecycle_state"],
            resource_type=json_body["resource_type"],
            route_direct_link_ingress=json_body["route_direct_link_ingress"],
            route_transit_gateway_ingress=json_body["route_transit_gateway_ingress"],
            route_vpc_zone_ingress=json_body["route_vpc_zone_ingress"],
        )

    def dis_params_eq(self, other):
        assert isinstance(other, self.__class__)

        return (self.resource_id == other.resource_id and self.name == other.name and self.href == other.href and
                self.lifecycle_state == other.lifecycle_state and self.resource_type == other.resource_type and
                self.route_direct_link_ingress == other.route_direct_link_ingress and
                self.route_transit_gateway_ingress == other.route_transit_gateway_ingress and
                self.route_vpc_zone_ingress == other.route_vpc_zone_ingress)

    def dis_add_update_db(self, session, db_vpc_route, db_cloud, db_vpc_network, db_region):
        existing = db_vpc_route or None
        if not existing:
            self.ibm_cloud = db_cloud
            self.vpc_network = db_vpc_network
            self.region = db_region
            session.add(self)
            session.commit()
            return

        if not self.dis_params_eq(existing):
            existing.update_from_object(self)
            existing.vpc_network = db_vpc_network
            existing.region = db_region

        session.commit()

    def update_from_object(self, other):
        assert isinstance(other, self.__class__)

        self.resource_id = other.resource_id
        self.name = other.name
        self.href = other.href
        self.lifecycle_state = other.lifecycle_state
        self.resource_type = other.resource_type
        self.route_direct_link_ingress = other.route_direct_link_ingress
        self.route_transit_gateway_ingress = other.route_transit_gateway_ingress
        self.route_vpc_zone_ingress = other.route_vpc_zone_ingress


class IBMRoutingTableRoute(IBMZonalResourceMixin, Base):
    ID_KEY = "id"
    RESOURCE_ID_KEY = "resource_id"
    NAME_KEY = "name"
    HREF_KEY = "href"
    CREATED_AT_KEY = "created_at"
    ACTION_KEY = "action"
    LIFECYCLE_STATE_KEY = "lifecycle_state"
    DESTINATION_KEY = "destination"
    NEXT_HOP_ADDRESS_IP_KEY = "next_hop_address_ip"
    NEXT_HOP_VPN_GATEWAY_CONNECTION_KEY = "next_hop_vpn_gateway_connection"
    ROUTING_TABLE_KEY = "routing_table"

    CRZ_BACKREF_NAME = "routing_table_routes"

    # status consts
    LIFECYCLE_STATE_DELETING = "deleting"
    LIFECYCLE_STATE_FAILED = "failed"
    LIFECYCLE_STATE_PENDING = "pending"
    LIFECYCLE_STATE_STABLE = "stable"
    LIFECYCLE_STATE_UPDATING = "updating"
    LIFECYCLE_STATE_WAITING = "waiting"
    LIFECYCLE_STATE_SUSPENDED = "suspended"
    ALL_LIFECYCLE_STATES_LIST = \
        [
            LIFECYCLE_STATE_DELETING, LIFECYCLE_STATE_FAILED, LIFECYCLE_STATE_PENDING, LIFECYCLE_STATE_STABLE,
            LIFECYCLE_STATE_UPDATING, LIFECYCLE_STATE_WAITING, LIFECYCLE_STATE_SUSPENDED
        ]

    ACTION_DELEGATE = "delegate"
    ACTION_DELEGATE_VPC = "delegate_vpc"
    ACTION_DELIVER = "deliver"
    ACTION_DROP = "drop"
    ALL_ACTIONS_LIST = [ACTION_DELEGATE, ACTION_DELEGATE_VPC, ACTION_DELIVER, ACTION_DROP]

    __tablename__ = "ibm_routing_table_routes"

    id = Column(String(32), primary_key=True)
    resource_id = Column(String(64), nullable=False)
    name = Column(String(255), nullable=False)
    href = Column(Text, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow(), nullable=False)
    action = Column(Enum(*ALL_ACTIONS_LIST))
    lifecycle_state = Column(String(50), nullable=False)
    destination = Column(String(32), nullable=False)
    next_hop_address_ip = Column(String(16))

    next_hop_vpn_gateway_connection_id = Column(String(32), ForeignKey("ibm_vpn_connections.id", ondelete="SET NULL"),
                                                nullable=True)
    routing_table_id = Column(String(32), ForeignKey("ibm_routing_tables.id", ondelete="CASCADE"))

    next_hop_vpn_gateway_connection = relationship(
        "IBMVpnConnection",
        backref=backref("routing_table_routes", lazy="dynamic"),
    )

    __table_args__ = (UniqueConstraint(name, routing_table_id, name="uix_ibm_route_name_routing_table_id"),)

    def __init__(
            self, resource_id=None, name=None, href=None, created_at=None, action=None,
            lifecycle_state=None, destination=None, next_hop_address_ip=None
    ):
        self.id = str(uuid.uuid4().hex)
        self.resource_id = resource_id
        self.name = name
        self.href = href
        self.created_at = created_at
        self.action = action
        self.lifecycle_state = lifecycle_state
        self.destination = destination
        self.next_hop_address_ip = next_hop_address_ip

    def to_reference_json(self):
        return {
            self.ID_KEY: self.id,
            self.NAME_KEY: self.name,
            self.ZONE_KEY: self.zone.to_reference_json(),
        }

    def to_template_json(self):
        payload = {
            self.ACTION_KEY: self.action,
            self.DESTINATION_KEY: self.destination,
            self.NAME_KEY: self.name,
            self.ZONE_KEY: {self.ID_KEY: self.zone_id}
        }
        if self.next_hop_address_ip:
            payload[self.NEXT_HOP_ADDRESS_IP_KEY] = self.next_hop_address_ip

        if self.next_hop_vpn_gateway_connection.count():  # TODO: uselist=False on this relationship
            payload[self.NEXT_HOP_VPN_GATEWAY_CONNECTION_KEY] = {
                self.ID_KEY: self.next_hop_vpn_gateway_connection[0].id
            }

        return

    def to_json(self):
        return {
            self.ID_KEY: self.id,
            self.RESOURCE_ID_KEY: self.resource_id,
            self.NAME_KEY: self.name,
            self.HREF_KEY: self.href,
            self.CREATED_AT_KEY: self.created_at,
            self.ACTION_KEY: self.action,
            self.LIFECYCLE_STATE_KEY: self.lifecycle_state,
            self.DESTINATION_KEY: self.destination,
            self.NEXT_HOP_ADDRESS_IP_KEY: self.next_hop_address_ip,
            self.NEXT_HOP_VPN_GATEWAY_CONNECTION_KEY:
                self.next_hop_vpn_gateway_connection.to_reference_json()
                if self.next_hop_vpn_gateway_connection else {},
            self.ROUTING_TABLE_KEY: self.routing_table.to_reference_json(),
            self.IBM_CLOUD_KEY: self.ibm_cloud.to_reference_json(),
            self.REGION_KEY: self.region.to_reference_json(),
            self.ZONE_KEY: self.zone.to_reference_json(),
        }

    @classmethod
    def from_ibm_json_body(cls, json_body):
        return cls(
            resource_id=json_body["id"],
            name=json_body["name"],
            href=json_body["href"],
            created_at=return_datetime_object(json_body["created_at"]),
            action=json_body["action"],
            lifecycle_state=json_body["lifecycle_state"],
            destination=json_body["destination"],
            next_hop_address_ip=json_body["next_hop"].get("address"),
        )
