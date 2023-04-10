import uuid
from datetime import datetime

from sqlalchemy import Boolean, Column, DateTime, ForeignKey, String, Text
from sqlalchemy.orm import relationship
from sqlalchemy.schema import UniqueConstraint

from ibm.common.consts import CREATED_AT_FORMAT, DUMMY_CLOUD_ID, DUMMY_CLOUD_NAME, DUMMY_REGION_ID, \
    DUMMY_REGION_NAME, DUMMY_RESOURCE_GROUP_ID, DUMMY_RESOURCE_GROUP_NAME
from ibm.models.base import Base
from ibm.models.ibm.mixins import IBMRegionalResourceMixin


class IBMVpcNetwork(IBMRegionalResourceMixin, Base):
    ID_KEY = "id"
    RESOURCE_ID_KEY = "resource_id"
    NAME_KEY = "name"
    CREATED_AT_KEY = "created_at"
    CLASSIC_ACCESS_KEY = "classic_access"
    RESOURCE_GROUP_KEY = "resource_group"
    NETWORK_ACLS_KEY = "network_acls"
    ADDRESS_PREFIXES_KEY = "address_prefixes"
    SECURITY_GROUPS_KEY = "security_groups"
    SUBNETS_KEY = "subnets"
    PUBLIC_GATEWAYS_KEY = "public_gateways"
    KUBERNETES_CLUSTERS_KEY = "kubernetes_clusters"
    INSTANCE_GROUPS_KEY = "instance_groups"
    ASSOCIATED_RESOURCES_KEY = "associated_resources"
    ROUTING_TABLES_KEY = "routing_tables"
    INSTANCES_KEY = "instances"
    VPN_GATEWAYS_KEY = "vpn_gateways"
    LOAD_BALANCERS_KEY = "load_balancers"
    RESOURCE_JSON_KEY = "resource_json"
    STATUS_KEY = "status"
    ADDRESS_PREFIX_MANAGEMENT_KEY = "address_prefix_management"
    TAGS_KEY = "tags"
    RECOMMENDATIONS_KEY = "recommendations"
    IDLE_RESOURCES_KEY = "idle_resources"
    RIGHTSIZING_KEY = "rightsizing"
    TOTAL_KEY = "total"
    TTL_KEY = "ttl"

    CRZ_BACKREF_NAME = "vpc_networks"

    # status consts
    STATUS_AVAILABLE = "available"
    STATUS_DELETING = "deleting"
    STATUS_FAILED = "failed"
    STATUS_PENDING = "pending"
    ALL_STATUSES_LIST = [STATUS_AVAILABLE, STATUS_DELETING, STATUS_FAILED, STATUS_PENDING]

    # address prefix consts
    ADDRESS_PREFIX_MANAGEMENT_AUTO = "auto"
    ADDRESS_PREFIX_MANAGEMENT_MANUAL = "manual"
    ALL_APM_MODES = [ADDRESS_PREFIX_MANAGEMENT_AUTO, ADDRESS_PREFIX_MANAGEMENT_MANUAL]

    __tablename__ = "ibm_vpc_networks"

    id = Column(String(32), primary_key=True)
    resource_id = Column(String(64), nullable=False)
    name = Column(String(255), nullable=False)
    crn = Column(String(255), nullable=False)
    href = Column(Text, nullable=False)
    status = Column(String(50), nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow(), nullable=False)
    classic_access = Column(Boolean, nullable=False)

    transit_gateway_connection_id = Column(String(32), ForeignKey("ibm_transit_gateway_connections.id",
                                                                  ondelete="SET NULL"), nullable=True)

    resource_group_id = Column(String(32), ForeignKey("ibm_resource_groups.id", ondelete="CASCADE"))

    acls = relationship("IBMNetworkAcl", backref="vpc_network", cascade="all, delete-orphan", passive_deletes=True,
                        lazy="dynamic")
    routing_tables = relationship("IBMRoutingTable", backref="vpc_network", cascade="all, delete-orphan",
                                  passive_deletes=True, lazy="dynamic")

    subnets = relationship(
        "IBMSubnet",
        backref="vpc_network",
        cascade="all, delete-orphan",
        passive_deletes=True,
        lazy="dynamic",
    )
    public_gateways = relationship(
        "IBMPublicGateway",
        backref="vpc_network",
        cascade="all, delete-orphan",
        passive_deletes=True,
        lazy="dynamic",
    )
    security_groups = relationship(
        "IBMSecurityGroup",
        backref="vpc_network",
        cascade="all, delete-orphan",
        passive_deletes=True,
        lazy="dynamic",
    )
    vpn_gateways = relationship(
        "IBMVpnGateway",
        backref="vpc_network",
        cascade="all, delete-orphan",
        passive_deletes=True,
        lazy="dynamic",
    )
    address_prefixes = relationship(
        "IBMAddressPrefix",
        backref="vpc_network",
        cascade="all, delete-orphan",
        passive_deletes=True,
        lazy="dynamic",
    )
    kubernetes_clusters = relationship(
        "IBMKubernetesCluster",
        backref="vpc_network",
        cascade="all, delete-orphan",
        passive_deletes=True,
        lazy="dynamic"
    )
    instance_groups = relationship(
        "IBMInstanceGroup",
        backref="vpc_network",
        cascade="all, delete-orphan",
        passive_deletes=True,
        lazy="dynamic"
    )
    endpoint_gateways = relationship(
        "IBMEndpointGateway",
        backref="vpc_network",
        cascade="all, delete-orphan",
        passive_deletes=True,
        lazy="dynamic"
    )

    idle_resources = relationship("IBMIdleResource", backref='vpc_network', cascade="all,delete-orphan",
                                  passive_deletes=True, lazy="dynamic")
    ttl = relationship("TTLInterval", backref="vpc_network", cascade="all, delete-orphan", passive_deletes=True,
                       uselist=False)

    __table_args__ = (
        UniqueConstraint(name, "cloud_id", "region_id", name="uix_ibm_vpc_network_name_cloud_id_region_id"),
    )

    def __init__(self, name, href, crn, resource_id, created_at, classic_access=False,
                 status=None, cloud_id=None):
        self.id = str(uuid.uuid4().hex)
        self.name = name
        self.href = href
        self.crn = crn,
        self.resource_id = resource_id
        self.created_at = created_at
        self.classic_access = classic_access
        self.status = status
        self.cloud_id = cloud_id

    def to_template_json(self, vpc_name):
        resource_json = {
            self.NAME_KEY: vpc_name,
            self.ADDRESS_PREFIX_MANAGEMENT_KEY: self.ADDRESS_PREFIX_MANAGEMENT_MANUAL,
            self.RESOURCE_GROUP_KEY: {
                self.ID_KEY: self.resource_group.id,
                self.NAME_KEY: self.resource_group.name,
            }
        }
        vpc_schema = {
            self.ID_KEY: self.id,
            self.IBM_CLOUD_KEY: {
                self.ID_KEY: self.ibm_cloud.id,
                self.NAME_KEY: self.ibm_cloud.name,
            },
            self.REGION_KEY: {
                self.ID_KEY: self.region.id,
                self.NAME_KEY: self.region.name,
            },
            self.RESOURCE_JSON_KEY: resource_json
        }

        return vpc_schema

    def to_reference_json(self, address_prefixes=False):
        reference_json = {
            self.ID_KEY: self.id,
            self.NAME_KEY: self.name,
        }
        if address_prefixes:
            reference_json[self.ADDRESS_PREFIXES_KEY] = [address_prefix.to_reference_json() for address_prefix in
                                                         self.address_prefixes.all()]

        return reference_json

    def validate_json_for_schema(self, address_prefixes=False):
        reference_json = {
            self.ID_KEY: self.id,
            self.RESOURCE_JSON_KEY: {
                self.NAME_KEY: self.name,
            }
        }
        if address_prefixes:
            reference_json[self.RESOURCE_JSON_KEY][self.ADDRESS_PREFIXES_KEY] = [address_prefix.to_reference_json() for
                                                                                 address_prefix in
                                                                                 self.address_prefixes.all()]

        return reference_json

    def to_json(self, session=None):
        from ibm.web.ibm.tags.utils import get_tags
        from ibm.models import IBMRightSizingRecommendation, IBMInstance

        vpc_response = {
            self.ID_KEY: self.id,
            self.RESOURCE_ID_KEY: self.resource_id,
            self.NAME_KEY: self.name,
            self.CREATED_AT_KEY: self.created_at,
            self.STATUS_KEY: self.status,
            self.CLASSIC_ACCESS_KEY: self.classic_access,
            self.RESOURCE_GROUP_KEY: self.resource_group.to_reference_json(),
            self.REGION_KEY: self.region.to_reference_json(),
            self.IBM_CLOUD_KEY: self.ibm_cloud.to_reference_json(),
            self.TTL_KEY: self.ttl.to_reference_json() if self.ttl else None,
            self.ASSOCIATED_RESOURCES_KEY: {
                self.NETWORK_ACLS_KEY: [network_acl.to_reference_json() for network_acl in self.acls.all()],
                self.VPN_GATEWAYS_KEY: [vpn_gateway.to_reference_json() for vpn_gateway in self.vpn_gateways.all()],
                self.ADDRESS_PREFIXES_KEY: [address_prefix.to_reference_json() for address_prefix in
                                            self.address_prefixes.all()],
                self.ROUTING_TABLES_KEY: [routing_table.to_reference_json() for routing_table in
                                          self.routing_tables.all()],
                self.SECURITY_GROUPS_KEY:
                    [security_group.to_reference_json() for security_group in self.security_groups.all()],
                self.SUBNETS_KEY: [subnet.to_reference_json() for subnet in self.subnets.all()],
                self.INSTANCES_KEY: [instance.to_reference_json() for instance in self.instances.all()],
                self.PUBLIC_GATEWAYS_KEY:
                    [public_gateway.to_reference_json() for public_gateway in self.public_gateways.all()],
                self.KUBERNETES_CLUSTERS_KEY:
                    [kubernetes_cluster.to_reference_json() for kubernetes_cluster in self.kubernetes_clusters.all()],
                self.INSTANCE_GROUPS_KEY:
                    [instance_group.to_reference_json() for instance_group in self.instance_groups.all()],
                self.TAGS_KEY: [
                    tag.to_reference_json() for tag in get_tags(self.id, session)
                ]
            }
        }
        load_balancers = []
        for subnet in self.subnets.all():
            for lb in subnet.load_balancers.all():
                load_balancers.append(lb.to_reference_json())
        vpc_response[self.ASSOCIATED_RESOURCES_KEY][self.LOAD_BALANCERS_KEY] = load_balancers

        right_sizing_recommendations = session.query(IBMRightSizingRecommendation).join(IBMInstance).join(
            IBMVpcNetwork).filter(IBMRightSizingRecommendation.instance_id == IBMInstance.id,
                                  IBMVpcNetwork.id == self.id, IBMRightSizingRecommendation.cloud_id == self.cloud_id)
        idle_resources = self.idle_resources
        vpc_response[self.RECOMMENDATIONS_KEY] = {}
        total_count = idle_resources.count() + right_sizing_recommendations.count()

        if total_count > 0:
            vpc_response[self.RECOMMENDATIONS_KEY][
                self.TOTAL_KEY] = total_count

        if idle_resources.count() > 0:
            vpc_response[self.RECOMMENDATIONS_KEY][self.IDLE_RESOURCES_KEY] = idle_resources.count()

        if right_sizing_recommendations.count() > 0:
            vpc_response[self.RECOMMENDATIONS_KEY][self.RIGHTSIZING_KEY] = right_sizing_recommendations.count()

        return vpc_response

    @property
    def is_deletable(self):
        return not self.subnets.all()

    def to_json_body(self):
        return {
            "name": self.name,
            "classic_access": self.classic_access,
            "resource_group": {"id": self.ibm_resource_group.resource_id},
            "address_prefix_management": self.address_prefix_management,
        }

    def from_softlayer_to_ibm(self):
        resource_json = {
            self.NAME_KEY: self.name,
            self.RESOURCE_GROUP_KEY: {
                self.ID_KEY: DUMMY_RESOURCE_GROUP_ID,
                self.NAME_KEY: DUMMY_RESOURCE_GROUP_NAME
            }
        }
        vpc_schema = {
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

        return vpc_schema

    @classmethod
    def from_ibm_json_body(cls, json_body):
        ibm_vpc_network = cls(
            name=json_body["name"],
            href=json_body["href"],
            crn=json_body["crn"],
            status=json_body['status'],
            resource_id=json_body["id"],
            created_at=datetime.strptime(json_body["created_at"], CREATED_AT_FORMAT),
            classic_access=json_body["classic_access"]
        )

        return ibm_vpc_network

    def update_from_object(self, other):
        assert isinstance(other, self.__class__)

        self.name = other.name
        self.crn = other.crn
        self.status = other.status
        self.classic_access = other.classic_access
        self.resource_id = other.resource_id

    def dis_params_eq(self, other):
        assert isinstance(other, self.__class__)

        return (self.name == other.name and self.crn == other.crn and self.status == other.status and
                self.classic_access == other.classic_access and self.resource_id == other.resource_id)

    def dis_add_update_db(self, session, db_vpc_network, db_cloud, db_resource_group, db_region):
        if not db_vpc_network:
            self.ibm_cloud = db_cloud
            self.resource_group = db_resource_group
            self.region = db_region
            session.add(self)
            session.commit()
            return

        if not self.dis_params_eq(db_vpc_network):
            db_vpc_network.update_from_object(self)
            db_vpc_network.resource_group = db_resource_group
            db_vpc_network.region = db_region

        session.commit()

    def get_load_balancer_count(self):
        load_balancer_count = 0
        for subnet in self.subnets.all():
            load_balancer_count += subnet.load_balancers.count()
        return load_balancer_count

    def get_subresources_count(self):
        nodes_count = 0
        resources_list = {}

        if self.instances.count():
            nodes_count += self.instances.count()
            resources_list[self.INSTANCES_KEY] = self.instances.count()

        if self.subnets:
            nodes_count += 1
            resources_list[self.SUBNETS_KEY] = self.subnets.count()

        if self.public_gateways:
            nodes_count += 1
            resources_list[self.PUBLIC_GATEWAYS_KEY] = self.public_gateways.count()

        if self.security_groups:
            nodes_count += 1
            resources_list[self.SECURITY_GROUPS_KEY] = self.security_groups.count()

        if self.get_load_balancer_count():
            nodes_count += 1
            resources_list[self.LOAD_BALANCERS_KEY] = self.get_load_balancer_count()

        if self.vpn_gateways:
            nodes_count += 1
            resources_list[self.VPN_GATEWAYS_KEY] = self.vpn_gateways.count()

        if self.kubernetes_clusters:
            nodes_count += 1
            resources_list[self.KUBERNETES_CLUSTERS_KEY] = self.kubernetes_clusters.count()

        if self.instance_groups:
            nodes_count += 1
            resources_list[self.INSTANCE_GROUPS_KEY] = self.instance_groups.count()

        if self.routing_tables:
            nodes_count += 1
            resources_list[self.ROUTING_TABLES_KEY] = self.routing_tables.count()

        if self.acls:
            nodes_count += 1
            resources_list[self.NETWORK_ACLS_KEY] = self.acls.count()

        nodes_count += 1  # this count is for the vpc itself

        return {
            "nodes": nodes_count,
            "resources_list": resources_list
        }
