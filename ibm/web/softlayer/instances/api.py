import logging
from apiflask import abort, APIBlueprint, input, output
from copy import deepcopy

from ibm.auth import authenticate
from ibm.common.req_resp_schemas.schemas import WorkflowRootOutSchema
from ibm.models import IBMRegion, SoftlayerCloud, WorkflowRoot, WorkflowTask, IBMInstance, IBMCloud
from ibm.web import db as ibmdb
from ibm.web.common.utils import compose_ibm_sync_resource_workflow
from ibm.web.softlayer.instances.schemas import IBMInstancesInSchema, OnlyVMWareInSchema

LOGGER = logging.getLogger(__name__)

softlayer_instances = APIBlueprint('softlayer_instances', __name__, tag="SoftLayerInstance")


@softlayer_instances.post("<account_id>/instances/sync")
@authenticate
@input(IBMInstancesInSchema)
@output(WorkflowRootOutSchema, status_code=202)
def sync_softlayer_instances(account_id, data, user):
    """
    Create a sync task for softlayer Instances
    This request creates a workflow task syncing Softlayer Instances
    """
    region_id = data.get("region_id")
    if region_id:
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
    if region_id:
        task_data = {"account_id": account_id, "region_id": region_id}
    else:
        task_data = {"account_id": account_id}
    workflow_root = compose_ibm_sync_resource_workflow(user=user, resource_type="SoftLayerInstances", data=task_data)
    return workflow_root.to_json()


@softlayer_instances.post("/<account_id>/instances/<instance_id>/sync")
@authenticate
@input(IBMInstancesInSchema)
@output(WorkflowRootOutSchema, status_code=202)
def sync_softlayer_instance(account_id, instance_id, data, user):
    """
    Create a sync task for softlayer Instance provided ID
    This request creates a workflow task syncing Softlayer Instance
    """
    region_id = data.get("region_id")
    if region_id:
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
    if region_id:
        task_data = {"account_id": account_id, "region_id": region_id, "instance_id": instance_id}
    else:
        task_data = {"account_id": account_id, "instance_id": instance_id}
    workflow_root = compose_ibm_sync_resource_workflow(user=user, resource_type="SoftLayerInstance", data=task_data)
    return workflow_root.to_json()


@softlayer_instances.post("/instances/classic_to_vmware")
@authenticate
@input(OnlyVMWareInSchema)
def softlayer_instance_classic_to_vmware(data, user):
    """
    Create snapshot task and export task softlayer Instances
    This request creates a workflow task export snapshot Softlayer Instances
    """
    ibm_cloud = ibmdb.session.query(IBMCloud).filter_by(
        id=data["cloud_id"], user_id=user["id"], project_id=user["project_id"], deleted=False).first()
    if not ibm_cloud:
        message = f"No IBM Cloud with ID {data['cloud_id']} found for the user"
        LOGGER.debug(message)
        abort(404, message)

    region = ibmdb.session.query(IBMRegion).filter_by(
        name=data['region'], ibm_status=IBMRegion.IBM_STATUS_AVAILABLE, cloud_id=ibm_cloud.id).first()
    if not region:
        message = f"IBM Region {data['region']} does not exist"
        LOGGER.debug(message)
        abort(404, message)

    migration_json_dict = deepcopy(data)
    migration_json_dict.pop("cloud_id")
    migration_json_dict.pop("region")
    migration_json_dict["migrate_from"] = "CLASSIC_VSI"

    fe_request_dict = {
        "cloud_id": data['cloud_id'],
        "region": data["region"],
        "migration_json": migration_json_dict
    }

    resource_data_dict = {
        "ibm_cloud": {"id": data["cloud_id"]},
        "region": {"id": region.id},
        "migration_json": migration_json_dict
    }

    workflow_root = WorkflowRoot(
        user_id=user["id"], project_id=user["project_id"], workflow_name="classic_to_vmware", workflow_nature="CREATE",
        fe_request_data=fe_request_dict
    )
    snapshot_task = WorkflowTask(
        task_type=WorkflowTask.TYPE_SNAPSHOT, resource_type=IBMInstance.__name__,
        task_metadata={"resource_data": resource_data_dict}
    )
    export_task = WorkflowTask(
        task_type=WorkflowTask.TYPE_EXPORT, resource_type=IBMInstance.__name__,
        task_metadata={"resource_data": resource_data_dict}
    )
    workflow_root.add_next_task(snapshot_task)
    snapshot_task.add_next_task(export_task)
    ibmdb.session.add(workflow_root)
    ibmdb.session.commit()
    return workflow_root.to_json()
