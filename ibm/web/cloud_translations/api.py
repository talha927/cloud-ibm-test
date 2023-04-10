import logging

from apiflask import APIBlueprint, auth_required, input, output

from ibm.auth import auth
from ibm.common.req_resp_schemas.schemas import WorkflowRootOutSchema
from ibm.models import WorkflowRoot, WorkflowTask
from ibm.web import db as ibmdb
from ibm.web.cloud_translations.schemas import TranslationInSchema
from ibm.web.common.utils import authorize_and_get_ibm_cloud, verify_and_get_region

LOGGER = logging.getLogger(__name__)

cloud_translations = APIBlueprint('cloud_translations', __name__, tag="Cloud Translations")


@cloud_translations.route('/translations', methods=['POST'])
@auth_required(auth=auth)
@input(TranslationInSchema)
@output(WorkflowRootOutSchema, status_code=202)
def translate(data):
    """
    This function create translation task for translation from provided cloud to IBM
    """
    user = auth.current_user

    cloud_id = data["ibm_cloud"]["id"]
    region_id = data["region"]["id"]
    data["user"] = user

    ibm_cloud = authorize_and_get_ibm_cloud(cloud_id=cloud_id, user=user)
    verify_and_get_region(ibm_cloud=ibm_cloud, region_id=region_id)

    workflow_root = WorkflowRoot(
        workflow_name=f"{data['source_cloud']['type']}_TO_IBM", workflow_nature="TRANSLATION",
        project_id=user["project_id"], user_id=user["id"]
    )
    translation_task = WorkflowTask(
        resource_type="TRANSLATION", task_type=WorkflowTask.TYPE_CREATE, task_metadata=data)
    workflow_root.add_next_task(translation_task)

    ibmdb.session.add(workflow_root)
    ibmdb.session.commit()

    return workflow_root.to_json()
