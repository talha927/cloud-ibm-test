import json
from datetime import datetime

import yaml
from apiflask import APIBlueprint, abort, input, output
from flask import Response, request

from ibm import LOGGER
from ibm.auth import authenticate
from ibm.common.consts import ONPREM
from ibm.common.req_resp_schemas.schemas import WorkflowRootOutSchema
from ibm.models import WorkflowRoot, WorkflowTask, DisasterRecoveryResourceBlueprint, DisasterRecoveryBackup
from ibm.models.agent.agent_models import OnPremCluster
from ibm.web import db as ibmdb
from ibm.web.agent.consts import GET_AGENT_PATH
from ibm.web.agent.schemas import IBMAgentDiscoverClusterInSchema, IBMAgentBackupClusterInSchema, \
    IBMAgentRestoreClusterInSchema
from ibm.web.agent.utils import _execute_api, agent_health, parse_yaml_file
from ibm.web.common.utils import authorize_and_get_ibm_cloud

agent = APIBlueprint('agent', __name__, tag="Agent")


@agent.get('/clouds/<cloud_id>/agents')
@authenticate
def list_agents(cloud_id, user):
    """
    List of Agents
    """
    ibm_cloud = authorize_and_get_ibm_cloud(cloud_id=cloud_id, user=user)

    response = _execute_api("GET", GET_AGENT_PATH.format(user_id=ibm_cloud.user_id))
    if not response:
        return Response(status=204)
    agents = response.json()

    agents_list = []
    for user_agent in agents:
        if 'status' not in user_agent:
            user_agent['status'] = "UP"
        agents_list.append(user_agent)

    return Response(json.dumps(agents_list), status=200, mimetype='application/json')


@agent.post('/clouds/<cloud_id>/agents/clusters/discover')
@authenticate
@input(IBMAgentDiscoverClusterInSchema)
@output(WorkflowRootOutSchema, status_code=202)
def discover_on_prem_cluster(cloud_id, data, user):
    """
    Discover on_prem cluster
    :param cloud_id:
    :param data:
    :param user: object of the user initiating the request
    :return: Response object of workflow root
    """

    ibm_cloud = authorize_and_get_ibm_cloud(cloud_id=cloud_id, user=user)

    kube_config_file = request.files['file']
    if not kube_config_file:
        message = "Kube Config is missing"
        abort(400, message)
        return

    is_agent_up = agent_health(data['agent_id'])
    if not is_agent_up:
        message = f"IBM Agent {data['agent_id']} is down"
        LOGGER.debug(message)
        abort(400, message)
        return

    cluster_creds = parse_yaml_file(kube_config_file)

    file_data = kube_config_file.read()
    kube_config = yaml.load(file_data, Loader=yaml.FullLoader)

    cluster = ibmdb.session.query(OnPremCluster).filter_by(name=data['name'],
                                                           server_ip=cluster_creds['server']).first()
    if cluster:
        message = f"IBM Agent {data['name']} with this Server IP {cluster_creds['server']} already discovered"
        LOGGER.debug(message)
        abort(409, message)
        return

    resource_data_dict = {
        "cluster_creds": cluster_creds,
        "resource_json": data,
        "user_id": ibm_cloud.user_id,
        "cloud_id": cloud_id,
        "kube_config": kube_config
    }

    workflow_root = WorkflowRoot(
        user_id=user["id"],
        project_id=user["project_id"],
        workflow_name=OnPremCluster.__name__,
        workflow_nature="DISCOVERY"
    )
    discover_cluster_task = WorkflowTask(
        task_type=WorkflowTask.TYPE_DISCOVERY,
        resource_type=OnPremCluster.__name__,
        task_metadata={"resource_data": resource_data_dict}
    )
    workflow_root.add_next_task(discover_cluster_task)
    ibmdb.session.add(workflow_root)
    ibmdb.session.commit()
    return workflow_root.to_json(metadata=True)


@agent.post('/agents/clusters/<cluster_id>/backup')
@authenticate
@input(IBMAgentBackupClusterInSchema)
@output(WorkflowRootOutSchema, status_code=202)
def backup_on_prem_cluster(cluster_id, data, user):
    """
    Backup on_prem cluster
    :param cluster_id:
    :param data:
    :param user: object of the user initiating the request
    :return: Response object of workflow root
    """
    ibm_cloud = authorize_and_get_ibm_cloud(cloud_id=data["ibm_cloud"]["id"], user=user)

    cluster = ibmdb.session.query(OnPremCluster).filter_by(id=cluster_id, cloud_id=ibm_cloud.id).first()
    if not cluster:
        message = f"IBM Cluster {cluster_id} not found"
        LOGGER.debug(message)
        abort(404, message)
        return

    is_agent_up = agent_health(cluster.agent_id)
    if not is_agent_up:
        message = f"IBM Agent {cluster.agent_id} is down"
        LOGGER.debug(message)
        abort(400, message)
        return

    task_metadata = {
        "ibm_cloud": {
            "id": data["ibm_cloud"]["id"],
        },
        "cos_bucket_id": data["cos_bucket_id"],
        "cloud_object_storage_id": data["cloud_object_storage_id"],
        "cos_access_keys_id": data["cos_access_keys_id"],
        "backup_name": data["name"] + f"-{datetime.now().strftime('%d-%m-%Y-%H.%M.%S')}",
        "resource_json": cluster.cluster_json(),
        "region": {
            "id": data["region"]["id"],
        },
        "resource_type": ONPREM,
        "namespaces": data["namespaces"],
        "user": user
    }

    workflow_root = WorkflowRoot(
        user_id=user["id"],
        project_id=user["project_id"],
        workflow_name=OnPremCluster.__name__,
        workflow_nature="BACKUP"
    )
    create_onprem_backup_task = WorkflowTask(
        task_type=WorkflowTask.TYPE_BACKUP,
        resource_type=OnPremCluster.__name__,
        task_metadata=task_metadata
    )
    create_onprem_backup_cluster_task = WorkflowTask(
        task_type=WorkflowTask.TYPE_ONPREM_BACKUP, resource_type=DisasterRecoveryResourceBlueprint.__name__,
        task_metadata=task_metadata
    )
    workflow_root.add_next_task(create_onprem_backup_task)
    create_onprem_backup_task.add_next_task(create_onprem_backup_cluster_task)
    ibmdb.session.add(workflow_root)
    ibmdb.session.commit()
    return workflow_root.to_json(metadata=True)


@agent.post('/agents/backups/<backup_id>/restore')
@authenticate
@input(IBMAgentRestoreClusterInSchema)
@output(WorkflowRootOutSchema, status_code=202)
def restore_on_prem_cluster_backup(backup_id, data, user):
    """
    Restore on_prem cluster
    :param backup_id:
    :param data:
    :param user: object of the user initiating the request
    :return: Response object of workflow root
    """
    ibm_cloud = authorize_and_get_ibm_cloud(cloud_id=data["ibm_cloud"]["id"], user=user)

    backup = ibmdb.session.query(DisasterRecoveryBackup).filter_by(id=backup_id).first()
    if not backup:
        message = f"No Disaster recovery Backup found with ID {backup_id}"
        LOGGER.debug(message)
        abort(404, message)

    if backup.status != DisasterRecoveryBackup.SUCCESS:
        message = f"Disaster recovery Backup with ID {backup_id} not ready"
        LOGGER.debug(message)
        abort(400, message)

    blueprint = backup.disaster_recovery_resource_blueprint
    cos_bucket_id = blueprint.resource_metadata["cos_bucket_id"]
    cos_access_keys_id = blueprint.resource_metadata["cos_access_keys_id"]

    on_prem_cluster_target = ibmdb.session.query(OnPremCluster).filter_by(
        id=data["on_prem_cluster_target"]["id"], cloud_id=ibm_cloud.id).first()

    if not on_prem_cluster_target:
        message = f'On_prem Cluster {data["on_prem_cluster_target"]["id"]} does not exist'
        LOGGER.debug(message)
        abort(404, message)
        return

    is_agent_up = agent_health(on_prem_cluster_target.agent_id)
    if not is_agent_up:
        message = f"IBM Agent {on_prem_cluster_target.agent_id} is down"
        LOGGER.debug(message)
        abort(400, message)
        return

    task_metadata = {
        "ibm_cloud": {
            "id": data["ibm_cloud"]["id"]
        },
        "cos_bucket_id": cos_bucket_id,
        "cos_access_keys_id": cos_access_keys_id,
        "backup_name": backup.name,
        "backup_id": backup_id,
        "workflow_name": f"{DisasterRecoveryBackup.__name__} {on_prem_cluster_target.name}",
        "email": user.get("email"),
        "resource_json": on_prem_cluster_target.cluster_json(),
        "resource_type": ONPREM,
        "user": user
    }

    workflow_root = WorkflowRoot(
        user_id=user["id"],
        project_id=user["project_id"],
        workflow_name=OnPremCluster.__name__,
        workflow_nature="RESTORE"
    )

    create_on_prem_restore_task = WorkflowTask(
        task_type=WorkflowTask.TYPE_RESTORE,
        resource_type=OnPremCluster.__name__,
        task_metadata=task_metadata
    )
    workflow_root.add_next_task(create_on_prem_restore_task)
    ibmdb.session.add(workflow_root)
    ibmdb.session.commit()
    return workflow_root.to_json(metadata=True)
