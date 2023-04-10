import logging

from apiflask import abort, APIBlueprint, doc, input, output
from sqlalchemy.orm import undefer

from ibm.auth import authenticate
from ibm.common.req_resp_schemas.schemas import get_pagination_schema, IBMResourceQuerySchema, PaginationQuerySchema
from ibm.models import IBMCloud, IBMSatelliteCluster
from ibm.web import db as ibmdb
from ibm.web.common.utils import authorize_and_get_ibm_cloud, get_paginated_response_json
from .schemas import IBMSatelliteClusterOutSchema, IBMSatelliteClustersListOutSchema

LOGGER = logging.getLogger(__name__)
ibm_satellite_clusters = APIBlueprint('ibm_satellite_clusters', __name__, tag="IBM Satellite Clusters")


@ibm_satellite_clusters.get('/satellite_clusters/<cluster_id>')
@authenticate
@output(IBMSatelliteClusterOutSchema)
def get_satellite_cluster(cluster_id, user):
    """
    Get Satellite cluster by cluster_id
    :param cluster_id:
    :param user: object of the user initiating the request
    :return: Response object from flask package
    """

    satellite_cluster = ibmdb.session.query(IBMSatelliteCluster).filter_by(
        id=cluster_id
    ).options(undefer("workloads")).join(IBMCloud).filter(
        IBMCloud.user_id == user["id"],
        IBMCloud.project_id == user["project_id"],
        IBMCloud.deleted.is_(False)
    ).first()
    if not satellite_cluster:
        message = f"IBM Satellite Cluster {cluster_id} does not exist"
        LOGGER.debug(message)
        abort(404, message)

    return satellite_cluster.to_json(workloads=True)


@ibm_satellite_clusters.get('/satellite_clusters')
@authenticate
@input(IBMResourceQuerySchema, location='query')
@input(PaginationQuerySchema, location='query')
@output(get_pagination_schema(IBMSatelliteClustersListOutSchema))
@doc(
    responses={
        204: "No records found"
    }
)
def list_satellite_clusters(cloud_res_query_params, pagination_query_params, user):
    """
    List Satellite Cluster
    :param cloud_res_query_params: get clusters in a selected cloud
    :param pagination_query_params:
    :param user: object of the user initiating the request
    :return: Response object from flask package
    """
    cloud_id = cloud_res_query_params["cloud_id"]

    ibm_cloud = authorize_and_get_ibm_cloud(cloud_id=cloud_id, user=user)
    satellite_clusters_query = ibmdb.session.query(IBMSatelliteCluster).filter_by(cloud_id=ibm_cloud.id)

    satellite_clusters_page = satellite_clusters_query.paginate(
        page=pagination_query_params["page"], per_page=pagination_query_params["per_page"], error_out=False
    )
    if not satellite_clusters_page.items:
        message = f"No IBM Satellite Clusters found for Cloud {cloud_id}"
        LOGGER.debug(message)
        return '', 204

    return get_paginated_response_json(
        items=[item.to_json() for item in satellite_clusters_page.items],
        pagination_obj=satellite_clusters_page
    )
