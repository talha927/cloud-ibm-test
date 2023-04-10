import json
import logging

from apiflask import APIBlueprint, input, output
from flask import request, Response

from ibm.auth import authenticate
from ibm.common.req_resp_schemas.schemas import WorkflowRootOutSchema
from ibm.models import IBMCloud, IBMIdleResource, WorkflowRoot
from ibm.web import db as ibmdb
from .schemas import IBMIdleResourceInSchema
from .utils import IDLE_RESOURCE_TYPE_DELETE_WORKFLOW_MAPPER, IDLE_RESOURCE_TYPE_MODLE_MAPPER
from ...common.utils import authorize_and_get_ibm_cloud

LOGGER = logging.getLogger(__name__)

ibm_idle_resources = APIBlueprint('ibm_idle_resources', __name__, tag="IBM Idle Resources")


@ibm_idle_resources.get('/clouds/<cloud_id>/idle-resources')
@authenticate
def list_ibm_idle_resources(cloud_id, user):
    """
       List IBM Idle Resources with  cloud ID
       :param cloud_id: cloud_id for IBMCloud
       :param user: object of the user initiating the request
       :return: Response object from flask package
    """

    ibm_cloud = ibmdb.session.query(IBMCloud).filter_by(id=cloud_id, project_id=user["project_id"]).first()
    if not ibm_cloud:
        LOGGER.info(f"No IBM cloud found with ID: {cloud_id}")
        return Response("CLOUD_NOT_FOUND", status=404)

    if ibm_cloud.settings:
        if not ibm_cloud.settings.cost_optimization_enabled:
            error = f"IBM Cloud cost optimization disabled with Cloud ID {cloud_id}"
            LOGGER.info(error)
            return Response(json.dumps({"error": error}), status=200)

    ibm_idle_resource = IBMIdleResource.search_and_filter(request.args, cloud_id)
    if not ibm_idle_resource.items:
        LOGGER.info(f"No IBM Idle Resources for cloud with ID: {cloud_id}")
        return Response("IDLE_RESOURCES_WITH_CLOUD_ID_NOT_FOUND", status=204)

    idle_resource_json = {
        "items": [resource.to_json() for resource in ibm_idle_resource.items],
        "previous": ibm_idle_resource.prev_num if ibm_idle_resource.has_prev else None,
        "next": ibm_idle_resource.next_num if ibm_idle_resource.has_next else None,
        "pages": ibm_idle_resource.pages
    }
    return Response(json.dumps(idle_resource_json), status=200, mimetype="application/json")


@ibm_idle_resources.post('/clouds/<cloud_id>/idle-resources')
@authenticate
@input(IBMIdleResourceInSchema, location='json')
@output(WorkflowRootOutSchema, status_code=202)
def delete_ibm_idle_resource(cloud_id, data, user):
    """
    Delete an IBM Idle Resource
    :param cloud_id: cloud_id for IBMCloud
    :param user: object of the user initiating the request
    :return: Response object from flask package
    """
    authorize_and_get_ibm_cloud(cloud_id=cloud_id, user=user)

    workflow_root = WorkflowRoot(workflow_name=IBMIdleResource.__name__, workflow_nature="DELETE",
                                 user_id=user["id"], project_id=user["project_id"])

    for resource in data["resources"]:
        resource_type = resource["resource_type"]
        db_resource = ibmdb.session.query(IDLE_RESOURCE_TYPE_MODLE_MAPPER[resource_type]).filter_by(
            id=resource["id"]).first()
        if not db_resource:
            msg = f"The {resource_type} with ID: '{resource['id']}' does not exist"
            LOGGER.info(msg)
            return Response(msg, status=404)

        IDLE_RESOURCE_TYPE_DELETE_WORKFLOW_MAPPER[resource_type](workflow_root=workflow_root, db_resource=db_resource, )

    return Response(json.dumps({"task_id": workflow_root.id}), status=202, mimetype="application/json")
