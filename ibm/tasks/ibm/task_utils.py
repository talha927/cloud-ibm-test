import logging
from ibm_cloud_sdk_core import ApiException

from ibm.common.clients.ibm_clients import InstancesClient, VolumesClient
from ibm.models import WorkflowTask
from ibm.tasks.common.mappers import RESOURCE_TYPE_TO_RESOURCE_CLASS_MAPPER
from ibm.web import db as ibmdb

LOGGER = logging.getLogger(__name__)


def return_complete_instance_json(cloud_id, region_name, instance_json):
    """
    Get all Instance dependent resources json from IBM and return a complete information json
    """
    try:
        instance_client = InstancesClient(cloud_id, region=region_name)
        volume_client = VolumesClient(cloud_id, region=region_name)
        volume_attachments_list = []
        for volume_attachment_json in instance_client.list_instance_volume_attachments(instance_id=instance_json["id"]):
            volume_json = volume_client.get_volume(
                volume_id=volume_attachment_json["volume"]["id"]
            )
            volume_attachment_json["volume"] = volume_json
            volume_attachments_list.append(volume_attachment_json)
        instance_json["volume_attachments"] = volume_attachments_list

        network_interfaces_list = []
        for network_interface_json in instance_json["network_interfaces"]:
            network_interface_json = instance_client.get_instance_network_interface(
                instance_id=instance_json["id"], network_interface_id=network_interface_json["id"])
            network_interfaces_list.append(network_interface_json)
        instance_json["network_interfaces"] = network_interfaces_list
    except ApiException:
        return {}
    return instance_json


def load_previous_associated_resources(task, task_type=WorkflowTask.TYPE_CREATE, session=None):
    """
    This function query all previous tasks of the specified task which have been created and use the resource_id to
    query the resource specific model and transform it to a dictionary.
    :param task: task.
    :param session: session.
    :param task_type: task_type such as CREATE, UPDATE.
    :return:
    """
    session = session or ibmdb.session
    resource_name_value_dict = dict()
    for previous_task in task.previous_tasks.filter_by(task_type=task_type).all():
        resource = session.query(RESOURCE_TYPE_TO_RESOURCE_CLASS_MAPPER[previous_task.resource_type]).filter_by(
            id=previous_task.resource_id).first()
        if not resource:
            LOGGER.info(f"{previous_task.resource_type} with ID {previous_task.resource_id} not found in DB")
            continue

        if not previous_task.task_metadata.get("resource_data"):
            continue
        prev_resource_id = previous_task.task_metadata["resource_data"].get("id")
        if not prev_resource_id:
            continue
        resource_name_value_dict[prev_resource_id] = resource

    for previous_root in task.root.previous_roots.all():
        for previous_task in previous_root.associated_tasks.filter_by(task_type=task_type).all():
            resource = session.query(RESOURCE_TYPE_TO_RESOURCE_CLASS_MAPPER[previous_task.resource_type]).filter_by(
                id=previous_task.resource_id).first()
            if not resource:
                LOGGER.info(f"{previous_task.resource_type} with ID {previous_task.resource_id} not found in DB")
                continue

            resource_data = previous_task.task_metadata.get("resource_data")
            db_id = resource_data.get("id") if resource_data else previous_task.task_metadata.get("id")
            if not db_id:
                continue

            resource_name_value_dict[db_id] = resource

    return resource_name_value_dict


def get_relative_time_seconds(days_count=30, month_count=None):
    if month_count:
        return -60 * 60 * 24 * 30 * month_count  # sec * min * hr * day * month
    else:
        return -60 * 60 * 24 * days_count
