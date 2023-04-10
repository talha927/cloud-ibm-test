import logging
import uuid
from datetime import datetime

from sqlalchemy import Boolean, Column, DateTime, Enum, ForeignKey, Integer, orm, String, Text
from sqlalchemy.orm import relationship
from sqlalchemy.schema import UniqueConstraint

from ibm.common.consts import CREATED, CREATED_AT_FORMAT, DUMMY_CLOUD_ID, DUMMY_CLOUD_NAME, DUMMY_REGION_ID, \
    DUMMY_REGION_NAME, DUMMY_RESOURCE_GROUP_ID, DUMMY_RESOURCE_GROUP_NAME
from ibm.models.base import Base
from ibm.models.ibm.mixins import IBMRegionalResourceMixin

LOGGER = logging.getLogger(__name__)


class IBMSecurityGroup(IBMRegionalResourceMixin, Base):
    ID_KEY = "id"
    RESOURCE_ID_KEY = "resource_id"
    NAME_KEY = "name"
    IS_DEFAULT_KEY = "is_default"
    STATUS_KEY = "status"
    CRN_KEY = "crn"
    HREF_KEY = "href"
    CREATED_AT_KEY = "created_at"
    RULES_KEY = "rules"
    RESOURCE_GROUP_KEY = "resource_group"
    VPC_KEY = "vpc"
    TARGET_KEY = "target"
    ASSOCIATED_RESOURCES_KEY = "associated_resources"
    RESOURCE_JSON_KEY = "resource_json"
    NETWORK_INTERFACE_KEY = "network_interface"

    CRZ_BACKREF_NAME = "security_groups"

    __tablename__ = "ibm_security_groups"

    id = Column(String(32), primary_key=True)
    resource_id = Column(String(64), nullable=False)
    name = Column(String(255), nullable=False)
    is_default = Column(Boolean, default=False, nullable=False)
    status = Column(String(50), nullable=False)
    crn = Column(String(255), nullable=False)
    href = Column(Text, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow(), nullable=False)

    vpc_id = Column(String(32), ForeignKey("ibm_vpc_networks.id", ondelete="CASCADE"))
    resource_group_id = Column(String(32), ForeignKey("ibm_resource_groups.id", ondelete="SET NULL"), nullable=True)

    rules = relationship(
        "IBMSecurityGroupRule",
        backref="security_group",
        lazy="dynamic",
        cascade="all, delete-orphan",
        passive_deletes=True,
        foreign_keys="[IBMSecurityGroupRule.security_group_id]"
    )

    __table_args__ = (UniqueConstraint(name, vpc_id, "region_id", name="uix_ibm_security_group_name_vpc_id_region_id"),)

    def __init__(self, name, crn, href, created_at, resource_id, is_default=False, status=None,
                 cloud_id=None, vpc_id=None):
        self.id = str(uuid.uuid4().hex)
        self.name = name
        self.crn = crn
        self.href = href
        self.created_at = created_at
        self.resource_id = resource_id
        self.is_default = is_default
        self.status = status if status else CREATED
        self.cloud_id = cloud_id
        self.vpc_id = vpc_id

    @property
    def is_allow_all(self):
        allow_all_rules = [rule.is_inbound_allow_all and rule.is_outbound_allow_all for rule in self.rules.all()]
        return len(allow_all_rules) >= 2

    def to_reference_json(self):
        return {
            self.ID_KEY: self.id,
            self.NAME_KEY: self.name,
            self.RESOURCE_GROUP_KEY: self.resource_group.to_reference_json(),
        }

    def validate_json_for_schema(self):
        return {
            self.ID_KEY: self.id,
            self.RESOURCE_JSON_KEY: {
                self.NAME_KEY: self.name,
                self.RESOURCE_GROUP_KEY: self.resource_group.to_reference_json(),
            }
        }

    @property
    def __instance_ids(self):
        return [network_interface.instance_id for network_interface in self.network_interfaces.all()]

    @property
    def __instances_with_network_interfaces(self):
        instances = []
        for instance_id in self.__instance_ids:
            network_interfaces = self.network_interfaces.filter_by(instance_id=instance_id).all()
            instances.append({
                "id": instance_id,
                "network_interfaces": [net_int.to_reference_json() for net_int in network_interfaces]
            })

        return instances

    @property
    def target(self):
        json_data = {}

        if self.load_balancers.count():
            json_data["load_balancers"] = [lb.to_reference_json() for lb in self.load_balancers.all()]

        if self.endpoint_gateways.count():
            json_data["endpoint_gateways"] = [gateway.to_reference_json() for gateway in self.endpoint_gateways.all()]

        if self.__instances_with_network_interfaces:
            json_data["instances"] = self.__instances_with_network_interfaces

        return json_data

    def to_json(self):
        json_data = {
            self.ID_KEY: self.id,
            self.RESOURCE_ID_KEY: self.resource_id,
            self.NAME_KEY: self.name,
            self.IS_DEFAULT_KEY: self.is_default,
            self.STATUS_KEY: self.status,
            self.CRN_KEY: self.crn,
            self.HREF_KEY: self.href,
            self.CREATED_AT_KEY: self.created_at,
            self.RULES_KEY: [rule.to_json() for rule in self.rules.all()],
            self.IBM_CLOUD_KEY: self.ibm_cloud.to_reference_json(),
            self.RESOURCE_GROUP_KEY: self.resource_group.to_reference_json(),
            self.REGION_KEY: self.region.to_reference_json(),
            self.ASSOCIATED_RESOURCES_KEY: {
                self.VPC_KEY: self.vpc_network.to_reference_json(),
            }
        }
        if self.target:
            json_data[self.TARGET_KEY] = self.target

        return json_data

    def to_template_json(self):
        resource_json = {
            self.NAME_KEY: self.name,
            self.REGION_KEY: {
                self.ID_KEY: self.region_id,
            },
            self.RESOURCE_GROUP_KEY: {
                self.ID_KEY: self.resource_group_id,
            },
            self.VPC_KEY: {self.ID_KEY: self.vpc_network.id},
            self.RULES_KEY: [rule.to_template_json() for rule in self.rules.all()]
        }
        security_group_schema = {
            self.RESOURCE_JSON_KEY: resource_json,
            self.ID_KEY: self.id,
            self.NETWORK_INTERFACE_KEY: [{
                self.ID_KEY: network_interface.id,
                self.NAME_KEY: network_interface.name
            }
                for network_interface in self.network_interfaces.all()],
            self.IBM_CLOUD_KEY: {
                self.ID_KEY: self.cloud_id,
            },
            self.REGION_KEY: {
                self.ID_KEY: self.region_id,
            },
        }

        return security_group_schema

    def from_softlayer_to_ibm(self):
        resource_json = {
            self.NAME_KEY: self.name,
            self.REGION_KEY: {
                self.ID_KEY: DUMMY_REGION_ID, self.NAME_KEY: DUMMY_REGION_NAME
            },
            self.RESOURCE_GROUP_KEY: {
                self.ID_KEY: DUMMY_RESOURCE_GROUP_ID, self.NAME_KEY: DUMMY_RESOURCE_GROUP_NAME
            },
            self.VPC_KEY: {self.ID_KEY: self.vpc_network.id},
            self.RULES_KEY: [rule.from_softlayer_to_ibm() for rule in self.rules.all()]
        }
        security_group_schema = {
            self.NETWORK_INTERFACE_KEY: [{
                self.ID_KEY: network_interface.id,
                self.NAME_KEY: network_interface.name
            }
                for network_interface in self.network_interfaces.all()],
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

        return security_group_schema

    @property
    def is_deletable(self):
        # TODO: Add a check for IBMVPNServer
        if self.network_interfaces.count() or self.load_balancers.count() or self.endpoint_gateways.count():
            return False

        return True

    def to_json_body(self):
        return {
            "name": self.name,
            "vpc": {
                "id": self.ibm_vpc_network.resource_id if self.ibm_vpc_network else None
            },
            "rules": [rule.to_json_body() for rule in self.rules.all()],
            "resource_group": {
                "id": self.ibm_resource_group.resource_id
                if self.ibm_resource_group
                else ""
            },
        }

    def dis_params_eq(self, other):
        assert isinstance(other, self.__class__)

        return self.name == other.name and self.resource_id == other.resource_id

    def dis_add_update_db(self, session, db_security_groups, db_vpc_network, db_cloud, db_resource_group, db_region,
                          db_network_interface=None, db_vpe=None, db_load_balancer=None):
        if not (db_vpc_network and db_resource_group):
            return

        db_security_groups_id_obj_dict = dict()
        db_security_groups_name_obj_dict = dict()
        for db_security_group in db_security_groups:
            try:
                db_security_groups_id_obj_dict[db_security_group.resource_id] = db_security_group
                db_security_groups_name_obj_dict[db_security_group.name] = db_security_group
            except orm.exc.ObjectDeletedError as ex:
                LOGGER.warning(ex)

        if self.resource_id not in db_security_groups_id_obj_dict and self.name in db_security_groups_name_obj_dict:
            # Creation Pending / Creating
            existing = db_security_groups_name_obj_dict[self.name]
        elif self.resource_id in db_security_groups_id_obj_dict:
            # Created. Update everything including name
            existing = db_security_groups_id_obj_dict[self.resource_id]
        else:
            existing = None

        try:
            if not existing:
                self.ibm_cloud = db_cloud
                self.resource_group = db_resource_group
                self.vpc_network = db_vpc_network
                self.network_interfaces = db_network_interface
                self.endpoint_gateways = db_vpe
                self.region = db_region
                session.add(self)
                session.commit()
                return
        except orm.exc.ObjectDeletedError as ex:
            LOGGER.warning(ex)
            return

        try:
            if not self.dis_params_eq(existing):
                existing.update_from_object(self)
                existing.resource_group = db_resource_group
                existing.region = db_region
        except orm.exc.ObjectDeletedError as ex:
            LOGGER.warning(ex)

        session.commit()

    def update_from_object(self, other):
        assert isinstance(other, self.__class__)

        self.name = other.name
        self.crn = other.crn
        self.href = other.href
        self.resource_id = other.resource_id
        self.is_default = other.is_default
        self.status = other.status

    @classmethod
    def from_ibm_json_body(cls, json_body):
        ibm_security_group = cls(
            name=json_body["name"], resource_id=json_body["id"], status=CREATED, href=json_body["href"],
            crn=json_body["crn"], created_at=datetime.strptime(json_body["created_at"], CREATED_AT_FORMAT)
        )

        for rule in json_body["rules"]:
            ibm_security_group.rules.append(IBMSecurityGroupRule.from_ibm_json_body(rule))

        return ibm_security_group


class IBMSecurityGroupRule(Base):
    ID_KEY = "id"
    RESOURCE_ID_KEY = "resource_id"
    STATUS_KEY = "status"
    DIRECTION_KEY = "direction"
    HREF_KEY = "href"
    RULE_TYPE_KEY = "rule_type"
    PROTOCOL_KEY = "protocol"
    IP_VERSION_KEY = "ip_version"
    PORT_MIN_KEY = "port_min"
    PORT_MAX_KEY = "port_max"
    CODE_KEY = "code"
    TYPE_KEY = "type"
    REMOTE_KEY = "remote"
    SECURITY_GROUP_KEY = "security_group"

    # rule type consts
    RULE_TYPE_ADDRESS = "address"
    RULE_TYPE_ANY = "any"
    RULE_TYPE_CIDR_BLOCK = "cidr_block"
    RULE_TYPE_SECURITY_GROUP = "security_group"
    RULE_TYPES_LIST = [RULE_TYPE_ADDRESS, RULE_TYPE_ANY, RULE_TYPE_CIDR_BLOCK, RULE_TYPE_SECURITY_GROUP]

    # protocol consts
    PROTOCOL_ALL = "all"
    PROTOCOL_ICMP = "icmp"
    PROTOCOL_UDP = "udp"
    PROTOCOL_TCP = "tcp"
    PROTOCOLS_LIST = [PROTOCOL_ALL, PROTOCOL_ICMP, PROTOCOL_UDP, PROTOCOL_TCP]

    # ip version type
    IP_VERSION_IPV4 = "ipv4"

    # security group direction
    DIRECTION_INBOUND = "inbound"
    DIRECTION_OUTBOUND = "outbound"
    DIRECTIONS_LIST = [
        DIRECTION_INBOUND, DIRECTION_OUTBOUND
    ]

    __tablename__ = "ibm_security_group_rules"

    id = Column(String(32), primary_key=True)
    resource_id = Column(String(64), nullable=False)
    status = Column(String(50), nullable=False)
    direction = Column(Enum(DIRECTION_INBOUND, DIRECTION_OUTBOUND), nullable=False)
    href = Column(Text, nullable=False)
    rule_type = Column(
        Enum(RULE_TYPE_ADDRESS, RULE_TYPE_ANY, RULE_TYPE_CIDR_BLOCK, RULE_TYPE_SECURITY_GROUP),
        default=RULE_TYPE_ANY, nullable=False
    )
    protocol = Column(Enum(PROTOCOL_ALL, PROTOCOL_ICMP, PROTOCOL_TCP, PROTOCOL_UDP), nullable=False)
    remote_cidr_block = Column(String(255))
    remote_ip_address = Column(String(255))
    ip_version = Column(Enum(IP_VERSION_IPV4))
    port_min = Column(Integer)
    port_max = Column(Integer)
    code = Column(Integer)
    type_ = Column("type", Integer)

    security_group_id = Column(String(32), ForeignKey("ibm_security_groups.id", ondelete="CASCADE"))
    remote_security_group_id = Column(String(32), ForeignKey("ibm_security_groups.id", ondelete="SET NULL"),
                                      nullable=True)

    remote_security_group = relationship("IBMSecurityGroup", backref="remote_security_group",
                                         foreign_keys=[remote_security_group_id])

    def __init__(
            self, direction, href, ip_version, protocol=None, code=None, type_=None, port_min=None,
            port_max=None, remote_ip_address=None, remote_cidr_block=None, rule_type=None, resource_id=None,
            status=CREATED
    ):
        self.id = str(uuid.uuid4().hex)
        self.direction = direction
        self.href = href
        self.ip_version = ip_version
        self.protocol = protocol
        self.code = code
        self.type_ = type_
        self.port_min = port_min
        self.port_max = port_max
        self.remote_ip_address = remote_ip_address
        self.remote_cidr_block = remote_cidr_block
        self.rule_type = rule_type
        self.resource_id = resource_id
        self.status = status

    @property
    def _is_allow_all(self):
        return self.protocol == self.PROTOCOL_ALL and self.rule_type == self.RULE_TYPE_ANY

    @property
    def is_inbound_allow_all(self):
        return self.direction == self.DIRECTION_INBOUND and self._is_allow_all

    @property
    def is_outbound_allow_all(self):
        return self.direction == self.DIRECTION_OUTBOUND and self._is_allow_all

    def to_reference_json(self):
        return {
            self.ID_KEY: self.id,
        }

    def to_json(self, parent_reference=True):
        json_data = {
            self.ID_KEY: self.id,
            self.RESOURCE_ID_KEY: self.resource_id,
            self.STATUS_KEY: self.status,
            self.DIRECTION_KEY: self.direction,
            self.HREF_KEY: self.href,
            self.RULE_TYPE_KEY: self.rule_type,
            self.PROTOCOL_KEY: self.protocol,
            self.IP_VERSION_KEY: self.ip_version,
            self.PORT_MIN_KEY: self.port_min,
            self.PORT_MAX_KEY: self.port_max,
            self.CODE_KEY: self.code,
            self.TYPE_KEY: self.type_,
            self.REMOTE_KEY: dict()
        }
        if self.rule_type == self.RULE_TYPE_SECURITY_GROUP:
            json_data[self.REMOTE_KEY][self.RULE_TYPE_SECURITY_GROUP] = self.remote_security_group.to_reference_json() \
                if self.remote_security_group else {}

        elif self.remote_cidr_block:
            json_data[self.REMOTE_KEY] = {self.RULE_TYPE_CIDR_BLOCK: self.remote_cidr_block}

        elif self.remote_ip_address:
            json_data[self.REMOTE_KEY] = {self.RULE_TYPE_ADDRESS: self.remote_ip_address}

        if parent_reference:
            json_data[self.SECURITY_GROUP_KEY] = self.security_group.to_reference_json()

        return json_data

    def to_json_body(self):
        json_data = {
            self.DIRECTION_KEY: self.direction,
            self.IP_VERSION_KEY: self.IP_VERSION_IPV4,
            self.PROTOCOL_KEY: self.protocol,
        }

        if self.protocol in [self.PROTOCOL_TCP, self.PROTOCOL_UDP]:
            json_data[self.PORT_MAX_KEY] = self.port_max
            json_data[self.PORT_MIN_KEY] = self.port_min

        elif self.protocol == self.PROTOCOL_ICMP:
            json_data[self.CODE_KEY] = self.code
            json_data[self.TYPE_KEY] = self.type_

        if self.rule_type == self.RULE_TYPE_SECURITY_GROUP:
            json_data[self.REMOTE_KEY] = {
                self.ID_KEY: self.remote_security_group.resource_id} if self.remote_security_group else {}

        elif self.remote_cidr_block:
            json_data[self.REMOTE_KEY] = {self.RULE_TYPE_CIDR_BLOCK: self.remote_cidr_block}

        elif self.remote_ip_address:
            json_data[self.REMOTE_KEY] = {self.RULE_TYPE_ADDRESS: self.remote_ip_address}

        return json_data

    def to_template_json(self):
        resource_json = {
            self.ID_KEY: self.id,
            self.DIRECTION_KEY: self.direction,
            self.PROTOCOL_KEY: self.protocol,
            self.IP_VERSION_KEY: self.ip_version,
        }

        if self.code:
            resource_json[self.CODE_KEY] = self.code

        if self.type_:
            resource_json[self.TYPE_KEY] = self.type_

        if self.port_max:
            resource_json[self.PORT_MAX_KEY] = self.port_max

        if self.port_min:
            resource_json[self.PORT_MIN_KEY] = self.port_min

        if self.rule_type == self.RULE_TYPE_SECURITY_GROUP and self.remote_security_group:
            resource_json[self.REMOTE_KEY] = {}
            resource_json[self.REMOTE_KEY][
                self.RULE_TYPE_SECURITY_GROUP] = self.remote_security_group.to_reference_json()

        elif self.remote_cidr_block:
            resource_json[self.REMOTE_KEY] = {self.RULE_TYPE_CIDR_BLOCK: self.remote_cidr_block}

        elif self.remote_ip_address:
            resource_json[self.REMOTE_KEY] = {self.RULE_TYPE_ADDRESS: self.remote_ip_address}

        return resource_json

    def from_softlayer_to_ibm(self):
        resource_json = {
            self.ID_KEY: self.id,
            self.DIRECTION_KEY: self.direction,
            self.PROTOCOL_KEY: self.protocol,
        }

        if self.protocol is not self.PROTOCOL_ALL:
            if self.protocol is self.PROTOCOL_ICMP:
                if self.code:
                    resource_json[self.CODE_KEY] = self.code

                if self.type_:
                    resource_json[self.TYPE_KEY] = self.type_

            if self.protocol in [self.PROTOCOL_TCP, self.PROTOCOL_UDP]:
                if self.port_max:
                    resource_json[self.PORT_MAX_KEY] = self.port_max

                if self.port_min:
                    resource_json[self.PORT_MIN_KEY] = self.port_min

        if self.rule_type == self.RULE_TYPE_SECURITY_GROUP:
            resource_json[self.REMOTE_KEY][
                self.RULE_TYPE_SECURITY_GROUP] = self.remote_security_group.to_reference_json() \
                if self.remote_security_group else {}

        elif self.remote_cidr_block:
            resource_json[self.REMOTE_KEY] = {self.RULE_TYPE_CIDR_BLOCK: self.remote_cidr_block}

        elif self.remote_ip_address:
            resource_json[self.REMOTE_KEY] = {self.RULE_TYPE_ADDRESS: self.remote_ip_address}

        return resource_json

    @classmethod
    def from_ibm_json_body(cls, json_body):
        ibm_security_group_rule = IBMSecurityGroupRule(
            direction=json_body["direction"],
            href=json_body["href"],
            ip_version=json_body["ip_version"],
            protocol=json_body.get("protocol", cls.PROTOCOL_ALL),
            resource_id=json_body.get("id"),
            remote_ip_address=json_body["remote"].get("address"),
            remote_cidr_block=json_body["remote"].get("cidr_block"),
            status="CREATED"
        )

        if ibm_security_group_rule.protocol == cls.PROTOCOL_ICMP:
            ibm_security_group_rule.type_ = json_body.get("type")
            if ibm_security_group_rule.type_:
                ibm_security_group_rule.code = json_body.get("code")

        elif ibm_security_group_rule.protocol in [cls.PROTOCOL_TCP, cls.PROTOCOL_UDP]:
            ibm_security_group_rule.port_min = json_body.get("port_min")
            ibm_security_group_rule.port_max = json_body.get("port_max")

        # any or cidr block
        if json_body["remote"].get("cidr_block"):
            cidr_block = json_body["remote"]["cidr_block"]
            ibm_security_group_rule.rule_type = \
                cls.RULE_TYPE_ANY if cidr_block == "0.0.0.0/0" else cls.RULE_TYPE_CIDR_BLOCK
            ibm_security_group_rule.remote_cidr_block = cidr_block
        elif json_body["remote"].get("address"):
            ibm_security_group_rule.rule_type = cls.RULE_TYPE_ADDRESS
            ibm_security_group_rule.remote_ip_address = json_body["remote"]["address"]
        elif json_body["remote"].get("name"):
            ibm_security_group_rule.rule_type = cls.RULE_TYPE_SECURITY_GROUP

        return ibm_security_group_rule
