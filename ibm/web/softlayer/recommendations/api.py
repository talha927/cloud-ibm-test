import logging

from apiflask import abort, APIBlueprint, output

from ibm.auth import authenticate
from ibm.common.req_resp_schemas.schemas import WorkflowRootOutSchema
from ibm.models import SoftlayerCloud, WorkflowRoot, WorkflowTask
from ibm.web import db as ibmdb

LOGGER = logging.getLogger(__name__)

softlayer_recommendations = APIBlueprint('recommendations', __name__, tag="SoftLayerRecommendation")


@softlayer_recommendations.post('/recommendations/<softlayer_cloud_id>')
@authenticate
@output(WorkflowRootOutSchema, status_code=202)
def generate_softlayer_recommendations(softlayer_cloud_id, user):
    """
    Generate Softlayer recommendations based on Usage metrices
    This requests generates metrices for Softlayer Cloud for a given user
    """
    softlayer_cloud_account = ibmdb.session.query(SoftlayerCloud).filter_by(
        user_id=user["id"], project_id=user["project_id"], id=softlayer_cloud_id, status=SoftlayerCloud.STATUS_VALID
    ).first()
    if not softlayer_cloud_account:
        message = f"SoftlayerCloud: {softlayer_cloud_id} does not exist OR Not Valid"
        LOGGER.info(message)
        abort(404, message)

    workflow_root = WorkflowRoot(
        user_id=user["id"], project_id=user["project_id"], workflow_name="SoftLayerRecommendation",
        workflow_nature="CREATE")
    vs_discovery_task = WorkflowTask(
        task_type="SYNC", resource_type="SoftLayerVirtualGuest",
        task_metadata={'softlayer_cloud_id': softlayer_cloud_id})
    network_gateways_discovery_task = WorkflowTask(
        task_type="SYNC", resource_type="SoftLayerNetworkGateway",
        task_metadata={'softlayer_cloud_id': softlayer_cloud_id})
    generate_recommendations_task = WorkflowTask(
        task_type=WorkflowTask.TYPE_CREATE, resource_type="SoftLayerRecommendation",
        task_metadata={'softlayer_cloud_id': softlayer_cloud_id})
    workflow_root.add_next_task(vs_discovery_task)
    workflow_root.add_next_task(network_gateways_discovery_task)
    vs_discovery_task.add_next_task(generate_recommendations_task)
    network_gateways_discovery_task.add_next_task(generate_recommendations_task)
    ibmdb.session.add(workflow_root)
    ibmdb.session.commit()
    return workflow_root.to_json()
