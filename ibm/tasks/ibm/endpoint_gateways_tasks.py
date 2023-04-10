from copy import deepcopy
from ibm_cloud_sdk_core import ApiException

from ibm import get_db_session, LOGGER
from ibm.common.clients.ibm_clients import EndpointGatewaysClient, GlobalSearchClient, PrivateCatalogsClient
from ibm.common.clients.ibm_clients.exceptions import IBMAuthError, IBMConnectError, IBMExecuteError, \
    IBMInvalidRequestError
from ibm.common.utils import update_id_or_name_references
from ibm.models import IBMCloud, IBMEndpointGateway, IBMRegion, IBMResourceGroup, IBMResourceLog, IBMSecurityGroup, \
    IBMSubnet, IBMVpcNetwork, WorkflowTask
from ibm.tasks.celery_app import celery_app as celery
from ibm.tasks.common.tasks_base import IBMWorkflowTasksBase
from ibm.tasks.ibm.task_utils import load_previous_associated_resources
from ibm.tasks.other.consts import LOCATION_GLOBAL, REQUEST_BODY_VPE_GLOBAL_SEARCH, VPE_TARGETS_QUERY_PARAM
from ibm.web.ibm.endpoint_gateways.schemas import IBMEndpointGatewayInSchema, IBMEndpointGatewayIpSchema, \
    IBMEndpointGatewayResourceSchema
from ibm.web.ibm.subnets.schemas import IBMReservedIpResourceSchema


@celery.task(name="create_endpoint_gateway", base=IBMWorkflowTasksBase)
def create_endpoint_gateway(workflow_task_id):
    """
    Create an IBM Endpoint Gateway on IBM Cloud
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
        region_dict = resource_data["region"]

        region = db_session.query(IBMRegion).filter_by(**region_dict, cloud_id=cloud_id).first()
        if not region:
            workflow_task.status = WorkflowTask.STATUS_FAILED
            workflow_task.message = f"IBMRegion '{region_dict.get('id') or region_dict.get('name')}' not found"
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
            cloud_id=cloud_id, resource_json=resource_data, resource_schema=IBMEndpointGatewayInSchema,
            db_session=db_session, previous_resources=previous_resources
        )

        update_id_or_name_references(
            cloud_id=cloud_id, resource_json=resource_json, resource_schema=IBMEndpointGatewayResourceSchema,
            db_session=db_session, previous_resources=previous_resources
        )
        ips_list = list()
        for ip_json in resource_json.get("ips", []):
            if ip_json.get("ip_reference"):
                update_id_or_name_references(
                    cloud_id=cloud_id, resource_json=ip_json["ip_reference"],
                    resource_schema=IBMEndpointGatewayIpSchema, db_session=db_session,
                    previous_resources=previous_resources
                )
            elif ip_json.get("ip_resource_json"):
                update_id_or_name_references(
                    cloud_id=cloud_id, resource_json=ip_json["ip_resource_json"],
                    resource_schema=IBMReservedIpResourceSchema, db_session=db_session,
                    previous_resources=previous_resources
                )

            ips_list.append(ip_json.get("ip_reference") or ip_json.get("ip_resource_json"))

        resource_json.pop("ips", None)
        resource_json.pop("region", None)
        resource_json["ips"] = ips_list

    try:
        client = EndpointGatewaysClient(cloud_id=cloud_id, region=region_name)
        resp_json = client.create_endpoint_gateway(endpoint_gateway_json=resource_json)
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

        endpoint_gateway_lifecycle_state = resp_json["lifecycle_state"]
        endpoint_gateway_name = resp_json["name"]
        endpoint_gateway_resource_id = resp_json["id"]
        if endpoint_gateway_lifecycle_state in \
                [IBMEndpointGateway.STATE_PENDING, IBMEndpointGateway.STATE_WAITING, IBMEndpointGateway.STATE_UPDATING]:
            metadata = deepcopy(workflow_task.task_metadata) if workflow_task.task_metadata else {}
            metadata["ibm_resource_id"] = endpoint_gateway_resource_id
            workflow_task.task_metadata = metadata

            workflow_task.status = WorkflowTask.STATUS_RUNNING_WAIT
            message = f"IBM Endpoint Gateway {endpoint_gateway_name} for cloud {cloud_id} creation waiting"
            LOGGER.info(message)
        else:
            message = f"IBM Endpoint Gateway {endpoint_gateway_name} for cloud {cloud_id} creation failed"
            workflow_task.message = message
            workflow_task.status = WorkflowTask.STATUS_FAILED
            LOGGER.info(message)

        db_session.commit()


@celery.task(name="create_wait_endpoint_gateway", base=IBMWorkflowTasksBase)
def create_wait_endpoint_gateway(workflow_task_id):
    """
    Wait for an IBM Endpoint Gateway creation on IBM Cloud
    """
    with get_db_session() as db_session:
        workflow_task = db_session.query(WorkflowTask).filter_by(id=workflow_task_id).first()
        if not workflow_task:
            return

        workflow_task.status = WorkflowTask.STATUS_RUNNING
        db_session.commit()

        resource_data = deepcopy(workflow_task.task_metadata["resource_data"])
        cloud_id = resource_data["ibm_cloud"]["id"]
        region_dict = resource_data["region"]

        region = db_session.query(IBMRegion).filter_by(**region_dict, cloud_id=cloud_id).first()
        if not region:
            workflow_task.status = WorkflowTask.STATUS_FAILED
            workflow_task.message = f"IBMRegion '{region_dict.get('id') or region_dict.get('name')}' not found"
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
        resource_id = workflow_task.task_metadata["ibm_resource_id"]

    try:
        client = EndpointGatewaysClient(cloud_id=cloud_id, region=region_name)
        endpoint_gateway_json = client.get_endpoint_gateway(endpoint_gateway_id=resource_id)
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

        if endpoint_gateway_json["lifecycle_state"] == IBMEndpointGateway.STATE_FAILED:
            workflow_task.status = WorkflowTask.STATUS_FAILED
            workflow_task.message = \
                f"IBM Endpoint Gateway '{endpoint_gateway_json['name']}' creation failed on IBM Cloud"
            db_session.commit()
            LOGGER.fail(workflow_task.message)
            return

        elif endpoint_gateway_json["lifecycle_state"] in \
                [IBMEndpointGateway.STATE_PENDING, IBMEndpointGateway.STATE_WAITING, IBMEndpointGateway.STATE_UPDATING]:
            workflow_task.status = WorkflowTask.STATUS_RUNNING_WAIT
            db_session.commit()
            LOGGER.info(
                f"IBM Endpoint Gateway '{endpoint_gateway_json['name']}' creation for cloud '{cloud_id}' waiting")
            return

        with db_session.no_autoflush:
            region = db_session.query(IBMRegion).filter_by(**region_dict, cloud_id=cloud_id).first()

            resource_group = db_session.query(IBMResourceGroup).filter_by(
                resource_id=endpoint_gateway_json["resource_group"]["id"], cloud_id=cloud_id).first()

            vpc = db_session.query(IBMVpcNetwork).filter_by(
                resource_id=endpoint_gateway_json["vpc"]["id"], cloud_id=cloud_id).first()

            security_group_list = list()
            for security_group in endpoint_gateway_json.get("security_groups", []):
                security_group_obj = db_session.query(IBMSecurityGroup).filter_by(
                    resource_id=security_group["id"], cloud_id=cloud_id).first()
                if not security_group_obj:
                    workflow_task.status = WorkflowTask.STATUS_FAILED
                    workflow_task.message = \
                        "Creation Successful but record update failed. The records will update next time discovery " \
                        "runs"
                    db_session.commit()
                    LOGGER.note(workflow_task.message)
                    return

                security_group_list.append(security_group_obj)

            ip_subnet_dict = dict()
            for ip in endpoint_gateway_json.get("ips", []):
                subnet_resource_id = ip["href"].split("/")[-3]
                subnet_obj = db_session.query(IBMSubnet).filter_by(
                    resource_id=subnet_resource_id, cloud_id=cloud_id).first()
                if not subnet_obj:
                    workflow_task.status = WorkflowTask.STATUS_FAILED
                    workflow_task.message = \
                        "Creation Successful but record update failed. The records will update next time discovery " \
                        "runs"
                    db_session.commit()
                    LOGGER.note(workflow_task.message)
                    return

                ip_subnet_dict[ip["id"]] = subnet_obj

            if not (resource_group and region and vpc):
                workflow_task.status = WorkflowTask.STATUS_FAILED
                workflow_task.message = \
                    "Creation Successful but record update failed. The records will update next time discovery runs"
                db_session.commit()
                LOGGER.note(workflow_task.message)
                return

            endpoint_gateway = IBMEndpointGateway.from_ibm_json_body(json_body=endpoint_gateway_json)
            for ip in endpoint_gateway.reserved_ips.all():
                ip.subnet = ip_subnet_dict[ip.resource_id]

            endpoint_gateway.region = region
            endpoint_gateway.vpc_network = vpc
            endpoint_gateway.resource_group = resource_group
            endpoint_gateway.security_groups = security_group_list

            endpoint_gateway_json = endpoint_gateway.to_json()
            endpoint_gateway_json["created_at"] = str(endpoint_gateway_json["created_at"])

            IBMResourceLog(
                resource_id=endpoint_gateway.resource_id, region=endpoint_gateway.region,
                status=IBMResourceLog.STATUS_ADDED, resource_type=IBMEndpointGateway.__name__,
                data=endpoint_gateway_json)

            db_session.commit()

        workflow_task.status = WorkflowTask.STATUS_SUCCESSFUL
        db_session.commit()

    LOGGER.success(f"IBM Endpoint Gateway '{endpoint_gateway_json['name']}' creation for cloud '{cloud_id}' successful")


@celery.task(name="delete_endpoint_gateway", base=IBMWorkflowTasksBase)
def delete_endpoint_gateway(workflow_task_id):
    """
    Delete an IBM Endpoint Gateway on IBM Cloud
    """
    with get_db_session() as db_session:
        workflow_task: WorkflowTask = db_session.query(WorkflowTask).filter_by(id=workflow_task_id).first()
        if not workflow_task:
            return

        workflow_task.status = WorkflowTask.STATUS_RUNNING
        db_session.commit()

        endpoint_gateway: IBMEndpointGateway = db_session.query(IBMEndpointGateway) \
            .filter_by(id=workflow_task.resource_id).first()
        if not endpoint_gateway:
            workflow_task.status = WorkflowTask.STATUS_FAILED
            workflow_task.message = f"IBM Endpoint Gateway '{workflow_task.resource_id}' not found"
            db_session.commit()
            LOGGER.error(workflow_task.message)
            return

        region_name = endpoint_gateway.region.name
        endpoint_gateway_resource_id = endpoint_gateway.resource_id
        cloud_id = endpoint_gateway.cloud_id

    try:
        client = EndpointGatewaysClient(cloud_id, region=region_name)
        client.delete_endpoint_gateway(endpoint_gateway_id=endpoint_gateway_resource_id)
        endpoint_gateway_json = client.get_endpoint_gateway(endpoint_gateway_id=endpoint_gateway_resource_id)

    except ApiException as ex:
        # TODO: IBM Endpoint Gateway is deleted from IBM Cloud Console, but we still have it on VPC + side.
        with get_db_session() as db_session:
            workflow_task: WorkflowTask = db_session.query(WorkflowTask).filter_by(id=workflow_task_id).first()
            if not workflow_task:
                return

            if ex.code == 404:  # 404 means resource is not found on IBM Cloud.
                endpoint_gateway: IBMEndpointGateway = db_session.query(IBMEndpointGateway) \
                    .filter_by(id=workflow_task.resource_id).first()
                if endpoint_gateway:
                    db_session.delete(endpoint_gateway)

                workflow_task.status = WorkflowTask.STATUS_SUCCESSFUL
                LOGGER.success(
                    f"IBM Endpoint Gateway {endpoint_gateway_resource_id} for cloud {cloud_id} deletion successful.")

                endpoint_gateway_json = endpoint_gateway.to_json()
                endpoint_gateway_json["created_at"] = str(endpoint_gateway_json["created_at"])

                IBMResourceLog(
                    resource_id=endpoint_gateway.resource_id, region=endpoint_gateway.region,
                    status=IBMResourceLog.STATUS_DELETED, resource_type=IBMEndpointGateway.__name__,
                    data=endpoint_gateway_json)

                db_session.commit()
                return
            else:
                workflow_task.status = WorkflowTask.STATUS_FAILED
                workflow_task.message = str(ex.message)
                db_session.commit()
                LOGGER.fail(workflow_task.message)
                return

    with get_db_session() as db_session:
        workflow_task: WorkflowTask = db_session.query(WorkflowTask).filter_by(id=workflow_task_id).first()
        if not workflow_task:
            return

        endpoint_gateway_lifecycle_state = endpoint_gateway_json["lifecycle_state"]
        endpoint_gateway_name = endpoint_gateway_json["name"]
        if endpoint_gateway_lifecycle_state not in \
                [IBMEndpointGateway.STATE_DELETING, IBMEndpointGateway.STATE_PENDING,
                 IBMEndpointGateway.STATE_UPDATING]:
            message = f"IBM Endpoint Gateway {endpoint_gateway_resource_id} for cloud {cloud_id} deletion failed"
            workflow_task.message = message
            workflow_task.status = WorkflowTask.STATUS_FAILED
            LOGGER.fail(workflow_task.message)
            db_session.commit()
            return

        workflow_task.status = WorkflowTask.STATUS_RUNNING_WAIT
        db_session.commit()

    LOGGER.note(
        f"IBM Endpoint Gateway {endpoint_gateway_name} for cloud {endpoint_gateway_resource_id} deletion waiting")


@celery.task(name="delete_wait_endpoint_gateway", base=IBMWorkflowTasksBase)
def delete_wait_endpoint_gateway(workflow_task_id):
    """
    Wait task for Deletion of an IBM Endpoint Gateway on IBM Cloud
    """
    with get_db_session() as db_session:
        workflow_task: WorkflowTask = db_session.query(WorkflowTask).filter_by(id=workflow_task_id).first()
        if not workflow_task:
            return

        workflow_task.status = WorkflowTask.STATUS_RUNNING
        db_session.commit()

        endpoint_gateway: IBMEndpointGateway = db_session.query(IBMEndpointGateway) \
            .filter_by(id=workflow_task.resource_id).first()
        if not endpoint_gateway:
            workflow_task.status = WorkflowTask.STATUS_FAILED
            workflow_task.message = f"IBMEndpointGateway '{workflow_task.resource_id}' not found"
            db_session.commit()
            LOGGER.error(workflow_task.message)
            return

        region_name = endpoint_gateway.region.name
        endpoint_gateway_resource_id = endpoint_gateway.resource_id
        cloud_id = endpoint_gateway.cloud_id

    try:
        client = EndpointGatewaysClient(cloud_id, region=region_name)
        endpoint_gateway_json = client.get_endpoint_gateway(endpoint_gateway_id=endpoint_gateway_resource_id)

    except ApiException as ex:
        with get_db_session() as db_session:
            workflow_task: WorkflowTask = db_session.query(WorkflowTask).filter_by(id=workflow_task_id).first()
            if not workflow_task:
                return

            if ex.code == 404:  # 404 means resource is not found on IBM Cloud.
                endpoint_gateway: IBMEndpointGateway = db_session.query(IBMEndpointGateway).filter_by(
                    id=workflow_task.resource_id).first()
                if endpoint_gateway:
                    db_session.delete(endpoint_gateway)

                workflow_task.status = WorkflowTask.STATUS_SUCCESSFUL
                LOGGER.success(
                    f"IBM Endpoint Gateway {endpoint_gateway_resource_id} for cloud {cloud_id} deletion successful.")

                endpoint_gateway_json = endpoint_gateway.to_json()
                endpoint_gateway_json["created_at"] = str(endpoint_gateway_json["created_at"])

                IBMResourceLog(
                    resource_id=endpoint_gateway.resource_id, region=endpoint_gateway.region,
                    status=IBMResourceLog.STATUS_DELETED, resource_type=IBMEndpointGateway.__name__,
                    data=endpoint_gateway_json)

                db_session.commit()
                return
            else:
                workflow_task.status = WorkflowTask.STATUS_FAILED
                workflow_task.message = str(ex.message)
                db_session.commit()
                LOGGER.fail(workflow_task.message)
                return

    with get_db_session() as db_session:
        workflow_task: WorkflowTask = db_session.query(WorkflowTask).filter_by(id=workflow_task_id).first()
        if not workflow_task:
            return

        endpoint_gateway: IBMEndpointGateway = db_session.query(IBMEndpointGateway) \
            .filter_by(id=workflow_task.resource_id).first()
        if not endpoint_gateway:
            workflow_task.status = WorkflowTask.STATUS_FAILED
            workflow_task.message = f"IBMEndpointGateway '{workflow_task.resource_id}' not found"
            db_session.commit()
            LOGGER.error(workflow_task.message)
            return

        endpoint_gateway_lifecycle_state = endpoint_gateway_json["lifecycle_state"]
        endpoint_gateway_name = endpoint_gateway_json["name"]
        if endpoint_gateway_lifecycle_state not in \
                [IBMEndpointGateway.STATE_DELETING, IBMEndpointGateway.STATE_PENDING,
                 IBMEndpointGateway.STATE_UPDATING]:
            message = f"IBM Endpoint Gateway {endpoint_gateway_resource_id} for cloud {cloud_id} deletion failed"
            workflow_task.message = message
            workflow_task.status = WorkflowTask.STATUS_FAILED
            LOGGER.fail(message)
            db_session.commit()
            return

        workflow_task.status = WorkflowTask.STATUS_RUNNING_WAIT
        workflow_task.message = f"IBM Endpoint Gateway {endpoint_gateway_name} for cloud " \
                                f"{endpoint_gateway_resource_id} deletion waiting"
        IBMResourceLog(
            resource_id=endpoint_gateway.resource_id, region=endpoint_gateway.region,
            status=IBMResourceLog.STATUS_DELETED, resource_type=IBMEndpointGateway.__name__,
            data=endpoint_gateway.to_json())

        db_session.commit()

    LOGGER.note(workflow_task.message)


@celery.task(name="sync_endpoint_gateway_targets", base=IBMWorkflowTasksBase)
def sync_endpoint_gateway_targets(workflow_task_id):
    """
    Sync IBM Targets for Endpoint Gateways from ibm.
    """
    with get_db_session() as db_session:
        workflow_task = db_session.query(WorkflowTask).filter_by(id=workflow_task_id).first()
        if not workflow_task:
            return

        workflow_task.status = WorkflowTask.STATUS_RUNNING
        db_session.commit()

        resource_data = deepcopy(workflow_task.task_metadata["resource_data"])
        cloud_id = resource_data["cloud_id"]

        ibm_cloud: IBMCloud = db_session.query(IBMCloud).filter_by(id=cloud_id).first()
        if not ibm_cloud:
            workflow_task.status = WorkflowTask.STATUS_FAILED
            workflow_task.message = f"IBMCloud '{cloud_id}' not found"
            db_session.commit()
            LOGGER.error(workflow_task.message)
            return

        cloud_id = ibm_cloud.id

    try:
        client_private_search = PrivateCatalogsClient(cloud_id=cloud_id)
        client_global_search = GlobalSearchClient(cloud_id=cloud_id)

        private_data_list = client_private_search.list_objects_across_catalogs(
            query=VPE_TARGETS_QUERY_PARAM, digest=False)
        global_search_data = client_global_search.find_instance_of_resources(
            request_body=REQUEST_BODY_VPE_GLOBAL_SEARCH)

    except (IBMAuthError, IBMConnectError, IBMExecuteError, IBMInvalidRequestError) as ex:
        with get_db_session() as db_session:
            workflow_task = db_session.query(WorkflowTask).filter_by(id=workflow_task_id).first()
            if not workflow_task:
                return

            workflow_task.status = WorkflowTask.STATUS_FAILED
            workflow_task.message = f"Method failed with error: {str(ex)}"
            db_session.commit()
            LOGGER.fail(workflow_task.message)
        return

    with get_db_session() as db_session:
        workflow_task = db_session.query(WorkflowTask).filter_by(id=workflow_task_id).first()
        if not workflow_task:
            return

        # TODO: Enhance this piece.
        targets_dict = dict()
        for data in private_data_list:
            region = data["parent_id"]
            if region in targets_dict:
                regional_services_list = targets_dict[region]
            else:
                regional_services_list = ["ibm-ntp-server"]

            service_name = None
            for tag in data["tags"]:
                if "svc:" in tag:
                    service_name = tag.split(":")[-1]
                    break

            if service_name not in regional_services_list:
                regional_services_list.append(service_name)
                targets_dict[region] = regional_services_list

            if service_name in targets_dict:
                service = targets_dict[service_name]
            else:
                service = {
                    "locations": []
                }
                if "global" in data["data"]["service_crn"]:
                    service["locations"].append("global")

            if region in service:
                service[region].append(data["data"])
            else:
                service[region] = [data["data"]]

            if "global" not in service["locations"] and region not in service["locations"]:
                service["locations"].append(region)

            targets_dict[service_name] = service

        for data in global_search_data:
            region = data["region"]
            service_name = data["service_name"]
            if region in targets_dict:
                regional_services_list = targets_dict[region]
            else:
                regional_services_list = ["ibm-ntp-server"]

            if service_name not in regional_services_list:
                regional_services_list.append(service_name)
                targets_dict[region] = regional_services_list

            if service_name in targets_dict:
                service = targets_dict[service_name]
            else:
                service = {
                    "locations": []
                }
                if "global" in data["crn"]:
                    service["locations"].append("global")

            if LOCATION_GLOBAL not in service["locations"] and region not in service["locations"]:
                service["locations"].append(region)

            target_endpoints = data["doc"]["extensions"]["virtual_private_endpoints"]
            domains = list()
            for host in target_endpoints["dns_hosts"]:
                domains.append(host + "." + target_endpoints["dns_domain"])

            # name 'conversation' is FE equivalent to 'Watson Assistant'
            endpoint = {
                "name": data["name"],
                "endpoint_type": None,
                "fully_qualified_domain_names": domains,
                "service_crn": data["crn"]
            }
            if region in service:
                service[region].append(endpoint)
            else:
                service[region] = [endpoint]

            targets_dict[service_name] = service

        # TODO: This solo resource is not coming up in any of the APIs used to get the Targets for VPE.
        #  Need to look for an API to fetch this dynamically.
        targets_dict["ibm-ntp-server"] = {
            "name": "ibm-ntp-server",
            "resource_type": "provider_infrastructure_service"
        }

        workflow_task.status = WorkflowTask.STATUS_SUCCESSFUL
        workflow_task.result = {"resource_json": targets_dict}
        db_session.commit()

    LOGGER.success("IBMEndpointGateway targets synced successfully.")
