import logging
from concurrent.futures import ProcessPoolExecutor, wait
from datetime import datetime, timedelta

from celery_singleton import Singleton
from ibm_cloud_sdk_core import ApiException

from config import MangosIBMGRPCClientConfigs
from ibm.common.clients.ibm_clients import ResourceInstancesClient
from ibm.common.consts import VALID
from ibm.discovery import celery_app, dispose_connection_pool, get_db_session
from ibm.discovery.common.consts import (
    IBM_BLOCK_STORAGE_VOLUMES, IBM_CLOUD_OBJECT_STORAGES,
    IBM_CLUSTER_NAMESPACE_PODS, IBM_CLUSTER_NAMESPACE_PVCS,
    IBM_CLUSTER_NAMESPACE_SVCS, IBM_CLUSTER_NAMESPACES, IBM_COS_ACCESS_KEYS,
    IBM_COS_BUCKETS, IBM_DEDICATED_HOST_DISKS, IBM_DEDICATED_HOST_GROUPS,
    IBM_DEDICATED_HOST_PROFILES, IBM_DEDICATED_HOSTS, IBM_ENDPOINT_GATEWAYS,
    IBM_FLOATING_IPS, IBM_IKE_POLICIES, IBM_IMAGES, IBM_INSTANCE_DISKS,
    IBM_INSTANCE_GROUP_MANAGER_ACTIONS, IBM_INSTANCE_GROUP_MANAGER_POLICIES,
    IBM_INSTANCE_GROUP_MANAGERS, IBM_INSTANCE_GROUP_MEMBERSHIPS,
    IBM_INSTANCE_GROUPS, IBM_INSTANCE_INIT_CONFIGS,
    IBM_INSTANCE_NETWORK_INTERFACES, IBM_INSTANCE_PROFILES, IBM_INSTANCE_TEMPLATES,
    IBM_INSTANCE_VOLUME_ATTACHMENTS, IBM_INSTANCES, IBM_IPSEC_POLICIES,
    IBM_KUBERNETES_CLUSTER_WORKER_POOLS, IBM_KUBERNETES_CLUSTERS,
    IBM_LOAD_BALANCER_LISTENERS, IBM_LOAD_BALANCER_POOL_MEMBERS,
    IBM_LOAD_BALANCER_POOLS, IBM_LOAD_BALANCERS, IBM_NETWORK_ACLS,
    IBM_OPERATING_SYSTEMS, IBM_PLACEMENT_GROUPS, IBM_PUBLIC_GATEWAYS, IBM_REGIONS,
    IBM_RESOURCE_GROUPS, IBM_SATELLITE_CLUSTER_KUBE_CONFIG, IBM_SATELLITE_CLUSTERS,
    IBM_SECURITY_GROUPS, IBM_SNAPSHOTS, IBM_SSH_KEYS, IBM_SUBNET_RESERVED_IPS,
    IBM_SUBNETS, IBM_TAGS, IBM_TRANSIT_GATEWAY_CONNECTIONS, IBM_TRANSIT_GATEWAYS,
    IBM_VOLUME_PROFILES, IBM_VPC_ADDRESS_PREFIXES, IBM_VPC_ROUTING_TABLES,
    IBM_VPCS, IBM_VPN_GATEWAY_CONNECTIONS, IBM_VPN_GATEWAYS, IBM_ZONES,
    STATUS_VALID
)
from ibm.discovery.tasks import (
    set_default_network_acls_and_security_groups, update_address_prefixes,
    update_cloud_object_storages, update_cluster_worker_pools, update_cluster_workloads,
    update_clusters, update_cos_access_keys, update_cos_buckets, update_dedicated_host_disks,
    update_dedicated_host_groups, update_dedicated_host_profiles, update_dedicated_hosts, update_endpoint_gateways,
    update_floating_ips, update_ike_policies, update_images, update_instance_disks,
    update_instance_group_manager_actions, update_instance_group_manager_policies,
    update_instance_group_managers, update_instance_group_memberships,
    update_instance_groups, update_instance_profiles, update_instance_templates,
    update_instance_volume_attachments, update_instances,
    update_instances_network_interfaces, update_instances_ssh_keys, update_ipsec_policies,
    update_lb_pool_members, update_load_balancer_listeners, update_load_balancer_pools,
    update_load_balancers, update_load_balancers_listeners_default_pool,
    update_network_acls, update_operating_systems, update_placement_groups,
    update_public_gateways, update_regions, update_resource_groups,
    update_satellite_cluster_kube_configs, update_satellite_clusters,
    update_security_groups, update_snapshots, update_ssh_keys, update_subnet_reserved_ips,
    update_subnets, update_tags, update_transit_gateway_connections,
    update_transit_gateways, update_volume_profiles, update_volumes, update_vpc_networks,
    update_vpc_routes, update_vpn_connections, update_vpn_gateways, update_zones
)
from ibm.discovery.tasks.idle_resource_tasks import update_idle_resources
from ibm.models import DiscoveryController, IBMCloud, IBMCloudSetting, IBMCost, IBMInstance, IBMRegion, \
    IBMResourceControllerData, IBMResourceInstancesCost, WorkflowRoot, WorkflowTask
from mangos_grpc_client.ibm import create_mangos_client
from mangos_grpc_client.ibm.exceptions import MangosGRPCError, MangosIBMCloudNotFoundError, MangosIBMCloudNotSyncedError

LOGGER = logging.getLogger(__name__)


@celery_app.task(name="ibm_discovery_initiator", queue="ibm_discovery_initiator_queue", base=Singleton, lock_expiry=300)
def ibm_discovery_initiator():
    """
    Load all IBM Clouds and fire their discovery
    spawns
    """
    with get_db_session() as session:
        ibm_clouds = session.query(IBMCloud).filter_by(status=STATUS_VALID, deleted=False).all()
        for ibm_cloud in ibm_clouds:
            LOGGER.info(f"Delaying discovery executor task for cloud: {ibm_cloud.id} name: {ibm_cloud.name}")
            ibm_discovery_executor.delay(ibm_cloud.id)
            update_resource_catalog.delay(ibm_cloud.id)


@celery_app.task(name="ibm_discovery_executor", queue="ibm_discovery_executor_queue", base=Singleton, lock_expiry=3600)
def ibm_discovery_executor(cloud_id):
    LOGGER.info(f"Discovery executor task received for cloud: {cloud_id}")
    start_time = datetime.utcnow()
    with get_db_session() as session:
        ibm_cloud = session.query(IBMCloud).filter_by(id=cloud_id).first()
        if not ibm_cloud:
            return

        api_key_id = ibm_cloud.api_key_id
        cloud_name = ibm_cloud.name

    mangos = create_mangos_client(MangosIBMGRPCClientConfigs)
    try:

        cloud_resources = mangos.get_resources(filterable_parent_resource_id=api_key_id, api_key_id=api_key_id)
        mangos.channel.close()
    except (MangosGRPCError, MangosIBMCloudNotFoundError, MangosIBMCloudNotSyncedError) as ex:
        if isinstance(ex, MangosIBMCloudNotFoundError):
            with get_db_session() as session:
                ibm_cloud = session.query(IBMCloud).filter_by(id=cloud_id).first()
                if not ibm_cloud:
                    return
                ibm_cloud.added_in_mangos = False
                session.commit()

        LOGGER.info(
            f"Mangos get_resources call in ibm_discovery_executor task failed for cloud: {cloud_id} name: "
            f"{cloud_name}, trace: {ex}")
        mangos.channel.close()
        return

    resources = dict()
    for cloud_resource in cloud_resources:
        if cloud_resource["resource_type"] not in resources:
            resources[cloud_resource["resource_type"]] = list()

        if cloud_resource.get("response"):
            resources[cloud_resource["resource_type"]].append(cloud_resource["response"])

    update_resource_groups(cloud_id, resources.get(IBM_RESOURCE_GROUPS, []))
    update_tags(cloud_id, resources.get(IBM_TAGS, []))
    update_cloud_object_storages(cloud_id, resources.get(IBM_CLOUD_OBJECT_STORAGES, []))
    update_cos_buckets(cloud_id, resources.get(IBM_COS_BUCKETS, []))
    update_cos_access_keys(cloud_id, resources.get(IBM_COS_ACCESS_KEYS, []))
    update_regions(cloud_id, resources.get(IBM_REGIONS, []))
    update_satellite_clusters(cloud_id, resources.get(IBM_SATELLITE_CLUSTERS, []))
    update_satellite_cluster_kube_configs(cloud_id, resources.get(IBM_SATELLITE_CLUSTER_KUBE_CONFIG, []))
    update_transit_gateways(cloud_id, resources.get(IBM_TRANSIT_GATEWAYS, []))
    update_transit_gateway_connections(cloud_id, resources.get(IBM_TRANSIT_GATEWAY_CONNECTIONS, []))

    pending_process_tasks = set()
    region_names = list()
    with get_db_session() as session:
        db_regions = session.query(IBMRegion).filter_by(cloud_id=cloud_id).all()

        for db_region in db_regions:
            region_names.append(db_region.name)

    with ProcessPoolExecutor(initializer=dispose_connection_pool) as process_executor:
        for region_name in region_names:
            pending_process_tasks.add(process_executor.submit(ibm_run_region_discovery, cloud_id, region_name))

        wait(pending_process_tasks)

    dispose_connection_pool()

    LOGGER.info(
        f"\n{'*' * 100}\nDiscovery completed for cloud: {cloud_id} name: {cloud_name} in "
        f"{(datetime.utcnow() - start_time).total_seconds()} seconds.\n{'*' * 100}")


def ibm_run_region_discovery(cloud_id, region_name):
    LOGGER.info(f"Discovery worker task received for cloud: {cloud_id} and region_name: {region_name}")

    start_time = datetime.utcnow()
    with get_db_session() as session:
        ibm_cloud = session.query(IBMCloud).filter_by(id=cloud_id).first()
        if not ibm_cloud:
            return

        ibm_cloud_settings = session.query(IBMCloudSetting).filter_by(cloud_id=cloud_id).first()
        cost_optimization_enabled = ibm_cloud_settings.cost_optimization_enabled if ibm_cloud_settings else False

        api_key_id = ibm_cloud.api_key_id
        cloud_name = ibm_cloud.name
        project_id = ibm_cloud.project_id
        user_id = ibm_cloud.user_id
        region = session.query(IBMRegion).filter_by(name=region_name, cloud_id=cloud_id).first()
        if not region:
            return

        region_id = region.id
        monitoring_enabled = True if region.monitoring_token else False
        monitoring = region.monitoring_token
        monitoring_status = monitoring.status if monitoring else None

    mangos = create_mangos_client(MangosIBMGRPCClientConfigs)

    try:
        region_resources = mangos.get_resources(
            filterable_parent_resource_id=region_name, api_key_id=api_key_id)
        mangos.channel.close()
    except (MangosGRPCError, MangosIBMCloudNotFoundError, MangosIBMCloudNotSyncedError) as ex:
        if isinstance(ex, MangosIBMCloudNotFoundError):
            with get_db_session() as session:
                ibm_cloud = session.query(IBMCloud).filter_by(id=cloud_id).first()
                if not ibm_cloud:
                    return

                ibm_cloud.added_in_mangos = False
                session.commit()

        LOGGER.info(
            f"Mangos get_resources call in ibm_run_region_discovery task failed for cloud: {cloud_id} name: "
            f"{cloud_name}, region_name: {region_name}, trace: {ex}")
        mangos.channel.close()
        return
    except Exception as e:
        LOGGER.exception(f"Exception in mangos call for region {region_name} and cloud {cloud_id}. Trace: {e}")
        mangos.channel.close()
        return

    try:
        resources = dict()
        for region_resource in region_resources:
            if region_resource["resource_type"] not in resources:
                resources[region_resource["resource_type"]] = list()

            if region_resource.get("response"):
                resources[region_resource["resource_type"]].append(region_resource["response"])

        LOGGER.info(
            f"** Running discovery for Region: **{region_name}** Cloud ID: **{cloud_id}** Cloud Name: **{cloud_name}**")

        update_zones(cloud_id, region_name, resources.get(IBM_ZONES, []))
        update_ssh_keys(cloud_id, region_name, resources.get(IBM_SSH_KEYS, []))
        update_vpc_networks(cloud_id, region_name, resources.get(IBM_VPCS, []))
        update_address_prefixes(cloud_id, region_name, resources.get(IBM_VPC_ADDRESS_PREFIXES, []))
        update_vpc_routes(cloud_id, region_name, resources.get(IBM_VPC_ROUTING_TABLES, []))
        update_network_acls(cloud_id, region_name, resources.get(IBM_NETWORK_ACLS, []))
        update_security_groups(cloud_id, region_name, resources.get(IBM_SECURITY_GROUPS, []))
        set_default_network_acls_and_security_groups(cloud_id, region_name, resources.get(IBM_VPCS, []))
        update_operating_systems(cloud_id, region_name, resources.get(IBM_OPERATING_SYSTEMS, []))
        update_images(cloud_id, region_name, resources.get(IBM_IMAGES, []))
        update_instance_profiles(cloud_id, region_name, resources.get(IBM_INSTANCE_PROFILES, []))
        update_volume_profiles(cloud_id, region_name, resources.get(IBM_VOLUME_PROFILES, []))
        update_volumes(cloud_id, region_name, resources.get(IBM_BLOCK_STORAGE_VOLUMES, []))
        update_public_gateways(cloud_id, region_name, resources.get(IBM_PUBLIC_GATEWAYS, []))
        update_subnets(cloud_id, region_name, resources.get(IBM_SUBNETS, []))
        update_subnet_reserved_ips(cloud_id, region_name, resources.get(IBM_SUBNET_RESERVED_IPS, []))
        update_instances(cloud_id, region_name, resources.get(IBM_INSTANCES, []))
        update_instances_ssh_keys(cloud_id, region_name, resources.get(IBM_INSTANCE_INIT_CONFIGS, []))
        update_instances_network_interfaces(cloud_id, region_name, resources.get(IBM_INSTANCE_NETWORK_INTERFACES, []))
        update_instance_volume_attachments(cloud_id, region_name, resources.get(IBM_INSTANCE_VOLUME_ATTACHMENTS, []))
        update_instance_disks(cloud_id, region_name, resources.get(IBM_INSTANCE_DISKS, []))
        update_floating_ips(cloud_id, region_name, resources.get(IBM_FLOATING_IPS, []))
        # update_load_balancer_profiles(m_resources.get("IBM_LOAD_BALANCER_PROFILES", []))
        update_load_balancers(cloud_id, region_name, resources.get(IBM_LOAD_BALANCERS, []))
        update_load_balancer_listeners(cloud_id, region_name, resources.get(IBM_LOAD_BALANCER_LISTENERS, []))
        update_load_balancer_pools(cloud_id, region_name, resources.get(IBM_LOAD_BALANCER_POOLS, []))
        update_load_balancers_listeners_default_pool(cloud_id, region_name,
                                                     resources.get(IBM_LOAD_BALANCER_LISTENERS, []))
        update_lb_pool_members(cloud_id, region_name, resources.get(IBM_LOAD_BALANCER_POOL_MEMBERS, []))
        update_ike_policies(cloud_id, region_name, resources.get(IBM_IKE_POLICIES, []))
        update_ipsec_policies(cloud_id, region_name, resources.get(IBM_IPSEC_POLICIES, []))
        update_vpn_gateways(cloud_id, region_name, resources.get(IBM_VPN_GATEWAYS, []))
        update_vpn_connections(cloud_id, region_name, resources.get(IBM_VPN_GATEWAY_CONNECTIONS, []))
        update_dedicated_host_profiles(cloud_id, region_name, resources.get(IBM_DEDICATED_HOST_PROFILES, []))
        update_dedicated_host_groups(cloud_id, region_name, resources.get(IBM_DEDICATED_HOST_GROUPS, []))
        update_dedicated_hosts(cloud_id, region_name, resources.get(IBM_DEDICATED_HOSTS, []))
        update_dedicated_host_disks(cloud_id, region_name, resources.get(IBM_DEDICATED_HOST_DISKS, []))
        update_placement_groups(cloud_id, region_name, resources.get(IBM_PLACEMENT_GROUPS, []))
        update_instance_groups(cloud_id, region_name, resources.get(IBM_INSTANCE_GROUPS, []))
        update_instance_group_managers(cloud_id, region_name, resources.get(IBM_INSTANCE_GROUP_MANAGERS, []))
        update_instance_group_manager_actions(cloud_id, region_name,
                                              resources.get(IBM_INSTANCE_GROUP_MANAGER_ACTIONS, []))
        update_instance_group_manager_policies(
            cloud_id, region_name, resources.get(IBM_INSTANCE_GROUP_MANAGER_POLICIES, [])
        )
        update_instance_group_memberships(cloud_id, region_name, resources.get(IBM_INSTANCE_GROUP_MEMBERSHIPS, []))
        update_instance_templates(cloud_id, region_name, resources.get(IBM_INSTANCE_TEMPLATES, []))
        update_endpoint_gateways(cloud_id, region_name, resources.get(IBM_ENDPOINT_GATEWAYS, []))
        update_snapshots(cloud_id, region_name, resources.get(IBM_SNAPSHOTS, []))
        update_clusters(cloud_id, region_name, resources.get(IBM_KUBERNETES_CLUSTERS, []))
        update_cluster_worker_pools(cloud_id, region_name, resources.get(IBM_KUBERNETES_CLUSTER_WORKER_POOLS, []))
        update_cluster_workloads(
            cloud_id, region_name, resources.get(IBM_CLUSTER_NAMESPACES, []),
            resources.get(IBM_CLUSTER_NAMESPACE_PVCS, []),
            resources.get(IBM_CLUSTER_NAMESPACE_PODS, []), resources.get(IBM_CLUSTER_NAMESPACE_SVCS, [])
        )
        LOGGER.info(
            f"** IBM Region {region_name}** Cloud ID: **{cloud_id}** Cloud Name: **{cloud_name}** synced in: "
            f"{(datetime.utcnow() - start_time).total_seconds()} seconds")

        if not cost_optimization_enabled:
            return

        update_idle_resources(cloud_id, region_name)

        if not monitoring_enabled or (monitoring_enabled and monitoring_status != VALID):
            LOGGER.info(f"Monitoring not enabled for region {region_name}")
            return

        with get_db_session() as session:
            existing_root = session.query(WorkflowRoot).filter_by(
                project_id=project_id,
                user_id=user_id,
                workflow_name=f"{cloud_id}_{region_id}_VSI_USAGE",
                workflow_nature="DISCOVERY"
            ).filter(
                WorkflowRoot.status.in_([WorkflowRoot.STATUS_RUNNING, WorkflowRoot.STATUS_PENDING,
                                         WorkflowRoot.STATUS_INITIATED, WorkflowRoot.STATUS_C_SUCCESSFULLY_WFC,
                                         WorkflowRoot.STATUS_C_W_FAILURE_WFC, WorkflowRoot.STATUS_ON_HOLD])
            ).first()
            if existing_root:
                return

            existing_completed_roots = session.query(WorkflowRoot).filter_by(
                project_id=project_id,
                user_id=user_id,
                workflow_name=f"{cloud_id}_{region_id}_VSI_USAGE",
                workflow_nature="DISCOVERY"
            ).filter(
                WorkflowRoot.status.in_([WorkflowRoot.STATUS_C_SUCCESSFULLY, WorkflowRoot.STATUS_C_W_FAILURE])
            ).all()
            for existing_completed_root in existing_completed_roots:
                if existing_completed_root.status == WorkflowRoot.STATUS_C_W_FAILURE:
                    session.delete(existing_completed_root)
                    session.commit()
                    continue

                able_to_restart = datetime.utcnow() - timedelta(hours=24) >= existing_completed_root.completed_at
                if existing_completed_root.status == WorkflowRoot.STATUS_C_SUCCESSFULLY and not able_to_restart:
                    return

            workflow_root = WorkflowRoot(
                project_id=project_id,
                user_id=user_id,
                workflow_name=f"{cloud_id}_{region_id}_VSI_USAGE",
                workflow_nature="DISCOVERY"
            )
            workflow_root.add_next_task(WorkflowTask(
                task_type=IBMInstance.TYPE_IDLE, resource_type=IBMInstance.__name__,
                resource_id=region_id
            ))
            callback_workflow_root = WorkflowRoot(
                project_id=project_id,
                user_id=user_id,
                workflow_nature=IBMInstance.TYPE_MONITORING,
                root_type=WorkflowRoot.ROOT_TYPE_ON_COMPLETE
            )
            monitoring_task = WorkflowTask(
                resource_type=IBMInstance.TYPE_MONITORING, task_type=IBMInstance.__name__,
                resource_id=region_id)
            callback_workflow_root.add_next_task(monitoring_task)
            workflow_root.add_callback_root(callback_workflow_root)

            session.add(workflow_root)
            session.commit()

    except Exception as e:
        LOGGER.exception(f"Exception in discovery for region {region_name} and cloud {cloud_id}. Trace: {e}")


@celery_app.task(name="update_resource_catalog", queue="ibm_discovery_worker_queue", base=Singleton, lock_expiry=3600)
def update_resource_catalog(cloud_id):
    with get_db_session() as session:
        ibm_cloud = session.query(IBMCloud).filter_by(id=cloud_id).first()
        if not ibm_cloud:
            return

    with get_db_session() as session:
        # Fetch Discovery Controller entry for resource controller api, if flag is set to True then will fetch complete
        # data from resource controller api
        discovery_controller_db_obj = \
            session.query(DiscoveryController).filter_by(service_name=DiscoveryController.SERVICE_NAME_KEY).first()
        discovery_controller_flag = discovery_controller_db_obj.flag
        # Fetch count from resource controller database table, if there is no entry then will fetch complete data from
        # resource controller api
        resource_controlller_db_count = session.query(IBMResourceControllerData).filter_by(cloud_id=cloud_id).count()
        fetch_full_data = discovery_controller_flag or not resource_controlller_db_count
        updated_from = None
        if not fetch_full_data:
            updated_from = (datetime.utcnow() - timedelta(hours=24)).strftime("%Y-%m-%dT%H:%M:%S")
            updated_from = f"{updated_from}.000Z"

    try:
        resource_instances_client = ResourceInstancesClient(cloud_id=cloud_id)
        m_resource_catalog = resource_instances_client.list_resource_instances(updated_from=updated_from)

    except (ApiException, ConnectionError) as ex:
        LOGGER.info(ex)
        return

    except Exception as ex:
        LOGGER.info(f"{ex},{type(ex)},{cloud_id}")
        return

    start_time = datetime.utcnow()
    if not m_resource_catalog:
        return

    m_resource_catalog = m_resource_catalog
    with get_db_session() as session:
        cost_sq = session.query(IBMCost.id).filter_by(cloud_id=cloud_id).order_by(IBMCost.billing_month.desc()). \
            limit(2).subquery()
        resource_instances_obj = session.query(IBMResourceInstancesCost).filter(
            IBMResourceInstancesCost.cost_id.in_(session.query(cost_sq))).all()

        resource_crns = []
        for resource_instance_obj in resource_instances_obj:
            resource_crns.append(resource_instance_obj.crn)

    resource_catalogs = list()
    resource_catalog_crn = set()

    for resource_catalog in m_resource_catalog:
        if resource_catalog["resource_id"] in IBMResourceControllerData.RESOURCE_TYPE_LIST or \
                resource_catalog['id'] in resource_crns:
            r_catalog = IBMResourceControllerData.from_ibm_json_body(json_body=resource_catalog)
            resource_catalogs.append(r_catalog)
            resource_catalog_crn.add(r_catalog.crn)

    with get_db_session() as db_session:
        with db_session.no_autoflush:
            cloud = db_session.query(IBMCloud).filter_by(id=cloud_id).first()
            assert cloud

            db_session.commit()
            for resource_catalog in resource_catalogs:
                db_resource_catalog = db_session.query(IBMResourceControllerData).filter_by(
                    cloud_id=cloud_id, crn=resource_catalog.crn
                ).first()
                resource_catalog.dis_add_update_db(
                    db_session=db_session, db_resource_catalog=db_resource_catalog, db_cloud=cloud
                )

            db_session.commit()

    if discovery_controller_flag:
        with get_db_session() as session:
            discovery_controller_db_obj = \
                session.query(DiscoveryController).filter_by(service_name=DiscoveryController.SERVICE_NAME_KEY).first()
            discovery_controller_db_obj.flag = False
            session.commit()

    LOGGER.info("** Resource Controller Data synced in:{}".format((datetime.utcnow() - start_time).total_seconds()))
