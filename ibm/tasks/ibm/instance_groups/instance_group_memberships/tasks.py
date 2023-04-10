import logging
from ibm_cloud_sdk_core import ApiException

from ibm import get_db_session
from ibm.common.clients.ibm_clients import InstanceGroupsClient, LoadBalancersClient
from ibm.models import IBMInstanceGroup, IBMInstanceGroupManager, IBMInstanceGroupMembership, IBMLoadBalancer, \
    WorkflowTask
from ibm.tasks.celery_app import celery_app as celery
from ibm.tasks.common.tasks_base import IBMWorkflowTasksBase

LOGGER = logging.getLogger(__name__)


@celery.task(name="delete_all_instance_group_memberships", base=IBMWorkflowTasksBase)
def delete_all_instance_group_memberships(workflow_task_id):
    """
    Delete all IBM Instance Group Memberships
    :param workflow_task_id:
    :return:
    """

    with get_db_session() as db_session:
        workflow_task: WorkflowTask = db_session.get(WorkflowTask, workflow_task_id)
        if not workflow_task:
            return

        workflow_task.status = WorkflowTask.STATUS_RUNNING
        db_session.commit()

        instance_group: IBMInstanceGroup = db_session.get(
            IBMInstanceGroup, workflow_task.resource_id)
        if not instance_group:
            workflow_task.status = WorkflowTask.STATUS_FAILED
            workflow_task.message = f"IBM Instance Group '{workflow_task.resource_id}' not found"
            db_session.commit()
            LOGGER.info(workflow_task.message)
            return

        cloud_id = instance_group.cloud_id
        region_name = instance_group.region.name
        instance_group_resource_id = instance_group.resource_id
        instance_group_manager = db_session.query(
            IBMInstanceGroupManager).filter_by(manager_type=IBMInstanceGroupManager.MANAGER_TYPE_AUTOSCALE,
                                               instance_group_id=workflow_task.resource_id).first()
        if instance_group_manager:
            instance_group_manager_resource_id = instance_group_manager.resource_id
            updated_instance_group_manager_json = {
                "management_enabled": False
            }
        updated_instance_group_json = {
            "membership_count": 0
        }
    try:
        instance_group_client = InstanceGroupsClient(cloud_id, region=region_name)
        if instance_group_manager:
            instance_group_client.update_instance_group_manager(instance_group_resource_id,
                                                                instance_group_manager_resource_id,
                                                                updated_instance_group_manager_json)
        instance_group_client.update_instance_group(instance_group_resource_id, updated_instance_group_json)
        instance_group_json = instance_group_client.get_instance_group(instance_group_resource_id)

    except ApiException as ex:
        with get_db_session() as db_session:
            workflow_task: WorkflowTask = db_session.get(WorkflowTask, workflow_task_id)
            if not workflow_task:
                return

            if ex.code == 404:
                instance_group_memberships = db_session.query(
                    IBMInstanceGroupMembership).filter_by(instance_group_id=workflow_task.resource_id).all()
                for instance_group_membership in instance_group_memberships:
                    if instance_group_membership:
                        db_session.delete(instance_group_membership)

                workflow_task.status = WorkflowTask.STATUS_SUCCESSFUL
                LOGGER.info(
                    f"IBM Instance Group Memberships attached with instance group {workflow_task.resource_id} for "
                    f"cloud {cloud_id} deletion successful.")
                db_session.commit()
                return
            else:
                workflow_task.status = WorkflowTask.STATUS_FAILED
                message = f"Cannot delete the Instance Group Memberships attached with instance group " \
                          f"{workflow_task.resource_id} due to reason: {str(ex.message)}"
                workflow_task.message = message
                db_session.commit()
                LOGGER.info(message)
                return

    with get_db_session() as db_session:
        workflow_task: WorkflowTask = db_session.get(WorkflowTask, workflow_task_id)
        if not workflow_task:
            return

        instance_group_status = instance_group_json["status"]
        instance_group_name = instance_group_json["name"]

        if instance_group_status in [IBMInstanceGroup.STATUS_SCALING,
                                     IBMInstanceGroup.STATUS_DELETING]:
            message = f"IBM Instance Group Membership {instance_group_name} for cloud {cloud_id} " \
                      f"deletion waiting "
            workflow_task.status = WorkflowTask.STATUS_RUNNING_WAIT
            workflow_task.message = message
        elif instance_group_status == IBMInstanceGroup.STATUS_HEALTHY:
            instance_group_memberships = db_session.query(
                IBMInstanceGroupMembership).filter_by(instance_group_id=workflow_task.resource_id).all()
            for instance_group_membership in instance_group_memberships:
                if instance_group_membership:
                    db_session.delete(instance_group_membership)

            workflow_task.status = WorkflowTask.STATUS_SUCCESSFUL
            message = f"IBM Instance Group Memberships attached with instance group {workflow_task.resource_id} for " \
                      f"cloud {cloud_id} deletion successful."
        else:
            message = f"IBM Instance Group Membership {instance_group_name} for cloud {cloud_id} " \
                      f"deletion failed "
            workflow_task.status = WorkflowTask.STATUS_FAILED
            workflow_task.message = message

        db_session.commit()
    LOGGER.info(message)


@celery.task(name="delete_wait_all_instance_group_memberships", base=IBMWorkflowTasksBase)
def delete_wait_all_instance_group_memberships(workflow_task_id):
    """
    Wait for an IBM Instance Group Memberships deletion on IBM Cloud
    :param workflow_task_id:
    :return:
    """
    with get_db_session() as db_session:
        workflow_task: WorkflowTask = db_session.get(WorkflowTask, workflow_task_id)
        if not workflow_task:
            return

        workflow_task.status = WorkflowTask.STATUS_RUNNING
        db_session.commit()

        instance_group: IBMInstanceGroup = db_session.get(
            IBMInstanceGroup, workflow_task.resource_id)
        if not instance_group:
            workflow_task.status = WorkflowTask.STATUS_FAILED
            workflow_task.message = f"IBM Instance Group '{workflow_task.resource_id}' not found"
            db_session.commit()
            LOGGER.info(workflow_task.message)
            return
        lb_resource_id = None
        lb = db_session.query(IBMLoadBalancer).filter_by(id=instance_group.load_balancer_id).first()
        if lb:
            lb_resource_id = lb.resource_id

        cloud_id = instance_group.cloud_id
        region_name = instance_group.region.name
        instance_group_resource_id = instance_group.resource_id

    try:
        instance_group_client = InstanceGroupsClient(cloud_id, region=region_name)
        resp_json = instance_group_client.get_instance_group(instance_group_resource_id)
        lb_resp = None
        if lb_resource_id:
            load_balancer_client = LoadBalancersClient(cloud_id, region=region_name)
            lb_resp = load_balancer_client.get_load_balancer(lb_resource_id)

    except ApiException as ex:
        with get_db_session() as db_session:
            workflow_task: WorkflowTask = db_session.get(WorkflowTask, workflow_task_id)
            if not workflow_task:
                return

            if ex.code == 404:
                instance_group_memberships = db_session.query(
                    IBMInstanceGroupMembership).filter_by(instance_group_id=workflow_task.resource_id).all()
                for instance_group_membership in instance_group_memberships:
                    if instance_group_membership:
                        db_session.delete(instance_group_membership)

                workflow_task.status = WorkflowTask.STATUS_SUCCESSFUL
                LOGGER.info(
                    f"IBM Instance Group Memberships attached with instance group {workflow_task.resource_id} for "
                    f"cloud {cloud_id} deletion successful.")
                db_session.commit()
                return
            else:
                workflow_task.status = WorkflowTask.STATUS_FAILED
                message = f"Cannot delete the Instance Group Memberships attached with instance group " \
                          f"{workflow_task.resource_id} due to reason: {str(ex.message)}"
                workflow_task.message = message
                db_session.commit()
                LOGGER.info(message)
                return

    with get_db_session() as db_session:
        workflow_task: WorkflowTask = db_session.get(WorkflowTask, workflow_task_id)
        if not workflow_task:
            return

        instance_group_status = resp_json["status"]
        instance_group_name = resp_json["name"]
        lb_status = lb_resp.get("provisioning_status", {})

        if instance_group_status in [
            IBMInstanceGroup.STATUS_SCALING,
            IBMInstanceGroup.STATUS_DELETING
        ] or lb_status in [
            IBMLoadBalancer.PROVISIONING_STATUS_MAINTENANCE_PENDING,
            IBMLoadBalancer.PROVISIONING_STATUS_UPDATE_PENDING,
            IBMLoadBalancer.PROVISIONING_STATUS_CREATE_PENDING
        ]:
            message = f"IBM Instance Group Membership {instance_group_name} for cloud {cloud_id} " \
                      f"deletion waiting "
            workflow_task.status = WorkflowTask.STATUS_RUNNING_WAIT
            workflow_task.message = message
        elif instance_group_status == IBMInstanceGroup.STATUS_HEALTHY:
            instance_group_memberships = db_session.query(
                IBMInstanceGroupMembership).filter_by(instance_group_id=workflow_task.resource_id).all()
            for instance_group_membership in instance_group_memberships:
                if instance_group_membership:
                    db_session.delete(instance_group_membership)

            workflow_task.status = WorkflowTask.STATUS_SUCCESSFUL
            message = f"IBM Instance Group Memberships attached with instance group {workflow_task.resource_id} for " \
                      f"cloud {cloud_id} deletion successful."
        else:
            message = f"IBM Instance Group Membership {instance_group_name} for cloud {cloud_id} " \
                      f"deletion failed "
            workflow_task.status = WorkflowTask.STATUS_FAILED
            workflow_task.message = message

        db_session.commit()
    LOGGER.info(message)


@celery.task(name="delete_instance_group_membership", base=IBMWorkflowTasksBase)
def delete_instance_group_membership(workflow_task_id):
    """
    Delete an IBM Instance Group Membership on IBM Cloud
    """
    with get_db_session() as db_session:
        workflow_task: WorkflowTask = db_session.query(WorkflowTask).filter_by(id=workflow_task_id).first()
        if not workflow_task:
            return

        workflow_task.status = WorkflowTask.STATUS_RUNNING
        db_session.commit()

        instance_group_membership: IBMInstanceGroupMembership = db_session.query(IBMInstanceGroupMembership).filter_by(
            id=workflow_task.resource_id).first()
        if not instance_group_membership:
            workflow_task.status = WorkflowTask.STATUS_FAILED
            workflow_task.message = f"IBM Instance Group Membership '{workflow_task.resource_id}' not found"
            db_session.commit()
            LOGGER.info(workflow_task.message)
            return

        region_name = instance_group_membership.instance_group.region.name
        instance_group_membership_resource_id = instance_group_membership.resource_id
        instance_group_resource_id = instance_group_membership.instance_group.resource_id
        cloud_id = instance_group_membership.instance_group.cloud_id

    try:
        client = InstanceGroupsClient(cloud_id, region=region_name)
        client.delete_instance_group_membership(instance_group_id=instance_group_resource_id,
                                                instance_group_membership_id=instance_group_membership_resource_id)
        instance_group_membership_json = client.get_instance_group_membership(
            instance_group_id=instance_group_resource_id,
            instance_group_membership_id=instance_group_membership_resource_id)

    except ApiException as ex:
        # IBM Instance Group Membership is deleted from IBM Cloud Console, but we still have it on VPC + side.
        with get_db_session() as db_session:
            workflow_task: WorkflowTask = db_session.query(WorkflowTask).filter_by(id=workflow_task_id).first()
            if not workflow_task:
                return

            if ex.code == 404:  # 404 means resource is not found on IBM Cloud.
                instance_group_membership: IBMInstanceGroupMembership = db_session.query(
                    IBMInstanceGroupMembership).filter_by(id=workflow_task.resource_id).first()
                if instance_group_membership:
                    db_session.delete(instance_group_membership)

                workflow_task.status = WorkflowTask.STATUS_SUCCESSFUL
                LOGGER.info(
                    f"IBM Instance Group Membership {instance_group_membership_resource_id} for cloud {cloud_id}"
                    f" deletion successful.")
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

        instance_group_membership_status = instance_group_membership_json["status"]
        instance_group_membership_name = instance_group_membership_json["name"]
        if instance_group_membership_status in [IBMInstanceGroupMembership.STATUS_PENDING,
                                                IBMInstanceGroup.STATUS_HEALTHY,
                                                IBMInstanceGroup.STATUS_DELETING]:
            message = f"IBM Instance Group Membership {instance_group_membership_name} for cloud {cloud_id} " \
                      f"deletion waiting "
            workflow_task.status = WorkflowTask.STATUS_RUNNING_WAIT
            workflow_task.message = message
        else:
            message = f"IBM Instance Group Membership {instance_group_membership_name} for cloud {cloud_id} " \
                      f"deletion failed "
            workflow_task.status = WorkflowTask.STATUS_FAILED
            workflow_task.message = message

        db_session.commit()

    LOGGER.info(message)


@celery.task(name="delete_wait_instance_group_membership", base=IBMWorkflowTasksBase)
def delete_wait_instance_group_membership(workflow_task_id):
    """
    Wait tasks for Deletion of an IBM Instance Group Membership on IBM Cloud
    """
    with get_db_session() as db_session:
        workflow_task: WorkflowTask = db_session.query(WorkflowTask).filter_by(id=workflow_task_id).first()
        if not workflow_task:
            return

        workflow_task.status = WorkflowTask.STATUS_RUNNING
        db_session.commit()

        instance_group_membership: IBMInstanceGroupMembership = db_session.query(IBMInstanceGroupMembership).filter_by(
            id=workflow_task.resource_id).first()
        if not instance_group_membership:
            message = f"IBM Instance Group Membership '{workflow_task.resource_id}' not found"
            workflow_task.status = WorkflowTask.STATUS_FAILED
            workflow_task.message = message
            db_session.commit()
            LOGGER.info(message)
            return

        region_name = instance_group_membership.instance_group.region.name
        instance_group_membership_resource_id = instance_group_membership.resource_id
        instance_group_resource_id = instance_group_membership.instance_group.resource_id
        cloud_id = instance_group_membership.instance_group.cloud_id

    try:
        client = InstanceGroupsClient(cloud_id, region=region_name)
        instance_group_membership_json = client.get_instance_group_membership(
            instance_group_id=instance_group_resource_id,
            instance_group_membership_id=instance_group_membership_resource_id)

    except ApiException as ex:
        with get_db_session() as db_session:
            workflow_task: WorkflowTask = db_session.query(WorkflowTask).filter_by(id=workflow_task_id).first()
            if not workflow_task:
                return

            if ex.code == 404:  # 404 means resource is not found on IBM Cloud.
                instance_group_membership: IBMInstanceGroupMembership = db_session.query(
                    IBMInstanceGroupMembership).filter_by(id=workflow_task.resource_id).first()
                if instance_group_membership:
                    db_session.delete(instance_group_membership)

                workflow_task.status = WorkflowTask.STATUS_SUCCESSFUL
                LOGGER.info(
                    f"IBM Instance Group Membership {instance_group_membership_resource_id} for cloud {cloud_id}"
                    f" deletion successful.")
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

        instance_group_membership_status = instance_group_membership_json["status"]
        instance_group_membership_name = instance_group_membership_json["name"]
        if instance_group_membership_status in [IBMInstanceGroupMembership.STATUS_PENDING,
                                                IBMInstanceGroup.STATUS_HEALTHY,
                                                IBMInstanceGroup.STATUS_DELETING]:
            message = f"IBM Instance Group Membership {instance_group_membership_name} for cloud {cloud_id} " \
                      f"deletion waiting "
            workflow_task.status = WorkflowTask.STATUS_RUNNING_WAIT
            workflow_task.message = message
        else:
            message = f"IBM Instance Group Membership {instance_group_membership_name} for cloud {cloud_id} " \
                      f"deletion failed "
            workflow_task.status = WorkflowTask.STATUS_FAILED
            workflow_task.message = message

        db_session.commit()

    LOGGER.info(message)
