from datetime import timedelta

from celery import Celery
from celery.signals import worker_ready
from celery_singleton import clear_locks

from config import RedisConfig

broker = RedisConfig.REDIS_URL

celery_app = Celery(
    "vpcplus-ibm-celery",
    broker=broker,
    include=[
        "ibm.tasks.workflow_tasks",
        "ibm.tasks.ibm",
        "ibm.tasks.draas_tasks",
        "ibm.tasks.ttl_tasks",
        "ibm.tasks.consumption_tasks.consumption_tasks",
        "ibm.tasks.cost_per_tags_tasks",
        "ibm.tasks.cost_analyzer"
    ]
)

celery_app.conf.beat_schedule = {
    "run_workspace_manager": {
        "task": "workspace_manager",
        "schedule": 3.0,
    },
    "cloud_deletion_task": {
        "task": "delete_clouds_initiator",
        "schedule": timedelta(minutes=1),
        'options': {'queue': 'sync_queue'}
    },
    "delete_workflows_manager": {
        "task": "workflows_delete_task",
        "schedule": timedelta(hours=2),
        'options': {'queue': 'workflow_queue'}
    },
    "run_workflow_manager": {
        "task": "workflow_manager",
        "schedule": 3.0,
    },
    "run_ic_task_distributor": {
        "task": "ic_task_distributor",
        "schedule": 30,
    },
    "run_ic_instances_overseer": {
        "task": "ic_instances_overseer",
        "schedule": 40,
    },
    "run_ic_pending_task_executor": {
        "task": "ic_pending_task_executor",
        "schedule": 60,
    },
    "sync_ibm_clouds_with_mangos": {
        "task": "sync_ibm_clouds_with_mangos",
        "schedule": timedelta(minutes=2),
        'options': {'queue': 'sync_queue'}
    },
    "run_vpc_expiry_manager": {
        "task": "run_vpc_expiry_manager",
        "schedule": 60,
        "options": {'queue': 'ttl_manager_queue'}
    },
    "run_disaster_recovery_backups": {
        "task": "task_run_disaster_recovery_backups",
        "schedule": timedelta(minutes=1),
        'options': {'queue': 'disaster_recovery_queue'}
    },
    "run_post_consumption_stats": {
        "task": "update_cost_consumption_stats_task",
        "schedule": timedelta(minutes=30),
        "options": {'queue': 'consumption_queue'}
    },
    "run_cost_analyzer_task": {
        "task": "task_run_ibm_fetch_cost",
        "schedule": timedelta(hours=12),
        'options': {'queue': 'cost_analyzer_queue'}
    },

}


@worker_ready.connect
def unlock_all(**kwargs):
    clear_locks(celery_app)
