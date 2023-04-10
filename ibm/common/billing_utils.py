import json
import logging

from ibm.models import BillingResource, IBMCloud, SoftlayerCloud, IBMVpcNetwork

LOGGER = logging.getLogger(__name__)


def log_resource_billing_in_db(workflow_task):
    from ibm import get_db_session, models

    if workflow_task.resource_type in ['TRANSLATION', 'SoftLayerRecommendation']:
        return

    with get_db_session() as db_session:
        # These are not actual task, mostly just discovering,
        # Code should be like this but due to circular import can't do like this
        if workflow_task.task_type != "CREATE":
            return

        resource_model = getattr(models, workflow_task.resource_type)
        if isinstance(resource_model, IBMCloud) or isinstance(resource_model, SoftlayerCloud):
            return
        resource_obj = db_session.query(resource_model).filter_by(id=workflow_task.resource_id).first()
        if not resource_obj:
            data = workflow_task.task_metadata
            cloud_dict = workflow_task.task_metadata.get("resource_data", {}).get("ibm_cloud")
            if not cloud_dict:
                cloud_dict = workflow_task.task_metadata.get("ibm_cloud")
            ibm_cloud = db_session.query(IBMCloud).filter_by(**cloud_dict).first()
            if not ibm_cloud:
                return
            cloud_id = ibm_cloud.id
            user_id = ibm_cloud.user_id
            project_id = ibm_cloud.project_id
        else:
            if resource_model.__name__ == IBMVpcNetwork.__name__:
                data = json.dumps(resource_obj.to_json(session=db_session), indent=4, sort_keys=True, default=str)
            else:
                data = json.dumps(resource_obj.to_json(), indent=4, sort_keys=True, default=str)
            cloud_id = resource_obj.ibm_cloud.id
            user_id = resource_obj.ibm_cloud.user_id
            project_id = resource_obj.ibm_cloud.project_id
        try:
            log_resource = BillingResource(
                resource_type=resource_model.__name__,
                resource_data=data,
                action=workflow_task.task_type,
                cloud_id=cloud_id,
                user_id=user_id,
                project_id=project_id
            )
            db_session.add(log_resource)
            db_session.commit()
            LOGGER.info(f"Resource '{resource_model.__name__}' logged for billing.")
        except KeyError:
            LOGGER.error("Resource {} not registered for billing".format(resource_model.__name__))
