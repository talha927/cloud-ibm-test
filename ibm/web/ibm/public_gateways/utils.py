import json

from ibm.models import IBMPublicGateway, WorkflowTask
from ibm.web import db as ibmdb


def delete_ibm_public_gateway_workflow(workflow_root, db_resource):
    """
    This Function creates workflow task for Public Gateway deletion
    """
    workflow_root.add_next_task(WorkflowTask(
        resource_type=IBMPublicGateway.__name__, resource_id=db_resource.id, task_type=WorkflowTask.TYPE_DELETE,
        task_metadata=json.dumps(db_resource.to_json(), default=str)))
    ibmdb.session.add(workflow_root)
    ibmdb.session.commit()
