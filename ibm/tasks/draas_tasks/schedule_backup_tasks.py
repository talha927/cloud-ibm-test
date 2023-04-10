import logging
from datetime import datetime
from sqlalchemy import asc

from ibm import get_db_session
from ibm.models import DisasterRecoveryBackup, DisasterRecoveryResourceBlueprint, WorkflowRoot, WorkflowTask
from ibm.tasks.celery_app import celery_app

LOGGER = logging.getLogger(__name__)


@celery_app.task(name="task_run_disaster_recovery_backups")
def task_run_disaster_recovery_backups():
    """
    This is a scheduled task which runs every minute, and starts takes backups specified
    It also removes old/stale backups and keeps only the number specified in backup_count
    """

    with get_db_session() as db_session:
        draas_resource_blueprints = db_session.query(DisasterRecoveryResourceBlueprint).filter(
            DisasterRecoveryResourceBlueprint.next_backup_scheduled_at <= datetime.now()).filter_by(
            scheduled_policy_state=DisasterRecoveryResourceBlueprint.SCHEDULED_POLICY_ACTIVE_STATE
        ).all()

        for draas_resource_blueprint in draas_resource_blueprints:
            resource_type = draas_resource_blueprint.resource_type
            user_id = draas_resource_blueprint.user_id
            project_id = draas_resource_blueprint.ibm_cloud.project_id
            delete_backup_workflow_root = None
            draas_scheduled_policy = draas_resource_blueprint.disaster_recovery_scheduled_policy
            workflow_name = f"{resource_type}-{draas_resource_blueprint.resource_id.split('/')[-1]}"
            in_progress_root = db_session.query(WorkflowRoot).filter_by(
                user_id=user_id, project_id=project_id, workflow_name=workflow_name).filter(
                WorkflowRoot.status.in_([
                    WorkflowRoot.STATUS_PENDING,
                    WorkflowRoot.STATUS_INITIATED,
                    WorkflowRoot.STATUS_RUNNING
                ])).first()
            if in_progress_root:
                LOGGER.info(f"Workflow root with ID: {in_progress_root.id} in status {in_progress_root.status}")
                continue

            # keep only number of backups specified and remove stale backups.
            if draas_resource_blueprint.backups.count() >= draas_scheduled_policy.backup_count:
                # limit = active_policy_state.backups.count() - active_policy.backup_count + 1
                # cause we know that here a new backup is to be taken as well that's why +1
                stale_backups = draas_resource_blueprint.backups.order_by(asc(
                    DisasterRecoveryBackup.completed_at)).limit(
                    draas_resource_blueprint.backups.count() - draas_scheduled_policy.backup_count + 1).all()
                delete_backup_workflow_root = WorkflowRoot(
                    workflow_name=workflow_name,
                    workflow_nature="DELETE_BACKUP",
                    project_id=project_id,
                    user_id=user_id
                )
                delete_tasks = list()
                for stale_backup in stale_backups:
                    metadata = {"resource_id": stale_backup.id}
                    delete_backup_task = WorkflowTask(
                        resource_type=resource_type, task_type=WorkflowTask.TYPE_DELETE_BACKUP,
                        task_metadata=metadata, resource_id=stale_backup.id)
                    delete_backup_workflow_root.add_next_task(delete_backup_task)
                    for tasks in delete_tasks:
                        tasks.add_next_task(delete_backup_task)
                    delete_backup_workflow_root.add_next_task(delete_backup_task)
                db_session.commit()

            if delete_backup_workflow_root:
                create_backup_workflow_root = WorkflowRoot(
                    root_type=WorkflowRoot.ROOT_TYPE_ON_COMPLETE,
                    workflow_name=workflow_name,
                    workflow_nature="BACKUP",
                    project_id=project_id,
                    user_id=user_id
                )
            else:
                create_backup_workflow_root = WorkflowRoot(
                    workflow_name=workflow_name,
                    workflow_nature="BACKUP",
                    project_id=project_id,
                    user_id=user_id
                )

            backup_task = WorkflowTask(
                resource_type=resource_type, task_type=WorkflowTask.TYPE_BACKUP,
                task_metadata=draas_resource_blueprint.resource_metadata
            )
            create_backup_workflow_root.add_next_task(backup_task)
            if resource_type == "IKS":
                workloads_backup_task = WorkflowTask(
                    task_type=WorkflowTask.TYPE_BACKUP, resource_type=DisasterRecoveryResourceBlueprint.__name__,
                    task_metadata=draas_resource_blueprint.resource_metadata
                )
                backup_task.add_next_task(workloads_backup_task)

            if delete_backup_workflow_root:
                db_session.add(delete_backup_workflow_root)
                delete_backup_workflow_root.add_callback_root(create_backup_workflow_root)
            else:
                db_session.add(create_backup_workflow_root)

            db_session.commit()
