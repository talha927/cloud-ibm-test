from copy import deepcopy
from ibm_cloud_sdk_core import ApiException

from ibm import get_db_session, LOGGER
from ibm.common.clients.ibm_clients import InstancesClient
from ibm.common.utils import update_id_or_name_references
from ibm.models import IBMDedicatedHost, IBMDedicatedHostGroup, IBMImage, IBMInstanceProfile, IBMInstanceTemplate, \
    IBMNetworkInterfacePrototype, IBMPlacementGroup, IBMRegion, IBMResourceGroup, IBMResourceLog, IBMSecurityGroup, \
    IBMSshKey, IBMSubnet, IBMVolume, IBMVolumeAttachmentPrototype, IBMVolumeProfile, IBMVolumePrototype, \
    IBMVpcNetwork, IBMZone, WorkflowTask
from ibm.tasks.celery_app import celery_app as celery
from ibm.tasks.common.tasks_base import IBMWorkflowTasksBase
from ibm.tasks.ibm.task_utils import load_previous_associated_resources
from ibm.web.ibm.instances.network_interfaces.schemas import IBMInstanceNetworkInterfaceResourceSchema
from ibm.web.ibm.instances.schemas import PlacementTargetSchema
from ibm.web.ibm.instances.templates.schemas import IBMInstanceTemplateInSchema, IBMInstanceTemplateResourceSchema
from ibm.web.ibm.ssh_keys.schemas import IBMSshKeyResourceSchema
from ibm.web.ibm.volumes.schemas import IBMVolumeResourceSchema


def parse_network_interface_from_ibm_json(network_interface_json, cloud_id, workflow_task_id, db_session):
    workflow_task = db_session.query(WorkflowTask).filter_by(id=workflow_task_id).first()
    if not workflow_task:
        return

    subnet = db_session.query(IBMSubnet).filter_by(
        resource_id=network_interface_json["subnet"]["id"]).first()
    if not subnet:
        workflow_task.status = WorkflowTask.STATUS_FAILED
        workflow_task.message = \
            "Creation Successful but record update failed. The records will update next time discovery runs"
        db_session.commit()
        LOGGER.note(workflow_task.message)
        return

    network_interface = IBMNetworkInterfacePrototype.from_ibm_json_body(json_body=network_interface_json)
    network_interface.subnet = subnet
    for sg in network_interface_json.get("security_groups", []):
        sg_obj = db_session.query(IBMSecurityGroup).filter_by(resource_id=sg["id"],
                                                              cloud_id=cloud_id).first()
        if sg_obj:
            network_interface.security_groups.append(sg_obj)

    return network_interface


@celery.task(name="create_instance_template", base=IBMWorkflowTasksBase)
def create_instance_template(workflow_task_id):
    """
    Create an IBM Instance Template on IBM Cloud
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

        if region.ibm_status == IBMZone.IBM_STATUS_UNAVAILABLE:
            workflow_task.status = WorkflowTask.STATUS_FAILED
            workflow_task.message = f"IBMRegion '{region.name}' unavailable"
            db_session.commit()
            LOGGER.error(workflow_task.message)
            return

        region_name = region.name

        # TODO: Support for volume and source_template
        resource_json.update(**resource_json["instance_by_image"])
        del resource_json["instance_by_image"]

        previous_resources = load_previous_associated_resources(task=workflow_task, session=db_session)
        update_id_or_name_references(
            cloud_id=cloud_id, resource_json=resource_data, resource_schema=IBMInstanceTemplateInSchema,
            db_session=db_session, previous_resources=previous_resources
        )
        update_id_or_name_references(
            cloud_id=cloud_id, resource_json=resource_json, resource_schema=IBMInstanceTemplateResourceSchema,
            db_session=db_session, previous_resources=previous_resources
        )

        if resource_json.get("placement_target"):
            update_id_or_name_references(
                cloud_id=cloud_id, resource_json=resource_json["placement_target"],
                resource_schema=PlacementTargetSchema, previous_resources=previous_resources,
                db_session=db_session
            )
            placement_target = resource_json["placement_target"].get("dedicated_host") or resource_json[
                "placement_target"].get("dedicated_host_group") or resource_json["placement_target"].get(
                "placement_group")
            resource_json["placement_target"] = placement_target

        for ssh_key_json in resource_json.get("keys", []):
            update_id_or_name_references(
                cloud_id=cloud_id, resource_json=ssh_key_json, resource_schema=IBMSshKeyResourceSchema,
                db_session=db_session, previous_resources=previous_resources
            )

        for volume_attachment in resource_json.get("volume_attachments", []):
            update_id_or_name_references(
                cloud_id=cloud_id, resource_json=volume_attachment["volume"],
                resource_schema=IBMVolumeResourceSchema, previous_resources=previous_resources,
                db_session=db_session
            )
        if "boot_volume_attachment" in resource_json:
            update_id_or_name_references(
                cloud_id=cloud_id, resource_json=resource_json["boot_volume_attachment"]["volume"],
                resource_schema=IBMVolumeResourceSchema, previous_resources=previous_resources,
                db_session=db_session
            )
        for network_interface in resource_json.get("network_interfaces", []):
            update_id_or_name_references(
                cloud_id=cloud_id, resource_json=network_interface, previous_resources=previous_resources,
                resource_schema=IBMInstanceNetworkInterfaceResourceSchema,
                db_session=db_session
            )

        if "primary_network_interface" in resource_json:
            update_id_or_name_references(
                cloud_id=cloud_id, resource_json=resource_json["primary_network_interface"],
                resource_schema=IBMInstanceNetworkInterfaceResourceSchema, previous_resources=previous_resources,
                db_session=db_session
            )

    try:
        client = InstancesClient(cloud_id=cloud_id, region=region_name)
        template_json = client.create_instance_template(template_json=resource_json)
    except ApiException as ex:
        with get_db_session() as db_session:
            workflow_task = db_session.query(WorkflowTask).filter_by(id=workflow_task_id).first()
            if not workflow_task:
                return

            workflow_task.status = WorkflowTask.STATUS_FAILED
            workflow_task.message = f"Creation Failed. Reason: {str(ex.message)}"
            db_session.commit()
            LOGGER.fail(workflow_task.message)
            return

    with get_db_session() as db_session:
        workflow_task = db_session.query(WorkflowTask).filter_by(id=workflow_task_id).first()
        if not workflow_task:
            return

        with db_session.no_autoflush:
            resource_group = \
                db_session.query(IBMResourceGroup).filter_by(
                    resource_id=template_json["resource_group"]["id"], cloud_id=cloud_id
                ).first()

            zone = db_session.query(IBMZone).filter_by(name=template_json["zone"]["name"], cloud_id=cloud_id).first()
            instance_profile = db_session.query(IBMInstanceProfile). \
                filter_by(name=template_json["profile"]["name"], cloud_id=cloud_id).first()

            vpc_network = db_session.query(IBMVpcNetwork).filter_by(resource_id=template_json["vpc"]["id"],
                                                                    cloud_id=cloud_id).first()
            if not vpc_network:
                workflow_task.status = WorkflowTask.STATUS_FAILED
                workflow_task.message = f"IBM Vpc Network '{template_json['vpc']['id']}' not found"
                db_session.commit()
                LOGGER.fail(workflow_task.message)
                return

            if not (instance_profile and resource_group and zone):
                workflow_task.status = WorkflowTask.STATUS_FAILED
                workflow_task.message = \
                    "Creation Successful but record update failed. The records will update next time discovery runs"
                db_session.commit()
                LOGGER.note(workflow_task.message)
                return

            instance_template = IBMInstanceTemplate.from_ibm_json_body(json_body=template_json)
            instance_template.vpc_network = vpc_network
            instance_template.zone = zone
            instance_template.instance_profile = instance_profile
            instance_template.resource_group = resource_group

            for ssh_key in template_json["keys"]:
                ssh_key_obj = db_session.query(IBMSshKey).filter_by(
                    resource_id=ssh_key["id"], cloud_id=cloud_id).first()
                if ssh_key_obj:
                    instance_template.keys.append(ssh_key_obj)

            if "image" in template_json:
                image = db_session.query(IBMImage).filter_by(resource_id=template_json["image"]["id"],
                                                             cloud_id=cloud_id).first()
                instance_template.image = image

            if "boot_volume_attachment" in template_json:
                volume_json = template_json["boot_volume_attachment"]["volume"]
                if "id" in volume_json:  # provisioned_volume
                    volume = db_session.query(IBMVolume).filter_by(resource_id=volume_json["id"]).first()
                else:  # volume_prototype
                    volume = IBMVolumePrototype.from_ibm_json_body(json_body=volume_json)
                    volume_profile = db_session.query(IBMVolumeProfile).filter_by(
                        name=volume_json["profile"]["name"], cloud_id=cloud_id
                    ).first()
                    volume.profile = volume_profile
                    volume.zone = zone
                    volume.resource_group = resource_group

                volume_attachment = \
                    IBMVolumeAttachmentPrototype.from_ibm_json_body(json_body=template_json["boot_volume_attachment"])
                volume_attachment.is_boot = True
                volume_attachment.volume = volume
                instance_template.volume_attachments.append(volume_attachment)

            for volume_attachment_json in template_json.get("volume_attachments", []):
                volume_json = volume_attachment_json["volume"]
                if "id" in volume_json:  # provisioned_volume
                    volume = db_session.query(IBMVolume).filter_by(resource_id=volume_json["id"]).first()
                else:  # volume_prototype
                    volume = IBMVolumePrototype.from_ibm_json_body(json_body=volume_json)
                    volume_profile = db_session.query(IBMVolumeProfile).filter_by(
                        name=volume_json["profile"]["name"], cloud_id=cloud_id
                    ).first()
                    volume.profile = volume_profile
                    volume.zone = zone
                    volume.resource_group = resource_group

                volume_attachment = IBMVolumeAttachmentPrototype.from_ibm_json_body(json_body=volume_attachment_json)
                volume_attachment.volume = volume
                instance_template.volume_attachments.append(volume_attachment)

            placement_target = \
                db_session.query(IBMDedicatedHost).filter_by(
                    resource_id=template_json.get('placement_target', {}).get('id'), cloud_id=cloud_id
                ).first() or db_session.query(IBMDedicatedHostGroup).filter_by(
                    resource_id=template_json.get('placement_target', {}).get('id'), cloud_id=cloud_id
                ).first() or db_session.query(IBMPlacementGroup).filter_by(
                    resource_id=template_json.get('placement_target', {}).get('id'), cloud_id=cloud_id
                ).first()
            instance_template.placement_target = placement_target

            for network_interface_json in template_json.get("network_interfaces", []):
                network_interface = \
                    parse_network_interface_from_ibm_json(
                        network_interface_json, cloud_id, workflow_task_id, db_session
                    )
                instance_template.network_interfaces.append(network_interface)

            if "primary_network_interface" in template_json:
                primary_network_interface_json = template_json["primary_network_interface"]
                primary_network_interface = \
                    parse_network_interface_from_ibm_json(
                        primary_network_interface_json, cloud_id, workflow_task_id, db_session
                    )
                primary_network_interface.is_primary = True
                instance_template.network_interfaces.append(primary_network_interface)

            instance_template_json = instance_template.to_json()
            instance_template_json["created_at"] = str(instance_template_json["created_at"])

            IBMResourceLog(
                resource_id=instance_template.resource_id, region=instance_template.zone.region,
                status=IBMResourceLog.STATUS_ADDED, resource_type=IBMInstanceTemplate.__name__,
                data=instance_template_json)

            db_session.commit()

        workflow_task.status = WorkflowTask.STATUS_SUCCESSFUL
        db_session.commit()
        LOGGER.success(f"IBM Instance Template '{instance_template.name}' creation for cloud '{cloud_id}' successful")


@celery.task(name="delete_instance_template", base=IBMWorkflowTasksBase)
def delete_instance_template(workflow_task_id):
    """
    Delete an IBM Instance Template on IBM Cloud
    """
    with get_db_session() as db_session:
        workflow_task: WorkflowTask = db_session.get(WorkflowTask, workflow_task_id)
        if not workflow_task:
            return

        workflow_task.status = WorkflowTask.STATUS_RUNNING
        db_session.commit()

        instance_template: IBMInstanceTemplate = db_session.get(IBMInstanceTemplate, workflow_task.resource_id)
        if not instance_template:
            workflow_task.status = WorkflowTask.STATUS_FAILED
            workflow_task.message = f"IBMInstanceTemplate '{workflow_task.resource_id}' not found"
            db_session.commit()
            LOGGER.error(workflow_task.message)
            return

        region_name = instance_template.region.name
        instance_template_resource_id = instance_template.resource_id
        cloud_id = instance_template.cloud_id
        instance_template_name = instance_template.name
    try:
        client = InstancesClient(cloud_id, region=region_name)
        client.delete_instance_template(instance_template_resource_id)

    except ApiException as ex:
        with get_db_session() as db_session:
            workflow_task: WorkflowTask = db_session.get(WorkflowTask, workflow_task_id)
            if not workflow_task:
                return

            if ex.code == 404:
                instance_template: IBMInstanceTemplate = db_session.get(IBMInstanceTemplate, workflow_task.resource_id)
                if instance_template:
                    db_session.delete(instance_template)

                workflow_task.status = WorkflowTask.STATUS_SUCCESSFUL
                LOGGER.success(
                    f"IBMInstanceTemplate {instance_template_name} for cloud {cloud_id} deletion successful.")

                instance_template_json = instance_template.to_json()
                instance_template_json["created_at"] = str(instance_template_json["created_at"])

                IBMResourceLog(
                    resource_id=instance_template.resource_id, region=instance_template.zone.region,
                    status=IBMResourceLog.STATUS_DELETED, resource_type=IBMInstanceTemplate.__name__,
                    data=instance_template_json)

                db_session.commit()
                return

            workflow_task.status = WorkflowTask.STATUS_FAILED
            workflow_task.message = f"Instance Template Deletion Failed. Reason: {str(ex.message)}"
            db_session.commit()
            LOGGER.fail(workflow_task.message)
            return

    with get_db_session() as db_session:
        workflow_task: WorkflowTask = db_session.get(WorkflowTask, workflow_task_id)
        if not workflow_task:
            return

        instance_template: IBMInstanceTemplate = db_session.get(IBMInstanceTemplate, workflow_task.resource_id)
        if instance_template:
            db_session.delete(instance_template)

        IBMResourceLog(
            resource_id=instance_template.resource_id, region=instance_template.zone.region,
            status=IBMResourceLog.STATUS_DELETED, resource_type=IBMInstanceTemplate.__name__,
            data=instance_template.to_json())

        workflow_task.status = WorkflowTask.STATUS_SUCCESSFUL
        LOGGER.success(f"IBMInstanceTemplate {instance_template_name} for cloud {cloud_id} deletion successful.")
        db_session.commit()
