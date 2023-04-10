import uuid

from sqlalchemy import Column, ForeignKey, JSON, String
from sqlalchemy.orm import deferred, relationship
from sqlalchemy.schema import UniqueConstraint

from ibm.common.consts import DUMMY_ACCESS_KEY_ID, DUMMY_BACKUP_ID, DUMMY_CLOUD_ID, DUMMY_CLOUD_NAME, \
    DUMMY_COS_BUCKET_ID, DUMMY_COS_ID, DUMMY_REGION_ID, DUMMY_REGION_NAME
from ibm.common.utils import dict_keys_camel_to_snake_case
from ibm.models.base import Base
from ibm.models.ibm.mixins import IBMCloudResourceMixin, IBMRegionalResourceMixin


class IBMSatelliteLocation(IBMCloudResourceMixin, Base):
    """
    This class holds the model definition for IBMCloud Satellite Location.
    https://containers.cloud.ibm.com/global/swagger-global-api/#/satellite-location
    """
    __tablename__ = "ibm_satellite_locations"

    CRZ_BACKREF_NAME = "satellite_locations"

    ID_KEY = "id"
    NAME_KEY = "name"
    LOCATION_KEY = "location"
    LOCATION_DESCRIPTIVE_NAME_KEY = "descriptive_name"
    ZONES_KEY = "zones"

    id = Column(String(32), primary_key=True)
    name = Column(String(32), nullable=False)
    location = Column(String(10), nullable=False)
    zones = Column(String(255), nullable=False)

    sat_clusters = relationship(
        "IBMSatelliteCluster",
        backref="ibm_satellite_location",
        cascade="all, delete-orphan",
        passive_deletes=True,
        lazy="dynamic")


class IBMSatelliteCluster(IBMRegionalResourceMixin, Base):
    ID_KEY = "id"
    NAME_KEY = "name"
    POD_SUBNET_KEY = "pod_subnet"
    SERVICE_SUBNET_KEY = "service_subnet"
    MASTER_KUBE_VERSION_KEY = "master_kube_version"
    STATE_KEY = "state"
    PROVIDER_KEY = "provider"
    CLUSTER_TYPE_KEY = "cluster_type"
    RESOURCE_ID_KEY = "resource_id"
    WORKLOADS_KEY = "workloads"
    INGRESS_KEY = "ingress"
    SERVICE_END_POINT_KEY = "service_endpoint"
    RESOURCE_GROUP_KEY = "resource_group"
    WORKER_POOLS_KEY = "worker_pools"
    ASSOCIATED_RESOURCES_KEY = "associated_resources"
    RESOURCE_JSON_KEY = "resource_json"
    CLASSIC_CLUSTER_INGRESS_HOST_NAME = "classic_cluster_ingress_hostname"
    CLASSIC_CLUSTER_NAME = "classic_cluster_name"
    COS_BUCKET_ID_KEY = "cos_bucket_id"
    CLOUD_OBJECT_STORAGE_ID_KEY = "cloud_object_storage_id"
    COS_ACCESS_KEYS_ID_KEY = "cos_access_keys_id"
    DRAAS_RESTORE_TYPE_IKS_KEY = "draas_restore_type_iks"
    BACKUP_ID_KEY = "backup_id"
    BACKUP_NAME_KEY = "backup_name"
    INFRASTRUCTURE_TOPOLOGY_KEY = "infrastructure_topology"
    KUBE_CONFIG_KEY = "kube_config"

    CRZ_BACKREF_NAME = "ibm_satellite_clusters"

    # state consts
    STATE_DELETING = "deleting"
    STATE_DEPLOY_FAILED = "deploy_failed"
    STATE_PENDING = "pending"
    STATE_DEPLOYING = "deploying"
    STATE_NORMAL = "normal"
    STATE_WARNING = "warning"
    STATE_CRITICAL = "critical"
    STATE_UNSUPPORTED = "unsupported"
    STATES_LIST = [
        STATE_NORMAL, STATE_DEPLOYING, STATE_DELETING, STATE_DEPLOY_FAILED,
        STATE_PENDING, STATE_WARNING, STATE_CRITICAL, STATE_UNSUPPORTED
    ]

    # cluster type
    OPENSHIFT_CLUSTER = "openshift"
    ALL_CLUSTER_TYPES_LIST = [OPENSHIFT_CLUSTER]

    __tablename__ = "ibm_satellite_clusters"

    id = Column(String(32), primary_key=True)
    name = Column(String(32), nullable=False)
    pod_subnet = Column(String(255), nullable=True)
    service_subnet = Column(String(255), nullable=True)
    master_kube_version = Column(String(255), nullable=False)
    state = Column(String(50))
    agent_id = Column(String(255))
    provider = Column(String(50), nullable=False)
    cluster_type = Column(String(32), nullable=False)
    resource_id = Column(String(64), nullable=False)
    workloads = deferred(Column(JSON))
    kube_config = deferred(Column(JSON))
    ingress = Column(JSON)
    service_endpoint = Column(JSON)
    infrastructure_topology = Column(String(255))

    resource_group_id = Column(String(32), ForeignKey("ibm_resource_groups.id", ondelete="CASCADE"))

    sat_location = Column(String(32), ForeignKey("ibm_satellite_locations.id", ondelete="CASCADE"))

    __table_args__ = (
        UniqueConstraint(resource_id, "cloud_id", name="uix_ibm_resource_id_cloud_id"),
    )

    def __init__(self, name, master_kube_version, provider="satellite", infrastructure_topology=None,
                 ingress=None, cluster_type=None, service_endpoint=None, resource_id=None, pod_subnet=None,
                 service_subnet=None, state=None, cloud_id=None, region_id=None):
        self.id = str(uuid.uuid4().hex)
        self.name = name
        self.pod_subnet = pod_subnet
        self.service_subnet = service_subnet
        self.master_kube_version = master_kube_version
        self.state = state
        self.provider = provider
        self.infrastructure_topology = infrastructure_topology
        self.cluster_type = cluster_type
        self.resource_id = resource_id
        self.cloud_id = cloud_id
        self.region_id = region_id
        self.ingress = ingress
        self.service_endpoint = service_endpoint

    def to_reference_json(self):
        return {
            self.ID_KEY: self.id,
            self.NAME_KEY: self.name,
            self.MASTER_KUBE_VERSION_KEY: self.master_kube_version,
            self.CLUSTER_TYPE_KEY: self.cluster_type,
        }

    def validate_json_for_schema(self):
        return {
            self.ID_KEY: self.id,
            self.RESOURCE_JSON_KEY: {
                self.NAME_KEY: self.name,
                self.MASTER_KUBE_VERSION_KEY: self.master_kube_version,
                self.CLUSTER_TYPE_KEY: self.cluster_type,
            }
        }

    def to_json(self, workloads=False, kube_config=False):
        json_data = {
            self.ID_KEY: self.id,
            self.NAME_KEY: self.name,
            self.POD_SUBNET_KEY: self.pod_subnet,
            self.SERVICE_SUBNET_KEY: self.service_subnet,
            self.MASTER_KUBE_VERSION_KEY: self.master_kube_version,
            self.STATE_KEY: self.state,
            self.PROVIDER_KEY: self.provider,
            self.CLUSTER_TYPE_KEY: self.cluster_type,
            self.RESOURCE_ID_KEY: self.resource_id,
            self.INGRESS_KEY: self.ingress,
            self.SERVICE_END_POINT_KEY: self.service_endpoint,
            self.INFRASTRUCTURE_TOPOLOGY_KEY: self.infrastructure_topology,
            self.IBM_CLOUD_KEY: self.ibm_cloud.to_reference_json(),
            self.RESOURCE_GROUP_KEY: self.resource_group.to_reference_json() if self.resource_group else {},
            self.REGION_KEY: self.region.to_reference_json() if self.region else {},
        }
        if workloads:
            json_data[self.WORKLOADS_KEY] = self.workloads if self.workloads else list()
        if kube_config:
            json_data[self.KUBE_CONFIG_KEY] = self.kube_config if self.kube_config else dict()

        return json_data

    def ibm_draas_json(self):
        resource_json = {
            self.CLASSIC_CLUSTER_INGRESS_HOST_NAME: self.ingress['hostname'],
            self.CLASSIC_CLUSTER_NAME: self.name,
            self.NAME_KEY: self.name,
            self.MASTER_KUBE_VERSION_KEY: self.master_kube_version,
            self.PROVIDER_KEY: self.provider,
            self.RESOURCE_ID_KEY: self.resource_id,
            self.POD_SUBNET_KEY: self.pod_subnet,
            self.SERVICE_SUBNET_KEY: self.service_subnet,
            self.STATE_KEY: self.state,
            self.INFRASTRUCTURE_TOPOLOGY_KEY: self.infrastructure_topology,
            self.CLUSTER_TYPE_KEY: self.cluster_type,
            self.INGRESS_KEY: self.ingress,
            self.RESOURCE_GROUP_KEY: {"id": self.resource_group_id},
            self.WORKLOADS_KEY: self.workloads,
        }
        cluster_schema = {
            self.ID_KEY: str(uuid.uuid4().hex),
            self.IBM_CLOUD_KEY: {
                self.ID_KEY: DUMMY_CLOUD_ID,
                self.NAME_KEY: DUMMY_CLOUD_NAME,
            },
            self.REGION_KEY: {
                self.ID_KEY: DUMMY_REGION_ID,
                self.NAME_KEY: DUMMY_REGION_NAME,
            },
            self.COS_BUCKET_ID_KEY: DUMMY_COS_BUCKET_ID,
            self.CLOUD_OBJECT_STORAGE_ID_KEY: DUMMY_COS_ID,
            self.COS_ACCESS_KEYS_ID_KEY: DUMMY_ACCESS_KEY_ID,
            # "managed_view": None,
            self.BACKUP_ID_KEY: DUMMY_BACKUP_ID,
            self.BACKUP_NAME_KEY: "backup-name",
            self.DRAAS_RESTORE_TYPE_IKS_KEY: "Should be one of these values "
                                             "TYPE_EXISTING_VPC_NEW_IKS,"
                                             " TYPE_NEW_VPC_NEW_IKS,"
                                             " TYPE_EXISTING_IKS",
            self.RESOURCE_JSON_KEY: resource_json
        }

        return cluster_schema

    @classmethod
    def to_json_body(cls, json_body, db_session, previous_resources=None):
        json_data = {
            "kubeVersion": json_body['master_kube_version'],
            "name": json_body['name'],
            "podSubnet": json_body['pod_subnet'] if json_body.get('pod_subnet') else "",
            "provider": json_body['provider'] if json_body.get('provider') else "satellite",
            "serviceSubnet": json_body['service_subnet'] if json_body.get('service_subnet') else "172.21.0.0/16"
        }
        return json_data

    @classmethod
    def from_ibm_json_body(cls, json_body):
        return cls(
            name=json_body["name"],
            master_kube_version=json_body["masterKubeVersion"],
            provider=json_body["provider"],
            resource_id=json_body["id"],
            pod_subnet=json_body['podSubnet'],
            service_subnet=json_body['serviceSubnet'],
            state=json_body['state'],
            infrastructure_topology=json_body.get("infrastructure_topology"),
            cluster_type=json_body['type'],
            ingress=dict_keys_camel_to_snake_case(json_body["ingress"]),
            service_endpoint=dict_keys_camel_to_snake_case(json_body['serviceEndpoints'])
            if json_body.get('serviceEndpoints') else None
        )

    def dis_params_eq(self, other):
        assert isinstance(other, self.__class__)

        return (self.name == other.name and self.master_kube_version == other.master_kube_version and
                self.provider == other.provider and self.resource_id == other.resource_id and
                self.pod_subnet == other.pod_subnet and self.service_subnet == other.service_subnet and
                self.state == other.state and self.cluster_type == other.cluster_type and
                self.ingress == other.ingress and self.service_endpoint == other.service_endpoint)

    def update_from_object(self, other):
        assert isinstance(other, self.__class__)

        self.name = other.name
        self.master_kube_version = other.master_kube_version
        self.provider = other.provider
        self.resource_id = other.resource_id
        self.pod_subnet = other.pod_subnet
        self.service_subnet = other.service_subnet
        self.state = other.state
        self.cluster_type = other.cluster_type
        self.ingress = other.ingress
        self.service_endpoint = other.service_endpoint

    def dis_add_update_db(self, session, db_clusters, db_cloud, db_resource_group):
        db_clusters_id_obj_dict = dict()
        db_clusters_name_obj_dict = dict()
        for db_cluster in db_clusters:
            db_clusters_id_obj_dict[db_cluster.resource_id] = db_cluster
            db_clusters_name_obj_dict[db_cluster.name] = db_cluster

        if self.resource_id not in db_clusters_id_obj_dict and self.name in db_clusters_name_obj_dict:
            # Creation Pending / Creating
            existing = db_clusters_name_obj_dict[self.name]
        elif self.resource_id in db_clusters_id_obj_dict:
            # Created. Update everything including name
            existing = db_clusters_id_obj_dict[self.resource_id]
        else:
            existing = None

        if not existing:
            self.ibm_cloud = db_cloud
            self.resource_group = db_resource_group
            session.commit()
            return

        if not self.dis_params_eq(existing):
            existing.update_from_object(self)

        session.commit()
