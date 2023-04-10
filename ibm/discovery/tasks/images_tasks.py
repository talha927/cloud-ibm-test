import logging
from datetime import datetime

from ibm.discovery import get_db_session
from ibm.discovery.common.utils import discovery_locked_resource
from ibm.models import IBMCloud, IBMImage, IBMOperatingSystem, IBMRegion, IBMResourceGroup, IBMResourceLog

LOGGER = logging.getLogger(__name__)


def update_operating_systems(cloud_id, region_name, m_operating_systems):
    if not m_operating_systems:
        return

    start_time = datetime.utcnow()

    operating_systems = list()
    operating_systems_names = list()

    for m_operating_system_list in m_operating_systems:
        for m_operating_system in m_operating_system_list.get("response", []):
            operating_system = IBMOperatingSystem.from_ibm_json_body(json_body=m_operating_system)
            operating_systems.append(operating_system)
            operating_systems_names.append(operating_system.name)

    with get_db_session() as session:
        with session.no_autoflush:
            db_region = session.query(IBMRegion).filter_by(name=region_name, cloud_id=cloud_id).first()
            if not db_region:
                LOGGER.info(f"IBMRegion {region_name} not found")
                return
            region_id = db_region.id

            db_operating_systems = session.query(IBMOperatingSystem).filter_by(cloud_id=cloud_id,
                                                                               region_id=region_id).all()

            for db_operating_system in db_operating_systems:
                if db_operating_system.name not in operating_systems_names:
                    session.delete(db_operating_system)

            session.commit()

            for operating_system in operating_systems:
                db_operating_system = session.query(IBMOperatingSystem).filter_by(cloud_id=cloud_id,
                                                                                  region_id=region_id,
                                                                                  name=operating_system.name).first()
                operating_system.dis_add_update_db(
                    session=session, db_operating_system=db_operating_system, cloud_id=cloud_id,
                    db_region=db_region
                )

            session.commit()

    LOGGER.info("** Operating Systems synced in:{}".format((datetime.utcnow() - start_time).total_seconds()))


def update_images(cloud_id, region_name, m_images):
    if not m_images:
        return

    start_time = datetime.utcnow()

    images = list()
    images_ids = list()
    images_id_rgid_dict = dict()
    images_id_operating_system_obj_dict = dict()
    locked_rid_status = dict()

    with get_db_session() as session:
        db_region = session.query(IBMRegion).filter_by(name=region_name, cloud_id=cloud_id).first()
        if not db_region:
            LOGGER.info(f"IBMRegion {region_name} not found")
            return

        db_images = session.query(IBMImage).filter_by(cloud_id=cloud_id, region_id=db_region.id).all()
        db_image_rid_obj = {db_image.resource_id: db_image for db_image in db_images}

        for m_image_list in m_images:
            for m_image in m_image_list.get("response", []):
                images_ids.append(m_image["id"])
                db_image = db_image_rid_obj.get(m_image["id"])
                if db_image and db_image.mangos_params_eq(m_image):
                    continue

                image = IBMImage.from_ibm_json_body(json_body=m_image)
                if m_image["resource_group"]["id"]:
                    images_id_rgid_dict[image.resource_id] = m_image["resource_group"]["id"]

                if m_image.get("operating_system"):
                    images_id_operating_system_obj_dict[image.resource_id] = \
                        IBMOperatingSystem.from_ibm_json_body(json_body=m_image["operating_system"])
                images.append(image)

            last_synced_at = m_image_list["last_synced_at"]
            logged_resource = discovery_locked_resource(
                session=session, resource_type=IBMImage.__name__, cloud_id=cloud_id,
                sync_start=last_synced_at, region=db_region)
            locked_rid_status.update(logged_resource)

    with get_db_session() as session:
        with session.no_autoflush:
            db_region = session.query(IBMRegion).filter_by(name=region_name, cloud_id=cloud_id).first()
            if not db_region:
                LOGGER.info(f"IBMRegion {region_name} not found")
                return
            region_id = db_region.id

            db_images = \
                session.query(IBMImage).filter_by(cloud_id=cloud_id, region_id=region_id).all()

            for db_image in db_images:
                if locked_rid_status.get(db_image.resource_id) in [IBMResourceLog.STATUS_ADDED,
                                                                   IBMResourceLog.STATUS_UPDATED]:
                    continue

                if db_image.resource_id not in images_ids:
                    session.delete(db_image)

            session.commit()

            db_cloud = session.query(IBMCloud).filter_by(id=cloud_id).first()
            assert db_cloud

            for image in images:
                if locked_rid_status.get(image.resource_id) in [IBMResourceLog.STATUS_DELETED,
                                                                IBMResourceLog.STATUS_UPDATED]:
                    continue
                db_resource_group = session.query(IBMResourceGroup).filter_by(cloud_id=cloud_id,
                                                                              resource_id=images_id_rgid_dict.get(
                                                                                  image.resource_id)).first()

                db_image = session.query(IBMImage).filter_by(cloud_id=cloud_id, region_id=region_id,
                                                             resource_id=image.resource_id).first()
                if not images_id_operating_system_obj_dict.get(image.resource_id):
                    continue
                db_operating_systems = session.query(IBMOperatingSystem).filter_by(
                    cloud_id=cloud_id, region_id=region_id,
                    name=images_id_operating_system_obj_dict[image.resource_id].name
                ).first()

                image.dis_add_update_db(
                    session=session,
                    db_image=db_image,
                    db_operating_systems=db_operating_systems,
                    db_cloud=db_cloud,
                    db_resource_group=db_resource_group,
                    operating_system_obj=images_id_operating_system_obj_dict.get(image.resource_id),
                    db_region=db_region
                )

            session.commit()
    LOGGER.info("** Images synced in:{}".format((datetime.utcnow() - start_time).total_seconds()))
