import json
import uuid
from datetime import datetime

from sqlalchemy import Boolean, Column, DateTime, Enum, ForeignKey, Integer, JSON, String, Text
from sqlalchemy.orm import relationship
from sqlalchemy.schema import UniqueConstraint

from ibm import get_db_session as db
from ibm.common.consts import (
    CREATED, DUMMY_CLOUD_ID, DUMMY_CLOUD_NAME, DUMMY_REGION_ID, DUMMY_REGION_NAME,
    DUMMY_RESOURCE_GROUP_ID, DUMMY_RESOURCE_GROUP_NAME, DUMMY_ZONE_ID, DUMMY_ZONE_NAME,
)
from ibm.common.utils import return_datetime_object
from ibm.models.base import Base
from ibm.models.ibm.mixins import IBMRegionalResourceMixin


class IBMIKEPolicy(IBMRegionalResourceMixin, Base):
    ID_KEY = "id"
    NAME_KEY = "name"
    DH_GROUP_KEY = "dh_group"
    ENCRYPTION_ALGORITHM_KEY = "encryption_algorithm"
    AUTHENTICATION_ALGORITHM_KEY = "authentication_algorithm"
    KEY_LIFETIME_KEY = "key_lifetime"
    IKE_VERSION_KEY = "ike_version"
    RESOURCE_GROUP_KEY = "resource_group"
    STATUS_KEY = "status"
    REGION_KEY = "region"
    CLOUD_ID_KEY = "cloud_id"
    MESSAGE_KEY = "message"
    CREATED_AT_KEY = "created_at"
    HREF_KEY = "href"
    RESOURCE_TYPE_KEY = "resource_type"
    RESOURCE_JSON_KEY = "resource_json"

    CRZ_BACKREF_NAME = "ike_policies"

    # authentication_algorithm consts
    AUTHENTICATION_ALGORITHM_MD5 = "md5"
    AUTHENTICATION_ALGORITHM_SHA1 = "sha1"
    AUTHENTICATION_ALGORITHM_SHA256 = "sha256"
    AUTHENTICATION_ALGORITHM_SHA512 = "sha512"
    ALL_AUTHENTICATION_ALGORITHMS_LIST = [
        AUTHENTICATION_ALGORITHM_MD5, AUTHENTICATION_ALGORITHM_SHA1, AUTHENTICATION_ALGORITHM_SHA256,
        AUTHENTICATION_ALGORITHM_SHA512
    ]

    # encryption_algorithm consts
    ENCRYPTION_ALGORITHM_TRIPLE_DES = "triple_des"
    ENCRYPTION_ALGORITHM_AES128 = "aes128"
    ENCRYPTION_ALGORITHM_AES256 = "aes256"
    ALL_ENCRYPTION_ALGORITHMS_LIST = [
        ENCRYPTION_ALGORITHM_TRIPLE_DES, ENCRYPTION_ALGORITHM_AES128, ENCRYPTION_ALGORITHM_AES256
    ]

    # negotiation_mode consts
    NEGOTIATION_MODE_MAIN = "main"
    ALL_NEGOTIATION_MODES_LIST = [
        NEGOTIATION_MODE_MAIN
    ]

    # resource_type consts
    RESOURCE_TYPE_IKE_POLICY = "ike_policy"
    ALL_RESOURCE_TYPES_LIST = [
        RESOURCE_TYPE_IKE_POLICY
    ]

    # dh_group consts
    DH_GROUP_14 = "14"
    DH_GROUP_15 = "15"
    DH_GROUP_16 = "16"
    DH_GROUP_17 = "17"
    DH_GROUP_18 = "18"
    DH_GROUP_19 = "19"
    DH_GROUP_2 = "2"
    DH_GROUP_20 = "20"
    DH_GROUP_21 = "21"
    DH_GROUP_22 = "22"
    DH_GROUP_23 = "23"
    DH_GROUP_24 = "24"
    DH_GROUP_31 = "31"
    DH_GROUP_5 = "5"

    ALL_DH_GROUPS_LIST = [
        DH_GROUP_14, DH_GROUP_15, DH_GROUP_16, DH_GROUP_17, DH_GROUP_18, DH_GROUP_19, DH_GROUP_2,
        DH_GROUP_20, DH_GROUP_21, DH_GROUP_22, DH_GROUP_23, DH_GROUP_24, DH_GROUP_31, DH_GROUP_5]

    # ike_version consts
    IKE_VERSION_1 = "1"
    IKE_VERSION_2 = "2"
    ALL_IKE_VERSIONS_LIST = [
        IKE_VERSION_1, IKE_VERSION_2
    ]

    __tablename__ = "ibm_ike_policy"

    id = Column(String(32), primary_key=True)
    resource_id = Column(String(64), nullable=False)
    authentication_algorithm = Column(
        Enum(
            AUTHENTICATION_ALGORITHM_MD5, AUTHENTICATION_ALGORITHM_SHA1, AUTHENTICATION_ALGORITHM_SHA256,
            AUTHENTICATION_ALGORITHM_SHA512
        ),
        nullable=False
    )
    created_at = Column(DateTime, default=datetime.utcnow(), nullable=False)
    dh_group = Column(Enum(*ALL_DH_GROUPS_LIST), nullable=False)
    encryption_algorithm = Column(
        Enum(ENCRYPTION_ALGORITHM_TRIPLE_DES, ENCRYPTION_ALGORITHM_AES128, ENCRYPTION_ALGORITHM_AES256), nullable=False
    )
    href = Column(Text, nullable=False)
    ike_version = Column(Enum(IKE_VERSION_1, IKE_VERSION_2), nullable=False)
    key_lifetime = Column(Integer, nullable=False)
    name = Column(String(255), nullable=False)
    negotiation_mode = Column(Enum(NEGOTIATION_MODE_MAIN), default=NEGOTIATION_MODE_MAIN, nullable=False)
    resource_type = Column(Enum(RESOURCE_TYPE_IKE_POLICY), default=RESOURCE_TYPE_IKE_POLICY, nullable=False)
    status = Column(String(50), nullable=False)

    resource_group_id = Column(String(32), ForeignKey("ibm_resource_groups.id", ondelete="CASCADE"))

    vpn_connections = relationship("IBMVpnConnection", backref="ike_policy", cascade="all, delete-orphan",
                                   passive_deletes=True, lazy="dynamic")

    __table_args__ = (
        UniqueConstraint(name, "region_id", "cloud_id", name="uix_ibm_ike_policy_name_region_id_cloud_id"),
    )

    def __init__(
            self, resource_id, authentication_algorithm, created_at, dh_group, encryption_algorithm, href,
            ike_version, key_lifetime, name, negotiation_mode=NEGOTIATION_MODE_MAIN,
            resource_type=RESOURCE_TYPE_IKE_POLICY, status=CREATED
    ):
        self.id = str(uuid.uuid4().hex)
        self.resource_id = resource_id
        self.authentication_algorithm = authentication_algorithm
        self.created_at = created_at
        self.dh_group = dh_group
        self.encryption_algorithm = encryption_algorithm
        self.href = href
        self.ike_version = ike_version
        self.key_lifetime = key_lifetime
        self.name = name
        self.negotiation_mode = negotiation_mode
        self.resource_type = resource_type
        self.status = status

    def to_reference_json(self):
        return {
            self.ID_KEY: self.id,
            self.NAME_KEY: self.name
        }

    def validate_json_for_schema(self):
        return {
            self.ID_KEY: self.id,
            self.RESOURCE_JSON_KEY: {
                self.NAME_KEY: self.name,
            }
        }

    def to_json(self):
        return {
            self.ID_KEY: self.id,
            self.NAME_KEY: self.name,
            self.AUTHENTICATION_ALGORITHM_KEY: self.authentication_algorithm,
            self.ENCRYPTION_ALGORITHM_KEY: self.encryption_algorithm,
            self.KEY_LIFETIME_KEY: self.key_lifetime,
            self.IKE_VERSION_KEY: self.ike_version,
            self.DH_GROUP_KEY: self.dh_group,
            self.HREF_KEY: self.href,
            self.CREATED_AT_KEY: self.created_at,
            self.STATUS_KEY: self.status,
            self.RESOURCE_GROUP_KEY: self.resource_group_id if self.resource_group_id else "",
            self.CLOUD_ID_KEY: self.cloud_id,
        }

    def from_softlayer_to_ibm(self):
        resource_json = {
            self.NAME_KEY: self.name,
            self.AUTHENTICATION_ALGORITHM_KEY: self.authentication_algorithm,
            self.ENCRYPTION_ALGORITHM_KEY: self.encryption_algorithm,
            self.KEY_LIFETIME_KEY: self.key_lifetime if self.key_lifetime else None,
            self.IKE_VERSION_KEY: self.ike_version,
            self.DH_GROUP_KEY: self.dh_group,
            self.RESOURCE_GROUP_KEY: {
                "id": DUMMY_RESOURCE_GROUP_ID,
                "name": DUMMY_RESOURCE_GROUP_NAME
            },
        }
        ike_schema = {
            self.ID_KEY: self.id,
            "resource_json": resource_json,
            "ibm_cloud": {
                "id": DUMMY_CLOUD_ID,
                "name": DUMMY_CLOUD_NAME
            },
            "region": {
                "id": DUMMY_REGION_ID,
                "name": DUMMY_REGION_NAME
            },
        }
        return ike_schema

    @property
    def is_deletable(self):
        return not bool(self.vpn_connections.count())

    def to_json_body(self):
        return {
            "name": self.name,
            "authentication_algorithm": self.authentication_algorithm,
            "encryption_algorithm": self.encryption_algorithm,
            "key_lifetime": self.key_lifetime,
            "ike_version": self.ike_version,
            "dh_group": self.dh_group,
            "resource_group": {
                "id": self.ibm_resource_group.resource_id
                if self.ibm_resource_group
                else ""
            },
        }

    @classmethod
    def from_ibm_json_body(cls, json_body):
        # TODO: Verify Schema
        return cls(
            resource_id=json_body["id"],
            authentication_algorithm=json_body["authentication_algorithm"],
            created_at=return_datetime_object(json_body["created_at"]),
            dh_group=str(json_body["dh_group"]),
            encryption_algorithm=json_body["encryption_algorithm"],
            href=json_body["href"],
            ike_version=str(json_body["ike_version"]),
            key_lifetime=json_body["key_lifetime"],
            name=json_body["name"],
            negotiation_mode=json_body["negotiation_mode"],
            resource_type=json_body["resource_type"],
        )

    def dis_params_eq(self, other):
        assert isinstance(other, self.__class__)
        return (self.name == other.name and self.resource_id == other.resource_id and
                self.ike_version == other.ike_version and self.key_lifetime == other.key_lifetime and
                self.authentication_algorithm == other.authentication_algorithm and
                self.encryption_algorithm == other.encryption_algorithm and self.dh_group == other.dh_group and
                self.status == other.status)

    def dis_add_update_db(self, session, db_ike_policies, db_cloud, db_resource_group, db_region):
        if not db_resource_group:
            return
        db_ike_policies_id_obj_dict = dict()
        db_ike_policies_name_obj_dict = dict()
        for db_ike_policy in db_ike_policies:
            db_ike_policies_id_obj_dict[db_ike_policy.resource_id] = db_ike_policy
            db_ike_policies_name_obj_dict[db_ike_policy.name] = db_ike_policy

        if self.resource_id not in db_ike_policies_id_obj_dict and self.name in db_ike_policies_name_obj_dict:
            # Creation Pending / Creating
            existing = db_ike_policies_name_obj_dict[self.name]
        elif self.resource_id in db_ike_policies_id_obj_dict:
            # Created. Update everything including name
            existing = db_ike_policies_id_obj_dict[self.resource_id]
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
            existing.resource_group = db_resource_group
            existing.region = db_region

        session.commit()

    def update_from_object(self, other):
        assert isinstance(other, self.__class__)

        self.name = other.name
        self.status = other.status
        self.resource_id = other.resource_id
        self.ike_version = other.ike_version
        self.key_lifetime = other.key_lifetime
        self.authentication_algorithm = other.authentication_algorithm
        self.encryption_algorithm = other.encryption_algorithm
        self.dh_group = other.dh_group


class IBMIPSecPolicy(IBMRegionalResourceMixin, Base):
    ID_KEY = "id"
    NAME_KEY = "name"
    REGION_KEY = "region"
    STATUS_KEY = "status"
    PFS_KEY = "pfs"
    DH_GROUP_KEY = "dh_group"
    ENCRYPTION_ALGORITHM_KEY = "encryption_algorithm"
    AUTHENTICATION_ALGORITHM_KEY = "authentication_algorithm"
    KEY_LIFETIME_KEY = "key_lifetime"
    RESOURCE_GROUP_KEY = "resource_group"
    CLOUD_ID_KEY = "cloud_id"
    MESSAGE_KEY = "message"
    CREATED_AT_KEY = "created_at"
    HREF_KEY = "href"
    RESOURCE_TYPE_KEY = "resource_type"
    TRANSFORM_PROTOCOL_KEY = "transform_protocol"
    RESOURCE_JSON_KEY = "resource_json"

    CRZ_BACKREF_NAME = "ipsec_policies"

    # authentication_algorithm consts
    AUTHENTICATION_ALGORITHM_MD5 = "md5"
    AUTHENTICATION_ALGORITHM_SHA1 = "sha1"
    AUTHENTICATION_ALGORITHM_SHA256 = "sha256"
    AUTHENTICATION_ALGORITHM_SHA512 = "sha512"
    ALL_AUTHENTICATION_ALGORITHMS_LIST = [
        AUTHENTICATION_ALGORITHM_MD5, AUTHENTICATION_ALGORITHM_SHA1, AUTHENTICATION_ALGORITHM_SHA256,
        AUTHENTICATION_ALGORITHM_SHA512
    ]

    # encapsulation_mode consts
    ENCAPSULATION_MODE_TUNNEL = "tunnel"
    ALL_ENCAPSULATION_MODES_LIST = [
        ENCAPSULATION_MODE_TUNNEL
    ]

    # encryption_algorithm consts
    ENCRYPTION_ALGORITHM_TRIPLE_DES = "triple_des"
    ENCRYPTION_ALGORITHM_AES128 = "aes128"
    ENCRYPTION_ALGORITHM_AES256 = "aes256"
    ALL_ENCRYPTION_ALGORITHMS_LIST = [
        ENCRYPTION_ALGORITHM_TRIPLE_DES, ENCRYPTION_ALGORITHM_AES128, ENCRYPTION_ALGORITHM_AES256
    ]

    # pfs consts
    PFS_DISABLED = "disabled"
    PFS_GROUP_14 = "group_14"
    PFS_GROUP_19 = "group_19"
    PFS_GROUP_2 = "group_2"
    PFS_GROUP_5 = "group_5"
    ALL_PFS_LIST = [
        PFS_DISABLED, PFS_GROUP_14, PFS_GROUP_19, PFS_GROUP_2, PFS_GROUP_5
    ]

    # resource_type consts
    RESOURCE_TYPE_IPSEC_POLICY = "ipsec_policy"
    ALL_RESOURCE_TYPES_LIST = [
        RESOURCE_TYPE_IPSEC_POLICY
    ]

    # transform_protocol consts
    TRANSFORM_PROTOCOL_ESP = "esp"
    ALL_TRANSFORM_PROTOCOLS_LIST = [
        TRANSFORM_PROTOCOL_ESP
    ]

    __tablename__ = "ibm_ipsec_policy"

    id = Column(String(32), primary_key=True)
    resource_id = Column(String(64), nullable=False)
    authentication_algorithm = Column(Enum(AUTHENTICATION_ALGORITHM_MD5, AUTHENTICATION_ALGORITHM_SHA1,
                                           AUTHENTICATION_ALGORITHM_SHA256, AUTHENTICATION_ALGORITHM_SHA512),
                                      nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow(), nullable=False)
    encapsulation_mode = Column(Enum(ENCAPSULATION_MODE_TUNNEL), default=ENCAPSULATION_MODE_TUNNEL, nullable=False)
    encryption_algorithm = Column(Enum(ENCRYPTION_ALGORITHM_TRIPLE_DES, ENCRYPTION_ALGORITHM_AES128,
                                       ENCRYPTION_ALGORITHM_AES256), nullable=False)
    href = Column(Text, nullable=False)
    key_lifetime = Column(Integer, nullable=False)
    name = Column(String(255), nullable=False)
    pfs = Column(Enum(PFS_GROUP_2, PFS_GROUP_5, PFS_GROUP_14, PFS_GROUP_19, PFS_DISABLED), nullable=False)
    resource_type = Column(Enum(RESOURCE_TYPE_IPSEC_POLICY), default=RESOURCE_TYPE_IPSEC_POLICY, nullable=False)
    transform_protocol = Column(Enum(TRANSFORM_PROTOCOL_ESP), default=TRANSFORM_PROTOCOL_ESP, nullable=False)
    status = Column(String(50), nullable=False)

    resource_group_id = Column(String(32), ForeignKey("ibm_resource_groups.id", ondelete="CASCADE"))

    vpn_connections = relationship(
        "IBMVpnConnection", backref="ipsec_policy", cascade="all, delete-orphan", passive_deletes=True, lazy="dynamic"
    )

    __table_args__ = (
        UniqueConstraint(name, "region_id", "cloud_id", name="uix_ibm_ipsec_policy_name_region_id_cloud_id"),
    )

    def __init__(self, name, href, created_at=None, key_lifetime=None, status=CREATED,
                 authentication_algorithm=None, encryption_algorithm=None, pfs=None, resource_id=None,
                 resource_type=None, transform_protocol=None, encapsulation_mode=None):
        self.id = str(uuid.uuid4().hex)
        self.name = name
        self.href = href
        self.created_at = created_at
        self.resource_type = resource_type
        self.transform_protocol = transform_protocol
        self.status = status
        self.authentication_algorithm = authentication_algorithm
        self.encryption_algorithm = encryption_algorithm
        self.key_lifetime = key_lifetime
        self.pfs = pfs
        self.resource_id = resource_id
        self.encapsulation_mode = encapsulation_mode

    def to_reference_json(self):
        return {
            self.ID_KEY: self.id,
            self.NAME_KEY: self.name
        }

    def validate_json_for_schema(self):
        return {
            self.ID_KEY: self.id,
            self.RESOURCE_JSON_KEY: {
                self.NAME_KEY: self.name,
            }
        }

    def to_json(self):
        json_data = {
            self.ID_KEY: self.id,
            self.NAME_KEY: self.name,
            self.HREF_KEY: self.href,
            self.CREATED_AT_KEY: self.created_at,
            self.RESOURCE_TYPE_KEY: self.resource_type,
            self.TRANSFORM_PROTOCOL_KEY: self.transform_protocol,
            # self.REGION_KEY: self.region,
            self.STATUS_KEY: self.status,
            self.AUTHENTICATION_ALGORITHM_KEY: self.authentication_algorithm,
            self.ENCRYPTION_ALGORITHM_KEY: self.encryption_algorithm,
            self.KEY_LIFETIME_KEY: self.key_lifetime,
            self.RESOURCE_GROUP_KEY: self.resource_group_id if self.resource_group_id else "",
            self.CLOUD_ID_KEY: self.cloud_id,
        }

        if self.pfs != self.PFS_DISABLED:
            json_data[self.PFS_KEY] = "enabled"
            json_data[self.DH_GROUP_KEY] = self.pfs
        else:
            json_data[self.PFS_KEY] = "disabled"

        return json_data

    def from_softlayer_to_ibm(self):
        resource_json = {
            self.NAME_KEY: self.name,
            self.AUTHENTICATION_ALGORITHM_KEY: self.authentication_algorithm,
            self.ENCRYPTION_ALGORITHM_KEY: self.encryption_algorithm,
            self.PFS_KEY: self.pfs,
            self.KEY_LIFETIME_KEY: self.key_lifetime if self.key_lifetime else None,
            self.RESOURCE_GROUP_KEY: {
                "id": DUMMY_RESOURCE_GROUP_ID,
                "name": DUMMY_RESOURCE_GROUP_NAME
            },
        }
        ipsec_policy_schema = {
            self.ID_KEY: self.id,
            "resource_json": resource_json,
            "ibm_cloud": {
                "id": DUMMY_CLOUD_ID,
                "name": DUMMY_CLOUD_NAME
            },
            "region": {
                "id": DUMMY_REGION_ID,
                "name": DUMMY_REGION_NAME
            },
        }
        return ipsec_policy_schema

    @property
    def is_deletable(self):
        return not (self.vpn_connections.count())

    def to_json_body(self):
        return {
            "name": self.name,
            "authentication_algorithm": self.authentication_algorithm,
            "encryption_algorithm": self.encryption_algorithm,
            "key_lifetime": self.key_lifetime,
            "pfs": self.pfs,
            "resource_group": {"id": self.ibm_resource_group.resource_id if self.ibm_resource_group else ""},

        }

    @classmethod
    def from_ibm_json_body(cls, json_body):
        return cls(
            name=json_body["name"],
            href=json_body["href"],
            created_at=return_datetime_object(json_body["created_at"]),
            key_lifetime=json_body["key_lifetime"],
            status=CREATED,
            authentication_algorithm=json_body["authentication_algorithm"],
            encryption_algorithm=json_body["encryption_algorithm"],
            pfs=json_body["pfs"],
            resource_id=json_body["id"],
            resource_type=json_body["resource_type"],
            transform_protocol=json_body["transform_protocol"],
            encapsulation_mode=json_body["encapsulation_mode"],
        )

    def dis_params_eq(self, other):
        assert isinstance(other, self.__class__)
        return (self.name == other.name and self.resource_id == other.resource_id and
                self.authentication_algorithm == other.authentication_algorithm and
                self.encryption_algorithm == other.encryption_algorithm and self.pfs == other.pfs and
                self.key_lifetime == other.key_lifetime and self.status == other.status)

    def dis_add_update_db(self, session, db_ipsec_policies, db_cloud, db_resource_group, db_region):
        if not db_resource_group:
            return
        db_ipsec_policies_id_obj_dict = dict()
        db_ipsec_policies_name_obj_dict = dict()
        for db_ipsec_policy in db_ipsec_policies:
            db_ipsec_policies_id_obj_dict[db_ipsec_policy.resource_id] = db_ipsec_policy
            db_ipsec_policies_name_obj_dict[db_ipsec_policy.name] = db_ipsec_policy

        if self.resource_id not in db_ipsec_policies_id_obj_dict and self.name in db_ipsec_policies_name_obj_dict:
            # Creation Pending / Creating
            existing = db_ipsec_policies_name_obj_dict[self.name]
        elif self.resource_id in db_ipsec_policies_id_obj_dict:
            # Created. Update everything including name
            existing = db_ipsec_policies_id_obj_dict[self.resource_id]
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
            existing.resource_group = db_resource_group
            existing.region = db_region

        session.commit()

    def update_from_object(self, other):
        assert isinstance(other, self.__class__)

        self.name = other.name
        self.status = other.status
        self.resource_id = other.resource_id
        self.key_lifetime = other.key_lifetime
        self.authentication_algorithm = other.authentication_algorithm
        self.encryption_algorithm = other.encryption_algorithm
        self.pfs = other.pfs


class IBMVpnGateway(IBMRegionalResourceMixin, Base):
    ID_KEY = "id"
    NAME_KEY = "name"
    RESOURCE_ID_KEY = "resource_id"
    REGION_KEY = "region"
    SUBNET_KEY = "subnet"
    CREATED_AT_KEY = "created_at"
    CONNECTIONS_KEY = "connections"
    VPC_KEY = "vpc"
    RESOURCE_GROUP_KEY = "resource_group"
    IP_ADDRESS_KEY = "ip_address"
    LOCATION_KEY = "location"
    GATEWAY_STATUS_KEY = "gateway_status"
    STATUS_KEY = "status"
    CLOUD_ID_KEY = "cloud_id"
    MESSAGE_KEY = "message"
    CRN_KEY = "crn"
    HREF_KEY = "href"
    RESOURCE_TYPE_KEY = "resource_type"
    RESOURCE_TYPE_VPN_KEY = "VPN Gateway"
    COST_KEY = "cost"

    MODE_KEY = "mode"
    ASSOCIATED_RESOURCES_KEY = "associated_resources"
    RESOURCE_JSON_KEY = "resource_json"
    ZONE_KEY = "zone"

    CRZ_BACKREF_NAME = "vpn_gateways"

    # resource_type consts
    RESOURCE_TYPE_VPN_GATEWAY = "vpn_gateway"
    ALL_RESOURCE_TYPES_LIST = [
        RESOURCE_TYPE_VPN_GATEWAY
    ]

    # status consts
    STATUS_AVAILABLE = "available"
    STATUS_DELETING = "deleting"
    STATUS_FAILED = "failed"
    STATUS_PENDING = "pending"
    ALL_STATUSES_LIST = [
        STATUS_AVAILABLE, STATUS_DELETING, STATUS_FAILED, STATUS_PENDING
    ]

    # mode consts
    MODE_ROUTE = "route"
    MODE_POLICY = "policy"
    ALL_MODES_LIST = [
        MODE_ROUTE, MODE_POLICY
    ]

    gateway_location = {
        "eu-de": "Frankfurt",
        "us-south": "Dallas",
        "eu-gb": "London",
        "jp-tok": "Tokyo",
        "au-syd": "Sydney",
    }

    VPN_GATEWAY_COST = '75.46'

    __tablename__ = "ibm_vpn_gateways"

    id = Column(String(32), primary_key=True)
    resource_id = Column(String(64), nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow(), nullable=False)
    crn = Column(String(255), nullable=False)
    href = Column(Text, nullable=False)
    name = Column(String(255), nullable=False)
    resource_type = Column(Enum(RESOURCE_TYPE_VPN_GATEWAY), default=RESOURCE_TYPE_VPN_GATEWAY, nullable=False)
    status = Column(String(50), nullable=False)
    mode = Column(Enum(MODE_ROUTE, MODE_POLICY), nullable=False)

    vpc_id = Column(String(32), ForeignKey("ibm_vpc_networks.id", ondelete="CASCADE"))
    subnet_id = Column(String(32), ForeignKey("ibm_subnets.id", ondelete="CASCADE"))
    resource_group_id = Column(String(32), ForeignKey("ibm_resource_groups.id", ondelete="CASCADE"))

    vpn_connections = relationship("IBMVpnConnection", backref="vpn_gateway", cascade="all, delete-orphan",
                                   passive_deletes=True, lazy="dynamic")
    vpn_gateway_members = relationship("IBMVPNGatewayMember", backref="vpn_gateways", cascade="all, delete-orphan",
                                       passive_deletes=True, lazy="dynamic")

    __table_args__ = (UniqueConstraint(name, vpc_id, "cloud_id", name="uix_ibm_vpn_gateway_vpc_cloud_id"),)

    def __init__(self, name, crn, href, created_at=None, status=None, resource_type=None,
                 resource_id=None, mode=None):
        self.id = str(uuid.uuid4().hex)
        self.name = name
        self.crn = crn
        self.href = href
        self.mode = mode
        self.resource_type = resource_type
        self.status = status
        self.created_at = created_at
        self.resource_id = resource_id

    def to_reference_json(self):
        return {
            self.ID_KEY: self.id,
            self.NAME_KEY: self.name,
            self.SUBNET_KEY: self.subnet.to_reference_json(),
        }

    def validate_json_for_schema(self):
        return {
            self.ID_KEY: self.id,
            self.RESOURCE_JSON_KEY: {
                self.NAME_KEY: self.name,
                self.SUBNET_KEY: self.subnet.to_reference_json(),
            }
        }

    def to_json(self):
        return {
            self.ID_KEY: self.id,
            self.NAME_KEY: self.name,
            self.CRN_KEY: self.crn,
            self.HREF_KEY: self.href,
            self.MODE_KEY: self.mode,
            self.CREATED_AT_KEY: self.created_at,
            self.STATUS_KEY: self.status,
            self.REGION_KEY: self.region.to_reference_json(),
            self.CONNECTIONS_KEY: [
                connection.to_json() for connection in self.vpn_connections.all()
            ],
            self.CLOUD_ID_KEY: self.cloud_id,
            self.ASSOCIATED_RESOURCES_KEY: {
                self.VPC_KEY: self.vpc_network.to_reference_json(address_prefixes=True),
                self.SUBNET_KEY: self.subnet.to_reference_json(),
            }
        }

    def to_idle_json(self, session=None):
        from ibm.models.ibm.cost_models import IBMResourceInstancesCost

        session = session if session else db.session

        cost_obj = IBMResourceInstancesCost.get_cost(self.crn, self.cloud_id, session)
        return {
            self.MODE_KEY: self.mode,
            self.CRN_KEY: self.crn,
            self.STATUS_KEY: self.status,
            self.REGION_KEY: self.region.name,
            self.HREF_KEY: self.href,
            self.RESOURCE_TYPE_KEY: self.RESOURCE_TYPE_VPN_KEY,
            self.RESOURCE_ID_KEY: self.resource_id,
            self.IBM_CLOUD_KEY: self.cloud_id,
            self.ESTIMATED_SAVINGS: cost_obj.estimated_cost if cost_obj else None,
            self.COST_KEY: cost_obj.estimated_cost if cost_obj else None
        }

    def from_softlayer_to_ibm(self):
        vpn_connections = self.vpn_connections.all()
        resource_json = {
            self.NAME_KEY: self.name,
            self.CONNECTIONS_KEY: [connection.from_softlayer_to_ibm() for connection in vpn_connections],
            self.RESOURCE_GROUP_KEY: {
                "id": DUMMY_RESOURCE_GROUP_ID,
                "name": DUMMY_RESOURCE_GROUP_NAME
            },
            self.MODE_KEY: self.MODE_POLICY,
            self.SUBNET_KEY: {
                self.ID_KEY: self.subnet.id if self.subnet else None,
                self.NAME_KEY: self.subnet.name if self.subnet else None,
            },
        }
        vpn_schema = {
            self.ID_KEY: self.id,
            self.ZONE_KEY: {
                self.ID_KEY: DUMMY_ZONE_ID,
                self.NAME_KEY: DUMMY_ZONE_NAME,
            },
            "resource_json": resource_json,
            "ibm_cloud": {
                "id": DUMMY_CLOUD_ID,
                "name": DUMMY_CLOUD_NAME
            },
            "region": {
                "id": DUMMY_REGION_ID,
                "name": DUMMY_REGION_NAME
            },
        }
        return vpn_schema

    @property
    def is_deletable(self):
        return not self.vpn_connections.all()

    def to_json_body(self):
        return {
            "name": self.name,
            "subnet": {"id": self.ibm_subnet.resource_id if self.ibm_subnet else ""},
            "resource_group": {
                "id": self.ibm_resource_group.resource_id
                if self.ibm_resource_group
                else None
            }
        }

    @classmethod
    def from_ibm_json_body(cls, json_body):
        ibm_vpn_gateway = cls(
            name=json_body["name"],
            status=json_body["status"],
            crn=json_body["crn"],
            href=json_body["href"],
            created_at=return_datetime_object(json_body["created_at"]),
            resource_type=json_body["resource_type"],
            resource_id=json_body["id"],
            mode=json_body.get("mode") if json_body.get("mode") else "route",
        )
        for member in json_body.get("members", []):
            ibm_vpn_gateway.vpn_gateway_members.append(IBMVPNGatewayMember.from_ibm_json_body(member))

        return ibm_vpn_gateway

    def dis_params_eq(self, other):
        assert isinstance(other, self.__class__)

        return (self.name == other.name and self.crn == other.crn and self.href == other.href and
                self.mode == other.mode and self.resource_type == other.resource_type and
                self.status == other.status and self.created_at == other.created_at and
                self.resource_id == other.resource_id)

    def dis_add_update_db(self, session, db_vpn_gateways, db_cloud, db_resource_group, db_subnet, db_region):
        if not (db_resource_group and db_subnet):
            return
        db_vpn_gateways_id_obj_dict = dict()
        db_vpn_gateways_name_obj_dict = dict()
        for db_vpn_gateway in db_vpn_gateways:
            db_vpn_gateways_id_obj_dict[db_vpn_gateway.resource_id] = db_vpn_gateway
            db_vpn_gateways_name_obj_dict[db_vpn_gateway.name] = db_vpn_gateway

        if self.resource_id not in db_vpn_gateways_id_obj_dict and self.name in db_vpn_gateways_name_obj_dict:
            # Creation Pending / Creating
            existing = db_vpn_gateways_name_obj_dict[self.name]
        elif self.resource_id in db_vpn_gateways_id_obj_dict:
            # Created. Update everything including name
            existing = db_vpn_gateways_id_obj_dict[self.resource_id]
        else:
            existing = None

        if not existing:
            self.vpc_network = db_subnet.vpc_network
            self.ibm_cloud = db_cloud
            self.resource_group = db_resource_group
            self.subnet = db_subnet
            self.vpc_network = db_subnet.vpc_network
            self.region = db_region
            session.add(self)
            session.commit()
            return

        if not self.dis_params_eq(existing):
            existing.update_from_object(self)
            existing.resource_group = db_resource_group
            existing.subnet = db_subnet
            existing.vpc_network = db_subnet.vpc_network

        session.commit()

    def update_from_object(self, other):
        assert isinstance(other, self.__class__)

        self.name = other.name
        self.crn = other.crn
        self.href = other.href
        self.mode = other.mode
        self.resource_type = other.resource_type
        self.status = other.status
        self.resource_id = other.resource_id


class IBMVpnConnection(Base):
    ID_KEY = "id"
    NAME_KEY = "name"
    GATEWAY_ADDRESS_KEY = "gateway_ip"
    CREATED_AT_KEY = "created_at"
    PEER_ADDRESS_KEY = "peer_address"
    LOCAL_CIDRS_KEY = "local_cidrs"
    PEER_CIDRS_KEY = "peer_cidrs"
    PSK_KEY = "psk"
    DPD_ACTION_KEY = "action"
    DPD_INTERVAL_KEY = "interval"
    DPD_TIMEOUT_KEY = "timeout"
    VPN_STATUS_KEY = "vpn_status"
    ROUTE_MODE_KEY = "route_mode"
    ADMIN_STATE_UP_KEY = "admin_state_up"
    IKE_POLICY_KEY = "ike_policy"
    IPSEC_POLICY_KEY = "ipsec_policy"
    DISCOVERED_LOCAL_CIDRS = "discovered_local_cidrs"
    AUTHENTICATION_MODE = "authentication_mode"
    STATUS_KEY = "status"
    MESSAGE_KEY = "message"
    DEAD_PEER_DETECTION_KEY = "dead_peer_detection"
    HREF_KEY = "href"
    MODE_KEY = "mode"
    RESOURCE_TYPE_KEY = "resource_type"
    ROUTING_PROTOCOL_KEY = "routing_protocol"
    TUNNELS_KEY = "tunnels"
    VPN_GATEWAY_KEY = "vpn_gateway"

    # authentication_mode consts
    AUTHENTICATION_MODE_PSK = "psk"
    ALL_AUTHENTICATION_MODES_LIST = [
        AUTHENTICATION_MODE_PSK
    ]

    # mode consts
    MODE_POLICY = "policy"
    MODE_ROUTE = "route"
    ALL_MODES_LIST = [
        MODE_POLICY, MODE_ROUTE
    ]

    # status consts
    STATUS_DOWN = "down"
    STATUS_UP = "up"
    ALL_STATUSES_LIST = [
        STATUS_DOWN, STATUS_UP
    ]

    # resource_type consts
    RESOURCE_TYPE_VPN_GATEWAY_CONNECTION = "vpn_gateway_connection"
    ALL_RESOURCE_TYPES_LIST = [
        RESOURCE_TYPE_VPN_GATEWAY_CONNECTION
    ]

    # routing_protocol consts
    ROUTING_PROTOCOL_NONE = "none"
    ALL_ROUTING_PROTOCOLS_LIST = [
        ROUTING_PROTOCOL_NONE
    ]

    __tablename__ = "ibm_vpn_connections"

    id = Column(String(32), primary_key=True)
    resource_id = Column(String(64), nullable=False)
    admin_state_up = Column(Boolean, nullable=False)
    authentication_mode = Column(Enum(AUTHENTICATION_MODE_PSK), nullable=False, default=AUTHENTICATION_MODE_PSK)
    created_at = Column(DateTime, default=datetime.utcnow(), nullable=False)
    dead_peer_detection = Column(JSON, nullable=False)
    href = Column(Text, nullable=False)
    mode = Column(Enum(MODE_POLICY, MODE_ROUTE), nullable=False)
    name = Column(String(255), nullable=False)
    local_cidrs = Column(JSON)
    peer_address = Column(String(255), nullable=False)
    peer_cidrs = Column(JSON)
    psk = Column(String(255), nullable=False)
    resource_type = Column(Enum(RESOURCE_TYPE_VPN_GATEWAY_CONNECTION), nullable=False,
                           default=RESOURCE_TYPE_VPN_GATEWAY_CONNECTION)
    status = Column(String(50), nullable=False)
    routing_protocol = Column(Enum(ROUTING_PROTOCOL_NONE), nullable=False, default=ROUTING_PROTOCOL_NONE)
    tunnels = Column(JSON)

    ike_policy_id = Column(String(32), ForeignKey("ibm_ike_policy.id", ondelete="SET NULL"), nullable=True)
    ipsec_policy_id = Column(String(32), ForeignKey("ibm_ipsec_policy.id", ondelete="SET NULL"), nullable=True)
    vpn_gateway_id = Column(String(32), ForeignKey("ibm_vpn_gateways.id", ondelete="CASCADE"))

    __table_args__ = (UniqueConstraint(name, vpn_gateway_id, name="uix_ibm_vpn_connection_name_vpn_gateway_id"),)

    def __init__(self, name, href, admin_state_up=True, status=None, authentication_mode=None,
                 created_at=None, dead_peer_detection=None, local_cidrs=None, mode=None, peer_address=None,
                 peer_cidrs=None, psk=None, resource_type=None, resource_id=None, vpn_gateway_id=None,
                 routing_protocol=None, tunnels=None):
        self.id = str(uuid.uuid4().hex)
        self.name = name
        self.status = status
        self.peer_address = peer_address
        self.local_cidrs = local_cidrs
        self.peer_cidrs = peer_cidrs
        self.admin_state_up = admin_state_up
        self.created_at = created_at
        self.authentication_mode = authentication_mode or "psk"
        self.resource_id = resource_id
        self.vpn_gateway_id = vpn_gateway_id
        self.href = href
        self.dead_peer_detection = dead_peer_detection
        self.mode = mode
        self.psk = psk
        self.resource_type = resource_type
        self.routing_protocol = routing_protocol
        self.tunnels = tunnels

    def to_reference_json(self):
        return {
            self.ID_KEY: self.id,
            self.NAME_KEY: self.name
        }

    def to_json(self):
        return {
            self.ID_KEY: self.id,
            self.NAME_KEY: self.name,
            self.STATUS_KEY: self.status,
            self.PEER_ADDRESS_KEY: self.peer_address,
            self.LOCAL_CIDRS_KEY: self.local_cidrs or [],
            self.PEER_CIDRS_KEY: self.peer_cidrs or [],
            self.ADMIN_STATE_UP_KEY: self.admin_state_up,
            self.CREATED_AT_KEY: self.created_at,
            self.AUTHENTICATION_MODE: self.authentication_mode,
            self.HREF_KEY: self.href,
            self.DEAD_PEER_DETECTION_KEY: self.dead_peer_detection,
            self.MODE_KEY: self.mode,
            self.PSK_KEY: self.psk,
            self.RESOURCE_TYPE_KEY: self.resource_type,
            self.IKE_POLICY_KEY: self.ike_policy.to_reference_json() if self.ike_policy else {},
            self.IPSEC_POLICY_KEY: self.ipsec_policy.to_reference_json() if self.ipsec_policy else {},
            self.ROUTING_PROTOCOL_KEY: self.routing_protocol,
            self.TUNNELS_KEY: self.tunnels,
            self.VPN_GATEWAY_KEY: self.vpn_gateway.to_reference_json() if self.vpn_gateway else {},
        }

    def from_softlayer_to_ibm(self):
        return {
            self.ID_KEY: self.id,
            self.NAME_KEY: self.name,
            self.PEER_ADDRESS_KEY: self.peer_address,
            self.LOCAL_CIDRS_KEY: self.local_cidrs or [],
            self.PEER_CIDRS_KEY: self.peer_cidrs or [],
            self.IKE_POLICY_KEY: self.ike_policy.to_reference_json() if self.ike_policy else {},
            self.IPSEC_POLICY_KEY: self.ipsec_policy.to_reference_json() if self.ipsec_policy else {},
        }

    def to_json_body(self):
        json_data = {
            "name": self.name,
            "peer_address": self.peer_address,
            "local_cidrs": json.loads(self.local_cidrs),
            "peer_cidrs": json.loads(self.peer_cidrs),
            "psk": self.psk,
            "dead_peer_detection": self.dead_peer_detection
        }

        if self.ike_policy:
            json_data["ike_policy"] = {"id": self.ike_policy.resource_id}

        if self.ipsec_policy:
            json_data["ipsec_policy"] = {"id": self.ipsec_policy.resource_id}

        return json_data

    @classmethod
    def from_ibm_json_body(cls, json_body):
        return cls(
            name=json_body["name"],
            href=json_body["href"],
            admin_state_up=json_body["admin_state_up"],
            status=json_body["status"],
            authentication_mode=json_body["authentication_mode"],
            created_at=return_datetime_object(json_body["created_at"]),
            dead_peer_detection=json_body["dead_peer_detection"],
            local_cidrs=json_body.get("local_cidrs"),
            mode=json_body["mode"],
            peer_address=json_body["peer_address"],
            peer_cidrs=json_body.get("peer_cidrs"),
            psk=json_body["psk"],
            resource_type=json_body["resource_type"],
            resource_id=json_body["id"],
            routing_protocol=json_body.get("routing_protocol", cls.ROUTING_PROTOCOL_NONE),
            tunnels=json_body.get("tunnels"),
        )

    def dis_params_eq(self, other):
        assert isinstance(other, self.__class__)
        return (self.name == other.name and self.status == other.status and self.peer_address == other.peer_address and
                self.local_cidrs == other.local_cidrs and self.peer_cidrs == other.peer_cidrs and
                self.admin_state_up == other.admin_state_up and self.authentication_mode == other.authentication_mode
                and self.resource_id == other.resource_id and self.href == other.href and self.dead_peer_detection ==
                other.dead_peer_detection and self.mode == other.mode and self.psk == other.psk and
                self.resource_type == other.resource_type and self.routing_protocol == other.routing_protocol and
                self.tunnels == other.tunnels)

    def dis_add_update_db(self, session, db_vpn_connections, db_vpn_gateway, db_ike_policy, db_ipsec_policy):
        if not (db_vpn_connections and db_vpn_gateway and db_ipsec_policy and db_ike_policy):
            return

        db_vpn_connections_id_obj_dict = dict()
        db_vpn_connections_name_obj_dict = dict()
        for db_vpn_connection in db_vpn_connections:
            db_vpn_connections_id_obj_dict[db_vpn_connection.resource_id] = db_vpn_connection
            db_vpn_connections_name_obj_dict[db_vpn_connection.name] = db_vpn_connection

        if self.resource_id not in db_vpn_connections_id_obj_dict and self.name in db_vpn_connections_name_obj_dict:
            # Creation Pending / Creating
            existing = db_vpn_connections_name_obj_dict[self.name]
        elif self.resource_id in db_vpn_connections_id_obj_dict:
            # Created. Update everything including name
            existing = db_vpn_connections_id_obj_dict[self.resource_id]
        else:
            existing = None

        if not existing:
            self.ike_policy = db_ike_policy
            self.ipsec_policy = db_ipsec_policy
            self.vpn_gateway = db_vpn_gateway
            session.add(self)
            session.commit()
            return

        if not self.dis_params_eq(existing):
            existing.update_from_object(self)
            existing.ike_policy = db_ike_policy
            existing.ipsec_policy = db_ipsec_policy
            existing.vpn_gateway = db_vpn_gateway
        session.commit()

    def update_from_object(self, other):
        assert isinstance(other, self.__class__)

        self.name = other.name
        self.status = other.status
        self.peer_address = other.peer_address
        self.local_cidrs = other.local_cidrs
        self.peer_cidrs = other.peer_cidrs
        self.admin_state_up = other.admin_state_up
        self.authentication_mode = other.authentication_mode
        self.resource_id = other.resource_id
        self.href = other.href
        self.dead_peer_detection = other.dead_peer_detection
        self.mode = other.mode
        self.psk = other.psk
        self.resource_type = other.resource_type
        self.routing_protocol = other.routing_protocol
        self.tunnels = other.tunnels


class IBMVPNGatewayMember(Base):
    ID_KEY = "id"
    PUBLIC_IP_KEY = "public_ip"
    ROLE_KEY = "role"
    IBM_STATUS_KEY = "ibm_status"
    PRIVATE_IP_KEY = "private_ip"

    # role consts
    ROLE_ACTIVE = "active"
    ROLE_STANDBY = "standby"
    ALL_ROLES_LIST = [
        ROLE_ACTIVE, ROLE_STANDBY
    ]

    # ibm_status consts
    STATUS_AVAILABLE = "available"
    STATUS_FAILED = "failed"
    STATUS_PENDING = "pending"
    STATUS_DELETING = "deleting"
    ALL_IBM_STATUSES_LIST = [
        STATUS_AVAILABLE, STATUS_FAILED, STATUS_PENDING, STATUS_DELETING
    ]

    __tablename__ = "ibm_vpn_gateway_members"

    id = Column(String(32), primary_key=True)
    public_ip = Column(String(15), nullable=False)
    role = Column(Enum(ROLE_ACTIVE, ROLE_STANDBY), nullable=False)
    ibm_status = Column(Enum(STATUS_AVAILABLE, STATUS_FAILED, STATUS_PENDING, STATUS_DELETING), nullable=False)
    private_ip = Column(String(15))

    vpn_gateway_id = Column(String(32), ForeignKey("ibm_vpn_gateways.id", ondelete="CASCADE"))

    # TODO add unique contraint later

    def __init__(self, public_ip=None, role=None, ibm_status=None, private_ip=None):
        self.id = str(uuid.uuid4().hex)
        self.public_ip = public_ip
        self.role = role
        self.ibm_status = ibm_status
        self.private_ip = private_ip

    def to_reference_json(self):
        return {
            self.ID_KEY: self.id,
        }

    def to_json(self):
        return {
            self.ID_KEY: self.id,
            self.PUBLIC_IP_KEY: self.public_ip,
            self.ROLE_KEY: self.role,
            self.IBM_STATUS_KEY: self.ibm_status,
            self.PRIVATE_IP_KEY: self.private_ip,
        }

    def to_json_body(self):
        json_data = {
            "public_ip": self.public_ip,
            "role": self.role,
            "ibm_status": self.ibm_status,
            "private_ip": self.private_ip
        }

        return json_data

    @classmethod
    def from_ibm_json_body(cls, json_body):
        return IBMVPNGatewayMember(
            public_ip=json_body["public_ip"]["address"],
            role=json_body["role"],
            ibm_status=json_body["status"],
            private_ip=json_body["private_ip"]["address"] if "private_ip" in json_body else None
        )
