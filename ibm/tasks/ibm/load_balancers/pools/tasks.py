import logging
from copy import deepcopy
from ibm_cloud_sdk_core import ApiException

from ibm import get_db_session
from ibm.common.clients.ibm_clients import LoadBalancersClient
from ibm.common.utils import update_id_or_name_references
from ibm.models import IBMInstance, IBMLoadBalancer, IBMNetworkInterface, IBMPool, IBMPoolMember, IBMRegion, \
    WorkflowTask
from ibm.tasks.celery_app import celery_app as celery
from ibm.tasks.common.tasks_base import IBMWorkflowTasksBase
from ibm.tasks.ibm.task_utils import load_previous_associated_resources
from ibm.web.ibm.load_balancers.pools.schemas import IBMLoadBalancerPoolInSchema, \
    IBMLoadBalancerPoolResourceSchema

LOGGER = logging.getLogger(__name__)


@celery.task(name="create_load_balancer_pool", base=IBMWorkflowTasksBase)
def create_load_balancer_pool(workflow_task_id):
    """
    Create an IBM Load Balancer Pool on IBM Cloud
    """
    with get_db_session() as db_session:
        workflow_task: WorkflowTask = db_session.get(WorkflowTask, workflow_task_id)
        if not workflow_task:
            return

        workflow_task.status = WorkflowTask.STATUS_RUNNING
        db_session.commit()

        resource_data = deepcopy(workflow_task.task_metadata["resource_data"])
        resource_json = deepcopy(resource_data["resource_json"])
        cloud_id = resource_data["ibm_cloud"]["id"]
        region_id = resource_data["region"]["id"]
        load_balancer_id = resource_data["load_balancer"]["id"]

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

        load_balancer = db_session.query(IBMLoadBalancer).filter_by(id=load_balancer_id, cloud_id=cloud_id).first()
        if not load_balancer:
            workflow_task.status = WorkflowTask.STATUS_FAILED
            workflow_task.message = f"IBM Load Balancer '{load_balancer_id}' not found"
            db_session.commit()
            LOGGER.info(workflow_task.message)
            return

        target_id_or_address_to_subnet_id_dict = {}
        for member_resource_json in resource_json.get("members", []):
            target = member_resource_json["target"]
            target_id = target["id"]
            if member_resource_json["target"]["type"] == "instance":
                instance = db_session.query(IBMInstance).filter_by(id=target_id, cloud_id=cloud_id).first()
                if not instance:
                    workflow_task.status = WorkflowTask.STATUS_FAILED
                    workflow_task.message = f"IBM Instance with id: '{target_id}' not found"
                    db_session.commit()
                    LOGGER.info(workflow_task.message)
                    return

                member_resource_json["target"]["id"] = instance.resource_id
                target_id_or_address_to_subnet_id_dict[instance.resource_id] = target["subnet"]["id"]

            elif member_resource_json["target"]["type"] == "network_interface":
                network_interface = db_session.query(IBMNetworkInterface). \
                    filter_by(id=target_id, cloud_id=cloud_id).first()
                if not network_interface:
                    workflow_task.status = WorkflowTask.STATUS_FAILED
                    workflow_task.message = f"IBMNetworkInterface with id: '{target_id}' not found"
                    db_session.commit()
                    LOGGER.info(workflow_task.message)
                    return

                address = network_interface.primary_ipv4_address
                member_resource_json["target"]["address"] = address
                target_id_or_address_to_subnet_id_dict[address] = target["subnet"]["id"]

            del member_resource_json["target"]["type"]
            del member_resource_json["target"]["subnet"]

        previous_resources = load_previous_associated_resources(task=workflow_task, session=db_session)
        update_id_or_name_references(
            cloud_id=cloud_id, resource_json=resource_data, resource_schema=IBMLoadBalancerPoolInSchema,
            db_session=db_session, previous_resources=previous_resources
        )

        update_id_or_name_references(
            cloud_id=cloud_id, resource_json=resource_json, resource_schema=IBMLoadBalancerPoolResourceSchema,
            db_session=db_session, previous_resources=previous_resources
        )

        region_name = region.name
        load_balancer_resource_id = load_balancer.resource_id

    try:
        client = LoadBalancersClient(cloud_id=cloud_id, region=region_name)
        pool_json = client.create_load_balancer_pool(load_balancer_id=load_balancer_resource_id,
                                                     load_balancer_pool_json=resource_json)
    except ApiException as ex:
        with get_db_session() as db_session:
            workflow_task: WorkflowTask = db_session.get(WorkflowTask, workflow_task_id)
            if not workflow_task:
                return

            workflow_task.status = WorkflowTask.STATUS_FAILED
            workflow_task.message = f"Creation Failed. Reason: {str(ex.message)}"
            db_session.commit()

        LOGGER.info("Create Load Balancer Pool failed with status code " + str(ex.code) + ": " + ex.message)
        return

    with get_db_session() as db_session:
        workflow_task: WorkflowTask = db_session.get(WorkflowTask, workflow_task_id)
        if not workflow_task:
            return

        pool_status = pool_json["provisioning_status"]
        pool_resource_id = pool_json["id"]
        pool_name = pool_json["name"]
        if pool_status in [IBMPool.PROVISIONING_STATUS_ACTIVE, IBMPool.PROVISIONING_STATUS_CREATE_PENDING,
                           IBMPool.PROVISIONING_STATUS_UPDATE_PENDING]:
            metadata = deepcopy(workflow_task.task_metadata)
            metadata["ibm_resource_id"] = pool_resource_id
            metadata["target_id_or_address_to_subnet_id_dict"] = target_id_or_address_to_subnet_id_dict
            metadata["load_balancer_resource_id"] = load_balancer.resource_id
            workflow_task.task_metadata = metadata

            workflow_task.status = WorkflowTask.STATUS_RUNNING_WAIT
            message = f"IBM Pool '{pool_name}' for cloud {cloud_id} creation waiting."
        else:
            message = f"IBM Pool '{pool_name}' for cloud {cloud_id} creation failed."
            workflow_task.message = message
            workflow_task.status = WorkflowTask.STATUS_FAILED
        db_session.commit()
    LOGGER.info(message)


@celery.task(name="create_wait_load_balancer_pool", base=IBMWorkflowTasksBase)
def create_wait_load_balancer_pool(workflow_task_id):
    """
    Wait for an IBM Pool creation on IBM Cloud
    """
    with get_db_session() as db_session:
        workflow_task: WorkflowTask = db_session.get(WorkflowTask, workflow_task_id)
        if not workflow_task:
            return

        workflow_task.status = WorkflowTask.STATUS_RUNNING
        db_session.commit()

        resource_data = deepcopy(workflow_task.task_metadata["resource_data"])
        cloud_id = resource_data["ibm_cloud"]["id"]
        region_id = resource_data["region"]["id"]
        load_balancer_id = resource_data["load_balancer"]["id"]
        target_id_or_address_to_subnet_id_dict = workflow_task.task_metadata["target_id_or_address_to_subnet_id_dict"]

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

        load_balancer = db_session.query(IBMLoadBalancer).filter_by(id=load_balancer_id, cloud_id=cloud_id).first()
        if not load_balancer:
            workflow_task.status = WorkflowTask.STATUS_FAILED
            workflow_task.message = f"IBM Load Balancer '{load_balancer_id}' not found"
            db_session.commit()
            LOGGER.info(workflow_task.message)
            return

        region_name = region.name
        load_balancer_resource_id = load_balancer.resource_id
        pool_resource_id = workflow_task.task_metadata["ibm_resource_id"]

    try:
        client = LoadBalancersClient(cloud_id=cloud_id, region=region_name)
        pool_json = client.get_load_balancer_pool(load_balancer_id=load_balancer_resource_id, pool_id=pool_resource_id)
        pool_members = client.list_load_balancer_pool_members(load_balancer_resource_id, pool_json["id"])

    except ApiException as ex:
        with get_db_session() as db_session:
            workflow_task = db_session.get(WorkflowTask, workflow_task_id)
            if not workflow_task:
                return

            workflow_task.status = WorkflowTask.STATUS_FAILED
            workflow_task.message = f"Creation Failed. Reason: {str(ex.message)}"
            db_session.commit()

        LOGGER.info("Create Wait Load Balancer Pool failed with status code " + str(ex.code) + ": " + ex.message)
        return

    with get_db_session() as db_session:
        workflow_task = db_session.get(WorkflowTask, workflow_task_id)
        if not workflow_task:
            return

        pool_status = pool_json["provisioning_status"]
        pool_name = pool_json["name"]
        if pool_status == IBMPool.PROVISIONING_STATUS_ACTIVE:
            with db_session.no_autoflush:
                region = db_session.get(IBMRegion, region_id)
                if not region:
                    workflow_task.status = WorkflowTask.STATUS_FAILED
                    workflow_task.message = \
                        "Creation Successful but record update failed. The records will update next time discovery runs"
                    db_session.commit()
                    return
                load_balancer = db_session.get(IBMLoadBalancer, load_balancer_id)
                if not load_balancer:
                    workflow_task.status = WorkflowTask.STATUS_FAILED
                    workflow_task.message = \
                        "Creation Successful but record update failed. The records will update next time discovery runs"
                    db_session.commit()
                    return

                pool: IBMPool = IBMPool.from_ibm_json_body(json_body=pool_json)
                for member_json in pool_members:
                    pool_member = IBMPoolMember.from_ibm_json_body(member_json)
                    target_id_or_address = member_json["target"].get("id") or pool_member.target_ip_address
                    subnet_id = target_id_or_address_to_subnet_id_dict[target_id_or_address]
                    if member_json["target"].get("id"):
                        instance = db_session.query(IBMInstance). \
                            filter_by(resource_id=member_json["target"]["id"]).first()
                        pool_member.instance = instance

                    pool_member.subnet_id = subnet_id
                    pool.members.append(pool_member)

                pool_id = pool.id
                pool.load_balancer = load_balancer
                pool.region = region
                db_session.commit()

            workflow_task.status = WorkflowTask.STATUS_SUCCESSFUL
            workflow_task.resource_id = pool_id
            message = f"IBM Pool '{pool_name}' for cloud {cloud_id} creation successful"
        elif pool_status == IBMPool.PROVISIONING_STATUS_CREATE_PENDING:
            workflow_task.status = WorkflowTask.STATUS_RUNNING_WAIT
            message = f"IBM Pool '{pool_name}' for cloud {cloud_id} creation waiting"
        else:
            message = f"IBM Pool '{pool_name}' for cloud {cloud_id} creation failed"
            workflow_task.message = message
            workflow_task.status = WorkflowTask.STATUS_FAILED
        db_session.commit()
    LOGGER.info(message)


@celery.task(name="delete_load_balancer_pool", base=IBMWorkflowTasksBase)
def delete_load_balancer_pool(workflow_task_id):
    """
    Delete an IBM Load Balancer Pool on IBM Cloud
    :param workflow_task_id:
    :return:
    """

    with get_db_session() as db_session:
        workflow_task: WorkflowTask = db_session.get(WorkflowTask, workflow_task_id)
        if not workflow_task:
            return

        workflow_task.status = WorkflowTask.STATUS_RUNNING
        db_session.commit()

        pool: IBMPool = db_session.get(IBMPool, workflow_task.resource_id)
        if not pool:
            workflow_task.status = WorkflowTask.STATUS_FAILED
            workflow_task.message = f"IBMPool '{workflow_task.resource_id}' not found"
            db_session.commit()
            LOGGER.info(workflow_task.message)
            return

        cloud_id = pool.cloud_id
        region_name = pool.region.name
        load_balancer_resource_id = pool.load_balancer.resource_id
        pool_resource_id = pool.resource_id

    try:
        client = LoadBalancersClient(cloud_id, region=region_name)
        client.delete_load_balancer_pool(load_balancer_resource_id, pool_resource_id)
        pool_json = client.get_load_balancer_pool(load_balancer_resource_id, pool_resource_id)

    except ApiException as ex:
        with get_db_session() as db_session:
            workflow_task: WorkflowTask = db_session.get(WorkflowTask, workflow_task_id)
            if not workflow_task:
                return

            if ex.code == 404:
                pool: IBMPool = db_session.get(IBMPool, workflow_task.resource_id)
                if pool:
                    db_session.delete(pool)

                workflow_task.status = WorkflowTask.STATUS_SUCCESSFUL
                LOGGER.info(f"IBM Pool {workflow_task.resource_id} for cloud {cloud_id} deletion successful.")
                db_session.commit()
                return
            else:
                workflow_task.status = WorkflowTask.STATUS_FAILED
                message = f"Cannot delete the pool {workflow_task.resource_id} due to reason: {str(ex.message)}"
                workflow_task.message = message
                db_session.commit()
                LOGGER.info(message)
                return

    with get_db_session() as db_session:
        workflow_task: WorkflowTask = db_session.get(WorkflowTask, workflow_task_id)
        if not workflow_task:
            return

        pool_status = pool_json["provisioning_status"]
        load_balancer_name = pool_json["name"]
        if pool_status in [IBMPool.PROVISIONING_STATUS_DELETE_PENDING,
                           IBMPool.PROVISIONING_STATUS_UPDATE_PENDING]:
            workflow_task.status = WorkflowTask.STATUS_RUNNING_WAIT
            message = f"IBM Pool {load_balancer_name} for cloud {cloud_id} deletion waiting"
        else:
            message = f"IBM Pool {load_balancer_name} for cloud {cloud_id} deletion failed"
            workflow_task.message = message
            workflow_task.status = WorkflowTask.STATUS_FAILED

        db_session.commit()
    LOGGER.info(message)


@celery.task(name="delete_wait_load_balancer_pool", base=IBMWorkflowTasksBase)
def delete_wait_load_balancer_pool(workflow_task_id):
    """
    Wait for an IBM Pool deletion on IBM Cloud
    :param workflow_task_id:
    :return:
    """
    with get_db_session() as db_session:
        workflow_task: WorkflowTask = db_session.get(WorkflowTask, workflow_task_id)
        if not workflow_task:
            return

        workflow_task.status = WorkflowTask.STATUS_RUNNING
        db_session.commit()

        pool: IBMPool = db_session.get(IBMPool, workflow_task.resource_id)
        if not pool:
            workflow_task.status = WorkflowTask.STATUS_SUCCESSFUL
            db_session.commit()
            LOGGER.info(f"IBMPool '{workflow_task.resource_id}' deletion successful.")
            return

        cloud_id = pool.cloud_id
        region_name = pool.region.name
        load_balancer_resource_id = pool.load_balancer.resource_id
        pool_resource_id = pool.resource_id

    try:
        load_balancer_client = LoadBalancersClient(cloud_id, region=region_name)
        pool_json = load_balancer_client.get_load_balancer_pool(load_balancer_resource_id, pool_resource_id)

    except ApiException as ex:
        with get_db_session() as db_session:
            workflow_task: WorkflowTask = db_session.get(WorkflowTask, workflow_task_id)
            if not workflow_task:
                return

            if ex.code == 404:
                pool: IBMPool = db_session.get(IBMPool, workflow_task.resource_id)
                if pool:
                    db_session.delete(pool)

                workflow_task.status = WorkflowTask.STATUS_SUCCESSFUL
                LOGGER.info(f"IBM Pool {workflow_task.resource_id} for cloud {cloud_id} deletion successful.")
                db_session.commit()
                return
            else:
                workflow_task.status = WorkflowTask.STATUS_FAILED
                message = f"Cannot delete the pool {workflow_task.resource_id} due to reason: {str(ex.message)}"
                workflow_task.message = message
                db_session.commit()
                LOGGER.info(message)
                return

    with get_db_session() as db_session:
        workflow_task: WorkflowTask = db_session.get(WorkflowTask, workflow_task_id)
        if not workflow_task:
            return

        pool_name = pool_json["name"]
        if pool_json["provisioning_status"] in [IBMPool.PROVISIONING_STATUS_DELETE_PENDING,
                                                IBMPool.PROVISIONING_STATUS_UPDATE_PENDING]:
            workflow_task.status = WorkflowTask.STATUS_RUNNING_WAIT
            message = f"IBM Pool {pool_name} for cloud {cloud_id} deletion waiting"
        else:
            message = f"IBM Pool {pool_name} for cloud {cloud_id} deletion failed"
            workflow_task.message = message
            workflow_task.status = WorkflowTask.STATUS_FAILED

        db_session.commit()
    LOGGER.info(message)
