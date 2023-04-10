import json
import logging

from requests.exceptions import ConnectionError, ReadTimeout, RequestException

from ibm import get_db_session
from ibm.models import IBMCloud, IBMImage, IBMInstanceProfile, IBMLoadBalancerProfile, IBMOperatingSystem, IBMRegion, \
    IBMResourceGroup, WorkflowTask, WorkflowsWorkspace
from ibm.tasks.celery_app import celery_app as celery
from ibm.tasks.common.tasks_base import IBMWorkflowTasksBase
from ibm.tasks.translation_tasks.utils import get_cloud_translation_json, initiate_translation
from ibm.web.ibm.workspaces.utils import create_workspace_workflow

LOGGER = logging.getLogger(__name__)


@celery.task(name="translate_vpc_construct", queue="translation_queue", base=IBMWorkflowTasksBase)
def translate_vpc_construct(workflow_task_id):
    """
    This task executes requests respective clouds to get json data for translation.
    """
    with get_db_session() as db_session:
        workflow_task = db_session.query(WorkflowTask).filter_by(id=workflow_task_id).first()
        if not workflow_task:
            return

        workflow_task.status = WorkflowTask.STATUS_RUNNING
        db_session.commit()

        task_metadata = dict(workflow_task.task_metadata)
        cloud_id = task_metadata["ibm_cloud"]["id"]
        region_id = task_metadata["region"]["id"]

    try:
        response = get_cloud_translation_json(task_metadata)
    except (ConnectionError, ReadTimeout, RequestException, NotImplementedError) as ex:
        LOGGER.info(ex)
        with get_db_session() as db_session:
            workflow_task = db_session.query(WorkflowTask).filter_by(id=workflow_task_id).first()
            if not workflow_task:
                return

            workflow_task.status = WorkflowTask.STATUS_FAILED
            workflow_task.message = ex
            db_session.commit()

        return

    with get_db_session() as db_session:
        workflow_task = db_session.query(WorkflowTask).filter_by(id=workflow_task_id).first()
        if not workflow_task:
            return

        resource_group = db_session.query(IBMResourceGroup).filter_by(
            id=task_metadata["resource_group"]["id"]).first()
        if not resource_group:
            workflow_task.status = WorkflowTask.STATUS_FAILED
            workflow_task.message = f"Resource group with ID {task_metadata['resource_group']['id']} not found in DB"
            db_session.commit()
            LOGGER.info(workflow_task.message)
            return

        region = db_session.query(IBMRegion).filter_by(id=region_id).first()
        if not region:
            workflow_task.status = WorkflowTask.STATUS_FAILED
            workflow_task.message = f"Region with ID {region_id} not found in DB"
            db_session.commit()
            LOGGER.info(workflow_task.message)
            return

        if response.status_code == 200:
            response = response.json()
            ibm_cloud = db_session.query(IBMCloud).filter_by(id=cloud_id).first()
            images = db_session.query(IBMImage).filter_by(
                cloud_id=cloud_id, region_id=region_id, visibility="public"
            ).join(IBMOperatingSystem).filter(IBMOperatingSystem.family != "Windows Server").all()

            instance_profile = db_session.query(IBMInstanceProfile).filter_by(
                cloud_id=cloud_id, region_id=region_id, name="bx2-2x8").first()

            db_image_name_obj_dict = {
                image.name: image.to_translation_reference_json() for image in images
            }

            profiles = db_session.query(IBMLoadBalancerProfile).all()
            db_profile_family_obj_dict = {}
            for profile in profiles:
                if profile.name == 'network-fixed' or profile.name == 'dynamic':
                    db_profile_family_obj_dict[profile.family] = profile.to_reference_json()

            translated_data = initiate_translation(
                cloud=ibm_cloud, task_metadata=task_metadata, data_to_translate=response, region=region,
                resource_group=resource_group, db_image_name_obj_dict=db_image_name_obj_dict,
                instance_profile=instance_profile, load_balancer_profiles=db_profile_family_obj_dict
            )

            # TODO for now this only AWS, this should be taken from translated_data
            workspace = create_workspace_workflow(
                user=task_metadata["user"], data=translated_data, db_session=db_session, sketch=True,
                source_cloud=WorkflowsWorkspace.AWS, workspace_type=WorkflowsWorkspace.TYPE_TRANSLATION
            )
            task_metadata['translated_data'] = json.dumps(workspace.to_json(), default=str)
            workflow_task.task_metadata = task_metadata
            workflow_task.status = WorkflowTask.STATUS_SUCCESSFUL
            db_session.commit()
            LOGGER.info(f"Translation for Task ID {workflow_task_id} completed successfully")

        else:
            workflow_task.status = WorkflowTask.STATUS_FAILED
            workflow_task.message = f"Not able to Translate Data, status code {response.status_code}"
            db_session.commit()
            LOGGER.info(workflow_task.message)
