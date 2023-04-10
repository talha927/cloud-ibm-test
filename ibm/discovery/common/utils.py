import logging

from ibm.models import IBMResourceLog

LOGGER = logging.getLogger(__name__)


def discovery_locked_resource(session, resource_type, cloud_id, sync_start, region=None):
    region_id = region.id if region else None

    locked_resources = session.query(IBMResourceLog).filter(
        IBMResourceLog.cloud_id == cloud_id, IBMResourceLog.region_id == region_id,
        IBMResourceLog.resource_type == resource_type, IBMResourceLog.performed_at >= sync_start).order_by(
        IBMResourceLog.performed_at.asc()).all()

    locked_rid_status = {locked_resource.resource_id: locked_resource.status for locked_resource in locked_resources}

    return locked_rid_status
