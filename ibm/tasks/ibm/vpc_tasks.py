from copy import deepcopy
from ibm_cloud_sdk_core import ApiException

from ibm import get_db_session, LOGGER
from ibm.common.clients.ibm_clients import VPCsClient
from ibm.common.utils import update_id_or_name_references
from ibm.models import IBMAddressPrefix, IBMNetworkAcl, IBMRegion, IBMResourceGroup, IBMResourceLog, IBMRoutingTable, \
    IBMRoutingTableRoute, IBMSecurityGroup, IBMVpcNetwork, IBMZone, TTLInterval, WorkflowTask
from ibm.tasks.celery_app import celery_app as celery
from ibm.tasks.common.tasks_base import IBMWorkflowTasksBase
from ibm.tasks.ibm.task_utils import load_previous_associated_resources
from ibm.web.ibm.vpcs.schemas import IBMVpcNetworkInSchema, IBMVpcNetworkResourceSchema


@celery.task(name="create_vpc_network", base=IBMWorkflowTasksBase)
def create_vpc_network(workflow_task_id):
    """
    Create an IBM VPC Network on IBM Cloud
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

        region = db_session.query(IBMRegion).filter_by(id=resource_data["region"]["id"], cloud_id=cloud_id).first()
        if not region:
            workflow_task.status = WorkflowTask.STATUS_FAILED
            workflow_task.message = f"IBMRegion '{region_id}' not found"
            db_session.commit()
            LOGGER.error(workflow_task.message)
            return

        if region.ibm_status == IBMRegion.IBM_STATUS_UNAVAILABLE:
            workflow_task.status = WorkflowTask.STATUS_FAILED
            workflow_task.message = f"IBMRegion '{region.name}' unavailable"
            db_session.commit()
            LOGGER.error(workflow_task.message)
            return

        region_name = region.name

        # This is not required but would help with code consistency
        previous_resources = load_previous_associated_resources(task=workflow_task, session=db_session)
        update_id_or_name_references(
            cloud_id=cloud_id, resource_json=resource_data, resource_schema=IBMVpcNetworkInSchema,
            db_session=db_session, previous_resources=previous_resources
        )
        update_id_or_name_references(
            cloud_id=cloud_id, resource_json=resource_json, resource_schema=IBMVpcNetworkResourceSchema,
            db_session=db_session, previous_resources=previous_resources
        )

    try:
        client = VPCsClient(cloud_id=cloud_id, region=region_name)
        resp_json = client.create_vpc(vpc_json=resource_json)
    except ApiException as ex:
        with get_db_session() as db_session:
            workflow_task = db_session.query(WorkflowTask).filter_by(id=workflow_task_id).first()
            if not workflow_task:
                return

            workflow_task.status = WorkflowTask.STATUS_FAILED
            workflow_task.message = f"Creation Failed. Reason: {str(ex.message)}"
            db_session.commit()
            LOGGER.error(workflow_task.message)
            return

    with get_db_session() as db_session:
        workflow_task = db_session.query(WorkflowTask).filter_by(id=workflow_task_id).first()
        if not workflow_task:
            return

        vpc_status = resp_json["status"]
        vpc_name = resp_json["name"]
        vpc_resource_id = resp_json["id"]
        if vpc_status in [IBMVpcNetwork.STATUS_AVAILABLE, IBMVpcNetwork.STATUS_PENDING]:
            metadata = workflow_task.task_metadata.copy() if workflow_task.task_metadata else {}
            metadata["ibm_resource_id"] = vpc_resource_id
            workflow_task.task_metadata = metadata

            workflow_task.status = WorkflowTask.STATUS_RUNNING_WAIT
            message = f"IBM VPC Network {vpc_name} for cloud {cloud_id} creation waiting"
            LOGGER.info(message)
        else:
            message = f"IBM VPC Network {vpc_name} for cloud {cloud_id} creation failed"
            workflow_task.message = message
            workflow_task.status = WorkflowTask.STATUS_FAILED
            LOGGER.error(message)
        db_session.commit()


@celery.task(name="create_wait_vpc_network", base=IBMWorkflowTasksBase)
def create_wait_vpc_network(workflow_task_id):
    """
    Wait for an IBM VPC Network creation on IBM Cloud
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

        region = db_session.query(IBMRegion).filter_by(id=resource_data["region"]["id"], cloud_id=cloud_id).first()
        if not region:
            workflow_task.status = WorkflowTask.STATUS_FAILED
            workflow_task.message = f"IBMRegion '{region_id}' not found"
            db_session.commit()
            LOGGER.error(workflow_task.message)
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
        client = VPCsClient(cloud_id=cloud_id, region=region_name)
        vpc_json = client.get_vpc(vpc_id=resource_id)
        if vpc_json["status"] == IBMVpcNetwork.STATUS_AVAILABLE:
            vpc_address_prefix_jsons_list = client.list_address_prefixes(vpc_id=vpc_json["id"])
            vpc_default_network_acl_json = client.get_vpcs_default_network_acl(vpc_id=vpc_json["id"])
            vpc_default_routing_table_json = client.get_vpc_default_routing_table(vpc_id=vpc_json["id"])
            vpc_default_routing_table_route_jsons_list = \
                client.list_vpc_routing_table_routes(vpc_id=vpc_json["id"],
                                                     routing_table_id=vpc_default_routing_table_json["id"])
            vpc_default_security_group_json = client.get_vpcs_default_security_group(vpc_id=vpc_json["id"])
    except ApiException as ex:
        with get_db_session() as db_session:
            workflow_task = db_session.query(WorkflowTask).filter_by(id=workflow_task_id).first()
            if not workflow_task:
                return

            workflow_task.status = WorkflowTask.STATUS_FAILED
            workflow_task.message = f"Creation Failed. Reason: {str(ex.message)}"
            db_session.commit()

        LOGGER.error(workflow_task.message)
        return

    with get_db_session() as db_session:
        workflow_task = db_session.query(WorkflowTask).filter_by(id=workflow_task_id).first()
        if not workflow_task:
            return

        vpc_status = vpc_json["status"]
        vpc_name = vpc_json["name"]
        if vpc_status == IBMVpcNetwork.STATUS_AVAILABLE:
            with db_session.no_autoflush:
                region = db_session.query(IBMRegion).filter_by(id=region_id, cloud_id=cloud_id).first()
                vpc_resource_group = \
                    db_session.query(IBMResourceGroup).filter_by(
                        resource_id=vpc_json["resource_group"]["id"], cloud_id=cloud_id
                    ).first()

                vpc_network = IBMVpcNetwork.from_ibm_json_body(json_body=vpc_json)
                vpc_network.region = region
                vpc_network.resource_group = vpc_resource_group
                if resource_data.get('ttl'):
                    vpc_network.ttl = TTLInterval(expires_at=resource_data['ttl']['expires_at'])

                for vpc_address_prefix_json in vpc_address_prefix_jsons_list:
                    zone = \
                        db_session.query(IBMZone).filter_by(
                            name=vpc_address_prefix_json["zone"]["name"], cloud_id=cloud_id
                        ).first()

                    address_prefix = IBMAddressPrefix.from_ibm_json_body(json_body=vpc_address_prefix_json)
                    address_prefix.zone = zone

                    vpc_network.address_prefixes.append(address_prefix)

                default_network_acl = IBMNetworkAcl.from_ibm_json_body(json_body=vpc_default_network_acl_json)
                default_network_acl.is_default = True
                default_network_acl.region = region
                default_network_acl.resource_group = vpc_resource_group
                vpc_network.acls.append(default_network_acl)

                default_routing_table = IBMRoutingTable.from_ibm_json_body(json_body=vpc_default_routing_table_json)
                default_routing_table.region = region
                for route_json in vpc_default_routing_table_route_jsons_list:
                    zone = \
                        db_session.query(IBMZone).filter_by(name=route_json["zone"]["name"], cloud_id=cloud_id).first()

                    route = IBMRoutingTableRoute.from_ibm_json_body(json_body=route_json)
                    route.zone = zone

                    default_routing_table.routes.append(route)
                vpc_network.routing_tables.append(default_routing_table)

                default_security_group = IBMSecurityGroup.from_ibm_json_body(json_body=vpc_default_security_group_json)
                default_security_group.is_default = True
                default_security_group.region = region
                default_security_group.resource_group = vpc_resource_group
                vpc_network.security_groups.append(default_security_group)

                db_session.commit()

            workflow_task.resource_id = vpc_network.id
            workflow_task.status = WorkflowTask.STATUS_SUCCESSFUL

            vpc_network_json = vpc_network.to_json(db_session)
            vpc_network_json["created_at"] = str(vpc_network_json["created_at"])

            IBMResourceLog(
                resource_id=vpc_network.resource_id, region=vpc_network.region,
                status=IBMResourceLog.STATUS_ADDED, resource_type=IBMVpcNetwork.__name__,
                data=vpc_network_json)

            message = f"IBM VPC Network {vpc_name} for cloud {cloud_id} creation successful"
            LOGGER.success(message)
        elif vpc_status == IBMVpcNetwork.STATUS_PENDING:
            workflow_task.status = WorkflowTask.STATUS_RUNNING_WAIT
            message = f"IBM VPC Network {vpc_name} for cloud {cloud_id} creation waiting"
            LOGGER.info(message)
        else:
            message = f"IBM VPC Network {vpc_name} for cloud {cloud_id} creation failed"
            workflow_task.message = message
            workflow_task.status = WorkflowTask.STATUS_FAILED
            LOGGER.error(message)
        db_session.commit()


@celery.task(name="delete_vpc", base=IBMWorkflowTasksBase)
def delete_vpc(workflow_task_id):
    """
    Delete an IBM VPC
    :param workflow_task_id:
    :return:
    """

    with get_db_session() as db_session:
        workflow_task: WorkflowTask = db_session.query(WorkflowTask).filter_by(id=workflow_task_id).first()
        if not workflow_task:
            return

        workflow_task.status = WorkflowTask.STATUS_RUNNING
        db_session.commit()

        vpc: IBMVpcNetwork = db_session.query(IBMVpcNetwork).filter_by(id=workflow_task.resource_id).first()
        if not vpc:
            workflow_task.status = WorkflowTask.STATUS_FAILED
            workflow_task.message = f"IBM VPC '{workflow_task.resource_id}' not found"
            db_session.commit()
            LOGGER.error(workflow_task.message)
            return

        region_name = vpc.region.name
        vpc_resource_id = vpc.resource_id
        cloud_id = vpc.cloud_id
        vpc_name = vpc.name
    try:
        vpc_client = VPCsClient(cloud_id, region=region_name)
        vpc_client.delete_vpc(vpc_resource_id)
        vpc_json = vpc_client.get_vpc(vpc_resource_id)

    except ApiException as ex:
        # IBM VPC is deleted from IBM Cloud Console, but we still have it on VPC + side.
        with get_db_session() as db_session:
            workflow_task: WorkflowTask = db_session.query(WorkflowTask).filter_by(id=workflow_task_id).first()
            if not workflow_task:
                return

            if ex.code == 404:  # 404 means resource is not found on IBM Cloud.
                vpc: IBMVpcNetwork = db_session.query(IBMVpcNetwork).filter_by(id=workflow_task.resource_id).first()
                if vpc:
                    vpc_network_json = vpc.to_json(db_session)
                    vpc_network_json["created_at"] = str(vpc_network_json["created_at"])

                    IBMResourceLog(
                        resource_id=vpc.resource_id, region=vpc.region,
                        status=IBMResourceLog.STATUS_DELETED, resource_type=IBMVpcNetwork.__name__,
                        data=vpc_network_json)

                    db_session.delete(vpc)
                workflow_task.status = WorkflowTask.STATUS_SUCCESSFUL
                LOGGER.success(
                    f"IBM VPC {vpc_name} for cloud {cloud_id} deletion successful.")
                db_session.commit()
                return
            else:
                workflow_task.status = WorkflowTask.STATUS_FAILED
                workflow_task.message = str(ex.message)
                db_session.commit()
                LOGGER.fail(str(ex.message))
                return

    with get_db_session() as db_session:
        workflow_task: WorkflowTask = db_session.query(WorkflowTask).filter_by(id=workflow_task_id).first()
        if not workflow_task:
            return
        vpc_status = vpc_json["status"]
        if vpc_status != IBMVpcNetwork.STATUS_DELETING:
            message = f"IBM VPC Network {vpc_resource_id} for cloud {cloud_id} deletion failed"
            workflow_task.message = message
            workflow_task.status = WorkflowTask.STATUS_FAILED
            LOGGER.error(message)
            db_session.commit()
            return

        workflow_task.status = WorkflowTask.STATUS_RUNNING_WAIT
        message = f"IBM VPC Network {vpc_name} for cloud {cloud_id} deletion waiting"
        db_session.commit()
        LOGGER.info(message)


@celery.task(name="delete_wait_vpc", base=IBMWorkflowTasksBase)
def delete_wait_vpc(workflow_task_id):
    """
    Wait for an IBM VPC deletion on IBM Cloud
    :param workflow_task_id:
    :return:
    """
    with get_db_session() as db_session:
        workflow_task: WorkflowTask = db_session.query(WorkflowTask).filter_by(id=workflow_task_id).first()
        if not workflow_task:
            return

        workflow_task.status = WorkflowTask.STATUS_RUNNING
        db_session.commit()

        vpc: IBMVpcNetwork = db_session.query(IBMVpcNetwork).filter_by(id=workflow_task.resource_id).first()
        if not vpc:
            workflow_task.status = WorkflowTask.STATUS_FAILED
            workflow_task.message = f"IBM VPC '{workflow_task.resource_id}' not found"
            db_session.commit()
            LOGGER.error(workflow_task.message)
            return

        region_name = vpc.region.name
        vpc_resource_id = vpc.resource_id
        cloud_id = vpc.cloud_id
        vpc_name = vpc.name
    try:
        vpc_client = VPCsClient(cloud_id, region=region_name)
        vpc_json = vpc_client.get_vpc(vpc_resource_id)

    except ApiException as ex:
        with get_db_session() as db_session:
            workflow_task: WorkflowTask = db_session.query(WorkflowTask).filter_by(id=workflow_task_id).first()
            if not workflow_task:
                return

            if ex.code == 404:  # 404 means resource is not found on IBM Cloud.
                vpc: IBMVpcNetwork = db_session.query(IBMVpcNetwork).filter_by(id=workflow_task.resource_id).first()
                if vpc:
                    vpc_network_json = vpc.to_json(db_session)
                    vpc_network_json["created_at"] = str(vpc_network_json["created_at"])

                    IBMResourceLog(
                        resource_id=vpc.resource_id, region=vpc.region,
                        status=IBMResourceLog.STATUS_DELETED, resource_type=IBMVpcNetwork.__name__,
                        data=vpc_network_json)

                    db_session.delete(vpc)

                workflow_task.status = WorkflowTask.STATUS_SUCCESSFUL
                LOGGER.success(
                    f"IBM VPC {vpc_name} for cloud {cloud_id} deletion successful.")
                db_session.commit()
                return
            else:
                workflow_task.status = WorkflowTask.STATUS_FAILED
                workflow_task.message = str(ex.message)
                db_session.commit()
                LOGGER.error(str(ex.message))
                return

    with get_db_session() as db_session:
        workflow_task: WorkflowTask = db_session.query(WorkflowTask).filter_by(id=workflow_task_id).first()
        if not workflow_task:
            return
        vpc_status = vpc_json["status"]
        if vpc_status != IBMVpcNetwork.STATUS_DELETING:
            message = f"IBM VPC {vpc_name} for cloud {cloud_id} deletion waiting"
            workflow_task.message = message
            workflow_task.status = WorkflowTask.STATUS_FAILED
            LOGGER.info(message)
            db_session.commit()
            return

        workflow_task.status = WorkflowTask.STATUS_RUNNING_WAIT
        message = f"IBM VPC {vpc_name} for cloud {cloud_id} deletion waiting"
        db_session.commit()

    LOGGER.info(message)
