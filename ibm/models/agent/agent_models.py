import uuid
from datetime import datetime

from sqlalchemy import Column, DateTime, Enum, Integer, String, Text, JSON
from sqlalchemy.orm import deferred

from ibm.models import IBMRegionalResourceMixin
from ibm.models.base import Base


class OnPremCluster(IBMRegionalResourceMixin, Base):
    ID_KEY = "id"
    NAME_KEY = "name"
    SERVER_IP_KEY = "server_ip"
    CLIENT_CERTIFICATION_DATA_KEY = "client_certificate_data"
    CLIENT_KEY_DATA_KEY = "client_key_data"
    WORKER_COUNT_KEY = "worker_count"
    KUBE_VERSION_KEY = "kube_version"
    CREATED_AT_KEY = "created_at"
    COS_KEY = "cos"
    WORKLOADS_KEY = "workloads"
    KUBE_CONFIG_KEY = "kube_config"
    CLUSTER_TYPE_KEY = "cluster_type"
    AGENT_ID_KEY = "agent_id"

    OPENSHIFT_CLUSTER = "openshift"
    KUBERNETES_CLUSTER = "kubernetes"
    ALL_CLUSTER_TYPES_LIST = [OPENSHIFT_CLUSTER, KUBERNETES_CLUSTER]

    CRZ_BACKREF_NAME = "on_prem_clusters"

    __tablename__ = "on_prem_clusters"

    id = Column(String(32), primary_key=True)
    name = Column(String(255), nullable=False)
    server_ip = Column(String(255), nullable=False)
    client_certificate_data = Column(Text, nullable=False)
    client_key_data = Column(Text, nullable=False)
    worker_count = Column(Integer, nullable=True)
    kube_version = Column(String(255), nullable=True)
    created_at = Column(DateTime)
    cos = Column(JSON(), nullable=True)
    workloads = deferred(Column(JSON))
    kube_config = deferred(Column(JSON))
    cluster_type = Column(Enum(*ALL_CLUSTER_TYPES_LIST), nullable=True)
    agent_id = Column(String(100), nullable=False)

    def __init__(self, name, server_ip, client_certificate_data, client_key_data, workloads, kube_config, agent_id,
                 worker_count=None, kube_version=None, cluster_type=None, cloud_id=None):
        self.created_at = datetime.utcnow()
        self.id = str(uuid.uuid4().hex)
        self.name = name
        self.server_ip = server_ip
        self.client_certificate_data = client_certificate_data
        self.client_key_data = client_key_data
        self.worker_count = worker_count
        self.kube_version = kube_version
        self.cluster_type = cluster_type
        self.workloads = workloads
        self.kube_config = kube_config
        self.agent_id = agent_id
        self.cloud_id = cloud_id

    def to_json(self):
        return {
            "id": self.id,
            "name": self.name,
            "server_ip": self.server_ip,
            "client_certificate_data": self.client_certificate_data,
            "client_key_data": self.client_key_data,
            "create_at": str(self.created_at)
        }

    def request_json(self):
        return {
            "id": self.id,
            "name": self.name,
            "worker_count": self.worker_count,
            "kube_version": self.kube_version,
            "discovered_at": str(self.created_at),
            "cluster_type": self.cluster_type,
            "workloads": self.workloads,
            "cloud_id": self.cloud_id if self.cloud_id is not None else "null",
        }

    def cluster_json(self):
        return {
            "id": self.id,
            "name": self.name,
            "worker_count": self.worker_count,
            "kube_version": self.kube_version,
            "cluster_type": self.cluster_type,
            "workloads": self.workloads,
            "cloud_id": self.cloud_id if self.cloud_id is not None else "null",
        }

    def to_report_json(self):
        return {
            "id": self.id,
            "name": self.name,
            "status": "SUCCESS",
            "message": ""
        }
