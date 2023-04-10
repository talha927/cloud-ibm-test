import json
import logging
from copy import deepcopy

from config import WorkerConfig
from ibm import get_db_session
from ibm.common.clients.ibm_clients import VolumesClient
from ibm.common.clients.ibm_clients.consts import VPC_DATE_BASED_VERSION, VPC_GENERATION
from ibm.common.clients.ibm_clients.exceptions import IBMConnectError
from ibm.common.utils import get_volume_attachment_dict
from ibm.models import IBMCloud, IBMCOSBucket, IBMImage, IBMOperatingSystem, IBMRegion
from ibm.web.common.data_migration.consts import CAPACITY, CONTENT_MIGRATOR_AGENT_DEPLOY_SCRIPT, DISK_IDENTIFIER, \
    LARGEST_SECONDARY_VOLUMES_LIMIT, LINUX_SVM_REQUIREMENTS, LINUX_SVM_SCRIPT, MAX_SECONDARY_VOLUMES_LIMIT, NAME, \
    NAS_MIG_CONSTS, NAS_MIG_SCRIPT, SVM_ENV, VOLUME, WINDOWS_SVM_REQUIREMENTS, WINDOWS_SVM_SCRIPT
from ibm.web.common.data_migration.utils import return_class
from ibm.web.ibm.instances.consts import InstanceMigrationConsts

LOGGER = logging.getLogger(__name__)


def append_additional_volume_to_json(volumes, instance_name, cloud_id, region):
    """Append a volume json to instance json"""

    volume_client = VolumesClient(cloud_id=cloud_id, region=region)
    disk_name = instance_name + SVM_ENV
    for volume_index in range(MAX_SECONDARY_VOLUMES_LIMIT):
        try:
            existing_volumes = volume_client.list_volumes(name=disk_name)
        except IBMConnectError:
            raise IBMConnectError
        if existing_volumes:
            disk_name += str(volume_index)
        else:
            break

    new_volume = deepcopy(volumes[0])
    max_capacity = LARGEST_SECONDARY_VOLUMES_LIMIT
    for volume in volumes:
        max_capacity = min(LARGEST_SECONDARY_VOLUMES_LIMIT, volume[VOLUME][CAPACITY])
    max_capacity = max_capacity + DISK_IDENTIFIER if max_capacity < LARGEST_SECONDARY_VOLUMES_LIMIT else \
        max_capacity - DISK_IDENTIFIER
    new_volume[VOLUME][NAME] = disk_name
    new_volume[VOLUME][CAPACITY] = max_capacity
    volumes.append(new_volume)
    return volumes, max_capacity, disk_name


def construct_user_data_script(instance, cloud_id, region_id, migration_json):
    """
    Create user_data script from COS files and volume attachments
    :return:
    """
    if not migration_json:
        migration_json = {}
    bucket_id = migration_json.get("file", {}).get("bucket", {}).get("id")
    is_volume_migration = False
    if not bucket_id:
        for volume_attachment in instance.get("volume_attachments", []):
            if "source_cos_object" in volume_attachment["volume"]:
                bucket_id = volume_attachment["volume"]["source_cos_object"].get("bucket_id")
                is_volume_migration = True
                if bucket_id:
                    break

    if not migration_json.get("is_volume_migration") and \
            migration_json.get("migrate_from") != InstanceMigrationConsts.CLASSIC_VSI and \
            not is_volume_migration and not migration_json.get("nas_volume_migration"):
        return instance
    with get_db_session() as db_session:
        ibm_cloud = db_session.query(IBMCloud).filter_by(id=cloud_id, deleted=False).first()
        ibm_region = db_session.query(IBMRegion).filter_by(id=region_id).first()
        cos_bucket = db_session.query(IBMCOSBucket).filter_by(
            id=bucket_id).first()
        os_dict = migration_json.get("operating_system", {})
        if not os_dict:
            image = db_session.query(IBMImage).filter_by(**instance["image"]).first()
            os_ = image.operating_system
        else:
            os_ = db_session.query(IBMOperatingSystem).filter_by(**os_dict).first()
        if not all([ibm_cloud, ibm_region, ibm_cloud.status == IBMCloud.STATUS_VALID, os_]):
            LOGGER.error(f"IBMCloud: {ibm_cloud}, {ibm_cloud.status} OS: {os_} and Region: {ibm_region}")
            return
        api_key = ibm_cloud.api_key
        region_name = ibm_region.name
        region_id = ibm_region.id
        cos_bucket_name = cos_bucket.name if cos_bucket else None
        os_name = os_.name
        windows_os = os_.family == "Windows Server"

    # NAS migration
    nas_migration_user_data = "#!/bin/bash"
    if migration_json.get("nas_volume_migration"):
        nas_migration_user_data, instance["volume_attachments"] = construct_nas_migration_user_data(
            instance, migration_json
        )

    if not windows_os:
        operating_system = return_class(os_name)
        redhat_fix = "#!/bin/bash"
        if operating_system.reboot:
            redhat_fix = operating_system.PACKAGES_INSTALLATION_FIX
        if all([not migration_json.get("is_volume_migration", False), not is_volume_migration]):
            instance["user_data"] = redhat_fix
            if nas_migration_user_data:
                instance["user_data"] = f"{nas_migration_user_data}\n{redhat_fix}"
            return instance
    if all([not migration_json.get("is_volume_migration", False), not is_volume_migration]):
        return instance
    if len(instance.get("volume_attachments") or []) <= 0:
        LOGGER.error(f"Volume Attachments Counts {len(instance.get('volume_attachments', []))}")
        return
    try:
        index_capacity_mapping_dict = {}
        volume_capacity_vhd_name_mapping_dict = {}
        for i, volume in enumerate(instance.get("volume_attachments", [])):
            if volume[VOLUME].get("volume_index"):
                index_capacity_mapping_dict[volume[VOLUME]["volume_index"]] = volume[VOLUME]["capacity"]
                volume[VOLUME].pop("volume_index", None)
            elif volume[VOLUME].get("source_cos_object"):
                cos_image_name = volume[VOLUME]["source_cos_object"]["object_name"]
                volume_capacity_vhd_name_mapping_dict[f"{volume[VOLUME]['capacity']}{i}"] = cos_image_name
        if index_capacity_mapping_dict:
            index_capacity_mapping_dict = deepcopy(dict(sorted(index_capacity_mapping_dict.items())))
        elif volume_capacity_vhd_name_mapping_dict:
            volume_capacity_vhd_name_mapping_dict = deepcopy(dict(sorted(
                volume_capacity_vhd_name_mapping_dict.items())))

    except KeyError as ex:
        LOGGER.error(ex)
        return

    web_hook_uri = WorkerConfig.VPCPLUS_LINK + f"v1/ibm/clouds/{cloud_id}/regions/{region_id}/instances/" \
                                               f"{instance['name']}/secondary-volume-migration/"
    cos_images = ''
    if volume_capacity_vhd_name_mapping_dict:
        for cos_image in volume_capacity_vhd_name_mapping_dict.values():
            cos_images += " ," + f"'{cos_image}'"
    else:
        vhd_image_name = migration_json.get("file", {}).get("cos_bucket_object")
        if not vhd_image_name:
            LOGGER.error("No VHD_IMAGE_NAME provided")
            return
        for volume_index in index_capacity_mapping_dict.keys():
            cos_images += " ," + f"'{vhd_image_name}-{volume_index}.vhd'"

    if windows_os:
        windows_data = WINDOWS_SVM_REQUIREMENTS.format(
            API_KEY=api_key, REGION=region_name, BUCKET=cos_bucket_name, LIST_OF_COS_IMAGES=cos_images,
            INSTANCE_NAME=instance["name"],
            REGION_ID=region_id, CLOUD_ID=cloud_id, WEB_HOOK_URI=web_hook_uri, VERSION=VPC_DATE_BASED_VERSION,
            GENERATION=VPC_GENERATION
        )
        user_data_script = WINDOWS_SVM_SCRIPT.format(WINDOWS_MIG_REQ=windows_data)
    else:
        list_cos_images = [s.strip() for s in cos_images.split(",") if s.strip()]
        list_cos_images = str(tuple(list_cos_images)).replace(",", " ")
        list_cos_images = list_cos_images.replace("'", "")
        volumes, max_capacity, disk_name = append_additional_volume_to_json(
            instance["volume_attachments"], instance["name"], cloud_id, region_name
        )

        data_mig_req_string = LINUX_SVM_REQUIREMENTS.format(
            SVM_WORKING_DISK=str(max_capacity) + "G",
            INSTANCE_NAME=instance["name"],
            PACKAGES=operating_system.packages,
            LIST_OF_COS_IMAGES=list_cos_images,
            VOLUME_NAME=disk_name,
            REGION=region_name,
            IBM_CLOUD=cloud_id,
            VERSION=VPC_DATE_BASED_VERSION,
            WEB_HOOK_URI=web_hook_uri,
            BUCKET=cos_bucket_name,
            API_KEY=api_key,
        )
        if migration_json.get("migrate_from") == InstanceMigrationConsts.CLASSIC_VSI:
            data_mig_req_string = f"{data_mig_req_string}\n{redhat_fix}"

        user_data_script = "{data_mig_req_string}\n{packages}".format(
            data_mig_req_string=data_mig_req_string,
            packages=operating_system.bash_installation_string
        )
        user_data_script = f"{user_data_script}\n{LINUX_SVM_SCRIPT}"
        instance["volume_attachments"] = volumes
    instance["user_data"] = f"{nas_migration_user_data}\n{user_data_script}"
    return instance


def construct_nas_migration_user_data(instance, migration_json):
    """
    Create a User Data Script for NAS Migration and create Volumes as per NAS Volumes
    """

    volume_attachments = instance.get("volume_attachments", [])
    for ind_, disk in enumerate(migration_json["nas_volume_migration"]["cm_meta_data"].get("disks", [])):
        volume_attachments.append(get_volume_attachment_dict(capacity=disk["size"][:-1],
                                                             zone_dict=instance["zone"],
                                                             name=instance["name"], index_=ind_))
    migration_host = WorkerConfig.DB_MIGRATION_CONTROLLER_HOST
    if migration_host.find("https://") != -1:
        migration_host = migration_host.replace("https://", "")
    elif migration_host.find("https://") != -1:
        migration_host = migration_host.replace("http://", "")
    if migration_host.endswith("/"):
        migration_host = migration_host[:-1]

    nas_migration_script = NAS_MIG_CONSTS.format(
        user_id=migration_json["nas_volume_migration"]["cm_meta_data"]["user_id"],
        migration_host=migration_host,
        vpc_backend_host=WorkerConfig.VPCPLUS_LINK,
        trg_migrator_name=f"trg-{instance['name']}",
        src_migrator_name=migration_json["nas_volume_migration"]["cm_meta_data"]["migrator_name"],
        instance_type=WorkerConfig.DB_MIGRATION_INSTANCE_TYPE,
        disks=json.dumps(migration_json["nas_volume_migration"]["cm_meta_data"]["disks"])
    )
    return f"{nas_migration_script}\n{NAS_MIG_SCRIPT}\n{CONTENT_MIGRATOR_AGENT_DEPLOY_SCRIPT}", volume_attachments
