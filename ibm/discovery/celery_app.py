from datetime import timedelta

from celery import Celery

from ibm.discovery.config import RedisConfigs


def create_celery_app():
    broker = RedisConfigs.REDIS_URL

    celery_app = Celery(
        "ibm_discovery",
        broker=broker,
        include=["ibm.discovery.tasks.discovery_tasks"]
    )

    celery_app.conf.beat_schedule = {
        'ibm_discovery_initiator': {
            'task': 'ibm_discovery_initiator',
            'schedule': timedelta(minutes=1),
            'options': {'queue': 'ibm_discovery_initiator_queue'}
        },
    }

    return celery_app
