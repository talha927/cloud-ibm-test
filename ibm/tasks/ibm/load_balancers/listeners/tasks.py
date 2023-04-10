import logging
from copy import deepcopy
from ibm_cloud_sdk_core import ApiException

from ibm import get_db_session
from ibm.common.clients.ibm_clients import LoadBalancersClient
from ibm.common.utils import update_id_or_name_references
from ibm.models import IBMListener, IBMLoadBalancer, IBMPool, IBMRegion, WorkflowTask
from ibm.tasks.celery_app import celery_app as celery
from ibm.tasks.common.tasks_base import IBMWorkflowTasksBase
from ibm.tasks.ibm.task_utils import load_previous_associated_resources
from ibm.web.ibm.load_balancers.listeners.schemas import IBMLoadBalancerListenerInSchema, \
    IBMLoadBalancerListenerResourceSchema

LOGGER = logging.getLogger(__name__)


@celery.task(name="create_listener", base=IBMWorkflowTasksBase)
def create_listener(workflow_task_id):
    """
    Create an IBM Load Balancer Listener on IBM Cloud
    """
    with get_db_session() as db_session:
        workflow_task: WorkflowTask = db_session.query(WorkflowTask).get(workflow_task_id)
        if not workflow_task:
            return

        workflow_task.status = WorkflowTask.STATUS_RUNNING
        db_session.commit()

        resource_data = deepcopy(workflow_task.task_metadata["resource_data"])
        resource_json = deepcopy(resource_data["resource_json"])
        cloud_id = resource_data["ibm_cloud"]["id"]
        region_id = resource_data["region"]["id"]

        region: IBMRegion = db_session.query(IBMRegion).get(region_id)
        if not region:
            workflow_task.status = WorkflowTask.STATUS_FAILED
            workflow_task.message = f"IBMRegion `{region_id}` not found."
            db_session.commit()
            LOGGER.info(workflow_task.message)
            return

        if region.ibm_status == IBMRegion.IBM_STATUS_UNAVAILABLE:
            workflow_task.status = WorkflowTask.STATUS_FAILED
            workflow_task.message = f"IBMRegion '{region.name}' unavailable."
            db_session.commit()
            LOGGER.info(workflow_task.message)
            return

        previous_resources = load_previous_associated_resources(task=workflow_task, session=db_session)
        update_id_or_name_references(
            cloud_id=cloud_id, resource_json=resource_data, resource_schema=IBMLoadBalancerListenerInSchema,
            db_session=db_session, previous_resources=previous_resources
        )

        update_id_or_name_references(
            cloud_id=cloud_id, resource_json=resource_json, resource_schema=IBMLoadBalancerListenerResourceSchema,
            db_session=db_session, previous_resources=previous_resources
        )

        load_balancer_resource_id = resource_data["load_balancer"]["id"]

    try:
        client = LoadBalancersClient(cloud_id=cloud_id, region=region.name)
        resp_json = client.create_load_balancer_listener(load_balancer_id=load_balancer_resource_id,
                                                         load_balancer_listener_json=resource_json)
    except ApiException as ex:
        with get_db_session() as db_session:
            workflow_task: WorkflowTask = db_session.query(WorkflowTask).get(workflow_task_id)
            if not workflow_task:
                return

            workflow_task.status = WorkflowTask.STATUS_FAILED
            workflow_task.message = f"Creation Failed. Reason: {str(ex.message)}"
            db_session.commit()

        LOGGER.info("Create Listener failed with status code " + str(ex.code) + ": " + ex.message)
        return

    with get_db_session() as db_session:
        workflow_task: WorkflowTask = db_session.query(WorkflowTask).get(workflow_task_id)
        if not workflow_task:
            return

        listener_status = resp_json["provisioning_status"]
        listener_resource_id = resp_json["id"]
        port, protocol = resp_json["port"], resp_json["protocol"]

        if listener_status in [IBMListener.PROVISIONING_STATUS_ACTIVE, IBMListener.PROVISIONING_STATUS_CREATE_PENDING]:
            metadata = workflow_task.task_metadata.copy() if workflow_task.task_metadata else {}
            metadata["ibm_resource_id"] = listener_resource_id
            metadata["load_balancer_resource_id"] = load_balancer_resource_id
            workflow_task.task_metadata = metadata

            workflow_task.status = WorkflowTask.STATUS_RUNNING_WAIT
            message = f"IBM Listener '{port}-{protocol}' for cloud {cloud_id} creation waiting."
        else:
            message = f"IBM Listener '{port}-{protocol}' for cloud {cloud_id} creation failed."
            workflow_task.message = message
            workflow_task.status = WorkflowTask.STATUS_FAILED
        db_session.commit()
    LOGGER.info(message)


@celery.task(name="create_wait_listener", base=IBMWorkflowTasksBase)
def create_wait_listener(workflow_task_id):
    """
    Wait for an IBM Listener creation on IBM Cloud
    """
    with get_db_session() as db_session:
        workflow_task: WorkflowTask = db_session.query(WorkflowTask).get(workflow_task_id)
        if not workflow_task:
            return

        workflow_task.status = WorkflowTask.STATUS_RUNNING
        db_session.commit()

        resource_data = deepcopy(workflow_task.task_metadata["resource_data"])
        cloud_id = resource_data["ibm_cloud"]["id"]
        region_id = resource_data["region"]["id"]

        region: IBMRegion = db_session.query(IBMRegion).get(region_id)
        if not region:
            workflow_task.status = WorkflowTask.STATUS_FAILED
            workflow_task.message = f"IBMRegion '{region_id}' not found."
            db_session.commit()
            LOGGER.info(workflow_task.message)
            return

        if region.ibm_status == IBMRegion.IBM_STATUS_UNAVAILABLE:
            workflow_task.status = WorkflowTask.STATUS_FAILED
            workflow_task.message = f"IBMRegion '{region.name}' unavailable."
            db_session.commit()
            LOGGER.info(workflow_task.message)
            return

        load_balancer_resource_id = workflow_task.task_metadata["load_balancer_resource_id"]
        listener_resource_id = workflow_task.task_metadata["ibm_resource_id"]

    try:
        client = LoadBalancersClient(cloud_id=cloud_id, region=region.name)
        listener_json = client.get_load_balancer_listener(load_balancer_id=load_balancer_resource_id,
                                                          listener_id=listener_resource_id)

        listener_default_pool = None
        if listener_json["provisioning_status"] == IBMListener.PROVISIONING_STATUS_ACTIVE:
            if listener_json.get("default_pool"):
                listener_default_pool = client.get_load_balancer_pool(load_balancer_id=load_balancer_resource_id,
                                                                      pool_id=listener_json["default_pool"]["id"])

    except ApiException as ex:
        with get_db_session() as db_session:
            workflow_task = db_session.query(WorkflowTask).get(workflow_task_id)
            if not workflow_task:
                return

            workflow_task.status = WorkflowTask.STATUS_FAILED
            workflow_task.message = f"Creation Failed. Reason: {str(ex.message)}"
            db_session.commit()

        LOGGER.info("Create Wait Listener failed with status code " + str(ex.code) + ": " + ex.message)
        return

    with get_db_session() as db_session:
        workflow_task = db_session.query(WorkflowTask).get(workflow_task_id)
        if not workflow_task:
            return

        listener_status = listener_json["provisioning_status"]
        port, protocol = listener_json["port"], listener_json["protocol"]

        if listener_status == IBMListener.PROVISIONING_STATUS_ACTIVE:
            with db_session.no_autoflush:
                region = db_session.query(IBMRegion).get(region_id)
                if not region:
                    workflow_task.status = WorkflowTask.STATUS_FAILED
                    workflow_task.message = \
                        "Creation Successful but record update failed. The records will update next time discovery runs"
                    db_session.commit()
                    return
                load_balancer = db_session.query(IBMLoadBalancer).get(resource_data["load_balancer"]["id"])
                if not load_balancer:
                    workflow_task.status = WorkflowTask.STATUS_FAILED
                    workflow_task.message = \
                        "Creation Successful but record update failed. The records will update next time discovery runs"
                    db_session.commit()
                    return

                listener: IBMListener = IBMListener.from_ibm_json_body(json_body=listener_json, db_session=db_session)

                if listener_default_pool:
                    pool = db_session.query(IBMPool).filter_by(resource_id=listener_default_pool["id"]).first()
                    if not pool:
                        workflow_task.status = WorkflowTask.STATUS_FAILED
                        workflow_task.message = \
                            "Creation Successful but record update failed. The records will update next time " \
                            "discovery runs"
                        db_session.commit()
                        return
                    listener.default_pool = pool

                listener.load_balancer = load_balancer
                listener.region = region
                listener_id = listener.id

                db_session.add(listener)
                db_session.commit()

            workflow_task.status = WorkflowTask.STATUS_SUCCESSFUL
            workflow_task.resource_id = listener_id
            message = f"IBM Listener '{protocol}-{port}' for cloud {cloud_id} creation successful"
        elif listener_status == IBMListener.PROVISIONING_STATUS_CREATE_PENDING:
            workflow_task.status = WorkflowTask.STATUS_RUNNING_WAIT
            message = f"IBM Listener '{protocol}-{port}' for cloud {cloud_id} creation waiting"
        else:
            message = f"IBM Listener '{protocol}-{port}' for cloud {cloud_id} creation failed"
            workflow_task.message = message
            workflow_task.status = WorkflowTask.STATUS_FAILED
        db_session.commit()
    LOGGER.info(message)


@celery.task(name="delete_listener", base=IBMWorkflowTasksBase)
def delete_listener(workflow_task_id):
    """
    Delete an IBM Listener
    :param workflow_task_id:
    :return:
    """

    with get_db_session() as db_session:
        workflow_task: WorkflowTask = db_session.query(WorkflowTask).get(workflow_task_id)
        if not workflow_task:
            return

        workflow_task.status = WorkflowTask.STATUS_RUNNING
        db_session.commit()

        listener: IBMListener = db_session.query(IBMListener).get(workflow_task.resource_id)
        if not listener:
            workflow_task.status = WorkflowTask.STATUS_FAILED
            workflow_task.message = f"IBMListener '{workflow_task.resource_id}' not found"
            db_session.commit()
            LOGGER.info(workflow_task.message)
            return

        region_name = listener.region.name
        listener_resource_id = listener.resource_id
        load_balancer_resource_id = listener.load_balancer.resource_id
        listener_port_protocol = f"{str(listener.port) + listener.protocol}"

        try:
            load_balancer_client = LoadBalancersClient(listener.cloud_id, region=region_name)
            load_balancer_client.delete_load_balancer_listener(load_balancer_id=load_balancer_resource_id,
                                                               listener_id=listener_resource_id)
            listener_json = load_balancer_client.get_load_balancer_listener(load_balancer_id=load_balancer_resource_id,
                                                                            listener_id=listener_resource_id)
        except ApiException as ex:
            workflow_task: WorkflowTask = db_session.query(WorkflowTask).filter_by(id=workflow_task_id).first()
            if not workflow_task:
                return

            if ex.code == 404:  # 404 means resource is not found on IBM Cloud.
                listener: IBMListener = db_session.query(IBMListener).filter_by(
                    id=workflow_task.resource_id).first()
                if listener:
                    db_session.delete(listener)

                workflow_task.status = WorkflowTask.STATUS_SUCCESSFUL
                LOGGER.info(
                    f"IBM Listener {listener_port_protocol} for cloud {listener.cloud_id} deletion successful.")
                db_session.commit()
                return
            else:
                workflow_task.status = WorkflowTask.STATUS_FAILED
                workflow_task.message = str(ex.message)
                db_session.commit()
                LOGGER.info(str(ex.message))
                return

        listener_status = listener_json["provisioning_status"]
        if listener_status == IBMListener.PROVISIONING_STATUS_DELETE_PENDING:
            workflow_task.status = WorkflowTask.STATUS_RUNNING_WAIT
            message = f"IBM Listener {listener_port_protocol} for cloud {listener.cloud_id} deletion waiting"
        else:
            message = f"IBM Listener {listener_port_protocol} for cloud {listener.cloud_id} deletion failed"
            workflow_task.message = message
            workflow_task.status = WorkflowTask.STATUS_FAILED

        db_session.commit()
    LOGGER.info(message)


@celery.task(name="delete_wait_listener", base=IBMWorkflowTasksBase)
def delete_wait_listener(workflow_task_id):
    """
    Wait for an IBM Listener deletion on IBM Cloud.
    :param workflow_task_id:
    :return:
    """
    with get_db_session() as db_session:
        workflow_task: WorkflowTask = db_session.query(WorkflowTask).get(workflow_task_id)
        if not workflow_task:
            return

        workflow_task.status = WorkflowTask.STATUS_RUNNING
        db_session.commit()

        listener: IBMListener = db_session.query(IBMListener).get(workflow_task.resource_id)
        if not listener:
            workflow_task.status = WorkflowTask.STATUS_FAILED
            workflow_task.message = f"IBMListener '{workflow_task.resource_id}' not found"
            db_session.commit()
            LOGGER.info(workflow_task.message)
            return

        region_name = listener.region.name
        listener_resource_id = listener.resource_id
        load_balancer_resource_id = listener.load_balancer.resource_id
        listener_port_protocol = f"{str(listener.port) + listener.protocol}"

        try:
            load_balancer_client = LoadBalancersClient(listener.cloud_id, region=region_name)
            resp_json = load_balancer_client.get_load_balancer_listener(load_balancer_id=load_balancer_resource_id,
                                                                        listener_id=listener_resource_id)
        except ApiException as ex:
            workflow_task: WorkflowTask = db_session.query(WorkflowTask).filter_by(id=workflow_task_id).first()
            if not workflow_task:
                return

            if ex.code == 404:  # 404 means resource is not found on IBM Cloud.
                listener: IBMListener = db_session.query(IBMListener).filter_by(
                    id=workflow_task.resource_id).first()
                if listener:
                    db_session.delete(listener)

                workflow_task.status = WorkflowTask.STATUS_SUCCESSFUL
                LOGGER.info(
                    f"IBM Listener {listener_port_protocol} for cloud {listener.cloud_id} deletion successful.")
                db_session.commit()
                return
            else:
                workflow_task.status = WorkflowTask.STATUS_FAILED
                workflow_task.message = str(ex.message)
                db_session.commit()
                LOGGER.info(str(ex.message))
                return

        if resp_json["provisioning_status"] == IBMLoadBalancer.PROVISIONING_STATUS_DELETE_PENDING:
            workflow_task.status = WorkflowTask.STATUS_RUNNING_WAIT
            message = f"IBM Listener {listener_port_protocol} for cloud {listener.cloud_id} deletion waiting"
        else:
            message = f"IBM Listener {listener_port_protocol} for cloud {listener.cloud_id} deletion failed"
            workflow_task.message = message
            workflow_task.status = WorkflowTask.STATUS_FAILED

        db_session.commit()
    LOGGER.info(message)
