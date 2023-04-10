import json
import logging
from copy import deepcopy

from ibm import get_db_session
from ibm.common.clients.ibm_clients import KubernetesClient
from ibm.common.clients.ibm_clients.exceptions import IBMExecuteError
from ibm.common.clients.softlayer_clients import SoftlayerDedicateHostClient, SoftlayerInstanceClient, \
    SoftlayerLoadBalancerClient, SoftlayerSecurityGroupClient, SoftlayerSshKeyClient, SoftlayerSubnetClient
from ibm.common.clients.softlayer_clients.exceptions import SLAuthError, SLExecuteError, SLInvalidRequestError
from ibm.common.clients.softlayer_clients.placement_groups import SoftlayerPlacementGroupClient
from ibm.common.clients.softlayer_clients.vyatta56analyzer import Vyatta56Analyzer
from ibm.common.utils import transform_ibm_name
from ibm.models import IBMCloud, IBMKubernetesCluster, IBMKubernetesClusterWorkerPool, \
    IBMKubernetesClusterWorkerPoolZone, SoftlayerCloud, WorkflowTask, WorkflowsWorkspace
from ibm.tasks.celery_app import celery_app as celery
from ibm.tasks.common.tasks_base import IBMWorkflowTasksBase
from ibm.tasks.common.utils import generate_ibm_vpc_schema
from ibm.web.ibm.kubernetes.utils import Kubernetes
from ibm.web.ibm.workspaces.utils import create_workspace_workflow

LOGGER = logging.getLogger(__name__)


@celery.task(name="sync_softlayer_resources_task", base=IBMWorkflowTasksBase)
def sync_softlayer_resources_task(workflow_task_id):
    """
    Sync softlayer resources of Softlayer Cloud
    """
    with get_db_session() as db_session:
        workflow_task = db_session.query(WorkflowTask).filter_by(id=workflow_task_id).first()
        if not workflow_task:
            return

        workflow_task.status = WorkflowTask.STATUS_RUNNING
        db_session.commit()

        resource_data = deepcopy(workflow_task.task_metadata["resource_data"])
        configs = resource_data.get("config_file")
        cloud_id = resource_data["softlayer_cloud"]["id"]
        user = resource_data.get("user")

        softlayer_cloud: SoftlayerCloud = db_session.query(SoftlayerCloud).filter_by(id=cloud_id).first()
        if not softlayer_cloud:
            workflow_task.status = WorkflowTask.STATUS_FAILED
            workflow_task.message = f"Softlayer cloud {cloud_id} not found"
            db_session.commit()
            LOGGER.info(workflow_task.message)
            return

        vpc_data = dict()

    try:
        subnet_client = SoftlayerSubnetClient(cloud_id)
        security_group_client = SoftlayerSecurityGroupClient(cloud_id)
        instance_client = SoftlayerInstanceClient(cloud_id)
        placement_group_client = SoftlayerPlacementGroupClient(cloud_id)
        load_balancer_client = SoftlayerLoadBalancerClient(cloud_id)
        dedicated_host_client = SoftlayerDedicateHostClient(cloud_id)
        ssh_key_client = SoftlayerSshKeyClient(cloud_id)
        vpc_data['subnets'] = subnet_client.list_private_subnets()
        vpc_data['security_groups'] = security_group_client.list_security_groups()
        vpc_data['instances'] = instance_client.list_virtual_servers(subnets=vpc_data["subnets"])
        vpc_data["placement_groups"] = placement_group_client.list_placement_groups()
        vpc_data['load_balancers'] = load_balancer_client.list_load_balancers(vs_instances=vpc_data['instances'])
        vpc_data['dedicated_hosts'] = dedicated_host_client.list_dedicated_hosts()
        vpc_data['ssh_keys'] = ssh_key_client.list_ssh_keys()

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

    vy56_analyser = None
    if configs:
        LOGGER.info("Starting VRA discovery for VYATTA-5600 Config File")
        vy56_analyser = Vyatta56Analyzer(configs)
        vpc_data['firewalls'] = list()
        vpc_data['subnets'].extend(vy56_analyser.get_private_subnets())
        for subnet in vpc_data['subnets']:
            subnet.public_gateway = vy56_analyser.has_public_gateway(subnet.network)
            subnet.firewalls = vy56_analyser.get_attached_firewalls(subnet.vif_id)

        vpc_data['vpn_gateways'] = vy56_analyser.get_ipsec()
        for subnet in vpc_data['subnets']:
            vpc_data['firewalls'].extend(subnet.firewalls)
            for firewall, vpn in zip(subnet.firewalls, vpc_data['vpn_gateways']):
                if vpn.peer_address in firewall.destination_addresses:
                    vpn.subnet = transform_ibm_name(subnet.name)

    ported_schema = generate_ibm_vpc_schema(vpc_data, vy56_analyser, softlayer_cloud=cloud_id)
    with get_db_session() as db_session:
        workflow_task: WorkflowTask = db_session.query(WorkflowTask).filter_by(id=workflow_task_id).first()
        if not workflow_task:
            return

        # TODO: check the use for this method. revisit this later
        # discovered_schema = get_softlayer_schema(vpc_data)
        if workflow_task.next_tasks.all():
            workflow_task.result = ported_schema
        else:
            ported_schema["name"] = "wip-template"
            workspace = create_workspace_workflow(user=user, data=ported_schema, db_session=db_session, sketch=True,
                                                  source_cloud=WorkflowsWorkspace.SOFTLAYER,
                                                  workspace_type=WorkflowsWorkspace.TYPE_SOFTLAYER)
            workflow_task.result = {
                "resource_json": json.dumps(workspace.to_json(), default=str)
            }
        workflow_task.status = WorkflowTask.STATUS_SUCCESSFUL
        db_session.commit()

    LOGGER.info(f"Softlayer Discovery completed for Softlayer '{cloud_id}'")


@celery.task(name="sync_classic_kubernetes_task", base=IBMWorkflowTasksBase)
def sync_classic_kubernetes_task(workflow_task_id):
    """
    Sync classical kubernetes clusters.
    """
    with get_db_session() as db_session:
        workflow_task = db_session.query(WorkflowTask).filter_by(id=workflow_task_id).first()
        if not workflow_task:
            return

        workflow_task.status = WorkflowTask.STATUS_RUNNING
        db_session.commit()

        resource_data = deepcopy(workflow_task.task_metadata["resource_data"])
        ibm_cloud_id = resource_data["ibm_cloud"]["id"]

        ibm_cloud: IBMCloud = db_session.query(IBMCloud).filter_by(id=ibm_cloud_id).first()
        if not ibm_cloud:
            workflow_task.status = WorkflowTask.STATUS_FAILED
            workflow_task.message = f"IBMCloud if '{ibm_cloud_id}' not found"
            db_session.commit()
            LOGGER.info(workflow_task.message)
            return

        sl_cloud_id = resource_data["softlayer_cloud"]["id"]
        softlayer_cloud: SoftlayerCloud = db_session.query(SoftlayerCloud).filter_by(id=sl_cloud_id).first()
        if not softlayer_cloud:
            workflow_task.status = WorkflowTask.STATUS_FAILED
            workflow_task.message = f"Softlayer cloud {sl_cloud_id} not found"
            db_session.commit()
            LOGGER.info(workflow_task.message)
            return

        kubernetes_clusters_list = list()

    try:
        kubernetes_client = KubernetesClient(cloud_id=ibm_cloud_id)
        clusters = kubernetes_client.list_kubernetes_classic_clusters()

        if clusters:

            sl_subnet_client = SoftlayerSubnetClient(cloud_id=sl_cloud_id)
            subnets = sl_subnet_client.list_private_subnets()

            for cluster in clusters:
                if cluster['state'] != IBMKubernetesCluster.STATE_NORMAL or \
                        len(str(cluster['ingress'].get('hostname')).strip()) < 5:
                    continue

                kubernetes_cluster = IBMKubernetesCluster.from_ibm_json_body(cluster)
                kubernetes_cluster_subnets = kubernetes_client.get_cluster_subnets(
                    cluster=cluster["id"], resource_group=cluster["resourceGroup"])

                if kubernetes_cluster_subnets == "Free tier cluster":
                    continue

                kubernetes_cluster_worker_pools = kubernetes_client.get_classic_kubernetes_cluster_worker_pool(
                    cluster=cluster["id"])

                for kubernetes_cluster_worker_pool in kubernetes_cluster_worker_pools:
                    classic_cluster_worker_pool = IBMKubernetesClusterWorkerPool.from_classic_ibm_json_body(
                        kubernetes_cluster_worker_pool)
                    for kubernetes_cluster_worker_pool_zone in kubernetes_cluster_worker_pool['zones']:
                        classic_kubernetes_cluster_worker_pool_zone = \
                            IBMKubernetesClusterWorkerPoolZone.from_ibm_json_body_classic(
                                kubernetes_cluster_worker_pool_zone)

                        for subnet in subnets:
                            for kubernetes_cluster_subnet in kubernetes_cluster_subnets:
                                if classic_kubernetes_cluster_worker_pool_zone.private_vlan == \
                                        kubernetes_cluster_subnet["id"]:

                                    if subnet.network == kubernetes_cluster_subnet["subnets"][0]['cidr']:
                                        classic_kubernetes_cluster_worker_pool_zone.subnets.append(subnet.to_ibm())

                            classic_cluster_worker_pool.worker_zones.append(
                                classic_kubernetes_cluster_worker_pool_zone)
                        kubernetes_cluster.worker_pools.append(classic_cluster_worker_pool)

                kube_config = kubernetes_client.get_kubernetes_cluster_kube_config(cluster=cluster["id"])
                kube_config = Kubernetes(configuration_json=kube_config)

                kubernetes_cluster.workloads = IBMKubernetesCluster.sync_workloads_for_clsuter(kube_config)
                kubernetes_clusters_list.append(kubernetes_cluster)

    except (SLAuthError, SLExecuteError, SLInvalidRequestError, IBMExecuteError) as ex:
        with get_db_session() as db_session:
            workflow_task = db_session.query(WorkflowTask).filter_by(id=workflow_task_id).first()
            if not workflow_task:
                return

            workflow_task.status = WorkflowTask.STATUS_FAILED
            workflow_task.message = f"Classic Clusters Discovery Failed. Reason: {str(ex)}"
            db_session.commit()

        LOGGER.info(ex)
        return

    with get_db_session() as db_session:
        workflow_task: WorkflowTask = db_session.query(WorkflowTask).filter_by(id=workflow_task_id).first()
        if not workflow_task:
            return

        workflow_task.result = {
            "resource_json": [cluster.from_softlayer_to_ibm_json() for cluster in kubernetes_clusters_list]
        }
        workflow_task.status = WorkflowTask.STATUS_SUCCESSFUL
        db_session.commit()

    LOGGER.info(f"Kubernetes Classic discovery completed for IBMCloud '{ibm_cloud_id}'")
