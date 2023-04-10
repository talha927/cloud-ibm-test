import logging

from apiflask import abort, APIBlueprint, input, output

from ibm.auth import authenticate
from ibm.common.req_resp_schemas.schemas import get_pagination_schema, IBMZonalResourceListQuerySchema, \
    PaginationQuerySchema, WorkflowRootOutSchema
from ibm.models import IBMInstanceTemplate
from ibm.web import db as ibmdb
from ibm.web.common.utils import authorize_and_get_ibm_cloud, compose_ibm_resource_deletion_workflow, \
    create_ibm_resource_creation_workflow, \
    get_paginated_response_json, verify_and_get_region, verify_and_get_zone, verify_references
from .schemas import IBMInstanceTemplateInSchema, IBMInstanceTemplateListQuerySchema, IBMInstanceTemplateOutSchema, \
    IBMInstanceTemplateResourceSchema, \
    IBMInstanceTemplateUpdateSchema

LOGGER = logging.getLogger(__name__)

ibm_instance_templates = APIBlueprint('ibm_instance_templates', __name__, tag="IBM Instance Templates")


@ibm_instance_templates.post('/instance_templates')
@authenticate
@input(IBMInstanceTemplateInSchema)
@output(WorkflowRootOutSchema, status_code=202)
def create_instance_template(data, user):
    """
    Create IBM Instance Template
    This request create an Instance Templates on IBM Cloud with VPC+.
    """
    cloud_id = data["ibm_cloud"]["id"]
    region_id = data["region"]["id"]

    ibm_cloud = authorize_and_get_ibm_cloud(cloud_id=cloud_id, user=user)
    verify_and_get_region(ibm_cloud=ibm_cloud, region_id=region_id)

    verify_references(
        cloud_id=cloud_id, body_schema=IBMInstanceTemplateInSchema, resource_schema=IBMInstanceTemplateResourceSchema,
        data=data
    )

    workflow_root = create_ibm_resource_creation_workflow(
        user=user, resource_type=IBMInstanceTemplate, data=data, validate=False
    )
    return workflow_root.to_json()


@ibm_instance_templates.get('/instance_templates/<template_id>')
@authenticate
@output(IBMInstanceTemplateOutSchema, status_code=202)
def get_instance_template(template_id, user):
    """
    Get IBM Instance Template
    This request will fetch IBM Instance Template from IBM Cloud.
    """
    instance_template = ibmdb.session.query(IBMInstanceTemplate).filter_by(id=template_id).first()
    if not instance_template:
        message = f"IBMInstanceTemplate '{template_id}' does not exist"
        LOGGER.debug(message)
        abort(404, message)

    authorize_and_get_ibm_cloud(instance_template.cloud_id, user)

    return instance_template.to_json()


@ibm_instance_templates.get('/instance_templates')
@authenticate
@input(IBMZonalResourceListQuerySchema, location='query')
@input(IBMInstanceTemplateListQuerySchema, location='query')
@input(PaginationQuerySchema, location='query')
@output(get_pagination_schema(IBMInstanceTemplateOutSchema))
def list_instance_templates(zonal_res_query_params, it_for_ig_query_params, pagination_query_params, user):
    """
    List IBM Instance Templates
    This request fetches all Instance Template from IBM Cloud attached to an instance.
    """
    cloud_id = zonal_res_query_params["cloud_id"]
    region_id = zonal_res_query_params.get("region_id")
    zone_id = zonal_res_query_params.get("zone_id")
    it_for_ig = it_for_ig_query_params.get("it_for_ig")

    ibm_cloud = authorize_and_get_ibm_cloud(cloud_id=cloud_id, user=user)

    instance_template_query = ibmdb.session.query(IBMInstanceTemplate).filter_by(cloud_id=cloud_id)

    if region_id:
        verify_and_get_region(ibm_cloud=ibm_cloud, region_id=region_id)
        instance_template_query = instance_template_query.filter_by(region_id=region_id)

    if zone_id:
        verify_and_get_zone(cloud_id, zone_id)
        instance_template_query = instance_template_query.filter_by(zone_id=zone_id)

    if it_for_ig:
        instance_template_query = instance_template_query.filter(
            IBMInstanceTemplate.network_interfaces.any(is_primary=True))

    instances_page = instance_template_query.paginate(
        page=pagination_query_params["page"], per_page=pagination_query_params["per_page"], error_out=False
    )
    if not instances_page.items:
        return '', 204

    return get_paginated_response_json(
        items=[item.to_json() for item in instances_page.items],
        pagination_obj=instances_page
    )


@ibm_instance_templates.patch('/instance_templates/<template_id>')
@authenticate
@input(IBMInstanceTemplateUpdateSchema)
@output(WorkflowRootOutSchema, status_code=202)
def update_instance_template(template_id, data, user):
    """
    Update IBM Instance Template
    This request updates an IBM Instance Templates
    """
    abort(404)


@ibm_instance_templates.delete('/instance_templates/<template_id>')
@authenticate
@output(WorkflowRootOutSchema, status_code=202)
def delete_instance_template(template_id, user):
    """
    Delete IBM Instance Template
    This request deletes an IBM Instance Template provided its ID.
    """
    instance_template = ibmdb.session.query(IBMInstanceTemplate).filter_by(id=template_id).first()
    if not instance_template:
        message = f"IBMInstanceTemplate '{template_id}' does not exist"
        LOGGER.debug(message)
        abort(404, message)

    authorize_and_get_ibm_cloud(instance_template.cloud_id, user)

    return compose_ibm_resource_deletion_workflow(
        user=user, resource_type=IBMInstanceTemplate, resource_id=template_id
    ).to_json(metadata=True)
