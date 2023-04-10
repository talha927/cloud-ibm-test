import logging
import re
from datetime import datetime

from ibm.discovery import get_db_session
from ibm.discovery.common.consts import IBM_TAG_TO_RESOURCE_MAPPER
from ibm.discovery.common.utils import discovery_locked_resource
from ibm.models import IBMCloud, IBMResourceLog, IBMTag

LOGGER = logging.getLogger("tags_tasks.py")


def update_tags(cloud_id, m_tags):
    if not m_tags:
        return

    start_time = datetime.utcnow()

    tags, tags_set = list(), set()
    locked_rid_status = dict()
    for m_tag_list in m_tags:
        for m_tag in m_tag_list.get("response", []):
            if not m_tag.get('name'):
                continue

            tag = IBMTag.from_ibm_json_body(m_tag)
            crn = m_tag.get("crn")
            if not crn:
                LOGGER.info("CRN not found in tags discovery task")
                continue

            resource_type = re.search('::(.+?):', m_tag['crn'])

            tag.resource_type = resource_type.group(1) if resource_type else "None"
            model = IBM_TAG_TO_RESOURCE_MAPPER.get(tag.resource_type)

            resource_id = "None"
            if model:
                with get_db_session() as session:
                    resource = session.query(model).filter_by(crn=crn, cloud_id=cloud_id).first()
                    if not resource:
                        continue

                    resource_id = resource.id if resource else "None"
            tag.resource_id = resource_id
            tags.append(tag)
            tags_set.add(f"{tag.resource_id}-{tag.name}")

        with get_db_session() as session:
            last_synced_at = m_tag_list["last_synced_at"]

            logged_resource = discovery_locked_resource(
                session=session, resource_type=IBMTag.__name__, cloud_id=cloud_id,
                sync_start=last_synced_at)
            locked_rid_status.update(logged_resource)

    with get_db_session() as session:
        with session.no_autoflush:
            ibm_cloud = session.query(IBMCloud).filter_by(id=cloud_id).first()
            if not ibm_cloud:
                LOGGER.info(f"IBMCloud {cloud_id} not found")
                return

            db_tags = session.query(IBMTag).filter_by(cloud_id=cloud_id).all()
            for db_tag in db_tags:
                unique_tag_id = f"{db_tag.resource_id}-{db_tag.name}"
                if locked_rid_status.get(unique_tag_id) in [IBMResourceLog.STATUS_ADDED, IBMResourceLog.STATUS_UPDATED]:
                    continue

                if unique_tag_id not in tags_set:
                    session.delete(db_tag)

            session.commit()

            for tag in tags:
                unique_tag_id = f"{tag.resource_id}-{tag.name}"
                if locked_rid_status.get(unique_tag_id) in [IBMResourceLog.STATUS_DELETED,
                                                            IBMResourceLog.STATUS_UPDATED]:
                    continue

                db_tag = session.query(IBMTag).filter_by(
                    resource_crn=tag.resource_crn, name=tag.name).first()
                if db_tag:
                    continue

                tag.cloud_id = cloud_id
                session.add(tag)
                session.commit()
    LOGGER.info("** IBM Tags synced in: {}".format((datetime.utcnow() - start_time).total_seconds()))
