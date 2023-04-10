"""
This file contains tasks for Workspaces
"""
import logging

from ibm import get_db_session
from ibm.models import WorkflowRoot
from ibm.models.workflow.workflow_models import WorkflowsWorkspace
from ibm.tasks.celery_app import celery_app as celery
from ibm.tasks.workflow_tasks.workflow_tasks_base import WorkflowTasksBase

LOGGER = logging.getLogger(__name__)


@celery.task(name="workspace_manager", queue="workspace_queue")
def workspace_manager():
    """
    Manage workspaces
    """
    with get_db_session() as db_session:
        workflows_workspaces = db_session.query(WorkflowsWorkspace).filter(
            ~WorkflowsWorkspace.executor_running,
            WorkflowsWorkspace.status.in_(
                (
                    WorkflowsWorkspace.STATUS_PENDING,
                    WorkflowsWorkspace.STATUS_RUNNING,
                    WorkflowsWorkspace.STATUS_ON_HOLD_WITH_SUCCESS
                )
            )
        ).all()

        for workflows_workspace in workflows_workspaces:
            if workflows_workspace.status == WorkflowsWorkspace.STATUS_PENDING:
                workflows_workspace.status = WorkflowsWorkspace.STATUS_INITIATED
                db_session.commit()

            workspace_executor.delay(workflows_workspace.id)


@celery.task(name="workspace_executor", base=WorkflowTasksBase, queue="workspace_initiator_queue")
def workspace_executor(workflows_workspace_id):
    """
    :param workflows_workspace_id:
    :return:
    """
    with get_db_session() as db_session:
        workflows_workspace: WorkflowsWorkspace = db_session.query(WorkflowsWorkspace).filter_by(
            id=workflows_workspace_id
        ).first()
        if not workflows_workspace:
            LOGGER.debug("Workflows Workspace ID: {} not found".format(workflows_workspace_id))
            return

        workflows_workspace.executor_running = True
        db_session.commit()

        running_roots_count = 0

        if workflows_workspace.status in [WorkflowsWorkspace.STATUS_INITIATED,
                                          WorkflowsWorkspace.STATUS_ON_HOLD_WITH_SUCCESS]:
            workflows_workspace.status = WorkflowsWorkspace.STATUS_RUNNING
            db_session.commit()

            for workflow_root in workflows_workspace.associated_roots.filter(
                    WorkflowRoot.status.in_((
                            WorkflowRoot.STATUS_READY,
                    ))).all():
                if not workflow_root.is_provisionable:
                    continue

                workflow_root.status = WorkflowRoot.STATUS_PENDING
                workflow_root.in_focus = True
                db_session.commit()
                running_roots_count += 1

        elif workflows_workspace.status == WorkflowsWorkspace.STATUS_RUNNING:
            iteration_roots = workflows_workspace.in_focus_roots
            for workflow_root in iteration_roots:
                # This condition will only run for tasks which are appended to the task_ids from
                #  STATUS_C_SUCCESSFULLY case
                if workflow_root.status == WorkflowRoot.STATUS_READY:
                    if workflow_root.previous_roots.filter_by(status=WorkflowRoot.STATUS_C_SUCCESSFULLY).count() \
                            != workflow_root.previous_roots.count():
                        continue

                    workflow_root.status = WorkflowRoot.STATUS_PENDING
                    workflow_root.in_focus = True
                    db_session.commit()
                    running_roots_count += 1

                # If not yet picked by worker or If picked by worker and still in running state
                elif workflow_root.status in [
                    WorkflowRoot.STATUS_INITIATED, WorkflowRoot.STATUS_RUNNING, WorkflowRoot.STATUS_PENDING
                ]:
                    running_roots_count += 1

                # If picked by worker, completed and was successful
                elif workflow_root.status == WorkflowRoot.STATUS_C_SUCCESSFULLY:
                    workflow_root.in_focus = False
                    db_session.commit()

                    iteration_root_ids = [iteration_root.id for iteration_root in iteration_roots]
                    for next_root in workflow_root.next_roots.all():
                        if next_root.id not in iteration_root_ids:
                            iteration_roots.append(next_root)
        if workflows_workspace.status == WorkflowsWorkspace.STATUS_RUNNING and not running_roots_count:
            if workflows_workspace.associated_roots.filter(
                    WorkflowRoot.status == WorkflowRoot.STATUS_C_W_FAILURE
            ).count():
                workflows_workspace.status = WorkflowsWorkspace.STATUS_ON_HOLD_WITH_FAILURE
            elif workflows_workspace.associated_roots.filter(
                    WorkflowRoot.status == WorkflowRoot.STATUS_ON_HOLD
            ).count():
                workflows_workspace.status = WorkflowsWorkspace.STATUS_ON_HOLD_WITH_SUCCESS
            else:
                workflows_workspace.status = WorkflowsWorkspace.STATUS_C_SUCCESSFULLY

            db_session.commit()
        workflows_workspace.executor_running = False

        db_session.commit()
