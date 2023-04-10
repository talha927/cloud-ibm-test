import json
import logging

from apiflask import abort, input

from ibm.auth import authenticate
from ibm.middleware import log_restore_activity
from ibm.models import (DisasterRecoveryBackup, IBMCloud, IBMImage, IBMKubernetesCluster, IBMSshKey, WorkflowRoot,
                        WorkflowsWorkspace, IBMSatelliteCluster)
from ibm.tasks.draas_tasks.utils import update_payload_with_new_ids
from ibm.web import db as ibmdb
from ibm.web.common.utils import authorize_and_get_ibm_cloud, verify_and_get_region, create_kubernetes_restore_workflow
from ibm.web.ibm.draas import ibm_draas
from .schemas import ClusterRestoreInSchema, DisasterRecoveryRestoreInSchema, AgentClusterRestoreInSchema
from .utils import create_ibm_draas_restore_workflow, region_to_zones

LOGGER = logging.getLogger(__name__)


@ibm_draas.post('/draas_backups/<backup_id>/restore')
@authenticate
@log_restore_activity
@input(DisasterRecoveryRestoreInSchema)
def restore_backup(backup_id, data, user):
    """
    Restore Disaster Recovery Backup
    This request restores Disaster Recovery Backup for a given backup_id
    """
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

    if data["resource_type"] == "IKS":
        restore_type_existing_iks = data.get("restore_type_existing_iks")
        kubernetes_cluster_target = ibmdb.session.query(IBMKubernetesCluster).filter_by(
            id=restore_type_existing_iks["ibm_cluster_target"]["id"]
        ).first()

        if not kubernetes_cluster_target:
            message = f'IBM Kubernetes Cluster {restore_type_existing_iks["ibm_cluster_target"]["id"]} does not exist'
            LOGGER.debug(message)
            abort(404, message)

        cos_bucket_id = blueprint.resource_metadata["cos_bucket_id"]
        cos_access_keys_id = blueprint.resource_metadata["cos_access_keys_id"]
        namespaces = blueprint.resource_metadata["namespaces"]
        task_metadata = {
            "ibm_cloud": {
                "id": restore_type_existing_iks["ibm_cloud"]["id"]
            },
            "cos_bucket_id": cos_bucket_id,
            "cos_access_keys_id": cos_access_keys_id,
            "backup_name": backup.name,
            "namespaces": namespaces,
            "backup_id": backup_id,
            "workflow_name": f"{DisasterRecoveryBackup.__name__} {kubernetes_cluster_target.name}",
            "email": user.get("email"),
            "resource_type": data["resource_type"],
            "user": user
        }
        backup_provider = backup.backup_metadata['resource_json'].get('provider')
        task_metadata["backup_provider"] = backup_provider
        if backup_provider and backup_provider != "vpc-gen2":  # Classic cluster backup
            kubernetes_cluster = ibmdb.session.query(IBMKubernetesCluster).filter_by(
                id=restore_type_existing_iks["ibm_cluster_source"]["id"]
            ).first()
            if not kubernetes_cluster:
                message = f'IBM Kubernetes Cluster {restore_type_existing_iks["ibm_cluster_source"]["id"]} does not ' \
                          f'exist'
                LOGGER.debug(message)
                abort(404, message)

            resource_json = {
                "name": kubernetes_cluster_target.name,
                "target_resource_id": kubernetes_cluster_target.resource_id,
                "resource_id": kubernetes_cluster.resource_id,
                "target_cluster_hostname": kubernetes_cluster_target.ingress.get("hostname"),
                "classic_cluster_name": kubernetes_cluster.name,
                "classic_cluster_ingress_hostname": kubernetes_cluster.ingress.get("hostname")
            }

        else:
            resource_json = {
                "name": kubernetes_cluster_target.name,
                "resource_id": kubernetes_cluster_target.resource_id
            }

        task_metadata["resource_json"] = resource_json
        workflow_root = create_ibm_draas_restore_workflow(data=task_metadata, user=user)
        return workflow_root.to_json(metadata=True)
    else:
        from ibm.web.ibm.workspaces.utils import create_workspace_workflow
        cloud_id = data["ibm_cloud"]["id"]
        region_id = data["region"]["id"]

        ibm_cloud = authorize_and_get_ibm_cloud(cloud_id=cloud_id, user=user)
        verify_and_get_region(ibm_cloud=ibm_cloud, region_id=region_id)

        workspace_payload = backup.backup_metadata["workspace_payload"]
        updated_workspace_payload = update_payload_with_new_ids(workspace_payload)
        if workspace_payload.get("address_prefixes"):
            old_region_id = updated_workspace_payload["address_prefixes"][0]["region"]["id"]

            zones_old_ids = region_to_zones(old_region_id)
            zones_new_ids = region_to_zones(region_id)

            json_dict_str = json.dumps(updated_workspace_payload)
            json_dict_str = json_dict_str.replace(old_region_id, region_id)

            for old_id, new_id in zip(zones_old_ids, zones_new_ids):
                json_dict_str = json_dict_str.replace(old_id[0], new_id[0])

            updated_workspace_payload = json.loads(json_dict_str)

        for ibm_ssh_key in updated_workspace_payload['ssh_keys']:
            ssh_key = ibmdb.session.query(IBMSshKey).filter_by(name=ibm_ssh_key["resource_json"]['name'],
                                                               public_key=ibm_ssh_key["resource_json"]['public_key'],
                                                               region_id=ibm_ssh_key["region"]["id"]).first()
            if ssh_key:
                for instance in updated_workspace_payload.get("instances"):
                    for key in instance.get("resource_json").get("keys"):
                        if key.get("name") == ssh_key.name:
                            key["id"] = ssh_key.id
                updated_workspace_payload["ssh_keys"].remove(ibm_ssh_key)

        for instance_images in updated_workspace_payload["instances"]:
            image = instance_images["resource_json"].get("image")
            if not image:
                continue
            if image.get("name"):
                instance_images["resource_json"]["image"].pop("id", None)
                continue
            old_image = ibmdb.session.query(IBMImage).filter_by(
                region_id=old_region_id, cloud_id=cloud_id, id=instance_images["resource_json"]["image"]["id"]
            ).first()
            if old_image:
                new_image = ibmdb.session.query(IBMImage).filter_by(region_id=region_id, cloud_id=cloud_id,
                                                                    name=old_image.name).first()
                if new_image:
                    updated_workspace_payload["instances"][0]["resource_json"]["image"]["id"] = new_image.id

        updated_workspace_payload["cloud_id"] = blueprint.cloud_id
        updated_workspace_payload["backup_name"] = backup.name
        updated_workspace_payload['resource_type'] = blueprint.resource_type
        updated_workspace_payload['project_id'] = user.get("project_id")
        updated_workspace_payload["user_id"] = user.get("id")

        workspace_tree = create_workspace_workflow(user, data=updated_workspace_payload, backup_id=backup_id,
                                                   source_cloud=WorkflowsWorkspace.IBM,
                                                   workspace_type=WorkflowsWorkspace.TYPE_RESTORE)
        for workflow_root in workspace_tree.associated_roots.all():
            workflow_root.status = WorkflowRoot.STATUS_READY
            ibmdb.session.commit()

        workspace_tree.status = WorkflowsWorkspace.STATUS_PENDING
        ibmdb.session.commit()

        return workspace_tree.to_json()


@ibm_draas.post('/draas-eks-restores')
@authenticate
@input(ClusterRestoreInSchema)
def restore_eks_backup(data, user):
    """
    Restore Disaster Recovery EKS Backup in IKS cluster
    This request restores Disaster Recovery Backup for a eks backup
    """
    cloud = data["ibm_cloud"]
    cloud["user_id"] = user["id"]
    cloud["project_id"] = user["project_id"]
    ibm_cloud = ibmdb.session.query(IBMCloud).filter_by(
        **cloud
    ).first()
    if not ibm_cloud:
        message = f"IBM Cloud {cloud['id'] if cloud.get('id') else cloud.get('name')} not found"
        LOGGER.debug(message)
        abort(404, message)

    if ibm_cloud.status != IBMCloud.STATUS_VALID:
        message = f"IBM Cloud {ibm_cloud.name} is not in {IBMCloud.STATUS_VALID} status"
        LOGGER.debug(message)
        abort(404, message)

    cluster = data["cluster"]
    cluster["cloud_id"] = ibm_cloud.id
    kubernetes_cluster = ibmdb.session.query(IBMKubernetesCluster).filter_by(
        **cluster
    ).first()
    if not kubernetes_cluster:
        message = f'IBM Kubernetes Cluster {cluster["id"] if data["cluster"].get["id"] else cluster["name"]} does ' \
                  f'not exist'
        LOGGER.debug(message)
        abort(404, message)

    workflow_root = create_kubernetes_restore_workflow(user, IBMKubernetesCluster, data)
    return workflow_root.to_json()


@ibm_draas.post('/draas-satellite-restores')
@authenticate
@input(AgentClusterRestoreInSchema)
def restore_eks_backup_satellite_cluster(data, user):
    """
    Restore Disaster Recovery EKS Backup in Satellite cluster
    This request restores Disaster Recovery Backup for a eks backup
    """
    cloud = data["ibm_cloud"]
    cloud["user_id"] = user["id"]
    cloud["project_id"] = user["project_id"]
    ibm_cloud = ibmdb.session.query(IBMCloud).filter_by(
        **cloud
    ).first()
    if not ibm_cloud:
        message = f"IBM Cloud {cloud['id'] if cloud.get('id') else cloud.get('name')} not found"
        LOGGER.debug(message)
        abort(404, message)

    if ibm_cloud.status != IBMCloud.STATUS_VALID:
        message = f"IBM Cloud {ibm_cloud.name} is not in {IBMCloud.STATUS_VALID} status"
        LOGGER.debug(message)
        abort(404, message)

    cluster = data["cluster"]
    agent_id = data['agent_id']
    cluster["cloud_id"] = ibm_cloud.id
    satellite_cluster = ibmdb.session.query(IBMSatelliteCluster).filter_by(
        **cluster
    ).first()
    if not satellite_cluster:
        message = f'IBM Satellite Cluster {cluster["id"] if data["cluster"].get["id"] else cluster["name"]} does ' \
                  f'not exist'
        LOGGER.debug(message)
        abort(404, message)

    satellite_cluster.agent_id = agent_id
    ibmdb.session.commit()

    workflow_root = create_kubernetes_restore_workflow(user, IBMSatelliteCluster, data)
    return workflow_root.to_json()
