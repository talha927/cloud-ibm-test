import logging
from copy import deepcopy
from ibm_cloud_sdk_core import ApiException

from ibm import get_db_session
from ibm.common.clients.ibm_clients import LoadBalancersClient
from ibm.common.utils import update_id_or_name_references
from ibm.models import IBMInstance, IBMLoadBalancer, IBMNetworkInterface, IBMPool, IBMPoolMember, WorkflowTask
from ibm.tasks.celery_app import celery_app as celery
from ibm.tasks.common.tasks_base import IBMWorkflowTasksBase
from ibm.tasks.ibm.task_utils import load_previous_associated_resources
from ibm.web.ibm.load_balancers.pools.members.schema import IBMLoadBalancerPoolMemberInSchema, \
    IBMLoadBalancerPoolMemberResourceSchema

LOGGER = logging.getLogger(__name__)


@celery.task(name="create_load_balancer_pool_member", base=IBMWorkflowTasksBase)
def create_load_balancer_pool_member(workflow_task_id):
    """
    Create an IBM Load balancer pool member on IBM Cloud
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
        pool_id = resource_data["pool"]["id"]

        pool = db_session.query(IBMPool).filter_by(id=pool_id, cloud_id=cloud_id).first()
        if not pool:
            workflow_task.status = WorkflowTask.STATUS_FAILED
            workflow_task.message = f"IBM Pool with id: '{pool_id}' not found"
            db_session.commit()
            LOGGER.info(workflow_task.message)
            return

        target_id = resource_json["target"]["id"]
        subnet_id = resource_json["target"]["subnet"]["id"]
        if resource_json["target"]["type"] == "instance":
            instance = db_session.query(IBMInstance).filter_by(id=target_id, cloud_id=cloud_id).first()
            if not instance:
                workflow_task.status = WorkflowTask.STATUS_FAILED
                workflow_task.message = f"IBM Instance with id: '{target_id}' not found"
                db_session.commit()
                LOGGER.info(workflow_task.message)
                return

            resource_json["target"]["id"] = instance.resource_id

        elif resource_json["target"]["type"] == "network_interface":
            network_interface = db_session.query(IBMNetworkInterface).filter_by(id=target_id, cloud_id=cloud_id).first()
            if not network_interface:
                workflow_task.status = WorkflowTask.STATUS_FAILED
                workflow_task.message = f"IBMNetworkInterface with id: '{target_id}' not found"
                db_session.commit()
                LOGGER.info(workflow_task.message)
                return

            resource_json["target"]["address"] = network_interface.primary_ipv4_address

        del resource_json["target"]["type"]
        del resource_json["target"]["subnet"]

        region_name = pool.load_balancer.region.name

        previous_resources = load_previous_associated_resources(task=workflow_task, session=db_session)
        update_id_or_name_references(
            cloud_id=cloud_id, resource_json=resource_data, resource_schema=IBMLoadBalancerPoolMemberInSchema,
            db_session=db_session, previous_resources=previous_resources
        )
        update_id_or_name_references(
            cloud_id=cloud_id, resource_json=resource_json, resource_schema=IBMLoadBalancerPoolMemberResourceSchema,
            db_session=db_session, previous_resources=previous_resources
        )

        load_balancer_resource_id = pool.load_balancer.resource_id
        pool_resource_id = pool.resource_id
    try:
        client = LoadBalancersClient(cloud_id=cloud_id, region=region_name)
        load_balancer_json = client.get_load_balancer(load_balancer_resource_id)
        pool_member_json = None
        if load_balancer_json["provisioning_status"] == IBMLoadBalancer.PROVISIONING_STATUS_ACTIVE:
            pool_member_json = client.create_load_balancer_pool_member(load_balancer_id=load_balancer_resource_id,
                                                                       pool_id=pool_resource_id,
                                                                       pool_member_json=resource_json)
    except ApiException as ex:
        with get_db_session() as db_session:
            workflow_task = db_session.query(WorkflowTask).filter_by(id=workflow_task_id).first()
            if not workflow_task:
                return

            workflow_task.status = WorkflowTask.STATUS_FAILED
            workflow_task.message = f"Creation Failed. Reason: {str(ex.message)}"
            db_session.commit()

        LOGGER.info("Create Load Balancer Pool Member failed with status code " + str(ex.code) + ": " + ex.message)
        return

    with get_db_session() as db_session:
        workflow_task = db_session.query(WorkflowTask).filter_by(id=workflow_task_id).first()
        if not workflow_task:
            return

        member_name = f"{pool_member_json['port']}-{pool_member_json['health']}"
        member_status = pool_member_json["provisioning_status"]
        if load_balancer_json["provisioning_status"] == IBMLoadBalancer.PROVISIONING_STATUS_ACTIVE:
            if member_status in [IBMPoolMember.PROVISIONING_STATUS_ACTIVE,
                                 IBMPoolMember.PROVISIONING_STATUS_CREATE_PENDING,
                                 IBMPoolMember.PROVISIONING_STATUS_MAINTENANCE_PENDING,
                                 IBMPoolMember.PROVISIONING_STATUS_UPDATE_PENDING]:
                metadata = deepcopy(workflow_task.task_metadata)
                metadata["ibm_resource_id"] = pool_member_json["id"]
                metadata["subnet_id"] = subnet_id
                metadata["ibm_resource_name"] = member_name
                workflow_task.task_metadata = metadata

                workflow_task.status = WorkflowTask.STATUS_RUNNING_WAIT
                message = f"IBM Pool Member {member_name} for {cloud_id} creation waiting."
            else:
                workflow_task.status = WorkflowTask.STATUS_SUCCESSFUL
                message = f"IBM pool member '{member_name}' creation for cloud '{cloud_id}' successful"
        elif load_balancer_json["provisioning_status"] == IBMLoadBalancer.PROVISIONING_STATUS_UPDATE_PENDING:
            workflow_task.status = WorkflowTask.STATUS_RUNNING_WAIT
            message = f"IBM Pool Member {member_name} for {cloud_id} creation waiting."

        db_session.commit()
    LOGGER.info(message)


@celery.task(name="create_wait_load_balancer_pool_member", base=IBMWorkflowTasksBase)
def create_wait_load_balancer_pool_member(workflow_task_id):
    """
    Wait for an IBM Pool Member creation on IBM Cloud
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
        pool_id = resource_data["pool"]["id"]

        pool = db_session.query(IBMPool).filter_by(id=pool_id, cloud_id=cloud_id).first()
        if not pool:
            workflow_task.status = WorkflowTask.STATUS_FAILED
            workflow_task.message = f"IBM Pool '{pool_id}' not found"
            db_session.commit()
            LOGGER.info(workflow_task.message)
            return

        region_name = pool.load_balancer.region.name
        load_balancer_resource_id = pool.load_balancer.resource_id
        pool_resource_id = pool.resource_id
        pool_member_resource_id = workflow_task.task_metadata["ibm_resource_id"]

    try:
        client = LoadBalancersClient(cloud_id=cloud_id, region=region_name)
        pool_json_list = client.list_load_balancer_pool_members(
            load_balancer_id=load_balancer_resource_id, pool_id=pool_resource_id
        )

    except ApiException as ex:
        with get_db_session() as db_session:
            workflow_task = db_session.get(WorkflowTask, workflow_task_id)
            if not workflow_task:
                return

            workflow_task.status = WorkflowTask.STATUS_FAILED
            workflow_task.message = f"Creation Failed. Reason: {str(ex.message)}"
            db_session.commit()

        LOGGER.info("Create Load Balancer Pool Member failed with status code " + str(ex.code) + ": " + ex.message)
        return

    with get_db_session() as db_session:
        workflow_task = db_session.get(WorkflowTask, workflow_task_id)
        if not workflow_task:
            return

        member_json = list(filter(lambda json_: pool_member_resource_id == json_["id"], pool_json_list))[0]

        member_name = f"{member_json['port']}-{member_json['health']}"
        if member_json["provisioning_status"] == IBMPoolMember.PROVISIONING_STATUS_ACTIVE:
            with db_session.no_autoflush:
                pool = db_session.get(IBMPool, pool_id)
                if not pool:
                    workflow_task.status = WorkflowTask.STATUS_FAILED
                    message = "Creation Successful but record update failed. The records will update next time " \
                              "discovery runs pool not found"
                    workflow_task.message = message
                    db_session.commit()
                    LOGGER.info(message)
                    return

                pool_member: IBMPoolMember = IBMPoolMember.from_ibm_json_body(json_body=member_json)

                if "id" in member_json["target"]:
                    instance = db_session.get(IBMInstance, resource_json["target"].get("id"))
                    if not instance:
                        workflow_task.status = WorkflowTask.STATUS_FAILED
                        message = "Creation Successful but record update failed. The records will update next time " \
                                  "discovery runs by instance"
                        workflow_task.message = message
                        db_session.commit()
                        LOGGER.info(message)
                        return

                    pool_member.instance = instance

                pool_member.pool = pool
                pool_member.subnet_id = workflow_task.task_metadata["subnet_id"]
                pool_member_id = pool_member.id
                db_session.commit()

            workflow_task.status = WorkflowTask.STATUS_SUCCESSFUL
            workflow_task.resource_id = pool_member_id
            message = f"IBM Pool Member '{member_name}' for cloud {cloud_id} creation successful"
        elif member_json["provisioning_status"] == IBMPool.PROVISIONING_STATUS_CREATE_PENDING:
            workflow_task.status = WorkflowTask.STATUS_RUNNING_WAIT
            message = f"IBM Pool Member '{member_name}' for cloud {cloud_id} creation waiting"
        else:
            message = f"IBM Pool Member'{member_name}' for cloud {cloud_id} creation failed"
            workflow_task.message = message
            workflow_task.status = WorkflowTask.STATUS_FAILED
        db_session.commit()
    LOGGER.info(message)


@celery.task(name="delete_load_balancer_pool_member", base=IBMWorkflowTasksBase)
def delete_load_balancer_pool_member(workflow_task_id):
    """
    Delete an IBM Load Balancer Pool Member on IBM Cloud
    :param workflow_task_id:
    :return:
    """

    with get_db_session() as db_session:
        workflow_task: WorkflowTask = db_session.get(WorkflowTask, workflow_task_id)
        if not workflow_task:
            return

        workflow_task.status = WorkflowTask.STATUS_RUNNING
        db_session.commit()

        pool_member: IBMPoolMember = db_session.get(IBMPoolMember, workflow_task.resource_id)
        if not pool_member:
            workflow_task.status = WorkflowTask.STATUS_FAILED
            workflow_task.message = f"IBMPool Member '{workflow_task.resource_id}' not found"
            db_session.commit()
            LOGGER.info(workflow_task.message)
            return

        pool = pool_member.pool
        cloud_id = pool.cloud_id
        region_name = pool.region.name
        load_balancer_resource_id = pool.load_balancer.resource_id
        pool_resource_id = pool.resource_id
        pool_member_resource_id = pool_member.resource_id

    try:
        client = LoadBalancersClient(cloud_id, region=region_name)
        client.delete_load_balancer_pool_member(load_balancer_resource_id, pool_resource_id, pool_member_resource_id)
        pool_members_json_list = client.list_load_balancer_pool_members(load_balancer_resource_id, pool_resource_id)

    except ApiException as ex:
        with get_db_session() as db_session:
            workflow_task: WorkflowTask = db_session.get(WorkflowTask, workflow_task_id)
            if not workflow_task:
                return

            if ex.code == 404:
                pool_member: IBMPoolMember = db_session.get(IBMPoolMember, workflow_task.resource_id)
                if pool_member:
                    db_session.delete(pool_member)

                workflow_task.status = WorkflowTask.STATUS_SUCCESSFUL
                LOGGER.info(f"IBM Pool Member {workflow_task.resource_id} for cloud {cloud_id} deletion successful.")
                db_session.commit()
                return
            else:
                workflow_task.status = WorkflowTask.STATUS_FAILED
                message = f"Cannot delete the pool member {workflow_task.resource_id} due to reason: {str(ex.message)}"
                workflow_task.message = message
                db_session.commit()
                LOGGER.info(message)
                return

    with get_db_session() as db_session:
        workflow_task: WorkflowTask = db_session.get(WorkflowTask, workflow_task_id)
        if not workflow_task:
            return

        member_json = list(filter(lambda json_: pool_member_resource_id == json_["id"], pool_members_json_list))[0]

        member_name = f"{member_json['port']}-{member_json['health']}"
        if member_json["provisioning_status"] in [IBMPoolMember.PROVISIONING_STATUS_DELETE_PENDING,
                                                  IBMPoolMember.PROVISIONING_STATUS_UPDATE_PENDING,
                                                  IBMPoolMember.PROVISIONING_STATUS_MAINTENANCE_PENDING]:
            workflow_task.status = WorkflowTask.STATUS_RUNNING_WAIT
            message = f"IBM Pool Member {member_name} for cloud {cloud_id} deletion waiting"
        else:
            message = f"IBM Pool Member {member_name} for cloud {cloud_id} deletion failed"
            workflow_task.message = message
            workflow_task.status = WorkflowTask.STATUS_FAILED

        db_session.commit()
    LOGGER.info(message)


@celery.task(name="delete_wait_load_balancer_pool_member", base=IBMWorkflowTasksBase)
def delete_wait_load_balancer_pool_member(workflow_task_id):
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

        pool_member: IBMPoolMember = db_session.get(IBMPoolMember, workflow_task.resource_id)
        if not pool_member:
            workflow_task.status = WorkflowTask.STATUS_SUCCESSFUL
            db_session.commit()
            LOGGER.info(f"IBMPool Member '{workflow_task.resource_id}' deletion successful.")
            return

        pool = pool_member.pool
        cloud_id = pool.cloud_id
        region_name = pool.region.name
        load_balancer_resource_id = pool.load_balancer.resource_id
        pool_resource_id = pool.resource_id
        pool_member_resource_id = pool_member.resource_id

    try:
        load_balancer_client = LoadBalancersClient(cloud_id, region=region_name)
        pool_members_json_list = load_balancer_client.list_load_balancer_pool_members(load_balancer_resource_id,
                                                                                      pool_resource_id)
    except ApiException as ex:
        with get_db_session() as db_session:
            workflow_task: WorkflowTask = db_session.get(WorkflowTask, workflow_task_id)
            if not workflow_task:
                return

            if ex.code == 404:
                pool_member: IBMPoolMember = db_session.get(IBMPoolMember, workflow_task.resource_id)
                if pool_member:
                    db_session.delete(pool_member)

                workflow_task.status = WorkflowTask.STATUS_SUCCESSFUL
                LOGGER.info(f"IBM Pool Member {workflow_task.resource_id} for cloud {cloud_id} deletion successful.")
                db_session.commit()
                return
            else:
                workflow_task.status = WorkflowTask.STATUS_FAILED
                message = f"Cannot delete the pool member {workflow_task.resource_id} due to reason: {str(ex.message)}"
                workflow_task.message = message
                db_session.commit()
                LOGGER.info(message)
                return

    with get_db_session() as db_session:
        workflow_task: WorkflowTask = db_session.get(WorkflowTask, workflow_task_id)
        if not workflow_task:
            return

        if not pool_members_json_list:
            pool_member: IBMPoolMember = db_session.get(IBMPoolMember, workflow_task.resource_id)
            if pool_member:
                db_session.delete(pool_member)

            workflow_task.status = WorkflowTask.STATUS_SUCCESSFUL
            LOGGER.info(f"IBM Pool Member {workflow_task.resource_id} for cloud {cloud_id} deletion successful.")
            db_session.commit()
            return

        LOGGER.info(f"pool_members_json_list=>{pool_members_json_list}")

        member_json = list(filter(lambda json_: pool_member_resource_id == json_["id"], pool_members_json_list))[0]

        LOGGER.info(f"member_json=>{member_json}")

        member_name = f"{member_json['port']}-{member_json['health']}"
        if member_json["provisioning_status"] in [IBMPoolMember.PROVISIONING_STATUS_DELETE_PENDING,
                                                  IBMPoolMember.PROVISIONING_STATUS_UPDATE_PENDING,
                                                  IBMPoolMember.PROVISIONING_STATUS_MAINTENANCE_PENDING]:
            workflow_task.status = WorkflowTask.STATUS_RUNNING_WAIT
            message = f"IBM Pool Member {member_name} for cloud {cloud_id} deletion waiting"
        else:
            message = f"IBM Pool Member {member_name} for cloud {cloud_id} deletion failed"
            workflow_task.message = message
            workflow_task.status = WorkflowTask.STATUS_FAILED

        db_session.commit()
    LOGGER.info(message)
