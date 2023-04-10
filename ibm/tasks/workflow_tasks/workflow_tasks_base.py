import logging

from celery_singleton import Singleton

from ibm import get_db_session
from ibm.models import WorkflowRoot

LOGGER = logging.getLogger(__name__)


class WorkflowTasksBase(Singleton):
    def after_return(self, status, retval, task_id, args, kwargs, einfo):
        LOGGER.info('TASK FINISHED: {0.name}[{0.request.id}]'.format(self))

    def on_failure(self, exc, task_id, args, kwargs, einfo):
        LOGGER.error('{0!r} failed: {1!r}'.format(task_id, exc))
        with get_db_session() as db_session:
            workflow_root = db_session.query(WorkflowRoot).filter_by(id=args[0]).first()
            if not workflow_root:
                return

            workflow_root.executor_running = False
            workflow_root.status = WorkflowRoot.STATUS_C_W_FAILURE
            db_session.commit()
