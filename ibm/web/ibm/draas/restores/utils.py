from ibm.models import DisasterRecoveryBackup, IBMKubernetesCluster, IBMZone, WorkflowRoot, WorkflowTask
from ibm.web import db as ibmdb


def create_ibm_draas_restore_workflow(data, user, db_session=None, sketch=False):
    if not db_session:
        db_session = ibmdb.session

    workflow_name = data["workflow_name"]
    workflow_root = WorkflowRoot(user_id=user["id"], project_id=user["project_id"], workflow_name=workflow_name,
                                 workflow_nature="CREATE", fe_request_data=data)

    create_kubernetes_cluster_restore = WorkflowTask(
        task_type=WorkflowTask.TYPE_RESTORE, resource_type=IBMKubernetesCluster.__name__,
        resource_id=data["resource_json"]["resource_id"], task_metadata=data
    )

    workloads_restore_task = WorkflowTask(
        task_type=WorkflowTask.TYPE_SYNC,
        resource_type=f"{IBMKubernetesCluster.__name__}_workloads",
        task_metadata=data)

    workflow_root.add_next_task(create_kubernetes_cluster_restore)
    create_kubernetes_cluster_restore.add_next_task(workloads_restore_task)

    if not sketch:
        db_session.add(workflow_root)
    db_session.commit()
    return workflow_root


def ibm_draas_restore_workflow(data, user, db_session=None, sketch=False, backup_id=None):
    if not db_session:
        db_session = ibmdb.session

    workflow_name = f"{DisasterRecoveryBackup.__name__} {data['resource_json']['name']}"
    workflow_root = WorkflowRoot(user_id=user["id"], project_id=user["project_id"], workflow_name=workflow_name,
                                 workflow_nature="CREATE", fe_request_data=data)

    if data.get("draas_restore_type_iks") == "TYPE_EXISTING_IKS":
        create_kubernetes_cluster_restore = WorkflowTask(
            task_type=WorkflowTask.TYPE_RESTORE, resource_type=IBMKubernetesCluster.__name__,
            task_metadata=data
        )

        workloads_restore_task = WorkflowTask(
            task_type=WorkflowTask.TYPE_SYNC,
            resource_type=f"{IBMKubernetesCluster.__name__}_workloads",
            task_metadata=data)

        workflow_root.add_next_task(create_kubernetes_cluster_restore)
        create_kubernetes_cluster_restore.add_next_task(workloads_restore_task)

    if data.get("draas_restore_type_iks") in ["TYPE_EXISTING_VPC_NEW_IKS", "TYPE_NEW_VPC_NEW_IKS"]:
        create_cluster_task = WorkflowTask(
            task_type=WorkflowTask.TYPE_CREATE, resource_type=IBMKubernetesCluster.__name__,
            task_metadata=data
        )

        create_kubernetes_cluster_restore = WorkflowTask(
            task_type=WorkflowTask.TYPE_RESTORE, resource_type=IBMKubernetesCluster.__name__,
            task_metadata=data
        )

        workloads_sync_task = WorkflowTask(
            task_type=WorkflowTask.TYPE_SYNC,
            resource_type=f"{IBMKubernetesCluster.__name__}_workloads",
            task_metadata=data)

        workflow_root.add_next_task(create_cluster_task)
        create_cluster_task.add_next_task(create_kubernetes_cluster_restore)
        create_kubernetes_cluster_restore.add_next_task(workloads_sync_task)

    if not sketch:
        db_session.add(workflow_root)
    db_session.commit()

    return workflow_root


def region_to_zones(region_id):
    """This function's intention is only to get zones ids for a given region_id.
    """
    return ibmdb.session.query(IBMZone.id).filter_by(region_id=region_id).all()
