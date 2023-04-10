import logging

from ibm.models import WorkflowTask

LOGGER = logging.getLogger(__name__)


def get_resource_json_for_recommendations(workflow_root):
    """
    Generates JSON of a successfully completed task for generation Softlayer Recommendations
    :param workflow_root: <Object: WorkflowRoot> The workflow root from which to extract main resource's info
    :return:
    """
    resource_json = {}
    try:
        recommendation_task = workflow_root.associated_tasks.filter(
            WorkflowTask.resource_type == "SoftLayerRecommendation",
            WorkflowTask.task_type == WorkflowTask.TYPE_CREATE).first()
        if recommendation_task:
            resource_json = recommendation_task.result

    except Exception as ex:
        LOGGER.info(str(ex))
    finally:
        return resource_json
