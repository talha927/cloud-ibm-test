from copy import deepcopy
from random import randint

import requests
from SoftLayer import SoftLayerAPIError
from ibm_botocore.exceptions import ClientError
from ibm_cloud_sdk_core import ApiException
from ping3 import ping
from sdcclient import SdMonitorClient

from config import WorkerConfig
from ibm import get_db_session, LOGGER
from ibm.common.clients.ibm_clients import COSClient, InstancesClient
from ibm.common.clients.softlayer_clients import SoftlayerImageClient, SoftlayerInstanceClient
from ibm.common.clients.softlayer_clients.exceptions import SLAuthError, SLExecuteError, SLInvalidRequestError, \
    SLRateLimitExceededError
from ibm.common.utils import get_cos_object_name, update_id_or_name_references
from ibm.models import IBMCloud, IBMCOSBucket, IBMImage, IBMInstance, IBMInstanceDisk, IBMInstanceProfile, \
    IBMMonitoringToken, IBMNetworkInterface, IBMRegion, IBMResourceGroup, IBMResourceLog, IBMResourceTracking, \
    IBMRightSizingRecommendation, IBMSecurityGroup, IBMSshKey, IBMSubnet, IBMVolume, IBMVolumeAttachment, \
    IBMVolumeProfile, IBMVpcNetwork, IBMZone, SoftlayerCloud, WorkflowTask
from ibm.models.idle_resources.idle_resource_models import IBMIdleResource
from ibm.models.softlayer.resources_models import SoftLayerInstance
from ibm.tasks.celery_app import celery_app as celery
from ibm.tasks.common.tasks_base import IBMWorkflowTasksBase
from ibm.tasks.ibm.consts import METRICS, METRICS_FOR_IDLE_INSTANCES, MONITORING_INSTANCE_URL
from ibm.tasks.ibm.recommendations.consts import LOWEST_INSTANCE_PROFILE
from ibm.tasks.ibm.recommendations.utils import get_cost_saving_instance_profile
from ibm.tasks.ibm.task_utils import get_relative_time_seconds, load_previous_associated_resources, \
    return_complete_instance_json
from ibm.web.common.data_migration.volume_extraction_utils import construct_user_data_script
from ibm.web.ibm.instances.consts import InstanceMigrationConsts
from ibm.web.ibm.instances.network_interfaces.schemas import IBMInstanceNetworkInterfaceResourceSchema
from ibm.web.ibm.instances.schemas import IBMInstanceResourceSchema, IBMRightSizeInSchema, \
    IBMRightSizeResourceSchema, PlacementTargetSchema
from ibm.web.ibm.volumes.schemas import IBMVolumeResourceSchema
from ibm.web.resource_tracking.utils import create_resource_tracking_object


@celery.task(name="create_ibm_instance", base=IBMWorkflowTasksBase)
def create_ibm_instance(workflow_task_id):
    """
    Create an IBM Instance on IBM Cloud
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
        # TODO look for some good fix in case of CLASSIC_VSI
        if not resource_json.get("image") and not resource_json["boot_volume_attachment"]["volume"] \
                .get("source_snapshot"):
            image = db_session.query(IBMImage).filter_by(
                operating_system_id=resource_data["migration_json"]["operating_system"]["id"], visibility="public",
                region_id=region_id
            ).first()
            resource_json["image"] = {"id": image.id}
        # TODO Temp fix, Need to get only one from schema layer
        # TODO add exception handling
        # if resource_data.get("migration_json"):
        resource_json = construct_user_data_script(
            instance=resource_json, cloud_id=cloud_id, region_id=region_id,
            migration_json=resource_data.get("migration_json")
        )
        if not resource_json:
            with get_db_session() as db_session:
                workflow_task = db_session.query(WorkflowTask).filter_by(id=workflow_task_id).first()
                if not workflow_task:
                    return

                workflow_task.status = WorkflowTask.STATUS_FAILED
                workflow_task.message = f"IBMInstance: {resource_json['name']} payload has issues for Volume " \
                                        f"Migration for IBM Cloud: {cloud_id} "
                db_session.commit()
                LOGGER.debug(workflow_task.message)
                return

        if resource_json.get("boot_volume_attachment", {}).get("volume", {}).get("source_snapshot"):
            resource_json.pop("image", None)
        previous_resources = load_previous_associated_resources(task=workflow_task, session=db_session)
        update_id_or_name_references(
            cloud_id=cloud_id, resource_json=resource_json, resource_schema=IBMInstanceResourceSchema,
            db_session=db_session, previous_resources=previous_resources, region_id=region_id
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

        for volume_attachment in resource_json.get("volume_attachments", []):
            volume_attachment.pop("name", None)
            update_id_or_name_references(
                cloud_id=cloud_id, resource_json=volume_attachment["volume"],
                resource_schema=IBMVolumeResourceSchema, previous_resources=previous_resources,
                db_session=db_session
            )

        update_id_or_name_references(
            cloud_id=cloud_id, resource_json=resource_json["boot_volume_attachment"].get("volume", {}),
            resource_schema=IBMVolumeResourceSchema, previous_resources=previous_resources,
            db_session=db_session
        )
        for network_interface in resource_json.get("network_interfaces", []):
            network_interface.pop("floating_ip", None)
            network_interface.pop("id", None)
            update_id_or_name_references(
                cloud_id=cloud_id, resource_json=network_interface,
                resource_schema=IBMInstanceNetworkInterfaceResourceSchema, previous_resources=previous_resources,
                db_session=db_session
            )
        resource_json["primary_network_interface"].pop("floating_ip", None)
        resource_json["primary_network_interface"].pop("id", None)
        update_id_or_name_references(
            cloud_id=cloud_id, resource_json=resource_json["primary_network_interface"],
            resource_schema=IBMInstanceNetworkInterfaceResourceSchema, previous_resources=previous_resources,
            db_session=db_session
        )
    try:
        client = InstancesClient(cloud_id=cloud_id, region=region_name)
        resp_json = client.create_instance(instance_json=resource_json)
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

        instance_status = resp_json["status"]
        instance_name = resp_json["name"]
        instance_resource_id = resp_json["id"]
        if instance_status in [
            IBMInstance.STATUS_PENDING, IBMInstance.STATUS_RESTARTING, IBMInstance.STATUS_RUNNING,
            IBMInstance.STATUS_STARTING
        ]:
            metadata = workflow_task.task_metadata.copy() if workflow_task.task_metadata else {}
            metadata["ibm_resource_id"] = instance_resource_id
            workflow_task.task_metadata = metadata
            workflow_task.status = WorkflowTask.STATUS_RUNNING_WAIT
            workflow_task.message = f"IBM Instance {instance_name} for cloud {cloud_id} creation waiting"
            LOGGER.info(workflow_task.message)
        else:
            workflow_task.message = f"IBM Instance {instance_name} for cloud {cloud_id} creation failed"
            workflow_task.status = WorkflowTask.STATUS_FAILED
            LOGGER.fail(workflow_task.message)

        db_session.commit()


@celery.task(name="create_wait_ibm_instance", base=IBMWorkflowTasksBase)
def create_wait_ibm_instance(workflow_task_id):
    """
    Wait for an IBM Instance creation on IBM Cloud
    """
    with get_db_session() as db_session:
        workflow_task = db_session.query(WorkflowTask).filter_by(id=workflow_task_id).first()
        if not workflow_task:
            return

        workflow_task.status = WorkflowTask.STATUS_RUNNING
        db_session.commit()

        resource_data = deepcopy(workflow_task.task_metadata["resource_data"])
        resource_group_dict = deepcopy(resource_data["resource_json"]["resource_group"])
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
        client = InstancesClient(cloud_id=cloud_id, region=region_name)
        instance_json = client.get_instance(instance_id=resource_id)
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

        if instance_json["status"] in [IBMInstance.STATUS_STOPPING, IBMInstance.STATUS_DELETING,
                                       IBMInstance.STATUS_STOPPED]:
            workflow_task.status = WorkflowTask.STATUS_FAILED
            workflow_task.message = f"IBM Instance '{instance_json['name']}' creation for cloud '{cloud_id}' " \
                                    f"failed on IBM Cloud"
            db_session.commit()
            LOGGER.fail(workflow_task.message)
            return

        elif instance_json["status"] in [
            IBMInstance.STATUS_PENDING, IBMInstance.STATUS_RESTARTING, IBMInstance.STATUS_STARTING
        ]:
            workflow_task.status = WorkflowTask.STATUS_RUNNING_WAIT
            workflow_task.message = f"IBM Instance '{instance_json['name']}' creation for cloud '{cloud_id}' waiting"
            db_session.commit()
            LOGGER.info(workflow_task.message)
            return

    # TODO fix this portion if we really need this method or some other way
    instance_json = return_complete_instance_json(
        cloud_id=cloud_id, region_name=region_name, instance_json=instance_json
    )
    instance_config_json = client.get_instance_initialization(instance_id=resource_id)

    with get_db_session() as db_session:
        workflow_task = db_session.query(WorkflowTask).filter_by(id=workflow_task_id).first()
        if not workflow_task:
            return

        with db_session.no_autoflush:
            if not instance_json:
                workflow_task.status = WorkflowTask.STATUS_FAILED
                workflow_task.message = \
                    "Creation Successful but record update failed. The records will update next time discovery runs"
                db_session.commit()
                LOGGER.note(workflow_task.message)
                return

            ibm_cloud = db_session.query(IBMCloud).filter_by(
                id=cloud_id, status=IBMCloud.STATUS_VALID, deleted=False
            ).first()

            instance = IBMInstance.from_ibm_json_body(json_body=instance_json)
            zone = db_session.query(IBMZone).filter_by(name=instance_json["zone"]["name"],
                                                       cloud_id=cloud_id).first()
            vpc_network = db_session.query(IBMVpcNetwork).filter_by(resource_id=instance_json["vpc"]["id"],
                                                                    cloud_id=cloud_id).first()

            for ssh_key in instance_config_json["keys"]:
                ssh_key_obj = db_session.query(IBMSshKey).filter_by(
                    resource_id=ssh_key["id"], cloud_id=cloud_id).first()
                if ssh_key_obj:
                    instance.ssh_keys.append(ssh_key_obj)

            instance_profile = db_session.query(IBMInstanceProfile).filter_by(
                name=instance_json["profile"]["name"],
                cloud_id=cloud_id).first()
            resource_group = db_session.query(IBMResourceGroup).filter_by(
                resource_id=instance_json["resource_group"]["id"], cloud_id=cloud_id).first()
            image = db_session.query(IBMImage).filter_by(resource_id=instance_json["image"]["id"],
                                                         cloud_id=cloud_id).first()

            if not (ibm_cloud and instance_profile and resource_group and vpc_network and zone):
                workflow_task.status = WorkflowTask.STATUS_FAILED
                workflow_task.message = \
                    "Creation Successful but record update failed. The records will update next time discovery runs"
                db_session.commit()
                LOGGER.note(workflow_task.message)
                return

            for volume_attachment_json in instance_json.get("volume_attachments", []):
                volume_profile = db_session.query(IBMVolumeProfile).filter_by(
                    name=volume_attachment_json["volume"]["profile"]["name"],
                    cloud_id=cloud_id).first()
                volume_attachment = IBMVolumeAttachment.from_ibm_json_body(json_body=volume_attachment_json)
                volume = IBMVolume.from_ibm_json_body(json_body=volume_attachment_json["volume"])
                volume.zone = zone
                volume.resource_group = resource_group
                volume.volume_profile = volume_profile
                volume_attachment.volume = volume
                volume_attachment.zone = zone
                instance.volume_attachments.append(volume_attachment)

            for instance_disk_json in instance_json["disks"]:
                instance_disk = IBMInstanceDisk.from_ibm_json_body(json_body=instance_disk_json)
                instance.instance_disks.append(instance_disk)

            for network_interface_json in instance_json["network_interfaces"]:
                subnet = db_session.query(IBMSubnet).filter_by(
                    resource_id=network_interface_json["subnet"]["id"]).first()
                if not subnet:
                    workflow_task.status = WorkflowTask.STATUS_FAILED
                    workflow_task.message = \
                        "Creation Successful but record update failed. The records will update next time discovery runs"
                    db_session.commit()
                    LOGGER.note(workflow_task.message)
                    return

                network_interface = IBMNetworkInterface.from_ibm_json_body(json_body=network_interface_json)
                network_interface.subnet = subnet
                network_interface.ibm_cloud = ibm_cloud
                for sg in network_interface_json["security_groups"]:
                    sg_obj = db_session.query(IBMSecurityGroup).filter_by(resource_id=sg["id"],
                                                                          cloud_id=cloud_id).first()
                    if sg_obj:
                        network_interface.security_groups.append(sg_obj)
                instance.network_interfaces.append(network_interface)
            if instance_json.get("placement_target"):
                placement_resource_type = instance_json["placement_target"]["resource_type"]
                placement_resource_id = instance_json["placement_target"]["id"]
                placement_target = \
                    db_session.query(PlacementTargetSchema.REF_KEY_TO_RESOURCE_TYPE_MAPPER[placement_resource_type]
                                     ).filter_by(resource_id=placement_resource_id).first()
                if not placement_target:
                    workflow_task.status = WorkflowTask.STATUS_FAILED
                    workflow_task.message = \
                        "Creation Successful but record update failed. The records will update next time discovery runs"
                    db_session.commit()
                    LOGGER.note(workflow_task.message)
                    return

                instance.placement_target = placement_target

            # TODO
            # Instance Templates but once this is done
            # There will be list of SSH Keys associated with an instance on call `Retrieve initialization
            # configuration for an instance`
            # ssh_keys = db_session.query(IBMSshKey)

            instance.instance_profile = instance_profile
            instance.vpc_network = vpc_network
            instance.zone = zone
            if image:
                instance.image = image
            instance.resource_group = resource_group
            db_session.add(instance)
            db_session.commit()
        workflow_task.status = WorkflowTask.STATUS_SUCCESSFUL
        workflow_task.resource_id = instance.id
        db_session.commit()

        instance_json = instance.to_json()
        instance_json["created_at"] = str(instance_json["created_at"])

        IBMResourceLog(
            resource_id=instance.resource_id, region=instance.zone.region,
            status=IBMResourceLog.STATUS_ADDED, resource_type=IBMInstance.__name__,
            data=instance_json
        )

        # TODO handle the same for other interfaces and check if next task is floating ip or not
        # data["resource_json"]["primary_network_interface"].get("floating_ip")
        if workflow_task.next_tasks and len(workflow_task.next_tasks.all()) >= 1:
            target = instance.network_interfaces.filter_by(is_primary=True).first()
            resource_data["resource_json"] = {
                "name": resource_data["resource_json"]["name"] + str(randint(0, 999))[:50],
                "resource_group": resource_group_dict, "target": {"id": target.id}
            }
            workflow_task.next_tasks[0].task_metadata = {"resource_data": resource_data}
            db_session.commit()
    LOGGER.success(f"IBM Instance '{instance_json['name']}' creation for cloud '{cloud_id}' successful")


@celery.task(name="delete_instance", base=IBMWorkflowTasksBase)
def delete_instance(workflow_task_id):
    """
    Delete an IBM Instance
    :param workflow_task_id:
    :return:
    """

    with get_db_session() as db_session:
        workflow_task: WorkflowTask = db_session.get(WorkflowTask, workflow_task_id)
        if not workflow_task:
            return

        workflow_task.status = WorkflowTask.STATUS_RUNNING
        db_session.commit()

        instance: IBMInstance = db_session.get(IBMInstance, workflow_task.resource_id)
        if not instance:
            workflow_task.status = WorkflowTask.STATUS_FAILED
            workflow_task.message = f"IBMInstance '{workflow_task.resource_id}' not found"
            db_session.commit()
            LOGGER.error(workflow_task.message)
            return

        region_name = instance.region.name
        instance_resource_id = instance.resource_id
        cloud_id = instance.cloud_id

    try:
        client = InstancesClient(cloud_id, region=region_name)
        client.delete_instance(instance_id=instance_resource_id)
        instance_json = client.get_instance(instance_id=instance_resource_id)

    except ApiException as ex:
        with get_db_session() as db_session:
            workflow_task: WorkflowTask = db_session.get(WorkflowTask, workflow_task_id)
            if not workflow_task:
                return

            if ex.code == 404:
                instance = db_session.get(IBMInstance, workflow_task.resource_id)
                if instance:
                    for volume_attachment in instance.volume_attachments.filter_by(
                            delete_volume_on_instance_delete=True).all():
                        db_session.delete(volume_attachment.volume)
                    db_session.delete(instance)

                instance_json = instance.to_json()
                instance_json["created_at"] = str(instance_json["created_at"])

                IBMResourceLog(
                    resource_id=instance.resource_id, region=instance.zone.region,
                    status=IBMResourceLog.STATUS_DELETED, resource_type=IBMInstance.__name__,
                    data=instance_json)

                workflow_task.status = WorkflowTask.STATUS_SUCCESSFUL
                LOGGER.success(f"IBM Instance {workflow_task.resource_id} deletion successful.")
                db_session.commit()
                return
            else:
                workflow_task.status = WorkflowTask.STATUS_FAILED
                workflow_task.message = \
                    f"IBM Instance {workflow_task.resource_id} deletion failed. Reason: {str(ex.message)}"
                db_session.commit()
                LOGGER.fail(workflow_task.message)
                return

    with get_db_session() as db_session:
        workflow_task: WorkflowTask = db_session.get(WorkflowTask, workflow_task_id)
        if not workflow_task:
            return

        instance_status = instance_json["status"]
        if instance_status in [IBMInstance.STATUS_DELETING, IBMInstance.STATUS_STOPPING, IBMInstance.STATUS_PENDING]:
            workflow_task.status = WorkflowTask.STATUS_RUNNING_WAIT
            message = f"IBM Instance {workflow_task.resource_id} deletion waiting."
            LOGGER.info(message)
        else:
            workflow_task.message = f"IBM Instance {workflow_task.resource_id} deletion failed."
            LOGGER.fail(workflow_task.message)
            workflow_task.status = WorkflowTask.STATUS_FAILED

        db_session.commit()


@celery.task(name="delete_wait_instance", base=IBMWorkflowTasksBase)
def delete_wait_instance(workflow_task_id):
    """
    Wait for an IBM Instance deletion on IBM Cloud.
    :param workflow_task_id:
    :return:
    """
    with get_db_session() as db_session:
        workflow_task: WorkflowTask = db_session.get(WorkflowTask, workflow_task_id)
        if not workflow_task:
            return

        workflow_task.status = WorkflowTask.STATUS_RUNNING
        db_session.commit()

        instance: IBMInstance = db_session.get(IBMInstance, workflow_task.resource_id)
        if not instance:
            workflow_task.status = WorkflowTask.STATUS_SUCCESSFUL
            db_session.commit()
            LOGGER.success(f"IBM Instance {workflow_task.resource_id} deletion successful.")
            return

        region_name = instance.region.name
        instance_resource_id = instance.resource_id
        cloud_id = instance.cloud_id

    try:
        client = InstancesClient(cloud_id, region=region_name)
        resp_json = client.get_instance(instance_id=instance_resource_id)

    except ApiException as ex:
        with get_db_session() as db_session:
            workflow_task: WorkflowTask = db_session.get(WorkflowTask, workflow_task_id)
            if not workflow_task:
                return

            if ex.code == 404:
                instance = db_session.get(IBMInstance, workflow_task.resource_id)
                if instance:
                    for volume_attachment in instance.volume_attachments.filter_by(
                            delete_volume_on_instance_delete=True).all():
                        db_session.delete(volume_attachment.volume)

                    # Adding resource to IBMResourceTracking
                    create_resource_tracking_object(db_resource=instance,
                                                    action_type=IBMResourceTracking.DELETED,
                                                    session=db_session)
                    db_session.delete(instance)

                workflow_task.status = WorkflowTask.STATUS_SUCCESSFUL
                LOGGER.success(f"IBM Instance {workflow_task.resource_id} deletion successful.")

                instance_json = instance.to_json()
                instance_json["created_at"] = str(instance_json["created_at"])

                IBMResourceLog(
                    resource_id=instance.resource_id, region=instance.zone.region,
                    status=IBMResourceLog.STATUS_DELETED, resource_type=IBMInstance.__name__,
                    data=instance_json)

                db_session.commit()
                return
            else:
                workflow_task.status = WorkflowTask.STATUS_FAILED
                workflow_task.message = \
                    f"IBM Instance {workflow_task.resource_id} deletion failed. Reason: {str(ex.message)}"
                db_session.commit()
                LOGGER.fail(workflow_task.message)
                return

    with get_db_session() as db_session:
        workflow_task: WorkflowTask = db_session.get(WorkflowTask, workflow_task_id)
        if not workflow_task:
            return

        instance_status = resp_json["status"]
        if instance_status in [IBMInstance.STATUS_DELETING, IBMInstance.STATUS_STOPPING, IBMInstance.STATUS_PENDING]:
            workflow_task.status = WorkflowTask.STATUS_RUNNING_WAIT
            LOGGER.info(f"IBM Instance {workflow_task.resource_id} deletion waiting.")
        else:
            workflow_task.message = f"IBM Instance {workflow_task.resource_id} deletion failed."
            LOGGER.fail(workflow_task.message)
            workflow_task.status = WorkflowTask.STATUS_FAILED

        db_session.commit()


@celery.task(name="create_ibm_instance_export_to_cos", base=IBMWorkflowTasksBase)
def create_ibm_instance_export_to_cos(workflow_task_id):
    with get_db_session() as db_session:
        workflow_task = db_session.query(WorkflowTask).filter_by(id=workflow_task_id).first()
        if not workflow_task:
            return

        workflow_task.status = WorkflowTask.STATUS_RUNNING
        db_session.commit()

        task_metadata = deepcopy(workflow_task.task_metadata)
        resource_data = deepcopy(task_metadata["resource_data"])
        cloud_id = resource_data["ibm_cloud"]["id"]
        region_id = resource_data["region"]["id"]
        migration_json = deepcopy(resource_data["migration_json"])
        classic_account_id = migration_json["classic_account_id"]
        classic_image_id = migration_json["classic_image_id"]

        ibm_cloud = db_session.query(IBMCloud).filter_by(id=cloud_id, deleted=False).first()
        if not ibm_cloud:
            workflow_task.message = f"IBM Cloud {cloud_id} not found"
            workflow_task.status = WorkflowTask.STATUS_FAILED
            db_session.commit()
            LOGGER.error(workflow_task.message)
            return

        if ibm_cloud.status != IBMCloud.STATUS_VALID:
            workflow_task.message = f"IBM Cloud {ibm_cloud.name} is not {IBMCloud.STATUS_VALID} status"
            workflow_task.status = WorkflowTask.STATUS_FAILED
            db_session.commit()
            LOGGER.error(workflow_task.message)
            return

        api_key = ibm_cloud.api_key
        region = ibm_cloud.regions.filter_by(id=region_id).first()
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

        classic_account = db_session.query(SoftlayerCloud).filter_by(
            id=classic_account_id, status=SoftlayerCloud.STATUS_VALID).first()
        if not classic_account:
            workflow_task.status = WorkflowTask.STATUS_FAILED
            workflow_task.message = f"SoftlayerCloud '{migration_json['classic_account_id']}' not found OR not VALID" \
                                    f"for IBM Cloud: {cloud_id}"
            db_session.commit()
            LOGGER.error(workflow_task.message)
            return
    try:
        image_client = SoftlayerImageClient(cloud_id=classic_account_id)
        fetched_image = image_client.get_image_by_id(image_id=classic_image_id)
        classic_image_name = fetched_image["name"]
    except (SLExecuteError, SLAuthError, SLRateLimitExceededError, SLInvalidRequestError, KeyError) as ex:
        with get_db_session() as db_session:
            workflow_task = db_session.query(WorkflowTask).filter_by(id=workflow_task_id).first()
            if not workflow_task:
                return

            workflow_task.message = f"Export to COS Failed. Reason: {str(ex)}"
            workflow_task.status = WorkflowTask.STATUS_FAILED
            db_session.commit()
            LOGGER.fail(workflow_task.message)
            return

    with get_db_session() as db_session:
        workflow_task = db_session.query(WorkflowTask).filter_by(id=workflow_task_id).first()
        if not workflow_task:
            return

        if not fetched_image:
            workflow_task.status = WorkflowTask.STATUS_FAILED
            workflow_task.message = f"SoftlayerCloudImage '{classic_image_id}' not found in Classic Account: " \
                                    f"{classic_account_id} for IBM Cloud: {cloud_id}"
            LOGGER.fail(workflow_task.message)
            db_session.commit()
            return

        elif fetched_image.get("activeTransaction"):
            workflow_task.status = WorkflowTask.STATUS_FAILED
            workflow_task.message = f"SoftlayerCloudImage '{classic_image_id}' has an activeTransaction in Classic " \
                                    f"Account: {classic_account_id} for IBM Cloud: {cloud_id}"
            LOGGER.fail(workflow_task.message)
            db_session.commit()
            return

        bucket_dict = migration_json.get("file", {}).get("bucket") or {
            IBMCOSBucket.NAME_KEY: migration_json.get('cos_bucket_name')}
        bucket = db_session.query(IBMCOSBucket).filter_by(**bucket_dict).first()
        if not bucket:
            workflow_task.status = WorkflowTask.STATUS_FAILED
            workflow_task.message = f"IBMCOSBucket {bucket_dict} not found for IBM Cloud: {cloud_id}"
            LOGGER.fail(workflow_task.message)
            db_session.commit()
            return
        bucket_name = bucket.name
    try:
        image_client = SoftlayerImageClient(cloud_id=classic_account_id)
        cos_bucket_object = get_cos_object_name(
            region_name=region_name, cloud_id=cloud_id, bucket_name=bucket_name, object_name=classic_image_name
        )
        cos_url = f"cos://{region_name}/{bucket_name}/{cos_bucket_object}.vhd"
        export_image_response = image_client.export_image(
            image_id=classic_image_id, cos_url=cos_url, api_key=api_key
        )
    except (SLExecuteError, SLAuthError, SLRateLimitExceededError, SLInvalidRequestError, ClientError) as ex:
        with get_db_session() as db_session:
            workflow_task = db_session.query(WorkflowTask).filter_by(id=workflow_task_id).first()
            if not workflow_task:
                return

            workflow_task.message = \
                f"""Exporting Classic Image with ID '{classic_image_id}' to COS Failed. Reason: {str(ex)}
                COS_URL: {cos_url}
                """
            workflow_task.status = WorkflowTask.STATUS_FAILED
            db_session.commit()
            LOGGER.fail(workflow_task.message)
            return

    with get_db_session() as db_session:
        workflow_task = db_session.query(WorkflowTask).filter_by(id=workflow_task_id).first()
        if not workflow_task:
            return

        if migration_json.get("file"):
            migration_json["file"]["cos_bucket_object"] = cos_bucket_object
            migration_json["file"]["href"] = cos_url.replace(".vhd", "-0.vhd")
        else:
            migration_json["cos_bucket_object"] = cos_bucket_object
            migration_json["href"] = cos_url.replace(".vhd", "-0.vhd")
        resource_data["migration_json"] = migration_json
        task_metadata["resource_data"] = resource_data
        workflow_task.task_metadata = task_metadata

        if not export_image_response:
            workflow_task.status = WorkflowTask.STATUS_FAILED
            workflow_task.message = f"SoftlayerCloudImage '{classic_image_id}' Failed to export to COS bucket for " \
                                    f"IBM Cloud: {cloud_id}"
            LOGGER.fail(workflow_task.message)
        else:
            workflow_task.status = WorkflowTask.STATUS_RUNNING_WAIT
            LOGGER.note(f"SoftlayerCloudImage {classic_image_id}, Export Waiting for IBM Cloud {cloud_id}.")
        db_session.commit()


@celery.task(name="create_wait_ibm_instance_export_to_cos", base=IBMWorkflowTasksBase)
def create_wait_ibm_instance_export_to_cos(workflow_task_id):
    with get_db_session() as db_session:
        workflow_task = db_session.query(WorkflowTask).filter_by(id=workflow_task_id).first()
        if not workflow_task:
            return

        workflow_task.status = WorkflowTask.STATUS_RUNNING
        db_session.commit()
        resource_data = deepcopy(workflow_task.task_metadata["resource_data"])
        migration_json = deepcopy(resource_data["migration_json"])
        cloud_id = resource_data["ibm_cloud"]["id"]
        region_id = resource_data["region"]["id"]
        classic_account_id = migration_json["classic_account_id"]
        classic_image_id = migration_json["classic_image_id"]

        ibm_cloud = db_session.query(IBMCloud).filter_by(id=cloud_id, deleted=False).first()
        if not ibm_cloud:
            workflow_task.status = WorkflowTask.STATUS_FAILED
            workflow_task.message = f"IBM Cloud {cloud_id} not found"
            LOGGER.error(workflow_task.message)
            return

        if ibm_cloud.status != IBMCloud.STATUS_VALID:
            workflow_task.status = WorkflowTask.STATUS_FAILED
            workflow_task.message = f"IBM Cloud {ibm_cloud.name} is not in {IBMCloud.STATUS_VALID} status"
            LOGGER.error(workflow_task.message)
            return

        region = ibm_cloud.regions.filter_by(id=region_id).first()
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

        classic_account = db_session.query(SoftlayerCloud).filter_by(
            id=classic_account_id, status=SoftlayerCloud.STATUS_VALID).first()
        if not classic_account:
            workflow_task.status = WorkflowTask.STATUS_FAILED
            workflow_task.message = f"SoftlayerCloud '{migration_json['classic_account_id']}' not found OR not VALID " \
                                    f"for IBM Cloud: {cloud_id}"
            db_session.commit()
            LOGGER.fail(workflow_task.message)
            return

        bucket_dict = migration_json.get("file", {}).get("bucket") or {
            IBMCOSBucket.NAME_KEY: migration_json.get('cos_bucket_name')}
        bucket = db_session.query(IBMCOSBucket).filter_by(**bucket_dict).first()
        if not bucket:
            workflow_task.status = WorkflowTask.STATUS_FAILED
            workflow_task.message = f"IBMCOSBucket {bucket_dict} not found for IBM Cloud: {cloud_id}"
            LOGGER.fail(workflow_task.message)
            db_session.commit()
            return

        bucket_name = bucket.name
    try:
        image_client = SoftlayerImageClient(cloud_id=classic_account_id)
        classic_image = image_client.get_image_by_id(classic_image_id)
        exported_image_list = list()
        expected_image_list = list()
        if classic_image and not classic_image.get("activeTransaction"):
            cos_client = COSClient(cloud_id=cloud_id)
            exported_image_list = [i["Key"] for i in
                                   cos_client.list_cos_bucket_objects(region=region_name, bucket=bucket_name)]
            if migration_json.get("file"):
                cos_bucket_object = migration_json["file"]["cos_bucket_object"]
                migration_json["cos_bucket_object"] = cos_bucket_object
                resource_data["migration_json"] = migration_json
            else:
                cos_bucket_object = migration_json["cos_bucket_object"]
            expected_image_list = [cos_bucket_object + "-0.vhd"]
            if migration_json.get("is_volume_migration"):
                for volume in resource_data["resource_json"].get("volume_attachments", []):
                    if volume["volume"].get("volume_index"):
                        expected_image_list.append(
                            str(cos_bucket_object) + "-" + str(volume["volume"]["volume_index"]) + ".vhd")
            elif migration_json.get("volume_count"):
                expected_image_list = \
                    [f"{str(cos_bucket_object)}-{ind_}.vhd" for ind_ in range(migration_json["volume_count"])]
    except (SLExecuteError, SLAuthError, SLRateLimitExceededError, SLInvalidRequestError) as ex:
        with get_db_session() as db_session:
            workflow_task = db_session.query(WorkflowTask).filter_by(id=workflow_task_id).first()
            if not workflow_task:
                return
            workflow_task.message = f"SoftlayerCloudImage {classic_image_id} Exporting for IBM Cloud" \
                                    f" {cloud_id} FAILED, Reason: {str(ex)}"
            workflow_task.status = WorkflowTask.STATUS_FAILED
            workflow_task.task_metadata["resource_data"] = deepcopy(resource_data)
            db_session.commit()
            LOGGER.fail(workflow_task.message)
            return

    with get_db_session() as db_session:
        workflow_task = db_session.query(WorkflowTask).filter_by(id=workflow_task_id).first()
        if not workflow_task:
            return
        if not classic_image:
            workflow_task.status = WorkflowTask.STATUS_FAILED
            workflow_task.message = f"SoftlayerCloudImage {classic_image_id} not found " \
                                    f"for cloud {cloud_id}"
            LOGGER.fail(workflow_task.message)
            db_session.commit()
            return
        elif classic_image.get("activeTransaction") or not all(x in exported_image_list for x in expected_image_list):
            workflow_task.status = WorkflowTask.STATUS_RUNNING_WAIT
            LOGGER.info(f"Images exporting to COS: {expected_image_list}")
            workflow_task.message = f"SoftlayerCloudImage {classic_image_id} Export Waiting for IBM Cloud {cloud_id}"
            LOGGER.note(workflow_task.message)
            db_session.commit()
            return
        else:
            workflow_task.status = WorkflowTask.STATUS_SUCCESSFUL
            workflow_task.message = f"SoftlayerCloudImage {classic_image_id}, Export Successful for IBM Cloud " \
                                    f"{cloud_id}"
            LOGGER.success(workflow_task.message)
            for next_task in workflow_task.next_tasks:
                next_task.task_metadata = deepcopy(workflow_task.task_metadata)

            workflow_task.result = {"ALL_COS_BUCKET_OBJECT": expected_image_list}
            db_session.commit()
    if migration_json["migrate_from"] in [
        InstanceMigrationConsts.CLASSIC_VSI, InstanceMigrationConsts.ONLY_VOLUME_MIGRATION
    ]:
        image_client = SoftlayerImageClient(cloud_id=classic_account_id)
        try:
            image_client.delete_image(classic_image_id)
        except (SLRateLimitExceededError, SLAuthError, SLExecuteError) as ex:
            LOGGER.fail(f"Failed to Delete Classic Image with ID: {classic_image_id}. Reason: {str(ex)}")


@celery.task(name="create_ibm_instance_snapshot", base=IBMWorkflowTasksBase)
def create_ibm_instance_snapshot(workflow_task_id):
    with get_db_session() as db_session:
        workflow_task = db_session.query(WorkflowTask).filter_by(id=workflow_task_id).first()
        if not workflow_task:
            return

        workflow_task.status = WorkflowTask.STATUS_RUNNING
        db_session.commit()

        task_metadata = deepcopy(workflow_task.task_metadata)
        resource_data = deepcopy(task_metadata["resource_data"])
        migration_json = deepcopy(resource_data["migration_json"])
        cloud_id = resource_data["ibm_cloud"]["id"]
        classic_instance_id = migration_json["classic_instance_id"]
        classic_account_id = migration_json["classic_account_id"]

        classic_account = db_session.query(SoftlayerCloud).filter_by(
            id=classic_account_id, status=SoftlayerCloud.STATUS_VALID
        ).first()
        if not classic_account:
            workflow_task.status = WorkflowTask.STATUS_FAILED
            workflow_task.message = f"SoftlayerCloud '{classic_account_id}' not found OR not VALID"
            db_session.commit()
            LOGGER.error(workflow_task.message)
            return
    try:
        image_client = SoftlayerImageClient(cloud_id=classic_account_id)
        instance_client = SoftlayerInstanceClient(cloud_id=classic_account_id)
        fetched_instance = instance_client.get_instance_by_id(instance_id=classic_instance_id)
        captured_image = None
        if fetched_instance and not fetched_instance.get("activeTransaction"):
            classic_image_name = image_client.get_classic_image_name(image_name=fetched_instance.get("hostname"))
            captured_image = instance_client.capture_image(
                instance_id=classic_instance_id, image_name=classic_image_name,
                additional_disks=migration_json.get("is_volume_migration") or bool(
                    migration_json.get("volume_count") >= 1)
            )
            migration_json["classic_image_id"] = \
                image_client.get_image_by_name(classic_image_name, captured_image.get("createDate"))["id"]
            migration_json["classic_image_name"] = classic_image_name
    except (
            SLExecuteError, SLAuthError, SLRateLimitExceededError, SLInvalidRequestError, SoftLayerAPIError, KeyError,
            AttributeError
    ) as ex:
        with get_db_session() as db_session:
            workflow_task = db_session.query(WorkflowTask).filter_by(id=workflow_task_id).first()
            if not workflow_task:
                return
            workflow_task.message = f"Failed to create image snapshot for instance: {classic_instance_id} for IBM " \
                                    f"Cloud:{cloud_id}, Reason: {str(ex)}"
            workflow_task.status = WorkflowTask.STATUS_FAILED
            db_session.commit()
            LOGGER.fail(workflow_task.message)
        return
    with get_db_session() as db_session:
        workflow_task = db_session.query(WorkflowTask).filter_by(id=workflow_task_id).first()
        if not workflow_task:
            return

        if not fetched_instance:
            workflow_task.status = WorkflowTask.STATUS_FAILED
            workflow_task.message = f"SoftlayerCloudInstance id: {classic_instance_id} not found on " \
                                    f"SoftlayerCloud: {classic_account_id} for IBM Cloud: {cloud_id}"
            db_session.commit()
            LOGGER.fail(workflow_task.message)
            return

        if fetched_instance.get("activeTransaction"):
            workflow_task.status = WorkflowTask.STATUS_FAILED
            workflow_task.message = f"SoftlayerCloudInstance: {classic_instance_id}, has already an active " \
                                    f"transaction for IBM Cloud: {cloud_id}"
            db_session.commit()
            LOGGER.fail(workflow_task.message)
            return

        if not captured_image:
            workflow_task.status = WorkflowTask.STATUS_FAILED
            workflow_task.message = f"Failed to create image snapshot for instance: {classic_instance_id} for " \
                                    f"IBM Cloud: {cloud_id}, Reason: {captured_image}"
            LOGGER.fail(workflow_task.message)
            db_session.commit()
            return

        resource_data["migration_json"] = migration_json
        task_metadata["resource_data"] = resource_data
        workflow_task.task_metadata = task_metadata
        workflow_task.status = WorkflowTask.STATUS_RUNNING_WAIT
        workflow_task.message = f"SoftlayerCloudInstance {classic_instance_id}, Snapshot Creation Waiting " \
                                f"for cloud {cloud_id}"
        LOGGER.info(workflow_task.message)
        db_session.commit()


@celery.task(name="create_wait_ibm_instance_snapshot", base=IBMWorkflowTasksBase)
def create_wait_ibm_instance_snapshot(workflow_task_id):
    with get_db_session() as db_session:
        workflow_task = db_session.query(WorkflowTask).filter_by(id=workflow_task_id).first()
        if not workflow_task:
            return

        workflow_task.status = WorkflowTask.STATUS_RUNNING
        db_session.commit()

        task_metadata = deepcopy(workflow_task.task_metadata)
        resource_data = deepcopy(task_metadata["resource_data"])
        migration_json = deepcopy(resource_data["migration_json"])
        cloud_id = resource_data["ibm_cloud"]["id"]
        classic_account_id = migration_json["classic_account_id"]
        classic_instance_id = migration_json["classic_instance_id"]
        classic_image_id = migration_json["classic_image_id"]

        softlayer_cloud = db_session.query(SoftlayerCloud).filter_by(
            id=classic_account_id, status=SoftlayerCloud.STATUS_VALID
        ).first()
        if not softlayer_cloud:
            workflow_task.status = WorkflowTask.STATUS_FAILED
            workflow_task.message = f"SoftlayerCloud '{classic_account_id}' not found OR not VALID for " \
                                    f"User having IBM CLoud: {cloud_id}"
            db_session.commit()
            LOGGER.error(workflow_task.message)
            return
    try:
        instance_client = SoftlayerInstanceClient(cloud_id=classic_account_id)
        image_client = SoftlayerImageClient(cloud_id=classic_account_id)
        classic_instance = instance_client.get_instance_by_id(instance_id=classic_instance_id)
        image_client.get_image_by_id(image_id=classic_image_id)
    except (SLExecuteError, SLAuthError, SLRateLimitExceededError, SLInvalidRequestError, SoftLayerAPIError) as ex:
        workflow_task.status = WorkflowTask.STATUS_FAILED
        workflow_task.message = f"Failed to fetch image: {classic_image_id} and instance: {classic_instance_id} on" \
                                f" SoftlayerCloud '{classic_account_id}' for IBM CLoud: {cloud_id} Reason: {str(ex)}"
        db_session.commit()
        LOGGER.fail(workflow_task.message)
        return

    with get_db_session() as db_session:
        workflow_task = db_session.query(WorkflowTask).filter_by(id=workflow_task_id).first()
        if not workflow_task:
            return
        if not classic_instance:
            workflow_task.status = WorkflowTask.STATUS_FAILED
            workflow_task.message = f"SoftlayerCloudInstance: {classic_instance_id}, not found on SoftlayerAccount:" \
                                    f" {classic_account_id} for User having IBM Cloud: {cloud_id}"
            LOGGER.fail(workflow_task.message)
            db_session.commit()
            return

        if classic_instance.get("activeTransaction"):
            workflow_task.status = WorkflowTask.STATUS_RUNNING_WAIT
            workflow_task.message = f"SoftlayerCloudInstance: {classic_instance_id}, Snapshot Creation Waiting " \
                                    f"for IBM Cloud: {cloud_id}"
            LOGGER.info(workflow_task.message)
            db_session.commit()
            return

        workflow_task.status = WorkflowTask.STATUS_SUCCESSFUL
        workflow_task.message = f"SoftlayerCloudInstance {classic_instance_id}, Snapshot Creation Successful for " \
                                f"IBM Cloud: {cloud_id}"
        LOGGER.success(workflow_task.message)

        for next_task in workflow_task.next_tasks:
            next_task.task_metadata = deepcopy(task_metadata)
        db_session.commit()
    if migration_json.get("BACKUP_INSTANCE_REPORTING_META"):
        backup_instance_id = migration_json["backup_instance_id"]
        instance_client = SoftlayerInstanceClient(cloud_id=classic_account_id)
        try:
            instance_client.delete_instance(instance_id=backup_instance_id)
            LOGGER.info(f"Backup Instance Deleted with ID: {backup_instance_id}")
        except (SLRateLimitExceededError, SLExecuteError) as ex:
            # TODO add a retry mechanism
            LOGGER.info(f"Backup Instance Failed to Delete with ID: {backup_instance_id}. Reason: {str(ex)}")


@celery.task(name="create_softlayer_backup_instance", base=IBMWorkflowTasksBase)
def create_softlayer_backup_instance(workflow_task_id):
    with get_db_session() as db_session:
        workflow_task = db_session.query(WorkflowTask).filter_by(id=workflow_task_id).first()
        if not workflow_task:
            return

        workflow_task.status = WorkflowTask.STATUS_RUNNING
        db_session.commit()

        task_metadata = deepcopy(workflow_task.task_metadata)
        resource_data = deepcopy(task_metadata["resource_data"])
        migration_json = deepcopy(resource_data["migration_json"])
        classic_account_id = migration_json["classic_account_id"]
        classic_instance_id = migration_json["classic_instance_id"]
        classic_image_id = migration_json["classic_image_id"]

        classic_account = db_session.query(SoftlayerCloud).filter_by(
            id=classic_account_id, status=SoftlayerCloud.STATUS_VALID
        ).first()
        if not classic_account:
            workflow_task.status = WorkflowTask.STATUS_FAILED
            workflow_task.message = f"SoftlayerCloud '{classic_account_id}' not found OR not VALID"
            db_session.commit()
            LOGGER.error(workflow_task.message)
            return
    try:
        image_client = SoftlayerImageClient(cloud_id=classic_account_id)
        instance_client = SoftlayerInstanceClient(cloud_id=classic_account_id)
        original_vsi_json = instance_client.get_instance_by_id(classic_instance_id)
        backup_image_json = image_client.get_image_by_id(classic_image_id)
        if not (original_vsi_json and backup_image_json):
            with get_db_session() as db_session:
                workflow_task = db_session.query(WorkflowTask).filter_by(id=workflow_task_id).first()
                if not workflow_task:
                    return

                workflow_task.status = WorkflowTask.STATUS_FAILED
                workflow_task.message = f"Classical Instance {migration_json['classical_instance_id']} or " \
                                        f"Classical Backup Image {migration_json['classic_image_id']} not found on " \
                                        f"IBM Softlayer"
                LOGGER.fail(workflow_task.message)
                db_session.commit()

        create_vsi_json = SoftLayerInstance.from_softlayer_json_body(
            instance_json=original_vsi_json, image_guid=backup_image_json["globalIdentifier"]
        )
        created_vsi_json = instance_client.create_instance(create_vsi_json)
        with get_db_session() as db_session:
            workflow_task = db_session.query(WorkflowTask).filter_by(id=workflow_task_id).first()
            if not workflow_task:
                return

            migration_json["BACKUP_INSTANCE_REPORTING_META"] = {"WAIT_COUNT": 1, "IPv4": "", "CREATED": False}
            migration_json["backup_instance_id"] = created_vsi_json["id"]
            resource_data["migration_json"] = migration_json
            task_metadata["resource_data"] = resource_data
            workflow_task.task_metadata = task_metadata
            workflow_task.status = WorkflowTask.STATUS_RUNNING_WAIT
            db_session.commit()
            LOGGER.info(f"Softlayer Windows Backup Instance create Waiting with ID: {created_vsi_json['id']}")
            return

    except (
            SLExecuteError, SLAuthError, SLRateLimitExceededError, SLInvalidRequestError, SoftLayerAPIError, KeyError
    ) as ex:
        with get_db_session() as db_session:
            workflow_task = db_session.query(WorkflowTask).filter_by(id=workflow_task_id).first()
            if not workflow_task:
                return

            workflow_task.message = f"Softlayer Backup Instance Creation Failed. Reason: {str(ex)}"
            workflow_task.status = WorkflowTask.STATUS_FAILED
            db_session.commit()
            LOGGER.fail(workflow_task.message)
            return


@celery.task(name="create_wait_softlayer_backup_instance", base=IBMWorkflowTasksBase)
def create_wait_softlayer_backup_instance(workflow_task_id):
    with get_db_session() as db_session:
        workflow_task = db_session.query(WorkflowTask).filter_by(id=workflow_task_id).first()
        if not workflow_task:
            return

        workflow_task.status = WorkflowTask.STATUS_RUNNING
        db_session.commit()

        task_metadata = deepcopy(workflow_task.task_metadata)
        resource_data = deepcopy(task_metadata["resource_data"])
        resource_json = deepcopy(resource_data["resource_json"])
        migration_json = deepcopy(resource_data["migration_json"])
        backup_instance_status_meta = deepcopy(migration_json["BACKUP_INSTANCE_REPORTING_META"])
        classic_account_id = migration_json["classic_account_id"]
        classic_image_id = migration_json["classic_image_id"]
        original_instance_id = migration_json["classic_instance_id"]
        backup_instance_id = migration_json["backup_instance_id"]
        cloud_id = resource_data["ibm_cloud"]["id"]
        classic_account = db_session.query(SoftlayerCloud).filter_by(
            id=classic_account_id, status=SoftlayerCloud.STATUS_VALID
        ).first()
        if not classic_account:
            workflow_task.status = WorkflowTask.STATUS_FAILED
            workflow_task.message = f"SoftlayerCloud not found for ID: {classic_account_id} OR not Valid for " \
                                    f"IBM Cloud: {cloud_id}"
            db_session.commit()
            LOGGER.error(workflow_task.message)
            return

    try:
        instance_client = SoftlayerInstanceClient(cloud_id=classic_account_id)
        backup_vsi_json = instance_client.get_instance_by_id(instance_id=backup_instance_id)
        if not backup_vsi_json:
            with get_db_session() as db_session:
                workflow_task = db_session.query(WorkflowTask).filter_by(id=workflow_task_id).first()
                if not workflow_task:
                    return

                workflow_task.status = WorkflowTask.STATUS_FAILED
                workflow_task.message = f"Classical Instance {backup_instance_id} Created as a BACKUP not found on " \
                                        f"IBM Softlayer"
                LOGGER.fail(workflow_task.message)
                db_session.commit()
                return

        if not backup_instance_status_meta["CREATED"]:
            backup_instance_status_meta["CREATED"] = instance_client.wait_instance_for_ready(
                instance_id=backup_instance_id, limit=2)
            with get_db_session() as db_session:
                workflow_task = db_session.query(WorkflowTask).filter_by(id=workflow_task_id).first()
                if not workflow_task:
                    return

                migration_json["BACKUP_INSTANCE_REPORTING_META"] = backup_instance_status_meta
                resource_data["migration_json"] = migration_json
                task_metadata["resource_data"] = resource_data
                workflow_task.task_metadata = task_metadata

                workflow_task.status = WorkflowTask.STATUS_RUNNING_WAIT
                db_session.commit()
                LOGGER.info(f"Backup VSI {backup_instance_id} is not ready yet for cloud {cloud_id}")
                return

    except (SLExecuteError, SLAuthError, SLRateLimitExceededError, SLInvalidRequestError, SoftLayerAPIError) as ex:
        with get_db_session() as db_session:
            workflow_task = db_session.query(WorkflowTask).filter_by(id=workflow_task_id).first()
            if not workflow_task:
                return

            workflow_task.status = WorkflowTask.STATUS_FAILED
            workflow_task.message = f"Classical Instance {backup_instance_id} Created as a BACKUP has issue on " \
                                    f"IBM Softlayer: {classic_account_id} Reason: {str(ex)}"
            LOGGER.fail(workflow_task.message)
            db_session.commit()
            return

    if not backup_instance_status_meta['IPv4']:
        backup_instance_status_meta['IPv4'] = backup_vsi_json.get("primaryIpAddress")
    pingable = ping(backup_instance_status_meta['IPv4']) if backup_instance_status_meta['IPv4'] else True
    with get_db_session() as db_session:
        workflow_task = db_session.query(WorkflowTask).filter_by(id=workflow_task_id).first()
        if not workflow_task:
            return

        if pingable:
            migration_json["BACKUP_INSTANCE_REPORTING_META"] = backup_instance_status_meta
            resource_data["migration_json"] = migration_json
            task_metadata["resource_data"] = resource_data
            workflow_task.task_metadata = deepcopy(task_metadata)
            workflow_task.status = WorkflowTask.STATUS_RUNNING_WAIT
            db_session.commit()
            LOGGER.info(f"Backup VSI {backup_instance_id} SYSPREP is still waiting to run for cloud {cloud_id}")
            return

        elif int(backup_instance_status_meta["WAIT_COUNT"]) <= 100:
            LOGGER.info(f"IBM Instance {resource_json['name']} is getting ready for sysprep to be migrated with"
                        f" wait count {backup_instance_status_meta['WAIT_COUNT']} for ibm cloud: {cloud_id}")
            backup_instance_status_meta["WAIT_COUNT"] = int(backup_instance_status_meta["WAIT_COUNT"]) + 1
            migration_json["BACKUP_INSTANCE_REPORTING_META"] = backup_instance_status_meta
            resource_data["migration_json"] = migration_json
            task_metadata["resource_data"] = resource_data
            workflow_task.task_metadata = deepcopy(task_metadata)
            workflow_task.status = WorkflowTask.STATUS_RUNNING_WAIT
            db_session.commit()
            return

        migration_json["classic_instance_id"] = backup_instance_id
        migration_json["original_instance_id"] = original_instance_id
        migration_json["BACKUP_INSTANCE_REPORTING_META"] = backup_instance_status_meta
        resource_data["migration_json"] = migration_json
        task_metadata["resource_data"] = resource_data
        workflow_task.task_metadata = task_metadata
        workflow_task.status = WorkflowTask.STATUS_SUCCESSFUL
        for next_task in workflow_task.next_tasks:
            next_task.task_metadata = deepcopy(task_metadata)
        db_session.commit()
        LOGGER.success(f"Softlayer Windows Backup Instance created with ID: {backup_instance_id} for IBM Cloud: "
                       f"{cloud_id}")
        if migration_json["migrate_from"] == InstanceMigrationConsts.CLASSIC_VSI:
            image_client = SoftlayerImageClient(cloud_id=classic_account_id)
            try:
                image_client.delete_image(classic_image_id)
            except SLExecuteError:
                pass


@celery.task(name="start_nas_migration", base=IBMWorkflowTasksBase)
def task_start_nas_migration(data, user_id):
    db_migration_api_key = WorkerConfig.DB_MIGRATION_API_KEY
    db_migration_controller_host = WorkerConfig.DB_MIGRATION_CONTROLLER_HOST
    get_all_locations_url = f"{db_migration_controller_host}v1/dbmigration/locations?user_id=" \
                            f"{user_id}&limit=1000&start=1"

    headers = {'s-api-key': db_migration_api_key}
    response = requests.get(get_all_locations_url, headers=headers)
    if response.status_code != 200:
        LOGGER.info(
            f"NAS Migration Failed for user: {user_id} on getting locations with response {response.status_code}")
        return
    locations = data["locations"]
    src_migrator = data["src_migrator"]
    trg_migrator = data["trg_migrator"]
    src_migrator_id, trg_migrator_id = None, None
    for item in response.json()["items"]:
        if item["name"] == src_migrator:
            src_migrator_id = item["id"]
        elif item["name"] == trg_migrator:
            trg_migrator_id = item["id"]

        if src_migrator_id and trg_migrator_id:
            break
    if not (src_migrator_id and trg_migrator_id):
        LOGGER.fail(
            f"NAS Migration Failed for user: {user_id} as src_migrator_id: {src_migrator_id} for Name: {src_migrator} "
            f"and trg_migrator_id: {trg_migrator_id} for Name: {src_migrator}"
        )
        return
    payload = {
        "name": "NAS-Migration",
        "databases": locations,
        "user_id": user_id,
        "src_location_id": src_migrator_id,
        "trg_location_id": trg_migrator_id
    }

    migration_post_url = db_migration_controller_host + "/v1/dbmigration/migrations"

    post_response = requests.post(url=migration_post_url, headers=headers, json=payload)
    if post_response.status_code not in [200, 201]:
        LOGGER.info(f"Content Migration Object Creation Payload: {payload}")
        LOGGER.info(f"NAS Migration Failed for user: {user_id} on creating migration object with status code "
                    f"{post_response.status_code}")
        return

    patch_response = requests.patch(
        url=f"{db_migration_controller_host}v1/dbmigration/dbmigration/{post_response.json()['id']}", headers=headers)

    if post_response.status_code == 202:
        LOGGER.info(f"NAS Migration for user: {user_id} started with ID: {post_response.json()['id']}")
    else:
        LOGGER.info(f"NAS Migration for user: {user_id} started with status code: {patch_response.status_code}")


@celery.task(name="stop_ibm_instance", base=IBMWorkflowTasksBase)
def stop_ibm_instance_task(workflow_task_id):
    """
    Stop an IBM Instance on IBM Cloud
    """
    with get_db_session() as db_session:
        workflow_task: WorkflowTask = db_session.get(WorkflowTask, workflow_task_id)
        if not workflow_task:
            return

        workflow_task.status = WorkflowTask.STATUS_RUNNING
        db_session.commit()

        instance: IBMInstance = db_session.get(IBMInstance, workflow_task.resource_id)
        if not instance:
            workflow_task.status = WorkflowTask.STATUS_FAILED
            workflow_task.message = f"IBMInstance with ID '{workflow_task.resource_id}' not found in DB"
            db_session.commit()
            LOGGER.error(workflow_task.message)
            return

        region_name = instance.region.name
        instance_resource_id = instance.resource_id
        cloud_id = instance.cloud_id

    try:
        client = InstancesClient(cloud_id, region=region_name)
        client.create_instance_action(
            instance_id=instance_resource_id, instance_action_json={"type": "stop", "force": False})
        client.create_instance_action(
            instance_id=instance_resource_id, instance_action_json={"type": "stop", "force": True})
        instance_json = client.get_instance(instance_id=instance_resource_id)

    except ApiException as ex:
        with get_db_session() as db_session:
            workflow_task: WorkflowTask = db_session.get(WorkflowTask, workflow_task_id)
            if not workflow_task:
                return

            workflow_task.status = WorkflowTask.STATUS_FAILED
            workflow_task.message = f"IBM Instance {workflow_task.resource_id} stop failed. Reason: {str(ex.message)}"
            db_session.commit()
            LOGGER.fail(workflow_task.message)
            return

    with get_db_session() as db_session:
        workflow_task = db_session.query(WorkflowTask).filter_by(id=workflow_task_id).first()
        if not workflow_task:
            return

        instance: IBMInstance = db_session.get(IBMInstance, workflow_task.resource_id)
        if not instance:
            workflow_task.status = WorkflowTask.STATUS_FAILED
            workflow_task.message = f"IBMInstance with ID '{workflow_task.resource_id}' not found in DB"
            db_session.commit()
            LOGGER.error(workflow_task.message)
            return

        if instance_json["status"] in [IBMInstance.STATUS_PENDING, IBMInstance.STATUS_RESTARTING,
                                       IBMInstance.STATUS_STOPPING]:
            workflow_task.status = WorkflowTask.STATUS_RUNNING_WAIT
            db_session.commit()
            LOGGER.info(f"IBM Instance '{instance_json['name']}' stop action for cloud '{cloud_id}' waiting")
            return

        if instance_json["status"] == IBMInstance.STATUS_STOPPED:
            IBMResourceLog(
                resource_id=instance.resource_id, region=instance.zone.region,
                status=IBMResourceLog.STATUS_UPDATED, resource_type=IBMInstance.__name__,
                data=instance_json)

            instance.status = IBMInstance.STATUS_STOPPED
            workflow_task.status = WorkflowTask.STATUS_SUCCESSFUL
            db_session.commit()
            LOGGER.success(f"IBM Instance with ID: '{instance_resource_id}' stopped successfully")
            return


@celery.task(name="stop_wait_ibm_instance", base=IBMWorkflowTasksBase)
def stop_wait_ibm_instance_task(workflow_task_id):
    """
    Wait for an IBM Instance start on IBM Cloud
    """
    with get_db_session() as db_session:
        workflow_task = db_session.query(WorkflowTask).filter_by(id=workflow_task_id).first()
        if not workflow_task:
            return

        workflow_task.status = WorkflowTask.STATUS_RUNNING
        db_session.commit()

        instance: IBMInstance = db_session.get(IBMInstance, workflow_task.resource_id)
        if not instance:
            workflow_task.status = WorkflowTask.STATUS_FAILED
            workflow_task.message = f"IBMInstance with ID '{workflow_task.resource_id}' not found in DB"
            db_session.commit()
            LOGGER.error(workflow_task.message)
            return

        region_name = instance.region.name
        instance_resource_id = instance.resource_id
        cloud_id = instance.cloud_id

    try:
        client = InstancesClient(cloud_id=cloud_id, region=region_name)
        instance_json = client.get_instance(instance_id=instance_resource_id)

    except ApiException as ex:
        with get_db_session() as db_session:
            workflow_task = db_session.query(WorkflowTask).filter_by(id=workflow_task_id).first()
            if not workflow_task:
                return

            workflow_task.status = WorkflowTask.STATUS_FAILED
            workflow_task.message = f"Start Task Failed. Reason: {str(ex.message)}"
            db_session.commit()
            LOGGER.fail(workflow_task.message)
            return

    with get_db_session() as db_session:
        workflow_task = db_session.query(WorkflowTask).filter_by(id=workflow_task_id).first()
        if not workflow_task:
            return

        instance: IBMInstance = db_session.get(IBMInstance, workflow_task.resource_id)
        if not instance:
            workflow_task.status = WorkflowTask.STATUS_FAILED
            workflow_task.message = f"IBMInstance with ID '{workflow_task.resource_id}' not found in DB"
            db_session.commit()
            LOGGER.fail(workflow_task.message)
            return

        if instance_json["status"] in [IBMInstance.STATUS_PENDING, IBMInstance.STATUS_RESTARTING,
                                       IBMInstance.STATUS_STOPPING]:
            workflow_task.status = WorkflowTask.STATUS_RUNNING_WAIT
            db_session.commit()
            LOGGER.info(f"IBM Instance '{instance_json['name']}' stop action for cloud '{cloud_id}' waiting")
            return

        if instance_json["status"] == IBMInstance.STATUS_STOPPED:
            IBMResourceLog(
                resource_id=instance.resource_id, region=instance.zone.region,
                status=IBMResourceLog.STATUS_UPDATED, resource_type=IBMInstance.__name__,
                data=instance_json)

            instance.status = IBMInstance.STATUS_STOPPED
            workflow_task.status = WorkflowTask.STATUS_SUCCESSFUL
            db_session.commit()
            LOGGER.success(f"IBM Instance with ID: '{instance_resource_id}' stopped successfully")
            return


@celery.task(name="start_ibm_instance", base=IBMWorkflowTasksBase)
def start_ibm_instance_task(workflow_task_id):
    """
    Stop an IBM Instance on IBM Cloud
    """
    with get_db_session() as db_session:
        workflow_task: WorkflowTask = db_session.get(WorkflowTask, workflow_task_id)
        if not workflow_task:
            return

        workflow_task.status = WorkflowTask.STATUS_RUNNING
        db_session.commit()

        instance: IBMInstance = db_session.get(IBMInstance, workflow_task.resource_id)
        if not instance:
            workflow_task.status = WorkflowTask.STATUS_FAILED
            workflow_task.message = f"IBMInstance with ID '{workflow_task.resource_id}' not found in DB"
            db_session.commit()
            LOGGER.error(workflow_task.message)
            return

        region_name = instance.region.name
        instance_resource_id = instance.resource_id
        cloud_id = instance.cloud_id

    try:
        client = InstancesClient(cloud_id, region=region_name)
        client.create_instance_action(
            instance_id=instance_resource_id, instance_action_json={"type": "start", "force": True})
        instance_json = client.get_instance(instance_id=instance_resource_id)

    except ApiException as ex:
        with get_db_session() as db_session:
            workflow_task: WorkflowTask = db_session.get(WorkflowTask, workflow_task_id)
            if not workflow_task:
                return

            workflow_task.status = WorkflowTask.STATUS_FAILED
            workflow_task.message = \
                f"IBM Instance {workflow_task.resource_id} start action failed. Reason: {str(ex.message)}"
            db_session.commit()
            LOGGER.fail(workflow_task.message)
            return

    with get_db_session() as db_session:
        workflow_task: WorkflowTask = db_session.get(WorkflowTask, workflow_task_id)
        if not workflow_task:
            return

        instance_status = instance_json["status"]
        if instance_status in [IBMInstance.STATUS_PENDING, IBMInstance.STATUS_RESTARTING, IBMInstance.STATUS_STARTING]:
            workflow_task.status = WorkflowTask.STATUS_RUNNING_WAIT
            db_session.commit()
            LOGGER.info(f"IBM Instance '{instance_json['name']}' start for cloud '{cloud_id}' waiting")
            return

        if instance_status == IBMInstance.STATUS_RUNNING:
            instance: IBMInstance = db_session.get(IBMInstance, workflow_task.resource_id)
            if not instance:
                workflow_task.status = WorkflowTask.STATUS_FAILED
                workflow_task.message = f"IBMInstance with ID '{workflow_task.resource_id}' not found in DB"
                db_session.commit()
                LOGGER.info(workflow_task.message)
                return

            IBMResourceLog(
                resource_id=instance.resource_id, region=instance.zone.region,
                status=IBMResourceLog.STATUS_UPDATED, resource_type=IBMInstance.__name__,
                data=instance_json)
            instance.status = IBMInstance.STATUS_RUNNING

            workflow_task.status = WorkflowTask.STATUS_SUCCESSFUL
            db_session.commit()
            LOGGER.success(f"IBM Instance with ID: '{instance_resource_id}' started successfully")
            return


@celery.task(name="start_wait_ibm_instance", base=IBMWorkflowTasksBase)
def start_wait_ibm_instance_task(workflow_task_id):
    """
    Wait for an IBM Instance start on IBM Cloud
    """
    with get_db_session() as db_session:
        workflow_task = db_session.query(WorkflowTask).filter_by(id=workflow_task_id).first()
        if not workflow_task:
            return

        workflow_task.status = WorkflowTask.STATUS_RUNNING
        db_session.commit()

        instance: IBMInstance = db_session.get(IBMInstance, workflow_task.resource_id)
        if not instance:
            workflow_task.status = WorkflowTask.STATUS_FAILED
            workflow_task.message = f"IBMInstance with ID '{workflow_task.resource_id}' not found in DB"
            db_session.commit()
            LOGGER.error(workflow_task.message)
            return

        region_name = instance.region.name
        instance_resource_id = instance.resource_id
        cloud_id = instance.cloud_id

    try:
        client = InstancesClient(cloud_id=cloud_id, region=region_name)
        instance_json = client.get_instance(instance_id=instance_resource_id)

    except ApiException as ex:
        with get_db_session() as db_session:
            workflow_task = db_session.query(WorkflowTask).filter_by(id=workflow_task_id).first()
            if not workflow_task:
                return

            workflow_task.status = WorkflowTask.STATUS_FAILED
            workflow_task.message = f"Start Task Failed. Reason: {str(ex.message)}"
            db_session.commit()
            LOGGER.fail(workflow_task.message)
            return

    with get_db_session() as db_session:
        workflow_task = db_session.query(WorkflowTask).filter_by(id=workflow_task_id).first()
        if not workflow_task:
            return

        instance: IBMInstance = db_session.get(IBMInstance, workflow_task.resource_id)
        if not instance:
            workflow_task.status = WorkflowTask.STATUS_FAILED
            workflow_task.message = f"IBMInstance with ID '{workflow_task.resource_id}' not found in DB"
            db_session.commit()
            LOGGER.error(workflow_task.message)
            return

        if instance_json["status"] in [IBMInstance.STATUS_PENDING, IBMInstance.STATUS_RESTARTING,
                                       IBMInstance.STATUS_STARTING]:
            workflow_task.status = WorkflowTask.STATUS_RUNNING_WAIT
            db_session.commit()
            LOGGER.info(f"IBM Instance '{instance_json['name']}' start for cloud '{cloud_id}' waiting")
            return

        if instance_json["status"] == IBMInstance.STATUS_RUNNING:
            IBMResourceLog(
                resource_id=instance.resource_id, region=instance.zone.region,
                status=IBMResourceLog.STATUS_UPDATED, resource_type=IBMInstance.__name__,
                data=instance_json)
            instance.status = IBMInstance.STATUS_RUNNING
            workflow_task.status = WorkflowTask.STATUS_SUCCESSFUL
            db_session.commit()
            LOGGER.success(f"IBM Instance with ID: '{instance_resource_id}' started successfully")
            return


@celery.task(name="update_instance", base=IBMWorkflowTasksBase)
def update_instance(workflow_task_id):
    """
    Update an IBM Instance on IBM Cloud
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
        instance_id = resource_json["instance_id"]
        instance_profile_name = resource_json["profile"]["name"]

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

        instance = db_session.query(IBMInstance).filter_by(
            id=instance_id, cloud_id=cloud_id, region_id=region_id).first()
        if not instance:
            workflow_task.status = WorkflowTask.STATUS_FAILED
            workflow_task.message = f"IBMInstance '{instance_id}' not found"
            db_session.commit()
            LOGGER.error(workflow_task.message)
            return

        instance_profile = db_session.query(IBMInstanceProfile).filter_by(
            name=instance_profile_name, cloud_id=cloud_id, region_id=region_id).first()
        if not instance_profile:
            workflow_task.status = WorkflowTask.STATUS_FAILED
            workflow_task.message = f"IBMInstanceProfile '{instance_profile_name}' not found"
            db_session.commit()
            LOGGER.error(workflow_task.message)
            return

        previous_resources = load_previous_associated_resources(task=workflow_task, session=db_session)
        update_id_or_name_references(
            cloud_id=cloud_id, resource_json=resource_data, resource_schema=IBMRightSizeInSchema,
            db_session=db_session, previous_resources=previous_resources
        )

        update_id_or_name_references(
            cloud_id=cloud_id, resource_json=resource_json, resource_schema=IBMRightSizeResourceSchema,
            db_session=db_session, previous_resources=previous_resources
        )

        region_name = region.name
        instance_resource_id = instance.resource_id
        resource_json.pop('id', None)

    try:
        client = InstancesClient(cloud_id=cloud_id, region=region_name)
        resp_json = client.update_instance(instance_id=instance_resource_id, instance_json=resource_json)

    except ApiException as ex:
        with get_db_session() as db_session:
            workflow_task = db_session.query(WorkflowTask).filter_by(id=workflow_task_id).first()
            if not workflow_task:
                return

            workflow_task.status = WorkflowTask.STATUS_FAILED
            workflow_task.message = f"Failed to Update instance. Reason: {str(ex.message)}"
            ibm_cloud = db_session.query(IBMCloud).filter_by(id=workflow_task.resource_id).first()
            if ibm_cloud:
                ibm_cloud.status = IBMCloud.STATUS_INVALID
            db_session.commit()

            LOGGER.info(workflow_task.message)
            return

    with get_db_session() as db_session:
        workflow_task = db_session.query(WorkflowTask).filter_by(id=workflow_task_id).first()
        if not workflow_task:
            return

        ibm_cloud = db_session.query(IBMCloud).filter_by(id=cloud_id).first()
        if not ibm_cloud:
            workflow_task.status = WorkflowTask.STATUS_FAILED
            workflow_task.message = f"IBMCloud '{cloud_id}' not found"
            db_session.commit()
            LOGGER.error(workflow_task.message)
            return

        with db_session.no_autoflush:
            instance = db_session.query(IBMInstance).filter_by(
                id=instance_id).first()
            if not instance:
                workflow_task.status = WorkflowTask.STATUS_FAILED
                workflow_task.message = f"IBMInstance '{instance_id}' not found"
                db_session.commit()
                LOGGER.error(workflow_task.message)
                return

            configured_instance = IBMInstance.from_ibm_json_body(resp_json)
            instance.update_from_object(configured_instance)
            instance.instance_profile = instance_profile

            # Adding resource to AWSResourceTracking
            create_resource_tracking_object(db_resource=instance, action_type=IBMResourceTracking.RIGHT_SIZED,
                                            session=db_session)

            IBMResourceLog(
                resource_id=instance.resource_id, region=instance.zone.region,
                status=IBMResourceLog.STATUS_UPDATED, resource_type=IBMInstance.__name__,
                data=resp_json)

            workflow_task.status = WorkflowTask.STATUS_SUCCESSFUL
            db_session.commit()
            db_session.query(IBMRightSizingRecommendation).filter_by(
                cloud_id=ibm_cloud.id, resource_id=instance.resource_id,
                recommended_instance_type=instance_profile_name
            ).delete()
            db_session.commit()
        LOGGER.success(f"IBMInstance successfully updated with ID {instance_resource_id}")


@celery.task(name="get_vsi_usage_task", base=IBMWorkflowTasksBase)
def get_vsi_usage_data(workflow_task_id):
    """
    Get usage for ibm vsi's using monitoring apis.
    """
    with get_db_session() as db_session:
        workflow_task = db_session.query(WorkflowTask).filter_by(id=workflow_task_id).first()
        if not workflow_task:
            return

        workflow_task.status = WorkflowTask.STATUS_RUNNING
        db_session.commit()

        region = db_session.query(IBMRegion).filter_by(id=workflow_task.resource_id).first()
        if not region:
            workflow_task.status = WorkflowTask.STATUS_FAILED
            workflow_task.message = f"IBMRegion '{workflow_task.resource_id}' not found"
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
        region_id = region.id
        monitoring_token = db_session.query(IBMMonitoringToken).filter_by(
            region_id=region_id, status=IBMMonitoringToken.STATUS_VALID).first()
        if not monitoring_token:
            workflow_task.status = WorkflowTask.STATUS_FAILED
            workflow_task.message = f"Monitoring not enable for region {region_name}"
            db_session.commit()
            LOGGER.error(workflow_task.message)
            return

        token = monitoring_token.token

    url = MONITORING_INSTANCE_URL.format(region_name=region_name)
    monitoring_client = SdMonitorClient(sdc_url=url, token=token)
    results = []
    got_data = True
    start_time = get_relative_time_seconds(month_count=3)
    page_from = 0
    page_to = 49
    paging_range = page_from + page_to
    while got_data:
        ok, res = monitoring_client.get_data(metrics=METRICS, start_ts=start_time, paging={"from": page_from,
                                                                                           "to": page_to,
                                                                                           "latest": True})
        if not ok:
            with get_db_session() as db_session:
                workflow_task = db_session.query(WorkflowTask).filter_by(id=workflow_task_id).first()
                if not workflow_task:
                    return

                if res == "'ibm_resource_name' is not a Sysdig metric: Metric not found":
                    workflow_task.status = WorkflowTask.STATUS_SUCCESSFUL
                    db_session.commit()
                    return

                if res == "status code 401":
                    monitoring_token = db_session.query(IBMMonitoringToken).filter_by(region_id=region_id,
                                                                                      token=token).first()
                    if not monitoring_token:
                        workflow_task.status = WorkflowTask.STATUS_FAILED
                        workflow_task.message = f"IBMMonitoringToken region_id: '{region_id}', token:{token} not found"
                        db_session.commit()
                        LOGGER.fail(workflow_task.message)
                        return

                    monitoring_token.status = IBMMonitoringToken.STATUS_INVALID

                workflow_task.status = WorkflowTask.STATUS_FAILED
                workflow_task.message = str(res)
                db_session.commit()
                LOGGER.info(workflow_task.message)
                return

        if not res.get('data'):
            got_data = False
            continue
        if len(res.get('data')) < paging_range:
            got_data = False

        results.append(res)
        page_from = page_to + 1,
        page_to = paging_range

    with get_db_session() as db_session:
        workflow_task = db_session.query(WorkflowTask).filter_by(id=workflow_task_id).first()
        if not workflow_task:
            return

        region = db_session.query(IBMRegion).filter_by(id=region_id).first()
        if not region:
            workflow_task.status = WorkflowTask.STATUS_FAILED
            workflow_task.message = f"IBMRegion '{workflow_task.resource_id}' not found"
            db_session.commit()
            LOGGER.error(workflow_task.message)
            return

        cloud = region.ibm_cloud
        instances_name_obj_dict = dict()
        instances_id_obj_dict = dict()
        existing_instances = db_session.query(IBMInstance).filter_by(region_id=region_id).all()
        for instance in existing_instances:
            instances_name_obj_dict[instance.name] = instance
            instances_id_obj_dict[instance.id] = instance

        for res in results:
            for d in res.get("data", []):
                instance = instances_name_obj_dict.get(d['d'][0])
                if not instance:
                    LOGGER.error(f"Instance with name {d['d'][0]} not found in region {region_name}")
                    continue

                usage = {
                    "cpu_usage_percentage": {"avg": f"{d['d'][1]}"},
                    "memory_usage_percentage": {"avg": f"{d['d'][2]}"}
                }  # TODO: this can be done dynamically. will do it later.
                instance.usage = usage

                if instance.instance_profile.name == LOWEST_INSTANCE_PROFILE:
                    continue

                if db_session.query(IBMIdleResource).filter_by(cloud_id=cloud.id, db_resource_id=instance.id).first():
                    continue

                low_memory_usage, low_cpu_usage = False, False
                if float(usage['cpu_usage_percentage']['avg']) <= 20:
                    low_cpu_usage = True
                if float(usage['memory_usage_percentage']['avg']) <= 45:
                    low_memory_usage = True

                existing = db_session.query(IBMRightSizingRecommendation).filter_by(
                    cloud_id=cloud.id, instance_id=instance.id).first()
                if low_memory_usage or low_cpu_usage:
                    recommended_instance_profile = get_cost_saving_instance_profile(
                        instance.instance_profile, low_memory_usage, low_cpu_usage)
                    if not recommended_instance_profile:
                        if existing:
                            db_session.delete(existing)
                        continue
                    if recommended_instance_profile == instance.instance_profile.name:
                        if existing:
                            db_session.delete(existing)
                        continue

                    current_instance_resource_details = {'memory': instance.instance_profile.memory['value'],
                                                         'vcpu': instance.instance_profile.vcpu_count['value']}
                    recommended_instance_profile_split = recommended_instance_profile.split('-')[1].split('x')
                    vcpu, memory = recommended_instance_profile_split[0], recommended_instance_profile_split[1]
                    recommended_instance_resource_details = {'memory': memory, 'vcpu': vcpu}
                    rightsizing_recommendation = IBMRightSizingRecommendation(
                        region=region_name, current_instance_type=instance.instance_profile.name,
                        current_instance_resource_details=current_instance_resource_details,
                        recommended_instance_resource_details=recommended_instance_resource_details,
                        monthly_cost=0.0, resource_id=instance.resource_id,
                        estimated_monthly_cost=0.0, estimated_monthly_savings=0.0,
                        recommended_instance_type=recommended_instance_profile)

                    if existing:
                        existing.update_db(rightsizing_recommendation)
                    else:
                        rightsizing_recommendation.ibm_instance = instance
                        rightsizing_recommendation.ibm_cloud = cloud
                elif existing:
                    db_session.delete(existing)

                db_session.commit()

        stale_recommendations = db_session.query(IBMRightSizingRecommendation).filter_by(cloud_id=cloud.id,
                                                                                         region=region_name).filter(
            IBMRightSizingRecommendation.instance_id.notin_(instances_id_obj_dict)).all()
        for stale_recommendation in stale_recommendations:
            db_session.delete(stale_recommendation)

        workflow_task.status = WorkflowTask.STATUS_SUCCESSFUL
        db_session.commit()

    LOGGER.success(f"Usage in region {region_name} has been gathered successfully")


@celery.task(name="get_idle_instances", base=IBMWorkflowTasksBase)
def get_idle_instances(workflow_task_id):
    """
    Get usage for ibm vsi's using monitoring apis.
    """
    with get_db_session() as db_session:
        workflow_task = db_session.query(WorkflowTask).filter_by(id=workflow_task_id).first()
        if not workflow_task:
            return

        workflow_task.status = WorkflowTask.STATUS_RUNNING
        db_session.commit()
        region = db_session.query(IBMRegion).filter_by(id=workflow_task.resource_id).first()
        if not region:
            workflow_task.status = WorkflowTask.STATUS_FAILED
            workflow_task.message = f"IBMRegion '{workflow_task.resource_id}' not found"
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
        region_id = region.id
        monitoring_token = db_session.query(IBMMonitoringToken).filter_by(
            region_id=region_id, status=IBMMonitoringToken.STATUS_VALID).first()
        if not monitoring_token:
            workflow_task.status = WorkflowTask.STATUS_FAILED
            workflow_task.message = f"Monitoring not enable for region {region_name}"
            db_session.commit()
            LOGGER.fail(workflow_task.message)
            return

        token = monitoring_token.token

    url = MONITORING_INSTANCE_URL.format(region_name=region_name)
    monitoring_client = SdMonitorClient(sdc_url=url, token=token)
    results = []
    got_data = True
    start_time = get_relative_time_seconds(days_count=14)
    page_from = 0
    page_to = 49
    paging_range = page_from + page_to
    while got_data:
        ok, res = monitoring_client.get_data(metrics=METRICS_FOR_IDLE_INSTANCES, start_ts=start_time,
                                             paging={"from": page_from, "to": page_to, "latest": True})
        if not ok:
            with get_db_session() as db_session:
                workflow_task = db_session.query(WorkflowTask).filter_by(id=workflow_task_id).first()
                if not workflow_task:
                    return

                if res == "status code 401":
                    monitoring_token = db_session.query(IBMMonitoringToken).filter_by(region_id=region_id,
                                                                                      token=token).first()
                    if not monitoring_token:
                        workflow_task.status = WorkflowTask.STATUS_FAILED
                        workflow_task.message = f"IBMMonitoringToken region_id: '{region_id}', token:{token} not found"
                        db_session.commit()
                        LOGGER.info(workflow_task.message)
                        return

                    monitoring_token.status = IBMMonitoringToken.STATUS_INVALID

                workflow_task.status = WorkflowTask.STATUS_FAILED
                workflow_task.message = str(res)
                db_session.commit()
                LOGGER.info(workflow_task.message)
                return

        if not res.get('data'):
            got_data = False
            continue
        if len(res.get('data')) < paging_range:
            got_data = False

        results.append(res)
        page_from = page_to + 1,
        page_to = paging_range

    with get_db_session() as db_session:
        workflow_task = db_session.query(WorkflowTask).filter_by(id=workflow_task_id).first()
        if not workflow_task:
            return

        region = db_session.query(IBMRegion).filter_by(id=region_id).first()
        if not region:
            workflow_task.status = WorkflowTask.STATUS_FAILED
            workflow_task.message = f"IBMRegion '{workflow_task.resource_id}' not found"
            db_session.commit()
            LOGGER.info(workflow_task.message)
            return

        cloud = region.ibm_cloud
        instances_name_obj_dict = dict()
        instances_id_obj_dict = dict()
        idle_resources_rids = dict()
        db_idle_resources = db_session.query(IBMIdleResource).filter_by(cloud_id=cloud.id, region_id=region.id,
                                                                        source_type=IBMIdleResource.SOURCE_DISCOVERY,
                                                                        resource_type=IBMInstance.__tablename__).all()
        for db_idle_resource in db_idle_resources:
            idle_resources_rids[db_idle_resource.db_resource_id] = db_idle_resource

        existing_instances = db_session.query(IBMInstance).filter_by(region_id=region_id).all()
        for instance in existing_instances:
            instances_name_obj_dict[instance.name] = instance
            instances_id_obj_dict[instance.id] = instance

        for res in results:
            for d in res.get("data", []):
                try:
                    instance = instances_name_obj_dict.get(d['d'][0])
                    if not instance:
                        LOGGER.info(f"Instance with name {d['d'][0]} not found in region {region_name}")
                        continue

                    cpu_utilization = float(d['d'][1])
                    in_network_traffic_bytes = float(d['d'][2])
                    out_network_traffic_bytes = float(d['d'][3])
                except (ValueError, KeyError) as ex:
                    LOGGER.debug(f"Exception raised while parsing : {ex} \n Data: {res}")
                    continue

                if cpu_utilization <= 1 and \
                        ((in_network_traffic_bytes / (1024 * 1024)) + (out_network_traffic_bytes / (1024 * 1024))) <= 5:
                    idle_resource = db_session.query(IBMIdleResource).filter_by(db_resource_id=instance.id).first()
                    if not idle_resource:
                        new_idle_resource = IBMIdleResource(
                            db_resource_id=instance.id,
                            source_type=IBMIdleResource.SOURCE_DISCOVERY,
                            resource_type=instance.__tablename__,
                            resource_json=instance.to_idle_json(session=db_session),
                            reason="CPU Utilization is less than 1% and Network Traffic less than 5MB"
                        )
                        new_idle_resource.ibm_cloud = cloud
                        new_idle_resource.region = region
                    else:
                        idle_resources_rids[idle_resource.db_resource_id].update_db(instance, db_session)
                        del idle_resources_rids[idle_resource.db_resource_id]

        for idle_resource in idle_resources_rids.values():
            db_session.delete(idle_resource)
            db_session.commit()

        workflow_task.status = WorkflowTask.STATUS_SUCCESSFUL
        db_session.commit()
