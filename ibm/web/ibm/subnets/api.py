from apiflask import abort, APIBlueprint, input, output

from ibm import LOGGER
from ibm.auth import authenticate
from ibm.common.req_resp_schemas.schemas import get_pagination_schema, IBMResourceQuerySchema, PaginationQuerySchema, \
    WorkflowRootOutSchema
from ibm.common.utils import get_resource_by_name_or_id
from ibm.middleware import log_activity
from ibm.models import IBMEndpointGateway, IBMNetworkAcl, IBMPublicGateway, IBMRoutingTable, IBMSubnet, \
    IBMSubnetReservedIp, IBMVpcNetwork, WorkflowRoot, WorkflowTask
from ibm.web import db as ibmdb
from ibm.web.common.utils import authorize_and_get_ibm_cloud, compose_ibm_resource_attachment_workflow, \
    compose_ibm_resource_deletion_workflow, compose_ibm_resource_detachment_workflow, \
    create_ibm_resource_creation_workflow, get_paginated_response_json, verify_and_get_region, verify_and_get_zone, \
    verify_references
from ibm.web.ibm.acls.schemas import IBMAclOutSchema
from ibm.web.ibm.public_gateways.schemas import IBMPublicGatewayOutSchema
from ibm.web.ibm.routing_tables.schemas import IBMRoutingTableOutSchema
from .schemas import IBMReservedIpInSchema, IBMReservedIpListQuerySchema, IBMReservedIpOutSchema, \
    IBMReservedIpResourceSchema, IBMSubnetAvailableIp4ListQuerySchema, IBMSubnetInSchema, IBMSubnetOutSchema, \
    IBMSubnetQuerySchema, IBMSubnetResourceSchema, IBMVpcListQuerySchema, SubnetRoutingTableTargetSchema, \
    SubnetTargetSchema, UpdateIBMSubnetSchema, SubnetAvailableIPsOutSchema

ibm_subnets = APIBlueprint('ibm_subnets', __name__, tag="IBM Subnets")


@ibm_subnets.post('/subnets')
@authenticate
@log_activity
@input(IBMSubnetInSchema)
@output(WorkflowRootOutSchema, status_code=202)
def create_ibm_subnet(data, user):
    """
    Create an IBM Subnet
    This request registers an IBM Subnet with VPC+.
    """
    cloud_id = data["ibm_cloud"]["id"]
    region_id = data["region"]["id"]

    ibm_cloud = authorize_and_get_ibm_cloud(cloud_id=cloud_id, user=user)
    verify_and_get_region(ibm_cloud=ibm_cloud, region_id=region_id)

    verify_references(
        cloud_id=cloud_id, body_schema=IBMSubnetInSchema, resource_schema=IBMSubnetResourceSchema, data=data
    )

    workflow_root = create_ibm_resource_creation_workflow(
        user=user, resource_type=IBMSubnet, data=data, validate=False
    )
    return workflow_root.to_json()


@ibm_subnets.get('/subnets')
@authenticate
@input(IBMVpcListQuerySchema, location='query')
@input(IBMSubnetAvailableIp4ListQuerySchema, location='query')
@input(PaginationQuerySchema, location='query')
@output(get_pagination_schema(IBMSubnetOutSchema))
def list_ibm_subnets(vpc_res_query_params, available_ip_query_params, pagination_query_params, user):
    """
    List IBM Subnets
    This request lists all IBM Subnets for the project of the authenticated user calling the API.
    """
    cloud_id = vpc_res_query_params["cloud_id"]
    region_id = vpc_res_query_params.get("region_id")
    zone_id = vpc_res_query_params.get("zone_id")
    vpc_id = vpc_res_query_params.get("vpc_id")
    number_of_ips = available_ip_query_params.get("number_of_ips")

    ibm_cloud = authorize_and_get_ibm_cloud(cloud_id=cloud_id, user=user)
    subnets_query = ibmdb.session.query(IBMSubnet).filter_by(cloud_id=cloud_id)

    if region_id:
        verify_and_get_region(ibm_cloud=ibm_cloud, region_id=region_id)
        subnets_query = subnets_query.filter_by(region_id=region_id)

    if zone_id:
        verify_and_get_zone(cloud_id=cloud_id, zone_id=zone_id)
        subnets_query = subnets_query.filter_by(zone_id=zone_id)

    if vpc_id:
        vpc = ibmdb.session.query(IBMVpcNetwork).filter_by(id=vpc_id).first()
        if not vpc:
            message = f"IBM VPC Network with id  {vpc_id} does not exist"
            LOGGER.error(message)
            abort(404, message)

        subnets_query = subnets_query.filter_by(vpc_id=vpc_id)

    if number_of_ips:
        subnets_query = subnets_query.filter(IBMSubnet.available_ipv4_address_count >= number_of_ips)

    subnets_page = subnets_query.paginate(
        page=pagination_query_params["page"], per_page=pagination_query_params["per_page"], error_out=False
    )
    if not subnets_page.items:
        return '', 204

    return get_paginated_response_json(
        items=[item.to_json() for item in subnets_page.items],
        pagination_obj=subnets_page
    )


@ibm_subnets.get('/subnets/<subnet_id>')
@authenticate
@output(IBMSubnetOutSchema)
def get_ibm_subnet(subnet_id, user):
    """
    Get an IBM Subnet
    This request returns an IBM Subnet provided its ID.
    """
    subnet = ibmdb.session.query(IBMSubnet).filter_by(
        id=subnet_id
    ).join(IBMSubnet.ibm_cloud).filter_by(
        user_id=user["id"], project_id=user["project_id"], deleted=False
    ).first()
    if not subnet:
        message = f"IBM Subnet {subnet_id} does not exist"
        LOGGER.error(message)
        abort(404, message)

    return subnet.to_json()


@ibm_subnets.delete('/subnets/<subnet_id>')
@authenticate
@log_activity
@output(WorkflowRootOutSchema, status_code=202)
def delete_ibm_subnet(subnet_id, user):
    """
    Delete an IBM Subnet
    This request deletes an IBM Subnet provided its ID.
    """
    subnet = ibmdb.session.query(IBMSubnet).filter_by(
        id=subnet_id
    ).join(IBMSubnet.ibm_cloud).filter_by(
        user_id=user["id"], project_id=user["project_id"], deleted=False
    ).first()
    if not subnet:
        message = f"IBM Subnet {subnet_id} does not exist"
        LOGGER.error(message)
        abort(404, message)

    # TODO: Uncomment when we have update calls
    # if not subnet.is_deletable:  # TODO: what resources are attached ???
    #     message = f"This subnet '{subnet_id}' has attached resources. Please delete them and try again later."
    #     LOGGER.error(message)
    #     abort(404, message)

    return compose_ibm_resource_deletion_workflow(
        user=user, resource_type=IBMSubnet, resource_id=subnet_id
    ).to_json(metadata=True)


@ibm_subnets.patch('/subnets/<subnet_id>')
@authenticate
@input(UpdateIBMSubnetSchema)
@output(WorkflowRootOutSchema, status_code=202)
def update_ibm_subnet(subnet_id, data, user):
    """
    Update an IBM Subnets
    This request updates an IBM Subnet
    """
    abort(404)


@ibm_subnets.post('/network_acl')
@authenticate
@input(IBMSubnetQuerySchema(only=("subnet_id", "cloud_id")), location='query')
@output(WorkflowRootOutSchema, status_code=202)
def update_ibm_subnet_with_acl(subnet_id_query_params, user):
    """
    Update an IBM Subnets
    This request updates an IBM Subnet
    """
    cloud_id = subnet_id_query_params["cloud_id"]
    subnet_id = subnet_id_query_params["subnet_id"]

    authorize_and_get_ibm_cloud(cloud_id=cloud_id, user=user)

    subnet = ibmdb.session.query(IBMSubnet).filter_by(id=subnet_id).first()

    if not subnet:
        abort(404, f"No IBM Subnet with ID {subnet_id} found")

    workflow_root = WorkflowRoot(
        user_id=user["id"],
        project_id=user["project_id"],
        workflow_name=f"{IBMSubnet.__name__} ({subnet.name})",
        workflow_nature="PUT"
    )
    workflow_task = WorkflowTask(
        task_type=WorkflowTask.TYPE_ATTACH, resource_type=f'{IBMSubnet.__name__}-{IBMNetworkAcl.__name__}',
        resource_id=subnet.id
    )
    workflow_root.add_next_task(workflow_task)
    ibmdb.session.add(workflow_root)
    ibmdb.session.commit()

    return workflow_root.to_json(metadata=True)


@ibm_subnets.get('/subnets/<subnet_id>/public_gateway')
@authenticate
@output(IBMPublicGatewayOutSchema)
def get_ibm_public_gateway_attached_subnet(subnet_id, user):
    """
    Get a Subnet attached Public Gateway
    This request returns an IBM Public Gateway provided its Subnet ID.
    """
    subnet = ibmdb.session.query(IBMSubnet).filter_by(
        id=subnet_id
    ).join(IBMSubnet.ibm_cloud).filter_by(
        user_id=user["id"], project_id=user["project_id"], deleted=False
    ).first()
    if not subnet:
        message = f"IBM Subnet {subnet_id} does not exist"
        LOGGER.error(message)
        abort(404, message)

    public_gateway = subnet.public_gateway
    if not public_gateway:
        message = f"IBM Public Gateway is not attached to this subnet {subnet_id}"
        LOGGER.error(message)
        abort(409, message)

    return public_gateway.to_json()


@ibm_subnets.get('/subnets/<subnet_id>/routing_table')
@authenticate
@output(IBMRoutingTableOutSchema)
def get_ibm_routing_table_attached_subnet(subnet_id, user):
    """
    Get a Subnet attached Routing Table
    This request returns an IBM Routing Table provided its Subnet ID.
    """
    subnet = ibmdb.session.query(IBMSubnet).filter_by(
        id=subnet_id
    ).join(IBMSubnet.ibm_cloud).filter_by(
        user_id=user["id"], project_id=user["project_id"], deleted=False
    ).first()
    if not subnet:
        message = f"IBM Subnet {subnet_id} does not exist"
        LOGGER.error(message)
        abort(404, message)

    routing_table = subnet.routing_table
    if not routing_table:
        message = f"IBM Routing Table is not attached to this subnet {subnet_id}"
        LOGGER.error(message)
        abort(409, message)

    return routing_table.to_json()


@ibm_subnets.get('/subnets/<subnet_id>/network_acl')
@authenticate
@output(IBMAclOutSchema)
def get_ibm_acl_attached_subnet(subnet_id, user):
    """
    Get a Subnet attached ACL
    This request returns an IBM ACL provided its Subnet ID.
    """
    subnet = ibmdb.session.query(IBMSubnet).filter_by(
        id=subnet_id
    ).join(IBMSubnet.ibm_cloud).filter_by(
        user_id=user["id"], project_id=user["project_id"], deleted=False
    ).first()
    if not subnet:
        message = f"IBM Subnet {subnet_id} does not exist"
        LOGGER.error(message)
        abort(404, message)

    network_acl = subnet.network_acl
    if not network_acl:
        message = f"IBM Network ACL is not attached to this subnet {subnet_id}"
        LOGGER.error(message)
        abort(409, message)

    return network_acl.to_json()


@ibm_subnets.put('/subnets/<subnet_id>/public_gateway')
@authenticate
@input(SubnetTargetSchema)
@output(WorkflowRootOutSchema, status_code=202)
def attach_ibm_subnet_target(subnet_id, target_data, user):
    """
    Attach IBM Subnet with Target (Public gateway)
    """
    subnet: IBMSubnet = ibmdb.session.query(IBMSubnet) \
        .filter_by(id=subnet_id).first()
    if not subnet:
        message = f"IBM Subnet {subnet_id} does not exist"
        LOGGER.error(message)
        abort(404, message)

    if subnet.public_gateway_id:
        message = "IBMPublicGateway is already attached to this subnet"
        LOGGER.error(message)
        abort(409, message)

    authorize_and_get_ibm_cloud(cloud_id=subnet.ibm_cloud.id, user=user)
    task_metadata = {
        "subnet": {
            "id": subnet.id
        },
        "region": {
            "id": subnet.region.id
        },
        "vpc": {
            "id": subnet.vpc_id
        }
    }

    target, message = get_resource_by_name_or_id(subnet.ibm_cloud.id, IBMPublicGateway, ibmdb.session,
                                                 target_data["public_gateway"])
    if message:
        LOGGER.error(message)
        abort(404, message)

    task_metadata["public_gateway"] = target_data["public_gateway"]
    workflow_root = compose_ibm_resource_attachment_workflow(
        user=user, resource_type_name=f'{IBMSubnet.__name__}-{IBMPublicGateway.__name__}', resource_id=subnet_id,
        data=task_metadata
    )

    return workflow_root.to_json()


@ibm_subnets.delete('/subnets/<subnet_id>/public_gateway')
@authenticate
@output(WorkflowRootOutSchema, status_code=202)
def detach_ibm_subnet_target(subnet_id, user):
    """
    Detach IBM Subnet with Target (Public Gateways)
    """
    subnet: IBMSubnet = ibmdb.session.query(IBMSubnet) \
        .filter_by(id=subnet_id).first()
    if not subnet:
        message = f"IBM Subnet {subnet_id} does not exist"
        LOGGER.error(message)
        abort(404, message)

    if not subnet.public_gateway_id:
        message = "None of the Public Gateway is attached to this subnet"
        LOGGER.error(message)
        abort(409, message)

    authorize_and_get_ibm_cloud(cloud_id=subnet.ibm_cloud.id, user=user)
    task_metadata = {
        "subnet": {
            "id": subnet.id
        },
        "region": {
            "id": subnet.region.id
        }
    }

    workflow_root = compose_ibm_resource_detachment_workflow(
        user=user, resource_type=IBMSubnet, resource_id=subnet_id,
        data=task_metadata
    )
    return workflow_root.to_json()


@ibm_subnets.get('/subnets/reserved_ips')
@authenticate
@input(PaginationQuerySchema, location='query')
@input(IBMReservedIpListQuerySchema, location='query')
@output(get_pagination_schema(IBMReservedIpOutSchema))
def list_ibm_reserved_ips(pagination_query_params, reserved_ips_res_query_params, user):
    """
    List IBM Reserved Ips
    This request lists all IBM Reserved Ips for the given cloud id.
    """
    cloud_id = reserved_ips_res_query_params["cloud_id"]
    subnet_id = reserved_ips_res_query_params.get("subnet_id")
    endpoint_gateway_id = reserved_ips_res_query_params.get("endpoint_gateway_id")
    is_vpe = reserved_ips_res_query_params.get("is_vpe")

    authorize_and_get_ibm_cloud(cloud_id=cloud_id, user=user)
    reserved_ips_query = ibmdb.session.query(IBMSubnetReservedIp)

    if subnet_id:
        subnet = ibmdb.session.query(IBMSubnet).filter_by(id=subnet_id).first()
        if not subnet:
            message = f"IBM Subnet {subnet_id} not found."
            LOGGER.error(message)
            abort(404, message)

        reserved_ips_query = reserved_ips_query.filter_by(subnet_id=subnet_id)

    if endpoint_gateway_id:
        endpoint_gateway = ibmdb.session.query(IBMEndpointGateway).filter_by(id=endpoint_gateway_id).first()
        if not endpoint_gateway:
            message = f"IBM Endpoint Gateway {endpoint_gateway_id} not found."
            LOGGER.error(message)
            abort(404, message)

        reserved_ips_query = reserved_ips_query.filter_by(target_id=endpoint_gateway_id)

    if is_vpe is not None:
        if is_vpe:
            reserved_ips_query = reserved_ips_query.filter(IBMSubnetReservedIp.target_id.is_not(None))
        else:
            reserved_ips_query = reserved_ips_query.filter(IBMSubnetReservedIp.target_id.is_(None))

    reserved_ips_page = reserved_ips_query.paginate(
        page=pagination_query_params["page"], per_page=pagination_query_params["per_page"], error_out=False
    )
    if not reserved_ips_page.items:
        return '', 204

    return get_paginated_response_json(
        items=[item.to_json() for item in reserved_ips_page.items],
        pagination_obj=reserved_ips_page
    )


@ibm_subnets.get('/subnets/<subnet_id>/available_ips')
@authenticate
@output(SubnetAvailableIPsOutSchema)
def list_ibm_available_ips(subnet_id, user):
    """
    List IBM Subnet Available IPs
    This request will list out only available IPs and filtered out the reserved IPs
    """
    subnet = ibmdb.session.query(IBMSubnet).filter_by(
        id=subnet_id
    ).join(IBMSubnet.ibm_cloud).filter_by(
        user_id=user["id"], project_id=user["project_id"], deleted=False
    ).first()
    if not subnet:
        message = f"IBM Subnet {subnet_id} does not exist"
        LOGGER.error(message)
        abort(404, message)
    return {'available_ips': subnet.available_ip_addresses}


@ibm_subnets.get('/subnets/reserved_ips/<reserved_ip_id>')
@authenticate
@input(IBMResourceQuerySchema, location='query')
@output(IBMReservedIpOutSchema)
def get_ibm_reserved_ip(reserved_ip_id, cloud_resource_query_param, user):
    """
    Get IBM Reserved Ip by id
    This request returns an IBM Reserved IP provided its ID.
    """
    cloud_id = cloud_resource_query_param["cloud_id"]
    authorize_and_get_ibm_cloud(cloud_id=cloud_id, user=user)
    reserved_ip = ibmdb.session.query(IBMSubnetReservedIp).filter_by(
        id=reserved_ip_id).first()
    if not reserved_ip:
        message = f"IBM Reserved ip with ID {reserved_ip_id}, does not exist"
        LOGGER.error(message)
        abort(404, message)

    return reserved_ip.to_json()


@ibm_subnets.put('/subnets/<subnet_id>/routing_table')
@authenticate
@input(SubnetRoutingTableTargetSchema)
@output(WorkflowRootOutSchema, status_code=202)
def attach_routing_table_to_subnet(subnet_id, target_data, user):
    """
    Attach IBM Subnet with Target (Routing Table)
    """
    subnet: IBMSubnet = ibmdb.session.query(IBMSubnet) \
        .filter_by(id=subnet_id).first()
    if not subnet:
        message = f"IBM Subnet {subnet_id} does not exist"
        LOGGER.error(message)
        abort(404, message)

    if subnet.routing_table:
        message = "IBMRoutingTable is already attached to this subnet"
        LOGGER.error(message)
        abort(409, message)

    authorize_and_get_ibm_cloud(cloud_id=subnet.ibm_cloud.id, user=user)
    task_metadata = {
        "subnet": {
            "id": subnet.id
        },
        "region": {
            "id": subnet.region.id
        },
        "vpc": {
            "id": subnet.vpc_id
        }
    }

    target, message = get_resource_by_name_or_id(subnet.ibm_cloud.id, IBMRoutingTable, ibmdb.session,
                                                 target_data["routing_table"])
    if message:
        LOGGER.error(message)
        abort(404, message)

    task_metadata["routing_table"] = target_data["routing_table"]
    workflow_root = compose_ibm_resource_attachment_workflow(
        user=user, resource_id=subnet_id, resource_type_name=f'{IBMSubnet.__name__}-{IBMRoutingTable.__name__}',
        data=task_metadata
    )

    return workflow_root.to_json()


@ibm_subnets.post('/subnets/reserved_ips')
@authenticate
@input(IBMReservedIpInSchema)
@output(WorkflowRootOutSchema, status_code=202)
def reserve_ip_for_subnet(data, user):
    """
    Reserve Ip for IBM Subnet
    """
    cloud_id = data["ibm_cloud"]["id"]
    region_id = data["region"]["id"]

    ibm_cloud = authorize_and_get_ibm_cloud(cloud_id=cloud_id, user=user)
    verify_and_get_region(ibm_cloud=ibm_cloud, region_id=region_id)
    verify_references(cloud_id=cloud_id, body_schema=IBMReservedIpInSchema, resource_schema=IBMReservedIpResourceSchema,
                      data=data)
    workflow_root = create_ibm_resource_creation_workflow(
        user=user, resource_type=IBMSubnetReservedIp, validate=False, data=data
    )

    return workflow_root.to_json()


@ibm_subnets.delete('/subnets/reserved_ips/<reserved_ip_id>')
@authenticate
@output(WorkflowRootOutSchema, status_code=202)
def release_reserved_ip_for_subnet(reserved_ip_id, user):
    """
    Release a Reserve Ip for IBM Subnet
    """
    reserved_ip = ibmdb.session.query(IBMSubnetReservedIp).filter_by(
        id=reserved_ip_id).first()
    if not reserved_ip:
        message = f"IBM Subnet Reserved Ip {reserved_ip_id} does not exist"
        LOGGER.error(message)
        abort(404, message)

    authorize_and_get_ibm_cloud(cloud_id=reserved_ip.subnet.ibm_cloud.id, user=user)
    workflow_root = compose_ibm_resource_deletion_workflow(
        user=user, resource_type=IBMSubnetReservedIp, resource_id=reserved_ip.id
    )

    return workflow_root.to_json()
