import logging
from copy import deepcopy
from ibm_cloud_sdk_core import ApiException

from ibm import get_db_session
from ibm.common.clients.ibm_clients import SecurityGroupsClient
from ibm.common.utils import update_id_or_name_references
from ibm.models import IBMEndpointGateway, IBMLoadBalancer, IBMNetworkInterface, IBMRegion, IBMResourceGroup, \
    IBMResourceLog, IBMSecurityGroup, IBMSecurityGroupRule, IBMVpcNetwork, WorkflowTask
from ibm.tasks.celery_app import celery_app as celery
from ibm.tasks.common.tasks_base import IBMWorkflowTasksBase
from ibm.tasks.ibm.task_utils import load_previous_associated_resources
from ibm.web.ibm.security_groups.schemas import IBMSecurityGroupInSchema, IBMSecurityGroupResourceSchema, \
    IBMSecurityGroupRuleInSchema, IBMSecurityGroupRuleResourceSchema, SecurityGroupRuleRemoteSchema

LOGGER = logging.getLogger(__name__)


@celery.task(name="create_security_group", base=IBMWorkflowTasksBase)
def create_security_group(workflow_task_id):
    """
    Create an IBM Security Group on IBM Cloud
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
            LOGGER.info(workflow_task.message)
            return

        if region.ibm_status == IBMRegion.IBM_STATUS_UNAVAILABLE:
            workflow_task.status = WorkflowTask.STATUS_FAILED
            workflow_task.message = f"IBMRegion '{region.name}' unavailable"
            db_session.commit()
            LOGGER.info(workflow_task.message)
            return

        region_name = region.name
        resource_json.pop('target', None)

        previous_resources = load_previous_associated_resources(task=workflow_task, session=db_session)
        update_id_or_name_references(
            cloud_id=cloud_id, resource_json=resource_data, resource_schema=IBMSecurityGroupInSchema,
            db_session=db_session, previous_resources=previous_resources
        )
        update_id_or_name_references(
            cloud_id=cloud_id, resource_json=resource_json, resource_schema=IBMSecurityGroupResourceSchema,
            db_session=db_session, previous_resources=previous_resources
        )
        for rule in resource_json.get("rules", []):
            update_id_or_name_references(
                cloud_id=cloud_id, resource_json=rule, previous_resources=previous_resources,
                resource_schema=IBMSecurityGroupRuleResourceSchema, db_session=db_session
            )
            if "id" in rule:
                del rule["id"]

            if rule.get("remote"):
                update_id_or_name_references(
                    cloud_id=cloud_id, resource_json=rule["remote"], previous_resources=previous_resources,
                    resource_schema=SecurityGroupRuleRemoteSchema, db_session=db_session
                )
            if rule.get("remote") and rule["remote"].get("security_group"):
                rule["remote"] = rule["remote"]["security_group"]
                rule["remote"].pop('security_group', None)

        resource_json.pop("region")

    try:
        client = SecurityGroupsClient(cloud_id=cloud_id, region=region_name)
        security_group_json = client.create_security_group(security_group_json=resource_json)
    except ApiException as ex:
        with get_db_session() as db_session:
            workflow_task = db_session.query(WorkflowTask).filter_by(id=workflow_task_id).first()
            if not workflow_task:
                return

            workflow_task.status = WorkflowTask.STATUS_FAILED
            workflow_task.message = f"Creation Failed. Reason: {str(ex.message)}"
            db_session.commit()

        LOGGER.info("Create Security Group failed with status code " + str(ex.code) + ": " + ex.message)
        return

    with get_db_session() as db_session:
        workflow_task = db_session.query(WorkflowTask).filter_by(id=workflow_task_id).first()
        if not workflow_task:
            return

        metadata = workflow_task.task_metadata.copy() if workflow_task.task_metadata else {}
        metadata["ibm_resource_id"] = security_group_json["id"]

        workflow_task.task_metadata = metadata
        with db_session.no_autoflush:
            resource_group = db_session.query(IBMResourceGroup).filter_by(
                resource_id=security_group_json["resource_group"]["id"], cloud_id=cloud_id).first()

            vpc_network = db_session.query(IBMVpcNetwork).filter_by(
                resource_id=security_group_json["vpc"]["id"], cloud_id=cloud_id).first()

            region = db_session.query(IBMRegion).filter_by(
                id=resource_data["region"]["id"], cloud_id=cloud_id).first()

            if not (resource_group and vpc_network and region):
                workflow_task.status = WorkflowTask.STATUS_FAILED
                workflow_task.message = \
                    "Creation Successful but record update failed. The records will update next time discovery runs"
                db_session.commit()
                LOGGER.info(workflow_task.message)
                return

            security_group = IBMSecurityGroup.from_ibm_json_body(json_body=security_group_json)
            for target in security_group_json.get("targets", []):
                if target.get("resource_type") == IBMNetworkInterface.TYPE_NETWORK_INTERFACE:
                    network_interface = db_session.query(IBMNetworkInterface).filter_by(
                        resource_id=target["id"], cloud_id=cloud_id).first()
                else:
                    load_balancer = db_session.query(IBMLoadBalancer).filter_by(
                        resource_id=target["id"], cloud_id=cloud_id).first()

                if not (network_interface and load_balancer):
                    workflow_task.status = WorkflowTask.STATUS_FAILED
                    workflow_task.message = \
                        "Creation Successful but record update failed. The records will " \
                        "update next time discovery runs"
                    db_session.commit()
                    LOGGER.info(workflow_task.message)
                    return

                if target.get("resource_type") == IBMNetworkInterface.TYPE_NETWORK_INTERFACE:
                    security_group.network_interfaces.append(network_interface)
                else:
                    security_group.load_balancers.append(load_balancer)

            security_group.region = region
            security_group.resource_group = resource_group
            security_group.vpc_network = vpc_network
            db_session.commit()

        workflow_task.resource_id = security_group.id

        security_group_json = security_group.to_json()
        security_group_json["created_at"] = str(security_group_json["created_at"])

        IBMResourceLog(
            resource_id=security_group.resource_id, region=security_group.region,
            status=IBMResourceLog.STATUS_ADDED, resource_type=IBMSecurityGroup.__name__,
            data=security_group_json)

        workflow_task.status = WorkflowTask.STATUS_SUCCESSFUL
        message = f"IBM Security Group '{security_group_json['name']}' creation for cloud '{cloud_id}' successful"
        db_session.commit()

    LOGGER.info(message)


@celery.task(name="create_security_group_rule", base=IBMWorkflowTasksBase)
def create_security_group_rule(workflow_task_id):
    """
    Create an IBM Security Group Rule for a Security Group on IBM Cloud
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
        security_group_id = resource_data["security_group"]["id"]

        security_group = db_session.query(IBMSecurityGroup).filter_by(id=security_group_id,
                                                                      cloud_id=cloud_id).first()
        if not security_group:
            workflow_task.status = WorkflowTask.STATUS_FAILED
            workflow_task.message = f"IBM Security Group with id: '{security_group_id}' not found"
            db_session.commit()
            LOGGER.info(workflow_task.message)
            return

        region_name = security_group.region.name
        previous_resources = load_previous_associated_resources(task=workflow_task, session=db_session)
        update_id_or_name_references(
            cloud_id=cloud_id, resource_json=resource_data, resource_schema=IBMSecurityGroupRuleInSchema,
            db_session=db_session, previous_resources=previous_resources
        )
        update_id_or_name_references(
            cloud_id=cloud_id, resource_json=resource_json, resource_schema=IBMSecurityGroupRuleResourceSchema,
            db_session=db_session, previous_resources=previous_resources
        )
        update_id_or_name_references(
            cloud_id=cloud_id, resource_json=resource_json["remote"], resource_schema=SecurityGroupRuleRemoteSchema,
            db_session=db_session, previous_resources=previous_resources
        )
        if resource_json["remote"].get("security_group"):
            resource_json["remote"]["id"] = resource_json["remote"]["security_group"]["id"]

    try:
        client = SecurityGroupsClient(cloud_id=cloud_id, region=region_name)
        security_group_rule_json = client.create_security_group_rule(
            security_group_id=security_group.resource_id, rule_json=resource_json)
    except ApiException as ex:
        with get_db_session() as db_session:
            workflow_task = db_session.query(WorkflowTask).filter_by(id=workflow_task_id).first()
            if not workflow_task:
                return

            workflow_task.status = WorkflowTask.STATUS_FAILED
            workflow_task.message = f"Creation Failed. Reason: {str(ex.message)}"
            db_session.commit()

        LOGGER.info("Create Security Group Rule failed with status code " + str(ex.code) + ": " + ex.message)
        return

    with get_db_session() as db_session:
        workflow_task = db_session.query(WorkflowTask).filter_by(id=workflow_task_id).first()
        if not workflow_task:
            return

        metadata = workflow_task.task_metadata.copy() if workflow_task.task_metadata else {}
        metadata["ibm_resource_id"] = security_group_rule_json["id"]
        workflow_task.task_metadata = metadata
        with db_session.no_autoflush:
            security_group = db_session.query(IBMSecurityGroup).filter_by(id=security_group_id,
                                                                          cloud_id=cloud_id).first()
            if not security_group:
                workflow_task.status = WorkflowTask.STATUS_FAILED
                workflow_task.message = \
                    "Creation Successful but record update failed. The records will update next time discovery runs"
                db_session.commit()
                LOGGER.info(workflow_task.message)
                return

            if security_group_rule_json["remote"].get("id"):
                remote_security_group = db_session.query(IBMSecurityGroup).filter_by(id=security_group_id,
                                                                                     cloud_id=cloud_id).first()
                if not remote_security_group:
                    workflow_task.status = WorkflowTask.STATUS_FAILED
                    workflow_task.message = \
                        "Creation Successful but record update failed. The records will update next time discovery " \
                        "runs"
                    db_session.commit()
                    LOGGER.info(workflow_task.message)
                    return

            security_group_rule = IBMSecurityGroupRule.from_ibm_json_body(json_body=security_group_rule_json)
            security_group_rule.security_group = security_group
            if security_group_rule_json["remote"].get("id"):
                security_group_rule.remote_security_group = remote_security_group

            db_session.commit()

        workflow_task.status = WorkflowTask.STATUS_SUCCESSFUL
        workflow_task.resource_id = security_group_rule.id
        message = f"IBM Security Group Rule with id '{security_group_rule_json['id']}' " \
                  f"creation for cloud '{cloud_id}' successful"
        db_session.commit()

    LOGGER.info(message)


@celery.task(name="attach_target_to_security_group", base=IBMWorkflowTasksBase)
def attach_target_to_security_group(workflow_task_id):
    """
    Attach a Target (Load Balancer or Network Interface) to IBM Security Group on IBM Cloud
    """
    with get_db_session() as db_session:
        workflow_task = db_session.query(WorkflowTask).filter_by(id=workflow_task_id).first()
        if not workflow_task:
            return

        workflow_task.status = WorkflowTask.STATUS_RUNNING
        db_session.commit()

        task_metadata = deepcopy(workflow_task.task_metadata)
        resource_data = deepcopy(task_metadata["resource_data"])
        security_group_r_json = resource_data["security_group"]
        region_id = resource_data["region"]["id"]

        region = db_session.query(IBMRegion).filter_by(id=region_id).first()
        if not region:
            workflow_task.status = WorkflowTask.STATUS_FAILED
            workflow_task.message = f"IBMRegion '{region_id}' not found"
            db_session.commit()
            LOGGER.info(workflow_task.message)
            return

        if region.ibm_status == IBMRegion.IBM_STATUS_UNAVAILABLE:
            workflow_task.status = WorkflowTask.STATUS_FAILED
            workflow_task.message = f"IBMRegion '{region.name}' unavailable"
            db_session.commit()
            LOGGER.info(workflow_task.message)
            return

        security_group = db_session.query(IBMSecurityGroup).filter_by(
            **security_group_r_json, region_id=region_id).first()

        sec_grp_id_or_name = security_group_r_json.get("id") or security_group_r_json.get("name")
        if not security_group:
            workflow_task.status = WorkflowTask.STATUS_FAILED
            workflow_task.message = f"IBM Security group with '{sec_grp_id_or_name}' not found"
            db_session.commit()
            LOGGER.info(workflow_task.message)
            return

        security_group_vpc_subnetworks = security_group.vpc_network.subnets.all()

        if resource_data.get("network_interface"):
            target = db_session.query(IBMNetworkInterface).filter_by(**resource_data["network_interface"]).first()
        elif resource_data.get("load_balancer"):
            target = db_session.query(IBMNetworkInterface).filter_by(**resource_data["load_balancer"]).first()
        elif resource_data.get("endpoint_gateway"):
            target = db_session.query(IBMEndpointGateway).filter_by(**resource_data["endpoint_gateway"]).first()

        sec_grp_target = resource_data.get("network_interface") or resource_data.get(
            "load_balancer") or resource_data.get("endpoint_gateway")
        if not target:
            workflow_task.status = WorkflowTask.STATUS_FAILED
            workflow_task.message = f"IBMTarget with ID  '{sec_grp_target['id']}' not found"
            db_session.commit()
            LOGGER.info(workflow_task.message)
            return

        if hasattr(target, 'subnet') and target.subnet not in security_group_vpc_subnetworks:
            workflow_task.status = WorkflowTask.STATUS_FAILED
            workflow_task.message = \
                f"Target with ID '{sec_grp_target['id']}' not attached to Security Group's VPC."
            db_session.commit()
            LOGGER.info(workflow_task.message)
            return

        cloud_id = target.cloud_id
        security_group_resource_id = security_group.resource_id
        target_resource_id = target.resource_id
        region_name = region.name

    try:
        client = SecurityGroupsClient(cloud_id=cloud_id, region=region_name)
        sg_target_resource_json = client.add_security_group_target(security_group_id=security_group_resource_id,
                                                                   target_id=target_resource_id)
    except ApiException as ex:
        with get_db_session() as db_session:
            workflow_task = db_session.query(WorkflowTask).filter_by(id=workflow_task_id).first()
            if not workflow_task:
                return

            workflow_task.status = WorkflowTask.STATUS_FAILED
            workflow_task.message = f"Attach Failed. Reason: {str(ex.message)}"
            db_session.commit()

        LOGGER.info("Attach Security Group Target failed with status code " + str(ex.code) + ": " + ex.message)
        return

    with get_db_session() as db_session:
        workflow_task = db_session.query(WorkflowTask).filter_by(id=workflow_task_id).first()
        if not workflow_task:
            return

        target_resource_id = sg_target_resource_json["id"]
        target_type = sg_target_resource_json["resource_type"]
        if target_type == IBMNetworkInterface.TYPE_NETWORK_INTERFACE:
            target = db_session.query(IBMNetworkInterface).filter_by(resource_id=target_resource_id).first()
        elif target_type == IBMEndpointGateway.RESOURCE_TYPE_ENDPOINT_GATEWAY:
            target = db_session.query(IBMEndpointGateway).filter_by(resource_id=target_resource_id).first()
        elif target_type == IBMLoadBalancer.RESOURCE_TYPE_LOAD_BALANCER:
            target = db_session.query(IBMLoadBalancer).filter_by(resource_id=target_resource_id).first()

        if not target:
            workflow_task.status = WorkflowTask.STATUS_FAILED
            workflow_task.message = \
                "Creation Successful but record update failed. The records will update next time discovery runs"
            db_session.commit()
            LOGGER.info(workflow_task.message)
            return

        security_group = db_session.query(IBMSecurityGroup).filter_by(
            **security_group_r_json, region_id=region_id, cloud_id=cloud_id).first()

        if not security_group:
            workflow_task.status = WorkflowTask.STATUS_FAILED
            workflow_task.message = f"IBM Security group with '{sec_grp_id_or_name}' not found"
            db_session.commit()
            LOGGER.info(workflow_task.message)
            return

        if target_type == IBMNetworkInterface.TYPE_NETWORK_INTERFACE:
            security_group.network_interfaces.append(target)
        elif target_type == IBMLoadBalancer.RESOURCE_TYPE_LOAD_BALANCER:
            security_group.load_balancers.append(target)
        elif target_type == IBMEndpointGateway.RESOURCE_TYPE_ENDPOINT_GATEWAY:
            security_group.endpoint_gateways.append(target)

        db_session.commit()
        workflow_task.resource_id = security_group.id

        workflow_task.status = WorkflowTask.STATUS_SUCCESSFUL
        db_session.commit()

    LOGGER.info(
        f"IBM Security Group {security_group_resource_id} attached with target with resource id "
        f"'{sg_target_resource_json['id']}'")


@celery.task(name="detach_target_to_security_group", base=IBMWorkflowTasksBase)
def detach_target_to_security_group(workflow_task_id):
    """
    Detach a Target (Load Balancer or Network Interface) from IBM Security Group on IBM Cloud
    """
    with get_db_session() as db_session:
        workflow_task = db_session.query(WorkflowTask).filter_by(id=workflow_task_id).first()
        if not workflow_task:
            return

        workflow_task.status = WorkflowTask.STATUS_RUNNING
        db_session.commit()

        task_metadata = deepcopy(workflow_task.task_metadata)
        resource_data = deepcopy(task_metadata["resource_data"])
        security_group = resource_data["security_group"]
        region_id = resource_data["region"]["id"]

        region = db_session.query(IBMRegion).filter_by(id=region_id).first()
        if not region:
            workflow_task.status = WorkflowTask.STATUS_FAILED
            workflow_task.message = f"IBMRegion '{region_id}' not found"
            db_session.commit()
            LOGGER.info(workflow_task.message)
            return

        if region.ibm_status == IBMRegion.IBM_STATUS_UNAVAILABLE:
            workflow_task.status = WorkflowTask.STATUS_FAILED
            workflow_task.message = f"IBMRegion '{region.name}' unavailable"
            db_session.commit()
            LOGGER.info(workflow_task.message)
            return

        security_group = db_session.query(IBMSecurityGroup).filter_by(
            **security_group, region_id=region_id).first()

        if not security_group:
            workflow_task.status = WorkflowTask.STATUS_FAILED
            workflow_task.message = f"IBM Security group with name " \
                                    f"'{security_group.get('id') or security_group.get('name')}' not found"
            db_session.commit()
            LOGGER.info(workflow_task.message)
            return

        security_group_vpc_subnetworks = security_group.vpc_network.subnets.all()

        if resource_data.get("network_interface"):
            target = db_session.query(IBMNetworkInterface).filter_by(**resource_data["network_interface"]).first()
        elif resource_data.get("load_balancer"):
            target = db_session.query(IBMNetworkInterface).filter_by(**resource_data["load_balancer"]).first()
        elif resource_data.get("endpoint_gateway"):
            target = db_session.query(IBMEndpointGateway).filter_by(**resource_data["endpoint_gateway"]).first()

        if not target:
            workflow_task.status = WorkflowTask.STATUS_FAILED
            workflow_task.message = f"IBMTarget " \
                                    f"{resource_data.get('network_interface') or resource_data.get('load_balancer')} " \
                                    f"not found"
            db_session.commit()
            LOGGER.info(workflow_task.message)
            return

        if hasattr(target, 'subnet') and target.subnet not in security_group_vpc_subnetworks:
            workflow_task.status = WorkflowTask.STATUS_FAILED
            workflow_task.message = \
                f"IBMTarget " \
                f"{resource_data.get('network_interface')['id'] or resource_data.get('load_balancer')['id']}" \
                f"not attached to security group VPC."
            db_session.commit()
            LOGGER.info(workflow_task.message)
            return

        cloud_id = target.cloud_id
        security_group_resource_id = security_group.resource_id
        target_resource_id = target.resource_id
        target_resource_type = target.resource_type
        region_name = region.name

    try:
        client = SecurityGroupsClient(cloud_id=cloud_id, region=region_name)
        client.delete_security_group_target(security_group_id=security_group_resource_id, target_id=target_resource_id)
    except ApiException as ex:
        with get_db_session() as db_session:
            workflow_task = db_session.query(WorkflowTask).filter_by(id=workflow_task_id).first()
            if not workflow_task:
                return

            workflow_task.status = WorkflowTask.STATUS_FAILED
            workflow_task.message = f"Detaching Failed. Reason: {str(ex.message)}"
            db_session.commit()

        LOGGER.info("Detach Security Group Target failed with status code " + str(ex.code) + ": " + ex.message)
        return

    with get_db_session() as db_session:
        workflow_task = db_session.query(WorkflowTask).filter_by(id=workflow_task_id).first()
        if not workflow_task:
            return

        security_group = db_session.query(IBMSecurityGroup).filter_by(
            **security_group, region_id=region_id, cloud_id=cloud_id).first()

        if not security_group:
            workflow_task.status = WorkflowTask.STATUS_FAILED
            workflow_task.message = f"IBM Security group with name " \
                                    f"'{security_group.get('id') or security_group.get('name')}' not found"
            db_session.commit()
            LOGGER.info(workflow_task.message)
            return

        if target_resource_type == IBMNetworkInterface.TYPE_NETWORK_INTERFACE:
            security_group.network_interface = None
        else:
            security_group.load_balancer = None

        workflow_task.resource_id = security_group.id
        workflow_task.status = WorkflowTask.STATUS_SUCCESSFUL
        db_session.commit()

    LOGGER.info(
        f"IBM Security Group {security_group_resource_id} detached with target with resource id "
        f"'{target_resource_id}'")


@celery.task(name="delete_security_group", base=IBMWorkflowTasksBase)
def delete_security_group(workflow_task_id):
    """
    Delete an IBM Security Group on IBM Cloud
    """
    with get_db_session() as db_session:
        workflow_task: WorkflowTask = db_session.query(WorkflowTask).filter_by(id=workflow_task_id).first()
        if not workflow_task:
            return

        workflow_task.status = WorkflowTask.STATUS_RUNNING
        db_session.commit()

        security_group: IBMSecurityGroup = db_session.query(IBMSecurityGroup).filter_by(id=workflow_task.resource_id) \
            .first()
        if not security_group:
            workflow_task.status = WorkflowTask.STATUS_FAILED
            workflow_task.message = f"IBM Security Group '{workflow_task.resource_id}' not found"
            db_session.commit()
            LOGGER.info(workflow_task.message)
            return

        region_name = security_group.region.name
        security_group_resource_id = security_group.resource_id
        cloud_id = security_group.cloud_id

    try:
        client = SecurityGroupsClient(cloud_id, region=region_name)
        client.delete_security_group(security_group_id=security_group_resource_id)
    except ApiException as ex:
        with get_db_session() as db_session:
            workflow_task: WorkflowTask = db_session.query(WorkflowTask).filter_by(id=workflow_task_id).first()
            if not workflow_task:
                return

            if ex.code == 404:
                security_group: IBMSecurityGroup = db_session.query(IBMSecurityGroup). \
                    filter_by(id=workflow_task.resource_id).first()
                if security_group:
                    security_group_json = security_group.to_json()
                    security_group_json["created_at"] = str(security_group_json["created_at"])

                    IBMResourceLog(
                        resource_id=security_group.resource_id, region=security_group.region,
                        status=IBMResourceLog.STATUS_DELETED, resource_type=IBMSecurityGroup.__name__,
                        data=security_group_json)

                    db_session.delete(security_group)

                workflow_task.status = WorkflowTask.STATUS_SUCCESSFUL
                db_session.commit()
                LOGGER.info(
                    f"IBM Security Group {security_group_resource_id} for cloud {cloud_id} deletion successful.")
                return
            else:
                workflow_task.status = WorkflowTask.STATUS_FAILED
                workflow_task.message = str(ex.message)
                db_session.commit()
                LOGGER.info(str(ex.message))
                return

    with get_db_session() as db_session:
        workflow_task: WorkflowTask = db_session.query(WorkflowTask).filter_by(id=workflow_task_id).first()
        if not workflow_task:
            return

        security_group: IBMSecurityGroup = db_session.query(IBMSecurityGroup) \
            .filter_by(id=workflow_task.resource_id).first()
        if security_group:
            db_session.delete(security_group)

        workflow_task.status = WorkflowTask.STATUS_SUCCESSFUL
        message = f"IBM Security Group {security_group_resource_id} for cloud {cloud_id} " \
                  f"deletion successful."
        db_session.commit()

    LOGGER.info(message)


@celery.task(name="delete_security_group_rule", base=IBMWorkflowTasksBase)
def delete_security_group_rule(workflow_task_id):
    """
    Delete an IBM Security Group Rule for a Security Group on IBM Cloud
    """
    with get_db_session() as db_session:
        workflow_task: WorkflowTask = db_session.query(WorkflowTask).filter_by(id=workflow_task_id).first()
        if not workflow_task:
            return

        workflow_task.status = WorkflowTask.STATUS_RUNNING
        db_session.commit()

        security_group_rule: IBMSecurityGroupRule = db_session.query(IBMSecurityGroupRule). \
            filter_by(id=workflow_task.resource_id).first()
        if not security_group_rule:
            workflow_task.status = WorkflowTask.STATUS_FAILED
            workflow_task.message = f"IBM Security Group Rule'{workflow_task.resource_id}' not found"
            db_session.commit()
            LOGGER.info(workflow_task.message)
            return

        region_name = security_group_rule.security_group.region.name
        security_group_rule_resource_id = security_group_rule.resource_id
        security_group_resource_id = security_group_rule.security_group.resource_id
        cloud_id = security_group_rule.security_group.ibm_cloud.id

    try:
        client = SecurityGroupsClient(cloud_id, region=region_name)
        client.delete_security_group_rules(security_group_id=security_group_resource_id,
                                           rule_id=security_group_rule_resource_id)

    except ApiException as ex:
        with get_db_session() as db_session:
            workflow_task: WorkflowTask = db_session.query(WorkflowTask).filter_by(id=workflow_task_id).first()
            if not workflow_task:
                return

            if ex.code == 404:
                security_group_rule: IBMSecurityGroupRule = \
                    db_session.query(IBMSecurityGroupRule).filter_by(id=workflow_task.resource_id).first()
                if security_group_rule:
                    security_group_rule_json = security_group_rule.to_json()
                    security_group_rule_json["created_at"] = str(security_group_rule_json["created_at"])

                    IBMResourceLog(
                        resource_id=security_group_rule.resource_id, region=security_group_rule.security_group.region,
                        status=IBMResourceLog.STATUS_DELETED, resource_type=IBMSecurityGroupRule.__name__,
                        data=security_group_rule_json)

                    db_session.delete(security_group_rule)

                workflow_task.status = WorkflowTask.STATUS_SUCCESSFUL
                LOGGER.info(f"IBM Security Group Rule {security_group_rule_resource_id} "
                            f"for cloud {cloud_id} deletion successful.")
                db_session.commit()
                return
            else:
                workflow_task.status = WorkflowTask.STATUS_FAILED
                workflow_task.message = str(ex.message)
                db_session.commit()
                LOGGER.info(str(ex.message))
                return

    with get_db_session() as db_session:
        workflow_task: WorkflowTask = db_session.query(WorkflowTask).filter_by(id=workflow_task_id).first()
        if not workflow_task:
            return

        security_group_rule: IBMSecurityGroupRule = \
            db_session.query(IBMSecurityGroupRule).filter_by(id=workflow_task.resource_id).first()
        if security_group_rule:
            db_session.delete(security_group_rule)

        workflow_task.status = WorkflowTask.STATUS_SUCCESSFUL
        message = f"IBM Security Group Rule {security_group_rule_resource_id} for cloud {cloud_id} " \
                  f"deletion successful."
        db_session.commit()

    LOGGER.info(message)
