import logging
from datetime import datetime

from ibm import get_db_session
from ibm.models import IBMVpcNetwork, TTLInterval
from ibm.tasks.celery_app import celery_app as celery
from ibm.web.common.utils import compose_ibm_vpc_deletion_workflow

LOGGER = logging.getLogger(__name__)


@celery.task(name="run_vpc_expiry_manager")
def run_vpc_expiry_manager():
    """
    This method periodically polls the DB to query the expired VPCs, and if the VPC is found to be expired,
    it executes another job of sequential deletion for that VPC.
    """
    with get_db_session() as db_session:
        expired_ttls = db_session.query(TTLInterval).filter(TTLInterval.expires_at <= datetime.now()).all()
        for expired_ttl in expired_ttls:
            expired_vpc = expired_ttl.vpc_network
            cloud = expired_vpc.ibm_cloud
            user = {
                'id': cloud.user_id,
                'project_id': cloud.project_id
            }
            LOGGER.info(f"TTL expired for VPC with ID {expired_vpc.id}")
            compose_ibm_vpc_deletion_workflow(
                user=user, resource_type=IBMVpcNetwork, resource_id=expired_vpc.id, db_session=db_session)
