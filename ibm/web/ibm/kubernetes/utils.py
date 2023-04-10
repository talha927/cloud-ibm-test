from datetime import datetime

from kubernetes import client
from kubernetes.client import Configuration
from kubernetes.config import kube_config

from ibm.common.consts import ONPREM
from ibm.models import IBMKubernetesCluster, WorkflowRoot, WorkflowTask
from ibm.web import db as ibmdb
from ibm.web.ibm.kubernetes.consts import BACKUP, RESTORE, velero_payload


class Kubernetes(object):
    def __init__(self, configuration_json):
        self.configuration_json = configuration_json

    @property
    def client(self):
        kubernetes_loader = kube_config.KubeConfigLoader(self.configuration_json)
        call_config = type.__call__(Configuration)
        kubernetes_loader.load_and_set(call_config)
        Configuration.set_default(call_config)
        return client


def create_ibm_kubernetes_cluster_migration_workflow(data, user, db_session=None, sketch=False):
    if not db_session:
        db_session = ibmdb.session

    workflow_name = IBMKubernetesCluster.__name__
    if data["resource_json"].get("name"):
        workflow_name = ' '.join([workflow_name, data["resource_json"]["name"]])

    workflow_root = WorkflowRoot(user_id=user["id"], project_id=user["project_id"], workflow_name=workflow_name,
                                 workflow_nature="CREATE", fe_request_data=data)

    if data.get('managed_view'):
        create_cluster_task = WorkflowTask(
            task_type=WorkflowTask.TYPE_CREATE, resource_type=IBMKubernetesCluster.__name__,
            task_metadata=data
        )

        create_sync_workloads_task = WorkflowTask(
            task_type=WorkflowTask.TYPE_SYNC,
            resource_type=f"{IBMKubernetesCluster.__name__}_workloads",
            task_metadata=data)

        workflow_root.add_next_task(create_cluster_task)
        create_cluster_task.add_next_task(create_sync_workloads_task)

    else:
        data['backup_name'] = "backup" + str(datetime.utcnow().strftime("-%m-%d-%Y%H-%M-%S"))
        data["backup_provider"] = "classic"
        create_backup_task = WorkflowTask(
            task_type=WorkflowTask.TYPE_BACKUP, resource_type=IBMKubernetesCluster.__name__,
            task_metadata=data
        )

        create_cluster_task = WorkflowTask(
            task_type=WorkflowTask.TYPE_CREATE, resource_type=IBMKubernetesCluster.__name__,
            task_metadata=data
        )

        create_restore_task = WorkflowTask(
            task_type=WorkflowTask.TYPE_RESTORE, resource_type=IBMKubernetesCluster.__name__,
            task_metadata=data)

        create_sync_workloads_task = WorkflowTask(
            task_type=WorkflowTask.TYPE_SYNC,
            resource_type=f"{IBMKubernetesCluster.__name__}_workloads",
            task_metadata=data)

        workflow_root.add_next_task(create_backup_task)
        create_backup_task.add_next_task(create_cluster_task)
        create_cluster_task.add_next_task(create_restore_task)
        create_restore_task.add_next_task(create_sync_workloads_task)

    if not sketch:
        db_session.add(workflow_root)

    db_session.commit()
    return workflow_root


def construct_payload(cluster_name, kube_config, hmac_keys, operation_type, bucket_name, region,
                      source_cloud, cluster_type=None, namespaces=None, backup_name=None, restore_name=None,
                      persistent_volume_claims=None, target_cluster_host_name=None, source_cluster_host_name=None,
                      agent_id=None, user_id=None, auth_type=None, target_cloud=None, satellite=False):
    velero_payload["cluster_name"] = cluster_name
    if cluster_type:
        velero_payload["cluster_type"] = cluster_type.upper()
    velero_payload["kube_config"] = kube_config
    if source_cloud in ["AWS", "IBM", "ONPREM"]:
        velero_payload["source_cloud"] = source_cloud
        velero_payload["hmac"] = {
            "access_key_id": hmac_keys["access_key"],
            "secret_access_key": hmac_keys["secret_key"]
        }

    meta = {
        "task_type": operation_type,
        "backup_name": backup_name,
        "bucket_region": region,
        "bucket_name": bucket_name
    }

    if operation_type == BACKUP:
        meta["namespaces"] = namespaces
        if target_cloud:
            velero_payload["target_cloud"] = target_cloud

    elif operation_type == RESTORE:
        meta["restore_name"] = restore_name
        meta["persistent_volume_claims"] = persistent_volume_claims
        if target_cluster_host_name:
            meta["target_cluster_host_name"] = target_cluster_host_name
        if source_cluster_host_name:
            meta["source_cluster_host_name"] = source_cluster_host_name
        velero_payload["target_cloud"] = "IBM" if not satellite and target_cloud is not ONPREM else ONPREM

    # For satellite and on-prem cluster integrations
    if agent_id:
        velero_payload["agent_id"] = agent_id
    if user_id:
        velero_payload["user_id"] = user_id
    if auth_type:
        velero_payload["auth_type"] = auth_type

    velero_payload["meta_data"] = meta
    return velero_payload
