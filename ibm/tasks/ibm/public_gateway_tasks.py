import logging
from copy import deepcopy
from ibm_cloud_sdk_core import ApiException

from ibm import get_db_session
from ibm.common.clients.ibm_clients import FloatingIPsClient, PublicGatewaysClient
from ibm.common.utils import update_id_or_name_references
from ibm.models import IBMFloatingIP, IBMIdleResource, IBMPublicGateway, IBMRegion, IBMResourceGroup, IBMResourceLog, \
    IBMVpcNetwork, IBMZone, WorkflowTask, IBMResourceTracking
from ibm.tasks.celery_app import celery_app as celery
from ibm.tasks.common.tasks_base import IBMWorkflowTasksBase
from ibm.tasks.ibm.task_utils import load_previous_associated_resources
from ibm.web.ibm.public_gateways.schemas import IBMPublicGatewayResourceSchema
from ibm.web.resource_tracking.utils import create_resource_tracking_object

LOGGER = logging.getLogger(__name__)


@celery.task(name="create_public_gateway", base=IBMWorkflowTasksBase)
def create_public_gateway(workflow_task_id):
    """
    Create an IBM Public Gateway on IBM Cloud
    """
    with get_db_session() as db_session:
        workflow_task = db_session.query(WorkflowTask).filter_by(id=workflow_task_id).first()
        if not workflow_task:
            return

        workflow_task.status = WorkflowTask.STATUS_RUNNING
        db_session.commit()

        resource_data = deepcopy(workflow_task.task_metadata["resource_data"])
        resource_json = deepcopy(resource_data["resource_json"])
        cloud_id = resource_data["ibm_cloud"]["id"]
        region_id = resource_data["region"]["id"]

        region = db_session.query(IBMRegion).filter_by(id=region_id, cloud_id=cloud_id).first()
        if not region:
            workflow_task.status = WorkflowTask.STATUS_FAILED
            workflow_task.message = f"IBMRegion '{region_id}' not found"
            db_session.commit()
            LOGGER.info(workflow_task.message)
            return

        if region.ibm_status == IBMRegion.IBM_STATUS_UNAVAILABLE:
            workflow_task.status = WorkflowTask.STATUS_FAILED
            workflow_task.message = f"IBMRegion '{region.name}' unavailable"
            db_session.commit()
            LOGGER.info(workflow_task.message)
            return

        region_name = region.name
        previous_resources = load_previous_associated_resources(task=workflow_task, session=db_session)
        update_id_or_name_references(
            cloud_id=cloud_id, resource_json=resource_json, resource_schema=IBMPublicGatewayResourceSchema,
            db_session=db_session, previous_resources=previous_resources
        )

    try:
        client = PublicGatewaysClient(cloud_id=cloud_id, region=region_name)
        public_gateway_json = client.create_public_gateway(public_gateway_json=resource_json)
    except ApiException as ex:
        with get_db_session() as db_session:
            workflow_task = db_session.query(WorkflowTask).filter_by(id=workflow_task_id).first()
            if not workflow_task:
                return

            workflow_task.status = WorkflowTask.STATUS_FAILED
            workflow_task.message = f"Creation Failed. Reason: {str(ex.message)}"
            db_session.commit()

        LOGGER.info("Create Public Gateway failed with status code " + str(ex.code) + ": " + ex.message)
        return

    with get_db_session() as db_session:
        workflow_task = db_session.query(WorkflowTask).filter_by(id=workflow_task_id).first()
        if not workflow_task:
            return

        if public_gateway_json["status"] == IBMPublicGateway.STATUS_FAILED:
            workflow_task.status = WorkflowTask.STATUS_FAILED
            workflow_task.message = \
                f"IBM PublicGateway '{public_gateway_json['name']}' creation for cloud '{cloud_id}' failed on IBM Cloud"
            db_session.commit()
            LOGGER.info(workflow_task.message)
            return

        metadata = workflow_task.task_metadata.copy() if workflow_task.task_metadata else {}
        metadata["ibm_resource_id"] = public_gateway_json["id"]
        workflow_task.task_metadata = metadata

        workflow_task.status = WorkflowTask.STATUS_RUNNING_WAIT
        message = f"IBM Public Gateway '{public_gateway_json['name']}' creation for cloud '{cloud_id}' waiting"
        db_session.commit()
    LOGGER.info(message)


@celery.task(name="create_wait_public_gateway", base=IBMWorkflowTasksBase)
def create_wait_public_gateway(workflow_task_id):
    """
    Create an IBM Public Gateway on IBM Cloud
    """
    with get_db_session() as db_session:
        workflow_task = db_session.query(WorkflowTask).filter_by(id=workflow_task_id).first()
        if not workflow_task:
            return

        workflow_task.status = WorkflowTask.STATUS_RUNNING
        db_session.commit()

        resource_data = deepcopy(workflow_task.task_metadata["resource_data"])
        cloud_id = resource_data["ibm_cloud"]["id"]
        region_id = resource_data["region"]["id"]

        region = db_session.query(IBMRegion).filter_by(id=region_id, cloud_id=cloud_id).first()
        if not region:
            workflow_task.status = WorkflowTask.STATUS_FAILED
            workflow_task.message = f"IBMRegion '{region_id}' not found"
            db_session.commit()
            LOGGER.info(workflow_task.message)
            return

        if region.ibm_status == IBMRegion.IBM_STATUS_UNAVAILABLE:
            workflow_task.status = WorkflowTask.STATUS_FAILED
            workflow_task.message = f"IBMRegion '{region.name}' unavailable"
            db_session.commit()
            LOGGER.info(workflow_task.message)
            return

        region_name = region.name
        resource_id = workflow_task.task_metadata["ibm_resource_id"]

    try:
        client = PublicGatewaysClient(cloud_id=cloud_id, region=region_name)
        public_gateway_json = client.get_public_gateway(public_gateway_id=resource_id)
        if public_gateway_json["status"] == IBMPublicGateway.STATUS_AVAILABLE:
            floating_ip_client = FloatingIPsClient(cloud_id=cloud_id, region=region_name)
            floating_ip_json = floating_ip_client.get_floating_ip(
                floating_ip_id=public_gateway_json["floating_ip"]["id"])

    except ApiException as ex:
        with get_db_session() as db_session:
            workflow_task = db_session.query(WorkflowTask).filter_by(id=workflow_task_id).first()
            if not workflow_task:
                return

            workflow_task.status = WorkflowTask.STATUS_FAILED
            workflow_task.message = f"Creation Failed. Reason: {str(ex.message)}"
            db_session.commit()

        LOGGER.info(ex.message)
        return

    with get_db_session() as db_session:
        workflow_task = db_session.query(WorkflowTask).filter_by(id=workflow_task_id).first()
        if not workflow_task:
            return

        if public_gateway_json["status"] == IBMPublicGateway.STATUS_FAILED:
            workflow_task.status = WorkflowTask.STATUS_FAILED
            workflow_task.message = \
                f"IBM Public Gateway '{public_gateway_json['name']}' creation for cloud '{cloud_id}' failed on " \
                f"IBM Cloud"
            db_session.commit()
            LOGGER.info(workflow_task.message)
            return

        elif public_gateway_json["status"] == IBMPublicGateway.STATUS_PENDING:
            workflow_task.status = WorkflowTask.STATUS_RUNNING_WAIT
            LOGGER.info(f"IBM Public Gateway '{public_gateway_json['name']}' creation for cloud '{cloud_id}' waiting")
            db_session.commit()
            return

        with db_session.no_autoflush:
            floating_ip = \
                db_session.query(IBMFloatingIP).filter_by(
                    resource_id=public_gateway_json["floating_ip"]["id"], cloud_id=cloud_id
                ).first()
            if not floating_ip:
                fip_zone = \
                    db_session.query(IBMZone).filter_by(
                        name=floating_ip_json["zone"]["name"], cloud_id=cloud_id
                    ).first()

                fip_resource_group = \
                    db_session.query(IBMResourceGroup).filter_by(
                        resource_id=floating_ip_json["resource_group"]["id"], cloud_id=cloud_id
                    ).first()
                if not fip_resource_group:
                    fip_resource_group = \
                        IBMResourceGroup(
                            name=floating_ip_json["resource_group"]["name"],
                            resource_id=floating_ip_json["resource_group"]["id"]
                        )
                    fip_resource_group.ibm_cloud = fip_zone.ibm_cloud

                floating_ip = IBMFloatingIP.from_ibm_json_body(json_body=floating_ip_json)
                floating_ip.zone = fip_zone
                floating_ip.resource_group = fip_resource_group

            pgw_zone = \
                db_session.query(IBMZone).filter_by(
                    name=public_gateway_json["zone"]["name"], cloud_id=cloud_id
                ).first()

            pgw_resource_group = \
                db_session.query(IBMResourceGroup).filter_by(
                    resource_id=public_gateway_json["resource_group"]["id"], cloud_id=cloud_id
                ).first()
            if not pgw_resource_group:
                pgw_resource_group = \
                    IBMResourceGroup(
                        name=public_gateway_json["resource_group"]["name"],
                        resource_id=public_gateway_json["resource_group"]["id"]
                    )
                pgw_resource_group.ibm_cloud = pgw_zone.ibm_cloud

            pgw_vpc_network = \
                db_session.query(IBMVpcNetwork).filter_by(
                    resource_id=public_gateway_json["vpc"]["id"], cloud_id=cloud_id
                ).first()

            public_gateway = IBMPublicGateway.from_ibm_json_body(json_body=public_gateway_json)
            public_gateway.zone = pgw_zone
            public_gateway.floating_ip = floating_ip
            public_gateway.resource_group = pgw_resource_group
            public_gateway.vpc_network = pgw_vpc_network
            db_session.commit()

            public_gateway_json = public_gateway.to_json()
            public_gateway_json["created_at"] = str(public_gateway_json["created_at"])

            IBMResourceLog(
                resource_id=public_gateway.resource_id, region=public_gateway.zone.region,
                status=IBMResourceLog.STATUS_ADDED, resource_type=public_gateway.__class__.__name__,
                data=public_gateway_json)
        workflow_task.resource_id = public_gateway.id
        workflow_task.status = WorkflowTask.STATUS_SUCCESSFUL
        db_session.commit()

    LOGGER.info(f"IBM Public Gateway '{public_gateway_json['name']}' creation for cloud '{cloud_id}' successful")


@celery.task(name="delete_public_gateway", base=IBMWorkflowTasksBase)
def delete_public_gateway(workflow_task_id):
    """
    Delete an IBM Public Gateway on IBM Cloud
    """
    with get_db_session() as db_session:
        workflow_task: WorkflowTask = db_session.query(WorkflowTask).filter_by(id=workflow_task_id).first()
        if not workflow_task:
            return

        workflow_task.status = WorkflowTask.STATUS_RUNNING
        db_session.commit()

        public_gateway: IBMPublicGateway = db_session.query(IBMPublicGateway).filter_by(
            id=workflow_task.resource_id).first()
        if not public_gateway:
            workflow_task.status = WorkflowTask.STATUS_FAILED
            workflow_task.message = f"IBM Public Gateway '{workflow_task.resource_id}' not found"
            db_session.commit()
            LOGGER.info(workflow_task.message)
            return

        region_name = public_gateway.region.name
        public_gateway_resource_id = public_gateway.resource_id
        cloud_id = public_gateway.cloud_id

    try:
        client = PublicGatewaysClient(cloud_id, region=region_name)
        client.delete_public_gateway(public_gateway_id=public_gateway_resource_id)
        public_gateway_json = client.get_public_gateway(public_gateway_id=public_gateway_resource_id)

    except ApiException as ex:
        # IBM Public Gateway is deleted from IBM Cloud Console, but we still have it on VPC + side.
        with get_db_session() as db_session:
            workflow_task: WorkflowTask = db_session.query(WorkflowTask).filter_by(id=workflow_task_id).first()
            if not workflow_task:
                return

            if ex.code == 404:  # 404 means resource is not found on IBM Cloud.
                public_gateway: IBMPublicGateway = db_session.query(IBMPublicGateway).filter_by(
                    id=workflow_task.resource_id).first()
                if public_gateway:
                    public_gateway_json = public_gateway.to_json()
                    public_gateway_json["created_at"] = str(public_gateway_json["created_at"])

                    IBMResourceLog(
                        resource_id=public_gateway.resource_id, region=public_gateway.zone.region,
                        status=IBMResourceLog.STATUS_DELETED, resource_type=IBMPublicGateway.__name__,
                        data=public_gateway_json)

                    db_session.query(IBMIdleResource).filter_by(cloud_id=public_gateway.cloud_id,
                                                                db_resource_id=public_gateway.id).delete()

                    db_session.delete(public_gateway)

                workflow_task.status = WorkflowTask.STATUS_SUCCESSFUL
                LOGGER.info(
                    f"IBM Public Gateway {public_gateway_resource_id} for cloud {cloud_id} deletion successful.")
                db_session.commit()
                return
            else:
                workflow_task.status = WorkflowTask.STATUS_FAILED
                workflow_task.message = str(ex.message)
                db_session.commit()
                LOGGER.info(str(ex.message))
                return

    with get_db_session() as db_session:
        workflow_task: WorkflowTask = db_session.query(WorkflowTask).filter_by(id=workflow_task_id).first()
        if not workflow_task:
            return

        public_gateway_status = public_gateway_json["status"]
        public_gateway_name = public_gateway_json["name"]
        if public_gateway_status != IBMPublicGateway.STATUS_DELETING:
            message = f"IBM Public Gateway {public_gateway_name} for cloud {cloud_id} deletion failed"
            workflow_task.message = message
            workflow_task.status = WorkflowTask.STATUS_FAILED
            LOGGER.info(message)
            db_session.commit()
            return

        workflow_task.status = WorkflowTask.STATUS_RUNNING_WAIT
        message = f"IBM Public Gateway {public_gateway_name} for cloud {cloud_id} deletion waiting"
        db_session.commit()

    LOGGER.info(message)


@celery.task(name="delete_wait_public_gateway", base=IBMWorkflowTasksBase)
def delete_wait_public_gateway(workflow_task_id):
    """
    Wait task for Deletion of an IBM Public Gateway on IBM Cloud
    """
    with get_db_session() as db_session:
        workflow_task: WorkflowTask = db_session.query(WorkflowTask).filter_by(id=workflow_task_id).first()
        if not workflow_task:
            return

        workflow_task.status = WorkflowTask.STATUS_RUNNING
        db_session.commit()

        public_gateway: IBMPublicGateway = db_session.query(IBMPublicGateway).filter_by(
            id=workflow_task.resource_id).first()
        if not public_gateway:
            message = f"IBM Public Gateway '{workflow_task.resource_id}' not found"
            workflow_task.status = WorkflowTask.STATUS_FAILED
            workflow_task.message = message
            db_session.commit()
            LOGGER.info(message)
            return

        region_name = public_gateway.region.name
        public_gateway_resource_id = public_gateway.resource_id
        cloud_id = public_gateway.cloud_id

    try:
        client = PublicGatewaysClient(cloud_id, region=region_name)
        public_gateway_json = client.get_public_gateway(public_gateway_id=public_gateway_resource_id)

    except ApiException as ex:
        with get_db_session() as db_session:
            workflow_task: WorkflowTask = db_session.query(WorkflowTask).filter_by(id=workflow_task_id).first()
            if not workflow_task:
                return

            if ex.code == 404:  # 404 means resource is not found on IBM Cloud.
                public_gateway: IBMPublicGateway = db_session.query(IBMPublicGateway).filter_by(
                    id=workflow_task.resource_id).first()
                if public_gateway:
                    public_gateway_json = public_gateway.to_json()
                    public_gateway_json["created_at"] = str(public_gateway_json["created_at"])

                    IBMResourceLog(
                        resource_id=public_gateway.resource_id, region=public_gateway.zone.region,
                        status=IBMResourceLog.STATUS_DELETED, resource_type=IBMPublicGateway.__name__,
                        data=public_gateway_json)

                    # Adding resource to IBMResourceTracking
                    create_resource_tracking_object(db_resource=public_gateway, action_type=IBMResourceTracking.DELETED,
                                                    session=db_session)

                    db_session.delete(public_gateway)

                workflow_task.status = WorkflowTask.STATUS_SUCCESSFUL
                LOGGER.info(
                    f"IBM Public Gateway {public_gateway_resource_id} deletion successful.")
                db_session.commit()
                return
            else:
                workflow_task.status = WorkflowTask.STATUS_FAILED
                workflow_task.message = str(ex.message)
                db_session.commit()
                LOGGER.info(str(ex.message))
                return

    with get_db_session() as db_session:
        workflow_task: WorkflowTask = db_session.query(WorkflowTask).filter_by(id=workflow_task_id).first()
        if not workflow_task:
            return

        public_gateway_status = public_gateway_json["status"]
        public_gateway_name = public_gateway_json["name"]
        if public_gateway_status != IBMPublicGateway.STATUS_DELETING:
            message = f"IBM Public Gateway {public_gateway_name} for cloud {cloud_id} deletion failed"
            workflow_task.message = message
            workflow_task.status = WorkflowTask.STATUS_FAILED
            LOGGER.info(message)
            db_session.commit()
            return

        workflow_task.status = WorkflowTask.STATUS_RUNNING_WAIT
        message = f"IBM Public Gateway {public_gateway_name} for cloud {cloud_id} deletion waiting"
        db_session.commit()

    LOGGER.info(message)
