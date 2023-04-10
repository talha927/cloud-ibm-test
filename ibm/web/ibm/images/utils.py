import json
import random

from ibm.common.clients.ibm_clients import ImagesClient
from ibm.common.clients.ibm_clients.exceptions import IBMAuthError, IBMConnectError, IBMExecuteError, \
    IBMInvalidRequestError
from ibm.models import IBMImage, WorkflowTask
from ibm.web import db as ibmdb


def return_image_name(cloud_id, region, image_name):
    try:
        client = ImagesClient(cloud_id=cloud_id, region=region)
        images = client.list_images(name=image_name, visibility="private")
    except (IBMExecuteError, IBMAuthError, IBMConnectError) as ex:
        raise IBMExecuteError(f"Could not get images from ibm for region: {region} for cloud: {cloud_id}, Error: {ex}")
    if not images:
        return image_name
    for i in range(10):
        rad = random.randint(0, 1000)
        image_name = image_name[-58:] + str(rad)
        images = client.list_images(name=image_name, visibility="private")
        if not images:
            return image_name
    raise IBMInvalidRequestError(f"Couldn't get a unique name for image in region: {region}")


def delete_ibm_image_workflow(workflow_root, db_resource):
    """
    This Function creates workflow task for Image deletion
    """
    workflow_root.add_next_task(WorkflowTask(
        resource_type=IBMImage.__name__, resource_id=db_resource.id, task_type=WorkflowTask.TYPE_DELETE,
        task_metadata=json.dumps(db_resource.to_json(), default=str)))
    ibmdb.session.add(workflow_root)
    ibmdb.session.commit()
