import logging
from datetime import datetime

from ibm.discovery import get_db_session
from ibm.discovery.common.utils import discovery_locked_resource
from ibm.models import IBMCloud, IBMImage, IBMInstance, IBMInstanceDisk, IBMInstanceProfile, IBMNetworkInterface, \
    IBMRegion, \
    IBMResourceGroup, IBMResourceLog, IBMSecurityGroup, IBMSshKey, IBMSubnet, IBMVolume, IBMVolumeAttachment, \
    IBMVpcNetwork, IBMZone

LOGGER = logging.getLogger(__name__)


def update_instance_volume_attachments(cloud_id, region_name, m_instance_volume_attachments):
    if not m_instance_volume_attachments:
        return

    start_time = datetime.utcnow()

    volume_attachments = list()
    volume_attachments_ids = list()
    volume_attachments_id_volume_id_dict = dict()
    volume_attachments_id_instance_id_dict = dict()
    locked_rid_status = dict()

    for m_instance_volume_attachment_list in m_instance_volume_attachments:
        for m_instance_volume_attachment in m_instance_volume_attachment_list.get("response", []):
            volume_attachment = IBMVolumeAttachment.from_ibm_json_body(json_body=m_instance_volume_attachment)
            volume_attachments_id_volume_id_dict[volume_attachment.resource_id] = \
                m_instance_volume_attachment["volume"]["id"]
            volume_attachments_id_instance_id_dict[volume_attachment.resource_id] = \
                m_instance_volume_attachment["href"].split("/")[5]

            volume_attachments.append(volume_attachment)
            volume_attachments_ids.append(volume_attachment.resource_id)

        with get_db_session() as session:
            db_region = session.query(IBMRegion).filter_by(name=region_name, cloud_id=cloud_id).first()
            if not db_region:
                LOGGER.info(f"IBMRegion {region_name} not found")
                return

            last_synced_at = m_instance_volume_attachment_list["last_synced_at"]
            logged_resource = discovery_locked_resource(
                session=session, resource_type=IBMVolumeAttachment.__name__, cloud_id=cloud_id,
                sync_start=last_synced_at, region=db_region)
            locked_rid_status.update(logged_resource)

    with get_db_session() as session:
        with session.no_autoflush:

            db_region = session.query(IBMRegion).filter_by(name=region_name, cloud_id=cloud_id).first()
            if not db_region:
                LOGGER.info(f"IBMRegion {region_name} not found")
                return
            region_id = db_region.id

            db_instances = \
                session.query(IBMInstance).filter_by(cloud_id=cloud_id, region_id=region_id).all()

            db_volume_attachments = []
            for db_instance in db_instances:
                db_volume_attachments.extend(db_instance.volume_attachments.all())

            for db_volume_attachment in db_volume_attachments:
                if locked_rid_status.get(db_volume_attachment.resource_id) in [IBMResourceLog.STATUS_ADDED,
                                                                               IBMResourceLog.STATUS_UPDATED]:
                    continue
                if db_volume_attachment.resource_id not in volume_attachments_ids:
                    session.delete(db_volume_attachment)

            session.commit()

            db_cloud = session.query(IBMCloud).get(cloud_id)
            assert db_cloud

            db_instances = session.query(IBMInstance).filter_by(cloud_id=cloud_id, region_id=region_id).all()

            db_volume_attachments = []
            db_instances_id_obj_dict = dict()
            for db_instance in db_instances:
                db_volume_attachments.extend(db_instance.volume_attachments.all())
                db_instances_id_obj_dict[db_instance.resource_id] = db_instance

            for volume_attachment in volume_attachments:
                if locked_rid_status.get(volume_attachment.resource_id) in [IBMResourceLog.STATUS_DELETED,
                                                                            IBMResourceLog.STATUS_UPDATED]:
                    continue
                db_volume = session.query(IBMVolume).filter_by(cloud_id=cloud_id, region_id=region_id,
                                                               resource_id=volume_attachments_id_volume_id_dict.get(
                                                                   volume_attachment.resource_id)).first()
                if not db_volume:
                    LOGGER.info(f"No Volume for volume attachment with ID: "
                                f"{volume_attachments_id_volume_id_dict.get(volume_attachment.resource_id)}")
                    continue
                db_instance = session.query(IBMInstance).filter_by(
                    cloud_id=cloud_id, region_id=region_id, resource_id=volume_attachments_id_instance_id_dict.get(
                        volume_attachment.resource_id)).first()

                volume_attachment.dis_add_update_db(
                    session=session,
                    db_volume_attachments=db_volume_attachments,
                    db_cloud=db_cloud,
                    db_instance=db_instance,
                    db_volume=db_volume
                )

            session.commit()

    LOGGER.info("** Instance Volume Attachments synced in:{}".format((datetime.utcnow() - start_time).total_seconds()))


def update_instances(cloud_id, region_name, m_instances):
    if not m_instances:
        return

    start_time = datetime.utcnow()

    instances = list()
    instances_ids = list()
    instances_id_rgid_dict = dict()
    instances_id_instance_profile_name_dict = dict()
    instances_id_vpc_id_dict = dict()
    instances_id_image_id_dict = dict()
    instance_id_zone_name_dict = dict()
    locked_rid_status = dict()

    for m_instance_list in m_instances:
        for m_instance in m_instance_list.get("response", []):
            # if m_instance['status'] != 'running':
            #     continue
            instance = IBMInstance.from_ibm_json_body(json_body=m_instance)
            instances.append(instance)
            instances_ids.append(instance.resource_id)
            instances_id_rgid_dict[instance.resource_id] = m_instance["resource_group"]["id"]
            instances_id_instance_profile_name_dict[instance.resource_id] = m_instance["profile"]["name"]
            instances_id_vpc_id_dict[instance.resource_id] = m_instance["vpc"]["id"]
            instance_id_zone_name_dict[instance.resource_id] = m_instance["zone"]["name"]
            if m_instance.get("image"):
                instances_id_image_id_dict[instance.resource_id] = m_instance["image"]["id"]

        with get_db_session() as session:
            db_region = session.query(IBMRegion).filter_by(name=region_name, cloud_id=cloud_id).first()
            if not db_region:
                LOGGER.info(f"IBMRegion {region_name} not found")
                return

            last_synced_at = m_instance_list["last_synced_at"]
            logged_resource = discovery_locked_resource(
                session=session, resource_type=IBMInstance.__name__, cloud_id=cloud_id,
                sync_start=last_synced_at, region=db_region)
            locked_rid_status.update(logged_resource)

    with get_db_session() as session:
        with session.no_autoflush:

            db_region = session.query(IBMRegion).filter_by(name=region_name, cloud_id=cloud_id).first()
            if not db_region:
                LOGGER.info(f"IBMRegion {region_name} not found")
                return
            region_id = db_region.id

            db_instances = \
                session.query(IBMInstance).filter_by(cloud_id=cloud_id, region_id=region_id).all()

            for db_instance in db_instances:
                if locked_rid_status.get(db_instance.resource_id) in [IBMResourceLog.STATUS_ADDED,
                                                                      IBMResourceLog.STATUS_UPDATED]:
                    continue
                if db_instance.resource_id not in instances_ids:
                    session.delete(db_instance)

            session.commit()

            for instance in instances:
                if locked_rid_status.get(instance.resource_id) in [IBMResourceLog.STATUS_DELETED,
                                                                   IBMResourceLog.STATUS_UPDATED]:
                    continue
                resource_group_id = instances_id_rgid_dict[instance.resource_id]
                instance_profile_name = instances_id_instance_profile_name_dict.get(instance.resource_id)
                vpc_network_id = instances_id_vpc_id_dict.get(instance.resource_id)
                image_id = instances_id_image_id_dict.get(instance.resource_id)

                db_zone = session.query(IBMZone).filter_by(cloud_id=cloud_id, name=instance_id_zone_name_dict[
                    instance.resource_id]).first()

                db_resource_group = \
                    session.query(IBMResourceGroup).filter_by(cloud_id=cloud_id, resource_id=resource_group_id).first()
                if not db_resource_group:
                    LOGGER.info(
                        f"Provided IBMResourceGroup with Resource ID: "
                        f"{resource_group_id}, "
                        f"Cloud ID: {cloud_id} and Region: {region_name} while inserting "
                        f"IBMInstance {instance.resource_id} not found in DB.")
                    continue

                db_instance_profile = \
                    session.query(IBMInstanceProfile).filter_by(
                        name=instance_profile_name, region_id=db_zone.region.id, cloud_id=cloud_id
                    ).first()
                if not db_instance_profile:
                    LOGGER.info(
                        f"Provided IBMInstanceProfile with Name: "
                        f"{instance_profile_name}, "
                        f"Cloud ID: {cloud_id} and Region: {region_name} while inserting "
                        f"IBMInstance {instance.resource_id} not found in DB.")
                    continue

                db_vpc_network = \
                    session.query(IBMVpcNetwork).filter_by(
                        cloud_id=cloud_id, resource_id=vpc_network_id, region_id=db_zone.region.id
                    ).first()
                if not db_vpc_network:
                    LOGGER.info(
                        f"Provided IBMVpcNetwork with Resource ID: "
                        f"{vpc_network_id}, "
                        f"Cloud ID: {cloud_id} and Region: {region_name} while inserting "
                        f"IBMInstance {instance.resource_id} not found in DB.")
                    continue

                db_image = \
                    session.query(IBMImage).filter_by(
                        cloud_id=cloud_id, resource_id=image_id, region_id=db_zone.region.id
                    ).first()

                db_instance = session.query(IBMInstance).filter_by(cloud_id=cloud_id, zone_id=db_zone.id,
                                                                   resource_id=instance.resource_id).first()

                instance.dis_add_update_db(
                    session=session,
                    db_instance=db_instance,
                    cloud_id=cloud_id,
                    db_resource_group=db_resource_group,
                    db_instance_profile=db_instance_profile,
                    db_vpc_network=db_vpc_network,
                    db_image=db_image,
                    db_zone=db_zone
                )

            session.commit()
    LOGGER.info("** Instances synced in:{}".format((datetime.utcnow() - start_time).total_seconds()))


def update_instances_ssh_keys(cloud_id, region_name, m_instances_ssh_keys):
    if not m_instances_ssh_keys:
        return

    start_time = datetime.utcnow()

    with get_db_session() as session:
        with session.no_autoflush:

            db_region = session.query(IBMRegion).filter_by(name=region_name, cloud_id=cloud_id).first()
            if not db_region:
                LOGGER.info(f"IBMRegion {region_name} not found")
                return
            region_id = db_region.id

            db_instances = session.query(IBMInstance).filter_by(cloud_id=cloud_id, region_id=region_id).all()
            db_ssh_keys = session.query(IBMSshKey).filter_by(cloud_id=cloud_id, region_id=region_id).all()

            db_instances_resource_id_obj_dict = dict()
            db_ssh_keys_resource_id_obj_dict = dict()

            for db_instance in db_instances:
                db_instances_resource_id_obj_dict[db_instance.resource_id] = db_instance

            for db_ssh_key in db_ssh_keys:
                db_ssh_keys_resource_id_obj_dict[db_ssh_key.resource_id] = db_ssh_key

            for m_instance_ssh_key_list in m_instances_ssh_keys:
                for response in m_instance_ssh_key_list.get("response", []):
                    if not response:
                        continue
                    instance_id = response.get("instance", {}).get("id")
                    db_instance = db_instances_resource_id_obj_dict.get(instance_id)
                    if not db_instance:
                        LOGGER.debug(f"IBMInstance with resource id {instance_id} not found in db")
                        continue

                    updated_ssh_key_ids = []
                    for m_instance_ssh_key in response.get("keys", []):
                        updated_ssh_key_ids.append(m_instance_ssh_key["id"])

                        db_associated_ssh_key_ids = []
                        for associated_ssh_key in db_instance.ssh_keys.all():
                            if associated_ssh_key.resource_id not in updated_ssh_key_ids:
                                db_instance.ssh_keys.remove(associated_ssh_key)
                            else:
                                db_associated_ssh_key_ids.append(associated_ssh_key.resource_id)

                        session.commit()

                        if m_instance_ssh_key["id"] in db_associated_ssh_key_ids:
                            continue

                        db_ssh_key = db_ssh_keys_resource_id_obj_dict.get(m_instance_ssh_key["id"])
                        if not db_ssh_key:
                            continue
                        db_instance.ssh_keys.append(db_ssh_key)

                        session.commit()

    LOGGER.info("** Instance SSH Keys synced in:{}".format((datetime.utcnow() - start_time).total_seconds()))


def update_instances_network_interfaces(cloud_id, region_name, m_instances_network_interfaces):
    if not m_instances_network_interfaces:
        return

    start_time = datetime.utcnow()
    network_interfaces = list()
    network_interfaces_ids = list()
    network_interfaces_id_security_group_ids_dict = dict()
    network_interfaces_id_subnet_id_dict = dict()
    network_interfaces_id_instance_id_dict = dict()
    locked_rid_status = dict()

    # Extracting required information for CRUD operations
    for m_instances_network_interface_list in m_instances_network_interfaces:
        for m_instances_network_interface in m_instances_network_interface_list.get("response", []):
            network_interface = IBMNetworkInterface.from_ibm_json_body(json_body=m_instances_network_interface)
            network_interfaces_id_security_group_ids_dict[network_interface.resource_id] = [
                m_interface_sg["id"] for m_interface_sg in m_instances_network_interface["security_groups"]
            ]
            network_interfaces_id_subnet_id_dict[network_interface.resource_id] = \
                m_instances_network_interface["subnet"]["id"]
            network_interfaces_id_instance_id_dict[network_interface.resource_id] = \
                m_instances_network_interface["href"].split("/")[5]
            network_interfaces.append(network_interface)
            network_interfaces_ids.append(network_interface.resource_id)

        # Getting resources information which are added/deleted/updated before mangoes time
        with get_db_session() as session:
            db_region = session.query(IBMRegion).filter_by(name=region_name, cloud_id=cloud_id).first()
            if not db_region:
                LOGGER.info(f"IBMRegion {region_name} not found")
                return

            last_synced_at = m_instances_network_interface_list["last_synced_at"]
            logged_resource = discovery_locked_resource(
                session=session, resource_type=IBMNetworkInterface.__name__, cloud_id=cloud_id,
                sync_start=last_synced_at, region=db_region)
            locked_rid_status.update(logged_resource)
    with get_db_session() as session:
        with session.no_autoflush:
            db_region = session.query(IBMRegion).filter_by(name=region_name, cloud_id=cloud_id).first()
            if not db_region:
                LOGGER.info(f"IBMRegion {region_name} not found")
                return
            region_id = db_region.id

            db_instances = \
                session.query(IBMInstance).filter_by(cloud_id=cloud_id, region_id=region_id).all()

            db_network_interfaces = []
            for db_instance in db_instances:
                db_network_interfaces.extend(db_instance.network_interfaces.all())

            # Deleting stale network_interfaces
            for db_network_interface in db_network_interfaces:
                if locked_rid_status.get(db_network_interface.resource_id) in [IBMResourceLog.STATUS_ADDED,
                                                                               IBMResourceLog.STATUS_UPDATED]:
                    continue
                if db_network_interface.resource_id not in network_interfaces_ids:
                    session.delete(db_network_interface)
                    session.commit()

            db_cloud = session.query(IBMCloud).filter_by(id=cloud_id).first()
            assert db_cloud

            # Querying again for fresh data after deletion
            db_instances = session.query(IBMInstance).filter_by(cloud_id=cloud_id, region_id=region_id).all()
            db_network_interfaces = []
            db_instances_id_obj_dict = dict()
            for db_instance in db_instances:
                db_network_interfaces.extend(db_instance.network_interfaces.all())
                db_instances_id_obj_dict[db_instance.resource_id] = db_instance

            db_network_interfaces_id_obj_dict = dict()
            for db_network_interface in db_network_interfaces:
                db_network_interfaces_id_obj_dict[db_network_interface.resource_id] = db_network_interface

            db_security_groups = session.query(IBMSecurityGroup).filter_by(cloud_id=cloud_id, region_id=region_id).all()
            db_security_groups_id_obj_dict = {
                db_security_group.resource_id: db_security_group for db_security_group in db_security_groups
            }

            db_subnets = session.query(IBMSubnet).filter_by(cloud_id=cloud_id, region_id=region_id).all()
            db_subnets_id_obj_dict = {
                db_subnet.resource_id: db_subnet for db_subnet in db_subnets
            }
            # Adding and deleting network interfaces
            for network_interface in network_interfaces:
                if locked_rid_status.get(network_interface.resource_id) in [IBMResourceLog.STATUS_DELETED,
                                                                            IBMResourceLog.STATUS_UPDATED]:
                    continue

                dis_add_update_db_security_groups = list()
                for sg_id in network_interfaces_id_security_group_ids_dict.get(network_interface.resource_id, []):
                    if db_security_groups_id_obj_dict.get(sg_id):
                        if db_security_groups_id_obj_dict[sg_id] not in dis_add_update_db_security_groups:
                            dis_add_update_db_security_groups.append(db_security_groups_id_obj_dict[sg_id])

                db_instance_obj = db_instances_id_obj_dict.get(
                    network_interfaces_id_instance_id_dict.get(network_interface.resource_id)
                )
                if not db_instance_obj:
                    continue

                db_subnet_obj = db_subnets_id_obj_dict.get(
                    network_interfaces_id_subnet_id_dict.get(network_interface.resource_id)
                )

                if not db_subnet_obj:
                    continue
                db_network_interface = db_network_interfaces_id_obj_dict.get(network_interface.resource_id)
                if db_network_interface:
                    if not network_interface.dis_params_eq(db_network_interface):
                        db_network_interface.update_from_object(network_interface)

                    db_network_interface.security_groups = list()
                    session.commit()
                    network_interface = db_network_interface
                network_interface.instance = db_instance_obj
                network_interface.security_groups = dis_add_update_db_security_groups
                network_interface.subnet = db_subnet_obj
                network_interface.ibm_cloud = db_cloud
                session.commit()

            session.commit()

    LOGGER.info("** Instance Network Interfaces synced in:{}".format((datetime.utcnow() - start_time).total_seconds()))


def update_instance_profiles(cloud_id, region_name, m_instance_profiles):
    if not m_instance_profiles:
        return

    start_time = datetime.utcnow()

    instance_profiles = list()
    instance_profiles_names = list()
    with get_db_session() as session:
        db_region = session.query(IBMRegion).filter_by(name=region_name, cloud_id=cloud_id).first()
        if not db_region:
            LOGGER.info(f"IBMRegion {region_name} not found")
            return

        db_instance_profiles = session.query(IBMInstanceProfile).filter_by(cloud_id=cloud_id,
                                                                           region_id=db_region.id).all()
        db_instance_profile_name_objs = {db_instance_profile.name: db_instance_profile for db_instance_profile in
                                         db_instance_profiles}

        for m_instance_profile_list in m_instance_profiles:
            for m_instance_profile in m_instance_profile_list.get('response', []):
                instance_profiles_names.append(m_instance_profile["name"])
                db_instance_profile = db_instance_profile_name_objs.get(m_instance_profile["name"])
                if db_instance_profile and db_instance_profile.mangos_params_eq(m_instance_profile):
                    continue

                instance_profile = IBMInstanceProfile.from_ibm_json_body(json_body=m_instance_profile)
                instance_profiles.append(instance_profile)

    with get_db_session() as session:
        with session.no_autoflush:
            db_region = session.query(IBMRegion).filter_by(name=region_name, cloud_id=cloud_id).first()
            if not db_region:
                LOGGER.info(f"IBMRegion {region_name} not found")
                return

            region_id = db_region.id
            db_instance_profiles = session.query(IBMInstanceProfile).filter_by(cloud_id=cloud_id,
                                                                               region_id=region_id).all()

            for db_instance_profile in db_instance_profiles:
                if db_instance_profile.name not in instance_profiles_names:
                    session.delete(db_instance_profile)

            session.commit()

            db_instance_profiles = session.query(IBMInstanceProfile).filter_by(cloud_id=cloud_id,
                                                                               region_id=region_id).all()

            for instance_profile in instance_profiles:
                instance_profile.dis_add_update_db(
                    session=session, db_instance_profiles=db_instance_profiles, cloud_id=cloud_id, db_region=db_region
                )

            session.commit()
    LOGGER.info("** Instance Profiles synced in:{}".format((datetime.utcnow() - start_time).total_seconds()))


def update_instance_disks(cloud_id, region_name, m_instance_disks):
    if not m_instance_disks:
        return

    start_time = datetime.utcnow()

    instance_disks = list()
    instance_disks_ids = list()
    locked_rid_status = dict()
    instance_disks_id_instance_id_dict = dict()

    for m_instance_disk_list in m_instance_disks:
        for m_instance_disk in m_instance_disk_list.get("response", []):
            instance_disk = IBMInstanceDisk.from_ibm_json_body(json_body=m_instance_disk)
            instance_disks_id_instance_id_dict[instance_disk.resource_id] = \
                m_instance_disk["href"].split("/")[5]
            instance_disks.append(instance_disk)
            instance_disks_ids.append(instance_disk.resource_id)

        with get_db_session() as session:
            db_region = session.query(IBMRegion).filter_by(name=region_name, cloud_id=cloud_id).first()
            if not db_region:
                LOGGER.info(f"IBMRegion {region_name} not found")
                return

            last_synced_at = m_instance_disk_list["last_synced_at"]
            logged_resource = discovery_locked_resource(
                session=session, resource_type=IBMInstanceDisk.__name__, cloud_id=cloud_id,
                sync_start=last_synced_at, region=db_region)
            locked_rid_status.update(logged_resource)

    with get_db_session() as db_session:
        with db_session.no_autoflush:

            db_region = db_session.query(IBMRegion).filter_by(name=region_name, cloud_id=cloud_id).first()
            if not db_region:
                LOGGER.info(f"IBMRegion {region_name} not found")
                return
            region_id = db_region.id

            db_instances = \
                db_session.query(IBMInstance).filter_by(cloud_id=cloud_id, region_id=region_id).all()

            db_instance_disks = []
            for db_instance in db_instances:
                db_instance_disks.extend(db_instance.instance_disks.all())

            for db_instance_disk in db_instance_disks:
                if locked_rid_status.get(db_instance_disk.resource_id) in [IBMResourceLog.STATUS_ADDED,
                                                                           IBMResourceLog.STATUS_UPDATED]:
                    continue
                if db_instance_disk.resource_id not in instance_disks_ids:
                    db_session.delete(db_instance_disk)

            db_session.commit()

            db_cloud = db_session.query(IBMCloud).filter_by(id=cloud_id).first()
            assert db_cloud

            db_instances = db_session.query(IBMInstance).filter_by(cloud_id=cloud_id, region_id=region_id).all()

            db_instance_disks = []
            db_instances_id_obj_dict = dict()
            for db_instance in db_instances:
                db_instance_disks.extend(db_instance.instance_disks.all())
                db_instances_id_obj_dict[db_instance.resource_id] = db_instance

            for instance_disk in instance_disks:
                if locked_rid_status.get(instance_disk.resource_id) in [IBMResourceLog.STATUS_DELETED,
                                                                        IBMResourceLog.STATUS_UPDATED]:
                    continue
                instance_disk.dis_add_update_db(
                    db_session=db_session, db_instance_disks=db_instance_disks, db_cloud=db_cloud,
                    db_instance=db_instances_id_obj_dict.get(
                        instance_disks_id_instance_id_dict[instance_disk.resource_id]
                    )
                )

    LOGGER.info("** Instance Disks synced in:{}".format((datetime.utcnow() - start_time).total_seconds()))
