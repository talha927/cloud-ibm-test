import logging
from copy import deepcopy

from ibm_cloud_sdk_core import ApiException

from ibm import get_db_session
from ibm.common.clients.ibm_clients import TransitGatewaysClient
from ibm.common.utils import update_id_or_name_references
from ibm.models import IBMRegion, IBMResourceGroup, IBMTransitGateway, WorkflowTask, IBMTransitGatewayConnection, \
    IBMVpcNetwork, IBMTransitGatewayConnectionPrefixFilter, IBMCloud, IBMTransitGatewayRouteReport, IBMResourceLog
from ibm.tasks.celery_app import celery_app as celery
from ibm.tasks.common.tasks_base import IBMWorkflowTasksBase
from ibm.tasks.ibm.task_utils import load_previous_associated_resources
from ibm.web.ibm.transit_gateways.schemas import IBMTransitGatewayConnectionPrefixFilterInSchema, \
    IBMTransitGatewayConnectionPrefixFilterResourceSchema, IBMTransitGatewayRouteReportInSchema, \
    IBMTransitGatewayRouteReportResourceSchema
from ibm.web.ibm.transit_gateways.schemas import IBMTransitGatewayInSchema, IBMTransitGatewayResourceSchema, \
    IBMTransitGatewayConnectionResourceSchema, IBMTransitGatewayConnectionInSchema

LOGGER = logging.getLogger(__name__)


@celery.task(name="create_transit_gateway", base=IBMWorkflowTasksBase)
def create_transit_gateway(workflow_task_id):
    """
    Create an IBM Transit Gateway on IBM Cloud
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
        region_name = resource_json["location"]

        region = db_session.query(IBMRegion).filter_by(name=region_name, cloud_id=cloud_id).first()
        if not region:
            workflow_task.status = WorkflowTask.STATUS_FAILED
            workflow_task.message = f"IBM Region '{region_name}' not found"
            db_session.commit()
            LOGGER.info(workflow_task.message)
            return

        if region.ibm_status == IBMRegion.IBM_STATUS_UNAVAILABLE:
            workflow_task.status = WorkflowTask.STATUS_FAILED
            workflow_task.message = f"IBM Region '{region.name}' unavailable"
            db_session.commit()
            LOGGER.info(workflow_task.message)
            return

        region_name = region.name

        previous_resources = load_previous_associated_resources(task=workflow_task, session=db_session)
        update_id_or_name_references(
            cloud_id=cloud_id, resource_json=resource_data, resource_schema=IBMTransitGatewayInSchema,
            db_session=db_session, previous_resources=previous_resources
        )

        update_id_or_name_references(
            cloud_id=cloud_id, resource_json=resource_json, resource_schema=IBMTransitGatewayResourceSchema,
            db_session=db_session, previous_resources=previous_resources
        )

    if "is_global" in resource_json:
        resource_json["global_"] = resource_json["is_global"]
        del resource_json["is_global"]

    try:
        client = TransitGatewaysClient(cloud_id=cloud_id, region=region_name)
        resp_json = client.create_transit_gateway(transit_gateway_json=resource_json)

    except ApiException as ex:
        with get_db_session() as db_session:
            workflow_task = db_session.query(WorkflowTask).filter_by(id=workflow_task_id).first()
            if not workflow_task:
                return

            workflow_task.status = WorkflowTask.STATUS_FAILED
            workflow_task.message = f"Creation Failed. Reason: {str(ex)}"
            db_session.commit()

        LOGGER.info("Creation Of Transit Gateway Failed with status code " + str(ex.code) + ": " + ex.message)
        return

    with get_db_session() as db_session:
        workflow_task = db_session.query(WorkflowTask).filter_by(id=workflow_task_id).first()
        if not workflow_task:
            return

        transit_gateway_ibm_status = resp_json["status"]
        transit_gateway_name = resp_json["name"]
        transit_gateway_resource_id = resp_json["id"]

        if transit_gateway_ibm_status in [IBMTransitGateway.STATUS_PENDING]:
            metadata = deepcopy(workflow_task.task_metadata) if workflow_task.task_metadata else {}
            metadata["ibm_resource_id"] = transit_gateway_resource_id
            workflow_task.task_metadata = metadata

            workflow_task.status = WorkflowTask.STATUS_RUNNING_WAIT
            message = f"IBM Transit Gateway {transit_gateway_name} for cloud {cloud_id} creation waiting"
            workflow_task.message = message
        elif transit_gateway_ibm_status in [IBMTransitGateway.STATUS_FAILED]:
            message = f"IBM Transit Gateway {transit_gateway_name} for cloud {cloud_id} creation failed"
            workflow_task.message = message
            workflow_task.status = WorkflowTask.STATUS_FAILED

        else:
            metadata = deepcopy(workflow_task.task_metadata) if workflow_task.task_metadata else {}
            metadata["ibm_resource_id"] = transit_gateway_resource_id
            workflow_task.task_metadata = metadata
            workflow_task.status = WorkflowTask.STATUS_RUNNING_WAIT
            message = f"IBM Transit Gateway {transit_gateway_name} for cloud {cloud_id} creation waiting"
            workflow_task.message = message

        db_session.commit()


@celery.task(name="create_wait_transit_gateway", base=IBMWorkflowTasksBase)
def create_wait_transit_gateway(workflow_task_id):
    """
    Wait for an IBM Transit Gateway creation on IBM Cloud
    """
    with get_db_session() as db_session:
        workflow_task = db_session.query(WorkflowTask).filter_by(id=workflow_task_id).first()
        if not workflow_task:
            return

        workflow_task.status = WorkflowTask.STATUS_RUNNING
        db_session.commit()

        resource_data = deepcopy(workflow_task.task_metadata["resource_data"])
        cloud_id = resource_data["ibm_cloud"]["id"]
        region_name = resource_data["resource_json"]["location"]

        region = db_session.query(IBMRegion).filter_by(name=region_name, cloud_id=cloud_id).first()
        if not region:
            workflow_task.status = WorkflowTask.STATUS_FAILED
            workflow_task.message = f"IBM Region '{region_name}' not found"
            db_session.commit()
            LOGGER.info(workflow_task.message)
            return

        if region.ibm_status == IBMRegion.IBM_STATUS_UNAVAILABLE:
            workflow_task.status = WorkflowTask.STATUS_FAILED
            workflow_task.message = f"IBM Region '{region.name}' unavailable"
            db_session.commit()
            LOGGER.info(workflow_task.message)
            return

        region_name = region.name
        resource_id = workflow_task.task_metadata["ibm_resource_id"]

    try:
        client = TransitGatewaysClient(cloud_id=cloud_id, region=region_name)
        transit_gateway_json = client.get_transit_gateway(transit_gateway_id=resource_id)

    except ApiException as ex:
        with get_db_session() as db_session:
            workflow_task = db_session.query(WorkflowTask).filter_by(id=workflow_task_id).first()
            if not workflow_task:
                return

            workflow_task.status = WorkflowTask.STATUS_FAILED
            workflow_task.message = f"Creation Failed. Reason: {str(ex)}"
            db_session.commit()

        LOGGER.info("Creation Of Transit Gateway From IBM Cloud Failed with status code " + str(ex.code) + ": "
                    + ex.message)
        return

    with get_db_session() as db_session:
        workflow_task = db_session.query(WorkflowTask).filter_by(id=workflow_task_id).first()
        if not workflow_task:
            return

        if transit_gateway_json["status"] in [IBMTransitGateway.STATUS_FAILED]:
            workflow_task.status = WorkflowTask.STATUS_FAILED
            workflow_task.message = f"IBM Transit Gateway '{transit_gateway_json['name']}'" \
                                    f" creation for cloud '{cloud_id}' " \
                                    f"failed on IBM Cloud"
            db_session.commit()
            LOGGER.info(workflow_task.message)
            return

        elif transit_gateway_json["status"] == IBMTransitGateway.STATUS_PENDING:
            workflow_task.status = WorkflowTask.STATUS_RUNNING_WAIT
            db_session.commit()
            LOGGER.info(f"IBM Transit Gateway '{transit_gateway_json['name']}' creation for cloud '{cloud_id}' waiting")
            return

        with db_session.no_autoflush:
            region = db_session.query(IBMRegion).filter_by(name=region_name,
                                                           cloud_id=cloud_id).first()
            resource_group = db_session.query(IBMResourceGroup).filter_by(
                resource_id=transit_gateway_json["resource_group"]["id"], cloud_id=cloud_id).first()

            if not (resource_group and region):
                workflow_task.status = WorkflowTask.STATUS_FAILED
                workflow_task.message = \
                    "Creation Successful but record update failed. The records will update next time discovery runs"
                db_session.commit()
                LOGGER.info(workflow_task.message)
                return

            transit_gateway = IBMTransitGateway.from_ibm_json_body(json_body=transit_gateway_json)
            transit_gateway.region = region
            transit_gateway.resource_group = resource_group
            db_session.add(transit_gateway)

            IBMResourceLog(
                resource_id=transit_gateway.resource_id, region=transit_gateway.region,
                status=IBMResourceLog.STATUS_ADDED, resource_type=IBMTransitGateway.__name__,
                data=transit_gateway_json)

            workflow_task.status = WorkflowTask.STATUS_SUCCESSFUL
            workflow_task.resource_id = transit_gateway.id
            db_session.commit()

    LOGGER.info(f"IBM Transit Gateway '{transit_gateway_json['name']}' creation for cloud '{cloud_id}' successful")


@celery.task(name="delete_transit_gateway", base=IBMWorkflowTasksBase)
def delete_transit_gateway(workflow_task_id):
    """
    Delete an IBM Transit Gateway on IBM Cloud
    """
    with get_db_session() as db_session:
        workflow_task: WorkflowTask = db_session.query(WorkflowTask).filter_by(id=workflow_task_id).first()
        if not workflow_task:
            return

        workflow_task.status = WorkflowTask.STATUS_RUNNING
        db_session.commit()

        transit_gateway: IBMTransitGateway = db_session.query(IBMTransitGateway).filter_by(
            id=workflow_task.resource_id).first()
        if not transit_gateway:
            workflow_task.status = WorkflowTask.STATUS_FAILED
            workflow_task.message = f"IBM Transit Gateway '{workflow_task.resource_id}' not found"
            db_session.commit()
            LOGGER.info(workflow_task.message)
            return

        resource_id = workflow_task.task_metadata["resource_id"]
        transit_gateway: IBMTransitGateway = db_session.query(IBMTransitGateway).filter_by(
            id=resource_id).first()
        if not transit_gateway:
            workflow_task.status = WorkflowTask.STATUS_FAILED
            workflow_task.message = f"IBM Transit Gateway '{resource_id}' not found"
            db_session.commit()
            LOGGER.info(workflow_task.message)
            return

        transit_gateway_resource_id = transit_gateway.resource_id
        cloud_id = transit_gateway.cloud_id

    try:
        client = TransitGatewaysClient(cloud_id)
        client.delete_transit_gateway(transit_gateway_id=transit_gateway_resource_id)

    except ApiException as ex:
        with get_db_session() as db_session:
            workflow_task: WorkflowTask = db_session.query(WorkflowTask).filter_by(id=workflow_task_id).first()
            if not workflow_task:
                return

            if ex.code == 404:
                transit_gateway: IBMTransitGateway = db_session.query(IBMTransitGateway).get(workflow_task.resource_id)
                if transit_gateway:
                    transit_gateway_json = transit_gateway.to_json()
                    transit_gateway_json["created_at"] = str(transit_gateway_json["created_at"])
                    IBMResourceLog(
                        resource_id=transit_gateway.resource_id, region=transit_gateway.region,
                        status=IBMResourceLog.STATUS_DELETED, resource_type=IBMTransitGateway.__name__,
                        data=transit_gateway.to_json()
                    )

                    db_session.delete(transit_gateway)

                workflow_task.status = WorkflowTask.STATUS_SUCCESSFUL
                LOGGER.info(f"IBM Transit Gateway {resource_id} for cloud {cloud_id} deletion successful.")

                db_session.commit()
                return

            workflow_task.status = WorkflowTask.STATUS_FAILED
            workflow_task.message = f"Deletion Failed. Reason: {str(ex)}"
            db_session.commit()
            LOGGER.info("Deletion Of Transit Gateway Failed with status code " + str(ex.code) + ": " + ex.message)
            return

    with get_db_session() as db_session:
        workflow_task: WorkflowTask = db_session.query(WorkflowTask).filter_by(id=workflow_task_id).first()
        if not workflow_task:
            return

        workflow_task.status = WorkflowTask.STATUS_RUNNING_WAIT
        message = f"IBM Transit Gateway {workflow_task.resource_id} for cloud {cloud_id} deletion waiting"
        workflow_task.message = message
        db_session.commit()
        LOGGER.info(message)


@celery.task(name="delete_wait_transit_gateway", base=IBMWorkflowTasksBase)
def delete_wait_transit_gateway(workflow_task_id):
    """
    Wait task for Deletion of an IBM Transit Gateway on IBM Cloud
    """
    with get_db_session() as db_session:
        workflow_task: WorkflowTask = db_session.query(WorkflowTask).filter_by(id=workflow_task_id).first()
        if not workflow_task:
            return

        workflow_task.status = WorkflowTask.STATUS_RUNNING
        db_session.commit()

        transit_gateway: IBMTransitGateway = db_session.query(IBMTransitGateway).filter_by(
            id=workflow_task.resource_id).first()
        if not transit_gateway:
            workflow_task.status = WorkflowTask.STATUS_FAILED
            workflow_task.message = f"IBMTransitGateway '{workflow_task.resource_id}' not found"
            db_session.commit()
            LOGGER.info(workflow_task.message)
            return

        resource_id = workflow_task.task_metadata["resource_id"]
        transit_gateway: IBMTransitGateway = db_session.query(IBMTransitGateway).filter_by(
            id=resource_id).first()
        if not transit_gateway:
            workflow_task.status = WorkflowTask.STATUS_SUCCESSFUL
            workflow_task.message = f"IBMTransitGateway '{resource_id}' deleted Successfully"
            db_session.commit()
            LOGGER.info(workflow_task.message)
            return

        transit_gateway_resource_id = transit_gateway.resource_id
        cloud_id = transit_gateway.cloud_id

    try:
        client = TransitGatewaysClient(cloud_id)
        transit_gateway_json = client.get_transit_gateway(transit_gateway_id=transit_gateway_resource_id)

    except ApiException as ex:
        with get_db_session() as db_session:
            workflow_task: WorkflowTask = db_session.query(WorkflowTask).filter_by(id=workflow_task_id).first()
            if not workflow_task:
                return

            if ex.code == 404:
                transit_gateway: IBMTransitGateway = db_session.query(IBMTransitGateway).get(workflow_task.resource_id)
                if transit_gateway:
                    transit_gateway_json = transit_gateway.to_json()
                    transit_gateway_json["created_at"] = str(transit_gateway_json["created_at"])
                    IBMResourceLog(
                        resource_id=transit_gateway.resource_id, region=transit_gateway.region,
                        status=IBMResourceLog.STATUS_DELETED, resource_type=IBMTransitGateway.__name__,
                        data=transit_gateway.to_json()
                    )

                    db_session.delete(transit_gateway)

                workflow_task.status = WorkflowTask.STATUS_SUCCESSFUL
                LOGGER.info(f"IBM Transit Gateway {resource_id} for cloud {cloud_id} deletion successful.")

                db_session.commit()
                return

            workflow_task.status = WorkflowTask.STATUS_FAILED
            workflow_task.message = f"Deletion Failed. Reason: {str(ex)}"
            db_session.commit()

            LOGGER.info("Deletion Of Transit Gateway From IBM Cloud Failed with status code " + str(ex.code) + ": "
                        + ex.message)
            return

    with get_db_session() as db_session:
        workflow_task: WorkflowTask = db_session.query(WorkflowTask).filter_by(id=workflow_task_id).first()
        if not workflow_task:
            return

        if not transit_gateway_json:
            workflow_task.status = WorkflowTask.STATUS_SUCCESSFUL
            transit_gateway: IBMTransitGateway = db_session.query(IBMTransitGateway).filter_by(
                id=workflow_task.resource_id).first()
            if transit_gateway:
                db_session.delete(transit_gateway)
            db_session.commit()
            LOGGER.info(
                f"IBM Transit gateway {transit_gateway_resource_id} for cloud {cloud_id} deletion successful.")
            return

        transit_gateway: IBMTransitGateway = db_session.query(IBMTransitGateway).filter_by(
            id=workflow_task.resource_id).first()
        if transit_gateway:
            if transit_gateway_json["status"] == IBMTransitGateway.STATUS_DELETING:
                transit_gateway.status = IBMTransitGateway.STATUS_DELETING
                db_session.commit()

            workflow_task.status = WorkflowTask.STATUS_RUNNING_WAIT
            message = f"IBM Transit Gateway {workflow_task.resource_id} for cloud {cloud_id} deletion waiting"
            workflow_task.message = message
            db_session.commit()

        LOGGER.info(message)


@celery.task(name="create_transit_gateway_connection", base=IBMWorkflowTasksBase)
def create_transit_gateway_connection(workflow_task_id):
    """
    Create an IBM Transit Gateway Connection on IBM Cloud
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
        transit_gateway_dict = deepcopy(resource_data["transit_gateway"])
        vpc_id = resource_json.get("vpc", {}).get("id", None)

        if resource_json["network_type"] == "vpc" and vpc_id:
            vpc = db_session.query(IBMVpcNetwork).filter_by(id=vpc_id, cloud_id=cloud_id).first()
            if not vpc:
                workflow_task.status = WorkflowTask.STATUS_FAILED
                workflow_task.message = f"IBM VPC Network'{vpc}' not found"
                db_session.commit()
                LOGGER.info(workflow_task.message)
                return
            resource_json["network_id"] = vpc.crn
            del resource_json["vpc"]

        previous_resources = load_previous_associated_resources(task=workflow_task, session=db_session)
        if previous_resources:
            transit_gateway = previous_resources[transit_gateway_dict["id"]]
        else:
            transit_gateway = db_session.query(IBMTransitGateway).filter_by(**transit_gateway_dict,
                                                                            cloud_id=cloud_id).first()
            if not transit_gateway:
                workflow_task.message = f"IBM Transit Gateway with " \
                                        f"'{transit_gateway_dict.get('id') or transit_gateway_dict.get('name')}'" \
                                        f" not found"
                db_session.commit()
                LOGGER.info(workflow_task.message)
                return

        update_id_or_name_references(
            cloud_id=cloud_id, resource_json=resource_data, resource_schema=IBMTransitGatewayConnectionInSchema,
            db_session=db_session, previous_resources=previous_resources
        )

        update_id_or_name_references(
            cloud_id=cloud_id, resource_json=resource_json, resource_schema=IBMTransitGatewayConnectionResourceSchema,
            db_session=db_session, previous_resources=previous_resources
        )

    try:

        client = TransitGatewaysClient(cloud_id=cloud_id)
        resp_json = client.create_transit_gateway_connection(transit_gateway_id=transit_gateway.resource_id,
                                                             transit_gateway_connection_json=resource_json)

    except ApiException as ex:
        with get_db_session() as db_session:
            workflow_task = db_session.query(WorkflowTask).filter_by(id=workflow_task_id).first()
            if not workflow_task:
                return

            workflow_task.status = WorkflowTask.STATUS_FAILED
            workflow_task.message = f"Creation Failed. Reason: {str(ex)}"
            db_session.commit()

        LOGGER.info("Creation Of Transit Gateway Connection Failed with status code " + str(ex.code) + ": "
                    + ex.message)
        return

    with get_db_session() as db_session:
        workflow_task = db_session.query(WorkflowTask).filter_by(id=workflow_task_id).first()
        if not workflow_task:
            return

        connection_ibm_status = resp_json["status"]
        connection_name = resp_json["name"]
        connection_resource_id = resp_json["id"]
        if connection_ibm_status == IBMTransitGatewayConnection.CONN_STATUS_FAILED:
            message = f"IBM Transit Gateway Connection {connection_name} for cloud {cloud_id} creation failed"
            workflow_task.message = message
            workflow_task.status = WorkflowTask.STATUS_FAILED
        else:
            metadata = deepcopy(workflow_task.task_metadata) if workflow_task.task_metadata else {}
            metadata["ibm_resource_id"] = connection_resource_id
            workflow_task.task_metadata = metadata
            workflow_task.status = WorkflowTask.STATUS_RUNNING_WAIT
            message = f"IBM Transit Gateway Connection{connection_name} for cloud {cloud_id} creation waiting"
            workflow_task.message = message

        db_session.commit()


@celery.task(name="create_wait_transit_gateway_connection", base=IBMWorkflowTasksBase)
def create_wait_transit_gateway_connection(workflow_task_id):
    """
    Wait for an IBM Transit Gateway Connection creation on IBM Cloud
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
        transit_gateway_dict = deepcopy(resource_data["transit_gateway"])
        vpc_id = resource_json.get("vpc", {}).get("id", None)

        if resource_json["network_type"] == "vpc" and vpc_id:
            vpc = db_session.query(IBMVpcNetwork).filter_by(id=vpc_id, cloud_id=cloud_id).first()
            if not vpc:
                workflow_task.status = WorkflowTask.STATUS_FAILED
                workflow_task.message = f"IBM VPC Network'{vpc.id}' not found"
                db_session.commit()
                LOGGER.info(workflow_task.message)
                return
            resource_json["network_id"] = vpc

        previous_resources = load_previous_associated_resources(task=workflow_task, session=db_session)
        if previous_resources:
            transit_gateway = previous_resources[transit_gateway_dict["id"]]
        else:
            transit_gateway = db_session.query(IBMTransitGateway).filter_by(**transit_gateway_dict,
                                                                            cloud_id=cloud_id).first()
            if not transit_gateway:
                workflow_task.message = f"IBM Transit Gateway with " \
                                        f"'{transit_gateway_dict.get('id') or transit_gateway_dict.get('name')}'" \
                                        f" not found"
                db_session.commit()
                LOGGER.info(workflow_task.message)
                return

        connection_id = workflow_task.task_metadata["ibm_resource_id"]

    try:
        client = TransitGatewaysClient(cloud_id=cloud_id)
        connection_json = client.get_transit_gateway_connection(transit_gateway_id=transit_gateway.resource_id,
                                                                connection_id=connection_id)

    except ApiException as ex:
        with get_db_session() as db_session:
            workflow_task = db_session.query(WorkflowTask).filter_by(id=workflow_task_id).first()
            if not workflow_task:
                return

            workflow_task.status = WorkflowTask.STATUS_FAILED
            workflow_task.message = f"Creation Failed. Reason: {str(ex)}"
            db_session.commit()

        LOGGER.info("Creation Of Transit Gateway Connection From IBM Cloud Failed with status code " + str(ex.code)
                    + ": " + ex.message)
        return

    with get_db_session() as db_session:
        workflow_task = db_session.query(WorkflowTask).filter_by(id=workflow_task_id).first()
        if not workflow_task:
            return

        if connection_json["status"] in [IBMTransitGatewayConnection.CONN_STATUS_FAILED]:
            workflow_task.status = WorkflowTask.STATUS_FAILED
            workflow_task.message = f"IBM Transit Gateway Connection'{connection_json['name']}'" \
                                    f" creation for cloud '{cloud_id}' " \
                                    f"failed on IBM Cloud"
            db_session.commit()
            LOGGER.info(workflow_task.message)
            return

        elif connection_json["status"] == IBMTransitGatewayConnection.CONN_STATUS_PENDING:
            workflow_task.status = WorkflowTask.STATUS_RUNNING_WAIT
            db_session.commit()
            LOGGER.info(
                f"IBM Transit Gateway Connection'{connection_json['name']}' creation for cloud '{cloud_id}' waiting")
            return

        with db_session.no_autoflush:
            if resource_json["network_type"] == "vpc":
                vpc = db_session.query(IBMVpcNetwork).filter_by(cloud_id=cloud_id, id=vpc_id).first()
                if not vpc:
                    workflow_task.status = WorkflowTask.STATUS_FAILED
                    workflow_task.message = \
                        "Creation Successful but record update failed. The records will update next time discovery runs"
                    db_session.commit()
                    LOGGER.info(workflow_task.message)
                    return

            transit_gateway = db_session.query(IBMTransitGateway).filter_by(id=transit_gateway.id, cloud_id=cloud_id) \
                .first()
            ibm_cloud = db_session.query(IBMCloud).filter_by(id=cloud_id).first()

            transit_gateway_connection = IBMTransitGatewayConnection.from_ibm_json_body(json_body=connection_json)

            transit_gateway_connection.transit_gateway = transit_gateway
            if connection_json["network_type"] == "vpc":
                transit_gateway_connection.vpc = vpc
            transit_gateway_connection.ibm_cloud = ibm_cloud
            db_session.add(transit_gateway_connection)

            IBMResourceLog(
                resource_id=transit_gateway_connection.resource_id,
                region=transit_gateway_connection.transit_gateway.region,
                status=IBMResourceLog.STATUS_ADDED, resource_type=IBMTransitGatewayConnection.__name__,
                data=connection_json)

            workflow_task.status = WorkflowTask.STATUS_SUCCESSFUL
            workflow_task.resource_id = transit_gateway_connection.id
            db_session.commit()

    LOGGER.info(f"IBM Transit Gateway Connection'{connection_json['name']}' creation for cloud '{cloud_id}' successful")


@celery.task(name="delete_transit_gateway_connection", base=IBMWorkflowTasksBase)
def delete_transit_gateway_connection(workflow_task_id):
    """
    Delete an IBM Transit Gateway Connection on IBM Cloud
    """
    with get_db_session() as db_session:
        workflow_task: WorkflowTask = db_session.query(WorkflowTask).filter_by(id=workflow_task_id).first()
        if not workflow_task:
            return

        workflow_task.status = WorkflowTask.STATUS_RUNNING
        db_session.commit()

        transit_gateway_connection: IBMTransitGatewayConnection = db_session.query(
            IBMTransitGatewayConnection).filter_by(
            id=workflow_task.resource_id).first()
        if not transit_gateway_connection:
            workflow_task.status = WorkflowTask.STATUS_FAILED
            workflow_task.message = f"IBM Transit Gateway Connection '{workflow_task.resource_id}' not found"
            db_session.commit()
            LOGGER.info(workflow_task.message)
            return

        resource_id = workflow_task.task_metadata["resource_id"]
        transit_gateway_connection: IBMTransitGatewayConnection = db_session.query(
            IBMTransitGatewayConnection).filter_by(
            id=resource_id).first()
        if not transit_gateway_connection:
            workflow_task.status = WorkflowTask.STATUS_FAILED
            workflow_task.message = f"IBM Transit Gateway Connection '{resource_id}' not found"
            db_session.commit()
            LOGGER.info(workflow_task.message)
            return

        transit_gateway: IBMTransitGateway = transit_gateway_connection.transit_gateway

        transit_gateway_connection_resource_id = transit_gateway_connection.resource_id
        transit_gateway_resource_id = transit_gateway.resource_id
        cloud_id = transit_gateway_connection.cloud_id

    try:
        client = TransitGatewaysClient(cloud_id)
        client.delete_transit_gateway_connection(transit_gateway_id=transit_gateway_resource_id,
                                                 connection_id=transit_gateway_connection_resource_id)

    except ApiException as ex:
        with get_db_session() as db_session:
            workflow_task: WorkflowTask = db_session.query(WorkflowTask).filter_by(id=workflow_task_id).first()
            if not workflow_task:
                return

            if ex.code == 404:
                transit_gateway_connection: IBMTransitGatewayConnection = db_session.query(
                    IBMTransitGatewayConnection).get(workflow_task.resource_id)

                if transit_gateway_connection:
                    transit_gateway_connection_json = transit_gateway_connection.to_json()
                    transit_gateway_connection_json["created_at"] = str(transit_gateway_connection_json["created_at"])
                    IBMResourceLog(
                        resource_id=transit_gateway_connection.resource_id,
                        region=transit_gateway_connection.transit_gateway.region,
                        status=IBMResourceLog.STATUS_DELETED, resource_type=IBMTransitGatewayConnection.__name__,
                        data=transit_gateway_connection_json
                    )

                    db_session.delete(transit_gateway_connection)

                workflow_task.status = WorkflowTask.STATUS_SUCCESSFUL
                LOGGER.info(f"IBM Transit Gateway Connection {resource_id} for cloud {cloud_id} deletion successful.")

                db_session.commit()
                return

            workflow_task.status = WorkflowTask.STATUS_FAILED
            workflow_task.message = f"Deletion Failed. Reason: {str(ex)}"
            db_session.commit()
            LOGGER.info(
                "Deletion Of Transit Gateway Connection Failed with status code " + str(ex.code) + ": " + ex.message)
            return

    with get_db_session() as db_session:
        workflow_task: WorkflowTask = db_session.query(WorkflowTask).filter_by(id=workflow_task_id).first()
        if not workflow_task:
            return

        workflow_task.status = WorkflowTask.STATUS_RUNNING_WAIT
        message = f"IBM Transit Gateway Connection {workflow_task.resource_id} for cloud {cloud_id} deletion waiting"
        workflow_task.message = message
        db_session.commit()
        LOGGER.info(message)


@celery.task(name="delete_wait_transit_gateway_connection", base=IBMWorkflowTasksBase)
def delete_wait_transit_gateway_connection(workflow_task_id):
    """
    Wait task for Deletion of an IBM Transit Gateway Connection on IBM Cloud
    """
    with get_db_session() as db_session:
        workflow_task: WorkflowTask = db_session.query(WorkflowTask).filter_by(id=workflow_task_id).first()
        if not workflow_task:
            return

        workflow_task.status = WorkflowTask.STATUS_RUNNING
        db_session.commit()

        transit_gateway_connection: IBMTransitGatewayConnection = db_session.query(
            IBMTransitGatewayConnection).filter_by(
            id=workflow_task.resource_id).first()
        if not transit_gateway_connection:
            workflow_task.status = WorkflowTask.STATUS_FAILED
            workflow_task.message = f"IBMTransitGateway '{workflow_task.resource_id}' not found"
            db_session.commit()
            LOGGER.info(workflow_task.message)
            return

        resource_id = workflow_task.task_metadata["resource_id"]
        transit_gateway_connection: IBMTransitGatewayConnection = db_session.query(
            IBMTransitGatewayConnection).filter_by(
            id=resource_id).first()
        if not transit_gateway_connection:
            workflow_task.status = WorkflowTask.STATUS_SUCCESSFUL
            workflow_task.message = f"IBMTransitGatewayConnection '{resource_id}' deleted Successfully"
            db_session.commit()
            LOGGER.info(workflow_task.message)
            return

        transit_gateway: IBMTransitGateway = transit_gateway_connection.transit_gateway
        transit_gateway_resource_id = transit_gateway.resource_id
        transit_gateway_connection_resource_id = transit_gateway_connection.resource_id
        cloud_id = transit_gateway_connection.cloud_id

    try:
        client = TransitGatewaysClient(cloud_id)
        transit_gateway_connection_json = client.get_transit_gateway_connection(
            transit_gateway_id=transit_gateway_resource_id,
            connection_id=transit_gateway_connection_resource_id)

    except ApiException as ex:
        with get_db_session() as db_session:
            workflow_task: WorkflowTask = db_session.query(WorkflowTask).filter_by(id=workflow_task_id).first()
            if not workflow_task:
                return

            if ex.code == 404:
                transit_gateway_connection: IBMTransitGatewayConnection = db_session.query(
                    IBMTransitGatewayConnection).filter_by(id=workflow_task.resource_id).first()
                if transit_gateway_connection:
                    transit_gateway_connection_json = transit_gateway_connection.to_json()
                    transit_gateway_connection_json["created_at"] = str(transit_gateway_connection_json["created_at"])
                    IBMResourceLog(
                        resource_id=transit_gateway_connection.resource_id,
                        region=transit_gateway_connection.transit_gateway.region,
                        status=IBMResourceLog.STATUS_DELETED, resource_type=IBMTransitGatewayConnection.__name__,
                        data=transit_gateway_connection_json
                    )

                    db_session.delete(transit_gateway_connection)

                workflow_task.status = WorkflowTask.STATUS_SUCCESSFUL
                LOGGER.info(f"IBM Transit Gateway Connection {resource_id} for cloud {cloud_id} deletion successful.")

                db_session.commit()
                return

            workflow_task.status = WorkflowTask.STATUS_FAILED
            workflow_task.message = f"Deletion Failed. Reason: {str(ex)}"
            db_session.commit()

            LOGGER.info("Deletion Of Transit Gateway Connection From IBM Cloud Failed with status code " +
                        str(ex.code) + ": " + ex.message)
            return

    with get_db_session() as db_session:
        workflow_task: WorkflowTask = db_session.query(WorkflowTask).filter_by(id=workflow_task_id).first()
        if not workflow_task:
            return

        if not transit_gateway_connection_json:
            workflow_task.status = WorkflowTask.STATUS_SUCCESSFUL
            transit_gateway_connection: IBMTransitGatewayConnection = db_session.query(
                IBMTransitGatewayConnection).filter_by(
                id=workflow_task.resource_id).first()
            if transit_gateway_connection:
                db_session.delete(transit_gateway_connection)
            db_session.commit()
            LOGGER.info(
                f"IBM Transit gateway Connection {transit_gateway_connection_resource_id} for cloud {cloud_id}"
                f" deletion successful.")
            return

        transit_gateway_connection: IBMTransitGatewayConnection = db_session.query(
            IBMTransitGatewayConnection).filter_by(
            id=workflow_task.resource_id).first()
        if transit_gateway_connection:
            if transit_gateway_connection_json["status"] == IBMTransitGatewayConnection.CONN_STATUS_DELETING:
                transit_gateway_connection.status = IBMTransitGatewayConnection.CONN_STATUS_DELETING
                db_session.commit()

            workflow_task.status = WorkflowTask.STATUS_RUNNING_WAIT
            message = f"IBM Transit Gateway Connection {workflow_task.resource_id} for cloud " \
                      f"{cloud_id} deletion waiting"
            workflow_task.message = message
            db_session.commit()

            LOGGER.info(message)


@celery.task(name="create_transit_gateway_connection_prefix_filter", base=IBMWorkflowTasksBase)
def create_transit_gateway_connection_prefix_filter(workflow_task_id):
    """
    Create an IBM Transit Gateway Connection Prefix Filter on IBM Cloud
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
        transit_gateway_dict = deepcopy(resource_data["transit_gateway"])
        connection_dict = deepcopy(resource_data["transit_gateway_connection"])

        previous_resources = load_previous_associated_resources(task=workflow_task, session=db_session)
        if previous_resources.get(transit_gateway_dict["id"]):
            transit_gateway = previous_resources[transit_gateway_dict["id"]]
        else:
            transit_gateway = db_session.query(IBMTransitGateway).filter_by(**transit_gateway_dict,
                                                                            cloud_id=cloud_id).first()
            if not transit_gateway:
                workflow_task.message = f"IBM Transit Gateway with " \
                                        f"'{transit_gateway_dict.get('id') or transit_gateway_dict.get('name')}'" \
                                        f" not found"
                db_session.commit()
                LOGGER.info(workflow_task.message)
                return

        if previous_resources.get(connection_dict["id"]):
            transit_gateway_connection = previous_resources[connection_dict["id"]]
        else:
            transit_gateway_connection = db_session.query(IBMTransitGatewayConnection).filter_by(**connection_dict,
                                                                                                 cloud_id=cloud_id). \
                first()
            if not transit_gateway_connection:
                workflow_task.message = f"IBM Transit Gateway Connection with " \
                                        f"'{connection_dict.get('id') or connection_dict.get('name')}' not found"
                db_session.commit()
                LOGGER.info(workflow_task.message)
                return

        update_id_or_name_references(
            cloud_id=cloud_id, resource_json=resource_data,
            resource_schema=IBMTransitGatewayConnectionPrefixFilterInSchema,
            db_session=db_session, previous_resources=previous_resources
        )

        update_id_or_name_references(
            cloud_id=cloud_id, resource_json=resource_json,
            resource_schema=IBMTransitGatewayConnectionPrefixFilterResourceSchema,
            db_session=db_session, previous_resources=previous_resources
        )

        tg_resource_id = transit_gateway.resource_id
        connection_resource_id = transit_gateway_connection.resource_id

    try:
        client = TransitGatewaysClient(cloud_id=cloud_id)
        resp_json = client.create_transit_gateway_connection_prefix_filter(
            transit_gateway_id=tg_resource_id, connection_id=connection_resource_id,
            transit_gateway_connection_prefix_filter_json=resource_json)

    except ApiException as ex:
        with get_db_session() as db_session:
            workflow_task = db_session.query(WorkflowTask).filter_by(id=workflow_task_id).first()
            if not workflow_task:
                return

            workflow_task.status = WorkflowTask.STATUS_FAILED
            workflow_task.message = f"Creation Failed. Reason: {str(ex)}"
            db_session.commit()

        LOGGER.info("Creation Of Transit Gateway Connection Prefix Filter Failed with status code " + str(ex.code) +
                    ": " + ex.message)
        return

    with get_db_session() as db_session:
        workflow_task = db_session.query(WorkflowTask).filter_by(id=workflow_task_id).first()
        if not workflow_task:
            return

        with db_session.no_autoflush:
            ibm_cloud = db_session.query(IBMCloud).filter_by(id=cloud_id).first()
            connection = db_session.query(IBMTransitGatewayConnection).filter_by(resource_id=connection_resource_id,
                                                                                 cloud_id=cloud_id).first()

            connection_prefix_filter = IBMTransitGatewayConnectionPrefixFilter.from_ibm_json_body(
                json_body=resp_json)

            connection_prefix_filter.transit_gateway_connection = connection
            transit_gateway = connection.transit_gateway
            connection_prefix_filter.before = connection_prefix_filter.before
            connection_prefix_filter.ibm_cloud = ibm_cloud
            db_session.add(connection_prefix_filter)
        db_session.commit()

        IBMResourceLog(
            resource_id=connection_prefix_filter.resource_id, region=transit_gateway.region,
            status=IBMResourceLog.STATUS_ADDED, resource_type=IBMTransitGatewayConnectionPrefixFilter.__name__,
            data=resource_json)

        workflow_task.status = WorkflowTask.STATUS_SUCCESSFUL
        workflow_task.resource_id = connection_prefix_filter.id
        message = f"IBM Transit gateway Connection Prefix Filter '{resp_json['id']}' " \
                  f"creation for cloud '{cloud_id}' successful"
        db_session.commit()

    LOGGER.info(message)


@celery.task(name="delete_transit_gateway_connection_prefix_filter", base=IBMWorkflowTasksBase)
def delete_transit_gateway_connection_prefix_filter(workflow_task_id):
    """
    Delete an IBM Transit Gateway Connection Prefix Filter
    :param workflow_task_id:
    :return:
    """
    with get_db_session() as db_session:
        workflow_task: WorkflowTask = db_session.get(WorkflowTask, workflow_task_id)
        if not workflow_task:
            return

        workflow_task.status = WorkflowTask.STATUS_RUNNING
        db_session.commit()

        transit_gateway_connection_prefix_filter: IBMTransitGatewayConnectionPrefixFilter = db_session.get(
            IBMTransitGatewayConnectionPrefixFilter, workflow_task.resource_id)
        if not transit_gateway_connection_prefix_filter:
            workflow_task.status = WorkflowTask.STATUS_FAILED
            workflow_task.message = f"IBM Transit Gateway Connection Prefix Filter with'{workflow_task.resource_id}'" \
                                    f" not found"
            db_session.commit()
            LOGGER.info(workflow_task.message)
            return

        transit_gateway_connection: IBMTransitGatewayConnection = \
            transit_gateway_connection_prefix_filter.transit_gateway_connection
        transit_gateway: IBMTransitGateway = transit_gateway_connection.transit_gateway

        filter_resource_id = transit_gateway_connection_prefix_filter.resource_id
        transit_gateway_resource_id = transit_gateway.resource_id
        transit_gateway_connection_resource_id = transit_gateway_connection.resource_id
        cloud_id = transit_gateway_connection_prefix_filter.cloud_id

    try:
        transit_gateway_connection_prefix_filter_client = TransitGatewaysClient(cloud_id)
        transit_gateway_connection_prefix_filter_client.delete_transit_gateway_connection_prefix_filter(
            transit_gateway_id=transit_gateway_resource_id,
            connection_id=transit_gateway_connection_resource_id, filter_id=filter_resource_id)

    except ApiException as ex:
        with get_db_session() as db_session:
            workflow_task: WorkflowTask = db_session.get(WorkflowTask, workflow_task_id)
            if not workflow_task:
                return

            if ex.code == 404:  # 404 means resource is not found on IBM Cloud.
                transit_gateway_connection_prefix_filter: IBMTransitGatewayConnectionPrefixFilter = db_session.get(
                    IBMTransitGatewayConnectionPrefixFilter, workflow_task.resource_id)
                if transit_gateway_connection_prefix_filter:
                    transit_gateway_connection_prefix_filter_json = transit_gateway_connection_prefix_filter.to_json()
                    transit_gateway_connection_prefix_filter_json["created_at"] = str(
                        transit_gateway_connection_prefix_filter_json["created_at"])

                    IBMResourceLog(
                        resource_id=transit_gateway_connection_prefix_filter.resource_id,
                        region=transit_gateway_connection_prefix_filter.transit_gateway_connection.
                        transit_gateway.region,
                        status=IBMResourceLog.STATUS_DELETED,
                        resource_type=IBMTransitGatewayConnectionPrefixFilter.__name__,
                        data=transit_gateway_connection_prefix_filter_json
                    )

                    db_session.delete(transit_gateway_connection_prefix_filter)

                workflow_task.status = WorkflowTask.STATUS_SUCCESSFUL
                LOGGER.info(f"IBM Transit Gateway Connection Prefix Filter {filter_resource_id} for cloud "
                            f"{transit_gateway_connection_prefix_filter.cloud_id} deletion successful.")
                db_session.commit()
                return

            workflow_task.status = WorkflowTask.STATUS_FAILED
            workflow_task.message = f"Deletion Failed. Reason: {str(ex)}"
            db_session.commit()
            LOGGER.info("Deletion Of Transit Gateway Connection Prefix Filter failed with status code " + str(ex.code)
                        + ": " + ex.message)
            return

    with get_db_session() as db_session:
        workflow_task: WorkflowTask = db_session.get(WorkflowTask, workflow_task_id)
        if not workflow_task:
            return

        transit_gateway_connection_prefix_filter: IBMTransitGatewayConnectionPrefixFilter = db_session.get(
            IBMTransitGatewayConnectionPrefixFilter, workflow_task.resource_id)
        if transit_gateway_connection_prefix_filter:
            transit_gateway_connection_prefix_filter_json = transit_gateway_connection_prefix_filter.to_json()
            transit_gateway_connection_prefix_filter_json["created_at"] = str(
                transit_gateway_connection_prefix_filter_json["created_at"])

            IBMResourceLog(
                resource_id=transit_gateway_connection_prefix_filter.resource_id,
                region=transit_gateway_connection_prefix_filter.transit_gateway_connection.
                transit_gateway.region,
                status=IBMResourceLog.STATUS_DELETED,
                resource_type=IBMTransitGatewayConnectionPrefixFilter.__name__,
                data=transit_gateway_connection_prefix_filter_json
            )

            db_session.delete(transit_gateway_connection_prefix_filter)

        workflow_task.status = WorkflowTask.STATUS_SUCCESSFUL
        LOGGER.info(f"IBM Transit Gateway Prefix Filter {transit_gateway_connection_prefix_filter.resource_id}"
                    f" for cloud {cloud_id} deletion successful.")
        db_session.commit()
        return


@celery.task(name="create_transit_gateway_route_report", base=IBMWorkflowTasksBase)
def create_transit_gateway_route_report(workflow_task_id):
    """
    Create an IBM Transit Gateway Route Report on IBM Cloud
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
        transit_gateway_id = resource_data["resource_json"]["transit_gateway"]["id"]

        transit_gateway = db_session.query(IBMTransitGateway).filter_by(id=transit_gateway_id,
                                                                        cloud_id=cloud_id).first()
        if not transit_gateway:
            workflow_task.status = WorkflowTask.STATUS_FAILED
            workflow_task.message = f"IBM Transit Gateway '{transit_gateway}' not found"
            db_session.commit()
            LOGGER.info(workflow_task.message)
            return

        update_id_or_name_references(
            cloud_id=cloud_id, resource_json=resource_data, resource_schema=IBMTransitGatewayRouteReportInSchema,
            db_session=db_session
        )

        update_id_or_name_references(
            cloud_id=cloud_id, resource_json=resource_json, resource_schema=IBMTransitGatewayRouteReportResourceSchema,
            db_session=db_session
        )

    try:
        client = TransitGatewaysClient(cloud_id=cloud_id)
        resp_json = client.create_transit_gateway_route_report(transit_gateway_id=transit_gateway.resource_id)

    except ApiException as ex:
        with get_db_session() as db_session:
            workflow_task = db_session.query(WorkflowTask).filter_by(id=workflow_task_id).first()
            if not workflow_task:
                return

            workflow_task.status = WorkflowTask.STATUS_FAILED
            workflow_task.message = f"Creation Failed. Reason: {str(ex)}"
            db_session.commit()

            LOGGER.info("Creation Of Transit Gateway Route Report Failed with status code " + str(ex.code) + ": "
                        + ex.message)
            return

    with get_db_session() as db_session:
        workflow_task = db_session.query(WorkflowTask).filter_by(id=workflow_task_id).first()
        if not workflow_task:
            return

        route_report_ibm_status = resp_json["status"]
        route_report_resource_id = resp_json["id"]
        if route_report_ibm_status == IBMTransitGatewayRouteReport.STATUS_PENDING:
            metadata = deepcopy(workflow_task.task_metadata) if workflow_task.task_metadata else {}
            metadata["ibm_resource_id"] = route_report_resource_id
            workflow_task.task_metadata = metadata
            workflow_task.status = WorkflowTask.STATUS_RUNNING_WAIT
            message = f"IBM Transit Gateway Connection{route_report_resource_id} for cloud {cloud_id} creation waiting"
            workflow_task.message = message

        db_session.commit()


@celery.task(name="create_wait_transit_gateway_route_report", base=IBMWorkflowTasksBase)
def create_wait_transit_gateway_route_report(workflow_task_id):
    """
    Wait for an IBM Transit Gateway Route Report creation on IBM Cloud
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
        transit_gateway_id = resource_json["transit_gateway"]["id"]

        transit_gateway = db_session.query(IBMTransitGateway).filter_by(id=transit_gateway_id,
                                                                        cloud_id=cloud_id).first()
        if not transit_gateway:
            workflow_task.status = WorkflowTask.STATUS_FAILED
            workflow_task.message = f"IBM Transit Gateway '{transit_gateway}' not found"
            db_session.commit()
            LOGGER.info(workflow_task.message)
            return

        routes_report_id = workflow_task.task_metadata["ibm_resource_id"]

    try:
        client = TransitGatewaysClient(cloud_id=cloud_id)
        route_report_json = client.get_transit_gateway_route_report(
            transit_gateway_id=transit_gateway.resource_id,
            id=routes_report_id)
    except ApiException as ex:
        with get_db_session() as db_session:
            workflow_task = db_session.query(WorkflowTask).filter_by(id=workflow_task_id).first()
            if not workflow_task:
                return

            workflow_task.status = WorkflowTask.STATUS_FAILED
            workflow_task.message = f"Creation Failed. Reason: {str(ex)}"
            db_session.commit()

            LOGGER.info("Creation Of Transit Gateway Route Report Failed with status code " + str(ex.code) + ": "
                        + ex.message)
            return

    with get_db_session() as db_session:
        workflow_task = db_session.query(WorkflowTask).filter_by(id=workflow_task_id).first()
        if not workflow_task:
            return

        if route_report_json["status"] == IBMTransitGatewayRouteReport.STATUS_PENDING:
            workflow_task.status = WorkflowTask.STATUS_RUNNING_WAIT
            db_session.commit()
            LOGGER.info(
                f"IBM Transit Gateway Route Report'{routes_report_id}' creation for cloud '{cloud_id}' waiting")
            return

        with db_session.no_autoflush:
            ibm_cloud = db_session.query(IBMCloud).filter_by(id=cloud_id).first()
            transit_gateway = db_session.query(IBMTransitGateway).filter_by(id=transit_gateway.id).first()

            route_report = IBMTransitGatewayRouteReport.from_ibm_json_body(json_body=route_report_json)

            route_report.transit_gateway = transit_gateway
            route_report.ibm_cloud = ibm_cloud

            IBMResourceLog(
                resource_id=route_report.resource_id, region=transit_gateway.region,
                status=IBMResourceLog.STATUS_ADDED, resource_type=IBMTransitGatewayRouteReport.__name__,
                data=route_report_json)

            workflow_task.status = WorkflowTask.STATUS_SUCCESSFUL
            workflow_task.resource_id = route_report.id
            db_session.commit()

    LOGGER.info(f"IBM Transit Gateway Route Report'{routes_report_id}' creation for cloud '{cloud_id}' successful")


@celery.task(name="delete_transit_gateway_route_report", base=IBMWorkflowTasksBase)
def delete_transit_gateway_route_report(workflow_task_id):
    """
    Delete an IBM Transit Gateway Route Report
    :param workflow_task_id:
    :return:
    """
    with get_db_session() as db_session:
        workflow_task: WorkflowTask = db_session.get(WorkflowTask, workflow_task_id)
        if not workflow_task:
            return

        workflow_task.status = WorkflowTask.STATUS_RUNNING
        db_session.commit()

        transit_gateway_route_report: IBMTransitGatewayRouteReport = db_session.get(
            IBMTransitGatewayRouteReport, workflow_task.resource_id)
        if not transit_gateway_route_report:
            workflow_task.status = WorkflowTask.STATUS_FAILED
            workflow_task.message = f"IBM Transit Gateway Route Report with'{workflow_task.resource_id}' not found"
            db_session.commit()
            LOGGER.info(workflow_task.message)
            return

        transit_gateway: IBMTransitGateway = transit_gateway_route_report.transit_gateway

        route_report_resource_id = transit_gateway_route_report.resource_id
        transit_gateway_resource_id = transit_gateway.resource_id
        cloud_id = transit_gateway_route_report.cloud_id

    try:
        transit_gateway_connection_prefix_filter_client = TransitGatewaysClient(cloud_id)
        transit_gateway_connection_prefix_filter_client.delete_transit_gateway_route_report(
            transit_gateway_id=transit_gateway_resource_id, id=route_report_resource_id)

    except ApiException as ex:
        with get_db_session() as db_session:
            workflow_task: WorkflowTask = db_session.get(WorkflowTask, workflow_task_id)
            if not workflow_task:
                return

            if ex.code == 404:  # 404 means resource is not found on IBM Cloud.
                transit_gateway_route_report: IBMTransitGatewayRouteReport = db_session.get(
                    IBMTransitGatewayRouteReport, workflow_task.resource_id)
                if transit_gateway_route_report:
                    transit_gateway_route_report_json = transit_gateway_route_report.to_json()
                    transit_gateway_route_report_json["created_at"] = \
                        str(transit_gateway_route_report_json["created_at"])
                    IBMResourceLog(
                        resource_id=transit_gateway_route_report.resource_id,
                        region=transit_gateway.region,
                        status=IBMResourceLog.STATUS_DELETED, resource_type=IBMTransitGatewayRouteReport.__name__,
                        data=transit_gateway_route_report_json
                    )
                    db_session.delete(transit_gateway_route_report)

                workflow_task.status = WorkflowTask.STATUS_SUCCESSFUL
                LOGGER.info(f"IBM Transit Gateway Route Report{route_report_resource_id} for cloud "
                            f"{transit_gateway_route_report.cloud_id} deletion successful.")
                db_session.commit()
                return

            workflow_task.status = WorkflowTask.STATUS_FAILED
            workflow_task.message = f"Deletion Failed. Reason: {str(ex)}"
            db_session.commit()
            LOGGER.info("Deletion Of Transit Gateway Route Report failed with status code " + str(ex.code)
                        + ": " + ex.message)
            return

    with get_db_session() as db_session:
        workflow_task: WorkflowTask = db_session.get(WorkflowTask, workflow_task_id)
        if not workflow_task:
            return

        transit_gateway_route_report: IBMTransitGatewayRouteReport = db_session.get(
            IBMTransitGatewayRouteReport, workflow_task.resource_id)
        if transit_gateway_route_report:
            db_session.delete(transit_gateway_route_report)

        workflow_task.status = WorkflowTask.STATUS_SUCCESSFUL
        LOGGER.info(f"IBM Transit Gateway Route Report {transit_gateway_route_report.resource_id}"
                    f" for cloud {cloud_id} deletion successful.")
        db_session.commit()
        return
