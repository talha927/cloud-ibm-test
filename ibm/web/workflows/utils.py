from ibm import LOGGER, models
from ibm.models import WorkflowRoot, WorkflowTask
from ibm.web import db as ibmdb
from ibm.web.softlayer.recommendations.utils import get_resource_json_for_recommendations


def get_resource_json(workflow_root):
    """
    Generates JSON of a successfully completed CREATION WorkflowRoot's main resource
    :param workflow_root: <Object: WorkflowRoot> The workflow root from which to extract main resource's info
    :return:
    """
    resource_json = {}
    try:
        if workflow_root.status != WorkflowRoot.STATUS_C_SUCCESSFULLY or \
                workflow_root.workflow_nature not in ["ADD", "CREATE"]:
            LOGGER.info(
                f"Can not get resource json for status '{workflow_root.status}', "
                f"nature '{workflow_root.workflow_nature}'"
            )
            return resource_json

        resource_type = workflow_root.workflow_name.split()[0]
        if not resource_type:
            LOGGER.info(f"No resource type found for workflow root {workflow_root.id}")
            return resource_json

        if resource_type == "SoftLayerRecommendation":
            resource_json = get_resource_json_for_recommendations(workflow_root)
            return resource_json

        db_model = getattr(models, resource_type)
        if not db_model:
            LOGGER.info(f"Resource type {resource_type} not found in models")
            return resource_json

        resource_id_task = workflow_root.associated_tasks.filter(
            WorkflowTask.resource_type == resource_type, WorkflowTask.resource_id.is_not(None)
        ).first()
        if not resource_id_task:
            LOGGER.info(workflow_root.to_json())
            LOGGER.info(f"Could not find task having resource_id for {resource_type} in parent data")
            return resource_json

        resource = ibmdb.session.query(db_model).filter_by(id=resource_id_task.resource_id).first()
        if not resource:
            LOGGER.info(f"{resource_type} with id {resource_id_task.resource_id} not found in db")
            return resource_json

        resource_json = resource.to_json()
    except Exception as ex:
        LOGGER.error(str(ex))
    finally:
        return resource_json
