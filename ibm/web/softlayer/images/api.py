import logging

from apiflask import abort, APIBlueprint, output

from ibm.auth import authenticate
from ibm.common.req_resp_schemas.schemas import WorkflowRootOutSchema
from ibm.models import IBMRegion, SoftlayerCloud
from ibm.web import db as ibmdb
from ibm.web.common.utils import compose_ibm_sync_resource_workflow

LOGGER = logging.getLogger(__name__)

softlayer_images = APIBlueprint('softlayer_images', __name__, tag="SoftLayerImage")


@softlayer_images.post("/<account_id>/<region_id>/images/sync")
@authenticate
@output(WorkflowRootOutSchema, status_code=202)
def sync_softlayer_images(account_id, region_id, user):
    """
    Create a sync task for softlayer Images
    This request creates a workflow task syncing Softlayer Images
    """
    region = ibmdb.session.query(IBMRegion).filter_by(id=region_id).first()
    if not region:
        message = f"IBM Region {region_id} does not exist"
        LOGGER.debug(message)
        abort(404, message)
    if region.ibm_status != IBMRegion.IBM_STATUS_AVAILABLE:
        message = f"IBM Region {region_id} status {region.status}"
        LOGGER.debug(message)
        abort(404, message)
    softlayer_cloud_account = ibmdb.session.query(SoftlayerCloud).filter_by(
        user_id=user["id"], project_id=user["project_id"], id=account_id, status=SoftlayerCloud.STATUS_VALID
    ).first()
    if not softlayer_cloud_account:
        message = f"SoftlayerCloud: {account_id} does not exist OR Not Valid"
        LOGGER.info(message)
        abort(404, message)
    data = {"account_id": account_id, "region_id": region_id}
    workflow_root = compose_ibm_sync_resource_workflow(user=user, resource_type="SoftLayerImage", data=data)
    return workflow_root.to_json()
