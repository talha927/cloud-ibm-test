import logging
import uuid
from datetime import datetime

from sqlalchemy import BigInteger, Boolean, Column, DateTime, Enum, ForeignKey, String, Text, orm
from sqlalchemy.orm import relationship
from sqlalchemy.schema import UniqueConstraint

from ibm.common.consts import CREATED, CREATED_AT_FORMAT, DUMMY_CLOUD_ID, DUMMY_CLOUD_NAME, DUMMY_REGION_ID, \
    DUMMY_REGION_NAME, DUMMY_ZONE_ID, DUMMY_ZONE_NAME
from ibm.common.utils import return_datetime_object, validate_ip_in_range
from ibm.models.base import Base
from ibm.models.ibm.mixins import IBMZonalResourceMixin

LOGGER = logging.getLogger(__name__)


class IBMSubnet(IBMZonalResourceMixin, Base):
    ID_KEY = "id"
    NAME_KEY = "name"
    REGION_KEY = "region"
    ZONE_KEY = "zone"
    STATUS_KEY = "status"
    IPV4_CIDR_BLOCK = "ipv4_cidr_block"
    ACL_KEY = "network_acl"
    VPC_KEY = "vpc"
    PUBLIC_GATEWAY_KEY = "public_gateway"
    ADDRESS_PREFIX_KEY = "address_prefix"
    VPN_GATEWAYS_KEY = "vpn_gateways"
    NETWORK_INTERFACES_KEY = "network_interfaces"
    LOAD_BALANCERS_KEY = "load_balancers"
    MESSAGE_KEY = "message"
    AVAILABLE_IPV4_ADDRESS_COUNT_KEY = "available_ipv4_address_count"
    AVAILABLE_IPV4_ADDRESSES = "available_ipv4_addresses"
    TOTAL_IPV4_ADDRESS_COUNT_KEY = "total_ipv4_address_count"
    IP_VERSION_KEY = "ip_version"
    CRN_KEY = "crn"
    HREF_KEY = "href"
    RESOURCE_GROUP_KEY = "resource_group"
    ROUTING_TABLE_KEY = "routing_table"
    CREATED_AT_KEY = "created_at"
    ASSOCIATED_RESOURCES_KEY = "associated_resources"
    RESOURCE_JSON_KEY = "resource_json"

    CRZ_BACKREF_NAME = "subnets"

    # IP VERSIONS
    IPV4_VERSION = "ipv4"

    # STATUSES
    STATUS_AVAILABLE = "available"
    STATUS_DELETING = "deleting"
    STATUS_FAILED = "failed"
    STATUS_PENDING = "pending"
    ALL_STATUSES_LIST = [STATUS_AVAILABLE, STATUS_DELETING, STATUS_FAILED, STATUS_PENDING]

    __tablename__ = "ibm_subnets"

    id = Column(String(32), primary_key=True)
    resource_id = Column(String(64), nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow(), nullable=False)
    crn = Column(Text, nullable=False)
    href = Column(Text, nullable=False)
    name = Column(String(255), nullable=False)
    status = Column(String(50), nullable=False)
    available_ipv4_address_count = Column(BigInteger, nullable=False)
    total_ipv4_address_count = Column(BigInteger, nullable=False)
    ip_version = Column(Enum(IPV4_VERSION), default=IPV4_VERSION, nullable=False)
    ipv4_cidr_block = Column(String(255), nullable=False)

    vpc_id = Column(String(32), ForeignKey("ibm_vpc_networks.id", ondelete="CASCADE"))
    network_acl_id = Column(String(32), ForeignKey("ibm_network_acls.id", ondelete="SET NULL"), nullable=True)
    public_gateway_id = Column(String(32), ForeignKey("ibm_public_gateways.id", ondelete="SET NULL"), nullable=True)
    address_prefix_id = Column(String(32), ForeignKey("ibm_address_prefixes.id", ondelete="SET NULL"), nullable=True)
    resource_group_id = Column(String(32), ForeignKey("ibm_resource_groups.id", ondelete="CASCADE"))
    routing_table_id = Column(String(32), ForeignKey("ibm_routing_tables.id", ondelete="CASCADE"))
    instance_group_id = Column(String(32), ForeignKey("ibm_instance_groups.id", ondelete="SET NULL"), nullable=True)

    vpn_gateways = relationship("IBMVpnGateway", backref="subnet", lazy="dynamic", cascade="all, delete-orphan",
                                passive_deletes=True)
    reserved_ips = relationship("IBMSubnetReservedIp", backref="subnet", lazy="dynamic", cascade="all, delete-orphan",
                                passive_deletes=True)

    __table_args__ = (
        UniqueConstraint(name, "cloud_id", vpc_id, "region_id", name="uix_ibm_subnet_name_cloud_id_vpc_id_region_id"),
    )

    def __init__(self, name, ipv4_cidr_block, resource_id=None, status=None,
                 available_ipv4_address_count=None, total_ipv4_address_count=None, ip_version=None, created_at=None,
                 crn=None, href=None):
        self.id = str(uuid.uuid4().hex)
        self.name = name
        self.status = status
        self.ip_version = ip_version
        self.available_ipv4_address_count = available_ipv4_address_count
        self.total_ipv4_address_count = total_ipv4_address_count
        self.ipv4_cidr_block = ipv4_cidr_block
        self.crn = crn
        self.href = href
        self.created_at = created_at
        self.resource_id = resource_id

    def to_reference_json(self):
        return {
            self.ID_KEY: self.id,
            self.NAME_KEY: self.name,
            self.ZONE_KEY: self.zone.to_reference_json() if self.zone else {},
            self.ADDRESS_PREFIX_KEY: self.address_prefix.to_reference_json() if self.address_prefix else {},
            self.IPV4_CIDR_BLOCK: self.ipv4_cidr_block,
        }

    def to_template_json(self):
        resource_json = {
            self.NAME_KEY: self.name,
            self.VPC_KEY: {self.ID_KEY: self.vpc_id},
            self.ZONE_KEY: {self.ID_KEY: self.zone_id},
            self.IPV4_CIDR_BLOCK: self.ipv4_cidr_block,
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
                self.ADDRESS_PREFIX_KEY: self.address_prefix.to_reference_json() if self.address_prefix else {},
                self.IPV4_CIDR_BLOCK: self.ipv4_cidr_block,
            }
        }

    @property
    def available_ip_addresses(self):
        from ibm.web.ibm.subnets.utils import get_available_ip_list_from_cidr
        return get_available_ip_list_from_cidr(
            cloud_id=self.cloud_id, region_name=self.zone.region.name, subnet_resource_id=self.resource_id,
            cidr=self.ipv4_cidr_block
        )

    def to_json(self):
        return {
            self.ID_KEY: self.id,
            self.NAME_KEY: self.name,
            self.IP_VERSION_KEY: self.ip_version,
            self.TOTAL_IPV4_ADDRESS_COUNT_KEY: self.total_ipv4_address_count,
            self.AVAILABLE_IPV4_ADDRESS_COUNT_KEY: self.available_ipv4_address_count,
            self.CREATED_AT_KEY: self.created_at,
            self.IPV4_CIDR_BLOCK: self.ipv4_cidr_block,
            self.STATUS_KEY: self.status,
            self.IBM_CLOUD_KEY: self.ibm_cloud.to_reference_json(),
            self.RESOURCE_GROUP_KEY: self.resource_group.to_reference_json(),
            self.REGION_KEY: self.region.to_reference_json(),
            self.ZONE_KEY: self.zone.to_reference_json(),
            self.ROUTING_TABLE_KEY: self.routing_table.to_reference_json() if self.routing_table else {},
            self.ASSOCIATED_RESOURCES_KEY: {
                self.VPC_KEY: self.vpc_network.to_reference_json(),
                self.ADDRESS_PREFIX_KEY: self.address_prefix.to_reference_json() if self.address_prefix else {},
                self.PUBLIC_GATEWAY_KEY:
                    self.public_gateway.to_reference_json(subnets=False) if self.public_gateway else {},
                self.ACL_KEY: self.network_acl.to_reference_json() if self.network_acl else {},
                self.VPN_GATEWAYS_KEY: [vpn_gateway.to_reference_json() for vpn_gateway in self.vpn_gateways],
                self.NETWORK_INTERFACES_KEY: [
                    network_interface.to_reference_json() for network_interface in self.network_interfaces.all()
                ],
                self.LOAD_BALANCERS_KEY: [
                    load_balancer.to_reference_json() for load_balancer in self.load_balancers.all()
                ]
            }
        }

    def from_softlayer_to_ibm(self):
        resource_json = {
            self.NAME_KEY: self.name,
            self.VPC_KEY: {
                self.ID_KEY: self.vpc_network.id,
            },
            self.ZONE_KEY: {
                "id": DUMMY_ZONE_ID,
                "name": DUMMY_ZONE_NAME
            },
            "ipv4_cidr_block": self.address_prefix.cidr,
        }
        subnet_schema = {
            self.ID_KEY: self.id,
            self.ADDRESS_PREFIX_KEY: self.address_prefix.to_softlayer_reference_json(),
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

        return subnet_schema

    def to_json_body(self):
        obj = {
            "name": self.name,
            "ip_version": "ipv4",
            "ipv4_cidr_block": self.ipv4_cidr_block,
            "zone": {"name": self.zone},
            "vpc": {"id": self.ibm_vpc_network.resource_id} if self.ibm_vpc_network else "",
            "public_gateway": {"id": self.ibm_public_gateway.resource_id} if self.ibm_public_gateway else None,
            "network_acl": {"id": self.network_acl.resource_id} if self.network_acl else None,
        }
        if self.ibm_resource_group:
            obj["resource_group"] = {"id": self.ibm_resource_group.resource_id}
        return obj

    @classmethod
    def from_ibm_json_body(cls, json_body):
        return IBMSubnet(
            name=json_body["name"], ipv4_cidr_block=json_body.get("ipv4_cidr_block"),
            resource_id=json_body["id"],
            status=json_body["status"],
            created_at=datetime.strptime(json_body["created_at"], CREATED_AT_FORMAT),
            available_ipv4_address_count=json_body["available_ipv4_address_count"],
            total_ipv4_address_count=json_body["total_ipv4_address_count"], crn=json_body["crn"], href=json_body["href"]
        )

    @property
    def is_deletable(self):
        # TODO: Add a check for IBMInstanceGroup, IBMVirtualPrivateGateway and, IBMVPNServer
        if self.network_interfaces.count() or self.load_balancers.count() or self.vpn_gateways.count():
            return False

        return True

    def dis_params_eq(self, other):
        assert isinstance(other, self.__class__)

        return (self.name == other.name and self.status == other.status and self.resource_id == other.resource_id and
                self.ipv4_cidr_block == other.ipv4_cidr_block)

    def dis_add_update_db(self, session, db_subnets, cloud_id, vpc_network_id, public_gateway_id, network_acl_id,
                          resource_group_id, db_zone, routing_table_id):

        from ibm.models import IBMCloud, IBMVpcNetwork, IBMNetworkAcl, IBMPublicGateway, IBMResourceGroup, \
            IBMAddressPrefix, IBMRoutingTable

        db_public_gateway = \
            session.query(IBMPublicGateway).filter_by(
                resource_id=public_gateway_id, cloud_id=cloud_id
            ).first()

        db_network_acl = \
            session.query(IBMNetworkAcl).filter_by(
                resource_id=network_acl_id, cloud_id=cloud_id
            ).first()

        db_vpc_network = \
            session.query(IBMVpcNetwork).filter_by(
                cloud_id=cloud_id, resource_id=vpc_network_id
            ).first()

        db_resource_group = session.query(IBMResourceGroup).filter_by(cloud_id=cloud_id,
                                                                      resource_id=resource_group_id).first()

        db_routing_table = session.query(IBMRoutingTable).filter_by(cloud_id=cloud_id,
                                                                    resource_id=routing_table_id).first()
        if not db_routing_table:
            LOGGER.info(
                f"Provided IBMRoutingTable with Resource ID: "
                f"{routing_table_id}, "
                f"Cloud ID: {cloud_id} and Region: {db_zone.region} while inserting "
                f"IBMSubnet not found in DB.")
            return

        if not (db_vpc_network and db_resource_group):
            return

        db_address_prefixes = session.query(IBMAddressPrefix).filter_by(vpc_id=db_vpc_network.id).all()
        existing = None
        for db_subnet in db_subnets:
            if self.resource_id == db_subnet.resource_id:
                existing = db_subnet
                break

            params_eq = (self.name == db_subnet.name and self.zone == db_subnet.zone and self.region ==
                         db_subnet.region and self.ipv4_cidr_block == db_subnet.ipv4_cidr_block and
                         db_subnet.ibm_vpc_network and db_subnet.ibm_vpc_network.resource_id == vpc_network_id)

            if params_eq:
                existing = db_subnet
                break

        if not existing:
            cloud = session.query(IBMCloud).get(cloud_id)
            assert cloud

            self.vpc_network = db_vpc_network
            self.ibm_cloud = cloud
            self.public_gateway = db_public_gateway
            self.resource_group = db_resource_group
            self.network_acl = db_network_acl
            self.routing_table = db_routing_table
            self.address_prefix = self.get_subnet_address_prefix(db_address_prefixes)
            self.zone = db_zone
            session.commit()
            return

        if not self.dis_params_eq(existing):
            existing.update_from_object(self)

            existing.vpc_network = db_vpc_network
            existing.public_gateway = db_public_gateway
            existing.network_acl = db_network_acl
            existing.resource_group = db_resource_group
            existing.routing_table = db_routing_table
            existing.address_prefix = self.get_subnet_address_prefix(db_address_prefixes)
            existing.zone = db_zone

        session.commit()

    def update_from_object(self, other):
        assert isinstance(other, self.__class__)

        self.name = other.name
        self.status = other.status
        self.resource_id = other.resource_id
        self.ipv4_cidr_block = other.ipv4_cidr_block

    def get_subnet_address_prefix(self, address_prefixes):
        for address_prefix in address_prefixes:
            if not address_prefix.resource_id:
                continue
            subnet_address_prefix = validate_ip_in_range(self.ipv4_cidr_block, address_prefix.cidr)
            if subnet_address_prefix:
                return address_prefix
        return None


class IBMSubnetReservedIp(Base):
    ID_KEY = "id"
    ADDRESS_KEY = "address"
    HREF_KEY = "href"
    NAME_KEY = "name"
    RESOURCE_TYPE_KEY = "resource_type"
    SUBNET_KEY = "subnet"
    ENDPOINT_GATEWAY_KEY = "endpoint_gateway"
    OWNER_KEY = "owner"
    STATUS_KEY = "status"

    # owner/management type
    TYPE_USER = "user"
    TYPE_PROVIDER = "provider"
    TYPES_LIST = [TYPE_USER, TYPE_PROVIDER]

    RESOURCE_TYPE_SUBNET_RESERVED_IP = "subnet_reserved_ip"

    __tablename__ = "ibm_subnet_reserved_ips"

    id = Column(String(32), primary_key=True)
    address = Column(String(55), nullable=False)
    auto_delete = Column(Boolean, nullable=False, default=True)
    created_at = Column(DateTime, nullable=False)
    href = Column(Text, nullable=False)
    resource_id = Column(String(64), nullable=False)
    name = Column(String(255), nullable=False)
    status = Column(String(50), nullable=False)
    owner = Column(Enum(*TYPES_LIST))
    resource_type = Column(Enum(RESOURCE_TYPE_SUBNET_RESERVED_IP), nullable=False,
                           default=RESOURCE_TYPE_SUBNET_RESERVED_IP)

    subnet_id = Column(String(32), ForeignKey("ibm_subnets.id", ondelete="CASCADE"))
    target_id = Column(String(32), ForeignKey("ibm_endpoint_gateways.id", ondelete="SET NULL"), nullable=True)

    def __init__(self, address, href, resource_id, name, resource_type, auto_delete=None, created_at=None, owner=None,
                 status=CREATED):
        self.id = str(uuid.uuid4().hex)
        self.address = address
        self.href = href
        self.resource_id = resource_id
        self.name = name
        self.resource_type = resource_type
        self.auto_delete = auto_delete
        self.owner = owner
        self.created_at = created_at or datetime.utcnow()
        self.status = status

    def to_reference_json(self):
        return {
            self.ID_KEY: self.id,
            self.NAME_KEY: self.name,
        }

    def to_json(self):
        return {
            self.ID_KEY: self.id,
            self.ADDRESS_KEY: self.address,
            self.HREF_KEY: self.href,
            self.NAME_KEY: self.name,
            self.STATUS_KEY: self.status,
            self.RESOURCE_TYPE_KEY: self.resource_type,
            self.OWNER_KEY: self.owner,
            self.SUBNET_KEY: self.subnet.to_reference_json(),
            self.ENDPOINT_GATEWAY_KEY: self.endpoint_gateway.to_reference_json() if self.endpoint_gateway else {}
        }

    @classmethod
    def from_ibm_json_body(cls, json_body):
        return IBMSubnetReservedIp(
            address=json_body["address"], auto_delete=json_body.get("auto_delete"),
            created_at=return_datetime_object(json_body["created_at"]) if json_body.get("created_at") else None,
            href=json_body["href"], resource_id=json_body["id"], name=json_body["name"],
            resource_type=json_body["resource_type"], owner=json_body.get("owner")
        )

    def dis_params_eq(self, other):
        assert isinstance(other, self.__class__)

        return (self.address == other.address and self.href == other.href and self.resource_id == other.resource_id and
                self.name == other.name and self.auto_delete == other.auto_delete and self.owner == other.owner)

    def dis_add_update_db(self, session, db_subnet_reserved_ip, db_subnet):
        existing = db_subnet_reserved_ip or None
        try:
            if not existing:
                self.subnet = db_subnet
                session.add(self)
                session.commit()
                return
        except orm.exc.ObjectDeletedError as ex:
            LOGGER.warning(ex)
            return

        try:
            if not self.dis_params_eq(existing):
                existing.update_from_object(self)
                existing.subnet = db_subnet
        except orm.exc.ObjectDeletedError as ex:
            LOGGER.warning(ex)
            return

        session.commit()

    def update_from_object(self, other):
        assert isinstance(other, self.__class__)

        self.address = other.address
        self.href = other.href
        self.resource_id = other.resource_id
        self.name = other.name
        self.auto_delete = other.auto_delete
        self.owner = other.owner
