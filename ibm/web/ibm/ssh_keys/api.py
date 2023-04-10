import logging

from apiflask import abort, APIBlueprint, input, output

from ibm.auth import authenticate
from ibm.common.req_resp_schemas.schemas import get_pagination_schema, IBMRegionalResourceListQuerySchema, \
    PaginationQuerySchema, WorkflowRootOutSchema
from ibm.middleware import log_activity
from ibm.models import IBMSshKey
from ibm.web import db as ibmdb
from ibm.web.common.utils import authorize_and_get_ibm_cloud, compose_ibm_resource_deletion_workflow, \
    create_ibm_resource_creation_workflow, get_paginated_response_json, verify_and_get_region, verify_references
from .schemas import IBMSshKeyInSchema, IBMSshKeyOutSchema, IBMSshKeyResourceSchema, UpdateIBMSshKeySchema

LOGGER = logging.getLogger(__name__)
ibm_ssh_keys = APIBlueprint('ibm_ssh_keys', __name__, tag="IBM Ssh Keys")


@ibm_ssh_keys.post('/ssh_keys')
@authenticate
@log_activity
@input(IBMSshKeyInSchema)
@output(WorkflowRootOutSchema, status_code=202)
def create_ibm_ssh_key(data, user):
    """
    Create an IBM Ssh Key
    This request registers an IBM Ssh Key with VPC+.
    """
    cloud_id = data["ibm_cloud"]["id"]
    region_id = data["region"]["id"]

    ibm_cloud = authorize_and_get_ibm_cloud(cloud_id=cloud_id, user=user)
    verify_and_get_region(ibm_cloud=ibm_cloud, region_id=region_id)

    verify_references(
        cloud_id=cloud_id, body_schema=IBMSshKeyInSchema, resource_schema=IBMSshKeyResourceSchema, data=data
    )

    workflow_root = create_ibm_resource_creation_workflow(
        user=user, resource_type=IBMSshKey, data=data, validate=False
    )
    return workflow_root.to_json()


@ibm_ssh_keys.get('/ssh_keys')
@authenticate
@input(IBMRegionalResourceListQuerySchema, location='query')
@input(PaginationQuerySchema, location='query')
@output(get_pagination_schema(IBMSshKeyOutSchema))
def list_ibm_ssh_keys(regional_res_query_params, pagination_query_params, user):
    """
    List IBM Ssh Keys
    This request lists all IBM Ssh Keys for the project of the authenticated user calling the API.
    """
    cloud_id = regional_res_query_params["cloud_id"]
    region_id = regional_res_query_params.get("region_id")

    ibm_cloud = authorize_and_get_ibm_cloud(cloud_id=cloud_id, user=user)

    region = None
    if region_id:
        region = ibm_cloud.regions.filter_by(id=region_id).first()
        if not region:
            message = f"IBM Region {region_id} does not exist"
            LOGGER.debug(message)
            abort(404, message)

    ssh_keys_query = ibmdb.session.query(IBMSshKey).filter_by(cloud_id=cloud_id)
    if region:
        ssh_keys_query = ssh_keys_query.filter_by(region_id=region_id)

    ssh_keys_page = ssh_keys_query.paginate(
        page=pagination_query_params["page"], per_page=pagination_query_params["per_page"], error_out=False
    )
    if not ssh_keys_page.items:
        return '', 204

    return get_paginated_response_json(
        items=[item.to_json() for item in ssh_keys_page.items],
        pagination_obj=ssh_keys_page
    )


@ibm_ssh_keys.get('/ssh_keys/<ssh_key_id>')
@authenticate
@output(IBMSshKeyOutSchema)
def get_ibm_ssh_key(ssh_key_id, user):
    """
    Get an IBM Ssh Key
    This request returns an IBM Ssh Key provided its ID.
    """
    ssh_key = ibmdb.session.query(IBMSshKey).filter_by(
        id=ssh_key_id
    ).join(IBMSshKey.ibm_cloud).filter_by(
        user_id=user["id"], project_id=user["project_id"], deleted=False
    ).first()
    if not ssh_key:
        message = f"IBM SSH Key {ssh_key_id} does not exist"
        LOGGER.debug(message)
        abort(404, message)

    return ssh_key.to_json()


@ibm_ssh_keys.delete('/ssh_keys/<ssh_key_id>')
@authenticate
@log_activity
@output(WorkflowRootOutSchema, status_code=202)
def delete_ibm_ssh_key(ssh_key_id, user):
    """
    Delete an IBM Ssh Key
    This request deletes an IBM Ssh Key provided its ID.
    """
    ssh_key = ibmdb.session.query(IBMSshKey).filter_by(
        id=ssh_key_id
    ).join(IBMSshKey.ibm_cloud).filter_by(
        user_id=user["id"], project_id=user["project_id"], deleted=False
    ).first()
    if not ssh_key:
        message = f"IBM SSH Key {ssh_key} does not exist"
        LOGGER.debug(message)
        abort(404, message)

    return compose_ibm_resource_deletion_workflow(
        user=user, resource_type=IBMSshKey, resource_id=ssh_key_id
    ).to_json(metadata=True)


@ibm_ssh_keys.patch('/ssh_keys/<ssh_key_id>')
@authenticate
@input(UpdateIBMSshKeySchema)
@output(WorkflowRootOutSchema, status_code=202)
def update_ibm_ssh_key(ssh_key_id, data, user):
    """
    Update an IBM Ssh Key
    This request updates an IBM Ssh Key provided its ID.
    """
    abort(404)
