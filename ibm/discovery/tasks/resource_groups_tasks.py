import logging
from datetime import datetime

from ibm.discovery import get_db_session
from ibm.models import IBMCloud, IBMResourceGroup

LOGGER = logging.getLogger(__name__)


def update_resource_groups(cloud_id, ibm_resource_groups):
    if not ibm_resource_groups:
        return

    start_time = datetime.utcnow()
    resource_groups = list()
    resource_group_ids = list()
    for m_resource_groups in ibm_resource_groups:
        for m_resource_group in m_resource_groups.get("response", []):
            rg_obj = IBMResourceGroup.from_ibm_json_body(json_body=m_resource_group)
            resource_groups.append(rg_obj)
            resource_group_ids.append(rg_obj.resource_id)

    with get_db_session() as session:
        db_resource_groups = session.query(IBMResourceGroup).filter_by(cloud_id=cloud_id).all()

        for db_resource_group in db_resource_groups:
            if db_resource_group.resource_id not in resource_group_ids:
                LOGGER.error(
                    f"Deleting resource group {db_resource_group.name} and id: {db_resource_group.resource_id}")
                session.delete(db_resource_group)
                session.commit()
        db_cloud = session.query(IBMCloud).get(cloud_id)
        assert db_cloud

        for resource_group in resource_groups:
            db_resource_group = session.query(IBMResourceGroup).filter_by(
                cloud_id=cloud_id, resource_id=resource_group.resource_id).first()
            resource_group.dis_add_update_db(session, db_resource_group=db_resource_group, db_cloud=db_cloud)
        session.commit()

    LOGGER.info("** Resource Groups synced in:{}".format((datetime.utcnow() - start_time).total_seconds()))
