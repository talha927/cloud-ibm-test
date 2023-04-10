import logging
from datetime import datetime

from ibm.discovery import get_db_session
from ibm.discovery.common.utils import discovery_locked_resource
from ibm.models import IBMCloud, IBMSatelliteCluster, IBMResourceGroup, IBMResourceLog

LOGGER = logging.getLogger(__name__)


def update_satellite_clusters(cloud_id, m_clusters):
    if not m_clusters:
        return

    start_time = datetime.utcnow()

    clusters = list()
    clusters_ids = list()
    clusters_id_rgid_dict = dict()
    locked_rid_status = dict()

    for m_cluster_list in m_clusters:
        for m_cluster in m_cluster_list.get('response', []):
            cluster = IBMSatelliteCluster.from_ibm_json_body(json_body=m_cluster)
            # TODO: we should add resources in whatever condition they are
            if not len(str(cluster.ingress.get('hostname')).strip()) > 10:
                continue

            clusters_id_rgid_dict[cluster.resource_id] = m_cluster["resourceGroup"]
            clusters.append(cluster)
            clusters_ids.append(cluster.resource_id)

        with get_db_session() as session:
            last_synced_at = m_cluster_list["last_synced_at"]
            logged_resource = discovery_locked_resource(
                session=session, resource_type=IBMSatelliteCluster.__name__, cloud_id=cloud_id,
                sync_start=last_synced_at)
            locked_rid_status.update(logged_resource)

    with get_db_session() as session:
        with session.no_autoflush:
            db_cloud = session.query(IBMCloud).get(cloud_id)
            assert db_cloud

            db_clusters = session.query(IBMSatelliteCluster).filter_by(
                cloud_id=cloud_id
            ).all()

            for db_cluster in db_clusters:
                if locked_rid_status.get(db_cluster.resource_id) in [IBMResourceLog.STATUS_ADDED,
                                                                     IBMResourceLog.STATUS_UPDATED]:
                    continue

                if db_cluster.resource_id not in clusters_ids:
                    session.delete(db_cluster)

            session.commit()

            db_clusters = session.query(IBMSatelliteCluster).filter_by(
                cloud_id=cloud_id
            ).all()

            db_resource_groups = session.query(IBMResourceGroup).filter_by(cloud_id=cloud_id).all()
            db_resource_group_id_obj_dict = {
                db_resource_group.resource_id: db_resource_group for db_resource_group in db_resource_groups
            }

            for cluster in clusters:
                if locked_rid_status.get(cluster.resource_id) in [IBMResourceLog.STATUS_DELETED,
                                                                  IBMResourceLog.STATUS_UPDATED]:
                    continue

                cluster.dis_add_update_db(
                    session=session, db_clusters=db_clusters, db_cloud=db_cloud,
                    db_resource_group=db_resource_group_id_obj_dict.get(clusters_id_rgid_dict[cluster.resource_id])
                )

            session.commit()

    LOGGER.info("** Satellite Clusters synced in:{}".format((datetime.utcnow() - start_time).total_seconds()))


def update_satellite_cluster_kube_configs(cloud_id, m_cluster_kube_configs):
    if not m_cluster_kube_configs:
        return

    start_time = datetime.utcnow()
    for m_cluster_kube_config_list in m_cluster_kube_configs:
        for m_cluster_kube_config in m_cluster_kube_config_list.get('response', []):
            with get_db_session() as db_session:
                name = m_cluster_kube_config["clusters"][0]['name'].split('/')[0]
                resource_id = m_cluster_kube_config["clusters"][0]['name'].split('/')[1]
                satellite_cluster = db_session.query(IBMSatelliteCluster).filter_by(
                    cloud_id=cloud_id, name=name, resource_id=resource_id
                ).first()
                if not satellite_cluster:
                    continue

                satellite_cluster.kube_config = m_cluster_kube_config
                db_session.commit()

    LOGGER.info(
        "** Satellite Cluster Kube Config synced in:{}".format((datetime.utcnow() - start_time).total_seconds()))
