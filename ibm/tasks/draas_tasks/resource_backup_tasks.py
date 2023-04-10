import logging
from copy import deepcopy
from datetime import datetime

from croniter import croniter
from ibm import get_db_session
from ibm.models import DisasterRecoveryBackup, DisasterRecoveryResourceBlueprint, \
    IBMVpcNetwork, WorkflowTask, IBMSnapshot, WorkflowRoot
from ibm.tasks.celery_app import celery_app
from ibm.tasks.common.tasks_base import IBMWorkflowTasksBase
from ibm.tasks.draas_tasks.utils import construct_workspace_payload

LOGGER = logging.getLogger(__name__)


@celery_app.task(name="create_ibm_resource_backup_task", base=IBMWorkflowTasksBase, queue='disaster_recovery_queue')
def create_ibm_resource_backup_task(workflow_task_id):
    with get_db_session() as db_session:
        workflow_task = db_session.query(WorkflowTask).filter_by(id=workflow_task_id).first()
        if not workflow_task:
            return

        workflow_task.status = WorkflowTask.STATUS_RUNNING
        db_session.commit()
        task_metadata = workflow_task.task_metadata
        project_id = task_metadata.get("project_id")
        email = task_metadata.get("email")
        is_volume = task_metadata.get("is_volume")

        draas_resource_blueprint_id = task_metadata["draas_resource_blueprint_id"]
        draas_resource_blueprint: DisasterRecoveryResourceBlueprint = \
            db_session.query(DisasterRecoveryResourceBlueprint).filter_by(id=draas_resource_blueprint_id).first()
        if not draas_resource_blueprint:
            msg = f"Disaster Recovery Backup Resource Blueprint with ID {draas_resource_blueprint_id} not found in DB"
            workflow_task.message = msg
            workflow_task.status = WorkflowTask.STATUS_FAILED
            db_session.commit()
            LOGGER.info(msg)
            return

        user_id = draas_resource_blueprint.user_id

        resource_metadata = draas_resource_blueprint.resource_metadata
        resource_id = resource_metadata['resource_id']
        db_resource = db_session.query(IBMVpcNetwork).filter_by(id=resource_id).first()
        if not db_resource:
            workflow_task.status = WorkflowTask.STATUS_FAILED
            workflow_task.message = f"ibm {'IBMVpcNetwork'} with ID '{resource_id}' not found"
            db_session.commit()
            LOGGER.info(workflow_task.message)
            return

        workspace_payload, associated_resources = \
            construct_workspace_payload(vpc_name=resource_metadata["name"], resource_id=resource_id)

        workspace_payload["name"] = resource_metadata["name"]
        backup_name = f"{draas_resource_blueprint.name}_" \
                      f"{datetime.now().strftime('%d-%m-%Y-%H.%M.%S')}"
        backup = DisasterRecoveryBackup(
            name=backup_name,
            backup_metadata=dict(associated_resources=associated_resources, workspace_payload=workspace_payload),
            is_volume=is_volume
        )
        # Todo: remove ths resource_metadata column and send data to frontend from to_json
        backup.disaster_recovery_resource_blueprint = draas_resource_blueprint
        draas_resource_blueprint.last_backup_taken_at = datetime.now()
        draas_scheduled_policy = draas_resource_blueprint.disaster_recovery_scheduled_policy
        if draas_scheduled_policy:
            draas_resource_blueprint.next_backup_scheduled_at = croniter(
                draas_scheduled_policy.scheduled_cron_pattern, datetime.now()).get_next(
                datetime)
        consumption_workflow_root = WorkflowRoot(
            workflow_name=f"{task_metadata.get('resource_type')} {task_metadata.get('backup_name')}",
            workflow_nature="CONSUMPTION",
            root_type=WorkflowRoot.ROOT_TYPE_ON_SUCCESS,
            project_id=project_id,
            user_id=user_id
        )
        consumption_task = WorkflowTask(
            resource_type=IBMVpcNetwork.__name__, task_type=WorkflowTask.TYPE_BACKUP_CONSUMPTION,
            task_metadata={'backup_id': backup.id,
                           'email': email})
        consumption_workflow_root.add_next_task(consumption_task)
        workflow_task.root.add_callback_root(consumption_workflow_root)
        workflow_task.status = WorkflowTask.STATUS_SUCCESSFUL
        workflow_task.resource_id = backup.id
        db_session.add(consumption_workflow_root)
        db_session.commit()

        LOGGER.info(f"Backup successful of ID: {backup.id}")


@celery_app.task(name="update_vpc_metadata_for_instances_with_snapshot_references",
                 base=IBMWorkflowTasksBase, queue='disaster_recovery_queue')
def update_vpc_metadata_for_instances_with_snapshot_references(workflow_task_id):
    """
    Update VPC Backup Metadata for instances with snapshot references
    """
    with get_db_session() as db_session:
        workflow_task = db_session.query(WorkflowTask).filter_by(id=workflow_task_id).first()
        if not workflow_task:
            return

        workflow_task.status = WorkflowTask.STATUS_RUNNING
        db_session.commit()
        task_metadata = workflow_task.task_metadata
        backup_task_id = task_metadata["backup_task_id"]
        instances_snapshots_tasks_id = deepcopy(task_metadata["instances"])
        prev_backup_workflow_task = db_session.query(WorkflowTask).filter_by(id=backup_task_id).first()
        if not prev_backup_workflow_task:
            return

        backup_blueprint = db_session.query(DisasterRecoveryBackup).filter_by(
            id=prev_backup_workflow_task.resource_id).first()
        backup_metadata = deepcopy(backup_blueprint.backup_metadata)
        workspace_payload = deepcopy(backup_metadata["workspace_payload"])
        instances = deepcopy(workspace_payload["instances"])
        for instance in instances:
            # TODO add cloud filter
            resource_json = deepcopy(instance["resource_json"])
            instance_snapshot_task = instances_snapshots_tasks_id[instance["id"]]
            snapshot_workflow_task = db_session.query(WorkflowTask).filter_by(
                id=instance_snapshot_task["boot_volume_snapshot_task"]).first()
            if snapshot_workflow_task:
                boot_snapshot = db_session.query(IBMSnapshot).filter_by(id=snapshot_workflow_task.resource_id).first()
                if boot_snapshot:
                    resource_json["boot_volume_attachment"]["volume"]["source_snapshot"] = {"id": boot_snapshot.id}
            for volume_attachment in resource_json["volume_attachments"]:
                snapshot_task = db_session.query(WorkflowTask).filter_by(
                    id=instance_snapshot_task[volume_attachment["volume"]["name"]]).first()
                if snapshot_task:
                    volume_snapshot = db_session.query(IBMSnapshot).filter_by(id=snapshot_task.resource_id).first()
                    if volume_snapshot:
                        volume_attachment["volume"]["source_snapshot"] = {"id": volume_snapshot.id}
            instance["resource_json"] = deepcopy(resource_json)

        workspace_payload["instances"] = deepcopy(instances)
        backup_metadata["workspace_payload"] = deepcopy(workspace_payload)
        backup_blueprint.backup_metadata = deepcopy(backup_metadata)
        db_session.commit()
