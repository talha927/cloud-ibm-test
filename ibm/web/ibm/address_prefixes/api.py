from apiflask import abort, APIBlueprint, doc, input, output

from ibm import LOGGER
from ibm.auth import authenticate
from ibm.common.req_resp_schemas.schemas import get_pagination_schema, PaginationQuerySchema, WorkflowRootOutSchema
from ibm.middleware import log_activity
from ibm.models import IBMAddressPrefix, IBMVpcNetwork
from ibm.web import db as ibmdb
from ibm.web.common.utils import authorize_and_get_ibm_cloud, compose_ibm_resource_deletion_workflow, \
    create_ibm_resource_creation_workflow, \
    get_paginated_response_json, verify_and_get_region, verify_and_get_zone, verify_references
from .schemas import IBMAddressPrefixInSchema, IBMAddressPrefixOutSchema, IBMAddressPrefixResourceSchema, \
    IBMVpcResourceListQuerySchema, UpdateIBMAddressPrefixesSchema

ibm_address_prefixes = APIBlueprint('ibm_address_prefixes', __name__, tag="Address Prefixes")


@ibm_address_prefixes.route("address_prefixes", methods=["POST"])
@authenticate
@log_activity
@input(IBMAddressPrefixInSchema)
@output(WorkflowRootOutSchema, status_code=202)
def create_ibm_vpc_address_prefix(data, user):
    """
    Create an IBM vpc address prefix
    This request creates an IBM VPC address prefix.
    """
    cloud_id = data["ibm_cloud"]["id"]
    region_id = data["region"]["id"]

    ibm_cloud = authorize_and_get_ibm_cloud(cloud_id=cloud_id, user=user)
    verify_and_get_region(ibm_cloud=ibm_cloud, region_id=region_id)

    verify_references(
        cloud_id=cloud_id, body_schema=IBMAddressPrefixInSchema, resource_schema=IBMAddressPrefixResourceSchema,
        data=data
    )

    workflow_root = create_ibm_resource_creation_workflow(
        user=user, resource_type=IBMAddressPrefix, data=data, validate=False
    )
    return workflow_root.to_json()


@ibm_address_prefixes.route("address_prefixes", methods=["GET"])
@authenticate
@input(IBMVpcResourceListQuerySchema, location='query')
@input(PaginationQuerySchema, location='query')
@output(get_pagination_schema(IBMAddressPrefixOutSchema))
@doc(
    responses={
        204: "No records found"
    }
)
def list_ibm_vpc_address_prefixes(zonal_res_query_params, pagination_query_params, user):
    """
    List IBM address prefixes
    This request lists all IBM address prefixes.
    """
    cloud_id = zonal_res_query_params["cloud_id"]
    region_id = zonal_res_query_params.get("region_id")
    zone_id = zonal_res_query_params.get("zone_id")
    vpc_id = zonal_res_query_params.get("vpc_id")

    ibm_cloud = authorize_and_get_ibm_cloud(cloud_id=cloud_id, user=user)
    address_prefixes_query = ibmdb.session.query(IBMAddressPrefix).filter_by(cloud_id=cloud_id)

    if region_id:
        verify_and_get_region(ibm_cloud=ibm_cloud, region_id=region_id)
        address_prefixes_query = address_prefixes_query.filter_by(region_id=region_id)

    if zone_id:
        verify_and_get_zone(cloud_id=cloud_id, zone_id=zone_id)
        address_prefixes_query = address_prefixes_query.filter_by(zone_id=zone_id)

    if vpc_id:
        vpc = ibmdb.session.query(IBMVpcNetwork).filter_by(id=vpc_id).first()
        if not vpc:
            message = f"IBM VPC {vpc_id} does not exist"
            LOGGER.error(message)
            abort(404, message)
            return

        address_prefixes_query = address_prefixes_query.filter_by(vpc_id=vpc_id)

    address_prefixes_page = address_prefixes_query.paginate(
        page=pagination_query_params["page"], per_page=pagination_query_params["per_page"], error_out=False
    )
    if not address_prefixes_page.items:
        return '', 204

    return get_paginated_response_json(
        items=[item.to_json() for item in address_prefixes_page.items],
        pagination_obj=address_prefixes_page
    )


@ibm_address_prefixes.route('address_prefixes/<address_prefix_id>', methods=['GET'])
@authenticate
@output(IBMAddressPrefixOutSchema)
def get_ibm_vpc_address_prefix(address_prefix_id, user):
    """
    Get IBM Address Prefix
    This request returns an IBM Address Prefix provided its ID.
    """
    address_prefix = ibmdb.session.query(IBMAddressPrefix).filter_by(
        id=address_prefix_id
    ).join(IBMAddressPrefix.ibm_cloud).filter_by(
        user_id=user["id"], project_id=user["project_id"], deleted=False
    ).first()
    if not address_prefix:
        message = f"IBM Address Prefix {address_prefix_id} does not exist"
        LOGGER.error(message)
        abort(404, message)

    return address_prefix.to_json()


@ibm_address_prefixes.route('address_prefixes/<address_prefix_id>', methods=['PATCH'])
@authenticate
@input(UpdateIBMAddressPrefixesSchema)
@output(WorkflowRootOutSchema, status_code=202)
def update_ibm_vpc_address_prefix(address_prefix_id, data, user):
    """
    Update IBM Address Prefix
    This request updates an IBM Address Prefix
    """
    abort(404)


@ibm_address_prefixes.route('address_prefixes/<address_prefix_id>', methods=['DELETE'])
@authenticate
@log_activity
@output(WorkflowRootOutSchema, status_code=202)
def delete_ibm_vpc_address_prefix(address_prefix_id, user):
    """
    Delete IBM VPC Address prefix
    This request deletes an IBM VPC address prefix provided its ID.
    """
    address_prefix = ibmdb.session.query(IBMAddressPrefix).filter_by(
        id=address_prefix_id
    ).join(IBMAddressPrefix.ibm_cloud).filter_by(
        user_id=user["id"], project_id=user["project_id"], deleted=False
    ).first()
    if not address_prefix:
        message = f"IBM Address Prefix {address_prefix} does not exist"
        LOGGER.error(message)
        abort(404, message)

    if address_prefix.has_subnets:
        message = f"Please delete subnets attach to this IBM Address prefix {address_prefix_id}"
        LOGGER.error(message)
        abort(409, message)

    return compose_ibm_resource_deletion_workflow(
        user=user, resource_type=IBMAddressPrefix, resource_id=address_prefix_id
    ).to_json(metadata=True)
