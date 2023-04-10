import json.decoder
from copy import deepcopy
from datetime import datetime
from urllib.parse import urljoin

import requests
from croniter import croniter
from kubernetes.client import ApiException
from requests.exceptions import ConnectionError, ReadTimeout, RequestException
from sqlalchemy.orm import undefer
from urllib3.exceptions import ConnectTimeoutError, MaxRetryError, NewConnectionError

from config import VeleroConfig, WorkerConfig
from ibm import get_db_session, LOGGER
from ibm.common.clients.ibm_clients import KubernetesClient
from ibm.common.clients.ibm_clients.exceptions import IBMAuthError, IBMConnectError, IBMExecuteError, \
    IBMInvalidRequestError
from ibm.common.consts import AWS_HEADER, GET_AWS_BACKUP_URL_TEMPLATE, GET_AWS_CLOUD_CREDENTIAL_URL_TEMPLATE
from ibm.common.utils import update_id_or_name_references
from ibm.models import IBMCloud, IBMCloudObjectStorage, IBMCOSBucket, IBMKubernetesCluster, \
    IBMKubernetesClusterWorkerPool, IBMKubernetesClusterWorkerPoolZone, IBMResourceGroup, IBMResourceLog, \
    IBMServiceCredentialKey, IBMVpcNetwork, WorkflowRoot, WorkflowTask, IBMSatelliteCluster
from ibm.models.ibm_draas.draas_models import DisasterRecoveryBackup, DisasterRecoveryResourceBlueprint, \
    DisasterRecoveryScheduledPolicy
from ibm.tasks.celery_app import celery_app as celery
from ibm.tasks.common.tasks_base import IBMWorkflowTasksBase
from ibm.tasks.ibm.task_utils import load_previous_associated_resources
from ibm.web.ibm.kubernetes.consts import BACKUP, BACKUP_FAILURE_ERROR_MSG, CLASSIC_BLOCK_STORAGE_CLASSES, NAMESPACES, \
    PVC_PAYLOAD, RESTORE, RESTORE_FAILURE_ERROR_MSG, VELERO_HEADERS, VELERO_SERVER_URL, CLASSIC_FILE_STORAGE_CLASSES
from ibm.web.ibm.kubernetes.schemas import IBMKubernetesClusterInSchema, IBMKubernetesClusterResourceSchema
from ibm.web.ibm.kubernetes.utils import construct_payload, Kubernetes


def classic_to_gen2_iks_migration(workflow_task_id):
    with get_db_session() as db_session:
        workflow_task = db_session.query(WorkflowTask).filter_by(id=workflow_task_id).first()
        if not workflow_task:
            return

        workflow_task.status = WorkflowTask.STATUS_RUNNING
        db_session.commit()

        task_metadata = deepcopy(workflow_task.task_metadata)
        backup_name = task_metadata["backup_name"]
        cluster_name = task_metadata['resource_json']['name']
        cloud_id = task_metadata["ibm_cloud"]["id"]
        cos_bucket_id = task_metadata["cos_bucket_id"]
        cos_access_keys_id = task_metadata["cos_access_keys_id"]
        source_cluster_host_name = task_metadata['resource_json']['classic_cluster_ingress_hostname']
        source_cluster_id = task_metadata["resource_json"]["resource_id"]
        if task_metadata['resource_json'].get('target_resource_id'):
            kubernetes_cluster_resource_id = task_metadata['resource_json']['target_resource_id']
            target_cluster_host_name = task_metadata['resource_json']['target_cluster_hostname']
        else:
            create_cluster_task = workflow_task.root.associated_tasks.filter(
                WorkflowTask.task_type == WorkflowTask.TYPE_CREATE).first()
            create_task_metadata = create_cluster_task.task_metadata
            target_cluster_host_name = create_task_metadata['resource_json']['target_cluster_hostname']
            source_cluster = db_session.query(IBMKubernetesCluster).filter_by(
                id=create_cluster_task.resource_id).first()
            if not source_cluster:
                workflow_task.status = WorkflowTask.STATUS_FAILED
                workflow_task.message = f"IBM Cluster with ID '{create_cluster_task.resource_id}' not found"
                db_session.commit()
                LOGGER.error(workflow_task.message)
                return
            kubernetes_cluster_resource_id = source_cluster.resource_id

        cos_access_keys = db_session.query(IBMServiceCredentialKey).filter_by(id=cos_access_keys_id).first()
        if not cos_access_keys:
            workflow_task.status = WorkflowTask.STATUS_FAILED
            workflow_task.message = f"IBM COS Access Keys '{cos_access_keys_id}' not found"
            db_session.commit()
            LOGGER.error(workflow_task.message)
            return

        if cos_access_keys.role != IBMServiceCredentialKey.ROLE_MANAGER:
            workflow_task.status = WorkflowTask.STATUS_FAILED
            workflow_task.message = f"IBM COS Access Keys '{cos_access_keys_id}' don't have manager permissions"
            db_session.commit()
            LOGGER.error(workflow_task.message)
            return

        bucket = db_session.query(IBMCOSBucket).filter_by(id=cos_bucket_id).first()
        if not bucket:
            workflow_task.status = WorkflowTask.STATUS_FAILED
            workflow_task.message = f"IBM COS bucket '{cos_bucket_id}' not found"
            db_session.commit()
            LOGGER.error(workflow_task.message)
            return

        bucket_name = bucket.name
        bucket_region = bucket.location_constraint
        restore_name = "restore" + str(datetime.utcnow().strftime("-%m-%d-%Y%H-%M-%S"))
        backup_pvcs = []
        if task_metadata.get("backup_id"):
            backup_id = task_metadata["backup_id"]
            backup = db_session.query(DisasterRecoveryBackup).filter_by(id=backup_id).first()
            if backup:
                backup_pvcs = backup.backup_metadata

    client = KubernetesClient(cloud_id)
    try:
        source_cluster_admin_config = client.get_kubernetes_cluster_kube_config(cluster=source_cluster_id, admin=True)
        source_kube_config = Kubernetes(configuration_json=source_cluster_admin_config)
        pvcs = source_kube_config.client.CoreV1Api().list_persistent_volume_claim_for_all_namespaces(watch=False)
    except (ApiException, ConnectTimeoutError, MaxRetryError, NewConnectionError) as ex:
        with get_db_session() as db_session:
            workflow_task = db_session.query(WorkflowTask).filter_by(id=workflow_task_id).first()
            if not workflow_task:
                return

            workflow_task.status = WorkflowTask.STATUS_FAILED
            workflow_task.message = f"Failed to get Source Cluster Kube Config. Reason: {str(ex)}"
            db_session.commit()
            return

    try:
        target_cluster_admin_config = client.get_kubernetes_cluster_kube_config(
            cluster=kubernetes_cluster_resource_id, admin=True)

    except (ApiException, ConnectTimeoutError, MaxRetryError, NewConnectionError) as ex:
        with get_db_session() as db_session:
            workflow_task = db_session.query(WorkflowTask).filter_by(id=workflow_task_id).first()
            if not workflow_task:
                return

            workflow_task.status = WorkflowTask.STATUS_FAILED
            workflow_task.message = f"Failed to get Migrated Cluster Kube Config. Reason: {str(ex)}"
            db_session.commit()
            return

    pvcs_list = list()
    restore_pvcs_list = list()
    if pvcs.items:
        for pvc in pvcs.items:
            if pvc.spec.storage_class_name in ["manual", "standard"] \
                    or pvc.metadata.annotations.get('volume.beta.kubernetes.io/storage-provisioner') == \
                    "ibm.io/ibmc-file" or pvc.spec.storage_class_name in CLASSIC_FILE_STORAGE_CLASSES \
                    or "ibmc-file" in pvc.spec.storage_class_name:
                continue

            else:
                PVC_PAYLOAD['name'] = pvc.metadata.name
                PVC_PAYLOAD['namespace'] = pvc.metadata.namespace
                PVC_PAYLOAD['size'] = pvc.spec.resources.requests['storage']
                PVC_PAYLOAD['provisioner'] = "ibm.io/ibmc-block"

                if pvc.spec.storage_class_name in CLASSIC_BLOCK_STORAGE_CLASSES:
                    PVC_PAYLOAD['storageClassName'] = "ibmc-vpc-block-10iops-tier"
                else:
                    PVC_PAYLOAD['storageClassName'] = "ibmc-vpc-block-custom"

                if backup_pvcs:
                    if pvc.metadata.namespace in backup_pvcs:
                        restore_pvcs_list.append(PVC_PAYLOAD)
                else:
                    pvcs_list.append(PVC_PAYLOAD)

    if restore_pvcs_list:
        pvcs_list = restore_pvcs_list
    hmac = {
        "access_key": cos_access_keys.access_key_id,
        "secret_key": cos_access_keys.secret_access_key
    }
    payload = construct_payload(
        cluster_name=cluster_name, hmac_keys=hmac, kube_config=target_cluster_admin_config,
        region=bucket_region, operation_type=RESTORE, bucket_name=bucket_name, restore_name=restore_name,
        backup_name=backup_name, persistent_volume_claims=pvcs_list, source_cloud="IBM",
        source_cluster_host_name=source_cluster_host_name, target_cluster_host_name=target_cluster_host_name
    )

    try:
        response = requests.post(url=VeleroConfig.VELERO_URL, headers=VeleroConfig.VELERO_HEADERS, json=payload)
        response_json = response.json()
    except (ConnectionError, ReadTimeout, RequestException, json.decoder.JSONDecodeError) as ex:
        with get_db_session() as db_session:
            workflow_task = db_session.query(WorkflowTask).filter_by(id=workflow_task_id).first()
            if not workflow_task:
                return

            workflow_task.status = WorkflowTask.STATUS_FAILED
            workflow_task.message = ex
            db_session.commit()
            LOGGER.fail(workflow_task.message)
            return

    if response.status_code != 202:
        with get_db_session() as db_session:
            workflow_task = db_session.query(WorkflowTask).filter_by(id=workflow_task_id).first()
            if not workflow_task:
                return

            workflow_task.message = RESTORE_FAILURE_ERROR_MSG
            workflow_task.status = WorkflowTask.STATUS_FAILED
            LOGGER.fail(workflow_task.message)
            db_session.commit()
            return

    with get_db_session() as db_session:
        workflow_task = db_session.query(WorkflowTask).filter_by(id=workflow_task_id).first()
        if not workflow_task:
            return

        task_metadata['velero_task_id'] = response_json["task_id"]
        workflow_task.task_metadata = task_metadata
        workflow_task.status = WorkflowTask.STATUS_RUNNING_WAIT
        db_session.commit()
        LOGGER.info("Kubernetes cluster restore initiated on cluster {}".format(cluster_name))


def iks_gen2_to_iks_gen2_restoration(workflow_task_id):
    with get_db_session() as db_session:
        workflow_task = db_session.query(WorkflowTask).filter_by(id=workflow_task_id).first()
        if not workflow_task:
            return

        workflow_task.status = WorkflowTask.STATUS_RUNNING
        db_session.commit()

        task_metadata = deepcopy(workflow_task.task_metadata)

        backup = db_session.query(DisasterRecoveryBackup).filter_by(id=task_metadata["backup_id"]).first()
        if not backup:
            workflow_task.status = WorkflowTask.STATUS_FAILED
            workflow_task.message = f"Backup '{task_metadata['backup_id']}' not found"
            db_session.commit()
            LOGGER.error(workflow_task.message)
            return

        backup_name = task_metadata["backup_name"]
        cluster_name = task_metadata['resource_json']['name']
        cluster_rid = task_metadata['resource_json']['resource_id']
        cloud_id = task_metadata["ibm_cloud"]["id"]
        cos_bucket_id = task_metadata["cos_bucket_id"]
        cos_access_keys_id = task_metadata["cos_access_keys_id"]

        cos_access_keys = db_session.query(IBMServiceCredentialKey).filter_by(id=cos_access_keys_id).first()
        if not cos_access_keys:
            workflow_task.status = WorkflowTask.STATUS_FAILED
            workflow_task.message = f"IBM COS Access Keys '{cos_access_keys_id}' not found"
            db_session.commit()
            LOGGER.error(workflow_task.message)
            return

        if cos_access_keys.role != IBMServiceCredentialKey.ROLE_MANAGER:
            workflow_task.status = WorkflowTask.STATUS_FAILED
            workflow_task.message = f"IBM COS Access Keys '{cos_access_keys_id}' don't have manager permissions"
            db_session.commit()
            LOGGER.error(workflow_task.message)
            return

        bucket = db_session.query(IBMCOSBucket).filter_by(id=cos_bucket_id).first()
        if not bucket:
            workflow_task.status = WorkflowTask.STATUS_FAILED
            workflow_task.message = f"IBM COS bucket '{cos_bucket_id}' not found"
            db_session.commit()
            LOGGER.error(workflow_task.message)
            return

        bucket_name = bucket.name
        bucket_region = bucket.location_constraint
        restore_name = "restores" + str(datetime.utcnow().strftime("-%m-%d-%Y%H-%M-%S"))

    client = KubernetesClient(cloud_id)
    try:
        target_cluster_admin_config = client.get_kubernetes_cluster_kube_config(cluster=cluster_rid, admin=True)
    except (ApiException, ConnectTimeoutError, MaxRetryError, NewConnectionError) as ex:
        with get_db_session() as db_session:
            workflow_task = db_session.query(WorkflowTask).filter_by(id=workflow_task_id).first()
            if not workflow_task:
                return

            workflow_task.status = WorkflowTask.STATUS_FAILED
            workflow_task.message = f"Failed to get Migrated Cluster Kube Config. Reason: {str(ex)}"
            db_session.commit()
            LOGGER.fail(workflow_task.message)
            return

    pvcs_list = []
    if task_metadata.get("backup_id"):
        backup_id = task_metadata["backup_id"]
        backup = db_session.query(DisasterRecoveryBackup).filter_by(id=backup_id).first()
        if backup:
            if not backup.backup_metadata.get("resource_type") == "ONPREM":
                backup_workloads = backup.backup_metadata.get("workloads")
                for workload in backup_workloads:
                    pvcs_list.append(workload['pvc'])

            resource_json = backup.backup_metadata.get("resource_json")
            for workload in resource_json.get("workloads"):
                for pvc in workload["pvc"]:
                    PVC_PAYLOAD["name"] = pvc["name"]
                    PVC_PAYLOAD["size"] = pvc["size"]
                    PVC_PAYLOAD["namespace"] = pvc["namespace"]
                    PVC_PAYLOAD['provisioner'] = pvc["type"]
                    PVC_PAYLOAD["storageClassName"] = pvc["storage_class_name"]
                    pvcs_list.append(PVC_PAYLOAD)

    hmac = {
        "access_key": cos_access_keys.access_key_id,
        "secret_key": cos_access_keys.secret_access_key
    }
    payload = construct_payload(
        cluster_name=cluster_name, hmac_keys=hmac, kube_config=target_cluster_admin_config,
        region=bucket_region, operation_type=RESTORE, bucket_name=bucket_name, restore_name=restore_name,
        backup_name=backup_name, persistent_volume_claims=pvcs_list, source_cloud="IBM"
    )
    try:
        response = requests.post(url=VeleroConfig.VELERO_URL, headers=VeleroConfig.VELERO_HEADERS, json=payload)
        response_json = response.json()
    except (ConnectionError, ReadTimeout, RequestException, json.decoder.JSONDecodeError) as ex:
        with get_db_session() as db_session:
            workflow_task = db_session.query(WorkflowTask).filter_by(id=workflow_task_id).first()
            if not workflow_task:
                return

            workflow_task.status = WorkflowTask.STATUS_FAILED
            workflow_task.message = ex
            db_session.commit()
            LOGGER.fail(workflow_task.message)
            return

    if response.status_code != 202:
        with get_db_session() as db_session:
            workflow_task = db_session.query(WorkflowTask).filter_by(id=workflow_task_id).first()
            if not workflow_task:
                return

            workflow_task.message = RESTORE_FAILURE_ERROR_MSG
            workflow_task.status = WorkflowTask.STATUS_FAILED
            LOGGER.fail(workflow_task.message)
            db_session.commit()
            return

    with get_db_session() as db_session:
        workflow_task = db_session.query(WorkflowTask).filter_by(id=workflow_task_id).first()
        if not workflow_task:
            return

        task_metadata['velero_task_id'] = response_json["task_id"]
        workflow_task.task_metadata = task_metadata
        workflow_task.status = WorkflowTask.STATUS_RUNNING_WAIT
        db_session.commit()
        LOGGER.info("Kubernetes cluster restore initiated on cluster {}".format(cluster_name))


def aws_cloud_to_ibm_restoration(workflow_task_id):
    with get_db_session() as db_session:
        workflow_task = db_session.query(WorkflowTask).filter_by(id=workflow_task_id).first()
        if not workflow_task:
            return

        workflow_task.status = WorkflowTask.STATUS_RUNNING
        db_session.commit()

        resource_data = deepcopy(workflow_task.task_metadata["resource_data"])
        cloud_id = resource_data["ibm_cloud"]["id"]
        ibm_cloud = db_session.query(IBMCloud).filter_by(id=cloud_id).first()
        if not ibm_cloud:
            workflow_task.status = WorkflowTask.STATUS_FAILED
            workflow_task.message = f"IBM Cloud with ID '{cloud_id}' not found"
            db_session.commit()
            LOGGER.error(workflow_task.message)
            return

        user_id = ibm_cloud.user_id
        url = urljoin(
            WorkerConfig.VPCPLUS_LINK, GET_AWS_CLOUD_CREDENTIAL_URL_TEMPLATE.format(
                user_id=user_id, cloud_id=resource_data['source']['cloud']['id'])
        )
    try:
        response = requests.request("GET", url, headers=AWS_HEADER, timeout=30)
        response_json = response.json()
    except (ConnectionError, ReadTimeout, RequestException, json.decoder.JSONDecodeError) as ex:
        with get_db_session() as db_session:
            workflow_task = db_session.query(WorkflowTask).filter_by(id=workflow_task_id).first()
            if not workflow_task:
                return

            workflow_task.status = WorkflowTask.STATUS_FAILED
            workflow_task.message = ex
            db_session.commit()
            LOGGER.fail(workflow_task.message)
        return

    resource_data["hmac"] = response_json
    url = urljoin(
        WorkerConfig.VPCPLUS_LINK, GET_AWS_BACKUP_URL_TEMPLATE.format(
            user_id=user_id, cloud_id=resource_data['source']['cloud']['id'],
            backup_id=resource_data["source"]["backup"]["id"]
        )
    )
    try:
        response = requests.request("GET", url, headers=AWS_HEADER, timeout=30)
        response_json = response.json()
    except (ConnectionError, ReadTimeout, RequestException, json.decoder.JSONDecodeError) as ex:
        with get_db_session() as db_session:
            workflow_task = db_session.query(WorkflowTask).filter_by(id=workflow_task_id).first()
            if not workflow_task:
                return

            workflow_task.status = WorkflowTask.STATUS_FAILED
            workflow_task.message = ex
            db_session.commit()
            LOGGER.fail(workflow_task.message)
        return

    with get_db_session() as db_session:
        workflow_task = db_session.query(WorkflowTask).filter_by(id=workflow_task_id).first()
        if not workflow_task:
            return

        previous_resources = load_previous_associated_resources(task=workflow_task, session=db_session)
        resource = previous_resources.get(resource_data["cluster"]["id"]) or db_session.query(
            IBMKubernetesCluster).filter_by(id=resource_data["cluster"]["id"],
                                            cloud_id=cloud_id).first() or db_session.query(
            IBMSatelliteCluster).filter_by(id=resource_data["cluster"]["id"],
                                           cloud_id=cloud_id).first()
        if not resource:
            workflow_task.status = WorkflowTask.STATUS_FAILED
            workflow_task.message = f"Cluster not found with id {resource_data['cluster']['id']}"
            LOGGER.error(workflow_task.message)
            return

        restore_name = "restore" + str(datetime.utcnow().strftime("-%m-%d-%Y%H-%M-%S"))
        if isinstance(resource, IBMSatelliteCluster):
            agent_id = resource.agent_id
            target_cluster_admin_config = resource.kube_config
            payload = construct_payload(
                cluster_name=resource.name, hmac_keys=resource_data["hmac"], kube_config=target_cluster_admin_config,
                region=response_json["cluster_info"]["bucket_region"], operation_type=RESTORE,
                bucket_name=response_json["cluster_info"]["cluster_backup_bucket_name"],
                restore_name=restore_name, backup_name=response_json["backup_name"],
                source_cloud=resource_data['source']['cloud']['cloud_type'],
                persistent_volume_claims=response_json["cluster_info"].get("cluster_persistent_volumes"),
                cluster_type=resource.cluster_type, satellite=True, agent_id=agent_id, user_id=user_id,
                auth_type="CERTS"
            )

        else:
            client = KubernetesClient(cloud_id)
            try:
                target_cluster_admin_config = client.get_kubernetes_cluster_kube_config(cluster=resource.resource_id)
            except (ApiException, ConnectTimeoutError, MaxRetryError, NewConnectionError) as ex:
                with get_db_session() as db_session:
                    workflow_task = db_session.query(WorkflowTask).filter_by(id=workflow_task_id).first()
                    if not workflow_task:
                        return

                    workflow_task.status = WorkflowTask.STATUS_FAILED
                    workflow_task.message = f"Failed to get Migrated Cluster Kube Config. Reason: {str(ex)}"
                    db_session.commit()
                    LOGGER.fail(workflow_task.message)
                    return

            payload = construct_payload(
                cluster_name=resource.name, hmac_keys=resource_data["hmac"], kube_config=target_cluster_admin_config,
                region=response_json["cluster_info"]["bucket_region"], operation_type=RESTORE,
                bucket_name=response_json["cluster_info"]["cluster_backup_bucket_name"],
                restore_name=restore_name, backup_name=response_json["backup_name"],
                source_cloud=resource_data['source']['cloud']['cloud_type'],
                persistent_volume_claims=response_json["cluster_info"].get("cluster_persistent_volumes"),
                cluster_type=resource.cluster_type
            )

    try:
        response = requests.request("POST", VELERO_SERVER_URL, headers=VELERO_HEADERS, json=payload)
        response_json = response.json()
    except (ConnectionError, ReadTimeout, RequestException, json.decoder.JSONDecodeError) as ex:
        with get_db_session() as db_session:
            workflow_task = db_session.query(WorkflowTask).filter_by(id=workflow_task_id).first()
            if not workflow_task:
                return

            workflow_task.status = WorkflowTask.STATUS_FAILED
            workflow_task.message = ex
            db_session.commit()
            LOGGER.fail(workflow_task.message)
        return

    if response.status_code != 202:
        with get_db_session() as db_session:
            workflow_task = db_session.query(WorkflowTask).filter_by(id=workflow_task_id).first()
            if not workflow_task:
                return

            workflow_task.message = RESTORE_FAILURE_ERROR_MSG
            workflow_task.status = WorkflowTask.STATUS_FAILED
            LOGGER.fail(workflow_task.message)
            db_session.commit()
            return

    with get_db_session() as db_session:
        workflow_task = db_session.query(WorkflowTask).filter_by(id=workflow_task_id).first()
        if not workflow_task:
            return

        task_metadata = deepcopy(workflow_task.task_metadata)
        task_metadata['velero_task_id'] = response_json["task_id"]
        task_metadata["cluster"] = {
            "name": resource.name,
            "id": resource.id
        }
        workflow_task.task_metadata = task_metadata
        workflow_task.status = WorkflowTask.STATUS_RUNNING_WAIT
        db_session.commit()
        LOGGER.info("Kubernetes cluster restore initiated on cluster {}".format(task_metadata["cluster"]["id"]))


@celery.task(name="create_kubernetes_cluster_backup", queue='disaster_recovery_queue', base=IBMWorkflowTasksBase)
def create_kubernetes_cluster_backup(workflow_task_id):
    """
    Create Backup of a Kubernetes Cluster
    """
    with get_db_session() as db_session:
        workflow_task = db_session.query(WorkflowTask).filter_by(id=workflow_task_id).first()
        if not workflow_task:
            return

        workflow_task.status = WorkflowTask.STATUS_RUNNING
        db_session.commit()

        task_metadata = deepcopy(workflow_task.task_metadata)
        cloud_id = task_metadata["ibm_cloud"]["id"]
        cos_bucket_id = task_metadata["cos_bucket_id"]
        cloud_object_storage_id = task_metadata["cloud_object_storage_id"]
        cos_access_keys_id = task_metadata["cos_access_keys_id"]
        backup_name = task_metadata["backup_name"]
        source_cluster_name = \
            task_metadata['resource_json'].get('classic_cluster_name') or task_metadata['resource_json']['name']
        source_cluster_id = task_metadata['resource_json']['resource_id']
        backup_namespaces = task_metadata.get('namespaces')

        cloud_object_storage_key = db_session.query(IBMCloudObjectStorage).filter_by(id=cloud_object_storage_id).first()
        if not cloud_object_storage_key:
            workflow_task.status = WorkflowTask.STATUS_FAILED
            workflow_task.message = f"IBM COS Keys '{cloud_object_storage_id}' not found"
            db_session.commit()
            LOGGER.error(workflow_task.message)
            return

        cos_access_keys = db_session.query(IBMServiceCredentialKey).filter_by(id=cos_access_keys_id).first()
        if not cos_access_keys:
            workflow_task.status = WorkflowTask.STATUS_FAILED
            workflow_task.message = f"IBM COS Access Keys '{cos_access_keys_id}' not found"
            db_session.commit()
            LOGGER.error(workflow_task.message)
            return

        if cos_access_keys.role != IBMServiceCredentialKey.ROLE_MANAGER:
            workflow_task.status = WorkflowTask.STATUS_FAILED
            workflow_task.message = f"IBM COS Access Keys '{cos_access_keys_id}' don't have manager permissions"
            db_session.commit()
            LOGGER.error(workflow_task.message)
            return

        bucket = db_session.query(IBMCOSBucket).filter_by(id=cos_bucket_id).first()
        if not bucket:
            workflow_task.status = WorkflowTask.STATUS_FAILED
            workflow_task.message = f"IBM COS bucket '{cos_bucket_id}' not found"
            db_session.commit()
            LOGGER.error(workflow_task.message)
            return

        bucket_name = bucket.name
        bucket_region = bucket.location_constraint

    client = KubernetesClient(cloud_id)
    try:
        source_cluster_admin_config = client.get_kubernetes_cluster_kube_config(cluster=source_cluster_id, admin=True)
        kube_config = Kubernetes(configuration_json=source_cluster_admin_config)

        namespaces = list()
        backup_list = list()
        for namespace in kube_config.client.CoreV1Api().list_namespace().items:
            if namespace.metadata.name in NAMESPACES:
                continue

            if backup_namespaces and namespace.metadata.name in backup_namespaces:
                backup_list.append(namespace.metadata.name)
            else:
                namespaces.append(namespace.metadata.name)

    except (ApiException, ConnectTimeoutError, MaxRetryError, NewConnectionError) as ex:
        with get_db_session() as db_session:
            workflow_task = db_session.query(WorkflowTask).filter_by(id=workflow_task_id).first()
            if not workflow_task:
                return

            workflow_task.status = WorkflowTask.STATUS_FAILED
            workflow_task.message = f"Failed. Reason: {str(ex)}"
            db_session.commit()
            LOGGER.fail(workflow_task.message)
            return

    if backup_list:
        namespaces = backup_list
    hmac = {
        "access_key": cos_access_keys.access_key_id,
        "secret_key": cos_access_keys.secret_access_key
    }

    payload = construct_payload(
        cluster_name=source_cluster_name, hmac_keys=hmac,
        kube_config=source_cluster_admin_config, region=bucket_region, namespaces=namespaces, operation_type=BACKUP,
        bucket_name=bucket_name, backup_name=backup_name, source_cloud="IBM"
    )

    try:
        response = requests.post(url=VeleroConfig.VELERO_URL, headers=VeleroConfig.VELERO_HEADERS, json=payload)
        response_json = response.json()
    except (ConnectionError, ReadTimeout, RequestException, json.decoder.JSONDecodeError) as ex:
        with get_db_session() as db_session:
            workflow_task = db_session.query(WorkflowTask).filter_by(id=workflow_task_id).first()
            if not workflow_task:
                return

            workflow_task.status = WorkflowTask.STATUS_FAILED
            workflow_task.message = f"Failed to get ok response from Velero. Reason: {str(ex)}"
            db_session.commit()
            LOGGER.fail(workflow_task.message)
        return

    if response.status_code != 202:
        with get_db_session() as db_session:
            workflow_task = db_session.query(WorkflowTask).filter_by(id=workflow_task_id).first()
            if not workflow_task:
                return

            workflow_task.message = BACKUP_FAILURE_ERROR_MSG + "\n" + response.reason
            workflow_task.status = WorkflowTask.STATUS_FAILED
            LOGGER.fail(workflow_task.message)
            db_session.commit()
            return

    with get_db_session() as db_session:
        workflow_task = db_session.query(WorkflowTask).filter_by(id=workflow_task_id).first()
        if not workflow_task:
            return

        ibm_id = task_metadata['resource_json']['resource_id']
        task_metadata['velero_task_id'] = response_json["task_id"]
        workflow_task.task_metadata = task_metadata
        workflow_task.status = WorkflowTask.STATUS_RUNNING_WAIT
        db_session.commit()
        LOGGER.success(f"Kubernetes cluster backup initiated successfully for cluster having IBMid '{ibm_id}'")


@celery.task(name="create_wait_kubernetes_cluster_backup", queue='disaster_recovery_queue', base=IBMWorkflowTasksBase)
def create_wait_kubernetes_cluster_backup(workflow_task_id):
    with get_db_session() as db_session:
        workflow_task = db_session.query(WorkflowTask).filter_by(id=workflow_task_id).first()
        if not workflow_task:
            return

        workflow_task.status = WorkflowTask.STATUS_RUNNING
        db_session.commit()

        task_metadata = deepcopy(workflow_task.task_metadata)

    url = VeleroConfig.VELERO_URL + "/" + task_metadata['velero_task_id']
    try:
        response = requests.get(url=url, headers=VeleroConfig.VELERO_HEADERS)
        response_json = response.json()
    except (ConnectionError, ReadTimeout, RequestException, json.decoder.JSONDecodeError) as ex:
        with get_db_session() as db_session:
            workflow_task = db_session.query(WorkflowTask).filter_by(id=workflow_task_id).first()
            if not workflow_task:
                return

            workflow_task.status = WorkflowTask.STATUS_FAILED
            workflow_task.message = ex
            db_session.commit()
            LOGGER.fail(workflow_task.message)
            return

    with get_db_session() as db_session:
        workflow_task = db_session.query(WorkflowTask).filter_by(id=workflow_task_id).first()
        if not workflow_task:
            return

        if response.status_code == 404:
            workflow_task.message = f"Task with id '{workflow_task.id}' not Found"
            workflow_task.status = WorkflowTask.STATUS_FAILED
            db_session.commit()
            LOGGER.error(workflow_task.message)
            return
        elif response.status_code != 200:
            workflow_task.message = BACKUP_FAILURE_ERROR_MSG
            workflow_task.status = WorkflowTask.STATUS_FAILED
            db_session.commit()
            LOGGER.fail(workflow_task.message)
            return

    with get_db_session() as db_session:
        workflow_task = db_session.query(WorkflowTask).filter_by(id=workflow_task_id).first()
        if not workflow_task:
            return

        if response_json["status"] == WorkflowRoot.STATUS_C_SUCCESSFULLY:
            workflow_task.message = "Kubernetes cluster backup created successfully"
            workflow_task.status = WorkflowTask.STATUS_SUCCESSFUL
            db_session.commit()
            LOGGER.success(workflow_task.message)
            return

        elif response_json['status'] == WorkflowRoot.STATUS_C_W_FAILURE:
            for task in response_json.get("associated_tasks", []):
                if not task["status"] == WorkflowTask.STATUS_FAILED:
                    continue

                workflow_task.message = task["message"]
                workflow_task.status = WorkflowTask.STATUS_FAILED
                db_session.commit()
                LOGGER.fail(workflow_task.message)
                return

        workflow_task.status = WorkflowTask.STATUS_RUNNING_WAIT
        db_session.commit()
        ibm_id = task_metadata['resource_json']['resource_id']
        LOGGER.info(f"Kubernetes cluster backup in progress for cluster having IBMid '{ibm_id}'")


@celery.task(name="create_kubernetes_cluster", base=IBMWorkflowTasksBase)
def create_kubernetes_cluster(workflow_task_id):
    """
    Create an IBM Kubernetes Cluster on IBM Cloud
    :param workflow_task_id:
    :return:
    """

    with get_db_session() as db_session:
        workflow_task = db_session.query(WorkflowTask).filter_by(id=workflow_task_id).first()
        if not workflow_task:
            return

        task_metadata = deepcopy(workflow_task.task_metadata)
        cloud_id = task_metadata["ibm_cloud"]["id"]
        cloud_object_storage_id = task_metadata.get('cloud_object_storage_id')
        resource_json = deepcopy(task_metadata['resource_json'])

        previous_resources = load_previous_associated_resources(task=workflow_task, session=db_session)
        update_id_or_name_references(
            cloud_id=cloud_id, resource_json=task_metadata, resource_schema=IBMKubernetesClusterInSchema,
            db_session=db_session, previous_resources=previous_resources
        )

        update_id_or_name_references(
            cloud_id=cloud_id, resource_json=resource_json, resource_schema=IBMKubernetesClusterResourceSchema,
            db_session=db_session, previous_resources=previous_resources
        )

        vpc_id = resource_json["vpc"]["id"]
        resource_group_id = resource_json["resource_group"]["id"]

        data = IBMKubernetesCluster.to_json_body(resource_json, db_session, previous_resources)
        data['workerPool']['vpcID'] = vpc_id
        data['resource_group'] = resource_group_id

        if task_metadata['resource_json']['cluster_type'] == IBMKubernetesCluster.OPENSHIFT_CLUSTER:
            cos = db_session.query(IBMCloudObjectStorage).filter_by(id=cloud_object_storage_id,
                                                                    cloud_id=task_metadata['ibm_cloud']['id']).first()
            if not cos:
                workflow_task.status = WorkflowTask.STATUS_FAILED
                workflow_task.message = f"IBM Cloud Object Storage '{cloud_object_storage_id}' not found"
                db_session.commit()
                LOGGER.error(workflow_task.message)
                return

            data['cosInstanceCRN'] = cos.crn

    client = KubernetesClient(task_metadata['ibm_cloud']['id'])
    try:
        cluster_json = client.create_kubernetes_cluster(data)
        if len(resource_json["worker_pools"]) > 1:
            for workerpool in resource_json["worker_pools"]:
                if workerpool['name'] == data['workerPool']['name']:
                    continue
                with get_db_session() as db_session:
                    workflow_task = db_session.query(WorkflowTask).filter_by(id=workflow_task_id).first()
                    if not workflow_task:
                        return

                    previous_resources = load_previous_associated_resources(task=workflow_task, session=db_session)
                    workerpool_data = IBMKubernetesClusterWorkerPool.to_json_body(
                        workerpool, db_session, previous_resources=previous_resources
                    )
                workerpool_data['cluster'] = cluster_json['clusterID']
                workerpool_data['vpcID'] = vpc_id
                client.create_kubernetes_cluster_worker_pool(workerpool_data)
    except (IBMAuthError, IBMConnectError, IBMExecuteError, IBMInvalidRequestError) as ex:
        with get_db_session() as db_session:
            workflow_task = db_session.query(WorkflowTask).filter_by(id=workflow_task_id).first()
            if not workflow_task:
                return

            workflow_task.status = WorkflowTask.STATUS_FAILED
            workflow_task.message = f"{resource_json['cluster_type']} Cluster {resource_json['name']}" \
                                    f" Provisioning Failed for cloud {cloud_id}. Reason: {str(ex)}"
            db_session.commit()
            LOGGER.fail(workflow_task.message)
            return

    with get_db_session() as db_session:
        workflow_task = db_session.query(WorkflowTask).filter_by(id=workflow_task_id).first()
        if not workflow_task:
            return

        workflow_task.resource_id = cluster_json['clusterID']
        workflow_task.status = WorkflowTask.STATUS_RUNNING_WAIT
        db_session.commit()
        LOGGER.info(f"{resource_json['cluster_type']} Cluster {resource_json['name']} "
                    f"provisioning with id {cluster_json['clusterID']} for cloud id {cloud_id} on IBM Cloud")


@celery.task(name="create_wait_kubernetes_cluster", base=IBMWorkflowTasksBase)
def create_wait_kubernetes_cluster(workflow_task_id):
    """
    Create an IBM Kubernetes Cluster on IBM Cloud
    :param workflow_task_id:
    :return:
    """
    with get_db_session() as db_session:
        workflow_task = db_session.query(WorkflowTask).filter_by(id=workflow_task_id).first()
        if not workflow_task:
            return

        workflow_task.status = WorkflowTask.STATUS_RUNNING
        db_session.commit()
        task_metadata = deepcopy(workflow_task.task_metadata)
        cloud_id = task_metadata['ibm_cloud']['id']
        region_id = task_metadata['region']['id']
        resource_json = task_metadata['resource_json']
        cluster_resource_id = workflow_task.resource_id

    client = KubernetesClient(task_metadata['ibm_cloud']['id'])
    try:
        cluster_json = client.get_kubernetes_cluster_detail(resource_json["name"], show_resources=True)
    except (IBMAuthError, IBMConnectError, IBMExecuteError, IBMInvalidRequestError) as ex:
        with get_db_session() as db_session:
            workflow_task = db_session.query(WorkflowTask).filter_by(id=workflow_task_id).first()
            if not workflow_task:
                return

            workflow_task.status = WorkflowTask.STATUS_FAILED
            workflow_task.message = f"{resource_json['cluster_type']} Cluster {resource_json['name']} " \
                                    f" with id {workflow_task.resource_id}  for cloud id {cloud_id} " \
                                    f"Provisioning Failed. Reason: {str(ex)}"
            db_session.commit()
            LOGGER.fail(workflow_task.message)
            return

    if cluster_json['state'] == IBMKubernetesCluster.STATE_NORMAL and cluster_json['ingress']['hostname']:
        try:
            worker_pools = client.get_kubernetes_cluster_worker_pool(cluster=cluster_resource_id)
        except (IBMAuthError, IBMConnectError, IBMExecuteError, IBMInvalidRequestError) as ex:
            with get_db_session() as db_session:
                workflow_task = db_session.query(WorkflowTask).filter_by(id=workflow_task_id).first()
                if not workflow_task:
                    return

                workflow_task.status = WorkflowTask.STATUS_FAILED
                workflow_task.message = f"{resource_json['cluster_type']} Cluster {resource_json['name']} " \
                                        f"with id {workflow_task.resource_id}  for cloud id {cloud_id}" \
                                        f" WorkerPool Creation Failed." \
                                        f" Reason: {str(ex)}"
                db_session.commit()
                LOGGER.fail(workflow_task.message)
                return

        with get_db_session() as db_session:
            workflow_task = db_session.query(WorkflowTask).filter_by(id=workflow_task_id).first()
            if not workflow_task:
                return

            vpc = db_session.query(IBMVpcNetwork).filter_by(resource_id=cluster_json['vpcs'][0],
                                                            cloud_id=cloud_id).first()
            resource_group = db_session.query(IBMResourceGroup).filter_by(resource_id=cluster_json['resourceGroup'],
                                                                          cloud_id=cloud_id).first()

            cluster = IBMKubernetesCluster.from_ibm_json_body(cluster_json)
            cluster.cloud_id = cloud_id
            cluster.region_id = region_id
            cluster.vpc_id = vpc.id
            cluster.resource_group_id = resource_group.id
            workflow_task.resource_id = cluster.id
            for worker_pool in worker_pools:
                kubernetes_cluster_worker_pool = IBMKubernetesClusterWorkerPool.from_ibm_json_body(worker_pool)

                for worker_pool_zone in worker_pool['zones']:
                    kubernetes_cluster_worker_pool_zone = IBMKubernetesClusterWorkerPoolZone.from_ibm_json_body(
                        worker_pool_zone)

                    kubernetes_cluster_worker_pool.worker_zones.append(kubernetes_cluster_worker_pool_zone)
                cluster.worker_pools.append(kubernetes_cluster_worker_pool)

            task_metadata = deepcopy(workflow_task.task_metadata)
            task_metadata['resource_json']['target_cluster_hostname'] = cluster_json['ingress']['hostname']
            task_metadata['resource_json']['target_resource_id'] = cluster_json['id']
            workflow_task.task_metadata = task_metadata
            workflow_task.status = WorkflowTask.STATUS_SUCCESSFUL
            workflow_task.message = f"{resource_json['cluster_type']} Cluster {resource_json['name']}" \
                                    f" with id {workflow_task.resource_id}  for cloud id {cloud_id} " \
                                    f"provisioned successfully"

            db_session.add(cluster)
            db_session.commit()
            LOGGER.success(workflow_task.message)

            IBMResourceLog(
                resource_id=cluster.resource_id, region=cluster.region,
                status=IBMResourceLog.STATUS_ADDED, resource_type=IBMKubernetesCluster.__name__,
                data=cluster.to_json())
            db_session.commit()
    elif cluster_json['state'] == IBMKubernetesCluster.STATE_DEPLOY_FAILED:
        with get_db_session() as db_session:
            workflow_task = db_session.query(WorkflowTask).filter_by(id=workflow_task_id).first()
            if not workflow_task:
                return

            workflow_task.status = WorkflowTask.STATUS_FAILED
            workflow_task.message = f"{resource_json['cluster_type']} Cluster {resource_json['name']}" \
                                    f" with id {workflow_task.resource_id} for cloud id {cloud_id}" \
                                    f" provisioning failed on IBM Cloud"
            db_session.commit()
            LOGGER.fail(workflow_task.message)
    else:
        with get_db_session() as db_session:
            workflow_task = db_session.query(WorkflowTask).filter_by(id=workflow_task_id).first()
            if not workflow_task:
                return

            workflow_task.status = WorkflowTask.STATUS_RUNNING_WAIT
            LOGGER.info(f"{resource_json['cluster_type']} Cluster {resource_json['name']}"
                        f" with id {workflow_task.resource_id} for cloud id {cloud_id} provisioning")
            db_session.commit()


@celery.task(name="create_kubernetes_cluster_restore", queue='disaster_recovery_queue', base=IBMWorkflowTasksBase)
def create_kubernetes_cluster_restore(workflow_task_id):
    with get_db_session() as db_session:
        workflow_task = db_session.query(WorkflowTask).filter_by(id=workflow_task_id).first()
        if not workflow_task:
            return

        workflow_task.status = WorkflowTask.STATUS_RUNNING
        db_session.commit()
        task_metadata = deepcopy(workflow_task.task_metadata)

    if task_metadata.get('resource_data') and task_metadata['resource_data']['source']['cloud']['cloud_type'] == "AWS":
        aws_cloud_to_ibm_restoration(workflow_task_id=workflow_task_id)
    elif task_metadata.get("backup_provider") and task_metadata.get(
            "backup_provider") != "vpc-gen2":  # classic to gen2 migration
        classic_to_gen2_iks_migration(workflow_task_id=workflow_task_id)
    else:
        iks_gen2_to_iks_gen2_restoration(workflow_task_id=workflow_task_id)


@celery.task(name="create_wait_kubernetes_cluster_restore", queue='disaster_recovery_queue', base=IBMWorkflowTasksBase)
def create_wait_kubernetes_cluster_restore(workflow_task_id):
    with get_db_session() as db_session:
        workflow_task = db_session.query(WorkflowTask).filter_by(id=workflow_task_id).first()
        if not workflow_task:
            return

        workflow_task.status = WorkflowTask.STATUS_RUNNING
        db_session.commit()
        task_metadata = deepcopy(workflow_task.task_metadata)
        # Todo we need to handle this in a same manner either by resource_json key or by cluster key
        if task_metadata.get('resource_json', {}).get('name'):
            cluster_name = task_metadata['resource_json']['name']

        else:
            cluster_name = task_metadata["cluster"]["name"]

    url = VeleroConfig.VELERO_URL + "/" + task_metadata['velero_task_id']
    try:
        response = requests.get(url=url, headers=VeleroConfig.VELERO_HEADERS)
        response_json = response.json()
    except (ConnectionError, ReadTimeout, RequestException, json.decoder.JSONDecodeError) as ex:
        with get_db_session() as db_session:
            workflow_task = db_session.query(WorkflowTask).filter_by(id=workflow_task_id).first()
            if not workflow_task:
                return

            workflow_task.status = WorkflowTask.STATUS_FAILED
            workflow_task.message = ex
            db_session.commit()
            LOGGER.fail(workflow_task.message)
        return

    with get_db_session() as db_session:
        workflow_task = db_session.query(WorkflowTask).filter_by(id=workflow_task_id).first()
        if not workflow_task:
            return

        if response.status_code == 404:
            workflow_task.message = f"Task not Found with id '{task_metadata['velero_task_id']}'"
            workflow_task.status = WorkflowTask.STATUS_FAILED
            db_session.commit()
            LOGGER.fail(workflow_task.message)
            return

        elif response.status_code != 200:
            workflow_task.message = RESTORE_FAILURE_ERROR_MSG
            workflow_task.status = WorkflowTask.STATUS_FAILED
            db_session.commit()
            LOGGER.fail(workflow_task.message)
            return

    if response_json["status"] == WorkflowRoot.STATUS_C_SUCCESSFULLY:
        with get_db_session() as db_session:
            workflow_task = db_session.query(WorkflowTask).filter_by(id=workflow_task_id).first()
            if not workflow_task:
                return

            workflow_task.message = "Kubernetes cluster restore completed successfully"
            workflow_task.status = WorkflowTask.STATUS_SUCCESSFUL
            db_session.commit()
            LOGGER.success(workflow_task.message)
            return

    elif response_json['status'] == WorkflowRoot.STATUS_C_W_FAILURE:
        with get_db_session() as db_session:
            workflow_task = db_session.query(WorkflowTask).filter_by(id=workflow_task_id).first()
            if not workflow_task:
                return

            for task in response_json.get("associated_tasks", []):
                if not task["status"] == WorkflowTask.STATUS_FAILED:
                    continue

                workflow_task.message = task["message"]
                workflow_task.status = WorkflowTask.STATUS_FAILED
                db_session.commit()
                LOGGER.fail(workflow_task.message)
                return

    with get_db_session() as db_session:
        workflow_task = db_session.query(WorkflowTask).filter_by(id=workflow_task_id).first()
        if not workflow_task:
            return

        workflow_task.status = WorkflowTask.STATUS_RUNNING_WAIT
        db_session.commit()
        LOGGER.info("Kubernetes cluster {} restore in progress".format(cluster_name))


@celery.task(name="delete_kubernetes_cluster", base=IBMWorkflowTasksBase)
def delete_kubernetes_cluster(workflow_task_id):
    """
    Delete a Cluster on IBM cloud
    """
    with get_db_session() as db_session:
        workflow_task = db_session.query(WorkflowTask).filter_by(id=workflow_task_id).first()
        if not workflow_task:
            return

        workflow_task.status = WorkflowTask.STATUS_RUNNING
        db_session.commit()

        kubernetes_cluster = db_session.query(IBMKubernetesCluster).filter_by(id=workflow_task.resource_id).first()
        if not kubernetes_cluster:
            workflow_task.status = WorkflowTask.STATUS_FAILED
            workflow_task.message = f"IBM Kubernetes Cluster {workflow_task.resource_id} doesn't exist in DB."
            db_session.commit()
            LOGGER.error(workflow_task.message)
            return

        cluster_name = kubernetes_cluster.name
        ibm_cluster_id = kubernetes_cluster.resource_id
        cloud_id = kubernetes_cluster.cloud_id

    client = KubernetesClient(cloud_id=cloud_id)
    try:
        client.delete_kubernetes_cluster(cluster=ibm_cluster_id, delete_resources=True)
    except (IBMAuthError, IBMConnectError, IBMInvalidRequestError) as ex:
        with get_db_session() as db_session:
            workflow_task = db_session.query(WorkflowTask).filter_by(id=workflow_task_id).first()
            if not workflow_task:
                return

            workflow_task.status = WorkflowTask.STATUS_FAILED
            workflow_task.message = f"Cluster Deletion Failed. Reason: {str(ex)}"
            db_session.commit()
            LOGGER.fail(workflow_task.message)
            return

    except IBMExecuteError as ex:
        with get_db_session() as db_session:
            workflow_task: WorkflowTask = db_session.query(WorkflowTask).filter_by(id=workflow_task_id).first()
            if not workflow_task:
                return

            if ex.status_code == 404:
                cluster: IBMKubernetesCluster = db_session.query(IBMKubernetesCluster).filter_by(
                    id=workflow_task.resource_id
                ).first()

                if cluster:
                    IBMResourceLog(
                        resource_id=cluster.resource_id, region=cluster.region,
                        status=IBMResourceLog.STATUS_DELETED, resource_type=IBMKubernetesCluster.__name__,
                        data=cluster.to_json())

                    db_session.delete(cluster)
                    workflow_task.status = WorkflowTask.STATUS_SUCCESSFUL
                    db_session.commit()
                    LOGGER.success(f"IBM Cluster {cluster_name} for cloud {cloud_id} removed from vpc+.")
                    return
            else:
                workflow_task.status = WorkflowTask.STATUS_FAILED
                workflow_task.message = str(ex)
                db_session.commit()
                LOGGER.fail(workflow_task.message)
                return

    with get_db_session() as db_session:
        workflow_task = db_session.query(WorkflowTask).filter_by(id=workflow_task_id).first()
        if not workflow_task:
            return

        workflow_task.status = WorkflowTask.STATUS_RUNNING_WAIT
        db_session.commit()
        LOGGER.info(
            f"IBM Kubernetes Cluster {workflow_task.resource_id} for Cloud : {cloud_id} deletion process started")


@celery.task(name="delete_wait_kubernetes_cluster", base=IBMWorkflowTasksBase)
def delete_wait_kubernetes_cluster(workflow_task_id):
    """
    Wait for IBM Cluster to delete on IBM cloud
    """
    with get_db_session() as db_session:
        workflow_task = db_session.query(WorkflowTask).filter_by(id=workflow_task_id).first()
        if not workflow_task:
            return

        workflow_task.status = WorkflowTask.STATUS_RUNNING
        db_session.commit()

        kubernetes_cluster: IBMKubernetesCluster = db_session.query(IBMKubernetesCluster).filter_by(
            id=workflow_task.resource_id
        ).first()

        if not kubernetes_cluster:
            workflow_task.status = WorkflowTask.STATUS_SUCCESSFUL
            workflow_task.message = f"IBM Kubernetes Cluster {workflow_task.resource_id} deleted successfully."
            db_session.commit()
            LOGGER.success(workflow_task.message)
            return

        cluster_name = kubernetes_cluster.name
        cluster_status = kubernetes_cluster.status
        ibm_cluster_id = kubernetes_cluster.resource_id
        cloud_id = kubernetes_cluster.cloud_id

    client = KubernetesClient(cloud_id=cloud_id)
    try:
        cluster_json = client.get_kubernetes_cluster_detail(cluster=ibm_cluster_id, show_resources=True)
    except (IBMAuthError, IBMConnectError, IBMInvalidRequestError) as ex:
        with get_db_session() as db_session:
            workflow_task: WorkflowTask = db_session.query(WorkflowTask).filter_by(id=workflow_task_id).first()
            if not workflow_task:
                return

            workflow_task.status = WorkflowTask.STATUS_FAILED
            workflow_task.message = f"Deletion Failed. Reason: {str(ex)}"
            db_session.commit()
            LOGGER.fail(workflow_task.message)
            return

    except IBMExecuteError as ex:
        with get_db_session() as db_session:
            workflow_task: WorkflowTask = db_session.query(WorkflowTask).filter_by(id=workflow_task_id).first()
            if not workflow_task:
                return

            if ex.status_code == 404:
                cluster: IBMKubernetesCluster = db_session.query(IBMKubernetesCluster).filter_by(
                    id=workflow_task.resource_id
                ).first()

                if cluster:
                    db_session.delete(cluster)
                    IBMResourceLog(
                        resource_id=cluster.resource_id, region=cluster.region,
                        status=IBMResourceLog.STATUS_DELETED, resource_type=IBMKubernetesCluster.__name__,
                        data=cluster.to_json())

                    workflow_task.status = WorkflowTask.STATUS_SUCCESSFUL
                    db_session.commit()
                    LOGGER.success(f"IBM Cluster {cluster_name} for cloud {cloud_id} deleted from IBM successfully.")
                    return
            else:
                workflow_task.status = WorkflowTask.STATUS_FAILED
                workflow_task.message = str(ex)
                db_session.commit()
                LOGGER.fail(workflow_task.message)
                return

    with get_db_session() as db_session:
        workflow_task: WorkflowTask = db_session.query(WorkflowTask).filter_by(id=workflow_task_id).first()
        if not workflow_task:
            return

        if cluster_status != IBMKubernetesCluster.STATE_DELETING:
            if cluster_json["state"] == IBMKubernetesCluster.STATE_DELETING:
                kubernetes_cluster: IBMKubernetesCluster = db_session.query(IBMKubernetesCluster).filter_by(
                    id=workflow_task.resource_id
                ).first()

                kubernetes_cluster.ibm_state = IBMKubernetesCluster.STATE_DELETING
                kubernetes_cluster.status = IBMKubernetesCluster.STATE_DELETING.upper()
                db_session.commit()
        workflow_task.status = WorkflowTask.STATUS_RUNNING_WAIT
        db_session.commit()
        LOGGER.info(f"IBM Kubernetes Cluster {workflow_task.resource_id} deletion in progress")


@celery.task(name="sync_orchestration_versions", base=IBMWorkflowTasksBase)
def sync_orchestration_versions(workflow_task_id):
    """
    Sync latest Orchestration (Kubernetes/Openshift) Versions from IBM
    """
    with get_db_session() as db_session:
        workflow_task = db_session.query(WorkflowTask).filter_by(id=workflow_task_id).first()
        if not workflow_task:
            return

        workflow_task.status = WorkflowTask.STATUS_RUNNING
        db_session.commit()

        resource_data = deepcopy(workflow_task.task_metadata["resource_data"])
        cloud_id = resource_data["ibm_cloud"]["id"]

        cloud = db_session.query(IBMCloud).filter_by(id=cloud_id).first()
        if not cloud:
            workflow_task.status = WorkflowTask.STATUS_FAILED
            workflow_task.message = f"IBM Cloud {cloud_id} not found"
            db_session.commit()
            LOGGER.error(workflow_task.message)
            return

    client = KubernetesClient(cloud_id=cloud_id)
    try:
        orchestration_versions = client.get_kubernetes_kube_versions()
        if not orchestration_versions:
            with get_db_session() as db_session:
                workflow_task = db_session.query(WorkflowTask).filter_by(id=workflow_task_id).first()
                if not workflow_task:
                    return
                workflow_task.status = WorkflowTask.STATUS_FAILED
                workflow_task.message = \
                    f'{"IBM orchestration version for Cluster could not be fetched from IBM Cloud. Try again later"}'
                db_session.commit()
                LOGGER.note(workflow_task.message)
                return

    except (IBMAuthError, IBMConnectError, IBMExecuteError, IBMInvalidRequestError) as ex:
        with get_db_session() as db_session:
            workflow_task = db_session.query(WorkflowTask).filter_by(id=workflow_task_id).first()
            if not workflow_task:
                return

            workflow_task.status = WorkflowTask.STATUS_FAILED
            workflow_task.message = f"Sync Orchestration versions failed. Reason: {str(ex)}"
            db_session.commit()
            LOGGER.fail(workflow_task.message)
            return

    orchestration_type_details = {
        IBMKubernetesCluster.ORCHESTRATION_KUBERNETES: IBMKubernetesCluster.sync_orchestration_versions_from_ibm(
            json_body=orchestration_versions,
            orchestration_type=IBMKubernetesCluster.ORCHESTRATION_KUBERNETES
        ),
        IBMKubernetesCluster.ORCHESTRATION_OPENSHIFT: IBMKubernetesCluster.sync_orchestration_versions_from_ibm(
            json_body=orchestration_versions,
            orchestration_type=IBMKubernetesCluster.ORCHESTRATION_OPENSHIFT
        )
    }

    with get_db_session() as db_session:
        workflow_task = db_session.query(WorkflowTask).filter_by(id=workflow_task_id).first()
        if not workflow_task:
            return

        workflow_task.status = WorkflowTask.STATUS_SUCCESSFUL
        workflow_task.result = {"resource_json": orchestration_type_details}
        db_session.commit()
    LOGGER.info(f'{"IBM Orchestration Versions Synced"}')


@celery.task(name="sync_workerpool_zone_flavors", base=IBMWorkflowTasksBase)
def sync_workerpool_zone_flavors(workflow_task_id):
    """
    Sync IBM workerPool Zone flavors
    """
    with get_db_session() as db_session:
        workflow_task = db_session.query(WorkflowTask).filter_by(id=workflow_task_id).first()
        if not workflow_task:
            return

        workflow_task.status = WorkflowTask.STATUS_RUNNING
        db_session.commit()

        resource_data = deepcopy(workflow_task.task_metadata["resource_data"])
        cloud_id = resource_data["ibm_cloud"]["id"]
        zone_name = resource_data["resource_json"]["zone"]

        cloud = db_session.query(IBMCloud).filter_by(id=cloud_id).first()
        if not cloud:
            workflow_task.status = WorkflowTask.STATUS_FAILED
            workflow_task.message = f"IBM Cloud {cloud_id} not found"
            db_session.commit()
            LOGGER.error(workflow_task.message)
            return

    client = KubernetesClient(cloud_id=cloud_id)
    try:
        zone_flavors = client.list_kubernetes_zone_flavours(zone=zone_name)
        if not zone_flavors:
            with get_db_session() as db_session:
                workflow_task = db_session.query(WorkflowTask).filter_by(id=workflow_task_id).first()
                if not workflow_task:
                    return

                workflow_task.status = WorkflowTask.STATUS_FAILED
                workflow_task.message = f"Zone Flavors for zone: {zone_name} not found on on IBM cloud {cloud_id}."
                db_session.commit()
                LOGGER.error(workflow_task.message)
                return

    except (IBMAuthError, IBMConnectError, IBMExecuteError, IBMInvalidRequestError) as ex:
        with get_db_session() as db_session:
            workflow_task = db_session.query(WorkflowTask).filter_by(id=workflow_task_id).first()
            if not workflow_task:
                return

            workflow_task.status = WorkflowTask.STATUS_FAILED
            workflow_task.message = f"Sync Zone flavors failed. Reason: {str(ex)}"
            db_session.commit()
            LOGGER.fail(workflow_task.message)
            return

    flavors = IBMKubernetesCluster.sync_flavors_from_ibm(zone_flavors)
    with get_db_session() as db_session:
        workflow_task = db_session.query(WorkflowTask).filter_by(id=workflow_task_id).first()
        if not workflow_task:
            return

        workflow_task.status = WorkflowTask.STATUS_SUCCESSFUL
        workflow_task.result = {"resource_json": flavors}
        db_session.commit()
        LOGGER.success(f"IBM Zone flavors for zone {zone_name} synced successfully")


@celery.task(name="sync_workerpool_flavors_for_all_zones_in_region", base=IBMWorkflowTasksBase)
def sync_workerpool_flavors_for_all_zones_in_region(workflow_task_id):
    """
    Sync IBM workerPool flavors for zones. This is for MZR flavors.
    """
    with get_db_session() as db_session:
        workflow_task = db_session.query(WorkflowTask).filter_by(id=workflow_task_id).first()
        if not workflow_task:
            return

        workflow_task.status = WorkflowTask.STATUS_RUNNING
        db_session.commit()

        resource_data = deepcopy(workflow_task.task_metadata["resource_data"])
        cloud_id = resource_data["ibm_cloud"]["id"]
        zone_id_name_dict = resource_data["resource_json"]["zones"]

        cloud = db_session.query(IBMCloud).filter_by(id=cloud_id).first()
        if not cloud:
            workflow_task.status = WorkflowTask.STATUS_FAILED
            workflow_task.message = f"IBM Cloud {cloud_id} not found"
            db_session.commit()
            LOGGER.error(workflow_task.message)
            return

    client = KubernetesClient(cloud_id=cloud_id)
    try:
        for zone_id, zone_name in zone_id_name_dict.items():
            zone_flavors = client.list_kubernetes_zone_flavours(zone=zone_name)
            if not zone_flavors:
                with get_db_session() as db_session:
                    workflow_task = db_session.query(WorkflowTask).filter_by(id=workflow_task_id).first()
                    if not workflow_task:
                        return

                    workflow_task.status = WorkflowTask.STATUS_FAILED
                    workflow_task.message = f"Zone Flavors for zone: {zone_name} not found on on IBM cloud {cloud_id}."
                    db_session.commit()
                    LOGGER.error(workflow_task.message)
                    return

            zone_id_name_dict[zone_id] = IBMKubernetesCluster.sync_flavors_from_ibm(zone_flavors)
    except (IBMAuthError, IBMConnectError, IBMExecuteError, IBMInvalidRequestError) as ex:
        with get_db_session() as db_session:
            workflow_task = db_session.query(WorkflowTask).filter_by(id=workflow_task_id).first()
            if not workflow_task:
                return

            workflow_task.status = WorkflowTask.STATUS_FAILED
            workflow_task.message = f"Sync Zone flavors failed. Reason: {str(ex)}"
            db_session.commit()
            LOGGER.fail(workflow_task.message)
            return

    with get_db_session() as db_session:
        workflow_task = db_session.query(WorkflowTask).filter_by(id=workflow_task_id).first()
        if not workflow_task:
            return

        workflow_task.status = WorkflowTask.STATUS_SUCCESSFUL
        workflow_task.result = {"resource_json": zone_id_name_dict}
        db_session.commit()

    LOGGER.success(f'{"IBM Zones flavors for MZR synced successfully"}')


@celery.task(name="sync_cluster_workloads", base=IBMWorkflowTasksBase)
def sync_cluster_workloads(workflow_task_id):
    """
    Sync CLuster (Kubernetes/Openshift) Workloads
    """
    with get_db_session() as db_session:
        workflow_task = db_session.query(WorkflowTask).filter_by(id=workflow_task_id).first()
        if not workflow_task:
            return

        workflow_task.status = WorkflowTask.STATUS_RUNNING
        db_session.commit()

        task_metadata = deepcopy(workflow_task.task_metadata)
        cloud_id = task_metadata["ibm_cloud"]["id"]

        if workflow_task.previous_tasks:
            create_cluster_task = workflow_task.root.associated_tasks.filter(
                WorkflowTask.task_type == WorkflowTask.TYPE_CREATE).first()
            if create_cluster_task:
                cluster_resource_id = create_cluster_task.resource_id
            else:
                cluster_resource_id = task_metadata["resource_json"]["resource_id"]
        else:
            cluster_resource_id = task_metadata["resource_json"]["resource_id"]

        cloud = db_session.query(IBMCloud).filter_by(id=cloud_id).first()

        if not cloud:
            workflow_task.status = WorkflowTask.STATUS_FAILED
            workflow_task.message = f"IBM Cloud {cloud_id} not found"
            db_session.commit()
            LOGGER.error(workflow_task.message)
            return

        cluster = db_session.query(IBMKubernetesCluster).filter_by(id=cluster_resource_id).first() or db_session.query(
            IBMKubernetesCluster).filter_by(resource_id=cluster_resource_id, cloud_id=cloud_id).first()
        if not cluster:
            workflow_task.status = WorkflowTask.STATUS_FAILED
            workflow_task.message = f"IBM Cluster {cluster_resource_id} not found"
            db_session.commit()
            LOGGER.error(workflow_task.message)
            return

        cluster_resource_id = cluster.resource_id

    client = KubernetesClient(cloud_id=cloud_id)
    try:
        ibm_kube_config = client.get_kubernetes_cluster_kube_config(cluster=cluster_resource_id, admin=True)
        if not ibm_kube_config:
            with get_db_session() as db_session:
                workflow_task = db_session.query(WorkflowTask).filter_by(id=workflow_task_id).first()
                if not workflow_task:
                    return

                workflow_task.status = WorkflowTask.STATUS_FAILED
                workflow_task.message = \
                    f"Kube Config for Cluster {cluster_resource_id} could not be fetched from IBM Cloud. Try again"
                db_session.commit()
                LOGGER.note(workflow_task.message)
                return

    except (IBMAuthError, IBMConnectError, IBMExecuteError, IBMInvalidRequestError) as ex:
        with get_db_session() as db_session:
            workflow_task = db_session.query(WorkflowTask).filter_by(id=workflow_task_id).first()
            if not workflow_task:
                return

            workflow_task.status = WorkflowTask.STATUS_FAILED
            workflow_task.message = f"Sync Workloads Failed. Reason: {str(ex)}"
            db_session.commit()
            LOGGER.fail(workflow_task.message)
            return

    cluster_kube_config = Kubernetes(configuration_json=ibm_kube_config)
    try:
        cluster_workloads = IBMKubernetesCluster.sync_workloads_for_clsuter(cluster_kube_config)
    except (IBMAuthError, IBMConnectError, IBMExecuteError, IBMInvalidRequestError) as ex:
        with get_db_session() as db_session:
            workflow_task = db_session.query(WorkflowTask).filter_by(id=workflow_task_id).first()
            if not workflow_task:
                return

            workflow_task.status = WorkflowTask.STATUS_FAILED
            workflow_task.message = f"Sync Workloads Failed. Reason: {str(ex)}"
            db_session.commit()
            LOGGER.fail(workflow_task.message)
            return

    with get_db_session() as db_session:
        workflow_task = db_session.query(WorkflowTask).filter_by(id=workflow_task_id).first()
        if not workflow_task:
            return

        cluster = db_session.query(IBMKubernetesCluster).filter_by(
            resource_id=cluster_resource_id, cloud_id=cloud_id).options(undefer("workloads")).first()
        if not cluster:
            workflow_task.status = WorkflowTask.STATUS_FAILED
            workflow_task.message = f"Sync Workloads Failed as Cluster with ID '{cluster_resource_id}' doesn't exist"
            db_session.commit()
            LOGGER.error(workflow_task.message)
            return

        cluster.workloads = cluster_workloads
        workflow_task.status = WorkflowTask.STATUS_SUCCESSFUL
        workflow_task.result = {"resource_json": cluster_workloads}
        db_session.commit()

    LOGGER.success(f"Cluster {cluster_resource_id} Workloads synced")


@celery.task(name="delete_draas_blueprint", queue='disaster_recovery_queue', base=IBMWorkflowTasksBase)
def delete_draas_blueprint(workflow_task_id):
    """
    Delete draas blueprint
    """
    with get_db_session() as db_session:
        workflow_task = db_session.query(WorkflowTask).filter_by(id=workflow_task_id).first()
        if not workflow_task:
            return

        workflow_task.status = WorkflowTask.STATUS_RUNNING
        db_session.commit()

        draas_bp = db_session.query(DisasterRecoveryResourceBlueprint).filter_by(
            id=workflow_task.resource_id
        ).first()

        if not draas_bp:
            workflow_task.status = WorkflowTask.STATUS_FAILED
            workflow_task.message = f"DRaaS Blueprint {workflow_task.resource_id} doesn't exist in DB."
            db_session.commit()
            LOGGER.error(workflow_task.message)
            return

        db_session.delete(draas_bp)
        db_session.commit()

        workflow_task.status = WorkflowTask.STATUS_SUCCESSFUL
        workflow_task.message = f"DRaaS Blueprint {workflow_task.resource_id} deleted successfully from DB."
        db_session.commit()
        LOGGER.success(workflow_task.message)


@celery.task(name="create_draas_backup_iks", queue='disaster_recovery_queue', base=IBMWorkflowTasksBase)
def create_draas_backup_iks(workflow_task_id):
    """
    Create draas iks backup
    """
    with get_db_session() as db_session:
        workflow_task = db_session.query(WorkflowTask).filter_by(id=workflow_task_id).first()
        if not workflow_task:
            return

        workflow_task.status = WorkflowTask.STATUS_RUNNING
        db_session.commit()

        task_metadata = deepcopy(workflow_task.task_metadata)
        cloud_id = task_metadata["ibm_cloud"]["id"]

        cloud = db_session.query(IBMCloud).filter_by(id=cloud_id).first()
        if not cloud:
            workflow_task.status = WorkflowTask.STATUS_FAILED
            workflow_task.message = f"Cloud with id {cloud_id} doesn't exist in DB."
            db_session.commit()
            LOGGER.error(workflow_task.message)
            return

        user_id = cloud.user_id
        project_id = cloud.project_id
        backup = DisasterRecoveryBackup(name=task_metadata["backup_name"], started_at=datetime.utcnow(),
                                        scheduled=False, backup_metadata=task_metadata)

        resource_blueprint = db_session.query(DisasterRecoveryResourceBlueprint).filter_by(
            resource_id=task_metadata["cluster_id"], cloud_id=cloud_id).first()
        if resource_blueprint:
            backup.disaster_recovery_resource_blueprint = resource_blueprint
            db_session.add(backup)
            db_session.commit()
        else:
            scheduled_policy = task_metadata.get("scheduled_policy")
            dr_bp = DisasterRecoveryResourceBlueprint(
                name=task_metadata["blueprint_name"], resource_type=task_metadata["resource_type"],
                resource_id=task_metadata["cluster_id"], resource_metadata=task_metadata,
                user_id=task_metadata["user"]["id"],
                description=task_metadata.get("description"),
                scheduled_policy_state=DisasterRecoveryResourceBlueprint.SCHEDULED_POLICY_ACTIVE_STATE
                if scheduled_policy else DisasterRecoveryResourceBlueprint.SCHEDULED_POLICY_INACTIVE_STATE
            )

            dr_bp.cloud_id = task_metadata["ibm_cloud"]["id"]
            if scheduled_policy:
                if scheduled_policy.get("id"):
                    db_scheduled_policy = db_session.query(DisasterRecoveryScheduledPolicy).filter_by(
                        id=scheduled_policy["id"]
                    ).first()
                    dr_bp.disaster_recovery_scheduled_policy = db_scheduled_policy
                elif scheduled_policy.get("scheduled_cron_pattern"):
                    db_scheduled_policy = DisasterRecoveryScheduledPolicy(
                        scheduled_cron_pattern=scheduled_policy["scheduled_cron_pattern"],
                        backup_count=scheduled_policy.get("backup_count"),
                        description=scheduled_policy.get("description")
                    )
                    db_scheduled_policy.cloud_id = task_metadata["ibm_cloud"]["id"]
                    dr_bp.disaster_recovery_scheduled_policy = db_scheduled_policy

                dr_bp.last_backup_taken_at = datetime.now()
                draas_scheduled_policy = dr_bp.disaster_recovery_scheduled_policy
                if draas_scheduled_policy:
                    dr_bp.next_backup_scheduled_at = croniter(
                        draas_scheduled_policy.scheduled_cron_pattern, datetime.now()).get_next(
                        datetime)

            db_session.add(dr_bp)
            backup = DisasterRecoveryBackup(name=task_metadata["backup_name"],
                                            started_at=datetime.utcnow(),
                                            scheduled=False,
                                            backup_metadata=task_metadata
                                            )

            backup.disaster_recovery_resource_blueprint = dr_bp
            dr_bp.backups.append(backup)
            db_session.add(dr_bp)
            db_session.commit()
        consumption_workflow_root = WorkflowRoot(
            workflow_name=f"{task_metadata.get('resource_type')} {task_metadata.get('backup_name')}",
            workflow_nature="CONSUMPTION",
            root_type=WorkflowRoot.ROOT_TYPE_ON_SUCCESS,
            project_id=project_id,
            user_id=user_id
        )
        consumption_task = WorkflowTask(
            resource_type=IBMKubernetesCluster.__name__, task_type=WorkflowTask.TYPE_BACKUP_CONSUMPTION,
            task_metadata={'backup_id': backup.id, "email": task_metadata['user']['email']})
        db_session.add(consumption_workflow_root)
        consumption_workflow_root.add_next_task(consumption_task)
        workflow_task.root.add_callback_root(consumption_workflow_root)
        workflow_task.status = WorkflowTask.STATUS_SUCCESSFUL
        workflow_task.message = f'DRaaS Blueprint {task_metadata["resource_json"]["resource_id"]} backup saved in DB.'
        db_session.commit()
        LOGGER.success(workflow_task.message)


@celery.task(name="delete_draas_backup", queue='disaster_recovery_queue', base=IBMWorkflowTasksBase)
def delete_draas_backup(workflow_task_id):
    """
    Delete draas backup
    """
    with get_db_session() as db_session:
        workflow_task = db_session.query(WorkflowTask).filter_by(id=workflow_task_id).first()
        if not workflow_task:
            return

        workflow_task.status = WorkflowTask.STATUS_RUNNING
        db_session.commit()

        draas_backup = db_session.query(DisasterRecoveryBackup).filter_by(id=workflow_task.resource_id).first()
        if not draas_backup:
            workflow_task.status = WorkflowTask.STATUS_FAILED
            workflow_task.message = f"DRaaS Backup {workflow_task.resource_id} doesn't exist in DB."
            db_session.commit()
            LOGGER.error(workflow_task.message)
            return

        db_session.delete(draas_backup)
        db_session.commit()

        workflow_task.status = WorkflowTask.STATUS_SUCCESSFUL
        workflow_task.message = f"DRaaS Backup {workflow_task.resource_id} deleted successfully from DB."
        db_session.commit()
        LOGGER.success(workflow_task.message)
