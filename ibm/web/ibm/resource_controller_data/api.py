import logging

from apiflask import abort, APIBlueprint, input, output

from flask import Response
from ibm.auth import authenticate
from ibm.models import IBMResourceControllerData, IBMIdleResource
from ibm.web import db as ibmdb
from ibm.web.common.utils import authorize_and_get_ibm_cloud
from .schemas import IBMResourceControllerDataQueryParams, IBMResourceControllerDataOutSchema

LOGGER = logging.getLogger(__name__)

ibm_resource_controller_data = APIBlueprint('ibm_resource_controller_data', __name__, tag="IBM Idle Resource Catalog")


@ibm_resource_controller_data.route('/resource_controller_data/idle_resource', methods=['GET'])
@authenticate
@input(IBMResourceControllerDataQueryParams, location='query')
@output(IBMResourceControllerDataOutSchema)
def get_idle_idle_resource_catalog(list_query_params, user):
    """
    List IBM Idle Resource Catalog
    This request lists all IBM Idle Resource Catalog for the cloud id and idle resource id specified.
    """
    cloud_id = list_query_params["cloud_id"]
    idle_resource_id = list_query_params.get("idle_resource_id")
    ibm_cloud = authorize_and_get_ibm_cloud(cloud_id=cloud_id, user=user)

    idle_resource = ibmdb.session.query(IBMIdleResource).filter_by(id=idle_resource_id).first()
    if not idle_resource:
        abort(404, f"No IBM Idle_resource with ID {idle_resource_id} found for the user")

    crn = idle_resource.resource_json['crn']
    idle_resource_catalog = ibmdb.session.query(IBMResourceControllerData).filter_by(crn=crn,
                                                                                     cloud_id=ibm_cloud.id).first()
    if not idle_resource_catalog:
        return Response(status=204)

    return idle_resource_catalog.to_json()
