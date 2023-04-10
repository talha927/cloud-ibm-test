import uuid
from copy import deepcopy

from sqlalchemy import Boolean, Column, Enum, ForeignKey, JSON, PrimaryKeyConstraint, String, Table
from sqlalchemy.orm import backref, deferred, relationship
from sqlalchemy.schema import UniqueConstraint

from ibm.common.consts import CREATED, DUMMY_ACCESS_KEY_ID, DUMMY_BACKUP_ID, DUMMY_CLOUD_ID, \
    DUMMY_CLOUD_NAME, DUMMY_COS_BUCKET_ID, DUMMY_COS_ID, DUMMY_REGION_ID, DUMMY_REGION_NAME, \
    DUMMY_ZONE_ID, DUMMY_ZONE_NAME, OPENSHIFT_OS
from ibm.common.utils import dict_keys_camel_to_snake_case
from ibm.models.base import Base
from ibm.models.ibm.mixins import IBMRegionalResourceMixin

ibm_kubernetes_cluster_zone_subnets = Table(
    "ibm_kubernetes_cluster_zone_subnets",
    Base.metadata,
    Column(
        "zone_id",
        String(32),
        ForeignKey("ibm_kubernetes_cluster_worker_pool_zones.id", ondelete="CASCADE")
    ),
    Column(
        "subnets_id",
        String(32),
        ForeignKey("ibm_subnets.id", ondelete="CASCADE")
    ),
    PrimaryKeyConstraint("zone_id", "subnets_id"),
)


class IBMKubernetesCluster(IBMRegionalResourceMixin, Base):
    ID_KEY = "id"
    NAME_KEY = "name"
    POD_SUBNET_KEY = "pod_subnet"
    SERVICE_SUBNET_KEY = "service_subnet"
    MASTER_KUBE_VERSION_KEY = "master_kube_version"
    DISABLE_PUBLIC_SERVICE_ENDPOINT_KEY = "disable_public_service_endpoint"
    STATUS_KEY = "status"
    PROVIDER_KEY = "provider"
    CLUSTER_TYPE_KEY = "cluster_type"
    RESOURCE_ID_KEY = "resource_id"
    WORKLOADS_KEY = "workloads"
    INGRESS_KEY = "ingress"
    SERVICE_END_POINT_KEY = "service_endpoint"
    RESOURCE_GROUP_KEY = "resource_group"
    VPC_KEY = "vpc"
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

    cluster_status_mapper = {
        "normal": "CREATED",
        "deleting": "DELETING",
        "pending": "CREATING",
        "deploy_failed": "CREATION_FAILED",
        "warning": "WARNING",
        "deploying": "CREATING",
        "critical": "CRITICAL",
        "unsupported": "UNSUPPORTED"
    }

    CRZ_BACKREF_NAME = "ibm_kubernetes_clusters"

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

    # for orchestration type
    ORCHESTRATION_KUBERNETES = "kubernetes"
    ORCHESTRATION_OPENSHIFT = "openshift"

    # cluster type
    OPENSHIFT_CLUSTER = "openshift"
    KUBERNETES_CLUSTER = "kubernetes"
    ALL_CLUSTER_TYPES_LIST = [
        OPENSHIFT_CLUSTER, KUBERNETES_CLUSTER
    ]

    __tablename__ = "ibm_kubernetes_clusters"

    id = Column(String(32), primary_key=True)
    name = Column(String(32), nullable=False)
    pod_subnet = Column(String(255), nullable=True)
    service_subnet = Column(String(255), nullable=True)
    master_kube_version = Column(String(255), nullable=False)
    disable_public_service_endpoint = Column(Boolean, nullable=True)
    status = Column(String(255), nullable=False)
    provider = Column(String(50), nullable=False)
    cluster_type = Column(Enum(*ALL_CLUSTER_TYPES_LIST))
    resource_id = Column(String(64), nullable=False)
    workloads = deferred(Column(JSON))
    ingress = Column(JSON)
    service_endpoint = Column(JSON)

    resource_group_id = Column(String(32), ForeignKey("ibm_resource_groups.id", ondelete="CASCADE"))
    vpc_id = Column(String(32), ForeignKey("ibm_vpc_networks.id", ondelete="CASCADE"))

    worker_pools = relationship(
        "IBMKubernetesClusterWorkerPool",
        backref="ibm_kubernetes_cluster",
        cascade="all, delete-orphan",
        passive_deletes=True,
        lazy="dynamic")

    __table_args__ = (
        UniqueConstraint(resource_id, "cloud_id", "vpc_id", name="uix_ibm_resource_id_cloud_id_vpc_id"),
    )

    def __init__(self, name, master_kube_version, provider, disable_public_service_endpoint=None, ingress=None,
                 cluster_type=None, service_endpoint=None, resource_id=None, pod_subnet=None, service_subnet=None,
                 status=None, vpc_id=None, cloud_id=None, region_id=None, workloads=None):
        self.id = str(uuid.uuid4().hex)
        self.name = name
        self.pod_subnet = pod_subnet
        self.service_subnet = service_subnet
        self.master_kube_version = master_kube_version
        self.disable_public_service_endpoint = disable_public_service_endpoint
        self.status = status
        self.provider = provider
        self.cluster_type = cluster_type
        self.resource_id = resource_id
        self.vpc_id = vpc_id
        self.cloud_id = cloud_id
        self.region_id = region_id
        self.ingress = ingress
        self.service_endpoint = service_endpoint
        self.workloads = workloads

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

    def to_json(self, workloads=False):
        json_data = {
            self.ID_KEY: self.id,
            self.NAME_KEY: self.name,
            self.POD_SUBNET_KEY: self.pod_subnet,
            self.SERVICE_SUBNET_KEY: self.service_subnet,
            self.MASTER_KUBE_VERSION_KEY: self.master_kube_version,
            self.DISABLE_PUBLIC_SERVICE_ENDPOINT_KEY: self.disable_public_service_endpoint,
            self.STATUS_KEY: self.status,
            self.PROVIDER_KEY: self.provider,
            self.CLUSTER_TYPE_KEY: self.cluster_type,
            self.RESOURCE_ID_KEY: self.resource_id,
            self.INGRESS_KEY: self.ingress,
            self.SERVICE_END_POINT_KEY: self.service_endpoint,
            self.WORKER_POOLS_KEY: [worker_pool.to_json() for worker_pool in self.worker_pools.all()],
            self.ASSOCIATED_RESOURCES_KEY: {
                self.VPC_KEY: self.vpc_network.to_reference_json()
            },
            self.IBM_CLOUD_KEY: self.ibm_cloud.to_reference_json(),
            self.RESOURCE_GROUP_KEY: self.resource_group.to_reference_json(),
            self.REGION_KEY: self.region.to_reference_json() if self.region else {},
        }
        if workloads:
            json_data[self.WORKLOADS_KEY] = self.workloads if self.workloads else list()
        return json_data

    def from_softlayer_to_ibm_json(self):
        resource_json = {
            self.CLASSIC_CLUSTER_INGRESS_HOST_NAME: self.ingress['hostname'],
            self.CLASSIC_CLUSTER_NAME: self.name,
            self.NAME_KEY: self.name,
            self.MASTER_KUBE_VERSION_KEY: self.master_kube_version,
            self.PROVIDER_KEY: "vpc-gen2",
            self.RESOURCE_ID_KEY: self.resource_id,
            self.POD_SUBNET_KEY: self.pod_subnet,
            self.SERVICE_SUBNET_KEY: self.service_subnet,
            self.STATUS_KEY: self.status,
            self.CLUSTER_TYPE_KEY: self.cluster_type,
            self.INGRESS_KEY: self.ingress,
            self.WORKER_POOLS_KEY: [worker_pool.from_softlayer_to_ibm_json() for worker_pool in
                                    self.worker_pools.all()],
            self.VPC_KEY: {"id": self.vpc_id},
            self.RESOURCE_GROUP_KEY: {"id": self.resource_group_id},
            self.WORKLOADS_KEY: self.workloads,
            self.DISABLE_PUBLIC_SERVICE_ENDPOINT_KEY: False
        }
        if isinstance(self.ingress, list):
            resource_json[self.CLASSIC_CLUSTER_INGRESS_HOST_NAME] = self.ingress[0]["hostname"]
        else:
            resource_json[self.CLASSIC_CLUSTER_INGRESS_HOST_NAME] = self.ingress["hostname"]
        cluster_schema = {
            self.ID_KEY: self.id,
            "ibm_cloud": {
                "id": DUMMY_CLOUD_ID,
                "name": DUMMY_CLOUD_NAME,
            },
            "region": {
                "id": DUMMY_REGION_ID,
                "name": DUMMY_REGION_NAME,
            },
            "cos_bucket_id": DUMMY_COS_BUCKET_ID,
            "cloud_object_storage_id": DUMMY_COS_ID,
            "cos_access_keys_id": DUMMY_ACCESS_KEY_ID,
            "managed_view": None,
            "resource_json": resource_json
        }

        return cluster_schema

    def ibm_draas_json(self):
        resource_json = {
            self.CLASSIC_CLUSTER_NAME: self.name,
            self.NAME_KEY: self.name,
            self.MASTER_KUBE_VERSION_KEY: self.master_kube_version,
            self.PROVIDER_KEY: "vpc-gen2",
            self.RESOURCE_ID_KEY: self.resource_id,
            self.POD_SUBNET_KEY: self.pod_subnet,
            self.SERVICE_SUBNET_KEY: self.service_subnet,
            self.STATUS_KEY: self.status,
            self.CLUSTER_TYPE_KEY: self.cluster_type,
            self.INGRESS_KEY: self.ingress,
            self.WORKER_POOLS_KEY: [worker_pool.from_softlayer_to_ibm_json() for worker_pool in
                                    self.worker_pools.all()],
            self.VPC_KEY: {"id": self.vpc_id},
            self.RESOURCE_GROUP_KEY: {"id": self.resource_group_id},
            self.WORKLOADS_KEY: self.workloads,
            self.DISABLE_PUBLIC_SERVICE_ENDPOINT_KEY: False
        }
        if isinstance(self.ingress, list):
            resource_json[self.CLASSIC_CLUSTER_INGRESS_HOST_NAME] = self.ingress[0]["hostname"]
        else:
            resource_json[self.CLASSIC_CLUSTER_INGRESS_HOST_NAME] = self.ingress["hostname"]
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
        if not previous_resources:
            previous_resources = dict()
        json_data = {
            "disablePublicServiceEndpoint": json_body['disable_public_service_endpoint'],
            "kubeVersion": json_body['master_kube_version'],
            "name": json_body['name'],
            "podSubnet": json_body['pod_subnet'] if json_body.get('pod_subnet') else "",
            "provider": json_body['provider'] if json_body.get('provider') else "vpc-gen2",
            "serviceSubnet": json_body['service_subnet'] if json_body.get('service_subnet') else "172.21.0.0/16",
            "workerPool": IBMKubernetesClusterWorkerPool.to_json_body(json_body['worker_pools'][0], db_session,
                                                                      previous_resources)
        }
        return json_data

    @classmethod
    def from_ibm_json_body(cls, json_body):
        return IBMKubernetesCluster(
            name=json_body["name"],
            master_kube_version=json_body["masterKubeVersion"],
            provider=json_body["provider"],
            resource_id=json_body["id"],
            pod_subnet=json_body['podSubnet'],
            service_subnet=json_body['serviceSubnet'],
            status=json_body['state'],
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
                self.cluster_type == other.cluster_type and self.status == other.status and
                self.ingress == other.ingress and self.service_endpoint == other.service_endpoint)

    def update_from_object(self, other):
        assert isinstance(other, self.__class__)

        self.name = other.name
        self.master_kube_version = other.master_kube_version
        self.provider = other.provider
        self.resource_id = other.resource_id
        self.pod_subnet = other.pod_subnet
        self.service_subnet = other.service_subnet
        self.cluster_type = other.cluster_type
        self.status = other.status,
        self.ingress = other.ingress,
        self.service_endpoint = other.service_endpoint

    def dis_add_update_db(self, session, db_clusters, db_cloud, db_resource_group, db_region, db_vpc):
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
            self.region = db_region
            self.vpc_network = db_vpc
            session.commit()
            return

        if not self.dis_params_eq(existing):
            existing.update_from_object(self)

        session.commit()

    @staticmethod
    def sync_orchestration_versions_from_ibm(json_body, orchestration_type):

        orchestration_versions = []

        for orchestration_type_detail in json_body[orchestration_type]:
            orchestration = {
                "version": "{}.{}.{}{}".format(
                    orchestration_type_detail["major"],
                    orchestration_type_detail["minor"],
                    orchestration_type_detail["patch"],
                    "_openshift" if orchestration_type == IBMKubernetesCluster.ORCHESTRATION_OPENSHIFT else ""
                ),
                "default": orchestration_type_detail["default"],
                "end_of_service": orchestration_type_detail["end_of_service"]
            }
            orchestration_versions.append(orchestration)

        return sorted(orchestration_versions, key=lambda i: i['version'], reverse=True)

    @staticmethod
    def sync_flavors_from_ibm(zone_flavors):
        flavors = dict()
        iks_flavors = sorted(zone_flavors,
                             key=lambda i: (i['name'].split("x")[0], i['cores'], i['memory'].split("G")[0]))
        flavors["kubernetes"] = deepcopy(iks_flavors)
        # for openshift flavors
        zone_flavors_for_openshift = []

        for zone_flavor in zone_flavors:
            memory = zone_flavor.get("memory").split("GB")

            if int(zone_flavor.get("cores")) >= 4 and int(memory[0]) >= 16:
                zone_flavor["os"] = OPENSHIFT_OS
                zone_flavors_for_openshift.append(zone_flavor)

        openshift_flavors = sorted(zone_flavors_for_openshift,
                                   key=lambda i: (i['name'].split("x")[0], i['cores'], i['memory'].split("G")[0]))
        flavors["openshift"] = deepcopy(openshift_flavors)
        return flavors

    @staticmethod
    def sync_workloads_for_clsuter(cluster_kube_config):
        cluster_workloads = list()

        namespaces = cluster_kube_config.client.CoreV1Api().list_namespace(watch=False)
        for namespace in namespaces.items:
            workload = {"namespace": "", "pod": [], "svc": [], "pvc": []}

            if namespace.metadata.name != "velero":
                # namespace
                workload["namespace"] = namespace.metadata.name
                # pods
                pods = cluster_kube_config.client.CoreV1Api().list_namespaced_pod(namespace=namespace.metadata.name)
                if pods.items:
                    for pod in pods.items:
                        workload["pod"].append(pod.metadata.name)
                # pvcs
                persistent_volume_claims = cluster_kube_config.client.CoreV1Api(). \
                    list_namespaced_persistent_volume_claim(namespace=namespace.metadata.name)
                if persistent_volume_claims.items:
                    for pvc in persistent_volume_claims.items:
                        storage_class_name = pvc.spec.storage_class_name

                        persistent_volume_claims = {
                            "name": pvc.metadata.name,
                            "size": pvc.spec.resources.requests['storage'],
                            "phase": pvc.status.phase,
                        }

                        if pvc.status.phase == "Bound" and storage_class_name != "manual":
                            storage_provisioner = pvc.metadata.annotations.get(
                                'volume.beta.kubernetes.io/storage-provisioner') if pvc.metadata.annotations else None
                            if storage_provisioner:
                                persistent_volume_claims['type'] = storage_provisioner
                            elif storage_class_name == "default":
                                storage_classes_list = cluster_kube_config.client.StorageV1Api().list_storage_class()
                                for storage_class in storage_classes_list.items:
                                    if storage_class.metadata.annotations.get(
                                            'storageclass.kubernetes.io/is-default-class') == 'true':
                                        persistent_volume_claims['type'] = storage_class.provisioner
                            else:
                                storage_class = cluster_kube_config.client.StorageV1Api().read_storage_class(
                                    storage_class_name, pretty="true")
                                persistent_volume_claims['type'] = storage_class.provisioner if storage_class else ""

                        workload["pvc"].append(persistent_volume_claims)

                # svcs
                services = cluster_kube_config.client.CoreV1Api().list_namespaced_service(
                    namespace=namespace.metadata.name)
                if services.items:
                    for svc in services.items:
                        workload["svc"].append(svc.metadata.name)
                cluster_workloads.append(workload)
        return cluster_workloads

    def backup_json(self, namespaces=None):
        if not namespaces:
            namespaces = list()
        json_data = {
            self.ID_KEY: self.id,
            self.RESOURCE_ID_KEY: self.resource_id,
            self.NAME_KEY: self.name,
            self.POD_SUBNET_KEY: self.pod_subnet,
            self.SERVICE_SUBNET_KEY: self.service_subnet,
            self.MASTER_KUBE_VERSION_KEY: self.master_kube_version,
            self.DISABLE_PUBLIC_SERVICE_ENDPOINT_KEY: self.disable_public_service_endpoint,
            self.PROVIDER_KEY: self.provider,
            self.CLUSTER_TYPE_KEY: self.cluster_type,
            self.WORKER_POOLS_KEY: [worker_pool.to_json() for worker_pool in self.worker_pools.all()],
            self.WORKLOADS_KEY: self.workloads if self.workloads else list(),
            self.VPC_KEY: self.vpc_network.to_reference_json()
        }
        if self.workloads:
            json_data[self.WORKLOADS_KEY] = list()
            for workload in self.workloads:
                if workload["namespace"] in namespaces:
                    json_data[self.WORKLOADS_KEY].append(workload)

        if self.provider != "vpc-gen2":  # For classic clusters
            json_data[self.CLASSIC_CLUSTER_NAME] = self.name

        return json_data


class IBMKubernetesClusterWorkerPool(Base):
    ID_KEY = "id"
    NAME_KEY = "name"
    DISK_ENCRYPTION_KEY = "disk_encryption"
    FLAVOR_KEY = "flavor"
    WORKER_COUNT_KEY = "worker_count"
    RESOURCE_ID_KEY = "resource_id"
    KUBERNETES_CLUSTER_KEY = "kubernetes_cluster"
    WORKER_ZONES_KEY = "worker_zones"
    STATUS_KEY = "status"

    __tablename__ = "ibm_kubernetes_cluster_worker_pools"

    id = Column(String(32), primary_key=True)
    name = Column(String(32), nullable=False)
    status = Column(String(50), nullable=False)
    disk_encryption = Column(Boolean, nullable=False, default=True)
    flavor = Column(String(255), nullable=False)
    worker_count = Column(String(32), nullable=False)
    resource_id = Column(String(64), nullable=False)

    kubernetes_cluster_id = Column(String(32), ForeignKey('ibm_kubernetes_clusters.id', ondelete="CASCADE"))

    worker_zones = relationship(
        "IBMKubernetesClusterWorkerPoolZone",
        backref="ibm_kubernetes_cluster_worker_pools",  # TODO: this should singular
        cascade="all, delete-orphan",
        passive_deletes=True,
        lazy="dynamic"
    )

    def __init__(self, name, flavor, worker_count, disk_encryption=True, resource_id=None, status=CREATED):
        self.id = str(uuid.uuid4().hex)
        self.name = name
        self.disk_encryption = disk_encryption
        self.flavor = flavor
        self.worker_count = worker_count
        self.resource_id = resource_id
        self.status = status

    def to_reference_json(self):
        return {
            self.ID_KEY: self.id,
            self.NAME_KEY: self.name
        }

    def to_json(self):
        json_data = {
            self.ID_KEY: self.id,
            self.NAME_KEY: self.name,
            self.STATUS_KEY: self.status,
            self.DISK_ENCRYPTION_KEY: self.disk_encryption,
            self.FLAVOR_KEY: self.flavor,
            self.WORKER_COUNT_KEY: self.worker_count,
            self.RESOURCE_ID_KEY: self.resource_id,
            self.KUBERNETES_CLUSTER_KEY: self.ibm_kubernetes_cluster.to_reference_json(),
            self.WORKER_ZONES_KEY: [worker_zone.to_json() for worker_zone in self.worker_zones.all()]
        }
        return json_data

    def from_softlayer_to_ibm_json(self):
        worker_pool_schema = {
            self.ID_KEY: self.id,
            self.NAME_KEY: self.name,
            self.DISK_ENCRYPTION_KEY: self.disk_encryption,
            self.WORKER_COUNT_KEY: self.worker_count,
            self.FLAVOR_KEY: self.flavor,
            self.WORKER_ZONES_KEY: [worker_zone.from_softlayer_to_ibm_json() for worker_zone in self.worker_zones.all()]
        }
        return worker_pool_schema

    @classmethod
    def to_json_body(cls, json_body, db_session, previous_resources=None):
        if not previous_resources:
            previous_resources = dict()
        json_data = {
            "name": json_body['name'],
            "diskEncryption": json_body['disk_encryption'],
            "flavor": json_body['flavor'],
            "workerCount": int(json_body['worker_count']),
            "zones": [
                IBMKubernetesClusterWorkerPoolZone.to_json_body(zone, db_session, previous_resources) for zone in
                json_body["worker_zones"]
            ]
        }
        return json_data

    @classmethod
    def from_ibm_json_body(cls, json_body):
        return IBMKubernetesClusterWorkerPool(
            name=json_body['poolName'],
            disk_encryption=True,
            flavor=json_body['flavor'],
            worker_count=json_body['workerCount'],
            resource_id=json_body['id']
        )

    @classmethod
    def from_classic_ibm_json_body(cls, json_body):
        return IBMKubernetesClusterWorkerPool(
            name=json_body['name'],
            resource_id=json_body['id'],
            worker_count=json_body['sizePerZone'],
            flavor=json_body['machineType']
        )

    def dis_params_eq(self, other):
        assert isinstance(other, self.__class__)

        return (self.name == other.name and self.disk_encryption == other.disk_encryption and
                self.flavor == other.flavor and self.worker_count == other.worker_count and
                self.resource_id == other.resource_id)

    def update_from_object(self, other):
        assert isinstance(other, self.__class__)

        self.name = other.name
        self.disk_encryption = other.disk_encryption
        self.flavor = other.flavor
        self.worker_count = other.worker_count
        self.resource_id = other.resource_id

    def dis_add_update_db(self, session, db_cluster_worker_pools, existing_cluster):
        db_cluster_worker_pools_id_obj_dict = dict()
        for db_cluster_worker_pool in db_cluster_worker_pools:
            db_cluster_worker_pools_id_obj_dict[db_cluster_worker_pool.resource_id] = db_cluster_worker_pool

        if self.resource_id in db_cluster_worker_pools_id_obj_dict:
            existing = db_cluster_worker_pools_id_obj_dict[self.resource_id]
        else:
            existing = None

        if not existing:
            self.ibm_kubernetes_cluster = existing_cluster
            session.commit()
            return self

        if not self.dis_params_eq(existing):
            existing.update_from_object(self)

        existing.ibm_kubernetes_cluster = existing_cluster
        session.commit()
        return existing


class IBMKubernetesClusterWorkerPoolZone(Base):
    ID_KEY = "id"
    NAME_KEY = "name"
    PRIVATE_VLAN_KEY = "private_vlan"
    SUBNETS_KEY = "subnets"
    ZONES_KEY = "zones"

    __tablename__ = "ibm_kubernetes_cluster_worker_pool_zones"

    id = Column(String(32), primary_key=True)
    name = Column(String(32), nullable=False)
    private_vlan = Column(String(255))

    worker_pool_id = Column(String(32), ForeignKey('ibm_kubernetes_cluster_worker_pools.id', ondelete="CASCADE"))

    subnets = relationship(
        "IBMSubnet",
        secondary=ibm_kubernetes_cluster_zone_subnets,
        backref=backref("ibm_kubernetes_cluster_worker_pool_zones"),
        lazy="dynamic",
    )

    def __init__(self, name, private_vlan=None):
        self.id = str(uuid.uuid4().hex)
        self.name = name
        self.private_vlan = private_vlan

    def to_json(self):
        return {
            self.ID_KEY: self.id,
            self.NAME_KEY: self.name,
            self.PRIVATE_VLAN_KEY: self.private_vlan,
            self.SUBNETS_KEY: [subnet.to_reference_json() for subnet in self.subnets.all()]
        }

    def from_softlayer_to_ibm_json(self):
        subnet_zones = self.subnets.all()
        subnet_zone = subnet_zones[0]
        # getting 1st subnet because with zone only one subnet is attached
        worker_pool_zone = {
            self.ID_KEY: self.id,
            self.ZONES_KEY: {"id": DUMMY_ZONE_ID, "name": DUMMY_ZONE_NAME},
            self.SUBNETS_KEY: {"id": subnet_zone.id, "name": subnet_zone.name}
        }
        return worker_pool_zone

    @classmethod
    def to_json_body(cls, json_body, db_session, previous_resources):
        from ibm.models import IBMSubnet, IBMZone
        if not previous_resources:
            previous_resources = dict()

        subnet = previous_resources.get(json_body["subnets"]["id"]) or db_session.query(IBMSubnet).filter_by(
            **json_body['subnets']).first()
        if not subnet:
            raise ValueError(f"Subnet {json_body['subnets'].get('id') or json_body['subnets'].get('name')} not found")

        zone = db_session.query(IBMZone).filter_by(**json_body['zones']).first()
        if not zone:
            raise ValueError(f"Zone {json_body['zone'].get('id') or json_body['zone'].get('name')} not found")

        json_data = {
            "id": zone.name,
            "subnetID": subnet.resource_id
        }
        return json_data

    @classmethod
    def from_ibm_json_body(cls, json_body):
        return IBMKubernetesClusterWorkerPoolZone(
            name=json_body["id"]
        )

    @classmethod
    def from_ibm_json_body_classic(cls, json_body):
        return IBMKubernetesClusterWorkerPoolZone(
            name=json_body["id"],
            private_vlan=json_body["privateVlan"]
        )

    def dis_params_eq(self, other):
        assert isinstance(other, self.__class__)

        return self.name == other.name and self.subnets == other.subnets

    def update_from_object(self, other):
        assert isinstance(other, self.__class__)

        self.name = other.name

    def dis_add_update_db(self, session, db_cluster_worker_pool_zones,
                          existing_cluster_worker_pool, existing_subnet):
        if not (existing_cluster_worker_pool and existing_subnet):
            return
        db_cluster_worker_pool_zones_id_obj_dict = dict()
        db_cluster_worker_pool_zones_name_obj_dict_obj_dict = dict()

        for db_cluster_worker_pool_zone in db_cluster_worker_pool_zones:
            db_cluster_worker_pool_zones_id_obj_dict[
                db_cluster_worker_pool_zone.id] = db_cluster_worker_pool_zone
            db_cluster_worker_pool_zones_name_obj_dict_obj_dict[
                db_cluster_worker_pool_zone.name] = db_cluster_worker_pool_zone

        if not db_cluster_worker_pool_zones_id_obj_dict.get(
                self.id) and db_cluster_worker_pool_zones_name_obj_dict_obj_dict.get(self.name):
            # Creation Pending / Creating
            existing = None
        elif self.id in db_cluster_worker_pool_zones_id_obj_dict:
            # Created. Update everything including name
            existing = db_cluster_worker_pool_zones_id_obj_dict[self.id]
        else:
            existing = None

        if not existing:
            self.ibm_kubernetes_cluster_worker_pools = existing_cluster_worker_pool
            session.add(self)
            session.commit()
            if existing_subnet is not None:
                self.subnets.append(existing_subnet)
                session.commit()
            return

        if not self.dis_params_eq(existing):
            existing.update_from_object(self)
            if not existing_cluster_worker_pool:
                session.delete(self)
                session.commit()
                return
            existing.ibm_kubernetes_cluster_worker_pools = existing_cluster_worker_pool
            if not [i.id for i in existing.subnets.all()] in existing_subnet.id:
                existing.subnets.append(existing_subnet)
            session.commit()
        session.commit()
