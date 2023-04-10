from ibm.models import IBMKubernetesCluster, WorkflowRoot, WorkflowTask, DisasterRecoveryResourceBlueprint
from ibm.web import db as ibmdb


def create_ibm_draas_backup_workflow(data, user, db_session=None, sketch=False):
    if not db_session:
        db_session = ibmdb.session

    workflow_name = DisasterRecoveryResourceBlueprint.__name__
    workflow_root = WorkflowRoot(user_id=user["id"], project_id=user["project_id"], workflow_name=workflow_name,
                                 workflow_nature="CREATE", fe_request_data=data)

    create_backup_task = WorkflowTask(
        task_type=WorkflowTask.TYPE_BACKUP, resource_type=IBMKubernetesCluster.__name__,
        task_metadata=data, resource_id=data["resource_json"]["resource_id"]
    )

    create_sync_workloads_task = WorkflowTask(
        task_type=WorkflowTask.TYPE_SYNC,
        resource_type=f"{IBMKubernetesCluster.__name__}_workloads",
        task_metadata=data)

    workloads_backup_task = WorkflowTask(
        task_type=WorkflowTask.TYPE_BACKUP, resource_type=DisasterRecoveryResourceBlueprint.__name__,
        task_metadata=data
    )
    workflow_root.add_next_task(create_backup_task)
    create_backup_task.add_next_task(create_sync_workloads_task)
    create_sync_workloads_task.add_next_task(workloads_backup_task)

    if not sketch:
        db_session.add(workflow_root)
    db_session.commit()
    return workflow_root
