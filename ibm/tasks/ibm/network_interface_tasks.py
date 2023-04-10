from copy import deepcopy

from ibm_cloud_sdk_core import ApiException

from ibm import get_db_session, LOGGER
from ibm.common.clients.ibm_clients import InstancesClient
from ibm.common.utils import update_id_or_name_references
from ibm.models import IBMFloatingIP, IBMInstance, IBMNetworkInterface, IBMRegion, IBMResourceLog, IBMSecurityGroup, \
    IBMSubnet, IBMZone, WorkflowTask, IBMPublicGateway
from ibm.tasks.celery_app import celery_app as celery
from ibm.tasks.common.tasks_base import IBMWorkflowTasksBase
from ibm.tasks.ibm.task_utils import load_previous_associated_resources
from ibm.web.ibm.instances.network_interfaces.schemas import IBMInstanceNetworkInterfaceInSchema, \
    IBMInstanceNetworkInterfaceResourceSchema


@celery.task(name="create_ibm_network_interface", base=IBMWorkflowTasksBase)
def create_ibm_network_interface(workflow_task_id):
    """
    Create an IBM Network Interface on IBM Cloud Instance
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
        instance_id = resource_data["instance"]["id"]

        region = db_session.query(IBMRegion).filter_by(id=region_id, cloud_id=cloud_id).first()
        if not region:
            workflow_task.status = WorkflowTask.STATUS_FAILED
            workflow_task.message = f"IBMRegion '{region_id}' not found"
            db_session.commit()
            LOGGER.info(workflow_task.message)
            return

        if region.ibm_status == IBMZone.IBM_STATUS_UNAVAILABLE:
            workflow_task.status = WorkflowTask.STATUS_FAILED
            workflow_task.message = f"IBMRegion '{region.name}' unavailable"
            db_session.commit()
            LOGGER.info(workflow_task.message)
            return

        instance = db_session.query(IBMInstance).filter_by(id=instance_id, cloud_id=cloud_id).first()
        if not instance:
            workflow_task.status = WorkflowTask.STATUS_FAILED
            workflow_task.message = f"IBMInstance '{instance_id}' not found"
            db_session.commit()
            LOGGER.info(workflow_task.message)
            return
        instance_resource_id = instance.resource_id
        region_name = region.name
        previous_resources = load_previous_associated_resources(task=workflow_task, session=db_session)
        update_id_or_name_references(
            cloud_id=cloud_id, resource_json=resource_data, resource_schema=IBMInstanceNetworkInterfaceInSchema,
            db_session=db_session, previous_resources=previous_resources
        )
        update_id_or_name_references(
            cloud_id=cloud_id, resource_json=resource_json, resource_schema=IBMInstanceNetworkInterfaceResourceSchema,
            db_session=db_session, previous_resources=previous_resources
        )
    try:
        client = InstancesClient(cloud_id=cloud_id, region=region_name)
        resp_json = client.create_network_interface(instance_id=instance_resource_id,
                                                    network_interface_json=resource_json)
    except ApiException as ex:
        with get_db_session() as db_session:
            workflow_task = db_session.query(WorkflowTask).filter_by(id=workflow_task_id).first()
            if not workflow_task:
                return

            workflow_task.status = WorkflowTask.STATUS_FAILED
            workflow_task.message = f"Creation Failed. Reason: {str(ex.message)}"
            db_session.commit()

        LOGGER.info("Create Instance Network interface failed with status code " + str(ex.code) + ": " + ex.message)
        return

    with get_db_session() as db_session:
        workflow_task = db_session.query(WorkflowTask).filter_by(id=workflow_task_id).first()
        if not workflow_task:
            return

        network_interface_status = resp_json["status"]
        network_interface_name = resp_json["name"]
        network_interface_resource_id = resp_json["id"]
        if network_interface_status in [IBMNetworkInterface.STATUS_AVAILABLE, IBMNetworkInterface.STATUS_PENDING]:
            metadata = workflow_task.task_metadata.copy() if workflow_task.task_metadata else {}
            metadata["ibm_resource_id"] = network_interface_resource_id
            workflow_task.task_metadata = metadata
            workflow_task.status = WorkflowTask.STATUS_RUNNING_WAIT
            message = f"IBM Network Interface {network_interface_name} for cloud {cloud_id} creation waiting"
        else:
            message = f"IBM Network Interface {network_interface_name} for cloud {cloud_id} creation failed"
            workflow_task.message = message
            workflow_task.status = WorkflowTask.STATUS_FAILED
        db_session.commit()
    LOGGER.info(message)


@celery.task(name="create_wait_ibm_network_interface", base=IBMWorkflowTasksBase)
def create_wait_ibm_network_interface(workflow_task_id):
    """
    Wait for an IBM Network Interface on IBM Cloud Instance to get available
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
        instance_id = resource_data["instance"]["id"]

        region = db_session.query(IBMRegion).filter_by(id=region_id, cloud_id=cloud_id).first()
        if not region:
            workflow_task.status = WorkflowTask.STATUS_FAILED
            workflow_task.message = f"IBMRegion '{region_id}' not found"
            db_session.commit()
            LOGGER.info(workflow_task.message)
            return

        if region.ibm_status == IBMZone.IBM_STATUS_UNAVAILABLE:
            workflow_task.status = WorkflowTask.STATUS_FAILED
            workflow_task.message = f"IBMRegion '{region.name}' unavailable"
            db_session.commit()
            LOGGER.info(workflow_task.message)
            return
        instance = db_session.query(IBMInstance).filter_by(id=instance_id, cloud_id=cloud_id).first()
        if not instance:
            workflow_task.status = WorkflowTask.STATUS_FAILED
            workflow_task.message = f"IBMInstance '{instance_id}' not found"
            db_session.commit()
            LOGGER.info(workflow_task.message)
            return

        region_name = region.name
        resource_id = workflow_task.task_metadata["ibm_resource_id"]

    try:
        client = InstancesClient(cloud_id=cloud_id, region=region_name)
        network_interface_json = client.get_instance_network_interface(instance_id=instance.resource_id,
                                                                       network_interface_id=resource_id)
    except ApiException as ex:
        with get_db_session() as db_session:
            workflow_task = db_session.query(WorkflowTask).filter_by(id=workflow_task_id).first()
            if not workflow_task:
                return

            workflow_task.status = WorkflowTask.STATUS_FAILED
            workflow_task.message = f"Creation Failed. Reason: {str(ex.message)}"
            db_session.commit()

        LOGGER.info(
            "Create Wait Instance Network interface failed with status code " + str(ex.code) + ": " + ex.message)
        return

    with get_db_session() as db_session:
        workflow_task = db_session.query(WorkflowTask).filter_by(id=workflow_task_id).first()
        if not workflow_task:
            return

        if network_interface_json["status"] in [IBMNetworkInterface.STATUS_FAILED, IBMNetworkInterface.STATUS_DELETING]:
            workflow_task.status = WorkflowTask.STATUS_FAILED
            workflow_task.message = f"IBM Network Interface '{network_interface_json['name']}' creation for cloud '" \
                                    f"{cloud_id}' " \
                                    f"failed on IBM Cloud"
            db_session.commit()
            LOGGER.info(workflow_task.message)
            return

        elif network_interface_json["status"] == IBMNetworkInterface.STATUS_PENDING:
            workflow_task.status = WorkflowTask.STATUS_RUNNING_WAIT
            db_session.commit()
            LOGGER.info(
                f"IBM Network Interface '{network_interface_json['name']}' creation for cloud '{cloud_id}' waiting")
            return
        elif network_interface_json["status"] == IBMNetworkInterface.STATUS_AVAILABLE:
            with db_session.no_autoflush:
                network_interface = IBMNetworkInterface.from_ibm_json_body(network_interface_json)
                # TODO Handle target json as well for FloatingIP and Public Gateway
                subnet = db_session.query(IBMSubnet).filter_by(resource_id=network_interface_json["subnet"]["id"],
                                                               cloud_id=cloud_id).first()
                if not subnet:
                    workflow_task.status = WorkflowTask.STATUS_FAILED
                    workflow_task.message = \
                        "Creation Successful but record update failed. The records will update next time " \
                        "discovery runs"
                    db_session.commit()
                    return

                for sg in network_interface_json["security_groups"]:
                    sg_obj = db_session.query(IBMSecurityGroup).filter_by(resource_id=sg["id"],
                                                                          cloud_id=cloud_id).first()
                    if sg_obj:
                        network_interface.security_groups.append(sg_obj)
                network_interface.cloud_id = cloud_id
                network_interface.instance_id = instance_id
                network_interface.subnet = subnet
                db_session.add(network_interface)
                db_session.commit()
            workflow_task.status = WorkflowTask.STATUS_SUCCESSFUL

            network_interface_json = network_interface.to_json()
            network_interface_json["created_at"] = str(network_interface_json["created_at"])

            IBMResourceLog(
                resource_id=network_interface.resource_id, region=network_interface.instance.zone.region,
                status=IBMResourceLog.STATUS_ADDED, resource_type=IBMNetworkInterface.__name__,
                data=network_interface_json)
            db_session.commit()
            LOGGER.info(
                f"IBM Network Interface '{network_interface_json['name']}' creation for cloud '{cloud_id}' successful")


@celery.task(name="delete_network_interface", base=IBMWorkflowTasksBase)
def delete_network_interface(workflow_task_id):
    """
    Delete an IBM Network Interface
    :param workflow_task_id:
    :return:
    """
    with get_db_session() as db_session:
        workflow_task: WorkflowTask = db_session.query(WorkflowTask).get(workflow_task_id)
        if not workflow_task:
            return

        workflow_task.status = WorkflowTask.STATUS_RUNNING
        db_session.commit()

        network_interface: IBMNetworkInterface = db_session.query(IBMNetworkInterface).get(workflow_task.resource_id)
        if not network_interface:
            workflow_task.status = WorkflowTask.STATUS_FAILED
            workflow_task.message = f"IBMNetworkInterface '{workflow_task.resource_id}' not found"
            db_session.commit()
            LOGGER.info(workflow_task.message)
            return

        region_name = network_interface.instance.region.name
        instance_resource_id = network_interface.instance.resource_id
        network_interface_resource_id = network_interface.resource_id
        cloud_id = network_interface.cloud_id

    try:
        client = InstancesClient(cloud_id, region=region_name)
        client.delete_instance_network_interface(instance_id=instance_resource_id,
                                                 network_interface_id=network_interface_resource_id
                                                 )
        network_interface_json = client.get_instance_network_interface(
            instance_id=instance_resource_id, network_interface_id=network_interface_resource_id
        )
    except ApiException as ex:
        with get_db_session() as db_session:
            workflow_task = db_session.query(WorkflowTask).get(workflow_task_id)
            if not workflow_task:
                return

            if ex.code == 404:
                network_interface = db_session.query(IBMNetworkInterface).get(workflow_task.resource_id)
                if network_interface:
                    network_interface_json = network_interface.to_json()
                    network_interface_json["created_at"] = str(network_interface_json["created_at"])

                    IBMResourceLog(
                        resource_id=network_interface.resource_id, region=network_interface.instance.zone.region,
                        status=IBMResourceLog.STATUS_DELETED, resource_type=IBMNetworkInterface.__name__,
                        data=network_interface_json)

                    db_session.delete(network_interface)

                workflow_task.status = WorkflowTask.STATUS_SUCCESSFUL
                LOGGER.info(f"IBM Network Interface {workflow_task.resource_id} deletion successful.")
                db_session.commit()
                return
            else:
                workflow_task.status = WorkflowTask.STATUS_FAILED
                message = f"IBMNetworkInterface {workflow_task.resource_id} failed due to reason: {str(ex.message)}"
                workflow_task.message = message
                db_session.commit()
                LOGGER.info(message)
                return

    with get_db_session() as db_session:
        workflow_task: WorkflowTask = db_session.query(WorkflowTask).get(workflow_task_id)
        if not workflow_task:
            return

        network_interface_status = network_interface_json["status"]
        if network_interface_status in [IBMNetworkInterface.STATUS_DELETING, IBMNetworkInterface.STATUS_PENDING]:
            workflow_task.status = WorkflowTask.STATUS_RUNNING_WAIT
            message = f"IBM Network Interface {workflow_task.resource_id} deletion waiting."
        else:
            message = f"IBM Network Interface {workflow_task.resource_id} deletion failed."
            workflow_task.message = message
            workflow_task.status = WorkflowTask.STATUS_FAILED

        db_session.commit()
    LOGGER.info(message)


@celery.task(name="delete_wait_network_interface", base=IBMWorkflowTasksBase)
def delete_wait_network_interface(workflow_task_id):
    """
    Wait for an IBM Network Interface deletion on IBM Cloud.
    :param workflow_task_id:
    :return:
    """
    with get_db_session() as db_session:
        workflow_task: WorkflowTask = db_session.query(WorkflowTask).get(workflow_task_id)
        if not workflow_task:
            return

        workflow_task.status = WorkflowTask.STATUS_RUNNING
        db_session.commit()

        network_interface: IBMNetworkInterface = db_session.query(IBMNetworkInterface).get(workflow_task.resource_id)
        if not network_interface:
            workflow_task.status = WorkflowTask.STATUS_SUCCESSFUL
            db_session.commit()
            LOGGER.info(f"IBM Network Interface {workflow_task.resource_id} deletion successful.")
            return

        region_name = network_interface.instance.region.name
        instance_resource_id = network_interface.instance.resource_id
        network_interface_resource_id = network_interface.resource_id
        cloud_id = network_interface.cloud_id

    try:
        client = InstancesClient(cloud_id, region=region_name)
        network_interface_json = client.get_instance_network_interface(
            instance_id=instance_resource_id, network_interface_id=network_interface_resource_id
        )
    except ApiException as ex:
        with get_db_session() as db_session:
            workflow_task = db_session.query(WorkflowTask).get(workflow_task_id)
            if not workflow_task:
                return

            if ex.code == 404:
                network_interface = db_session.query(IBMNetworkInterface).get(workflow_task.resource_id)
                if network_interface:
                    db_session.delete(network_interface)

                workflow_task.status = WorkflowTask.STATUS_SUCCESSFUL

                network_interface_json = network_interface.to_json()
                network_interface_json["created_at"] = str(network_interface_json["created_at"])

                IBMResourceLog(
                    resource_id=network_interface.resource_id, region=network_interface.instance.zone.region,
                    status=IBMResourceLog.STATUS_DELETED, resource_type=IBMNetworkInterface.__name__,
                    data=network_interface_json)
                LOGGER.info(f"IBM Network Interface {workflow_task.resource_id} deletion successful.")
                db_session.commit()
                return
            else:
                workflow_task.status = WorkflowTask.STATUS_FAILED
                message = f"IBMNetworkInterface {workflow_task.resource_id} failed due to reason: {str(ex.message)}"
                workflow_task.message = message
                db_session.commit()
                LOGGER.info(message)
                return

    with get_db_session() as db_session:
        workflow_task: WorkflowTask = db_session.query(WorkflowTask).get(workflow_task_id)
        if not workflow_task:
            return

        if network_interface_json["status"] in [IBMNetworkInterface.STATUS_DELETING,
                                                IBMNetworkInterface.STATUS_PENDING]:
            workflow_task.status = WorkflowTask.STATUS_RUNNING_WAIT
            message = f"IBM Network Interface {workflow_task.resource_id} deletion waiting."
        else:
            message = f"IBM Network Interface {workflow_task.resource_id} deletion failed."
            workflow_task.message = message
            workflow_task.status = WorkflowTask.STATUS_FAILED

        db_session.commit()
    LOGGER.info(message)


@celery.task(name="attach_floating_ip_with_network_interface", base=IBMWorkflowTasksBase)
def attach_floating_ip_with_network_interface(workflow_task_id):
    """
    Attach an IBM Floating Ip with Network Interface on IBM Cloud Instance
    """
    with get_db_session() as db_session:
        workflow_task = db_session.query(WorkflowTask).filter_by(id=workflow_task_id).first()
        if not workflow_task:
            return

        workflow_task.status = WorkflowTask.STATUS_RUNNING
        db_session.commit()

        resource_data = deepcopy(workflow_task.task_metadata["resource_data"])
        floating_ip_id = resource_data["floating_ip_id"]
        network_interface_id = resource_data["network_interface_id"]

        network_interface = db_session.query(IBMNetworkInterface).filter_by(id=network_interface_id["id"]).first()
        if not network_interface:
            message = f"IBM Network Interface {network_interface_id} not found."
            workflow_task.status = WorkflowTask.STATUS_FAILED
            db_session.commit()
            LOGGER.debug(message)
            return

        floating_ip = db_session.query(IBMFloatingIP).filter_by(id=floating_ip_id["id"]).first()
        if not floating_ip:
            message = f"IBM Floating IP {floating_ip_id} not found."
            workflow_task.status = WorkflowTask.STATUS_FAILED
            db_session.commit()
            LOGGER.debug(message)
            return floating_ip

        floating_ip_resource_id = floating_ip.resource_id
        network_interface_resource_id = network_interface.resource_id
        instance_resource_id = network_interface.instance.resource_id
        cloud_id = network_interface.ibm_cloud.id
        region_name = floating_ip.region.name

    try:
        client = InstancesClient(cloud_id=cloud_id, region=region_name)
        response_json = client.add_instance_network_interface_floating_ip(
            instance_id=instance_resource_id, network_interface_id=network_interface_resource_id,
            floating_ip_id=floating_ip_resource_id)

    except ApiException as ex:
        with get_db_session() as db_session:
            workflow_task = db_session.query(WorkflowTask).filter_by(id=workflow_task_id).first()
            if not workflow_task:
                return

            workflow_task.status = WorkflowTask.STATUS_FAILED
            workflow_task.message = f"Attachment Failed. Reason: {str(ex.message)}"
            db_session.commit()

        LOGGER.info(ex.message)
        return

    with get_db_session() as db_session:
        workflow_task = db_session.query(WorkflowTask).filter_by(id=workflow_task_id).first()
        if not workflow_task:
            return

        with db_session.no_autoflush:
            network_interface = db_session.query(IBMNetworkInterface).filter_by(
                resource_id=response_json["target"]["id"], cloud_id=cloud_id).first()
            floating_ip = db_session.query(IBMFloatingIP).filter_by(resource_id=response_json["id"],
                                                                    cloud_id=cloud_id).first()
            public_gateway = None
            if not network_interface:
                public_gateway = db_session.query(IBMPublicGateway).filter_by(
                    resource_id=response_json["target"]["id"], cloud_id=cloud_id).first()

            if not (network_interface or public_gateway) and not floating_ip:
                workflow_task.status = WorkflowTask.STATUS_FAILED
                workflow_task.message = \
                    "Attachment Successful but record update failed. The records will update next time " \
                    "discovery runs"
                db_session.commit()
                return

            if network_interface:
                floating_ip.network_interface = network_interface
            elif public_gateway:
                floating_ip.public_gateway = public_gateway
            workflow_task.status = WorkflowTask.STATUS_SUCCESSFUL
            db_session.add(floating_ip)
            db_session.commit()

    LOGGER.success(
        f"IBM Network Interface {network_interface_id} association with floating IP {floating_ip_id} successful."
    )


@celery.task(name="detach_floating_ip_from_network_interface", base=IBMWorkflowTasksBase)
def detach_floating_ip_from_network_interface(workflow_task_id):
    """
    Detach an IBM Floating Ip from Network Interface on IBM Cloud Instance
    """
    with get_db_session() as db_session:
        workflow_task = db_session.query(WorkflowTask).filter_by(id=workflow_task_id).first()
        if not workflow_task:
            return

        workflow_task.status = WorkflowTask.STATUS_RUNNING
        db_session.commit()

        resource_data = deepcopy(workflow_task.task_metadata["resource_data"])
        floating_ip_id = resource_data["floating_ip_id"]
        network_interface_id = resource_data["network_interface_id"]

        network_interface = db_session.query(IBMNetworkInterface).filter_by(id=network_interface_id).first()
        if not network_interface:
            message = f"IBM Network Interface {network_interface_id} not found."
            workflow_task.status = WorkflowTask.STATUS_FAILED
            db_session.commit()
            LOGGER.debug(message)
            return

        floating_ip = db_session.query(IBMFloatingIP).filter_by(id=floating_ip_id).first()
        if not floating_ip:
            message = f"IBM Floating IP {floating_ip_id} not found."
            workflow_task.status = WorkflowTask.STATUS_FAILED
            db_session.commit()
            LOGGER.debug(message)
            return floating_ip

        floating_ip_resource_id = floating_ip.resource_id
        network_interface_resource_id = network_interface.resource_id
        instance_resource_id = network_interface.instance.resource_id
        cloud_id = network_interface.ibm_cloud.id
        region_name = floating_ip.region.name

    try:
        client = InstancesClient(cloud_id=cloud_id, region=region_name)
        client.remove_instance_network_interface_floating_ip(
            instance_id=instance_resource_id, network_interface_id=network_interface_resource_id,
            floating_ip_id=floating_ip_resource_id
        )

    except ApiException as ex:
        with get_db_session() as db_session:
            workflow_task = db_session.query(WorkflowTask).get(workflow_task_id)
            if not workflow_task:
                return

            if ex.code in [404, 400]:
                workflow_task.status = WorkflowTask.STATUS_FAILED
                message = f"IBM Floating IP {floating_ip_resource_id} detachment failed. Reason: {str(ex.message)}."
                workflow_task.message = message
                LOGGER.info(message)
                db_session.commit()
                return

            workflow_task.status = WorkflowTask.STATUS_FAILED
            workflow_task.message = str(ex.message)
            db_session.commit()
            LOGGER.info(str(ex.message))
            return

    with get_db_session() as db_session:
        workflow_task = db_session.query(WorkflowTask).filter_by(id=workflow_task_id).first()
        if not workflow_task:
            return

        floating_ip = db_session.query(IBMFloatingIP).filter_by(id=floating_ip_id, cloud_id=cloud_id).first()

        network_interface = db_session.query(IBMNetworkInterface).filter_by(
            id=network_interface_id, cloud_id=cloud_id).first()

        if not (floating_ip and network_interface):
            workflow_task.status = WorkflowTask.STATUS_FAILED
            workflow_task.message = \
                "Detachment Successful but record update failed. The records will update next time " \
                "discovery runs"
            db_session.commit()
            return

        floating_ip.network_interface = None
        workflow_task.status = WorkflowTask.STATUS_SUCCESSFUL
        db_session.commit()

    LOGGER.info(
        f"IBM Network Interface {network_interface_id} disassociation with floating IP {floating_ip_id} successful."
    )
