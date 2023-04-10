import uuid

from sqlalchemy import Column, String
from sqlalchemy.orm import relationship

from ibm.models.base import Base
from ibm.models.ibm.mixins import IBMCloudResourceMixin


class IBMResourceGroup(IBMCloudResourceMixin, Base):
    ID_KEY = "id"
    NAME_KEY = "name"
    RESOURCE_ID_KEY = "resource_id"
    MESSAGE_KEY = ""
    STATUS_KEY = "status"
    RESOURCE_GROUP_KEY = "resource_group"

    CRZ_BACKREF_NAME = "resource_groups"

    __tablename__ = "ibm_resource_groups"

    id = Column(String(32), primary_key=True)
    resource_id = Column(String(64))
    name = Column(String(255), nullable=False)

    vpc_networks = relationship(
        "IBMVpcNetwork",
        backref="resource_group",
        cascade="all, delete-orphan",
        passive_deletes=True,
        lazy="dynamic",
    )
    floating_ips = relationship(
        "IBMFloatingIP",
        backref="resource_group",
        cascade="all, delete-orphan",
        passive_deletes=True,
        lazy="dynamic"
    )
    network_acls = relationship(
        "IBMNetworkAcl",
        backref="resource_group",
        cascade="all, delete-orphan",
        passive_deletes=True,
        lazy="dynamic"
    )
    subnets = relationship(
        "IBMSubnet",
        backref="resource_group",
        cascade="all, delete-orphan",
        passive_deletes=True,
        lazy="dynamic"
    )
    ike_policies = relationship(
        "IBMIKEPolicy",
        backref="resource_group",
        cascade="all, delete-orphan",
        passive_deletes=True,
        lazy="dynamic",
    )
    ipsec_policies = relationship(
        "IBMIPSecPolicy",
        backref="resource_group",
        cascade="all, delete-orphan",
        lazy="dynamic",
    )
    public_gateways = relationship(
        "IBMPublicGateway",
        backref="resource_group",
        cascade="all, delete-orphan",
        passive_deletes=True,
        lazy="dynamic",
    )
    vpn_gateways = relationship(
        "IBMVpnGateway",
        backref="resource_group",
        cascade="all, delete-orphan",
        passive_deletes=True,
        lazy="dynamic",
    )
    security_groups = relationship(
        "IBMSecurityGroup",
        backref="resource_group",
        cascade="all, delete-orphan",
        passive_deletes=True,
        lazy="dynamic",
    )
    instances = relationship(
        "IBMInstance",
        backref="resource_group",
        cascade="all, delete-orphan",
        passive_deletes=True,
        lazy="dynamic",
    )
    ssh_keys = relationship(
        "IBMSshKey",
        backref="resource_group",
        cascade="all, delete-orphan",
        passive_deletes=True,
        lazy="dynamic",
    )
    load_balancers = relationship(
        "IBMLoadBalancer",
        backref="resource_group",
        cascade="all, delete-orphan",
        passive_deletes=True,
        lazy="dynamic",
    )
    images = relationship(
        "IBMImage",
        backref="resource_group",
        cascade="all, delete-orphan",
        passive_deletes=True,
        lazy="dynamic",
    )
    transit_gateways = relationship(
        "IBMTransitGateway",
        backref="resource_group",
        cascade="all, delete-orphan",
        passive_deletes=True,
        lazy="dynamic",
    )
    dedicated_hosts = relationship(
        "IBMDedicatedHost",
        backref="resource_group",
        cascade="all, delete-orphan",
        passive_deletes=True,
        lazy="dynamic",
    )
    dedicated_host_groups = relationship(
        "IBMDedicatedHostGroup",
        backref="resource_group",
        cascade="all, delete-orphan",
        passive_deletes=True,
        lazy="dynamic",
    )
    kubernetes_clusters = relationship(
        "IBMKubernetesCluster",
        backref="resource_group",
        cascade="all, delete-orphan",
        passive_deletes=True,
        lazy="dynamic"
    )
    satellite_clusters = relationship(
        "IBMSatelliteCluster",
        backref="resource_group",
        cascade="all, delete-orphan",
        passive_deletes=True,
        lazy="dynamic"
    )
    instance_groups = relationship(
        "IBMInstanceGroup",
        backref="resource_group",
        cascade="all, delete-orphan",
        passive_deletes=True,
        lazy="dynamic"
    )
    endpoint_gateways = relationship(
        "IBMEndpointGateway",
        backref="resource_group",
        cascade="all, delete-orphan",
        passive_deletes=True,
        lazy="dynamic"
    )
    credential_keys = relationship(
        "IBMServiceCredentialKey",
        backref="resource_group",
        cascade="all, delete-orphan",
        passive_deletes=True,
        lazy="dynamic",
    )

    def __init__(self, name, cloud_id=None, resource_id=None):
        self.id = str(uuid.uuid4().hex)
        self.name = name
        self.resource_id = resource_id
        self.cloud_id = cloud_id

    def to_reference_json(self):
        return {
            self.ID_KEY: self.id,
            self.NAME_KEY: self.name
        }

    def to_json(self):
        return {self.ID_KEY: self.id, self.NAME_KEY: self.name}

    def update_from_object(self, other):
        assert isinstance(other, self.__class__)

        self.name = other.name
        self.resource_id = other.resource_id

    @classmethod
    def from_ibm_json_body(cls, json_body):
        ibm_resource_group = IBMResourceGroup(
            name=json_body["name"],
            resource_id=json_body["id"],
        )
        return ibm_resource_group

    def dis_params_eq(self, other):
        assert isinstance(other, self.__class__)

        return self.name == other.name and self.resource_id == other.resource_id

    def dis_add_update_db(self, session, db_resource_group, db_cloud):
        existing = db_resource_group or None
        if not existing:
            self.ibm_cloud = db_cloud
            session.commit()
            return

        if not self.dis_params_eq(existing):
            existing.update_from_object(self)
        session.commit()
