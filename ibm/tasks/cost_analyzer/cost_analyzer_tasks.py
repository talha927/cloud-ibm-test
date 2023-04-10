from datetime import datetime

from ibm_cloud_sdk_core import ApiException

from ibm import get_db_session, LOGGER
from ibm.common.clients.ibm_clients import CostClient
from ibm.common.consts import BILLING_MONTH_FORMAT
from ibm.models import IBMCloud, IBMCost, WorkflowRoot, WorkflowTask
from ibm.tasks.celery_app import celery_app as celery
from .utils import update_cost, get_cost_billing_month
from ...common.clients.ibm_clients.exceptions import IBMAuthError, IBMConnectError, IBMExecuteError, \
    IBMInvalidRequestError


@celery.task(name="task_run_ibm_fetch_cost", queue='const_analyzer_queue')
def task_run_ibm_fetch_cost():
    with get_db_session() as db_session:
        ibm_clouds = db_session.query(IBMCloud).filter_by(status="VALID", added_in_mangos=True, deleted=False).all()
        for ibm_cloud in ibm_clouds:
            cloud_settings = ibm_cloud.settings
            if not (cloud_settings and cloud_settings.cost_optimization_enabled):
                continue
            cloud_workflow_root = WorkflowRoot(
                user_id=ibm_cloud.user_id,
                project_id=ibm_cloud.project_id,
                workflow_name=f"{IBMCloud.__name__} ({ibm_cloud.name})",
                workflow_nature="FETCH COST"
            )
            fetch_cost_task = WorkflowTask(
                task_type=WorkflowTask.TYPE_FETCH_COST, resource_type=IBMCloud.__name__,
                task_metadata={"cloud_id": ibm_cloud.id}
            )
            cloud_workflow_root.add_next_task(fetch_cost_task)
            db_session.add(cloud_workflow_root)

        db_session.commit()


@celery.task(name="fetch_ibm_cloud_cost")
def fetch_ibm_cloud_cost(workflow_task_id):
    with get_db_session() as db_session:
        workflow_task = db_session.query(WorkflowTask).filter_by(id=workflow_task_id).first()
        if not workflow_task:
            return
        workflow_task.status = WorkflowTask.STATUS_RUNNING
        db_session.commit()
        cloud_id = workflow_task.task_metadata["cloud_id"]
        ibm_cloud = db_session.query(IBMCloud).filter_by(id=cloud_id).first()
        if not ibm_cloud:
            workflow_task.status = WorkflowTask.STATUS_FAILED
            workflow_task.message = f"IBMCloud '{cloud_id}' not found"
            db_session.commit()
            LOGGER.error(workflow_task.message)
            return
    try:
        cost_client = CostClient(cloud_id=ibm_cloud.id)
        billing_month_list = get_cost_billing_month()
        curr_month = billing_month_list[-1]
        prev_month = billing_month_list[-2]

        for billing_month in billing_month_list:
            billing_month_formatted = datetime.strptime(billing_month, BILLING_MONTH_FORMAT)
            monthly_cost_obj = db_session.query(IBMCost).filter_by(cloud_id=ibm_cloud.id,
                                                                   billing_month=billing_month_formatted).first()

            if monthly_cost_obj is not None and (billing_month != curr_month and billing_month != prev_month):
                continue
            response_dict = cost_client.list_cost_and_usages(ibm_api_key=ibm_cloud.api_key,
                                                             ibm_account_id=ibm_cloud.account_id,
                                                             billing_month=billing_month)
            update_cost(cloud_id=ibm_cloud.id, m_ibm_cost=response_dict)
    except (IBMAuthError, IBMConnectError, IBMExecuteError, IBMInvalidRequestError, ApiException) as ex:
        with get_db_session() as db_session:
            workflow_task = db_session.query(WorkflowTask).filter_by(id=workflow_task_id).first()
            if not workflow_task:
                return
            workflow_task.status = WorkflowTask.STATUS_FAILED
            workflow_task.message = f"Cost fetch Failed. Reason: {str(ex)}"
            db_session.commit()
            LOGGER.error(workflow_task.message)
            return
    with get_db_session() as db_session:
        workflow_task = db_session.query(WorkflowTask).filter_by(id=workflow_task_id).first()
        if not workflow_task:
            return

        workflow_task.status = WorkflowTask.STATUS_SUCCESSFUL
        db_session.commit()
        LOGGER.info(f"Cost for IBM Cloud {cloud_id} fetched successfully")
