from copy import deepcopy
from ibm_cloud_sdk_core import ApiException

from ibm import get_db_session, LOGGER
from ibm.common.clients.ibm_clients import NetworkACLsClient
from ibm.common.utils import update_id_or_name_references
from ibm.models import IBMNetworkAcl, IBMNetworkAclRule, IBMRegion, IBMResourceGroup, IBMResourceLog, IBMVpcNetwork, \
    WorkflowTask
from ibm.tasks.celery_app import celery_app as celery
from ibm.tasks.common.tasks_base import IBMWorkflowTasksBase
from ibm.tasks.ibm.task_utils import load_previous_associated_resources
from ibm.web.ibm.acls.schemas import IBMAclInSchema, IBMAclResourceSchema, IBMAclRuleInSchema, IBMAclRuleResourceSchema


@celery.task(name="create_network_acl", base=IBMWorkflowTasksBase)
def create_network_acl(workflow_task_id):
    """
    Create an IBM Network Acl on IBM Cloud
    """
    with get_db_session() as db_session:
        workflow_task = db_session.query(WorkflowTask).filter_by(id=workflow_task_id).first()
        if not workflow_task:
            return

        workflow_task.status = WorkflowTask.STATUS_RUNNING
        db_session.commit()

        resource_data = deepcopy(workflow_task.task_metadata["resource_data"])
        resource_json = deepcopy(resource_data["resource_json"])
        cloud_id = resource_data["ibm_cloud"]["id"]
        region_id = resource_data["region"]["id"]

        region = db_session.query(IBMRegion).filter_by(id=region_id, cloud_id=cloud_id).first()
        if not region:
            workflow_task.status = WorkflowTask.STATUS_FAILED
            workflow_task.message = f"IBMRegion '{region_id}' not found"
            db_session.commit()
            LOGGER.error(workflow_task.message)
            return

        if region.ibm_status == IBMRegion.IBM_STATUS_UNAVAILABLE:
            workflow_task.status = WorkflowTask.STATUS_FAILED
            workflow_task.message = f"IBMRegion '{region.name}' unavailable"
            db_session.commit()
            LOGGER.error(workflow_task.message)
            return

        region_name = region.name

        previous_resources = load_previous_associated_resources(task=workflow_task, session=db_session)
        update_id_or_name_references(
            cloud_id=cloud_id, resource_json=resource_data, resource_schema=IBMAclInSchema,
            db_session=db_session, previous_resources=previous_resources
        )

        update_id_or_name_references(
            cloud_id=cloud_id, resource_json=resource_json, resource_schema=IBMAclResourceSchema,
            db_session=db_session, previous_resources=previous_resources
        )

        if "subnets" in resource_json:
            del resource_json["subnets"]

    try:
        client = NetworkACLsClient(cloud_id=cloud_id, region=region_name)
        network_acl_json = client.create_network_acl(network_acl_json=resource_json)

    except ApiException as ex:
        with get_db_session() as db_session:
            workflow_task = db_session.query(WorkflowTask).filter_by(id=workflow_task_id).first()
            if not workflow_task:
                return

            workflow_task.status = WorkflowTask.STATUS_FAILED
            workflow_task.message = f"Creation Failed. Reason: {str(ex.message)}"
            db_session.commit()
            LOGGER.fail(workflow_task.message)
            return

    with get_db_session() as db_session:
        workflow_task = db_session.query(WorkflowTask).filter_by(id=workflow_task_id).first()
        if not workflow_task:
            return

        with db_session.no_autoflush:
            region = db_session.query(IBMRegion).filter_by(id=region_id, cloud_id=cloud_id).first()
            vpc_network = \
                db_session.query(IBMVpcNetwork).filter_by(
                    resource_id=network_acl_json["vpc"]["id"], cloud_id=cloud_id).first()
            resource_group = \
                db_session.query(IBMResourceGroup).filter_by(
                    resource_id=network_acl_json["resource_group"]["id"], cloud_id=cloud_id).first()

            if not (region and vpc_network and resource_group):
                workflow_task.status = WorkflowTask.STATUS_FAILED
                workflow_task.message = \
                    "Creation Successful but record update failed. The records will update next time discovery runs"
                db_session.commit()
                LOGGER.note(workflow_task.message)

            network_acl = IBMNetworkAcl.from_ibm_json_body(json_body=network_acl_json)
            network_acl.vpc_network = vpc_network
            network_acl.region = region
            network_acl.resource_group = resource_group
            db_session.commit()

        workflow_task.status = WorkflowTask.STATUS_SUCCESSFUL
        network_acl_json = network_acl.to_json()
        network_acl_json["created_at"] = str(network_acl_json["created_at"])

        IBMResourceLog(
            resource_id=network_acl.resource_id, region=network_acl.region,
            status=IBMResourceLog.STATUS_ADDED, resource_type=IBMNetworkAcl.__name__,
            data=network_acl_json)

        workflow_task.resource_id = network_acl.id
        db_session.commit()

    LOGGER.success(f"IBM Network Acl '{network_acl_json['name']}' creation for cloud '{cloud_id}' successful")


@celery.task(name="create_network_acl_rule", base=IBMWorkflowTasksBase)
def create_network_acl_rule(workflow_task_id):
    """
    Create an IBM Network Acl Rule on IBM Cloud
    """
    with get_db_session() as db_session:
        workflow_task = db_session.query(WorkflowTask).filter_by(id=workflow_task_id).first()
        if not workflow_task:
            return

        workflow_task.status = WorkflowTask.STATUS_RUNNING
        db_session.commit()

        resource_data = deepcopy(workflow_task.task_metadata["resource_data"])
        resource_json = deepcopy(resource_data["resource_json"])
        cloud_id = resource_data["ibm_cloud"]["id"]
        network_acl_id = resource_data["network_acl"]["id"]

        network_acl = db_session.query(IBMNetworkAcl).filter_by(id=network_acl_id,
                                                                cloud_id=cloud_id).first()
        if not network_acl:
            workflow_task.status = WorkflowTask.STATUS_FAILED
            workflow_task.message = f"IBM Network Acl with id: '{network_acl_id}' not found"
            db_session.commit()
            LOGGER.error(workflow_task.message)
            return

        previous_resources = load_previous_associated_resources(task=workflow_task, session=db_session)
        update_id_or_name_references(
            cloud_id=cloud_id, resource_json=resource_data, resource_schema=IBMAclRuleInSchema,
            db_session=db_session, previous_resources=previous_resources
        )

        update_id_or_name_references(
            cloud_id=cloud_id, resource_json=resource_json, resource_schema=IBMAclRuleResourceSchema,
            db_session=db_session, previous_resources=previous_resources
        )

        region_name = network_acl.region.name
        network_acl_resource_id = network_acl.resource_id

    try:
        client = NetworkACLsClient(cloud_id=cloud_id, region=region_name)
        network_acl_rule_json = client.create_network_acl_rule(network_acl_id=network_acl_resource_id,
                                                               network_acl_rule_json=resource_json)
    except ApiException as ex:
        with get_db_session() as db_session:
            workflow_task = db_session.query(WorkflowTask).filter_by(id=workflow_task_id).first()
            if not workflow_task:
                return

            workflow_task.status = WorkflowTask.STATUS_FAILED
            workflow_task.message = f"Creation Failed. Reason: {str(ex.message)}"
            db_session.commit()
            LOGGER.fail(workflow_task.message)
            return

    with get_db_session() as db_session:
        workflow_task = db_session.query(WorkflowTask).filter_by(id=workflow_task_id).first()
        if not workflow_task:
            return

        with db_session.no_autoflush:
            network_acl = db_session.query(IBMNetworkAcl).filter_by(id=network_acl_id,
                                                                    cloud_id=cloud_id).first()
            if not network_acl:
                workflow_task.status = WorkflowTask.STATUS_FAILED
                workflow_task.message = \
                    "Creation Successful but record update failed. The records will update next time discovery runs"
                db_session.commit()
                LOGGER.note(workflow_task.message)
                return

            network_acl_rule = IBMNetworkAclRule.from_ibm_json_body(json_body=network_acl_rule_json)
            network_acl_rule.network_acl = network_acl
            db_session.commit()

        workflow_task.status = WorkflowTask.STATUS_SUCCESSFUL
        IBMResourceLog(
            resource_id=network_acl_rule.resource_id, region=network_acl_rule.network_acl.region,
            status=IBMResourceLog.STATUS_ADDED, resource_type=IBMNetworkAclRule.__name__,
            data=network_acl_rule.to_json())
        workflow_task.resource_id = network_acl_rule.id
        db_session.commit()

    LOGGER.success(
        f"IBM Network Acl Rule with id '{network_acl_rule_json['id']}' creation for cloud '{cloud_id}' successful")


@celery.task(name="delete_network_acl", base=IBMWorkflowTasksBase)
def delete_network_acl(workflow_task_id):
    """
    Delete an IBM Network Acl
    :param workflow_task_id:
    :return:
    """

    with get_db_session() as db_session:
        workflow_task: WorkflowTask = db_session.query(WorkflowTask).filter_by(id=workflow_task_id).first()
        if not workflow_task:
            return

        workflow_task.status = WorkflowTask.STATUS_RUNNING
        db_session.commit()

        network_acl: IBMNetworkAcl = db_session.query(IBMNetworkAcl).filter_by(id=workflow_task.resource_id).first()
        if not network_acl:
            workflow_task.status = WorkflowTask.STATUS_FAILED
            workflow_task.message = f"IBM Network Acl '{workflow_task.resource_id}' not found"
            db_session.commit()
            LOGGER.error(workflow_task.message)
            return

        region_name = network_acl.region.name
        network_acl_resource_id = network_acl.resource_id
        cloud_id = network_acl.cloud_id
        network_acl_name = network_acl.name
    try:

        network_acl_client = NetworkACLsClient(cloud_id, region=region_name)
        network_acl_client.delete_network_acl(network_acl_resource_id)

    except ApiException as ex:
        with get_db_session() as db_session:
            workflow_task = db_session.query(WorkflowTask).filter_by(id=workflow_task_id).first()
            if not workflow_task:
                return

            if ex.code == 404:  # 404 means resource is not found on IBM Cloud.
                network_acl: IBMNetworkAcl = db_session.query(IBMNetworkAcl).filter_by(
                    id=workflow_task.resource_id).first()
                if network_acl:
                    db_session.delete(network_acl)

                workflow_task.status = WorkflowTask.STATUS_SUCCESSFUL
                workflow_task.resource_id = network_acl.id

                network_acl_json = network_acl.to_json()
                network_acl_json["created_at"] = str(network_acl_json["created_at"])

                IBMResourceLog(
                    resource_id=network_acl.resource_id, region=network_acl.region,
                    status=IBMResourceLog.STATUS_DELETED, resource_type=IBMNetworkAcl.__name__,
                    data=network_acl_json)

                LOGGER.success(f"IBM Network ACL {network_acl_name} for cloud {cloud_id} deletion successful.")
                db_session.commit()
                return

            else:
                workflow_task.status = WorkflowTask.STATUS_FAILED
                message = f"IBM Network ACL {workflow_task.resource_id} deletion failed. Reason: {str(ex.message)}"
                workflow_task.message = message
                db_session.commit()
                LOGGER.fail(workflow_task.message)
                return

    with get_db_session() as db_session:
        workflow_task: WorkflowTask = db_session.query(WorkflowTask).filter_by(id=workflow_task_id).first()
        if not workflow_task:
            return

        network_acl: IBMNetworkAcl = db_session.query(IBMNetworkAcl).filter_by(id=workflow_task.resource_id).first()
        if network_acl:
            db_session.delete(network_acl)

        workflow_task.status = WorkflowTask.STATUS_SUCCESSFUL
        workflow_task.resource_id = network_acl.id

        network_acl_json = network_acl.to_json()
        network_acl_json["created_at"] = str(network_acl_json["created_at"])

        IBMResourceLog(
            resource_id=network_acl.resource_id, region=network_acl.region,
            status=IBMResourceLog.STATUS_DELETED, resource_type=IBMNetworkAcl.__name__,
            data=network_acl_json)
        db_session.commit()
        LOGGER.info(f"IBM Network ACL {network_acl_name} for cloud {cloud_id} deletion successful.")


@celery.task(name="delete_network_acl_rule", base=IBMWorkflowTasksBase)
def delete_network_acl_rule(workflow_task_id):
    """
    Delete an IBM Network Acl Rule
    :param workflow_task_id:
    :return:
    """

    with get_db_session() as db_session:
        workflow_task: WorkflowTask = db_session.query(WorkflowTask).filter_by(id=workflow_task_id).first()

        if not workflow_task:
            return

        workflow_task.status = WorkflowTask.STATUS_RUNNING
        db_session.commit()

        network_acl_rule: IBMNetworkAclRule = db_session.query(
            IBMNetworkAclRule).filter_by(id=workflow_task.resource_id).first()
        if not network_acl_rule:
            workflow_task.status = WorkflowTask.STATUS_FAILED
            workflow_task.message = f"IBM Network Acl Rule '{workflow_task.resource_id}' not found"
            db_session.commit()
            LOGGER.error(workflow_task.message)
            return

        region_name = network_acl_rule.network_acl.region.name
        network_acl_rule_resource_id = network_acl_rule.resource_id
        network_acl_resource_id = network_acl_rule.network_acl.resource_id
        cloud_id = network_acl_rule.network_acl.cloud_id
        network_acl_rule_name = network_acl_rule.name
    try:
        network_acl_client = NetworkACLsClient(cloud_id, region=region_name)
        network_acl_client.delete_network_acl_rule(network_acl_id=network_acl_resource_id,
                                                   network_acl_rule_id=network_acl_rule_resource_id)
    except ApiException as ex:
        with get_db_session() as db_session:
            workflow_task: WorkflowTask = db_session.query(WorkflowTask).filter_by(id=workflow_task_id).first()
            if not workflow_task:
                return

            if ex.code == 404:  # 404 means resource is not found on IBM Cloud.
                network_acl_rule: IBMNetworkAclRule = db_session.query(IBMNetworkAclRule).filter_by(
                    id=workflow_task.resource_id).first()
                if network_acl_rule:
                    db_session.delete(network_acl_rule)

                workflow_task.status = WorkflowTask.STATUS_SUCCESSFUL
                workflow_task.resource_id = network_acl_rule.id
                IBMResourceLog(
                    resource_id=network_acl_rule.resource_id, region=network_acl_rule.network_acl.region,
                    status=IBMResourceLog.STATUS_DELETED, resource_type=IBMNetworkAclRule.__name__,
                    data=network_acl_rule.to_json())
                LOGGER.success(
                    f"IBM Network Acl Rule {network_acl_rule_name} for cloud {cloud_id} deletion successful.")
                db_session.commit()
                return
            else:
                workflow_task.status = WorkflowTask.STATUS_FAILED
                message = f"IBM Network Acl Rule {workflow_task.resource_id} deletion failed. Reason: {str(ex.message)}"
                workflow_task.message = message
                db_session.commit()
                LOGGER.fail(message)
                return

    with get_db_session() as db_session:
        workflow_task: WorkflowTask = db_session.query(WorkflowTask).filter_by(id=workflow_task_id).first()
        if not workflow_task:
            return

        network_acl_rule: IBMNetworkAclRule = db_session.query(IBMNetworkAclRule).filter_by(
            id=workflow_task.resource_id).first()
        if network_acl_rule:
            db_session.delete(network_acl_rule)

        workflow_task.status = WorkflowTask.STATUS_SUCCESSFUL
        workflow_task.resource_id = network_acl_rule.id

        network_acl_rule_json = network_acl_rule.to_json()
        network_acl_rule_json["created_at"] = str(network_acl_rule_json["created_at"])

        IBMResourceLog(
            resource_id=network_acl_rule.resource_id, region=network_acl_rule.network_acl.region,
            status=IBMResourceLog.STATUS_DELETED, resource_type=IBMNetworkAclRule.__name__,
            data=network_acl_rule_json)

        db_session.commit()
        LOGGER.success(f"IBM Network Acl Rule {network_acl_rule_name} for cloud {cloud_id} deletion successful.")
