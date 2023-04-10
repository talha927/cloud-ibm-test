from ibm_cloud_sdk_core import ApiException

from ibm import get_db_session, LOGGER
from ibm.common.clients.ibm_clients import GeographyClient
from ibm.models import IBMCloud, IBMRegion, IBMZone, WorkflowTask
from ibm.tasks.celery_app import celery_app as celery
from ibm.tasks.common.tasks_base import IBMWorkflowTasksBase


@celery.task(name="update_geography", base=IBMWorkflowTasksBase)
def update_geography(workflow_task_id):
    """
    Update Geography data (Regions and Zones)
    """
    with get_db_session() as db_session:
        workflow_task = db_session.query(WorkflowTask).filter_by(id=workflow_task_id).first()
        if not workflow_task:
            return

        workflow_task.status = WorkflowTask.STATUS_RUNNING
        db_session.commit()

        task_metadata = workflow_task.task_metadata
        if not task_metadata:
            workflow_task.status = WorkflowTask.STATUS_FAILED
            workflow_task.message = "Internal Server Error"
            db_session.commit()
            LOGGER.error(workflow_task.message)
            return

        cloud_id = task_metadata["cloud_id"]
        if not cloud_id:
            workflow_task.status = WorkflowTask.STATUS_FAILED
            workflow_task.message = "Internal Server Error"
            db_session.commit()
            LOGGER.error(workflow_task.message)
            return

        ibm_cloud = db_session.query(IBMCloud).filter_by(id=cloud_id).first()
        if not ibm_cloud:
            workflow_task.status = WorkflowTask.STATUS_FAILED
            workflow_task.message = f"IBMCloud '{task_metadata['cloud_id']}' not found"
            db_session.commit()
            LOGGER.error(workflow_task.message)
            return

    updated_region_names = []
    updated_zone_names = []
    try:
        geo_client = GeographyClient(cloud_id)
        fetched_region_dicts_list = geo_client.list_regions()
        for region_dict in fetched_region_dicts_list:
            fetched_zone_dicts_list = geo_client.list_zones_in_region(region_dict["name"])
            region_dict["zones"] = fetched_zone_dicts_list

            updated_region_names.append(region_dict["name"])
            updated_zone_names.extend([zone_dict["name"] for zone_dict in fetched_zone_dicts_list])

    except ApiException as ex:
        with get_db_session() as db_session:
            workflow_task = db_session.query(WorkflowTask).filter_by(id=workflow_task_id).first()
            if not workflow_task:
                return

            workflow_task.status = WorkflowTask.STATUS_FAILED
            workflow_task.message = str(ex.message)
            ibm_cloud = db_session.query(IBMCloud).filter_by(id=workflow_task.resource_id).first()
            if ibm_cloud:
                ibm_cloud.status = IBMCloud.STATUS_INVALID
            db_session.commit()
            LOGGER.fail(ex.message)
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

        db_session.query(IBMRegion).filter(
            IBMRegion.cloud_id == cloud_id, IBMRegion.name.not_in(updated_region_names)
        ).delete()
        db_regions = db_session.query(IBMRegion).filter_by(cloud_id=cloud_id).all()
        db_region_name_region_obj_dict = {db_region.name: db_region for db_region in db_regions}

        db_session.query(IBMZone).filter(
            IBMZone.cloud_id == cloud_id, IBMZone.name.not_in(updated_zone_names)
        ).delete()
        db_zones = db_session.query(IBMZone).filter_by(cloud_id=cloud_id).all()
        db_zone_name_zone_obj_dict = {db_zone.name: db_zone for db_zone in db_zones}

        for region_dict in fetched_region_dicts_list:
            parsed_region = IBMRegion.from_ibm_json_body(region_dict)
            if parsed_region.name in db_region_name_region_obj_dict:
                db_region = db_region_name_region_obj_dict[parsed_region.name]
                db_region.update_from_obj(parsed_region)
            else:
                parsed_region.ibm_cloud = ibm_cloud
                db_region = parsed_region

            for zone_dict in region_dict["zones"]:
                parsed_zone = IBMZone.from_ibm_json_body(zone_dict)
                if parsed_zone.name in db_zone_name_zone_obj_dict:
                    db_zone = db_zone_name_zone_obj_dict[parsed_zone.name]
                    db_zone.update_from_obj(parsed_zone)
                    db_zone.region = db_region
                else:
                    parsed_zone.region = db_region

        workflow_task.status = WorkflowTask.STATUS_SUCCESSFUL
        db_session.commit()
        LOGGER.success(f"Regions for {ibm_cloud.id} updated successfully")
