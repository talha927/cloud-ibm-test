import uuid
from datetime import datetime

from sqlalchemy import Boolean, Column, DateTime, Enum, ForeignKey, Integer, String, Text
from sqlalchemy.orm import backref, relationship
from sqlalchemy.schema import UniqueConstraint

from ibm.common.consts import CREATED, CREATED_AT_FORMAT, DUMMY_CLOUD_ID, DUMMY_CLOUD_NAME, DUMMY_REGION_ID, \
    DUMMY_REGION_NAME
from ibm.models.base import Base
from ibm.models.ibm.mixins import IBMRegionalResourceMixin


class IBMNetworkAcl(IBMRegionalResourceMixin, Base):
    ID_KEY = "id"
    RESOURCE_ID_KEY = "resource_id"
    CREATED_AT_KEY = "created_at"
    CRN_KEY = "crn"
    HREF_KEY = "href"
    NAME_KEY = "name"
    STATUS_KEY = "status"
    IS_DEFAULT_KEY = "is_default"
    RESOURCE_GROUP_KEY = "resource_group"
    VPC_KEY = "vpc"
    RULES_KEY = "rules"
    SUBNETS_KEY = "subnets"
    ASSOCIATED_RESOURCES_KEY = "associated_resources"
    RESOURCE_JSON_KEY = "resource_json"

    CRZ_BACKREF_NAME = "network_acls"

    __tablename__ = "ibm_network_acls"

    id = Column(String(32), primary_key=True)
    resource_id = Column(String(64), nullable=False)
    created_at = Column(DateTime, nullable=False)
    crn = Column(String(255), nullable=False)
    href = Column(Text, nullable=False)
    name = Column(String(255), nullable=False)
    status = Column(String(50), nullable=False)
    is_default = Column(Boolean, default=False, nullable=False)

    resource_group_id = Column(String(32), ForeignKey("ibm_resource_groups.id", ondelete="CASCADE"))
    vpc_id = Column(String(32), ForeignKey("ibm_vpc_networks.id", ondelete="CASCADE"))

    rules = relationship("IBMNetworkAclRule", backref="network_acl", cascade="all, delete-orphan",
                         passive_deletes=True, lazy="dynamic")
    subnets = relationship("IBMSubnet", backref="network_acl", lazy="dynamic")

    __table_args__ = (
        UniqueConstraint(name, "region_id", vpc_id, "cloud_id", name="uix_ibm_acl_name_vpc_region_id_cloud_id"),
    )

    def __init__(self, name, crn, href, created_at=None, resource_id=None, is_default=False,
                 status=CREATED):
        self.id = str(uuid.uuid4().hex)
        self.name = name
        self.is_default = is_default
        self.created_at = created_at or datetime.utcnow()
        self.crn = crn
        self.href = href
        self.resource_id = resource_id
        self.status = status or CREATED

    def to_reference_json(self):
        return {
            self.ID_KEY: self.id,
            self.NAME_KEY: self.name,
            self.IS_DEFAULT_KEY: self.is_default,
        }

    def validate_json_for_schema(self):
        return {
            self.ID_KEY: self.id,
            self.RESOURCE_JSON_KEY: {
                self.NAME_KEY: self.name,
                self.IS_DEFAULT_KEY: self.is_default,
            }
        }

    def to_json(self):
        return {
            self.ID_KEY: self.id,
            self.RESOURCE_ID_KEY: self.resource_id,
            self.CREATED_AT_KEY: self.created_at,
            self.CRN_KEY: self.crn,
            self.HREF_KEY: self.href,
            self.NAME_KEY: self.name,
            self.STATUS_KEY: self.status,
            self.IS_DEFAULT_KEY: self.is_default,
            self.RULES_KEY: [rule.to_json(parent_reference=False) for rule in self.rules.all()],
            self.IBM_CLOUD_KEY: self.ibm_cloud.to_reference_json(),
            self.RESOURCE_GROUP_KEY: self.resource_group.to_reference_json(),
            self.REGION_KEY: self.region.to_reference_json(),
            self.ASSOCIATED_RESOURCES_KEY: {
                self.VPC_KEY: self.vpc_network.to_reference_json(),
                self.SUBNETS_KEY: [subnet.to_reference_json() for subnet in self.subnets.all()]
            }
        }

    def to_template_json(self):
        resource_json = {
            self.NAME_KEY: self.name,
            self.RULES_KEY: [rule.to_template_json() for rule in self.rules.all()],
            self.VPC_KEY: {self.ID_KEY: self.vpc_network.id if self.vpc_network else None},
            self.SUBNETS_KEY: [{self.ID_KEY: subnet.id} for subnet in self.subnets.all()],
            self.RESOURCE_GROUP_KEY: {
                self.ID_KEY: self.resource_group.id,
                self.NAME_KEY: self.resource_group.name,
            }
        }

        acl_schema = {
            self.RESOURCE_JSON_KEY: resource_json,
            self.ID_KEY: self.id,
            self.IBM_CLOUD_KEY: {
                self.ID_KEY: self.cloud_id,
            },
            self.REGION_KEY: {
                self.ID_KEY: self.region_id,
            }
        }

        return acl_schema

    def from_softlayer_to_ibm(self):
        resource_json = {
            self.NAME_KEY: self.name,
            self.IS_DEFAULT_KEY: self.is_default,
            self.RULES_KEY: [rule.from_softlayer_to_ibm() for rule in self.rules.all()],
            self.VPC_KEY: {
                self.ID_KEY: self.vpc_network.id if self.vpc_network else None,
            },
            self.SUBNETS_KEY: [{
                self.ID_KEY: subnet.id,
                self.NAME_KEY: subnet.name,
            } for subnet in self.subnets.all()]

        }
        acl_schema = {
            self.ID_KEY: self.id,
            "resource_json": resource_json,
            "ibm_cloud": {
                self.ID_KEY: DUMMY_CLOUD_ID,
                self.NAME_KEY: DUMMY_CLOUD_NAME,
            },
            self.REGION_KEY: {
                self.ID_KEY: DUMMY_REGION_ID,
                self.NAME_KEY: DUMMY_REGION_NAME,
            }
        }

        return acl_schema

    @property
    def is_deletable(self):
        return not self.subnets.count()

    def to_json_body(self):
        obj = {
            "name": self.name,
            "rules": [rule.to_json_body() for rule in self.rules.all()],
            "vpc": {
                "id": self.vpc_network.resource_id if self.vpc_network else ""
            },
        }
        if self.ibm_resource_group:
            obj["resource_group"] = {"id": self.ibm_resource_group.resource_id}
        return obj

    @classmethod
    def from_ibm_json_body(cls, json_body):
        # TODO: Check schema. Investigate resource_id = None for rules
        ibm_network_acl = cls(
            name=json_body["name"], href=json_body["href"], crn=json_body["crn"],
            resource_id=json_body["id"], status="CREATED",
            created_at=datetime.strptime(json_body["created_at"], CREATED_AT_FORMAT)
        )
        for rule in json_body.get("rules", []):
            ibm_network_acl.rules.append(IBMNetworkAclRule.from_ibm_json_body(rule))

        return ibm_network_acl

    def dis_params_eq(self, other):
        assert isinstance(other, self.__class__)

        return (self.name == other.name and self.resource_id == other.resource_id and
                self.is_default == other.is_default and self.status == other.status)

    def dis_add_update_db(self, session, db_network_acl, cloud_id, vpc_network_id, resource_group_id, db_region):
        from ibm.models import IBMVpcNetwork, IBMResourceGroup
        vpc_network = session.query(IBMVpcNetwork).filter_by(cloud_id=cloud_id, resource_id=vpc_network_id).first()
        resource_group = session.query(IBMResourceGroup).filter_by(resource_id=resource_group_id).first()

        if not (vpc_network and resource_group):
            return

        existing = db_network_acl or None

        if not existing:
            self.ibm_cloud = vpc_network.ibm_cloud
            self.resource_group = resource_group
            self.region = db_region

            vpc_network.acls.append(self)
            session.commit()
            return

        if not self.dis_params_eq(existing):
            existing.update_from_object(self)

        existing.resource_group = resource_group
        existing.region = db_region
        session.commit()

        updated_acl_rules_ids = [updated_acl_rule.resource_id for updated_acl_rule in self.rules.all()]
        for rule in existing.rules.all():
            if rule.resource_id and rule.resource_id not in updated_acl_rules_ids:
                session.delete(rule)

        session.commit()

        for updated_acl_rule in self.rules.all():
            updated_acl_rule.ibm_network_acl = None
            updated_acl_rule.dis_add_update_db(
                session=session, db_network_acl_rules=existing.rules.all(), existing_network_acl=existing
            )

        session.commit()

    def update_from_object(self, other):
        assert isinstance(other, self.__class__)

        self.name = other.name
        self.is_default = other.is_default
        self.status = other.status
        self.resource_id = other.resource_id


class IBMNetworkAclRule(Base):
    ID_KEY = "id"
    RESOURCE_ID_KEY = "resource_id"
    ACTION_KEY = "action"
    CREATED_AT_KEY = "created_at"
    DESTINATION_KEY = "destination"
    DIRECTION_KEY = "direction"
    HREF_KEY = "href"
    IP_VERSION_KEY = "ip_version"
    NAME_KEY = "name"
    PROTOCOL_KEY = "protocol"
    SOURCE_KEY = "source"
    TCP_UDP_DST_PORT_MAX_KEY = "tcp_udp_dst_port_max"
    TCP_UDP_DST_PORT_MIN_KEY = "tcp_udp_dst_port_min"
    TCP_UDP_SRC_PORT_MAX_KEY = "tcp_udp_src_port_max"
    TCP_UDP_SRC_PORT_MIN_KEY = "tcp_udp_src_port_min"
    STATUS_KEY = "status"
    ICMP_CODE_KEY = "icmp_code"
    ICMP_TYPE_KEY = "icmp_type"
    BEFORE_NETWORK_ACL_RULE_KEY = "before_network_acl_rule"
    NETWORK_ACL_KEY = "network_acl"

    # Softlayer payload variables
    CODE_KEY = "code"
    TYPE_KEY = "type"
    DESTINATION_PORT_MAX_KEY = "destination_port_max"
    DESTINATION_PORT_MIN_KEY = "destination_port_min"
    SOURCE_PORT_MAX_KEY = "source_port_max"
    SOURCE_PORT_MIN_KEY = "source_port_min"

    CRZ_BACKREF_NAME = "network_acl_rules"

    # protocol consts
    PROTOCOL_TYPE_ALL = "all"
    PROTOCOL_TYPE_ICMP = "icmp"
    PROTOCOL_TYPE_UDP = "udp"
    PROTOCOL_TYPE_TCP = "tcp"
    ALL_PROTOCOL_LIST = [
        PROTOCOL_TYPE_ALL, PROTOCOL_TYPE_ICMP, PROTOCOL_TYPE_UDP, PROTOCOL_TYPE_TCP
    ]

    # ip_version consts
    IP_VERSION_IPV4 = "ipv4"
    IP_VERSION_IPV6 = "ipv6"
    ALL_IP_VERSIONS_LIST = [
        IP_VERSION_IPV4, IP_VERSION_IPV6
    ]

    # direction consts
    DIRECTION_INBOUND = "inbound"
    DIRECTION_OUTBOUND = "outbound"
    ALL_DIRECTIONS_LIST = [
        DIRECTION_INBOUND, DIRECTION_OUTBOUND
    ]

    # action consts
    ACTION_ALLOW = "allow"
    ACTION_DENY = "deny"
    ALL_ACTIONS_LIST = [
        ACTION_ALLOW, ACTION_DENY
    ]

    __tablename__ = "ibm_network_acl_rules"

    id = Column(String(32), primary_key=True)
    resource_id = Column(String(64), nullable=False)
    action = Column(Enum(ACTION_ALLOW, ACTION_DENY), nullable=False)
    created_at = Column(DateTime, nullable=False)
    destination = Column(String(255), nullable=False)
    direction = Column(Enum(DIRECTION_INBOUND, DIRECTION_OUTBOUND), nullable=False)
    href = Column(Text, nullable=False)
    ip_version = Column(Enum(IP_VERSION_IPV4, IP_VERSION_IPV6), nullable=False)
    name = Column(String(255), nullable=False)
    protocol = Column(String(255), Enum(PROTOCOL_TYPE_ALL, PROTOCOL_TYPE_ICMP, PROTOCOL_TYPE_UDP, PROTOCOL_TYPE_TCP),
                      nullable=False)
    source = Column(String(255), nullable=False)
    tcp_udp_dst_port_max = Column(Integer)
    tcp_udp_dst_port_min = Column(Integer)
    tcp_udp_src_port_max = Column(Integer)
    tcp_udp_src_port_min = Column(Integer)
    status = Column(String(50), nullable=False)
    icmp_code = Column(Integer)
    icmp_type = Column(Integer)

    before_id = Column(String(32), ForeignKey('ibm_network_acl_rules.id', ondelete="SET NULL"), nullable=True)
    acl_id = Column(String(32), ForeignKey("ibm_network_acls.id", ondelete="CASCADE"))

    before = relationship('IBMNetworkAclRule', backref=backref("after", remote_side=[id]), uselist=False)

    __table_args__ = (UniqueConstraint(name, acl_id, name="uix_ibm_acl_name_acl_id"),)

    def __init__(
            self, resource_id, action, destination, direction, href, ip_version, name, protocol, source,
            created_at=None, tcp_udp_dst_port_max=None, tcp_udp_dst_port_min=None, tcp_udp_src_port_max=None,
            tcp_udp_src_port_min=None, status=CREATED, icmp_code=None, icmp_type=None
    ):
        self.id = str(uuid.uuid4().hex)
        self.resource_id = resource_id
        self.action = action
        self.created_at = created_at
        self.destination = destination
        self.direction = direction
        self.href = href
        self.ip_version = ip_version
        self.name = name
        self.protocol = protocol
        self.source = source
        self.tcp_udp_dst_port_max = tcp_udp_dst_port_max
        self.tcp_udp_dst_port_min = tcp_udp_dst_port_min
        self.tcp_udp_src_port_max = tcp_udp_src_port_max
        self.tcp_udp_src_port_min = tcp_udp_src_port_min
        self.status = status
        self.icmp_code = icmp_code
        self.icmp_type = icmp_type

    def to_reference_json(self):
        return {
            self.ID_KEY: self.id,
            self.NAME_KEY: self.name
        }

    def to_json(self, parent_reference=True):
        json_data = {
            self.ID_KEY: self.id,
            self.RESOURCE_ID_KEY: self.resource_id,
            self.ACTION_KEY: self.action,
            self.CREATED_AT_KEY: self.created_at,
            self.DESTINATION_KEY: self.destination,
            self.DIRECTION_KEY: self.direction,
            self.HREF_KEY: self.href,
            self.IP_VERSION_KEY: self.ip_version,
            self.NAME_KEY: self.name,
            self.PROTOCOL_KEY: self.protocol,
            self.SOURCE_KEY: self.source,
            self.TCP_UDP_DST_PORT_MAX_KEY: self.tcp_udp_dst_port_max,
            self.TCP_UDP_DST_PORT_MIN_KEY: self.tcp_udp_dst_port_min,
            self.TCP_UDP_SRC_PORT_MAX_KEY: self.tcp_udp_src_port_max,
            self.TCP_UDP_SRC_PORT_MIN_KEY: self.tcp_udp_src_port_min,
            self.STATUS_KEY: self.status,
            self.ICMP_CODE_KEY: self.icmp_code,
            self.ICMP_TYPE_KEY: self.icmp_type,
            self.BEFORE_NETWORK_ACL_RULE_KEY: self.before.to_reference_json() if self.before else {}
        }

        if parent_reference:
            json_data[self.NETWORK_ACL_KEY] = self.network_acl.to_reference_json()

        return json_data

    def to_json_body(self):
        json_data = {
            "name": self.name,
            "action": self.action,
            "direction": self.direction,
            "protocol": self.protocol,
            "source": self.source or "0.0.0.0/0",
            "destination": self.destination or "0.0.0.0/0",
        }

        if self.protocol in [self.PROTOCOL_TYPE_TCP, self.PROTOCOL_TYPE_UDP]:
            json_data["destination_port_max"] = self.tcp_udp_dst_port_max
            json_data["destination_port_min"] = self.tcp_udp_dst_port_min
            json_data["source_port_max"] = self.tcp_udp_src_port_max
            json_data["source_port_min"] = self.tcp_udp_src_port_min

        elif self.protocol == self.PROTOCOL_TYPE_ICMP:
            json_data["code"] = self.icmp_code
            json_data["type"] = self.icmp_type

        return json_data

    def to_template_json(self):
        resource_json = {
            self.NAME_KEY: self.name,
            self.ACTION_KEY: self.action,
            self.DESTINATION_KEY: self.destination,
            self.DIRECTION_KEY: self.direction,
            self.PROTOCOL_KEY: self.protocol,
            self.SOURCE_KEY: self.source,
        }
        if self.tcp_udp_dst_port_max:
            resource_json[self.DESTINATION_PORT_MAX_KEY] = self.tcp_udp_dst_port_max

        if self.tcp_udp_dst_port_min:
            resource_json[self.DESTINATION_PORT_MIN_KEY] = self.tcp_udp_dst_port_min

        if self.tcp_udp_src_port_max:
            resource_json[self.SOURCE_PORT_MAX_KEY] = self.tcp_udp_src_port_max

        if self.tcp_udp_src_port_min:
            resource_json[self.SOURCE_PORT_MIN_KEY] = self.tcp_udp_src_port_min

        if self.icmp_code:
            resource_json[self.CODE_KEY] = self.icmp_code

        if self.icmp_type:
            resource_json[self.TYPE_KEY] = self.icmp_type

        return resource_json

    def from_softlayer_to_ibm(self):
        resource_json = {
            self.ID_KEY: self.id,
            self.NAME_KEY: self.name,
            self.ACTION_KEY: self.action,
            self.DESTINATION_KEY: self.destination,
            self.DIRECTION_KEY: self.direction,
            self.IP_VERSION_KEY: self.ip_version,
            self.PROTOCOL_KEY: self.protocol,
            self.SOURCE_KEY: self.source,
        }
        if self.tcp_udp_dst_port_max:
            resource_json[self.DESTINATION_PORT_MAX_KEY] = self.tcp_udp_dst_port_max

        if self.tcp_udp_dst_port_min:
            resource_json[self.DESTINATION_PORT_MIN_KEY] = self.tcp_udp_dst_port_min

        if self.tcp_udp_src_port_max:
            resource_json[self.SOURCE_PORT_MAX_KEY] = self.tcp_udp_src_port_max

        if self.tcp_udp_src_port_min:
            resource_json[self.SOURCE_PORT_MIN_KEY] = self.tcp_udp_src_port_min

        if self.icmp_code:
            resource_json[self.CODE_KEY] = self.icmp_code

        if self.icmp_type:
            resource_json[self.TYPE_KEY] = self.icmp_type

        return resource_json

    @classmethod
    def from_ibm_json_body(cls, json_body):
        # TODO: Check schema. Investigate resource_id = None for rules
        return cls(
            resource_id=json_body["id"],
            action=json_body["action"],
            destination=json_body["destination"],
            direction=json_body["direction"],
            href=json_body["href"],
            ip_version=json_body["ip_version"],
            name=json_body["name"],
            protocol=json_body.get("protocol", "all"),
            source=json_body["source"],
            created_at=datetime.strptime(json_body["created_at"], CREATED_AT_FORMAT),
            tcp_udp_dst_port_max=json_body.get("destination_port_max"),
            tcp_udp_dst_port_min=json_body.get("destination_port_min"),
            tcp_udp_src_port_max=json_body.get("source_port_max"),
            tcp_udp_src_port_min=json_body.get("source_port_min"),
            status=CREATED,
            icmp_code=json_body.get("code"),
            icmp_type=json_body.get("type")
        )

    def dis_params_eq(self, other):
        assert isinstance(other, self.__class__)

        return (self.name == other.name and self.destination == other.destination and self.action == other.action
                and self.direction == other.direction and self.source == other.source and
                self.protocol == other.protocol and self.tcp_udp_dst_port_max == other.tcp_udp_dst_port_max and
                self.tcp_udp_dst_port_min == other.tcp_udp_dst_port_min and
                self.tcp_udp_src_port_max == other.tcp_udp_src_port_max and
                self.tcp_udp_src_port_min == other.tcp_udp_src_port_min and
                self.icmp_code == other.icmp_code and self.icmp_type == other.icmp_type and
                self.resource_id == other.resource_id and self.status == other.status)

    def dis_add_update_db(self, session, db_network_acl_rules, existing_network_acl):
        db_network_acl_rules_id_obj_dict = dict()
        db_network_acl_rules_name_obj_dict = dict()
        for db_network_acl_rule in db_network_acl_rules:
            db_network_acl_rules_id_obj_dict[db_network_acl_rule.resource_id] = db_network_acl_rule
            db_network_acl_rules_name_obj_dict[db_network_acl_rule.name] = db_network_acl_rule

        if self.resource_id not in db_network_acl_rules_id_obj_dict and self.name in db_network_acl_rules_name_obj_dict:
            # Creation Pending / Creating
            existing = db_network_acl_rules_name_obj_dict[self.name]
        elif self.resource_id in db_network_acl_rules_id_obj_dict:
            # Created. Update everything including name
            existing = db_network_acl_rules_id_obj_dict[self.resource_id]
        else:
            existing = None

        if not existing:
            self.ibm_network_acl = existing
            session.commit()
            return

        if not self.dis_params_eq(existing):
            existing.update_from_object(self)

        session.commit()

    def update_from_object(self, other):
        assert isinstance(other, self.__class__)

        self.name = other.name
        self.status = other.status
        self.destination = other.destination
        self.action = other.action
        self.direction = other.direction
        self.source = other.source
        self.protocol = other.protocol
        self.tcp_udp_dst_port_max = other.tcp_udp_dst_port_max
        self.tcp_udp_dst_port_min = other.tcp_udp_dst_port_min
        self.tcp_udp_src_port_max = other.tcp_udp_src_port_max
        self.tcp_udp_src_port_min = other.tcp_udp_src_port_min
        self.icmp_code = other.icmp_code
        self.icmp_type = other.icmp_type
        self.resource_id = other.resource_id
