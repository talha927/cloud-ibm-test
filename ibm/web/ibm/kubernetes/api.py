import logging

from apiflask import abort, APIBlueprint, doc, input, output
from sqlalchemy.orm import undefer

from ibm.auth import authenticate
from ibm.common.req_resp_schemas.schemas import get_pagination_schema, \
    IBMResourceQuerySchema, IBMVPCRegionalResourceListQuerySchema, PaginationQuerySchema, WorkflowRootOutSchema
from ibm.middleware import log_activity
from ibm.models import IBMCloud, IBMKubernetesCluster, IBMKubernetesClusterWorkerPool, IBMResourceGroup, \
    IBMVpcNetwork, \
    SoftlayerCloud, WorkflowRoot, WorkflowTask
from ibm.web import db as ibmdb
from ibm.web.common.utils import authorize_and_get_ibm_cloud, compose_ibm_resource_deletion_workflow, \
    compose_ibm_sync_resource_workflow, get_paginated_response_json, verify_and_get_region, verify_and_get_zone
from .schemas import IBMKubernetesClusterInSchema, IBMKubernetesClusterOutSchema, IBMKubernetesClustersListOutSchema, \
    IBMKubernetesClusterWorkerPoolOutSchema, IBMKubernetesClusterWorkloadsOutSchema, IBMMultiZoneDiscoverySchema, \
    IBMZonesList
from .utils import create_ibm_kubernetes_cluster_migration_workflow

LOGGER = logging.getLogger(__name__)
ibm_kubernetes_clusters = APIBlueprint('ibm_kubernetes_clusters', __name__, tag="IBM Kubernetes Clusters")


@ibm_kubernetes_clusters.post("/kubernetes_clusters")
@authenticate
@log_activity
@input(IBMKubernetesClusterInSchema)
@output(WorkflowRootOutSchema, status_code=202)
def migrate_kubernetes_cluster(data, user):
    """
    Create/Migrate Kubernetes Clusters
    This request Create an IBM Kubernetes cluster or migrate from classic to VPC infrastructure
    """

    cloud_id = data["ibm_cloud"]["id"]
    region_id = data["region"]["id"]
    vpc_dict = data["resource_json"]["vpc"]
    resource_group_dict = data["resource_json"]["resource_group"]

    ibm_cloud = authorize_and_get_ibm_cloud(cloud_id=cloud_id, user=user)
    verify_and_get_region(ibm_cloud=ibm_cloud, region_id=region_id)

    vpc = ibmdb.session.query(IBMVpcNetwork).filter_by(**vpc_dict).first()
    if not vpc:
        message = f"IBM VPC Network" \
                  f"'{vpc_dict.get('id') or vpc_dict.get('name')}' not found"
        LOGGER.debug(message)
        abort(404, message)

    resource_group = ibmdb.session.query(IBMResourceGroup).filter_by(**resource_group_dict).first()
    if not resource_group:
        message = f"ResourceGroup" \
                  f"'{resource_group_dict.get('id') or resource_group_dict.get('name')}' not found"
        LOGGER.debug(message)
        abort(404, message)

    data['resource_group'] = resource_group.resource_id
    workflow_root = create_ibm_kubernetes_cluster_migration_workflow(data, user)

    return workflow_root.to_json(metadata=True)


@ibm_kubernetes_clusters.get('/kubernetes_clusters/<cluster_id>')
@authenticate
@output(IBMKubernetesClusterOutSchema)
def get_kubernetes_cluster(cluster_id, user):
    """
    Get Kubernetes/Openshift cluster by cluster_id
    :param cluster_id:
    :param user: object of the user initiating the request
    :return: Response object from flask package
    """

    kubernetes_cluster = ibmdb.session.query(IBMKubernetesCluster).filter_by(
        id=cluster_id
    ).options(undefer("workloads")).join(IBMCloud).filter(
        IBMCloud.user_id == user["id"],
        IBMCloud.project_id == user["project_id"],
        IBMCloud.deleted.is_(False)
    ).first()
    if not kubernetes_cluster:
        message = f"IBM Kubernetes Cluster {cluster_id} does not exist"
        LOGGER.debug(message)
        abort(404, message)

    return kubernetes_cluster.to_json(workloads=True)


@ibm_kubernetes_clusters.get('/kubernetes_clusters')
@authenticate
@input(IBMVPCRegionalResourceListQuerySchema, location='query')
@input(PaginationQuerySchema, location='query')
@output(get_pagination_schema(IBMKubernetesClustersListOutSchema))
@doc(
    responses={
        204: "No records found"
    }
)
def list_kubernetes_clusters(vpc_regional_res_query_params, pagination_query_params, user):
    """
    List Kubernetes Cluster
    :param vpc_regional_res_query_params: get clusters in a selected vpc
    :param pagination_query_params:
    :param user: object of the user initiating the request
    :return: Response object from flask package
    """
    cloud_id = vpc_regional_res_query_params["cloud_id"]
    region_id = vpc_regional_res_query_params.get("region_id")
    vpc_id = vpc_regional_res_query_params.get("vpc_id")

    ibm_cloud = authorize_and_get_ibm_cloud(cloud_id=cloud_id, user=user)
    kubernetes_clusters_query = ibmdb.session.query(IBMKubernetesCluster).filter_by(cloud_id=cloud_id)

    if region_id:
        verify_and_get_region(ibm_cloud=ibm_cloud, region_id=region_id)
        kubernetes_clusters_query = kubernetes_clusters_query.filter_by(region_id=region_id)

    if vpc_id:
        kubernetes_clusters_query = kubernetes_clusters_query.filter_by(vpc_id=vpc_id)

    kubernetes_clusters_page = kubernetes_clusters_query.paginate(
        page=pagination_query_params["page"], per_page=pagination_query_params["per_page"], error_out=False
    )
    if not kubernetes_clusters_page.items:
        message = f"No IBM Kubernetes Clusters found for Cloud {cloud_id}"
        LOGGER.debug(message)
        return '', 204

    return get_paginated_response_json(
        items=[item.to_json() for item in kubernetes_clusters_page.items],
        pagination_obj=kubernetes_clusters_page
    )


@ibm_kubernetes_clusters.get('/kubernetes_clusters/cluster/<cluster_id>/worker_pools')
@authenticate
@input(IBMResourceQuerySchema, location='query')
@input(PaginationQuerySchema, location='query')
@output(get_pagination_schema(IBMKubernetesClusterWorkerPoolOutSchema))
def list_ibm_cluster_workerpools(cluster_id, res_query_params, pagination_query_params, user):
    """
    List Kubernetes/Openshift cluster workerpools by cluster_id
    :param cluster_id:
    :param res_query_params:
    :param pagination_query_params:
    :param user: object of the user initiating the request
    :return: Response from IBM Kubernetes workerpools
    """
    cloud_id = res_query_params["cloud_id"]
    authorize_and_get_ibm_cloud(cloud_id=cloud_id, user=user)

    cluster = ibmdb.session.query(IBMKubernetesCluster).filter_by(
        id=cluster_id,
        cloud_id=cloud_id
    ).first()

    if not cluster:
        message = f"No IBM Clusters found with ID {cluster_id}"
        LOGGER.debug(message)
        return message, 404

    worker_pools_query = ibmdb.session.query(IBMKubernetesClusterWorkerPool).filter_by(
        kubernetes_cluster_id=cluster_id,
    )

    worker_pools_page = worker_pools_query.paginate(
        page=pagination_query_params["page"], per_page=pagination_query_params["per_page"], error_out=False
    )

    if not worker_pools_page.items:
        message = f"No IBM Cluster workerpools found for cluster ID {cluster_id}"
        LOGGER.debug(message)
        return message, 204

    return get_paginated_response_json(
        items=[item.to_json() for item in worker_pools_page.items],
        pagination_obj=worker_pools_page
    )


@ibm_kubernetes_clusters.get('/kubernetes_clusters/worker_pools/<workerpool_id>')
@authenticate
@output(IBMKubernetesClusterWorkerPoolOutSchema)
def get_ibm_cluster_workerpool(workerpool_id, user):
    """
    Get Kubernetes/Openshift cluster workerpool by workerpool_id
    :param workerpool_id:
    :param user: object of the user initiating the request
    :return: Response from IBM Kubernetes workerpools
    """

    worker_pool = ibmdb.session.query(IBMKubernetesClusterWorkerPool).filter_by(
        id=workerpool_id
    ).join(IBMKubernetesCluster).join(IBMCloud).filter(
        IBMCloud.user_id == user["id"],
        IBMCloud.project_id == user["project_id"],
        IBMCloud.deleted.is_(False)
    ).first()

    if not worker_pool:
        message = f"No IBM Cluster workerpool found with workerpool ID {workerpool_id}"
        LOGGER.debug(message)
        return '', 404

    return worker_pool.to_json()


@ibm_kubernetes_clusters.delete('/kubernetes_clusters/<cluster_id>')
@authenticate
@log_activity
@output(WorkflowRootOutSchema, status_code=202)
def delete_ibm_cluster(cluster_id, user):
    """
    Delete an IBM Kubernetes Or Openshift Cluster
    :param cluster_id: cluster_id for cluster
    :param user: object of the user initiating the request
    :return: Response workflow root object
    """
    cluster = ibmdb.session.query(IBMKubernetesCluster).filter_by(
        id=cluster_id
    ).join(IBMCloud).filter(
        IBMCloud.user_id == user["id"],
        IBMCloud.project_id == user["project_id"],
        IBMCloud.deleted.is_(False)
    ).first()

    if not cluster:
        message = f"No IBM Kubernetes Cluster found with ID {cluster_id}"
        LOGGER.debug(message)
        abort(404)

    if cluster.status in [IBMKubernetesCluster.STATE_PENDING, IBMKubernetesCluster.STATE_DEPLOYING]:
        message = f"Unable to delete cluster {cluster_id}, cluster health not sufficient for deletion"
        LOGGER.debug(message)
        abort(400, message)

    workflow_root = compose_ibm_resource_deletion_workflow(
        user=user, resource_type=IBMKubernetesCluster,
        resource_id=cluster_id
    )

    return workflow_root.to_json(metadata=True)


@ibm_kubernetes_clusters.post('/kubernetes_clusters/kube_versions/sync')
@authenticate
@input(IBMResourceQuerySchema, location='query')
@output(WorkflowRootOutSchema)
def sync_orchestration_versions(res_query_params, user):
    """
    Sync latest Orchestration (Kubernetes/Openshift) Versions from IBM
    :param res_query_params:
    :param user: object of the user initiating the request
    :return: Response Workflow root object
    """

    cloud_id = res_query_params["cloud_id"]
    ibm_cloud = authorize_and_get_ibm_cloud(cloud_id=cloud_id, user=user)

    workflow_root_nature = "SYNC"
    workflow_name = "KubeVersions"

    sync_orchestration_versions_task = ibmdb.session.query(WorkflowRoot).filter(
        WorkflowRoot.user_id == user["id"],
        WorkflowRoot.workflow_name == workflow_name,
        WorkflowRoot.status.in_([WorkflowRoot.STATUS_PENDING,
                                 WorkflowRoot.STATUS_INITIATED,
                                 WorkflowRoot.STATUS_ON_HOLD,
                                 WorkflowRoot.STATUS_RUNNING])
    ).first()

    if sync_orchestration_versions_task:
        return sync_orchestration_versions_task.to_json(metadata=True)

    workflow_root = WorkflowRoot(
        user_id=user["id"],
        project_id=user["project_id"],
        workflow_name=workflow_name,
        workflow_nature=workflow_root_nature
    )

    data = {
        "resource_data": {
            "ibm_cloud": {
                "id": ibm_cloud.id
            }
        }
    }

    workflow_task = WorkflowTask(
        task_type=WorkflowTask.TYPE_SYNC,
        resource_type=workflow_name,
        task_metadata=data
    )

    workflow_root.add_next_task(workflow_task)
    ibmdb.session.add(workflow_root)
    ibmdb.session.commit()

    return workflow_root.to_json(metadata=True)


@ibm_kubernetes_clusters.post('/kubernetes_clusters/worker_flavors/zones/<zone_id>/sync')
@authenticate
@input(IBMResourceQuerySchema, location='query')
@output(WorkflowRootOutSchema, status_code=202)
def sync_cluster_worker_pool_zone_flavors(zone_id, res_query_params, user):
    """
    Sync Worker Machine Flavors of zones from IBM
    :param res_query_params:
    :param user: object of the user initiating the request
    :param zone_id:
    :return: Response object of workflow root
    """

    cloud_id = res_query_params["cloud_id"]
    ibm_cloud = authorize_and_get_ibm_cloud(cloud_id=cloud_id, user=user)

    workflow_root_nature = "SYNC"
    workflow_name = "ZoneFlavors"

    sync_zone_flavors_task = ibmdb.session.query(WorkflowRoot).filter(
        WorkflowRoot.user_id == user["id"],
        WorkflowRoot.workflow_name == workflow_name,
        WorkflowRoot.status.in_([WorkflowRoot.STATUS_PENDING,
                                 WorkflowRoot.STATUS_INITIATED,
                                 WorkflowRoot.STATUS_ON_HOLD,
                                 WorkflowRoot.STATUS_RUNNING])
    ).first()

    if sync_zone_flavors_task:
        return sync_zone_flavors_task.to_json(metadata=True)

    ibm_zone = verify_and_get_zone(cloud_id=cloud_id, zone_id=zone_id)

    workflow_root = WorkflowRoot(
        user_id=user["id"],
        project_id=user["project_id"],
        workflow_name=workflow_name,
        workflow_nature=workflow_root_nature
    )

    data = {
        "resource_data": {
            "ibm_cloud": {
                "id": ibm_cloud.id
            },
            "resource_json": {
                'zone': ibm_zone.name
            }
        }
    }

    workflow_task = WorkflowTask(
        task_type=WorkflowTask.TYPE_SYNC,
        resource_type=workflow_name,
        task_metadata=data
    )

    workflow_root.add_next_task(workflow_task)
    ibmdb.session.add(workflow_root)
    ibmdb.session.commit()

    return workflow_root.to_json(metadata=True)


@ibm_kubernetes_clusters.post('/kubernetes_clusters/worker_flavors/sync')
@authenticate
@input(IBMZonesList)
@output(WorkflowRootOutSchema, status_code=202)
def sync_cluster_worker_pool_flavors_by_zone(res_query_params, user):
    """
    Sync Worker Machine Flavors of zones for MZR
    :param res_query_params:
    :param user: object of the user initiating the request
    :param zone_id:
    :return: Response object of workflow root
    """

    cloud_id = res_query_params["ibm_cloud"]["id"]
    zones = res_query_params["zones"]

    ibm_cloud = authorize_and_get_ibm_cloud(cloud_id=cloud_id, user=user)
    zone_id_name_dict = dict()

    for zone in zones:
        ibm_zone = verify_and_get_zone(cloud_id=cloud_id, zone_id=zone)
        zone_id_name_dict[zone] = ibm_zone.name

    workflow_root_nature = "SYNC"
    workflow_name = "RegionalZoneFlavors"

    sync_zone_flavors_task = ibmdb.session.query(WorkflowRoot).filter(
        WorkflowRoot.user_id == user["id"],
        WorkflowRoot.workflow_name == workflow_name,
        WorkflowRoot.status.in_([WorkflowRoot.STATUS_PENDING,
                                 WorkflowRoot.STATUS_INITIATED,
                                 WorkflowRoot.STATUS_ON_HOLD,
                                 WorkflowRoot.STATUS_RUNNING])
    ).first()

    if sync_zone_flavors_task:
        flavor_task_zones = sync_zone_flavors_task.fe_request_data['resource_data']['resource_json']['zones']
        if zone_id_name_dict == flavor_task_zones:
            return sync_zone_flavors_task.to_json(metadata=True)

    data = {
        "resource_data": {
            "ibm_cloud": {
                "id": ibm_cloud.id
            },
            "resource_json": {
                'zones': zone_id_name_dict
            }
        }
    }

    workflow_root = WorkflowRoot(
        user_id=user["id"],
        project_id=user["project_id"],
        workflow_name=workflow_name,
        workflow_nature=workflow_root_nature,
        fe_request_data=data
    )

    workflow_task = WorkflowTask(
        task_type=WorkflowTask.TYPE_SYNC,
        resource_type=workflow_name,
        task_metadata=data
    )

    workflow_root.add_next_task(workflow_task)
    ibmdb.session.add(workflow_root)
    ibmdb.session.commit()

    return workflow_root.to_json(metadata=True)


@ibm_kubernetes_clusters.get('/kubernetes_clusters/<cluster_id>/workloads')
@authenticate
@input(IBMResourceQuerySchema, location='query')
@output(IBMKubernetesClusterWorkloadsOutSchema)
def get_ibm_cluster_workloads(cluster_id, res_query_params, user):
    """
    List Kubernetes/Openshift cluster workloads by cluster_id
    :param cluster_id:
    :param res_query_params:
    :param user: object of the user initiating the request
    :return: Response from IBM Kubernetes workloads
    """
    cloud_id = res_query_params["cloud_id"]
    authorize_and_get_ibm_cloud(cloud_id=cloud_id, user=user)

    cluster = ibmdb.session.query(IBMKubernetesCluster).filter_by(
        id=cluster_id,
        cloud_id=cloud_id
    ).options(undefer("workloads")).first()

    if not cluster:
        message = f"No IBM Clusters found with ID {cluster_id}"
        LOGGER.debug(message)
        return message, 404

    return cluster.to_json(workloads=True).workloads


@ibm_kubernetes_clusters.post('/kubernetes_clusters/<cluster_id>/workloads/sync')
@authenticate
@input(IBMResourceQuerySchema, location='query')
@output(IBMKubernetesClusterWorkloadsOutSchema, status_code=202)
def sync_ibm_cluster_workloads(cluster_id, res_query_params, user):
    """
    Sync Kubernetes/Openshift cluster workloads by cluster_id
    :param cluster_id:
    :param res_query_params:
    :param user: object of the user initiating the request
    :return: Response from IBM Kubernetes workloads
    """
    cloud_id = res_query_params["cloud_id"]
    ibm_cloud = authorize_and_get_ibm_cloud(cloud_id=cloud_id, user=user)

    cluster = ibmdb.session.query(IBMKubernetesCluster).filter_by(
        id=cluster_id,
        cloud_id=cloud_id
    ).first()

    if not cluster:
        message = f"No IBM Clusters found with ID {cluster_id}"
        LOGGER.debug(message)
        return message, 404

    data = {
        "ibm_cloud": {
            "id": ibm_cloud.id
        },
        "resource_json": {
            'cluster_resource_id': cluster.resource_id
        }
    }

    workflow_root = compose_ibm_sync_resource_workflow(
        user=user,
        resource_type=f"{IBMKubernetesCluster.__name__}_workloads",
        data=data
    )

    return workflow_root.to_json(metadata=True)


@ibm_kubernetes_clusters.post('/kubernetes_clusters/multizone_clusters/sync')
@authenticate
@input(IBMMultiZoneDiscoverySchema)
@output(WorkflowRootOutSchema, status_code=202)
def sync_classic_multizone_clusters(res_query_params, user):
    """
    Sync Multi zone Clusters for Migration
    :param res_query_params:
    :param user: object of the user initiating the request
    :return: Response object of workflow root
    """
    softlayer_cloud_id = res_query_params["softlayer_cloud"]["id"]
    ibm_cloud = res_query_params.get("ibm_cloud")

    if not ibm_cloud:
        abort(400, "IBM Cloud Id is required")

    authorize_and_get_ibm_cloud(cloud_id=ibm_cloud["id"], user=user)

    softlayer_cloud = ibmdb.session.query(SoftlayerCloud).filter_by(
        id=softlayer_cloud_id).first()

    if not softlayer_cloud:
        abort(400, "SOFTLAYER_CLOUD_NOT_FOUND")

    workflow_root_nature = "SYNC"
    workflow_name = "ClassicClusters"
    res_query_params["user"] = user

    workflow_root = WorkflowRoot(
        user_id=user["id"],
        project_id=user["project_id"],
        workflow_name=workflow_name,
        workflow_nature=workflow_root_nature,
        fe_request_data=res_query_params
    )

    kubernetes_task = WorkflowTask(
        task_type="SYNC_CLASSIC", resource_type=IBMKubernetesCluster.__name__,
        task_metadata={
            "resource_data": res_query_params
        }
    )

    workflow_root.add_next_task(kubernetes_task)
    ibmdb.session.add(workflow_root)
    ibmdb.session.commit()

    return workflow_root.to_json(metadata=True)
