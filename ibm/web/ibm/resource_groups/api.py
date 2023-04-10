import logging

from apiflask import abort, APIBlueprint, input, output
from flask import Response

from ibm.auth import authenticate
from ibm.common.req_resp_schemas.schemas import IBMResourceQuerySchema
from ibm.models import IBMCloud, IBMResourceGroup
from ibm.web import db as ibmdb
from .schemas import IBMResourceGroupOutSchema

LOGGER = logging.getLogger(__name__)
ibm_resource_groups = APIBlueprint('ibm_resource_groups', __name__, tag="IBM Resource Groups")


@ibm_resource_groups.route('/resource_groups', methods=['GET'])
@authenticate
@input(IBMResourceQuerySchema, location='query')
@output(IBMResourceGroupOutSchema(many=True))
def list_resource_groups(listing_query_params, user):
    """
    List IBM Resource Groups
    This request lists all IBM Resource Groups for the cloud specified.
    """
    cloud_id = listing_query_params["cloud_id"]
    cloud = ibmdb.session.query(IBMCloud).filter_by(
        id=cloud_id, user_id=user["id"], project_id=user["project_id"], deleted=False
    ).first()
    if not cloud:
        message = f"IBM Cloud {cloud_id} not found"
        LOGGER.debug(message)
        abort(404, message)

    resource_groups = ibmdb.session.query(IBMResourceGroup).filter_by(cloud_id=cloud_id).all()
    if not resource_groups:
        return Response(status=204)

    return [resource_group.to_json() for resource_group in resource_groups]


@ibm_resource_groups.route('/resource_groups/<resource_group_id>', methods=['GET'])
@authenticate
@output(IBMResourceGroupOutSchema)
def get_resource_group(resource_group_id, user):
    """
    Get IBM Resource Group
    This request returns an IBM IBM Resource Group provided its ID.
    """
    resource_group = ibmdb.session.query(IBMResourceGroup).filter_by(
        id=resource_group_id
    ).join(IBMResourceGroup.ibm_cloud).filter_by(
        user_id=user["id"], project_id=user["project_id"], deleted=False
    ).first()
    if not resource_group:
        message = f"IBM Resource Group {resource_group_id} does not exist"
        LOGGER.debug(message)
        abort(404, message)

    return resource_group.to_json()
