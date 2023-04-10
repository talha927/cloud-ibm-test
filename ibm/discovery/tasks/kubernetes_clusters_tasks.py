import logging
from datetime import datetime

from ibm.discovery import get_db_session
from ibm.discovery.common.utils import discovery_locked_resource
from ibm.models import IBMCloud, IBMKubernetesCluster, IBMKubernetesClusterWorkerPool, \
    IBMKubernetesClusterWorkerPoolZone, IBMRegion, IBMResourceGroup, IBMResourceLog, IBMSubnet, IBMVpcNetwork

LOGGER = logging.getLogger(__name__)


def update_clusters(cloud_id, region_name, m_clusters):
    if not m_clusters:
        return

    start_time = datetime.utcnow()

    clusters = list()
    clusters_ids = list()
    clusters_id_rgid_dict = dict()
    clusters_vpc_id_dict = dict()
    locked_rid_status = dict()

    for m_cluster_list in m_clusters:
        for m_cluster in m_cluster_list.get('response', []):
            cluster = IBMKubernetesCluster.from_ibm_json_body(json_body=m_cluster)
            # TODO: we should add resources in whatever condition they are
            if not len(str(cluster.ingress.get('hostname')).strip()) > 10:
                continue

            clusters_id_rgid_dict[cluster.resource_id] = m_cluster["resourceGroup"]
            clusters_vpc_id_dict[cluster.resource_id] = m_cluster["vpcs"][0]
            clusters.append(cluster)
            clusters_ids.append(cluster.resource_id)

        with get_db_session() as session:
            db_region = session.query(IBMRegion).filter_by(name=region_name, cloud_id=cloud_id).first()
            if not db_region:
                LOGGER.info(f"IBMRegion {region_name} not found")
                return

            last_synced_at = m_cluster_list["last_synced_at"]
            logged_resource = discovery_locked_resource(
                session=session, resource_type=IBMKubernetesCluster.__name__, cloud_id=cloud_id,
                sync_start=last_synced_at, region=db_region)
            locked_rid_status.update(logged_resource)

    with get_db_session() as session:
        with session.no_autoflush:
            db_cloud = session.query(IBMCloud).get(cloud_id)
            assert db_cloud

            db_region = session.query(IBMRegion).filter_by(name=region_name, cloud_id=cloud_id).first()
            if not db_region:
                LOGGER.info(f"IBMRegion {region_name} not found")
                return

            region_id = db_region.id

            db_clusters = session.query(IBMKubernetesCluster).filter_by(
                region_id=region_id, cloud_id=cloud_id
            ).all()

            for db_cluster in db_clusters:
                if locked_rid_status.get(db_cluster.resource_id) in [IBMResourceLog.STATUS_ADDED,
                                                                     IBMResourceLog.STATUS_UPDATED]:
                    continue

                if db_cluster.resource_id not in clusters_ids:
                    session.delete(db_cluster)

            session.commit()

            db_clusters = session.query(IBMKubernetesCluster).filter_by(
                region_id=region_id, cloud_id=cloud_id
            ).all()

            db_resource_groups = session.query(IBMResourceGroup).filter_by(cloud_id=cloud_id).all()
            db_resource_group_id_obj_dict = {
                db_resource_group.resource_id: db_resource_group for db_resource_group in db_resource_groups
            }

            for cluster in clusters:
                if locked_rid_status.get(cluster.resource_id) in [IBMResourceLog.STATUS_DELETED,
                                                                  IBMResourceLog.STATUS_UPDATED]:
                    continue

                vpc_network = session.query(IBMVpcNetwork).filter_by(
                    cloud_id=cloud_id,
                    resource_id=clusters_vpc_id_dict[cluster.resource_id]
                ).first()

                if not vpc_network:
                    LOGGER.info(
                        f"Vpc Network with resource id {clusters_vpc_id_dict[cluster.resource_id]} not found in DB")
                    continue

                cluster.dis_add_update_db(
                    session=session, db_clusters=db_clusters, db_cloud=db_cloud,
                    db_resource_group=db_resource_group_id_obj_dict.get(clusters_id_rgid_dict[cluster.resource_id]),
                    db_region=db_region,
                    db_vpc=vpc_network
                )

            session.commit()

    LOGGER.info("** Clusters synced in:{}".format((datetime.utcnow() - start_time).total_seconds()))


def update_cluster_worker_pools(cloud_id, region_name, m_cluster_worker_pools):
    if not m_cluster_worker_pools:
        return

    start_time = datetime.utcnow()

    cluster_worker_pools = list()
    cluster_worker_pool_ids = list()
    cluster_id_rgid_dict = dict()
    locked_rid_status = dict()
    cluster_worker_pool_zones_dict = dict()

    for m_cluster_worker_pool_list in m_cluster_worker_pools:
        for m_cluster_worker_pool in m_cluster_worker_pool_list.get("response", []):
            cluster_workerpool = IBMKubernetesClusterWorkerPool.from_ibm_json_body(json_body=m_cluster_worker_pool)
            cluster_id_rgid_dict[cluster_workerpool.resource_id] = m_cluster_worker_pool["id"].split("-")[0]

            cluster_worker_pool_zones_dict[cluster_workerpool.resource_id] = m_cluster_worker_pool['zones']

            cluster_worker_pools.append(cluster_workerpool)
            cluster_worker_pool_ids.append(cluster_workerpool.resource_id)

        with get_db_session() as session:
            db_region = session.query(IBMRegion).filter_by(name=region_name, cloud_id=cloud_id).first()
            if not db_region:
                LOGGER.info(f"IBMRegion {region_name} not found")
                return

            last_synced_at = m_cluster_worker_pool_list["last_synced_at"]
            logged_resource = discovery_locked_resource(
                session=session, resource_type=IBMKubernetesClusterWorkerPool.__name__, cloud_id=cloud_id,
                sync_start=last_synced_at, region=db_region)
            locked_rid_status.update(logged_resource)

    with get_db_session() as session:
        with session.no_autoflush:
            db_cloud = session.query(IBMCloud).get(cloud_id)
            assert db_cloud

            db_region = session.query(IBMRegion).filter_by(name=region_name, cloud_id=cloud_id).first()
            if not db_region:
                LOGGER.info(f"IBMRegion {region_name} not found")
                return

            region_id = db_region.id

            db_cluster_worker_pools = session.query(IBMKubernetesClusterWorkerPool).join(
                IBMKubernetesCluster).filter_by(
                region_id=region_id
            ).all()

            for db_cluster_worker_pool in db_cluster_worker_pools:
                if locked_rid_status.get(db_cluster_worker_pool.resource_id) in [IBMResourceLog.STATUS_ADDED,
                                                                                 IBMResourceLog.STATUS_UPDATED]:
                    continue

                if db_cluster_worker_pool.resource_id not in cluster_worker_pool_ids:
                    session.delete(db_cluster_worker_pool)

            session.commit()

            db_cluster_worker_pools = session.query(IBMKubernetesClusterWorkerPool).join(
                IBMKubernetesCluster).filter_by(
                region_id=region_id
            ).all()

            for cluster_worker_pool in cluster_worker_pools:
                if locked_rid_status.get(cluster_worker_pool.resource_id) in [IBMResourceLog.STATUS_DELETED,
                                                                              IBMResourceLog.STATUS_UPDATED]:
                    continue

                cluster = session.query(IBMKubernetesCluster).filter_by(
                    region_id=region_id,
                    resource_id=cluster_id_rgid_dict[cluster_worker_pool.resource_id]
                ).first()
                if not cluster:
                    LOGGER.info(
                        f"Cluster with resource id {cluster_id_rgid_dict[cluster_worker_pool.resource_id]} not found "
                        f"in DB")
                    continue

                worker_pool = cluster_worker_pool.dis_add_update_db(
                    session=session,
                    db_cluster_worker_pools=db_cluster_worker_pools,
                    existing_cluster=cluster
                )
                session.commit()

                # Syncing worker pool zones
                cluster_worker_pool_zones = list()
                cluster_worker_pool_zone_names = set()
                cluster_worker_pool_zone_subnet_rid = dict()
                for worker_pool_zone in cluster_worker_pool_zones_dict.get(cluster_worker_pool.resource_id, []):
                    workerpool_zone_obj = IBMKubernetesClusterWorkerPoolZone.from_ibm_json_body(
                        json_body=worker_pool_zone)

                    cluster_worker_pool_zone_subnet_rid[workerpool_zone_obj.name] = worker_pool_zone["subnets"][0]["id"]
                    cluster_worker_pool_zones.append(workerpool_zone_obj)
                    cluster_worker_pool_zone_names.add(workerpool_zone_obj.name)

                db_worker_pool_zones = worker_pool.worker_zones.all()
                for db_worker_pool_zone in db_worker_pool_zones:
                    if db_worker_pool_zone.name not in cluster_worker_pool_zone_names:
                        session.delete(db_worker_pool_zone)

                session.commit()

                db_worker_pool_zones = worker_pool.worker_zones.all()
                db_worker_pool_zones_name_dict = {
                    db_worker_pool_zone.name: db_worker_pool_zone for db_worker_pool_zone in db_worker_pool_zones
                }

                for cluster_worker_pool_zone in cluster_worker_pool_zones:
                    if cluster_worker_pool_zone.name in db_worker_pool_zones_name_dict:
                        continue

                    existing_subnet = session.query(IBMSubnet).filter_by(
                        region_id=region_id,
                        resource_id=cluster_worker_pool_zone_subnet_rid[cluster_worker_pool_zone.name]
                    ).first()
                    if not existing_subnet:
                        LOGGER.info(
                            f"Subnet with resource id "
                            f"{cluster_worker_pool_zone_subnet_rid[cluster_worker_pool_zone.name]} not found in DB")
                        continue

                    cluster_worker_pool_zone.ibm_kubernetes_cluster_worker_pools = worker_pool
                    cluster_worker_pool_zone.subnets.append(existing_subnet)
                    session.commit()

    LOGGER.info("** Cluster Worker Pools synced in:{}".format((datetime.utcnow() - start_time).total_seconds()))


def update_cluster_workloads(cloud_id, region_name, m_cluster_namespaces, m_cluster_pvcs, m_cluster_pods,
                             m_cluster_svcs):
    start_time = datetime.utcnow()
    cluster_rid_workloads = dict()
    for m_cluster_namespaces_list in m_cluster_namespaces:
        for cluster_namespace in m_cluster_namespaces_list.get("response", []):
            if cluster_namespace["cluster_rid"] not in cluster_rid_workloads:
                cluster_rid_workloads[cluster_namespace["cluster_rid"]] = list()

            namespace_workload = {
                "namespace": cluster_namespace["namespace"],
                "pod": [],
                "svc": [],
                "pvc": [],
                "cluster_rid": cluster_namespace["cluster_rid"]
            }

            for m_cluster_pods_list in m_cluster_pods:
                for cluster_pod in m_cluster_pods_list.get("response", []):
                    if cluster_pod["namespace"] == cluster_namespace["namespace"] and cluster_pod["cluster_rid"] == \
                            cluster_namespace["cluster_rid"]:
                        namespace_workload["pod"].append(cluster_pod["pod"])

            for m_cluster_svcs_list in m_cluster_svcs:
                for cluster_svc in m_cluster_svcs_list.get("response", []):
                    if cluster_svc["namespace"] == cluster_namespace["namespace"] and cluster_svc["cluster_rid"] == \
                            cluster_namespace["cluster_rid"]:
                        namespace_workload["svc"].append(cluster_svc["svc"])

            for m_cluster_pvcs_list in m_cluster_pvcs:
                for cluster_pvc in m_cluster_pvcs_list.get("response", []):
                    if cluster_pvc["namespace"] == cluster_namespace["namespace"] and cluster_pvc["cluster_rid"] == \
                            cluster_namespace["cluster_rid"]:
                        namespace_workload["pvc"].append(cluster_pvc)

            cluster_rid_workloads[cluster_namespace["cluster_rid"]].append(namespace_workload)

    with get_db_session() as session:
        db_region = session.query(IBMRegion).filter_by(
            name=region_name, cloud_id=cloud_id).first()
        if not db_region:
            LOGGER.info(f"IBMRegion {region_name} not found")
            return

        region_id = db_region.id

        db_clusters = session.query(IBMKubernetesCluster).filter_by(region_id=region_id, cloud_id=cloud_id).all()
        db_cluster_rid_workloads = {db_cluster.resource_id: db_cluster for db_cluster in db_clusters}

        for db_cluster_rid in db_cluster_rid_workloads:
            if db_cluster_rid in cluster_rid_workloads:
                db_cluster_rid_workloads[db_cluster_rid].workloads = cluster_rid_workloads[db_cluster_rid]
            else:
                db_cluster_rid_workloads[db_cluster_rid].workloads = list()

            session.commit()

    LOGGER.info("** Cluster Workloads synced in:{}".format((datetime.utcnow() - start_time).total_seconds()))
