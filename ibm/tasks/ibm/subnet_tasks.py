from copy import deepcopy
from ibm_cloud_sdk_core import ApiException

from ibm import get_db_session, LOGGER
from ibm.common.clients.ibm_clients import SubnetsClient
from ibm.common.clients.ibm_clients.exceptions import IBMAuthError, IBMConnectError, IBMExecuteError, \
    IBMInvalidRequestError
from ibm.common.utils import update_id_or_name_references
from ibm.models import IBMNetworkAcl, IBMPublicGateway, IBMRegion, IBMResourceGroup, IBMResourceLog, IBMRoutingTable, \
    IBMSubnet, IBMSubnetReservedIp, IBMVpcNetwork, IBMZone, WorkflowTask
from ibm.tasks.celery_app import celery_app as celery
from ibm.tasks.common.tasks_base import IBMWorkflowTasksBase
from ibm.tasks.ibm.task_utils import load_previous_associated_resources
from ibm.web.ibm.subnets.schemas import IBMReservedIpInSchema, IBMReservedIpResourceSchema, IBMSubnetResourceSchema


@celery.task(name="create_subnet", base=IBMWorkflowTasksBase)
def create_subnet(workflow_task_id):
    """
    Create an IBM Subnet on IBM Cloud
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
            LOGGER.error(workflow_task.message)
            return

        if region.ibm_status == IBMRegion.IBM_STATUS_UNAVAILABLE:
            workflow_task.status = WorkflowTask.STATUS_FAILED
            workflow_task.message = f"IBMRegion '{region.name}' unavailable"
            db_session.commit()
            LOGGER.error(workflow_task.message)
            return

        region_name = region.name

        previous_resources = load_previous_associated_resources(task=workflow_task, session=db_session)
        update_id_or_name_references(
            cloud_id=cloud_id, resource_json=resource_json, resource_schema=IBMSubnetResourceSchema,
            db_session=db_session, previous_resources=previous_resources
        )

    try:
        client = SubnetsClient(cloud_id=cloud_id, region=region_name)
        subnet_json = client.create_subnet(subnet_json=resource_json)
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

        if subnet_json["status"] == IBMSubnet.STATUS_FAILED:
            workflow_task.status = WorkflowTask.STATUS_FAILED
            workflow_task.message = \
                f"IBM Subnet '{subnet_json['name']}' creation for cloud '{cloud_id}' failed on IBM Cloud"
            db_session.commit()
            LOGGER.error(workflow_task.message)
            return

        metadata = workflow_task.task_metadata.copy() if workflow_task.task_metadata else {}
        metadata["ibm_resource_id"] = subnet_json["id"]
        workflow_task.task_metadata = metadata

        workflow_task.status = WorkflowTask.STATUS_RUNNING_WAIT
        message = f"IBM Subnet '{subnet_json['name']}' creation for cloud '{cloud_id}' waiting"
        db_session.commit()
    LOGGER.info(message)


@celery.task(name="create_wait_subnet", base=IBMWorkflowTasksBase)
def create_wait_subnet(workflow_task_id):
    """
    Create an IBM Subnet on IBM Cloud
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
            LOGGER.error(workflow_task.message)
            return

        if region.ibm_status == IBMRegion.IBM_STATUS_UNAVAILABLE:
            workflow_task.status = WorkflowTask.STATUS_FAILED
            workflow_task.message = f"IBMRegion '{region.name}' unavailable"
            db_session.commit()
            LOGGER.error(workflow_task.message)
            return

        region_name = region.name
        resource_id = workflow_task.task_metadata["ibm_resource_id"]

    try:
        client = SubnetsClient(cloud_id=cloud_id, region=region_name)
        subnet_json = client.get_subnet(subnet_id=resource_id)
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

        if subnet_json["status"] == IBMSubnet.STATUS_FAILED:
            workflow_task.status = WorkflowTask.STATUS_FAILED
            workflow_task.message = \
                f"IBM Subnet '{subnet_json['name']}' creation for cloud '{cloud_id}' failed on IBM Cloud"
            db_session.commit()
            LOGGER.error(workflow_task.message)
            return

        elif subnet_json["status"] == IBMSubnet.STATUS_PENDING:
            LOGGER.info(f"IBM Subnet '{subnet_json['name']}' creation for cloud '{cloud_id}' waiting")
            workflow_task.status = WorkflowTask.STATUS_RUNNING_WAIT
            db_session.commit()
            return

        with db_session.no_autoflush:
            network_acl = \
                db_session.query(IBMNetworkAcl).filter_by(
                    resource_id=subnet_json["network_acl"]["id"], cloud_id=cloud_id
                ).first()

            resource_group = \
                db_session.query(IBMResourceGroup).filter_by(
                    resource_id=subnet_json["resource_group"]["id"], cloud_id=cloud_id
                ).first()
            if not resource_group:
                workflow_task.status = WorkflowTask.STATUS_FAILED
                workflow_task.message = f"IBMResourceGroup with resource_id {subnet_json['resource_group']['id']} " \
                                        f"in db for cloud {cloud_id}"
                LOGGER.error(workflow_task.message)
                db_session.commit()
                return

            routing_table = \
                db_session.query(IBMRoutingTable).filter_by(
                    resource_id=subnet_json["routing_table"]["id"], cloud_id=cloud_id
                ).first()

            vpc_network = \
                db_session.query(IBMVpcNetwork).filter_by(
                    resource_id=subnet_json["vpc"]["id"], cloud_id=cloud_id
                ).first()
            if not vpc_network:
                workflow_task.status = WorkflowTask.STATUS_FAILED
                workflow_task.message = f"VPC network with resource_id {subnet_json['vpc']['id']} in " \
                                        f"db for cloud {cloud_id}"
                LOGGER.error(workflow_task.message)
                db_session.commit()
                return

            zone = \
                db_session.query(IBMZone).filter_by(
                    name=subnet_json["zone"]["name"], cloud_id=cloud_id
                ).first()
            if not zone:
                workflow_task.status = WorkflowTask.STATUS_FAILED
                workflow_task.message = f"IBMZone with name {subnet_json['zone']['name']} in db for cloud {cloud_id}"
                LOGGER.error(workflow_task.message)
                db_session.commit()
                return

            public_gateway = None
            if "public_gateway" in subnet_json:
                public_gateway = db_session.query(IBMPublicGateway).filter_by(
                    resource_id=subnet_json["public_gateway"]["id"], cloud_id=cloud_id
                ).first()

            # TODO: Find the associated address_prefix
            subnet = IBMSubnet.from_ibm_json_body(subnet_json)
            subnet.zone = zone
            subnet.vpc_network = vpc_network
            subnet.network_acl = network_acl
            subnet.resource_group = resource_group
            subnet.routing_table = routing_table
            subnet.public_gateway = public_gateway

            subnet_json = subnet.to_json()
            subnet_json["created_at"] = str(subnet_json["created_at"])

            IBMResourceLog(
                resource_id=subnet.resource_id, region=subnet.zone.region,
                status=IBMResourceLog.STATUS_ADDED, resource_type=IBMSubnet.__name__,
                data=subnet_json)

            db_session.commit()
        workflow_task.resource_id = subnet.id
        workflow_task.status = WorkflowTask.STATUS_SUCCESSFUL
        db_session.commit()

    LOGGER.success(f"IBM Subnet '{subnet_json['name']}' creation for cloud '{cloud_id}' successful")


@celery.task(name="attach_network_acl_to_subnet", base=IBMWorkflowTasksBase)
def attach_network_acl_to_subnet(workflow_task_id):
    """
    Attach a Network Acl to IBM Subnet on IBM Cloud
    """
    with get_db_session() as db_session:
        workflow_task = db_session.query(WorkflowTask).filter_by(id=workflow_task_id).first()

        if not workflow_task:
            return

        workflow_task.status = WorkflowTask.STATUS_RUNNING
        db_session.commit()

        resource_data = deepcopy(workflow_task.task_metadata["resource_data"])
        resource_json = deepcopy(resource_data["resource_json"])
        network_acl_name = resource_json["name"]
        subnet_id = deepcopy(workflow_task.task_metadata["subnet_id"])
        subnet = db_session.query(IBMSubnet).filter_by(id=subnet_id).first()

        if not subnet:
            workflow_task.status = WorkflowTask.STATUS_FAILED
            workflow_task.message = f"IBM subnet with name '{resource_json['name']}' not found"
            db_session.commit()
            LOGGER.error(workflow_task.message)
            return

        region_name = subnet.zone.region.name
        region_id = subnet.zone.region.id
        cloud_id = subnet.ibm_cloud.id
        subnet_resource_id = subnet.resource_id
        vpc_resource_id = resource_json["vpc"]["id"]
        vpc = db_session.query(IBMVpcNetwork).filter_by(id=vpc_resource_id).first()

        if not vpc:
            workflow_task.status = WorkflowTask.STATUS_FAILED
            workflow_task.message = f"IBM Vpc {vpc_resource_id} not found"
            db_session.commit()
            LOGGER.error(workflow_task.message)
            return

        network_acl = db_session.query(IBMNetworkAcl).filter_by(cloud_id=cloud_id, name=network_acl_name,
                                                                vpc_id=vpc_resource_id).first()

        if not network_acl:
            workflow_task.status = WorkflowTask.STATUS_FAILED
            workflow_task.message = f"IBM Network Acl with name {network_acl_name} not found"
            db_session.commit()
            LOGGER.error(workflow_task.message)
            return

        network_acl_resource_id = network_acl.resource_id

    try:
        client = SubnetsClient(cloud_id, region=region_name)
        resp_json = client.attach_acl_to_subnet(
            region=region_name, subnet_id=subnet_resource_id, attach_subnet_json={"id": network_acl_resource_id})
    except (IBMAuthError, IBMConnectError, IBMExecuteError, IBMInvalidRequestError) as ex:
        with get_db_session() as db_session:
            workflow_task = db_session.query(WorkflowTask).filter_by(id=workflow_task_id).first()

            if not workflow_task:
                return

            workflow_task.status = WorkflowTask.STATUS_FAILED
            workflow_task.message = f"Creation Failed. Reason: {str(ex)}"
            db_session.commit()

        LOGGER.error(str(ex))
        return

    with get_db_session() as db_session:
        workflow_task = db_session.query(WorkflowTask).filter_by(id=workflow_task_id).first()

        if not workflow_task:
            return

        network_acl = db_session.query(IBMNetworkAcl).filter_by(
            resource_id=resp_json["id"]).first()

        if not network_acl:
            workflow_task.status = WorkflowTask.STATUS_FAILED
            workflow_task.message = \
                "Attachment Successful but record update failed. The records will update next time discovery runs"
            db_session.commit()
            LOGGER.note(workflow_task.message)
            return

        attached_subnets = network_acl.subnets.all()

        for subnet in resp_json["subnets"]:
            subnet_obj = db_session.query(IBMSubnet).filter_by(
                resource_id=subnet["id"], region_id=region_id, cloud_id=cloud_id).first()

            if not subnet_obj:
                workflow_task.status = WorkflowTask.STATUS_FAILED
                workflow_task.message = f"IBM Subnet with name '{subnet['name']}' not found"
                db_session.commit()
                LOGGER.error(workflow_task.message)
                return

            if subnet_obj in attached_subnets:
                continue

            subnet_obj.network_acl = network_acl

            db_session.commit()
        IBMResourceLog(
            resource_id=subnet_obj.resource_id, region=subnet_obj.region,
            status=IBMResourceLog.STATUS_ADDED, resource_type=IBMSubnet.__name__,
            data=subnet_obj.to_json())

        workflow_task.status = WorkflowTask.STATUS_SUCCESSFUL
        db_session.commit()

    LOGGER.success(f"IBM Network Acl {resource_json['name']} attached with subnet '{subnet_resource_id}'")


@celery.task(name="delete_subnet", base=IBMWorkflowTasksBase)
def delete_subnet(workflow_task_id):
    """
    Delete an IBM Subnet
    :param workflow_task_id:
    :return:
    """

    with get_db_session() as db_session:
        workflow_task: WorkflowTask = db_session.query(WorkflowTask).get(workflow_task_id)
        if not workflow_task:
            return

        workflow_task.status = WorkflowTask.STATUS_RUNNING
        db_session.commit()
        resource_id = workflow_task.task_metadata["resource_id"]
        subnet: IBMSubnet = db_session.query(IBMSubnet).filter_by(id=resource_id).first()
        if not subnet:
            workflow_task.status = WorkflowTask.STATUS_FAILED
            workflow_task.message = f"IBMSubnet '{resource_id}' not found"
            db_session.commit()
            LOGGER.error(workflow_task.message)
            return

        region_name = subnet.region.name
        subnet_resource_id = subnet.resource_id
        cloud_id = subnet.cloud_id

    try:
        client = SubnetsClient(cloud_id, region=region_name)
        client.delete_subnet(subnet_resource_id)
        ibm_subnet_json = client.get_subnet(subnet_resource_id)

    except ApiException as ex:
        with get_db_session() as db_session:
            workflow_task: WorkflowTask = db_session.query(WorkflowTask).get(workflow_task_id)
            if not workflow_task:
                return

            if ex.code == 404:
                subnet = db_session.query(IBMSubnet).get(workflow_task.resource_id)
                if subnet:
                    subnet_json = subnet.to_json()
                    subnet_json["created_at"] = str(subnet_json["created_at"])

                    IBMResourceLog(
                        resource_id=subnet.resource_id, region=subnet.zone.region,
                        status=IBMResourceLog.STATUS_DELETED, resource_type=IBMSubnet.__name__,
                        data=subnet_json)

                    db_session.delete(subnet)

                workflow_task.status = WorkflowTask.STATUS_SUCCESSFUL
                LOGGER.success(
                    f"IBM Subnet {workflow_task.resource_id} for cloud {cloud_id} deletion successful.")
                db_session.commit()
                return
            else:
                workflow_task.status = WorkflowTask.STATUS_FAILED
                message = f"Cannot delete the subnet {workflow_task.resource_id} due to reason: {str(ex.message)}"
                workflow_task.message = message
                db_session.commit()
                LOGGER.fail(message)
                return

    with get_db_session() as db_session:
        workflow_task: WorkflowTask = db_session.query(WorkflowTask).get(workflow_task_id)
        if not workflow_task:
            return

        subnet_status = ibm_subnet_json["status"]
        subnet_name = ibm_subnet_json["name"]
        if subnet_status in [IBMSubnet.STATUS_DELETING, IBMSubnet.STATUS_PENDING]:
            workflow_task.status = WorkflowTask.STATUS_RUNNING_WAIT
            message = f"IBM Subnet {subnet_name} for cloud {subnet.cloud_id} deletion waiting"
            LOGGER.info(message)
        else:
            message = f"IBM Subnet {subnet_name} for cloud {subnet.cloud_id} deletion failed"
            workflow_task.message = message
            workflow_task.status = WorkflowTask.STATUS_FAILED
            LOGGER.error(message)

        db_session.commit()


@celery.task(name="delete_wait_subnet", base=IBMWorkflowTasksBase)
def delete_wait_subnet(workflow_task_id):
    """
    Wait for an IBM Subnet deletion on IBM Cloud
    :param workflow_task_id:
    :return:
    """
    with get_db_session() as db_session:
        workflow_task: WorkflowTask = db_session.query(WorkflowTask).get(workflow_task_id)
        if not workflow_task:
            return

        workflow_task.status = WorkflowTask.STATUS_RUNNING
        db_session.commit()

        subnet: IBMSubnet = db_session.query(IBMSubnet).get(workflow_task.resource_id)
        if not subnet:
            workflow_task.status = WorkflowTask.STATUS_SUCCESSFUL
            db_session.commit()
            LOGGER.success(f"IBM Subnet {workflow_task.resource_id} deletion successful.")
            return

        region_name = subnet.region.name
        subnet_resource_id = subnet.resource_id
        cloud_id = subnet.cloud_id

    try:
        client = SubnetsClient(cloud_id, region=region_name)
        ibm_subnet_json = client.get_subnet(subnet_id=subnet_resource_id)

    except ApiException as ex:
        with get_db_session() as db_session:
            workflow_task: WorkflowTask = db_session.query(WorkflowTask).get(workflow_task_id)
            if not workflow_task:
                return

            if ex.code == 404:
                subnet = db_session.query(IBMSubnet).get(workflow_task.resource_id)
                if subnet:
                    subnet_json = subnet.to_json()
                    subnet_json["created_at"] = str(subnet_json["created_at"])

                    IBMResourceLog(
                        resource_id=subnet.resource_id, region=subnet.zone.region,
                        status=IBMResourceLog.STATUS_DELETED, resource_type=IBMSubnet.__name__,
                        data=subnet_json)

                    db_session.delete(subnet)

                workflow_task.status = WorkflowTask.STATUS_SUCCESSFUL
                LOGGER.success(
                    f"IBM Subnet {workflow_task.resource_id} for cloud {cloud_id} deletion successful.")
                db_session.commit()
                return
            else:
                workflow_task.status = WorkflowTask.STATUS_FAILED
                message = f"Cannot delete the subnet {workflow_task.resource_id} due to reason: {str(ex.message)}"
                workflow_task.message = message
                db_session.commit()
                LOGGER.fail(message)
                return

    with get_db_session() as db_session:
        workflow_task: WorkflowTask = db_session.query(WorkflowTask).get(workflow_task_id)
        if not workflow_task:
            return

        if ibm_subnet_json["status"] in [IBMSubnet.STATUS_DELETING, IBMSubnet.STATUS_PENDING]:
            workflow_task.status = WorkflowTask.STATUS_RUNNING_WAIT
            message = f"IBM Subnet {subnet.name} for cloud {subnet.cloud_id} deletion waiting"
            LOGGER.info(message)
        else:
            message = f"IBM Subnet {subnet.name} for cloud {subnet.cloud_id} deletion failed"
            workflow_task.message = message
            workflow_task.status = WorkflowTask.STATUS_FAILED
            LOGGER.error(message)

        db_session.commit()


@celery.task(name="attach_public_gateway_to_subnet", base=IBMWorkflowTasksBase)
def attach_public_gateway_to_subnet(workflow_task_id):
    """
    Attach a Public Gateway to IBM Subnet on IBM Cloud
    """
    with get_db_session() as db_session:
        workflow_task = db_session.query(WorkflowTask).filter_by(id=workflow_task_id).first()
        if not workflow_task:
            return

        workflow_task.status = WorkflowTask.STATUS_RUNNING
        db_session.commit()

        resource_data = deepcopy(workflow_task.task_metadata["resource_data"])
        public_gateway_dict = resource_data["public_gateway"]
        vpc_dict = resource_data.get("vpc")
        subnet_dict = resource_data["subnet"]

        previous_resources = load_previous_associated_resources(task=workflow_task, session=db_session)
        subnet = previous_resources.get(subnet_dict["id"]) or db_session.query(IBMSubnet).filter_by(
            **subnet_dict).first()
        if not subnet:
            subnet_id_or_name = subnet_dict.get('id') or subnet_dict.get('name')
            workflow_task.status = WorkflowTask.STATUS_FAILED
            workflow_task.message = f"IBMSubnet '{subnet_id_or_name}' not found"
            db_session.commit()
            LOGGER.error(workflow_task.message)
            return

        region_name = subnet.zone.region.name
        cloud_id = subnet.ibm_cloud.id
        subnet_resource_id = subnet.resource_id
        if not vpc_dict:
            vpc_dict = {"id": subnet.vpc_id}
        vpc = db_session.query(IBMVpcNetwork).filter_by(**vpc_dict).first()
        if not vpc:
            workflow_task.status = WorkflowTask.STATUS_FAILED
            workflow_task.message = f"IBM Vpc {vpc_dict.get('id') or vpc_dict.get('name')} not found"
            db_session.commit()
            LOGGER.error(workflow_task.message)
            return

        public_gateway = previous_resources.get(public_gateway_dict["id"]) or db_session.query(
            IBMPublicGateway).filter_by(**public_gateway_dict).first()
        if not public_gateway:
            public_gateway_id_or_name = public_gateway_dict.get('id') or public_gateway_dict.get('name')
            workflow_task.status = WorkflowTask.STATUS_FAILED
            workflow_task.message = f"IBM Public Gateway with {public_gateway_id_or_name} not found"
            db_session.commit()
            LOGGER.error(workflow_task.message)
            return

        public_gateway_resource_id = public_gateway.resource_id
    try:
        client = SubnetsClient(cloud_id, region=region_name)
        resp_json = client.attach_pg_to_subnet(
            subnet_id=subnet_resource_id, attach_pg_json={"id": public_gateway_resource_id})
    except ApiException as ex:
        with get_db_session() as db_session:
            workflow_task = db_session.query(WorkflowTask).filter_by(id=workflow_task_id).first()
            if not workflow_task:
                return

            workflow_task.status = WorkflowTask.STATUS_FAILED
            workflow_task.message = f"Attachment Failed. Reason: {str(ex.message)}"
            db_session.commit()

        LOGGER.error(workflow_task.message)
        return

    with get_db_session() as db_session:
        workflow_task = db_session.query(WorkflowTask).filter_by(id=workflow_task_id).first()
        if not workflow_task:
            return

        if resp_json["status"] == IBMSubnet.STATUS_FAILED:
            message = f"IBM Public Gateway {public_gateway_dict.get('id') or public_gateway_dict.get('name')} " \
                      f"attached with subnet failed '{subnet_resource_id}'"
            workflow_task.message = message
            workflow_task.status = WorkflowTask.STATUS_FAILED
            LOGGER.error(message)
            return

        metadata = deepcopy(workflow_task.task_metadata.copy() if workflow_task.task_metadata else {})
        metadata["ibm_resource_id"] = resp_json["id"]
        metadata["subnet"] = subnet_dict
        metadata["cloud_id"] = cloud_id
        workflow_task.task_metadata = metadata

        workflow_task.status = WorkflowTask.STATUS_RUNNING_WAIT
        message = f"IBM Public Gateway {public_gateway_dict.get('id') or public_gateway_dict.get('name')} " \
                  f"attached with subnet waiting '{subnet_dict.get('id') or subnet_dict.get('name')}'"
        db_session.commit()

        LOGGER.info(message)


@celery.task(name="attach_wait_public_gateway_to_subnet", base=IBMWorkflowTasksBase)
def attach_wait_public_gateway_to_subnet(workflow_task_id):
    """
    Attach a Public Gateway to IBM Subnet on IBM Cloud
    """

    with get_db_session() as db_session:
        workflow_task = db_session.query(WorkflowTask).filter_by(id=workflow_task_id).first()
        if not workflow_task:
            return

        workflow_task.status = WorkflowTask.STATUS_RUNNING
        db_session.commit()

        cloud_id = workflow_task.task_metadata["cloud_id"]
        region_id = workflow_task.task_metadata["resource_data"].get("region", {}).get("id")
        subnet_dict = deepcopy(workflow_task.task_metadata["subnet"])

        previous_resources = load_previous_associated_resources(task=workflow_task, session=db_session)

        subnet = previous_resources.get(subnet_dict["id"]) or db_session.query(IBMSubnet).filter_by(
            **subnet_dict).first()
        if not subnet:
            subnet_id_or_name = subnet_dict.get('id') or subnet_dict.get('name')
            workflow_task.status = WorkflowTask.STATUS_FAILED
            workflow_task.message = f"IBMSubnet '{subnet_id_or_name}' not found"
            db_session.commit()
            LOGGER.error(workflow_task.message)
            return

        subnet_resource_id = subnet.resource_id
        if not region_id:
            region_id = subnet.region.id

        region = db_session.query(IBMRegion).filter_by(id=region_id, cloud_id=cloud_id).first()
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

    try:
        client = SubnetsClient(cloud_id=cloud_id, region=region_name)
        public_gateway_json = client.get_attached_pg_to_subnet(subnet_id=subnet_resource_id)
    except ApiException as ex:
        with get_db_session() as db_session:
            workflow_task = db_session.query(WorkflowTask).filter_by(id=workflow_task_id).first()
            if not workflow_task:
                return

            workflow_task.status = WorkflowTask.STATUS_FAILED
            workflow_task.message = f"Get Public Gateway Attachment Failed. Reason: {str(ex.message)}"
            db_session.commit()

        LOGGER.error(workflow_task.message)
        return

    with get_db_session() as db_session:
        workflow_task = db_session.query(WorkflowTask).filter_by(id=workflow_task_id).first()
        if not workflow_task:
            return

        public_gateway_name = public_gateway_json["name"]
        public_gateway_resource_id = public_gateway_json["id"]
        attachment_status = public_gateway_json["status"]
        if attachment_status == IBMSubnet.STATUS_FAILED:
            workflow_task.status = WorkflowTask.STATUS_FAILED
            workflow_task.message = \
                f"IBM Public Gateway '{public_gateway_json['name']}' attachment with for cloud '{cloud_id}' failed" \
                f" on IBM Cloud"
            db_session.commit()
            LOGGER.error(workflow_task.message)
            return
        elif attachment_status == IBMSubnet.STATUS_PENDING:
            LOGGER.info(f"IBM Public Gateway '{public_gateway_name}' attachment for cloud '{cloud_id}' waiting")
            workflow_task.status = WorkflowTask.STATUS_RUNNING_WAIT
            db_session.commit()
            return

        with db_session.no_autoflush:
            public_gateway = db_session.query(IBMPublicGateway).filter_by(
                resource_id=public_gateway_resource_id, cloud_id=cloud_id).first()

            if not public_gateway:
                workflow_task.status = WorkflowTask.STATUS_FAILED
                workflow_task.message = \
                    "Attachment Successful but record update failed. The records will update next time discovery runs"
                db_session.commit()
                LOGGER.note(workflow_task.message)
                return

            subnet = previous_resources.get(subnet_dict["id"]) or db_session.query(IBMSubnet).filter_by(
                id=subnet_dict["id"], cloud_id=cloud_id).first()
            if not subnet:
                workflow_task.status = WorkflowTask.STATUS_FAILED
                workflow_task.message = f"IBM subnet with id " \
                                        f"'{subnet_dict.get('id') or subnet_dict.get('name')}' not found"
                db_session.commit()
                LOGGER.error(workflow_task.message)
                return

            subnet.public_gateway = public_gateway
            workflow_task.status = WorkflowTask.STATUS_SUCCESSFUL
            db_session.commit()

        LOGGER.success(f"IBM Public Gateway {public_gateway_name} attached with subnet '{subnet.id}' successful")


@celery.task(name="detach_public_gateway_from_subnet", base=IBMWorkflowTasksBase)
def detach_public_gateway_from_subnet(workflow_task_id):
    """
    Detach a Target (Public Gateway) from IBM Subnet on IBM Cloud
    """
    with get_db_session() as db_session:
        workflow_task = db_session.query(WorkflowTask).filter_by(id=workflow_task_id).first()
        if not workflow_task:
            return

        workflow_task.status = WorkflowTask.STATUS_RUNNING
        db_session.commit()

        task_metadata = deepcopy(workflow_task.task_metadata)
        resource_data = deepcopy(task_metadata["resource_data"])
        subnet_dict = resource_data["subnet"]
        region_id = resource_data["region"]["id"]

        region = db_session.query(IBMRegion).filter_by(id=region_id).first()
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

        subnet = db_session.query(IBMSubnet).filter_by(
            **subnet_dict, region_id=region_id).first()

        if not subnet:
            workflow_task.status = WorkflowTask.STATUS_FAILED
            workflow_task.message = f"IBM Subnet with id {subnet_dict.get('id')}' not found"
            db_session.commit()
            LOGGER.error(workflow_task.message)
            return

        cloud_id = subnet.cloud_id
        subnet_resource_id = subnet.resource_id
        region_name = region.name

    try:
        client = SubnetsClient(cloud_id=cloud_id, region=region_name)
        client.detach_pg_from_subnet(subnet_id=subnet_resource_id)

    except ApiException as ex:
        with get_db_session() as db_session:
            workflow_task = db_session.query(WorkflowTask).filter_by(id=workflow_task_id).first()
            if not workflow_task:
                return

            if ex.code == 404:  # 404 means resource is not found on IBM Cloud.
                subnet = db_session.query(IBMSubnet).filter_by(
                    resource_id=subnet_resource_id).first()
                if subnet:
                    subnet.public_gateway = None

                workflow_task.status = WorkflowTask.STATUS_SUCCESSFUL
                LOGGER.success(f"Detachment of IBM Public Gateway with "
                               f"subnet {subnet_dict.get('id') or subnet_dict.get('name')} successful.")
                db_session.commit()
                return

            message = f"Detachment of IBM Public Gateway with " \
                      f"subnet {subnet_dict.get('id') or subnet_dict.get('name')} failed. Reason: {str(ex.message)}"
            LOGGER.error(message)
            workflow_task.status = WorkflowTask.STATUS_FAILED
            workflow_task.message = message
            db_session.commit()
            return

    with get_db_session() as db_session:
        workflow_task = db_session.query(WorkflowTask).filter_by(id=workflow_task_id).first()
        if not workflow_task:
            return

        subnet = db_session.query(IBMSubnet).filter_by(
            **subnet_dict, region_id=region_id, cloud_id=cloud_id).first()

        if not subnet:
            workflow_task.status = WorkflowTask.STATUS_FAILED
            workflow_task.message = f"IBM Subnet {subnet_dict.get('id') or subnet_dict.get('name')}' not found"
            db_session.commit()
            LOGGER.error(workflow_task.message)
            return

        subnet.public_gateway = None

        workflow_task.resource_id = subnet.id
        workflow_task.status = WorkflowTask.STATUS_SUCCESSFUL
        db_session.commit()

    LOGGER.success(f"Detachment of IBM Public Gateway "
                   f"with subnet {subnet_dict.get('id') or subnet_dict.get('name')} successful.")


@celery.task(name="attach_routing_table_to_subnet", base=IBMWorkflowTasksBase)
def attach_routing_table_to_subnet(workflow_task_id):
    """
    Attach a Routing Table to IBM Subnet on IBM Cloud
    """
    with get_db_session() as db_session:
        workflow_task = db_session.query(WorkflowTask).filter_by(id=workflow_task_id).first()
        if not workflow_task:
            return

        workflow_task.status = WorkflowTask.STATUS_RUNNING
        db_session.commit()

        resource_data = deepcopy(workflow_task.task_metadata["resource_data"])
        routing_table_dict = resource_data["routing_table"]
        vpc_dict = resource_data["vpc"]
        subnet_dict = resource_data["subnet"]

        subnet = db_session.query(IBMSubnet).filter_by(**subnet_dict).first()
        if not subnet:
            workflow_task.status = WorkflowTask.STATUS_FAILED
            workflow_task.message = f"IBMSubnet " \
                                    f"'{subnet_dict.get('id') or subnet_dict.get('name')}' not found"
            db_session.commit()
            LOGGER.error(workflow_task.message)
            return

        region_name = subnet.zone.region.name
        cloud_id = subnet.ibm_cloud.id
        subnet_resource_id = subnet.resource_id

        vpc = db_session.query(IBMVpcNetwork).filter_by(**vpc_dict).first()
        if not vpc:
            workflow_task.status = WorkflowTask.STATUS_FAILED
            workflow_task.message = f"IBM Vpc {vpc_dict.get('id') or vpc_dict.get('name')} not found"
            db_session.commit()
            LOGGER.error(workflow_task.message)
            return

        routing_table = db_session.query(IBMRoutingTable).filter_by(**routing_table_dict, cloud_id=cloud_id).first()
        if not routing_table:
            workflow_task.status = WorkflowTask.STATUS_FAILED
            workflow_task.message = f"IBM Routing Table " \
                                    f"with {routing_table_dict.get('id') or routing_table_dict.get('name')} not found"
            db_session.commit()
            LOGGER.error(workflow_task.message)
            return

        routing_table_resource_id = routing_table.resource_id
    try:
        client = SubnetsClient(cloud_id, region=region_name)
        resp_json = client.attach_routing_table_to_subnet(
            region=region_name, subnet_id=subnet_resource_id, routing_table_json={"id": routing_table_resource_id}
        )
    except (IBMAuthError, IBMConnectError, IBMExecuteError, IBMInvalidRequestError) as ex:
        with get_db_session() as db_session:
            workflow_task = db_session.query(WorkflowTask).filter_by(id=workflow_task_id).first()
            if not workflow_task:
                return

            workflow_task.status = WorkflowTask.STATUS_FAILED
            workflow_task.message = f"Attachment Failed. Reason: {str(ex)}"
            db_session.commit()

        LOGGER.error(str(ex))
        return

    with get_db_session() as db_session:
        workflow_task = db_session.query(WorkflowTask).filter_by(id=workflow_task_id).first()
        if not workflow_task:
            return

        if resp_json["lifecycle_state"] in [
            IBMRoutingTable.LIFECYCLE_STATE_FAILED, IBMRoutingTable.LIFECYCLE_STATE_SUSPENDED
        ]:
            message = f"IBM Routing Table {routing_table_dict.get('id') or routing_table_dict.get('name')} " \
                      f"attached with subnet failed '{subnet_resource_id}'"
            workflow_task.message = message
            workflow_task.status = WorkflowTask.STATUS_FAILED
            LOGGER.error(message)
            return

        metadata = deepcopy(workflow_task.task_metadata.copy() if workflow_task.task_metadata else {})
        metadata["ibm_resource_id"] = resp_json["id"]
        metadata["subnet"] = subnet_dict
        metadata["cloud_id"] = cloud_id
        workflow_task.task_metadata = metadata

        workflow_task.status = WorkflowTask.STATUS_RUNNING_WAIT
        message = f"IBM Routing Table {routing_table_dict.get('id') or routing_table_dict.get('name')} " \
                  f"attached with subnet waiting '{subnet_dict.get('id') or subnet_dict.get('name')}'"
        db_session.commit()

        LOGGER.info(message)


@celery.task(name="attach_wait_routing_table_to_subnet", base=IBMWorkflowTasksBase)
def attach_wait_routing_table_to_subnet(workflow_task_id):
    """
    Attach wait a Routing Table to IBM Subnet on IBM Cloud
    """

    with get_db_session() as db_session:
        workflow_task = db_session.query(WorkflowTask).filter_by(id=workflow_task_id).first()
        if not workflow_task:
            return

        workflow_task.status = WorkflowTask.STATUS_RUNNING
        db_session.commit()

        cloud_id = workflow_task.task_metadata["cloud_id"]
        region_id = workflow_task.task_metadata["resource_data"]["region"]["id"]
        subnet_dict = deepcopy(workflow_task.task_metadata["subnet"])

        subnet = db_session.query(IBMSubnet).filter_by(**subnet_dict, cloud_id=cloud_id).first()
        if not subnet:
            workflow_task.status = WorkflowTask.STATUS_FAILED
            workflow_task.message = f"IBMSubnet " \
                                    f"'{subnet_dict.get('id') or subnet_dict.get('name')}' not found"
            db_session.commit()
            LOGGER.error(workflow_task.message)
            return

        subnet_resource_id = subnet.resource_id

        region = db_session.query(IBMRegion).filter_by(id=region_id, cloud_id=cloud_id).first()
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

    try:
        client = SubnetsClient(cloud_id=cloud_id, region=region_name)
        routing_table_json = client.get_routing_table_attached_to_subnet(subnet_id=subnet_resource_id)
    except ApiException as ex:
        with get_db_session() as db_session:
            workflow_task = db_session.query(WorkflowTask).filter_by(id=workflow_task_id).first()
            if not workflow_task:
                return

            workflow_task.status = WorkflowTask.STATUS_FAILED
            workflow_task.message = f"Get Routing Table Attachment Failed. Reason: {str(ex.message)}"
            db_session.commit()

        LOGGER.error(str(ex.message))
        return

    with get_db_session() as db_session:
        workflow_task = db_session.query(WorkflowTask).filter_by(id=workflow_task_id).first()
        if not workflow_task:
            return

        routing_table_name = routing_table_json["name"]
        routing_table_resource_id = routing_table_json["id"]
        attachment_status = routing_table_json["lifecycle_state"]
        if attachment_status in [
            IBMRoutingTable.LIFECYCLE_STATE_UPDATING, IBMRoutingTable.LIFECYCLE_STATE_WAITING,
            IBMRoutingTable.LIFECYCLE_STATE_PENDING
        ]:
            LOGGER.info(f"IBM Routing Table '{routing_table_name}' attachment for cloud '{cloud_id}' waiting")
            workflow_task.status = WorkflowTask.STATUS_RUNNING_WAIT
            db_session.commit()
            return
        elif attachment_status in [IBMRoutingTable.LIFECYCLE_STATE_FAILED, IBMRoutingTable.LIFECYCLE_STATE_SUSPENDED]:
            workflow_task.status = WorkflowTask.STATUS_FAILED
            workflow_task.message = \
                f"IBM Routing Table '{routing_table_name}' attachment with for cloud '{cloud_id}' failed on IBM Cloud"
            db_session.commit()
            LOGGER.error(workflow_task.message)
            return

        with db_session.no_autoflush:
            routing_table = db_session.query(IBMRoutingTable).filter_by(
                resource_id=routing_table_resource_id, cloud_id=cloud_id).first()

            if not routing_table:
                workflow_task.status = WorkflowTask.STATUS_FAILED
                workflow_task.message = \
                    "Attachment Successful but record update failed. The records will update next time discovery runs"
                db_session.commit()
                LOGGER.note(workflow_task.message)
                return

            subnet = db_session.query(IBMSubnet).filter_by(**subnet_dict).first()
            if not subnet:
                workflow_task.status = WorkflowTask.STATUS_FAILED
                workflow_task.message = f"IBM subnet with id " \
                                        f"'{subnet_dict.get('id') or subnet_dict.get('name')}' not found"
                db_session.commit()
                LOGGER.error(workflow_task.message)
                return

            subnet.routing_table = routing_table
            workflow_task.status = WorkflowTask.STATUS_SUCCESSFUL
            db_session.commit()

        LOGGER.success(f"IBM Routing Table {routing_table_name} attached with subnet '{subnet.id}' successful")


@celery.task(name="reserve_ip_for_subnet", base=IBMWorkflowTasksBase)
def reserve_ip_for_subnet(workflow_task_id):
    """
    Reserved an Ip for IBM Subnet on IBM Cloud
    """
    with get_db_session() as db_session:
        workflow_task = db_session.query(WorkflowTask).filter_by(id=workflow_task_id).first()
        if not workflow_task:
            return

        workflow_task.status = WorkflowTask.STATUS_RUNNING
        db_session.commit()

        resource_data = deepcopy(workflow_task.task_metadata["resource_data"])
        resource_json = deepcopy(resource_data["resource_json"])
        subnet_dict = resource_json["subnet"]
        cloud_id = resource_data["ibm_cloud"]["id"]
        region_id = resource_data["region"]["id"]

        region = db_session.query(IBMRegion).filter_by(id=region_id, cloud_id=cloud_id).first()
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

        previous_resources = load_previous_associated_resources(task=workflow_task, session=db_session)
        update_id_or_name_references(
            cloud_id=cloud_id, resource_json=resource_data, resource_schema=IBMReservedIpInSchema,
            db_session=db_session, previous_resources=previous_resources
        )

        update_id_or_name_references(
            cloud_id=cloud_id, resource_json=resource_json, resource_schema=IBMReservedIpResourceSchema,
            db_session=db_session, previous_resources=previous_resources
        )

        subnet = db_session.query(IBMSubnet).filter_by(**subnet_dict).first()
        if not subnet:
            workflow_task.status = WorkflowTask.STATUS_FAILED
            workflow_task.message = f"IBMSubnet " \
                                    f"'{subnet_dict.get('id') or subnet_dict.get('name')}' not found"
            db_session.commit()
            LOGGER.error(workflow_task.message)
            return

        subnet_resource_id = subnet.resource_id
        region_name = region.name

    try:
        client = SubnetsClient(cloud_id=cloud_id, region=region_name)
        resp_json = client.reserve_ip_in_subnet(subnet_id=subnet_resource_id, reserve_ip_json=resource_json)
    except ApiException as ex:
        with get_db_session() as db_session:
            workflow_task = db_session.query(WorkflowTask).filter_by(id=workflow_task_id).first()
            if not workflow_task:
                return

            workflow_task.status = WorkflowTask.STATUS_FAILED
            workflow_task.message = f"Attachment Failed. Reason: {str(ex.message)}"
            db_session.commit()

        LOGGER.error(str(ex.message))
        return

    with get_db_session() as db_session:
        workflow_task = db_session.query(WorkflowTask).filter_by(id=workflow_task_id).first()
        if not workflow_task:
            return

        with db_session.no_autoflush:
            subnet = db_session.query(IBMSubnet).filter_by(**subnet_dict).first()
            if not subnet:
                workflow_task.status = WorkflowTask.STATUS_FAILED
                workflow_task.message = \
                    "Reservation Successful but record update failed. The records will update next time discovery runs"
                db_session.commit()
                LOGGER.note(workflow_task.message)
                return

            reserve_ip = IBMSubnetReservedIp.from_ibm_json_body(resp_json)
            reserve_ip.subnet = subnet
            db_session.commit()

        workflow_task.status = WorkflowTask.STATUS_SUCCESSFUL
        db_session.commit()

    LOGGER.success(f"IBM Subnet Reserved Ip '{resp_json['name']}' attachment for cloud '{cloud_id}' successful")


@celery.task(name="release_reserved_ip_for_subnet", base=IBMWorkflowTasksBase)
def release_reserved_ip_for_subnet(workflow_task_id):
    """
    Release an Ip for IBM Subnet on IBM Cloud
    """
    with get_db_session() as db_session:
        workflow_task = db_session.query(WorkflowTask).filter_by(id=workflow_task_id).first()
        if not workflow_task:
            return

        workflow_task.status = WorkflowTask.STATUS_RUNNING
        db_session.commit()

        reserve_ip_id = workflow_task.resource_id

        reserve_ip = db_session.query(IBMSubnetReservedIp).filter_by(id=reserve_ip_id).first()
        if not reserve_ip:
            workflow_task.status = WorkflowTask.STATUS_FAILED
            workflow_task.message = f"IBMSubnetReservedIp '{reserve_ip_id}' not found"
            db_session.commit()
            LOGGER.success(workflow_task.message)
            return

        region_name = reserve_ip.subnet.zone.region.name
        cloud_id = reserve_ip.subnet.ibm_cloud.id
        subnet_resource_id = reserve_ip.subnet.resource_id
        reserve_ip_resource_id = reserve_ip.resource_id

    try:
        client = SubnetsClient(cloud_id, region=region_name)
        client.release_subnet_reserved_ip(subnet_id=subnet_resource_id, reserved_ip_id=reserve_ip_resource_id)

    except ApiException as ex:
        with get_db_session() as db_session:
            workflow_task = db_session.query(WorkflowTask).filter_by(id=workflow_task_id).first()
            if not workflow_task:
                return

            if ex.code == 404:
                reserve_ip = db_session.query(IBMSubnetReservedIp).filter_by(id=reserve_ip_id).first()
                if reserve_ip:
                    db_session.delete(reserve_ip)

                workflow_task.status = WorkflowTask.STATUS_SUCCESSFUL
                workflow_task.message = f"Deletion successful for reserved ip {workflow_task.resource_id}"
                db_session.commit()
                LOGGER.success(workflow_task.message)
            else:
                workflow_task.status = WorkflowTask.STATUS_FAILED
                workflow_task.message = f"Detachment Failed. Reason: {str(ex.message)}"
                db_session.commit()
                LOGGER.fail(workflow_task.message)

        return

    with get_db_session() as db_session:
        workflow_task = db_session.query(WorkflowTask).filter_by(id=workflow_task_id).first()
        if not workflow_task:
            return

        with db_session.no_autoflush:
            reserve_ip = db_session.query(IBMSubnetReservedIp).filter_by(id=reserve_ip_id).first()
            if reserve_ip:
                db_session.delete(reserve_ip)

            workflow_task.status = WorkflowTask.STATUS_SUCCESSFUL
            workflow_task.message = f"Deletion successful for reserved ip {workflow_task.resource_id}"
            LOGGER.success(workflow_task.message)
            db_session.commit()
