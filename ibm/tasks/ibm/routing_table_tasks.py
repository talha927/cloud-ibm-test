import logging
from copy import deepcopy
from ibm_cloud_sdk_core import ApiException

from ibm import get_db_session
from ibm.common.clients.ibm_clients import VPCsClient
from ibm.common.utils import update_id_or_name_references
from ibm.models import IBMRegion, IBMResourceLog, IBMRoutingTable, IBMRoutingTableRoute, IBMVpcNetwork, \
    IBMVpnConnection, IBMZone, WorkflowTask
from ibm.tasks.celery_app import celery_app as celery
from ibm.tasks.common.tasks_base import IBMWorkflowTasksBase
from ibm.tasks.ibm.task_utils import load_previous_associated_resources
from ibm.web.ibm.routing_tables.schemas import IBMRoutingTableInSchema, IBMRoutingTableResourceSchema, \
    IBMRoutingTableRouteResourceSchema

LOGGER = logging.getLogger(__name__)


@celery.task(name="create_routing_table", base=IBMWorkflowTasksBase)
def create_routing_table(workflow_task_id):
    """
    Create an IBM Routing Table on IBM Cloud
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

        previous_resources = load_previous_associated_resources(task=workflow_task, session=db_session)
        update_id_or_name_references(
            cloud_id=cloud_id, resource_json=resource_data, resource_schema=IBMRoutingTableInSchema,
            db_session=db_session, previous_resources=previous_resources
        )

        update_id_or_name_references(
            cloud_id=cloud_id, resource_json=resource_json, resource_schema=IBMRoutingTableResourceSchema,
            db_session=db_session, previous_resources=previous_resources
        )
        for route_data in resource_json.get("routes", []):
            update_id_or_name_references(
                cloud_id=cloud_id, resource_json=route_data, resource_schema=IBMRoutingTableRouteResourceSchema,
                db_session=db_session, previous_resources=previous_resources
            )
            if route_data.get("next_hop_address_ip"):
                next_hop_address_ip = route_data["next_hop_address_ip"]
                del route_data["next_hop_address_ip"]
                route_data["next_hop"] = dict()
                route_data["next_hop"]["address"] = next_hop_address_ip

            elif route_data.get("next_hop_vpn_gateway_connection"):
                next_hop_vpn_gateway_resource_id = route_data["next_hop_vpn_gateway_connection"]["id"]
                del route_data["next_hop_vpn_gateway_connection"]
                route_data["next_hop"] = dict()
                route_data["next_hop"]["id"] = next_hop_vpn_gateway_resource_id

        region_name = region.name
        vpc_resource_id = resource_data["vpc"]["id"]

    try:
        vpcs_client = VPCsClient(cloud_id=cloud_id, region=region_name)
        routing_table_json = vpcs_client.create_vpc_routing_table(vpc_id=vpc_resource_id,
                                                                  routing_table_json=resource_json)
    except ApiException as ex:
        with get_db_session() as db_session:
            workflow_task = db_session.query(WorkflowTask).filter_by(id=workflow_task_id).first()
            if not workflow_task:
                return

            workflow_task.status = WorkflowTask.STATUS_FAILED
            workflow_task.message = f"Creation Failed. Reason: {str(ex.message)}"
            db_session.commit()
            LOGGER.info("Create VPC Routing Table failed with status code " + str(ex.code) + ": " + ex.message)
            return

    with get_db_session() as db_session:
        workflow_task = db_session.query(WorkflowTask).filter_by(id=workflow_task_id).first()
        if not workflow_task:
            return

        routing_table_lifecycle_state = routing_table_json["lifecycle_state"]
        routing_table_name = routing_table_json["name"]
        routing_table_resource_id = routing_table_json["id"]
        if routing_table_lifecycle_state in [
            IBMRoutingTable.LIFECYCLE_STATE_UPDATING, IBMRoutingTable.LIFECYCLE_STATE_WAITING,
            IBMRoutingTable.LIFECYCLE_STATE_PENDING, IBMRoutingTable.LIFECYCLE_STATE_STABLE
        ]:
            metadata = deepcopy(workflow_task.task_metadata)
            metadata["ibm_resource_id"] = routing_table_resource_id
            workflow_task.task_metadata = metadata

            workflow_task.status = WorkflowTask.STATUS_RUNNING_WAIT
            LOGGER.debug(f"IBM Routing Table {routing_table_name} for cloud {cloud_id} creation waiting")
        else:
            message = f"IBM Routing Table {routing_table_name} for cloud {cloud_id} creation failed on IBM"
            LOGGER.debug(message)
            workflow_task.message = message
            workflow_task.status = WorkflowTask.STATUS_FAILED
        db_session.commit()


@celery.task(name="create_wait_routing_table", base=IBMWorkflowTasksBase)
def create_wait_routing_table(workflow_task_id):
    """
    Wait for an IBM Routing Table to be successfully created on IBM Cloud
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

        previous_resources = load_previous_associated_resources(task=workflow_task, session=db_session)
        update_id_or_name_references(
            cloud_id=cloud_id, resource_json=resource_data, resource_schema=IBMRoutingTableInSchema,
            db_session=db_session, previous_resources=previous_resources
        )

        region_name = region.name
        vpc_resource_id = resource_data["vpc"]["id"]
        routing_table_resource_id = workflow_task.task_metadata["ibm_resource_id"]

    try:
        vpcs_client = VPCsClient(cloud_id=cloud_id, region=region_name)
        routing_table_json = vpcs_client.get_vpc_routing_table(vpc_id=vpc_resource_id,
                                                               routing_table_id=routing_table_resource_id)
        if routing_table_json["lifecycle_state"] == IBMRoutingTable.LIFECYCLE_STATE_STABLE:
            routing_table_route_jsons_list = \
                vpcs_client.list_vpc_routing_table_routes(vpc_id=vpc_resource_id,
                                                          routing_table_id=routing_table_resource_id)
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

        vpc = db_session.query(IBMVpcNetwork).filter_by(resource_id=vpc_resource_id, cloud_id=cloud_id).first()
        if not vpc:
            message = f"IBM Vpc Network '{resource_data['vpc_id']}' not found"
            LOGGER.debug(message)
            workflow_task.status = WorkflowTask.STATUS_FAILED
            workflow_task.message = message
            db_session.commit()
            return

        routing_table_lifecycle_state = routing_table_json["lifecycle_state"]
        routing_table_name = routing_table_json["name"]
        if routing_table_lifecycle_state == IBMRoutingTable.LIFECYCLE_STATE_STABLE:
            for routing_table_route_json in routing_table_route_jsons_list:
                if routing_table_route_json["lifecycle_state"] == IBMRoutingTableRoute.LIFECYCLE_STATE_STABLE:
                    continue
                elif routing_table_route_json["lifecycle_state"] in [
                    IBMRoutingTableRoute.LIFECYCLE_STATE_PENDING, IBMRoutingTableRoute.LIFECYCLE_STATE_WAITING,
                    IBMRoutingTableRoute.LIFECYCLE_STATE_UPDATING
                ]:
                    workflow_task.status = WorkflowTask.STATUS_RUNNING_WAIT
                    LOGGER.debug(f"IBM Routing Table {routing_table_name} for cloud {cloud_id} creation waiting")
                    db_session.commit()
                    return
                else:
                    message = \
                        f"IBM Routing Table {routing_table_name} for cloud {cloud_id} creation failed on IBM because " \
                        f"route {routing_table_route_json['name']} could not be created"
                    LOGGER.debug(message)
                    workflow_task.message = message
                    workflow_task.status = WorkflowTask.STATUS_FAILED
                    db_session.commit()
                    return

            with db_session.no_autoflush:
                routing_table_obj = IBMRoutingTable.from_ibm_json_body(routing_table_json)
                routing_table_obj.region = region
                routing_table_obj.vpc_network = vpc

                zone_name_to_obj_dict = {}
                for routing_table_route_json in routing_table_route_jsons_list:
                    if routing_table_route_json["zone"]["name"] in zone_name_to_obj_dict:
                        zone = zone_name_to_obj_dict[routing_table_route_json["zone"]["name"]]
                    else:
                        zone = \
                            db_session.query(IBMZone).filter_by(
                                name=routing_table_route_json["zone"]["name"], cloud_id=cloud_id
                            ).first()
                        if not zone:
                            workflow_task.status = WorkflowTask.STATUS_FAILED
                            workflow_task.message = f"IBMZone '{routing_table_route_json['zone']['name']}' not found"
                            db_session.commit()
                            LOGGER.info(workflow_task.message)
                            return

                        zone_name_to_obj_dict[zone.name] = zone

                    routing_table_route_obj = \
                        IBMRoutingTableRoute.from_ibm_json_body(json_body=routing_table_route_json)
                    routing_table_route_obj.zone = zone

                    if routing_table_route_json["next_hop"].get("id"):
                        vpn_gateway_connection = \
                            db_session.query(IBMVpnConnection).filter_by(
                                resource_id=routing_table_route_json["next_hop"]["id"], cloud_id=cloud_id
                            ).first()
                        routing_table_route_obj.vpn_gateway_connection = vpn_gateway_connection

                    routing_table_obj.routes.append(routing_table_route_obj)

                workflow_task.resource_id = routing_table_obj.id

                routing_table_json = routing_table_obj.to_json()
                routing_table_json["created_at"] = str(routing_table_json["created_at"])

                IBMResourceLog(
                    resource_id=routing_table_obj.resource_id, region=routing_table_obj.region,
                    status=IBMResourceLog.STATUS_ADDED, resource_type=IBMRoutingTable.__name__,
                    data=routing_table_json)

                workflow_task.status = WorkflowTask.STATUS_SUCCESSFUL
                db_session.commit()

        elif routing_table_lifecycle_state in [
            IBMRoutingTable.LIFECYCLE_STATE_UPDATING, IBMRoutingTable.LIFECYCLE_STATE_WAITING,
            IBMRoutingTable.LIFECYCLE_STATE_PENDING
        ]:
            workflow_task.status = WorkflowTask.STATUS_RUNNING_WAIT
            LOGGER.debug(f"IBM Routing Table {routing_table_name} for cloud {cloud_id} creation waiting")
        else:
            message = f"IBM Routing Table {routing_table_name} for cloud {cloud_id} creation failed on IBM"
            LOGGER.debug(message)
            workflow_task.message = message
            workflow_task.status = WorkflowTask.STATUS_FAILED
        db_session.commit()


@celery.task(name="delete_routing_table", base=IBMWorkflowTasksBase)
def delete_routing_table(workflow_task_id):
    """
    Delete an IBM Routing Table
    :param workflow_task_id:
    :return:
    """

    with get_db_session() as db_session:
        workflow_task: WorkflowTask = db_session.query(WorkflowTask).filter_by(id=workflow_task_id).first()
        if not workflow_task:
            return

        workflow_task.status = WorkflowTask.STATUS_RUNNING
        db_session.commit()

        routing_table = db_session.query(IBMRoutingTable).filter_by(id=workflow_task.resource_id).first()
        if not routing_table:
            workflow_task.status = WorkflowTask.STATUS_FAILED
            workflow_task.message = f"IBM Routing Table '{workflow_task.resource_id}' not found"
            db_session.commit()
            LOGGER.info(workflow_task.message)
            return

        region_name = routing_table.region.name
        vpc_resource_id = routing_table.vpc_network.resource_id
        cloud_id = routing_table.cloud_id
        routing_table_resource_id = routing_table.resource_id
        routing_table_name = routing_table.name
    try:
        vpc_client = VPCsClient(cloud_id, region=region_name)
        vpc_client.delete_vpc_routing_table(vpc_id=vpc_resource_id, routing_table_id=routing_table_resource_id)
        routing_table_json = vpc_client.get_vpc_routing_table(vpc_id=vpc_resource_id,
                                                              routing_table_id=routing_table_resource_id)

    except ApiException as ex:
        with get_db_session() as db_session:
            workflow_task: WorkflowTask = db_session.query(WorkflowTask).filter_by(id=workflow_task_id).first()
            if not workflow_task:
                return

            if ex.code == 404:
                routing_table = db_session.query(IBMRoutingTable).filter_by(id=workflow_task.resource_id).first()
                if routing_table:
                    routing_table_json = routing_table.to_json()
                    routing_table_json["created_at"] = str(routing_table_json["created_at"])

                    IBMResourceLog(
                        resource_id=routing_table.resource_id, region=routing_table.region,
                        status=IBMResourceLog.STATUS_DELETED, resource_type=IBMRoutingTable.__name__,
                        data=routing_table_json)

                    db_session.delete(routing_table)
                workflow_task.status = WorkflowTask.STATUS_SUCCESSFUL
                LOGGER.info(
                    f"IBM Routing Table {routing_table_name} for cloud {cloud_id} deletion successful.")
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

        lifecycle_state = routing_table_json["lifecycle_state"]
        if lifecycle_state in [IBMRoutingTable.LIFECYCLE_STATE_STABLE, IBMRoutingTable.LIFECYCLE_STATE_FAILED]:
            message = f"IBM Routing Table {routing_table_resource_id} for cloud {cloud_id} deletion failed"
            workflow_task.message = message
            workflow_task.status = WorkflowTask.STATUS_FAILED
            LOGGER.info(message)
            db_session.commit()
            return

        workflow_task.status = WorkflowTask.STATUS_RUNNING_WAIT
        message = f"IBM Routing Table {routing_table_name} for cloud {cloud_id} deletion waiting"
        db_session.commit()

    LOGGER.info(message)


@celery.task(name="delete_wait_routing_table", base=IBMWorkflowTasksBase)
def delete_wait_routing_table(workflow_task_id):
    """
    Wait for an IBM Routing Table deletion on IBM Cloud
    :param workflow_task_id:
    :return:
    """
    with get_db_session() as db_session:
        workflow_task: WorkflowTask = db_session.query(WorkflowTask).filter_by(id=workflow_task_id).first()
        if not workflow_task:
            return

        workflow_task.status = WorkflowTask.STATUS_RUNNING
        db_session.commit()

        routing_table = db_session.query(IBMRoutingTable).filter_by(id=workflow_task.resource_id).first()
        if not routing_table:
            workflow_task.status = WorkflowTask.STATUS_SUCCESSFUL
            db_session.commit()
            LOGGER.info(f"IBM Routing Table {workflow_task.resource_id} deletion successful.")
            return

        region_name = routing_table.region.name
        vpc_resource_id = routing_table.vpc_network.resource_id
        cloud_id = routing_table.cloud_id
        routing_table_resource_id = routing_table.resource_id
        routing_table_name = routing_table.name

    try:
        vpc_client = VPCsClient(cloud_id, region=region_name)
        routing_table_json = vpc_client.get_vpc_routing_table(vpc_id=vpc_resource_id,
                                                              routing_table_id=routing_table_resource_id)

    except ApiException as ex:
        with get_db_session() as db_session:
            workflow_task: WorkflowTask = db_session.query(WorkflowTask).filter_by(id=workflow_task_id).first()
            if not workflow_task:
                return

            if ex.code == 404:
                routing_table = db_session.query(IBMRoutingTable).filter_by(id=workflow_task.resource_id).first()
                if routing_table:
                    routing_table_json = routing_table.to_json()
                    routing_table_json["created_at"] = str(routing_table_json["created_at"])

                    IBMResourceLog(
                        resource_id=routing_table.resource_id, region=routing_table.region,
                        status=IBMResourceLog.STATUS_DELETED, resource_type=IBMRoutingTable.__name__,
                        data=routing_table_json)

                    db_session.delete(routing_table)
                workflow_task.status = WorkflowTask.STATUS_SUCCESSFUL
                LOGGER.info(
                    f"IBM Routing Table {routing_table_name} for cloud {cloud_id} deletion successful.")
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

        lifecycle_state = routing_table_json["lifecycle_state"]
        if lifecycle_state in [IBMRoutingTable.LIFECYCLE_STATE_STABLE, IBMRoutingTable.LIFECYCLE_STATE_FAILED]:
            message = f"IBM Routing Table {routing_table_resource_id} for cloud {cloud_id} deletion failed"
            workflow_task.message = message
            workflow_task.status = WorkflowTask.STATUS_FAILED
            LOGGER.info(message)
            db_session.commit()
            return

        workflow_task.status = WorkflowTask.STATUS_RUNNING_WAIT
        message = f"IBM Routing Table {routing_table_name} for cloud {cloud_id} deletion waiting"
        db_session.commit()

    LOGGER.info(message)
