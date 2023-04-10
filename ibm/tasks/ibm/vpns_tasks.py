import logging
from copy import deepcopy
from ibm_cloud_sdk_core import ApiException

from ibm import get_db_session
from ibm.common.clients.ibm_clients import VPNsClient
from ibm.common.utils import update_id_or_name_references
from ibm.models import IBMIdleResource, IBMIKEPolicy, IBMIPSecPolicy, IBMRegion, IBMResourceGroup, IBMResourceLog, \
    IBMResourceTracking, IBMSubnet, IBMVpnConnection, IBMVpnGateway, WorkflowTask
from ibm.tasks.celery_app import celery_app as celery
from ibm.tasks.common.tasks_base import IBMWorkflowTasksBase
from ibm.tasks.ibm.task_utils import load_previous_associated_resources
from ibm.web.ibm.vpn_gateways.schemas import IBMVpnGatewayConnectionInSchema, IBMVpnGatewayConnectionsResourceSchema, \
    IBMVpnGatewayInSchema, IBMVpnGatewaysResourceSchema
from ibm.web.resource_tracking.utils import create_resource_tracking_object

LOGGER = logging.getLogger(__name__)


@celery.task(name="create_vpn", base=IBMWorkflowTasksBase)
def create_vpn_gateway(workflow_task_id):
    """
    Create an IBM VPN on IBM Cloud
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
        resource_json.pop('connections', None)

        previous_resources = load_previous_associated_resources(task=workflow_task, session=db_session)
        update_id_or_name_references(
            cloud_id=cloud_id, resource_json=resource_data, resource_schema=IBMVpnGatewayInSchema,
            db_session=db_session, previous_resources=previous_resources
        )

        update_id_or_name_references(
            cloud_id=cloud_id, resource_json=resource_json, resource_schema=IBMVpnGatewaysResourceSchema,
            db_session=db_session, previous_resources=previous_resources
        )

    try:
        client = VPNsClient(cloud_id=cloud_id, region=region_name)
        vpn_json = client.create_vpn_gateway(vpn_gateway_json=resource_json)
    except ApiException as ex:
        with get_db_session() as db_session:
            workflow_task = db_session.query(WorkflowTask).filter_by(id=workflow_task_id).first()
            if not workflow_task:
                return

            workflow_task.status = WorkflowTask.STATUS_FAILED
            workflow_task.message = f"Creation Failed. Reason: {str(ex.message)}"
            db_session.commit()

        LOGGER.info("Create VPN Gateway failed with status code " + str(ex.code) + ": " + ex.message)
        return

    with get_db_session() as db_session:
        workflow_task = db_session.query(WorkflowTask).filter_by(id=workflow_task_id).first()
        if not workflow_task:
            return

        vpn_status = vpn_json["status"]
        vpn_name = vpn_json["name"]
        vpn_resource_id = vpn_json["id"]
        if vpn_status in [IBMVpnGateway.STATUS_AVAILABLE, IBMVpnGateway.STATUS_PENDING]:
            metadata = workflow_task.task_metadata.copy() if workflow_task.task_metadata else {}
            metadata["ibm_resource_id"] = vpn_resource_id
            workflow_task.task_metadata = metadata

            workflow_task.status = WorkflowTask.STATUS_RUNNING_WAIT
            message = f"IBM Vpn Gateway {vpn_name} for cloud {cloud_id} creation waiting"
        else:
            message = f"IBM Vpn Gateway {vpn_name} for cloud {cloud_id} creation failed"
            workflow_task.message = message
            workflow_task.status = WorkflowTask.STATUS_FAILED
        db_session.commit()
    LOGGER.info(message)


@celery.task(name="create_wait_vpn", base=IBMWorkflowTasksBase)
def create_wait_vpn_gateway(workflow_task_id):
    """
    Create an IBM Vpn on IBM Cloud
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
        client = VPNsClient(cloud_id=cloud_id, region=region_name)
        vpn_json = client.get_vpn_gateway(vpn_gateway_id=resource_id)
    except ApiException as ex:
        with get_db_session() as db_session:
            workflow_task = db_session.query(WorkflowTask).filter_by(id=workflow_task_id).first()
            if not workflow_task:
                return

            workflow_task.status = WorkflowTask.STATUS_FAILED
            workflow_task.message = f"Creation Failed. Reason: {str(ex.message)}"
            db_session.commit()

        LOGGER.info("Create Wait VPN Gateway failed with status code " + str(ex.code) + ": " + ex.message)
        return

    with get_db_session() as db_session:
        workflow_task = db_session.query(WorkflowTask).filter_by(id=workflow_task_id).first()
        if not workflow_task:
            return

        if vpn_json["status"] == IBMVpnGateway.STATUS_FAILED:
            workflow_task.status = WorkflowTask.STATUS_FAILED
            workflow_task.message = \
                f"IBM Vpn '{vpn_json['name']}' creation for cloud '{cloud_id}' failed on IBM Cloud"
            db_session.commit()
            LOGGER.info(workflow_task.message)
            return

        elif vpn_json["status"] == IBMVpnGateway.STATUS_PENDING:
            workflow_task.status = WorkflowTask.STATUS_RUNNING_WAIT
            db_session.commit()
            LOGGER.info(f"IBM Vpn '{vpn_json['name']}' creation for cloud '{cloud_id}' waiting")
            return

        with db_session.no_autoflush:
            region = db_session.query(IBMRegion).filter_by(id=region_id, cloud_id=cloud_id).first()
            resource_group = \
                db_session.query(IBMResourceGroup).filter_by(
                    resource_id=vpn_json["resource_group"]["id"], cloud_id=cloud_id
                ).first()
            subnet = \
                db_session.query(IBMSubnet).filter_by(
                    resource_id=vpn_json["subnet"]["id"], cloud_id=cloud_id
                ).first()
            vpc_id = subnet.vpc_id

            vpn_gateway = db_session.query(
                IBMVpnGateway).filter_by(name=vpn_json["name"], cloud_id=cloud_id, vpc_id=vpc_id,
                                         status=IBMVpnGateway.STATUS_PENDING).first()
            if vpn_gateway:
                vpn_gateway.ibm_status = IBMVpnGateway.STATUS_AVAILABLE
                workflow_task.status = WorkflowTask.STATUS_SUCCESSFUL
                workflow_task.resource_id = vpn_gateway.id
                db_session.commit()
                LOGGER.info(f"IBM Vpn '{vpn_json['name']}' creation for cloud '{cloud_id}' successful")
                return

            if not (resource_group and subnet and region and vpc_id):
                workflow_task.status = WorkflowTask.STATUS_FAILED
                workflow_task.message = \
                    "Creation Successful but record update failed. The records will update next time discovery runs"
                db_session.commit()

            vpn = IBMVpnGateway.from_ibm_json_body(json_body=vpn_json)
            vpn.resource_group = resource_group
            vpn.region = region
            vpn.subnet = subnet
            vpn.vpc_id = vpc_id
            db_session.commit()

        vpn_json = vpn.to_json()
        vpn_json["created_at"] = str(vpn_json["created_at"])

        IBMResourceLog(
            resource_id=vpn.resource_id, region=vpn.region,
            status=IBMResourceLog.STATUS_ADDED, resource_type=IBMVpnGateway.__name__,
            data=vpn_json)

        workflow_task.status = WorkflowTask.STATUS_SUCCESSFUL
        workflow_task.resource_id = vpn.id
        db_session.commit()

    LOGGER.info(f"IBM Vpn '{vpn_json['name']}' creation for cloud '{cloud_id}' successful")


@celery.task(name="create_vpn_connection", base=IBMWorkflowTasksBase)
def create_vpn_connection(workflow_task_id):
    """
    Create an IBM VPN Connection on IBM Cloud
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
        vpn_gateway_dict = deepcopy(resource_data["vpn_gateway"])

        vpn_gateway = db_session.query(IBMVpnGateway).filter_by(**vpn_gateway_dict,
                                                                cloud_id=cloud_id).first()

        if not vpn_gateway:
            workflow_task.status = WorkflowTask.STATUS_FAILED
            workflow_task.message = \
                f"IBM Vpn Gateway with '{vpn_gateway_dict.get('id') or vpn_gateway_dict.get('name')}' not found"
            db_session.commit()
            LOGGER.info(workflow_task.message)
            return

        region_name = vpn_gateway.region.name
        previous_resources = load_previous_associated_resources(task=workflow_task, session=db_session)
        update_id_or_name_references(
            cloud_id=cloud_id, resource_json=resource_data, resource_schema=IBMVpnGatewayConnectionInSchema,
            db_session=db_session, previous_resources=previous_resources
        )
        update_id_or_name_references(
            cloud_id=cloud_id, resource_json=resource_json, resource_schema=IBMVpnGatewayConnectionsResourceSchema,
            db_session=db_session, previous_resources=previous_resources
        )

    try:
        client = VPNsClient(cloud_id=cloud_id, region=region_name)
        vpn_gateway_connection_json = client.create_vpn_connection(vpn_gateway_id=vpn_gateway.resource_id,
                                                                   connection_json=resource_json)

    except ApiException as ex:
        with get_db_session() as db_session:
            workflow_task = db_session.query(WorkflowTask).filter_by(id=workflow_task_id).first()
            if not workflow_task:
                return

            workflow_task.status = WorkflowTask.STATUS_FAILED
            workflow_task.message = f"Creation Failed. Reason: {str(ex.message)}"
            db_session.commit()

        LOGGER.info("Create VPN Gateway Connection failed with status code " + str(ex.code) + ": " + ex.message)
        return

    with get_db_session() as db_session:
        workflow_task = db_session.query(WorkflowTask).filter_by(id=workflow_task_id).first()
        if not workflow_task:
            return

        metadata = workflow_task.task_metadata.copy() if workflow_task.task_metadata else {}
        metadata["ibm_resource_id"] = vpn_gateway_connection_json["id"]
        workflow_task.task_metadata = metadata
        with db_session.no_autoflush:
            vpn_gateway = db_session.query(IBMVpnGateway).filter_by(**vpn_gateway_dict,
                                                                    cloud_id=cloud_id).first()

            ike_policy = \
                db_session.query(IBMIKEPolicy).filter_by(
                    resource_id=vpn_gateway_connection_json.get('ike_policy', {}).get('id'), cloud_id=cloud_id
                ).first()
            ipsec_policy = \
                db_session.query(IBMIPSecPolicy).filter_by(
                    resource_id=vpn_gateway_connection_json.get('ipsec_policy', {}).get('id'), cloud_id=cloud_id
                ).first()

            if not vpn_gateway:
                workflow_task.status = WorkflowTask.STATUS_FAILED
                workflow_task.message = \
                    "Creation Successful but record update failed. The records will update next time discovery runs"
                db_session.commit()
                LOGGER.info(workflow_task.message)
                return

            vpn_gateway_connection = IBMVpnConnection.from_ibm_json_body(json_body=vpn_gateway_connection_json)
            vpn_gateway_connection.vpn_gateway = vpn_gateway
            if ike_policy:
                vpn_gateway_connection.ike_policy = ike_policy
            if ipsec_policy:
                vpn_gateway_connection.ipsec_policy = ipsec_policy
            db_session.commit()

        vpn_gateway_connection_json = vpn_gateway_connection.to_json()
        vpn_gateway_connection_json["created_at"] = str(vpn_gateway_connection_json["created_at"])

        IBMResourceLog(
            resource_id=vpn_gateway_connection.resource_id, region=vpn_gateway.region,
            status=IBMResourceLog.STATUS_ADDED, resource_type=IBMVpnConnection.__name__,
            data=vpn_gateway_connection_json)

        workflow_task.status = WorkflowTask.STATUS_SUCCESSFUL
        workflow_task.resource_id = vpn_gateway_connection.id
        message = f"IBM Vpn Gateway Connection with id '{vpn_gateway_connection_json['id']}' " \
                  f"creation for cloud '{cloud_id}' successful"
        db_session.commit()

    LOGGER.info(message)


@celery.task(name="delete_vpn", base=IBMWorkflowTasksBase)
def delete_vpn_gateway(workflow_task_id):
    """
    Delete an IBM Vpn
    :param workflow_task_id:
    :return:
    """

    with get_db_session() as db_session:
        workflow_task: WorkflowTask = db_session.query(WorkflowTask).filter_by(id=workflow_task_id).first()
        if not workflow_task:
            return

        workflow_task.status = WorkflowTask.STATUS_RUNNING
        db_session.commit()

        vpn: IBMVpnGateway = db_session.query(IBMVpnGateway).filter_by(id=workflow_task.resource_id).first()
        if not vpn:
            workflow_task.status = WorkflowTask.STATUS_FAILED
            workflow_task.message = f"IBM VPN '{workflow_task.resource_id}' not found"
            db_session.commit()
            LOGGER.info(workflow_task.message)
            return

        region_name = vpn.region.name
        vpn_resource_id = vpn.resource_id
        cloud_id = vpn.cloud_id

    try:
        client = VPNsClient(cloud_id, region=region_name)
        client.delete_vpn_gateway(vpn_gateway_id=vpn_resource_id)
        resp_json = client.get_vpn_gateway(vpn_gateway_id=vpn_resource_id)

    except ApiException as ex:
        with get_db_session() as db_session:
            workflow_task: WorkflowTask = db_session.query(WorkflowTask).filter_by(id=workflow_task_id).first()
            if not workflow_task:
                return

            if ex.code == 404:  # 404 means resource is not found on IBM Cloud.
                vpn: IBMVpnGateway = db_session.query(IBMVpnGateway).filter_by(id=workflow_task.resource_id) \
                    .first()
                if vpn:
                    vpn_json = vpn.to_json()
                    vpn_json["created_at"] = str(vpn_json["created_at"])
                    IBMResourceLog(
                        resource_id=vpn.resource_id, region=vpn.region,
                        status=IBMResourceLog.STATUS_DELETED, resource_type=IBMVpnGateway.__name__,
                        data=vpn_json)

                    db_session.query(IBMIdleResource).filter_by(cloud_id=vpn.cloud_id,
                                                                db_resource_id=vpn.id).delete()

                    db_session.delete(vpn)

                workflow_task.status = WorkflowTask.STATUS_SUCCESSFUL
                LOGGER.info(
                    f"IBM VPN {vpn_resource_id} for cloud {cloud_id} deletion successful.")
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

        vpn_status = resp_json["status"]
        vpn_name = resp_json["name"]
        if vpn_status != IBMVpnGateway.STATUS_DELETING:
            message = f"IBM VPN {vpn_resource_id} for cloud {cloud_id} deletion failed"
            workflow_task.message = message
            workflow_task.status = WorkflowTask.STATUS_FAILED
            LOGGER.info(message)
            db_session.commit()
            return

        workflow_task.status = WorkflowTask.STATUS_RUNNING_WAIT
        message = f"IBM VPN {vpn_name} for cloud {cloud_id} deletion waiting"
        db_session.commit()

    LOGGER.info(message)


@celery.task(name="delete_wait_vpn", base=IBMWorkflowTasksBase)
def delete_wait_vpn_gateway(workflow_task_id):
    """
    Wait tasks for Deletion of an IBM VPN Gateway on IBM Cloud
    """
    with get_db_session() as db_session:
        workflow_task: WorkflowTask = db_session.query(WorkflowTask).filter_by(id=workflow_task_id).first()
        if not workflow_task:
            return

        workflow_task.status = WorkflowTask.STATUS_RUNNING
        db_session.commit()

        vpn: IBMVpnGateway = db_session.query(IBMVpnGateway).filter_by(id=workflow_task.resource_id).first()
        if not vpn:
            workflow_task.status = WorkflowTask.STATUS_SUCCESSFUL
            workflow_task.message = f"IBM VPN '{workflow_task.resource_id}' deleted."
            db_session.commit()
            LOGGER.info(workflow_task.message)
            return

        region_name = vpn.region.name
        vpn_resource_id = vpn.resource_id
        cloud_id = vpn.cloud_id

    try:
        client = VPNsClient(cloud_id, region=region_name)
        resp_json = client.get_vpn_gateway(vpn_gateway_id=vpn_resource_id)

    except ApiException as ex:
        with get_db_session() as db_session:
            workflow_task: WorkflowTask = db_session.query(WorkflowTask).filter_by(id=workflow_task_id).first()
            if not workflow_task:
                return

            if ex.code == 404:  # 404 means resource is not found on IBM Cloud.
                vpn: IBMVpnGateway = db_session.query(IBMVpnGateway).filter_by(
                    id=workflow_task.resource_id).first()
                if vpn:
                    vpn_json = vpn.to_json()
                    vpn_json["created_at"] = str(vpn_json["created_at"])
                    IBMResourceLog(
                        resource_id=vpn.resource_id, region=vpn.region,
                        status=IBMResourceLog.STATUS_DELETED, resource_type=IBMVpnGateway.__name__,
                        data=vpn_json)

                    # Adding resource to IBMResourceTracking
                    create_resource_tracking_object(db_resource=vpn, action_type=IBMResourceTracking.DELETED,
                                                    session=db_session)
                    db_session.delete(vpn)

                workflow_task.status = WorkflowTask.STATUS_SUCCESSFUL
                LOGGER.info(
                    f"IBM VPN {vpn_resource_id} for cloud {cloud_id} deletion successful.")
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

        vpn_status = resp_json["status"]
        vpn_name = resp_json["name"]
        if vpn_status != IBMVpnGateway.STATUS_DELETING:
            message = f"IBM VPN {vpn_resource_id} for cloud {cloud_id} deletion failed"
            workflow_task.message = message
            workflow_task.status = WorkflowTask.STATUS_FAILED
            LOGGER.info(message)
            db_session.commit()
            return

        workflow_task.status = WorkflowTask.STATUS_RUNNING_WAIT
        message = f"IBM VPN {vpn_name} for cloud {cloud_id} deletion waiting"
        db_session.commit()

    LOGGER.info(message)


@celery.task(name="delete_vpn_connection", base=IBMWorkflowTasksBase)
def delete_vpn_connection(workflow_task_id):
    """
    Delete an IBM Connection for a VPN on IBM Cloud
    """
    with get_db_session() as db_session:
        workflow_task: WorkflowTask = db_session.query(WorkflowTask).filter_by(id=workflow_task_id).first()

        if not workflow_task:
            return

        workflow_task.status = WorkflowTask.STATUS_RUNNING
        db_session.commit()

        vpn_connection: IBMVpnConnection = db_session.query(
            IBMVpnConnection).filter_by(id=workflow_task.resource_id).first()
        if not vpn_connection:
            workflow_task.status = WorkflowTask.STATUS_FAILED
            workflow_task.message = f"IBM VPN Connection '{workflow_task.resource_id}' not found"
            db_session.commit()
            LOGGER.info(workflow_task.message)
            return

        region_name = vpn_connection.vpn_gateway.region.name
        vpn_connection_resource_id = vpn_connection.resource_id
        vpn_resource_id = vpn_connection.vpn_gateway.resource_id
        cloud_id = vpn_connection.vpn_gateway.cloud_id
        vpn_connection_name = vpn_connection.name
    try:
        vpn_connection_client = VPNsClient(cloud_id, region=region_name)
        vpn_connection_client.delete_vpn_connection(
            vpn_gateway_id=vpn_resource_id,
            connection_id=vpn_connection_resource_id
        )
        vpn_connection_client.get_vpn_connection(vpn_gateway_id=vpn_resource_id,
                                                 connection_id=vpn_connection_resource_id)
    except ApiException as ex:
        with get_db_session() as db_session:
            if ex.code == 404:  # 404 means resource is not found on IBM Cloud.
                vpn_connection: IBMVpnConnection = db_session.query(IBMVpnConnection).filter_by(
                    id=workflow_task.resource_id).first()
                if vpn_connection:
                    vpn_connection_json = vpn_connection.to_json()
                    vpn_connection_json["created_at"] = str(vpn_connection_json["created_at"])

                    IBMResourceLog(
                        resource_id=vpn_connection.resource_id, region=vpn_connection.vpn_gateway.region,
                        status=IBMResourceLog.STATUS_DELETED, resource_type=IBMVpnConnection.__name__,
                        data=vpn_connection_json)

                    db_session.delete(vpn_connection)

                workflow_task.status = WorkflowTask.STATUS_SUCCESSFUL
                LOGGER.info(
                    f"IBM VPN Connection {vpn_connection_name} for cloud {cloud_id} "
                    f"deletion successful.")
                db_session.commit()
                return
            else:
                workflow_task.status = WorkflowTask.STATUS_FAILED
                message = f"IBM VPN Connection {workflow_task.resource_id} deletion failed. Reason: {str(ex.message)}"
                workflow_task.message = message
                db_session.commit()
                LOGGER.info(message)
                return

    with get_db_session() as db_session:
        workflow_task: WorkflowTask = db_session.query(WorkflowTask).filter_by(id=workflow_task_id).first()
        if not workflow_task:
            return

        workflow_task.status = WorkflowTask.STATUS_RUNNING_WAIT
        message = f"IBM VPN Connection {vpn_connection_name} for cloud {cloud_id} deletion waiting."
        db_session.commit()

    LOGGER.info(message)


@celery.task(name="delete_wait_vpn_connection", base=IBMWorkflowTasksBase)
def delete_wait_vpn_connection(workflow_task_id):
    """
    Wait for an IBM Vpn Connection deletion on IBM Cloud
    :param workflow_task_id:
    :return:
    """
    with get_db_session() as db_session:
        workflow_task: WorkflowTask = db_session.query(WorkflowTask).filter_by(id=workflow_task_id).first()
        if not workflow_task:
            return

        workflow_task.status = WorkflowTask.STATUS_RUNNING
        db_session.commit()

        vpn_connection: IBMVpnConnection = db_session.query(IBMVpnConnection).filter_by(
            id=workflow_task.resource_id).first()
        if not vpn_connection:
            workflow_task.status = WorkflowTask.STATUS_FAILED
            workflow_task.message = f"IBM Vpn Connection '{workflow_task.resource_id}' not found"
            db_session.commit()
            LOGGER.info(workflow_task.message)
            return

        region_name = vpn_connection.vpn_gateway.region.name
        vpn_connection_resource_id = vpn_connection.resource_id
        vpn_resource_id = vpn_connection.vpn_gateway.resource_id
        cloud_id = vpn_connection.vpn_gateway.cloud_id
        vpn_connection_name = vpn_connection.name

    try:
        vpn_connection_client = VPNsClient(cloud_id, region=region_name)
        vpn_connection_client.get_vpn_connection(vpn_gateway_id=vpn_resource_id,
                                                 connection_id=vpn_connection_resource_id)
    except ApiException as ex:
        with get_db_session() as db_session:
            workflow_task: WorkflowTask = db_session.query(WorkflowTask).filter_by(id=workflow_task_id).first()
            if not workflow_task:
                return

            if ex.code == 404:  # 404 means resource is not found on IBM Cloud.
                vpn_connection: IBMVpnConnection = db_session.query(IBMVpnConnection).filter_by(
                    id=workflow_task.resource_id).first()
                if vpn_connection:
                    vpn_connection_json = vpn_connection.to_json()
                    vpn_connection_json["created_at"] = str(vpn_connection_json["created_at"])

                    IBMResourceLog(
                        resource_id=vpn_connection.resource_id, region=vpn_connection.vpn_gateway.region,
                        status=IBMResourceLog.STATUS_DELETED, resource_type=IBMVpnConnection.__name__,
                        data=vpn_connection_json)

                    db_session.delete(vpn_connection)

                workflow_task.status = WorkflowTask.STATUS_SUCCESSFUL
                LOGGER.info(
                    f"IBM VPN Connection {vpn_connection_name} for cloud {cloud_id} "
                    f"deletion successful.")
                db_session.commit()
                return
            else:
                workflow_task.status = WorkflowTask.STATUS_FAILED
                message = f"IBM VPN Connection {workflow_task.resource_id} deletion failed. Reason: {str(ex.message)}"
                workflow_task.message = message
                db_session.commit()
                LOGGER.info(message)
                return

    with get_db_session() as db_session:
        workflow_task: WorkflowTask = db_session.query(WorkflowTask).filter_by(id=workflow_task_id).first()
        if not workflow_task:
            return

        workflow_task.status = WorkflowTask.STATUS_RUNNING_WAIT
        message = f"IBM VPN Connection {vpn_connection_name} for cloud {cloud_id} deletion waiting."
        db_session.commit()
    LOGGER.info(message)
