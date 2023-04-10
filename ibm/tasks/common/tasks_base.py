import logging

from celery_singleton import Singleton

from ibm import get_db_session
from ibm.models import WorkflowTask

LOGGER = logging.getLogger(__name__)


class IBMWorkflowTasksBase(Singleton):
    def after_return(self, status, retval, task_id, args, kwargs, einfo):
        LOGGER.info('TASK FINISHED: {0.name}[{0.request.id}]'.format(self))

    def on_failure(self, exc, task_id, args, kwargs, einfo):
        LOGGER.error('{0!r} failed: {1!r}'.format(task_id, exc))
        with get_db_session() as db_session:
            db_session.rollback()
            db_session.commit()

            workflow_task = db_session.query(WorkflowTask).filter_by(id=args[0]).first()
            if not workflow_task:
                return

            workflow_task.status = WorkflowTask.STATUS_FAILED
            workflow_task.message = "Internal Server Error"
            db_session.commit()
