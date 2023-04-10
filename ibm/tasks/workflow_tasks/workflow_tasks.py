"""
This file contains tasks for Workflows
"""
from datetime import datetime, timedelta

from celery_singleton import Singleton

from ibm import get_db_session, LOGGER
from ibm.models import WorkflowRoot, WorkflowTask
from ibm.tasks.celery_app import celery_app as celery
from ibm.tasks.tasks_mapper import MAPPER
from ibm.tasks.workflow_tasks.workflow_tasks_base import WorkflowTasksBase


@celery.task(name="workflow_manager", queue="workflow_queue", base=Singleton)
def workflow_manager():
    """
    Manage workflows
    """
    with get_db_session() as db_session:
        workflow_roots = db_session.query(WorkflowRoot).filter(
            ~WorkflowRoot.executor_running,
            WorkflowRoot.status.in_(
                (
                    WorkflowRoot.STATUS_PENDING,
                    WorkflowRoot.STATUS_RUNNING,
                    WorkflowRoot.STATUS_C_SUCCESSFULLY_WFC,
                    WorkflowRoot.STATUS_C_W_FAILURE_WFC
                )
            )
        ).all()

        for workflow_root in workflow_roots:
            if workflow_root.status == WorkflowRoot.STATUS_PENDING:
                workflow_root.status = WorkflowRoot.STATUS_INITIATED
                db_session.commit()

            workflow_executor.delay(workflow_root.id)


@celery.task(name="workflow_executor", base=WorkflowTasksBase, queue="workflow_initiator_queue")
def workflow_executor(workflow_root_id):
    """
    :param workflow_root_id:
    :return:
    """
    with get_db_session() as db_session:
        workflow_root = db_session.query(WorkflowRoot).filter_by(id=workflow_root_id).first()
        if not workflow_root:
            LOGGER.error("Workflow Root ID: {} not found".format(workflow_root_id))
            return

        workflow_root.executor_running = True
        db_session.commit()

        running_tasks_count = 0

        if workflow_root.status == WorkflowRoot.STATUS_INITIATED:
            workflow_root.status = WorkflowRoot.STATUS_RUNNING
            db_session.commit()

            for task in workflow_root.next_tasks:
                task.status = WorkflowTask.STATUS_INITIATED
                task.in_focus = True
                db_session.commit()

                try:
                    run_func = MAPPER[task.resource_type][task.task_type]["RUN"]
                except KeyError as ex:
                    task.status = WorkflowTask.STATUS_FAILED
                    LOGGER.error("Task {task_type} for {resource_type} ill defined. Error: {error}".format(
                        task_type=task.task_type, resource_type=task.resource_type, error=str(ex)))
                    task.message = "Internal Error: Task not defined properly"
                    continue

                if not run_func:
                    task.status = WorkflowTask.STATUS_FAILED
                    LOGGER.error("Task {task_type} for {resource_type} does not have a 'RUN' function defined".format(
                        task_type=task.task_type, resource_type=task.resource_type))
                    task.message = "Internal Error: Run function not defined"
                    db_session.commit()
                    continue

                run_func.delay(task.id)
                running_tasks_count += 1
        elif workflow_root.status == WorkflowRoot.STATUS_RUNNING:
            iteration_tasks = workflow_root.in_focus_tasks
            for task in iteration_tasks:
                # This condition will only run for tasks which are appended to the task_ids from
                #  STATUS_C_SUCCESSFULLY case
                if task.status == WorkflowTask.STATUS_PENDING:
                    if task.previous_tasks.filter_by(status=WorkflowTask.STATUS_SUCCESSFUL).count() \
                            != task.previous_tasks.count():
                        continue

                    task.status = WorkflowTask.STATUS_INITIATED
                    task.in_focus = True
                    db_session.commit()

                    try:
                        run_func = MAPPER[task.resource_type][task.task_type]["RUN"]
                    except KeyError as ex:
                        task.status = WorkflowTask.STATUS_FAILED
                        LOGGER.error("Task {task_type} for {resource_type} ill defined. Error: {error}".format(
                            task_type=task.task_type, resource_type=task.resource_type, error=str(ex)))
                        task.message = "Internal Error: Task not defined properly"
                        continue

                    if not run_func:
                        task.status = WorkflowTask.STATUS_FAILED
                        LOGGER.error(
                            "Task {task_type} for {resource_type} does not have a 'RUN' function defined".format(
                                task_type=task.task_type, resource_type=task.resource_type))
                        task.message = "Internal Error: Run function not defined"
                        db_session.commit()
                        continue

                    run_func.delay(task.id)
                    running_tasks_count += 1

                # If not yet picked by worker or If picked by worker and still in running state
                elif task.status in [
                    WorkflowTask.STATUS_INITIATED, WorkflowTask.STATUS_RUNNING_WAIT_INITIATED,
                    WorkflowTask.STATUS_RUNNING
                ]:
                    running_tasks_count += 1

                # If picked by worker and completed running it but task needs to wait for poll
                #  (because it was long running)
                elif task.status == WorkflowTask.STATUS_RUNNING_WAIT:
                    try:
                        wait_func = MAPPER[task.resource_type][task.task_type]["WAIT"]
                    except KeyError as ex:
                        task.status = WorkflowTask.STATUS_FAILED
                        LOGGER.error("Task {task_type} for {resource_type} ill defined. Error: {error}".format(
                            task_type=task.task_type, resource_type=task.resource_type, error=str(ex)))
                        task.message = "Internal Error: Task not defined properly"
                        continue

                    if not wait_func:
                        task.status = WorkflowTask.STATUS_FAILED
                        task.message = "Internal Error: Wait function not defined"
                        db_session.commit()
                        continue

                    task.status = WorkflowTask.STATUS_RUNNING_WAIT_INITIATED
                    db_session.commit()
                    wait_func.delay(task.id)
                    running_tasks_count += 1

                # If picked by worker, completed and was successful
                elif task.status == WorkflowTask.STATUS_SUCCESSFUL:
                    task.in_focus = False
                    db_session.commit()

                    iteration_task_ids = [iteration_task.id for iteration_task in iteration_tasks]
                    for next_task in task.next_tasks.all():
                        if next_task.id not in iteration_task_ids:
                            iteration_tasks.append(next_task)

        if workflow_root.status == WorkflowRoot.STATUS_RUNNING and not running_tasks_count:
            if workflow_root.associated_tasks.filter(WorkflowTask.status == WorkflowTask.STATUS_FAILED).count():
                on_success_callbacks = workflow_root.callback_roots.filter_by(
                    root_type=WorkflowRoot.ROOT_TYPE_ON_SUCCESS).all()
                for on_success_callback in on_success_callbacks:
                    db_session.delete(on_success_callback)

                workflow_root.status = WorkflowRoot.STATUS_C_W_FAILURE_WFC \
                    if workflow_root.status_holding_callbacks_count else WorkflowRoot.STATUS_C_W_FAILURE
            else:
                on_failure_callbacks = workflow_root.callback_roots.filter_by(
                    root_type=WorkflowRoot.ROOT_TYPE_ON_FAILURE).all()
                for on_failure_callback in on_failure_callbacks:
                    db_session.delete(on_failure_callback)

                workflow_root.status = WorkflowRoot.STATUS_C_SUCCESSFULLY_WFC \
                    if workflow_root.status_holding_callbacks_count else WorkflowRoot.STATUS_C_SUCCESSFULLY

            db_session.commit()
            on_hold_callback_roots = \
                workflow_root.callback_roots.filter(WorkflowRoot.status == WorkflowRoot.STATUS_ON_HOLD).all()
            for on_hold_callback_root in on_hold_callback_roots:
                on_hold_callback_root.status = WorkflowRoot.STATUS_PENDING

        elif workflow_root.status == WorkflowRoot.STATUS_C_SUCCESSFULLY_WFC and \
                not workflow_root.status_holding_callbacks_count:
            workflow_root.status = WorkflowRoot.STATUS_C_SUCCESSFULLY

        elif workflow_root.status == WorkflowRoot.STATUS_C_W_FAILURE_WFC and \
                not workflow_root.status_holding_callbacks_count:
            workflow_root.status = WorkflowRoot.STATUS_C_W_FAILURE

        workflow_root.executor_running = False
        db_session.commit()


@celery.task(name="workflows_delete_task", queue="workflow_queue")
def workflows_delete_task():
    """
    Delete workflow roots, tasks and tree mappings that are 1 week old.
    """
    with get_db_session() as db_session:
        workflow_roots = db_session.query(WorkflowRoot).filter(
            ~WorkflowRoot.executor_running,
            WorkflowRoot.status.in_(
                (
                    WorkflowRoot.STATUS_C_W_FAILURE_WFC,
                    WorkflowRoot.STATUS_C_W_FAILURE,
                    WorkflowRoot.STATUS_C_SUCCESSFULLY_WFC,
                    WorkflowRoot.STATUS_C_SUCCESSFULLY,
                    WorkflowRoot.STATUS_PENDING,
                )
            ),
            WorkflowRoot.created_at < (datetime.now() - timedelta(days=7))
        ).all()
        for workflow_root in workflow_roots:
            if workflow_root.workspace:
                continue

            db_session.delete(workflow_root)

        db_session.commit()

        workflow_roots = db_session.query(WorkflowRoot).filter(
            WorkflowRoot.workflow_nature.in_(
                (
                    "SYNC", "DELETE", "ADD", "DETACH"
                )
            ),
            WorkflowRoot.created_at < (datetime.now() - timedelta(hours=2))
        ).all()

        for workflow_root in workflow_roots:
            if workflow_root.workspace:
                continue
            db_session.delete(workflow_root)

        db_session.commit()
