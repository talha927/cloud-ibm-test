import json
from copy import deepcopy
from datetime import datetime

import requests
from requests.exceptions import ConnectionError, ReadTimeout, RequestException

from config import VeleroConfig
from ibm import get_db_session, LOGGER
from ibm.common.consts import IBM_CLOUD, ONPREM, CERTS
from ibm.models import WorkflowTask, IBMCloudObjectStorage, IBMServiceCredentialKey, IBMCOSBucket, IBMCloud, \
    WorkflowRoot, DisasterRecoveryBackup, DisasterRecoveryResourceBlueprint
from ibm.models.agent.agent_models import OnPremCluster
from ibm.tasks.celery_app import celery_app as celery
from ibm.tasks.common.tasks_base import IBMWorkflowTasksBase
from ibm.web.agent.consts import POST_AGENT_TASK_PATH, GET_NODES, GET_NAMESPACES, GET_NAMESPACES_PODS, \
    GET_NAMESPACES_PVC, GET_NAMESPACES_SVC, GET_STORAGE_CLASSES, GET_STORAGE_CLASS_BY_NAME
from ibm.web.agent.utils import make_json_request_body, _execute_api, response_parser
from ibm.web.ibm.kubernetes.consts import BACKUP, BACKUP_FAILURE_ERROR_MSG, RESTORE_FAILURE_ERROR_MSG, RESTORE, \
    PVC_PAYLOAD
from ibm.web.ibm.kubernetes.utils import construct_payload


def validate_response_fail_task(status_code, workflow_task_id):
    with get_db_session() as db_session:
        workflow_task = db_session.query(WorkflowTask).filter_by(id=workflow_task_id).first()
        if not workflow_task:
            return

        if status_code != 200:
            workflow_task.status = WorkflowTask.STATUS_FAILED
            workflow_task.message = "Discovery Failed:  {}".format(status_code)
            db_session.commit()
            LOGGER.error(workflow_task.message)
            return False
        return True


@celery.task(name="discover_on_prem_cluster", base=IBMWorkflowTasksBase)
def discover_on_prem_cluster(workflow_task_id):
    """
    Discover on prem cluster
    """
    with get_db_session() as db_session:
        workflow_task = db_session.query(WorkflowTask).filter_by(id=workflow_task_id).first()
        if not workflow_task:
            return

        workflow_task.status = WorkflowTask.STATUS_RUNNING
        db_session.commit()

        resource_data = deepcopy(workflow_task.task_metadata["resource_data"])
        resource_json = deepcopy(resource_data["resource_json"])
        cluster_creds = resource_data["cluster_creds"]
        user_id = resource_data["user_id"]
        cloud_id = resource_data["cloud_id"]
        agent_id = resource_json["agent_id"]
        cluster_name = resource_json["name"]
        kube_config = resource_data["kube_config"]

        cluster_workloads = []
        oc_count = 0

    try:
        nodes_body = make_json_request_body(user_id, GET_NODES, cluster_creds, "GET")
        response = _execute_api("POST", POST_AGENT_TASK_PATH.format(agent_id=agent_id), nodes_body)
        if not validate_response_fail_task(response.status_code, workflow_task_id):
            return
        res = response_parser(response.json())

        namespace_body = make_json_request_body(user_id, GET_NAMESPACES, cluster_creds, "GET")
        ns_response = _execute_api("POST", POST_AGENT_TASK_PATH.format(agent_id=agent_id), namespace_body)
        if not validate_response_fail_task(ns_response.status_code, workflow_task_id):
            return

        if ns_response.status_code == 200:
            namespaces = json.loads(ns_response.json())

            for namespace in namespaces['items']:
                temp = {"namespace": "", "pod": [], "svc": [], "pvc": []}
                if namespace['metadata']['name'] == "velero":
                    pass
                else:
                    if 'openshift' in namespace['metadata']['name']:
                        oc_count += 1
                    temp["namespace"] = namespace['metadata']['name']
                    pods_body = make_json_request_body(user_id, GET_NAMESPACES_PODS.format(
                        namespace=namespace['metadata']['name']), cluster_creds, "GET")

                    res_pods = _execute_api("POST", POST_AGENT_TASK_PATH.format(agent_id=agent_id), body=pods_body)
                    if not validate_response_fail_task(res_pods.status_code, workflow_task_id):
                        return
                    if res_pods.status_code == 200:
                        pods = json.loads(res_pods.json())
                        if pods['items']:
                            for pod in pods['items']:
                                temp["pod"].append(pod['metadata']['name'])

                    pvcs_body = make_json_request_body(user_id, GET_NAMESPACES_PVC.format(
                        namespace=namespace['metadata']['name']), cluster_creds, "GET")

                    res_pvcs = _execute_api("POST", POST_AGENT_TASK_PATH.format(agent_id=agent_id), body=pvcs_body)
                    if not validate_response_fail_task(res_pvcs.status_code, workflow_task_id):
                        return
                    if res_pvcs.status_code == 200:
                        pvcs = json.loads(res_pvcs.json())
                        if pvcs['items']:
                            for pvc in pvcs['items']:
                                storage_class_name = pvc['spec']['storageClassName']
                                pvc_object = {"name": pvc['metadata']['name'],
                                              "namespace": pvc['metadata']['namespace'],
                                              "phase": pvc['status']['phase'],
                                              "size": pvc['spec']['resources']['requests']['storage'],
                                              "storage_class_name": pvc['spec']['storageClassName']}
                                if pvc['status']['phase'] == "Bound" and storage_class_name != "manual":
                                    storage_provisioner = pvc['metadata']['annotations'].get(
                                        'volume.beta.kubernetes.io/storage-provisioner') if pvc['metadata'][
                                        'annotations'] else None
                                    if storage_provisioner:
                                        pvc_object['type'] = storage_provisioner
                                    elif storage_class_name == "default":
                                        storage_classes_body = make_json_request_body(user_id, GET_STORAGE_CLASSES,
                                                                                      cluster_creds,
                                                                                      "GET")
                                        res_storage_classes = _execute_api("POST", POST_AGENT_TASK_PATH.format(
                                            agent_id=agent_id), body=storage_classes_body)

                                        if not validate_response_fail_task(res_storage_classes.status_code,
                                                                           workflow_task_id):
                                            return

                                        res_storage_classes_json = res_storage_classes.json()
                                        res_storage_classes_dict = json.loads(res_storage_classes_json)
                                        for storage_class in res_storage_classes_dict['items']:
                                            if storage_class['metadata']['annotations'].get(
                                                    'storageclass.kubernetes.io/is-default-class') == 'true':
                                                pvc_object['type'] = storage_class['provisioner']

                                    else:
                                        storage_class_detail_body = make_json_request_body(
                                            user_id,
                                            GET_STORAGE_CLASS_BY_NAME.format(
                                                storageclass_name=storage_class_name),
                                            cluster_creds, "GET")
                                        res_storage_class_detail = _execute_api("POST", POST_AGENT_TASK_PATH.format(
                                            agent_id=agent_id), body=storage_class_detail_body)

                                        if not validate_response_fail_task(res_storage_class_detail.status_code,
                                                                           workflow_task_id):
                                            return
                                        res_storage_class_detail_json = res_storage_class_detail.json()
                                        res_storage_class_detail_dict = json.loads(res_storage_class_detail_json)
                                        pvc_object['type'] = res_storage_class_detail_dict['provisioner']
                                    temp["pvc"].append(pvc_object)

                    svcs_body = make_json_request_body(user_id, GET_NAMESPACES_SVC.format(
                        namespace=namespace['metadata']['name']), cluster_creds, "GET")

                    res_svcs = _execute_api("POST", POST_AGENT_TASK_PATH.format(agent_id=agent_id), body=svcs_body)
                    if not validate_response_fail_task(res_svcs.status_code, workflow_task_id):
                        return
                    if res_svcs.status_code == 200:
                        svcs = json.loads(res_svcs.json())
                        if svcs['items']:
                            for svc in svcs['items']:
                                temp["svc"].append(svc['metadata']['name'])

                    cluster_workloads.append(temp)

        cluster_type = "Openshift" if oc_count > 0 else "Kubernetes"

    except Exception as ex:
        with get_db_session() as db_session:
            workflow_task = db_session.query(WorkflowTask).filter_by(id=workflow_task_id).first()
            if not workflow_task:
                return

            workflow_task.status = WorkflowTask.STATUS_FAILED
            workflow_task.message = f"Discovery Failed. Reason: {str(ex)}"
            db_session.commit()
            LOGGER.error(workflow_task.message)
            return

    with get_db_session() as db_session:
        workflow_task = db_session.query(WorkflowTask).filter_by(id=workflow_task_id).first()
        if not workflow_task:
            return

        cluster = OnPremCluster(name=cluster_name,
                                server_ip=cluster_creds['server'],
                                client_certificate_data=cluster_creds['client_certificate_data'],
                                client_key_data=cluster_creds['client_key_data'],
                                worker_count=res['worker_count'],
                                kube_version=res['kube_version'],
                                cluster_type=cluster_type,
                                workloads=cluster_workloads,
                                agent_id=agent_id,
                                kube_config=kube_config,
                                cloud_id=cloud_id)
        db_session.add(cluster)
        workflow_task.status = WorkflowTask.STATUS_SUCCESSFUL
        db_session.commit()

        workflow_task.result = {"Discover Cluster": cluster.request_json()}
        db_session.commit()

    LOGGER.info(f"OnPrem Cluster discovery completed with name '{cluster_name}' for IBMCloud '{cloud_id}'")


@celery.task(name="create_onprem_agent_cluster_backup", queue='disaster_recovery_queue', base=IBMWorkflowTasksBase)
def create_onprem_agent_cluster_backup(workflow_task_id):
    """
    Create Backup of a OnPrem Agent Cluster
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
        source_cluster_name = task_metadata['resource_json']['name']
        source_cluster_id = task_metadata['resource_json']['id']
        backup_namespaces = task_metadata.get('namespaces')
        user_id = task_metadata['user']["id"]

        ibm_cloud = db_session.query(IBMCloud).filter_by(id=cloud_id).first()
        if not ibm_cloud:
            workflow_task.status = WorkflowTask.STATUS_FAILED
            workflow_task.message = f"IBM Cloud {cloud_id} not found"
            db_session.commit()
            LOGGER.error(workflow_task.message)
            return

        cluster = db_session.query(OnPremCluster).filter_by(id=source_cluster_id, cloud_id=cloud_id).first()
        if not cluster:
            workflow_task.status = WorkflowTask.STATUS_FAILED
            workflow_task.message = f"IBM Cluster {source_cluster_id} not found"
            db_session.commit()
            LOGGER.error(workflow_task.message)
            return

        cloud_object_storage_key = db_session.query(IBMCloudObjectStorage).filter_by(id=cloud_object_storage_id,
                                                                                     cloud_id=cloud_id).first()
        if not cloud_object_storage_key:
            workflow_task.status = WorkflowTask.STATUS_FAILED
            workflow_task.message = f"IBM COS Keys '{cloud_object_storage_id}' not found"
            db_session.commit()
            LOGGER.error(workflow_task.message)
            return

        cos_access_keys = db_session.query(IBMServiceCredentialKey).filter_by(id=cos_access_keys_id,
                                                                              cloud_id=cloud_id).first()
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

        bucket = db_session.query(IBMCOSBucket).filter_by(id=cos_bucket_id, cloud_id=cloud_id).first()
        if not bucket:
            workflow_task.status = WorkflowTask.STATUS_FAILED
            workflow_task.message = f"IBM COS bucket '{cos_bucket_id}' not found"
            db_session.commit()
            LOGGER.error(workflow_task.message)
            return

        bucket_name = bucket.name
        bucket_region = bucket.location_constraint
        kube_config = cluster.kube_config
        agent_id = cluster.agent_id
        cluster_type = cluster.cluster_type

    hmac = {
        "access_key": cos_access_keys.access_key_id,
        "secret_key": cos_access_keys.secret_access_key
    }

    payload = construct_payload(
        cluster_name=source_cluster_name, hmac_keys=hmac,
        kube_config=kube_config, region=bucket_region, namespaces=backup_namespaces, operation_type=BACKUP,
        bucket_name=bucket_name, backup_name=backup_name, cluster_type=cluster_type, agent_id=agent_id,
        user_id=user_id, source_cloud=ONPREM, target_cloud=IBM_CLOUD, auth_type=CERTS
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

    with get_db_session() as db_session:
        workflow_task = db_session.query(WorkflowTask).filter_by(id=workflow_task_id).first()
        if not workflow_task:
            return

        if response.status_code != 202:
            workflow_task.message = BACKUP_FAILURE_ERROR_MSG + "\n" + response.reason
            workflow_task.status = WorkflowTask.STATUS_FAILED
            LOGGER.fail(workflow_task.message)
            return

        on_prem_id = task_metadata['resource_json']['id']
        task_metadata['velero_task_id'] = response_json["task_id"]
        workflow_task.task_metadata = task_metadata
        workflow_task.status = WorkflowTask.STATUS_RUNNING_WAIT
        db_session.commit()
        LOGGER.success(f"OnPrem cluster backup initiated successfully for cluster having ONPREMid '{on_prem_id}'")


@celery.task(name="create_wait_onprem_agent_cluster_backup", queue='disaster_recovery_queue', base=IBMWorkflowTasksBase)
def create_wait_onprem_agent_cluster_backup(workflow_task_id):
    """
    Create wait Backup of a OnPrem Agent Cluster
    """
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

        elif response_json["status"] == WorkflowRoot.STATUS_C_SUCCESSFULLY:
            workflow_task.message = "OnPrem cluster backup created successfully"
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
        on_prem_id = task_metadata['resource_json']['id']
        LOGGER.info(f"OnPrem cluster backup in progress for cluster having ONPREMid '{on_prem_id}'")


@celery.task(name="create_draas_backup_onprem", queue='disaster_recovery_queue', base=IBMWorkflowTasksBase)
def create_draas_backup_onprem(workflow_task_id):
    """
    Create draas onprem backup
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
            resource_id=task_metadata['resource_json']['id'], cloud_id=cloud_id).first()
        if resource_blueprint:
            backup.disaster_recovery_resource_blueprint = resource_blueprint
            db_session.add(backup)
            db_session.commit()
        else:
            scheduled_policy = task_metadata.get("scheduled_policy")
            dr_bp = DisasterRecoveryResourceBlueprint(
                name=task_metadata['resource_json']['name'], resource_type=task_metadata["resource_type"],
                resource_id=task_metadata['resource_json']['id'], resource_metadata=task_metadata,
                user_id=task_metadata["user"]["id"],
                scheduled_policy_state=DisasterRecoveryResourceBlueprint.SCHEDULED_POLICY_ACTIVE_STATE
                if scheduled_policy else DisasterRecoveryResourceBlueprint.SCHEDULED_POLICY_INACTIVE_STATE
            )

            dr_bp.cloud_id = task_metadata["ibm_cloud"]["id"]

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
            resource_type=OnPremCluster.__name__, task_type=WorkflowTask.TYPE_BACKUP_CONSUMPTION,
            task_metadata={'backup_id': backup.id})
        db_session.add(consumption_workflow_root)
        consumption_workflow_root.add_next_task(consumption_task)
        workflow_task.root.add_callback_root(consumption_workflow_root)
        workflow_task.status = WorkflowTask.STATUS_SUCCESSFUL
        workflow_task.message = f'DRaaS Blueprint {task_metadata["resource_json"]["id"]} onprem backup saved in DB.'
        db_session.commit()
        LOGGER.success(workflow_task.message)


@celery.task(name="create_onprem_cluster_restore", queue='disaster_recovery_queue', base=IBMWorkflowTasksBase)
def create_onprem_cluster_restore(workflow_task_id):
    """
    Create Restore on existing OnPrem Cluster
    """
    with get_db_session() as db_session:
        workflow_task = db_session.query(WorkflowTask).filter_by(id=workflow_task_id).first()
        if not workflow_task:
            return

        workflow_task.status = WorkflowTask.STATUS_RUNNING
        db_session.commit()
        task_metadata = deepcopy(workflow_task.task_metadata)

        cloud_id = task_metadata["ibm_cloud"]["id"]
        backup_id = task_metadata["backup_id"]
        backup_name = task_metadata["backup_name"]
        target_cluster_id = task_metadata['resource_json']['id']
        target_cluster_name = task_metadata['resource_json']['name']
        cos_bucket_id = task_metadata["cos_bucket_id"]
        cos_access_keys_id = task_metadata["cos_access_keys_id"]
        user_id = task_metadata['user']["id"]

        ibm_cloud = db_session.query(IBMCloud).filter_by(id=cloud_id).first()
        if not ibm_cloud:
            workflow_task.status = WorkflowTask.STATUS_FAILED
            workflow_task.message = f"IBM Cloud {cloud_id} not found"
            db_session.commit()
            LOGGER.error(workflow_task.message)
            return

        target_cluster = db_session.query(OnPremCluster).filter_by(id=target_cluster_id, cloud_id=cloud_id).first()
        if not target_cluster:
            workflow_task.status = WorkflowTask.STATUS_FAILED
            workflow_task.message = f"On_prem Cluster {target_cluster_id} not found"
            db_session.commit()
            LOGGER.error(workflow_task.message)
            return

        cos_access_keys = db_session.query(IBMServiceCredentialKey).filter_by(id=cos_access_keys_id,
                                                                              cloud_id=cloud_id).first()
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

        bucket = db_session.query(IBMCOSBucket).filter_by(id=cos_bucket_id, cloud_id=cloud_id).first()
        if not bucket:
            workflow_task.status = WorkflowTask.STATUS_FAILED
            workflow_task.message = f"IBM COS bucket '{cos_bucket_id}' not found"
            db_session.commit()
            LOGGER.error(workflow_task.message)
            return

        bucket_name = bucket.name
        bucket_region = bucket.location_constraint
        restore_name = "restore" + str(datetime.utcnow().strftime("-%m-%d-%Y%H-%M-%S"))
        kube_config = target_cluster.kube_config
        agent_id = target_cluster.agent_id
        cluster_type = target_cluster.cluster_type

        backup_pvcs_list = []
        backup = db_session.query(DisasterRecoveryBackup).filter_by(id=backup_id).first()
        if backup:
            resource_json = backup.backup_metadata.get("resource_json")
            for workload in resource_json.get("workloads"):
                for pvc in workload["pvc"]:
                    PVC_PAYLOAD["name"] = pvc["name"]
                    PVC_PAYLOAD["size"] = pvc["size"]
                    PVC_PAYLOAD["namespace"] = pvc["namespace"]
                    PVC_PAYLOAD['provisioner'] = pvc["type"]
                    PVC_PAYLOAD["storageClassName"] = pvc["storage_class_name"]
                    backup_pvcs_list.append(PVC_PAYLOAD)

        hmac = {
            "access_key": cos_access_keys.access_key_id,
            "secret_key": cos_access_keys.secret_access_key
        }

        payload = construct_payload(
            cluster_name=target_cluster_name, hmac_keys=hmac, kube_config=kube_config, cluster_type=cluster_type,
            region=bucket_region, operation_type=RESTORE, bucket_name=bucket_name, agent_id=agent_id, user_id=user_id,
            restore_name=restore_name, backup_name=backup_name, persistent_volume_claims=backup_pvcs_list,
            source_cloud=IBM_CLOUD, target_cloud=ONPREM, auth_type=CERTS
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
        LOGGER.info("On_prem cluster restore initiated on cluster {}".format(target_cluster_name))


@celery.task(name="create_wait_onprem_cluster_restore", queue='disaster_recovery_queue', base=IBMWorkflowTasksBase)
def create_wait_onprem_cluster_restore(workflow_task_id):
    with get_db_session() as db_session:
        workflow_task = db_session.query(WorkflowTask).filter_by(id=workflow_task_id).first()
        if not workflow_task:
            return

        workflow_task.status = WorkflowTask.STATUS_RUNNING
        db_session.commit()
        task_metadata = deepcopy(workflow_task.task_metadata)
        if task_metadata.get('resource_json', {}).get('name'):
            cluster_name = task_metadata['resource_json']['name']

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

            workflow_task.message = "On_prem cluster restore completed successfully"
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
        LOGGER.info("On_prem cluster {} restore in progress".format(cluster_name))
