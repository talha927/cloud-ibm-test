import logging

from ibm import get_db_session
from ibm.common.clients.softlayer_clients import SoftlayerMonitoringClient, SoftlayerNetworkGatewayClient
from ibm.common.clients.softlayer_clients.exceptions import SLAuthError, SLExecuteError, SLInvalidRequestError
from ibm.common.clients.softlayer_clients.instances.utils import get_ibm_instance_profile
from ibm.common.utils import calculate_average, get_months_date_interval
from ibm.models import SoftlayerCloud, WorkflowTask
from ibm.models.softlayer.monitoring_models import SoftLayerInstanceMonitoring
from ibm.models.softlayer.network_gateway_models import SoftLayerNetworkGateway
from ibm.models.softlayer.resources_models import SoftLayerImage, SoftLayerInstance, SoftLayerInstanceProfile
from ibm.tasks.celery_app import celery_app as celery
from ibm.tasks.common.tasks_base import IBMWorkflowTasksBase
from .utils import generate_network_gateway_recommendations, generate_virtual_server_recommendations

LOGGER = logging.getLogger(__name__)


@celery.task(name="sync_classic_network_gateways", base=IBMWorkflowTasksBase, queue='recommendations_queue')
def sync_classic_network_gateways_task(workflow_task_id):
    """
    Discover ALL network gateways on Classic Infrastructure
    """
    with get_db_session() as db_session:
        workflow_task = db_session.query(WorkflowTask).filter_by(id=workflow_task_id).first()
        if not workflow_task:
            return

        task_metadata = workflow_task.task_metadata
        softlayer_cloud_id = task_metadata['softlayer_cloud_id']
        softlayer_cloud: SoftlayerCloud = db_session.query(SoftlayerCloud).filter_by(id=softlayer_cloud_id).first()
        if not softlayer_cloud:
            workflow_task.status = WorkflowTask.STATUS_FAILED
            workflow_task.message = f"Softlayer cloud with ID {softlayer_cloud_id} not found in DB"
            db_session.commit()
            LOGGER.info(workflow_task.message)
            return

        try:
            network_gateways_client = SoftlayerNetworkGatewayClient(softlayer_cloud_id)
            response = network_gateways_client.get_network_gateways()

        except (SLAuthError, SLExecuteError, SLInvalidRequestError) as ex:
            with get_db_session() as db_session:
                workflow_task = db_session.query(WorkflowTask).filter_by(id=workflow_task_id).first()
                if not workflow_task:
                    return

                workflow_task.status = WorkflowTask.STATUS_FAILED
                workflow_task.message = f"Creation Failed. Reason: {str(ex)}"
                db_session.commit()
                LOGGER.info(ex)
                return

        with get_db_session() as db_session:
            workflow_task = db_session.query(WorkflowTask).filter_by(id=workflow_task_id).first()
            if not workflow_task:
                return

            workflow_task.result = response
            workflow_task.status = WorkflowTask.STATUS_SUCCESSFUL
            db_session.commit()

        LOGGER.info(f"Softlayer Network Gateways discovered successfully for Softlayer Cloud with ID "
                    f"{softlayer_cloud_id}")


@celery.task(name="sync_classic_virtual_guests_usage", base=IBMWorkflowTasksBase, queue='recommendations_queue')
def sync_classic_virtual_guests_usage_task(workflow_task_id):
    """
    Discover ALL virtual guests configured on Classic Infrastructure
    """
    with get_db_session() as db_session:
        workflow_task = db_session.query(WorkflowTask).filter_by(id=workflow_task_id).first()
        if not workflow_task:
            return

        task_metadata = workflow_task.task_metadata
        softlayer_cloud_id = task_metadata['softlayer_cloud_id']
        softlayer_cloud: SoftlayerCloud = db_session.query(SoftlayerCloud).filter_by(id=softlayer_cloud_id).first()
        if not softlayer_cloud:
            workflow_task.status = WorkflowTask.STATUS_FAILED
            workflow_task.message = f"Softlayer cloud with ID {softlayer_cloud_id} not found in DB"
            db_session.commit()
            LOGGER.info(workflow_task.message)
            return

    try:
        monitoring_client = SoftlayerMonitoringClient(softlayer_cloud_id)
        response = monitoring_client.get_virtual_guests()

    except (SLAuthError, SLExecuteError, SLInvalidRequestError) as ex:
        with get_db_session() as db_session:
            workflow_task = db_session.query(WorkflowTask).filter_by(id=workflow_task_id).first()
            if not workflow_task:
                return

            workflow_task.status = WorkflowTask.STATUS_FAILED
            workflow_task.message = f"Creation Failed. Reason: {str(ex)}"
            db_session.commit()
            LOGGER.info(ex)
            return

    with get_db_session() as db_session:
        workflow_task = db_session.query(WorkflowTask).filter_by(id=workflow_task_id).first()
        if not workflow_task:
            return

        generate_recommendation_task = workflow_task.next_tasks.filter(
            WorkflowTask.resource_type == "SoftLayerRecommendation").first()
        for virtual_guest in response:
            if not virtual_guest.get('metricTrackingObjectId'):
                continue

            task_metadata = {
                'guest': virtual_guest,
                'softlayer_cloud_id': softlayer_cloud_id
            }
            memory_usage_task = WorkflowTask(
                task_type="SYNC", resource_type="SoftLayerInstanceMemoryUsage", task_metadata=task_metadata)
            cpu_usage_task = WorkflowTask(
                task_type="SYNC", resource_type="SoftLayerInstanceCPUUsage", task_metadata=task_metadata)
            bandwidth_usage_task = WorkflowTask(
                task_type="SYNC", resource_type="SoftLayerInstanceBandwidthUsage", task_metadata=task_metadata
            )
            workflow_task.add_next_task(memory_usage_task)
            workflow_task.add_next_task(cpu_usage_task)
            workflow_task.add_next_task(bandwidth_usage_task)
            memory_usage_task.add_next_task(generate_recommendation_task)
            cpu_usage_task.add_next_task(generate_recommendation_task)
            bandwidth_usage_task.add_next_task(generate_recommendation_task)
            db_session.commit()

        workflow_task.result = response
        workflow_task.status = WorkflowTask.STATUS_SUCCESSFUL
        db_session.commit()

    LOGGER.info(f"Softlayer Instances discovered successfully for Softlayer Cloud with ID {softlayer_cloud_id}")


@celery.task(name="sync_classic_virtual_guest_memory_usage", base=IBMWorkflowTasksBase, queue='recommendations_queue')
def sync_classic_virtual_guest_memory_usage_task(workflow_task_id):
    """
    Formats and executes an API call to get memory usage data for a VM on Classic
    """
    with get_db_session() as db_session:
        workflow_task = db_session.query(WorkflowTask).filter_by(id=workflow_task_id).first()
        if not workflow_task:
            return

        task_metadata = workflow_task.task_metadata
        softlayer_cloud_id = task_metadata['softlayer_cloud_id']
        guest = task_metadata['guest']
        softlayer_cloud: SoftlayerCloud = db_session.query(SoftlayerCloud).filter_by(id=softlayer_cloud_id).first()
        if not softlayer_cloud:
            workflow_task.status = WorkflowTask.STATUS_FAILED
            workflow_task.message = f"Softlayer cloud with ID {softlayer_cloud_id} not found in DB"
            db_session.commit()
            LOGGER.info(workflow_task.message)
            return

    start_date, end_date = get_months_date_interval()
    try:
        monitoring_client = SoftlayerMonitoringClient(softlayer_cloud_id)
        response = monitoring_client.get_memory_usage(guest=guest, start_date=start_date, end_date=end_date)

    except (SLAuthError, SLExecuteError, SLInvalidRequestError) as ex:
        with get_db_session() as db_session:
            workflow_task = db_session.query(WorkflowTask).filter_by(id=workflow_task_id).first()
            if not workflow_task:
                return

            workflow_task.status = WorkflowTask.STATUS_FAILED
            workflow_task.message = f"Creation Failed. Reason: {str(ex)}"
            db_session.commit()
            LOGGER.info(ex)
            return

    with get_db_session() as db_session:
        workflow_task = db_session.query(WorkflowTask).filter_by(id=workflow_task_id).first()
        if not workflow_task:
            return

        average_memory_usage = calculate_average(response)
        if average_memory_usage.get('memory_usage'):
            average_memory_usage = round((average_memory_usage['memory_usage'] / (2 ** 30) * 1024), 2)
        workflow_task.result = {"MEMORY_USAGE": average_memory_usage}
        workflow_task.resource_id = guest['id']
        workflow_task.status = WorkflowTask.STATUS_SUCCESSFUL
        db_session.commit()

    LOGGER.info(f"Softlayer Virtual Guest with Name {guest['hostname']} Memory Usage discovered successfully")


@celery.task(name="sync_classic_virtual_guest_bandwidth_usage", base=IBMWorkflowTasksBase,
             queue='recommendations_queue')
def sync_classic_virtual_guest_bandwidth_usage_task(workflow_task_id):
    """
    Formats and executes an API call to get memory usage data for a VM on Classic
    """
    with get_db_session() as db_session:
        workflow_task = db_session.query(WorkflowTask).filter_by(id=workflow_task_id).first()
        if not workflow_task:
            return

        task_metadata = workflow_task.task_metadata
        softlayer_cloud_id = task_metadata['softlayer_cloud_id']
        guest = task_metadata['guest']
        softlayer_cloud: SoftlayerCloud = db_session.query(SoftlayerCloud).filter_by(id=softlayer_cloud_id).first()
        if not softlayer_cloud:
            workflow_task.status = WorkflowTask.STATUS_FAILED
            workflow_task.message = f"Softlayer cloud with ID {softlayer_cloud_id} not found in DB"
            db_session.commit()
            LOGGER.info(workflow_task.message)
            return

    start_date, end_date = get_months_date_interval()
    try:
        monitoring_client = SoftlayerMonitoringClient(softlayer_cloud_id)
        inbound_bandwidth_response = monitoring_client.get_bandwidth_usage(
            guest=guest, start_date=start_date, end_date=end_date, bandwidth_type="INBOUND")
        outbound_bandwidth_response = monitoring_client.get_bandwidth_usage(
            guest=guest, start_date=start_date, end_date=end_date, bandwidth_type="OUTBOUND")

    except (SLAuthError, SLExecuteError, SLInvalidRequestError) as ex:
        with get_db_session() as db_session:
            workflow_task = db_session.query(WorkflowTask).filter_by(id=workflow_task_id).first()
            if not workflow_task:
                return

            workflow_task.status = WorkflowTask.STATUS_FAILED
            workflow_task.message = f"Creation Failed. Reason: {str(ex)}"
            db_session.commit()
            LOGGER.info(ex)
            return

    with get_db_session() as db_session:
        workflow_task = db_session.query(WorkflowTask).filter_by(id=workflow_task_id).first()
        if not workflow_task:
            return

        inbound_usage, outbound_usage = 0, 0
        inbound_usage_average = calculate_average(inbound_bandwidth_response)
        outbound_usage_average = calculate_average(outbound_bandwidth_response)

        if inbound_usage_average.get('publicIn_net_octet'):
            inbound_usage = round((inbound_usage_average['publicIn_net_octet'] / (2 ** 30) * 1024), 2)
        if outbound_usage_average.get('publicOut_net_octet'):
            outbound_usage = round((outbound_usage_average['publicOut_net_octet'] / (2 ** 30) * 1024), 2)
        workflow_task.result = {
            "inbound_bandwidth_usage": inbound_usage,
            "outbound_bandwidth_usage": outbound_usage
        }
        workflow_task.resource_id = guest['id']
        workflow_task.status = WorkflowTask.STATUS_SUCCESSFUL
        db_session.commit()

    LOGGER.info(f"Softlayer Virtual Guest with Name {guest['hostname']} Bandwidth Usage discovered successfully")


@celery.task(name="sync_classic_virtual_guest_cpu_usage", base=IBMWorkflowTasksBase, queue='recommendations_queue')
def sync_classic_virtual_guest_cpu_usage_task(workflow_task_id):
    """
    Makes an API call to get CPU usage data for a Virtual Machine on Classic
    """
    with get_db_session() as db_session:
        workflow_task = db_session.query(WorkflowTask).filter_by(id=workflow_task_id).first()
        if not workflow_task:
            return

        task_metadata = workflow_task.task_metadata
        softlayer_cloud_id = task_metadata['softlayer_cloud_id']
        guest = task_metadata['guest']
        softlayer_cloud: SoftlayerCloud = db_session.query(SoftlayerCloud).filter_by(id=softlayer_cloud_id).first()
        if not softlayer_cloud:
            workflow_task.status = WorkflowTask.STATUS_FAILED
            workflow_task.message = f"Softlayer cloud with ID {softlayer_cloud_id} not found in DB"
            db_session.commit()
            LOGGER.info(workflow_task.message)
            return

    start_date, end_date = get_months_date_interval()
    try:
        monitoring_client = SoftlayerMonitoringClient(softlayer_cloud_id)
        response = monitoring_client.get_cpu_usage_per_cpu(guest=guest, start_date=start_date, end_date=end_date)

    except (SLAuthError, SLExecuteError, SLInvalidRequestError) as ex:
        with get_db_session() as db_session:
            workflow_task = db_session.query(WorkflowTask).filter_by(id=workflow_task_id).first()
            if not workflow_task:
                return

            workflow_task.status = WorkflowTask.STATUS_FAILED
            workflow_task.message = f"Creation Failed. Reason: {str(ex)}"
            db_session.commit()
            LOGGER.info(ex)
            return

    with get_db_session() as db_session:
        workflow_task = db_session.query(WorkflowTask).filter_by(id=workflow_task_id).first()
        if not workflow_task:
            return

        workflow_task.result = {"CPU_USAGE": calculate_average(response)}
        workflow_task.resource_id = guest['id']
        workflow_task.status = WorkflowTask.STATUS_SUCCESSFUL
        db_session.commit()

    LOGGER.info(f"Softlayer Virtual Guest with Name {guest['hostname']} CPU Usage discovered successfully")


@celery.task(name="generate_classic_recommendations", base=IBMWorkflowTasksBase, queue='recommendations_queue')
def generate_classic_recommendations_task(workflow_task_id):
    """
    This task examines previous tasks and generates recommendations as per needed
    """
    with get_db_session() as db_session:
        workflow_task = db_session.query(WorkflowTask).filter_by(id=workflow_task_id).first()
        if not workflow_task:
            return

        task_metadata = workflow_task.task_metadata
        softlayer_cloud_id = task_metadata['softlayer_cloud_id']
        softlayer_cloud: SoftlayerCloud = db_session.query(SoftlayerCloud).filter_by(id=softlayer_cloud_id).first()
        if not softlayer_cloud:
            workflow_task.status = WorkflowTask.STATUS_FAILED
            workflow_task.message = f"Softlayer cloud with ID {softlayer_cloud_id} not found in DB"
            db_session.commit()
            LOGGER.info(workflow_task.message)
            return

        softlayer_network_gateways = list()
        network_gateways_task = workflow_task.previous_tasks.filter(
            WorkflowTask.resource_type == "SoftLayerNetworkGateway").first()
        network_gateways = network_gateways_task.result
        for network_gateway in network_gateways:
            softlayer_network_gateway = SoftLayerNetworkGateway.from_softlayer_json(network_gateway)
            softlayer_ngw_json = softlayer_network_gateway.to_json()
            softlayer_ngw_json['recommendations'] = generate_network_gateway_recommendations(softlayer_network_gateway)
            softlayer_network_gateways.append(softlayer_ngw_json)

        instances = list()
        virtual_guest_task = workflow_task.previous_tasks.filter(
            WorkflowTask.resource_type == "SoftLayerVirtualGuest").first()
        for virtual_guest in virtual_guest_task.result:
            if not virtual_guest.get('operatingSystem'):
                continue

            softlayer_instance = SoftLayerInstance.from_softlayer_json(instance_json=virtual_guest)
            instance_profile, family = get_ibm_instance_profile(virtual_guest["maxCpu"], virtual_guest["maxMemory"])
            softlayer_instance.instance_profile = SoftLayerInstanceProfile(
                name=instance_profile, family=family, max_cpu=virtual_guest["maxCpu"],
                max_memory=virtual_guest["maxMemory"])
            os = virtual_guest["operatingSystem"]["softwareLicense"]["softwareDescription"]
            softlayer_instance.image = SoftLayerImage.from_softlayer_json(operating_system=os)
            softlayer_instance.monitoring_info = SoftLayerInstanceMonitoring()

            memory_usage_task = workflow_task.root.associated_tasks.filter(
                WorkflowTask.resource_type == "SoftLayerInstanceMemoryUsage",
                WorkflowTask.resource_id == virtual_guest['id']).first()
            if memory_usage_task:
                task_metadata = memory_usage_task.task_metadata['guest']
                softlayer_instance.monitoring_info.used_memory = memory_usage_task.result['MEMORY_USAGE']
                softlayer_instance.monitoring_info.total_memory = task_metadata['maxMemory']

            cpu_usage_task = workflow_task.root.associated_tasks.filter(
                WorkflowTask.resource_type == "SoftLayerInstanceCPUUsage",
                WorkflowTask.resource_id == virtual_guest['id']).first()
            if cpu_usage_task:
                result = cpu_usage_task.result['CPU_USAGE']
                softlayer_instance.monitoring_info.cpu_usage = result

            bandwidth_usage_task = workflow_task.root.associated_tasks.filter(
                WorkflowTask.resource_type == "SoftLayerInstanceBandwidthUsage",
                WorkflowTask.resource_id == virtual_guest['id']).first()
            if bandwidth_usage_task:
                result = bandwidth_usage_task.result
                softlayer_instance.monitoring_info.inbound_bandwidth_usage = result['inbound_bandwidth_usage']
                softlayer_instance.monitoring_info.outbound_bandwidth_usage = result['outbound_bandwidth_usage']

            recommendations, recommended_instance_profile, potential_savings = generate_virtual_server_recommendations(
                softlayer_instance)
            softlayer_instance_json = softlayer_instance.to_json()
            softlayer_instance_json['recommendations'] = recommendations
            softlayer_instance_json['recommended_profile'] = recommended_instance_profile
            softlayer_instance_json['potential_savings'] = potential_savings
            instances.append(softlayer_instance_json)

        workflow_task.result = {
            "instances": instances,
            "network_gateways": softlayer_network_gateways
        }
        workflow_task.status = WorkflowTask.STATUS_SUCCESSFUL
        workflow_task.resource_id = softlayer_cloud_id
        db_session.commit()

        LOGGER.info(f"Softlayer Recommendations for Softlayer cloud with {softlayer_cloud_id} generated successfully.")
