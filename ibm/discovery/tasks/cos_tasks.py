import logging
from datetime import datetime

from sqlalchemy.orm.exc import StaleDataError

from ibm.common.consts import BUCKET_CROSS_REGION_TO_REGIONS_MAPPER, BUCKET_DATA_CENTER_TO_REGION_MAPPER
from ibm.discovery import get_db_session
from ibm.discovery.common.utils import discovery_locked_resource
from ibm.models import IBMCloud, IBMCloudObjectStorage, IBMCOSBucket, IBMRegion, IBMResourceGroup, \
    IBMResourceLog, IBMServiceCredentialKey

LOGGER = logging.getLogger(__name__)


def update_cloud_object_storages(cloud_id, m_cloud_object_storages):
    if not m_cloud_object_storages:
        return

    start_time = datetime.utcnow()

    cloud_object_storages = list()
    cloud_object_storages_names = list()

    for m_cloud_object_storage_list in m_cloud_object_storages:
        for m_cloud_object_storage in m_cloud_object_storage_list.get("response"):
            cloud_object_storage = IBMCloudObjectStorage.from_ibm_json_body(json_body=m_cloud_object_storage)
            cloud_object_storages.append(cloud_object_storage)
            cloud_object_storages_names.append(cloud_object_storage.name)

    with get_db_session() as db_session:
        with db_session.no_autoflush:
            ibm_cloud = db_session.query(IBMCloud).filter_by(id=cloud_id).first()
            assert ibm_cloud, f"IBMCloud with id{cloud_id} not found."

            db_cloud_object_storages = db_session.query(IBMCloudObjectStorage).filter_by(cloud_id=cloud_id).all()
            for db_cloud_object_storage in db_cloud_object_storages:
                if db_cloud_object_storage.name not in cloud_object_storages_names:
                    db_session.delete(db_cloud_object_storage)
            # TODO this try catch is a jogar not fix, need this proper fix then will remove this StaleDataError
            try:
                db_session.commit()
            except StaleDataError as ex:
                db_session.rollback()
                LOGGER.info(ex)
            for cloud_object_storage in cloud_object_storages:
                db_cloud_object_storage = db_session.query(IBMCloudObjectStorage).filter_by(
                    name=cloud_object_storage.name, cloud_id=cloud_id).first()
                cloud_object_storage.dis_add_update_db(db_session=db_session,
                                                       db_cloud_object_storage=db_cloud_object_storage,
                                                       db_cloud=ibm_cloud)
            db_session.commit()

    LOGGER.info("** Cloud Object Storage synced in:{}".format((datetime.utcnow() - start_time).total_seconds()))


def update_cos_buckets(cloud_id, m_cos_buckets):
    if not m_cos_buckets:
        return

    start_time = datetime.utcnow()

    cos_buckets = list()
    cos_bucket_names = list()
    cos_bucket_name_cos_crns = dict()
    locked_rid_status = dict()

    for m_cos_bucket_list in m_cos_buckets:
        for m_cos_bucket in m_cos_bucket_list.get("response", []):
            cos_bucket = IBMCOSBucket.from_ibm_json_body(json_body=m_cos_bucket)
            cos_buckets.append(cos_bucket)
            new_cos_bucket_name = f"{m_cos_bucket['cos_crn']}/{cos_bucket.name}"
            cos_bucket_names.append(new_cos_bucket_name)
            cos_bucket_name_cos_crns[cos_bucket.name] = m_cos_bucket["cos_crn"]

        last_synced_at = m_cos_bucket_list["last_synced_at"]
        with get_db_session() as session:
            logged_resource = discovery_locked_resource(
                session=session, resource_type=IBMCOSBucket.__name__, cloud_id=cloud_id,
                sync_start=last_synced_at)
            locked_rid_status.update(logged_resource)

    with get_db_session() as session:
        with session.no_autoflush:
            ibm_cloud = session.query(IBMCloud).filter_by(id=cloud_id).first()
            assert ibm_cloud, f"IBMCloud with id {cloud_id} not found."

            db_cos_buckets = session.query(IBMCOSBucket).filter_by(cloud_id=cloud_id).all()

            db_cos_bucket_name_bucket = dict()
            for db_cos_bucket in db_cos_buckets:
                cloud_object_storage = db_cos_bucket.cloud_object_storage
                if not cloud_object_storage:
                    continue

                cos_bucket_name = f"{cloud_object_storage.crn}/{db_cos_bucket.name}"
                if locked_rid_status.get(cos_bucket_name) in [IBMResourceLog.STATUS_ADDED,
                                                              IBMResourceLog.STATUS_UPDATED]:
                    continue

                if cos_bucket_name not in cos_bucket_names:
                    session.delete(db_cos_bucket)
                    continue

                db_cos_bucket_name_bucket[cos_bucket_name] = db_cos_bucket

            session.commit()

            for cos_bucket in cos_buckets:
                cos_bucket_name = f"{cos_bucket_name_cos_crns[cos_bucket.name]}/{cos_bucket.name}"
                if locked_rid_status.get(cos_bucket_name) in [IBMResourceLog.STATUS_DELETED,
                                                              IBMResourceLog.STATUS_UPDATED]:
                    continue

                if cos_bucket_name in db_cos_bucket_name_bucket:
                    db_cos_bucket_name_bucket[cos_bucket_name].update_from_object(cos_bucket)
                    cos_bucket = db_cos_bucket_name_bucket[cos_bucket_name]
                    session.commit()

                bucket_regions = list()
                if cos_bucket.location_constraint in BUCKET_CROSS_REGION_TO_REGIONS_MAPPER:
                    bucket_regions.extend(BUCKET_CROSS_REGION_TO_REGIONS_MAPPER[cos_bucket.location_constraint])
                elif cos_bucket.location_constraint in BUCKET_DATA_CENTER_TO_REGION_MAPPER:
                    bucket_regions.extend(BUCKET_DATA_CENTER_TO_REGION_MAPPER[cos_bucket.location_constraint])
                else:
                    bucket_regions.append(cos_bucket.location_constraint)

                db_regions = session.query(IBMRegion).filter(
                    IBMRegion.name.in_(bucket_regions), IBMRegion.cloud_id == cloud_id
                ).all()
                if not db_regions:
                    LOGGER.info(f"IBMCOSBucket regions not found for cloud {cloud_id}.")
                    continue

                db_cloud_object_storage = session.query(IBMCloudObjectStorage).filter_by(
                    crn=cos_bucket_name_cos_crns[cos_bucket.name], cloud_id=cloud_id).first()
                if not db_cloud_object_storage:
                    continue

                cos_bucket.ibm_cloud = ibm_cloud
                cos_bucket.cloud_object_storage = db_cloud_object_storage
                cos_bucket.regions = db_regions
                session.commit()

    LOGGER.info("** COS Buckets synced in:{}".format((datetime.utcnow() - start_time).total_seconds()))


def update_cos_access_keys(cloud_id, m_credentials_keys):
    if not m_credentials_keys:
        return

    start_time = datetime.utcnow()

    parsed_keys_list = list()
    keys_names = set()
    keys_name_cos_crn = dict()
    keys_name_rg_rid = dict()

    with get_db_session() as db_session:
        db_credential_keys = db_session.query(IBMServiceCredentialKey).filter_by(cloud_id=cloud_id).all()
        db_credential_keys_names_set = {db_credential_key.name for db_credential_key in db_credential_keys}

    for m_credentials_key_list in m_credentials_keys:
        for keys_dict in m_credentials_key_list.get('response', []):
            keys_names.add(keys_dict["name"])
            if keys_dict["name"] in db_credential_keys_names_set:
                continue

            if not all([keys_dict.get("role"), keys_dict["credentials"].get("resource_instance_id")]):
                continue

            parsed_key = IBMServiceCredentialKey.from_ibm_json_body(keys_dict)
            parsed_keys_list.append(parsed_key)
            keys_name_cos_crn[parsed_key.name] = keys_dict["credentials"]["resource_instance_id"]
            keys_name_rg_rid[parsed_key.name] = keys_dict["resource_group_id"]

    with get_db_session() as db_session:
        ibm_cloud = db_session.query(IBMCloud).filter_by(id=cloud_id).first()
        if not ibm_cloud:
            LOGGER.info(f"IBMCloud '{cloud_id}' not found during update_cos_access_keys task")
            return

        stale_keys = db_session.query(IBMServiceCredentialKey).filter(
            IBMServiceCredentialKey.cloud_id == cloud_id, IBMServiceCredentialKey.name.not_in(keys_names)
        ).all()
        for key in stale_keys:
            db_session.delete(key)

        db_session.commit()

        db_cos_objects = db_session.query(IBMCloudObjectStorage).filter_by(cloud_id=cloud_id).all()
        db_cos_crn_obj_dict = {db_cos_object.crn: db_cos_object for db_cos_object in db_cos_objects}

        db_resource_groups = db_session.query(IBMResourceGroup).filter_by(cloud_id=cloud_id).all()
        db_resource_group_rid_obj_dict = {db_resource_group.resource_id: db_resource_group for db_resource_group in
                                          db_resource_groups}

        for parsed_key in parsed_keys_list:
            if parsed_key.name in db_credential_keys_names_set:
                continue

            cos_crn = keys_name_cos_crn.get(parsed_key.name)
            if not cos_crn:
                continue

            cos = db_cos_crn_obj_dict.get(cos_crn)
            if not cos:
                LOGGER.info(f"IBM Cloud Object Storage with crn '{cos_crn}' not found")
                continue

            rg_rid = keys_name_rg_rid.get(parsed_key.name)
            if not rg_rid:
                continue

            db_resource_group = db_resource_group_rid_obj_dict.get(rg_rid)
            if not db_resource_group:
                LOGGER.info(f"IBM Resource Group '{rg_rid}' not found")
                continue

            parsed_key.cloud_object_storage = cos
            parsed_key.resource_group = db_resource_group
            parsed_key.ibm_cloud = ibm_cloud

        db_session.commit()

    LOGGER.info(
        f"** COS Access keys for cloud: {cloud_id} synced in:{(datetime.utcnow() - start_time).total_seconds()}")
