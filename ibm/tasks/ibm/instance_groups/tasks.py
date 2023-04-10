import logging
from copy import deepcopy
from ibm_cloud_sdk_core import ApiException

from ibm import get_db_session
from ibm.common.clients.ibm_clients import InstanceGroupsClient, InstancesClient
from ibm.common.utils import update_id_or_name_references
from ibm.models import IBMInstance, IBMInstanceGroup, IBMInstanceGroupMembership, IBMInstanceProfile, \
    IBMInstanceTemplate, IBMPool, IBMRegion, IBMResourceGroup, IBMSubnet, IBMVpcNetwork, IBMZone, WorkflowTask
from ibm.tasks.celery_app import celery_app as celery
from ibm.tasks.common.tasks_base import IBMWorkflowTasksBase
from ibm.tasks.ibm.task_utils import load_previous_associated_resources
from ibm.web.ibm.instance_groups.schemas import IBMInstanceGroupInSchema, IBMInstanceGroupResourceSchema

LOGGER = logging.getLogger(__name__)


@celery.task(name="create_instance_group", base=IBMWorkflowTasksBase)
def create_instance_group(workflow_task_id):
    """
    Create an IBM Instance Group on IBM Cloud
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
            LOGGER.info(workflow_task.message)
            return

        if region.ibm_status == IBMRegion.IBM_STATUS_UNAVAILABLE:
            workflow_task.status = WorkflowTask.STATUS_FAILED
            workflow_task.message = f"IBMRegion '{region.name}' unavailable"
            db_session.commit()
            LOGGER.info(workflow_task.message)
            return

        region_name = region.name
        resource_json.pop('instance_group_managers', None)
        resource_json.pop('instance_group_manager_policies', None)

        # This is not required but would help with code consistency
        previous_resources = load_previous_associated_resources(task=workflow_task, session=db_session)
        update_id_or_name_references(
            cloud_id=cloud_id, resource_json=resource_data, resource_schema=IBMInstanceGroupInSchema,
            db_session=db_session, previous_resources=previous_resources
        )

        update_id_or_name_references(
            cloud_id=cloud_id, resource_json=resource_json, resource_schema=IBMInstanceGroupResourceSchema,
            db_session=db_session, previous_resources=previous_resources
        )

    try:
        client = InstanceGroupsClient(cloud_id=cloud_id, region=region_name, )
        resp_json = client.create_instance_group(instance_group_json=resource_json)
    except ApiException as ex:
        with get_db_session() as db_session:
            workflow_task = db_session.query(WorkflowTask).filter_by(id=workflow_task_id).first()
            if not workflow_task:
                return

            workflow_task.status = WorkflowTask.STATUS_FAILED
            workflow_task.message = f"Creation Failed. Reason: {str(ex.message)}"
            db_session.commit()

        LOGGER.info("Create Instance Group failed with status code " + str(ex.code) + ": " + ex.message)
        return

    with get_db_session() as db_session:
        workflow_task = db_session.query(WorkflowTask).filter_by(id=workflow_task_id).first()
        if not workflow_task:
            return

        instance_group_status = resp_json["status"]
        instance_group_name = resp_json["name"]
        instance_group_resource_id = resp_json["id"]
        if instance_group_status in [IBMInstanceGroup.STATUS_SCALING,
                                     IBMInstanceGroup.STATUS_HEALTHY]:
            metadata = workflow_task.task_metadata.copy() if workflow_task.task_metadata else {}
            metadata["ibm_resource_id"] = instance_group_resource_id
            workflow_task.task_metadata = metadata

            workflow_task.status = WorkflowTask.STATUS_RUNNING_WAIT
            message = f"IBM Instance Group {instance_group_name} for cloud {cloud_id} creation waiting"
        else:
            message = f"IBM Instance Group {instance_group_name} for cloud {cloud_id} creation failed"
            workflow_task.message = message
            workflow_task.status = WorkflowTask.STATUS_FAILED
        db_session.commit()
    LOGGER.info(message)


@celery.task(name="create_wait_instance_group", base=IBMWorkflowTasksBase)
def create_wait_instance_group(workflow_task_id):
    """
    Wait for an IBM Instance Group creation on IBM Cloud
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
        client = InstanceGroupsClient(cloud_id=cloud_id, region=region_name)
        instance_client = InstancesClient(cloud_id=cloud_id, region=region_name)
        instance_group_json = client.get_instance_group(instance_group_resource_id=resource_id)

        if instance_group_json["status"] == IBMInstanceGroup.STATUS_HEALTHY:
            membership_list = client.list_instance_group_memberships(instance_group_id=resource_id)
            instance_group_member_instances_dict = {}
            for membership in membership_list:
                instance_json = instance_client.get_instance(instance_id=membership["instance"]["id"])
                instance_group_member_instances_dict[membership["id"]] = instance_json

    except ApiException as ex:
        with get_db_session() as db_session:
            workflow_task = db_session.query(WorkflowTask).filter_by(id=workflow_task_id).first()
            if not workflow_task:
                return

            workflow_task.status = WorkflowTask.STATUS_FAILED
            workflow_task.message = f"Creation Failed. Reason: {str(ex.message)}"
            db_session.commit()

        LOGGER.info("Create Wait Instance Group Membership failed with status code " + str(ex.code) + ": " + ex.message)
        return

    with get_db_session() as db_session:
        workflow_task = db_session.query(WorkflowTask).filter_by(id=workflow_task_id).first()
        if not workflow_task:
            return
        instance_group_status = instance_group_json["status"]
        instance_group_name = instance_group_json["name"]
        if instance_group_status == IBMInstanceGroup.STATUS_HEALTHY:
            with db_session.no_autoflush:
                region = db_session.query(IBMRegion).filter_by(id=region_id, cloud_id=cloud_id).first()
                resource_group = \
                    db_session.query(IBMResourceGroup).filter_by(
                        resource_id=instance_group_json["resource_group"]["id"], cloud_id=cloud_id
                    ).first()
                vpc = \
                    db_session.query(IBMVpcNetwork).filter_by(
                        resource_id=instance_group_json["vpc"]["id"], cloud_id=cloud_id
                    ).first()
                instance_template = \
                    db_session.query(IBMInstanceTemplate).filter_by(
                        resource_id=instance_group_json["instance_template"]["id"], cloud_id=cloud_id
                    ).first()
                load_balancer_pool = \
                    db_session.query(IBMPool).filter_by(
                        resource_id=instance_group_json.get('load_balancer_pool', {}).get('id'), cloud_id=cloud_id
                    ).first()

                if not (resource_group and region and vpc and instance_template):
                    workflow_task.status = WorkflowTask.STATUS_FAILED
                    workflow_task.message = \
                        "Creation Successful but record update failed. The records will update next time discovery runs"
                    LOGGER.info(workflow_task.message)
                    db_session.commit()
                    return

                instance_group = IBMInstanceGroup.from_ibm_json_body(json_body=instance_group_json)

                for subnet in instance_group_json["subnets"]:
                    ibm_subnet = \
                        db_session.query(IBMSubnet).filter_by(
                            resource_id=subnet["id"], cloud_id=cloud_id
                        ).first()
                    if not ibm_subnet:
                        workflow_task.status = WorkflowTask.STATUS_FAILED
                        workflow_task.message = \
                            "Creation Successful but record update failed. The records will update next time " \
                            "discovery runs"
                        db_session.commit()
                        return
                    instance_group.subnets.append(ibm_subnet)

                for membership_json in membership_list:
                    instance_json = instance_group_member_instances_dict[membership_json["id"]]
                    instance = IBMInstance.from_ibm_json_body(instance_json)
                    resource_group = db_session.query(IBMResourceGroup).filter_by(
                        resource_id=instance_json["resource_group"]["id"],
                        cloud_id=cloud_id).first()
                    vpc = db_session.query(IBMVpcNetwork).filter_by(
                        resource_id=instance_json["vpc"]["id"],
                        cloud_id=cloud_id).first()
                    profile = db_session.query(IBMInstanceProfile).filter_by(
                        name=instance_json["profile"]["name"],
                        cloud_id=cloud_id).first()
                    zone = db_session.query(IBMZone).filter_by(
                        name=instance_json["zone"]["name"],
                        cloud_id=cloud_id).first()

                    instance.resource_group = resource_group
                    instance.vpc_network = vpc
                    instance.instance_profile = profile
                    instance.zone = zone

                    instance_template_obj = \
                        db_session.query(IBMInstanceTemplate).filter_by(
                            resource_id=membership_json["instance_template"]["id"], cloud_id=cloud_id
                        ).first()

                    membership = IBMInstanceGroupMembership.from_ibm_json_body(membership_json)
                    membership.instances = instance
                    membership.instance_template = instance_template_obj

                    instance_group.memberships.append(membership)

                instance_group.region = region
                instance_group.resource_group = resource_group
                instance_group.vpc_network = vpc
                instance_group.instance_template = instance_template
                if load_balancer_pool:
                    load_balancer = load_balancer_pool.load_balancer
                    instance_group.load_balancer = load_balancer
                instance_group_id = instance_group.id
                db_session.commit()

            workflow_task.status = WorkflowTask.STATUS_SUCCESSFUL
            workflow_task.resource_id = instance_group_id
            message = f"IBM Instance Group {instance_group_name} for cloud {cloud_id} creation successful"
        elif instance_group_status == IBMInstanceGroup.STATUS_SCALING:
            workflow_task.status = WorkflowTask.STATUS_RUNNING_WAIT
            message = f"IBM Instance Group {instance_group_name} for cloud {cloud_id} creation waiting"
        else:
            message = f"IBM Instance Group {instance_group_name} for cloud {cloud_id} creation failed"
            workflow_task.message = message
            workflow_task.status = WorkflowTask.STATUS_FAILED
        db_session.commit()
    LOGGER.info(message)


@celery.task(name="delete_instance_group", base=IBMWorkflowTasksBase)
def delete_instance_group(workflow_task_id):
    """
    Delete an IBM Instance Group
    :param workflow_task_id:
    :return:
    """

    with get_db_session() as db_session:
        workflow_task: WorkflowTask = db_session.get(WorkflowTask, workflow_task_id)
        if not workflow_task:
            return

        workflow_task.status = WorkflowTask.STATUS_RUNNING
        db_session.commit()

        instance_group: IBMInstanceGroup = db_session.get(IBMInstanceGroup, workflow_task.resource_id)
        if not instance_group:
            workflow_task.status = WorkflowTask.STATUS_FAILED
            workflow_task.message = f"IBM Instance Group '{workflow_task.resource_id}' not found"
            db_session.commit()
            LOGGER.info(workflow_task.message)
            return

        cloud_id = instance_group.cloud_id
        region_name = instance_group.region.name
        instance_group_resource_id = instance_group.resource_id

    try:
        instance_group_client = InstanceGroupsClient(cloud_id, region=region_name)
        instance_group_client.delete_instance_group(instance_group_resource_id)
        instance_group_json = instance_group_client.get_instance_group(instance_group_resource_id)

    except ApiException as ex:
        with get_db_session() as db_session:
            workflow_task: WorkflowTask = db_session.get(WorkflowTask, workflow_task_id)
            if not workflow_task:
                return

            if ex.code == 404:
                instance_group: IBMInstanceGroup = db_session.get(IBMInstanceGroup, workflow_task.resource_id)
                if instance_group:
                    db_session.delete(instance_group)

                workflow_task.status = WorkflowTask.STATUS_SUCCESSFUL
                LOGGER.info(
                    f"IBM Instance Group {workflow_task.resource_id} for cloud {cloud_id} deletion successful.")
                db_session.commit()
                return
            else:
                workflow_task.status = WorkflowTask.STATUS_FAILED
                message = \
                    f"Cannot delete the Instance Group {workflow_task.resource_id} due to reason: {str(ex.message)}"
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
                                     IBMInstanceGroup.STATUS_HEALTHY,
                                     IBMInstanceGroup.STATUS_DELETING]:
            workflow_task.status = WorkflowTask.STATUS_RUNNING_WAIT
            message = f"IBM Instance Group {instance_group_name} for cloud {cloud_id} deletion waiting"
        else:
            message = f"IBM Instance Group {instance_group_name} for cloud {cloud_id} deletion failed"
            workflow_task.message = message
            workflow_task.status = WorkflowTask.STATUS_FAILED

        db_session.commit()
    LOGGER.info(message)


@celery.task(name="delete_wait_instance_group", base=IBMWorkflowTasksBase)
def delete_wait_instance_group(workflow_task_id):
    """
    Wait for an IBM Instance Group deletion on IBM Cloud
    :param workflow_task_id:
    :return:
    """
    with get_db_session() as db_session:
        workflow_task: WorkflowTask = db_session.get(WorkflowTask, workflow_task_id)
        if not workflow_task:
            return

        workflow_task.status = WorkflowTask.STATUS_RUNNING
        db_session.commit()

        instance_group: IBMInstanceGroup = db_session.get(IBMInstanceGroup, workflow_task.resource_id)
        if not instance_group:
            workflow_task.status = WorkflowTask.STATUS_SUCCESSFUL
            db_session.commit()
            LOGGER.info(f"IBMInstanceGroup '{workflow_task.resource_id}' deletion successful.")
            return

        cloud_id = instance_group.cloud_id
        region_name = instance_group.region.name
        instance_group_resource_id = instance_group.resource_id

    try:
        instance_group_client = InstanceGroupsClient(cloud_id, region=region_name)
        resp_json = instance_group_client.get_instance_group(instance_group_resource_id)

    except ApiException as ex:
        with get_db_session() as db_session:
            workflow_task: WorkflowTask = db_session.get(WorkflowTask, workflow_task_id)
            if not workflow_task:
                return

            if ex.code == 404:
                instance_group: IBMInstanceGroup = db_session.get(IBMInstanceGroup, workflow_task.resource_id)
                if instance_group:
                    db_session.delete(instance_group)

                workflow_task.status = WorkflowTask.STATUS_SUCCESSFUL
                LOGGER.info(
                    f"IBM Instance Group {workflow_task.resource_id} for cloud {cloud_id} deletion successful.")

                db_session.commit()
                return
            else:
                workflow_task.status = WorkflowTask.STATUS_FAILED
                message = \
                    f"Cannot delete the Instance Group {workflow_task.resource_id} due to reason: {str(ex.message)}"
                workflow_task.message = message
                db_session.commit()
                LOGGER.info(message)
                return

    with get_db_session() as db_session:
        workflow_task: WorkflowTask = db_session.get(WorkflowTask, workflow_task_id)
        if not workflow_task:
            return

        instance_group_name = resp_json["name"]
        if resp_json["status"] in [IBMInstanceGroup.STATUS_SCALING,
                                   IBMInstanceGroup.STATUS_DELETING,
                                   IBMInstanceGroup.STATUS_HEALTHY]:
            workflow_task.status = WorkflowTask.STATUS_RUNNING_WAIT
            message = f"IBM Instance Group {instance_group_name} for cloud {cloud_id} deletion waiting"
        else:
            message = f"IBM Instance Group {instance_group_name} for cloud {cloud_id} deletion failed"
            workflow_task.message = message
            workflow_task.status = WorkflowTask.STATUS_FAILED

        db_session.commit()
    LOGGER.info(message)
