import logging

from apiflask import abort, APIBlueprint, input, output

from ibm.auth import authenticate
from ibm.common.req_resp_schemas.schemas import get_pagination_schema, IBMInstanceResourceQuerySchema, \
    PaginationQuerySchema, WorkflowRootOutSchema
from ibm.models import IBMFloatingIP, IBMInstance, IBMNetworkInterface
from ibm.web import db as ibmdb
from ibm.web.common.utils import authorize_and_get_ibm_cloud, compose_ibm_resource_attachment_workflow, \
    compose_ibm_resource_deletion_workflow, compose_ibm_resource_detachment_workflow, \
    create_ibm_resource_creation_workflow, \
    get_paginated_response_json, verify_and_get_region, verify_references
from .schemas import IBMInstanceNetworkInterfaceInSchema, IBMInstanceNetworkInterfaceOutSchema, \
    IBMInstanceNetworkInterfaceResourceSchema, IBMInstanceNetworkInterfaceUpdateSchema

LOGGER = logging.getLogger(__name__)

ibm_network_interfaces = APIBlueprint('ibm_network_interfaces', __name__, tag="IBM Network Interfaces")


@ibm_network_interfaces.post('/network_interfaces')
@authenticate
@input(IBMInstanceNetworkInterfaceInSchema)
@output(WorkflowRootOutSchema, status_code=202)
def create_ibm_network_interface(data, user):
    """
    Create IBM Network Interface
    This request create a network interface to an instance on IBM Cloud with VPC+.
    """
    cloud_id = data["ibm_cloud"]["id"]
    region_id = data["region"]["id"]
    instance_id = data["instance"]["id"]

    ibm_cloud = authorize_and_get_ibm_cloud(cloud_id=cloud_id, user=user)
    verify_and_get_region(ibm_cloud=ibm_cloud, region_id=region_id)

    instance = ibmdb.session.query(IBMInstance).filter_by(id=instance_id, cloud_id=cloud_id).first()
    if not instance:
        message = f"IBM Instance {instance_id} does not exist"
        LOGGER.debug(message)
        abort(404, message)

    verify_references(
        cloud_id=cloud_id, body_schema=IBMInstanceNetworkInterfaceInSchema,
        resource_schema=IBMInstanceNetworkInterfaceResourceSchema, data=data
    )

    workflow_root = create_ibm_resource_creation_workflow(
        user=user, resource_type=IBMNetworkInterface, data=data, validate=False
    )
    return workflow_root.to_json()


@ibm_network_interfaces.route('/network_interfaces/<network_interface_id>', methods=['GET'])
@authenticate
@output(IBMInstanceNetworkInterfaceOutSchema, status_code=202)
def get_ibm_network_interface(network_interface_id, user):
    """
    Get IBM Network Interface
    This request will fetch IBM Network Interface from IBM Cloud attached to an instance
    """
    network_interface = ibmdb.session.query(IBMNetworkInterface).filter_by(
        id=network_interface_id
    ).join(IBMNetworkInterface.ibm_cloud).filter_by(
        user_id=user["id"], project_id=user["project_id"], deleted=False
    ).first()
    if not network_interface:
        message = f"IBM Network Interface {network_interface_id} does not exist"
        LOGGER.debug(message)
        abort(404, message)
    return network_interface.to_json()


@ibm_network_interfaces.get('/network_interfaces')
@authenticate
@input(IBMInstanceResourceQuerySchema, location='query')
@input(PaginationQuerySchema, location='query')
@output(get_pagination_schema(IBMInstanceNetworkInterfaceOutSchema))
def list_ibm_network_interfaces(instance_res_query_params, pagination_query_params, user):
    """
    List IBM Network Interfaces
    This request fetches all Network Interface from IBM Cloud attached to an instance
    """
    cloud_id = instance_res_query_params["cloud_id"]
    instance_id = instance_res_query_params.get("instance_id")
    subnet_id = instance_res_query_params.get("subnet_id")

    ibm_cloud = authorize_and_get_ibm_cloud(cloud_id=cloud_id, user=user)

    interfaces_query = ibmdb.session.query(IBMNetworkInterface).filter_by(cloud_id=cloud_id)

    if instance_id:
        instance = ibm_cloud.instances.filter_by(id=instance_id).first()
        if not instance:
            message = f"IBM Instance {instance_id} does not exist"
            LOGGER.debug(message)
            abort(404, message)
        interfaces_query = interfaces_query.filter_by(instance_id=instance_id)

    if subnet_id:
        subnet = ibm_cloud.subnets.filter_by(id=subnet_id).first()
        if not subnet:
            message = f"IBMSubnet {subnet_id} does not exist"
            LOGGER.debug(message)
            abort(404, message)
        interfaces_query = interfaces_query.filter_by(subnet_id=subnet_id)

    instances_page = interfaces_query.paginate(
        page=pagination_query_params["page"], per_page=pagination_query_params["per_page"], error_out=False
    )
    if not instances_page.items:
        return '', 204

    return get_paginated_response_json(
        items=[item.to_json() for item in instances_page.items],
        pagination_obj=instances_page
    )


@ibm_network_interfaces.route('/network_interfaces/<network_interface_id>', methods=['PATCH'])
@authenticate
@input(IBMInstanceNetworkInterfaceUpdateSchema)
@output(WorkflowRootOutSchema, status_code=202)
def update_ibm_network_interface(network_interface_id, data, user):
    """
    Update IBM Network Interface
    This request updates an IBM Network Interface attached to an instance
    """
    abort(404)


@ibm_network_interfaces.route('/network_interfaces/<network_interface_id>', methods=['DELETE'])
@authenticate
@output(WorkflowRootOutSchema, status_code=202)
def delete_ibm_network_interface(network_interface_id, user):
    """
    Delete IBM Network Interface
    This request deletes an IBM Network Interface provided its ID.
    """
    network_interface = ibmdb.session.query(IBMNetworkInterface).filter_by(
        id=network_interface_id
    ).join(IBMNetworkInterface.ibm_cloud).filter_by(
        user_id=user["id"], project_id=user["project_id"], deleted=False
    ).first()
    if not network_interface:
        message = f"IBM Network Interface {network_interface_id} does not exist"
        LOGGER.debug(message)
        abort(404, message)

    # TODO: Uncomment when we have update api calls.
    # if not network_interface.is_deletable:
    #     message = f"IBM Network Interface {network_interface_id} is primary and cannot be deleted."
    #     LOGGER.debug(message)
    #     abort(403, message)

    return compose_ibm_resource_deletion_workflow(
        user=user, resource_type=IBMNetworkInterface, resource_id=network_interface_id
    ).to_json(metadata=True)


@ibm_network_interfaces.delete('/network_interfaces/<network_interface_id>/floating_ips/<floating_ip_id>')
@authenticate
@output(WorkflowRootOutSchema, status_code=202)
def disassociate_ibm_network_interface_floating_ip(network_interface_id, floating_ip_id, user):
    """
    Disassociate a floating IP from a network interface
    This request disassociates the specified floating IP from the specified network interface
    """
    network_interface = ibmdb.session.query(IBMNetworkInterface).filter_by(id=network_interface_id).first()
    if not network_interface:
        message = f"IBM Network Interface {network_interface_id} not found."
        LOGGER.debug(message)
        abort(404, message)

    floating_ip = ibmdb.session.query(IBMFloatingIP).filter_by(id=floating_ip_id).first()
    if not floating_ip:
        message = f"IBM Floating IP {floating_ip_id} not found."
        LOGGER.debug(message)
        abort(404, message)

    authorize_and_get_ibm_cloud(cloud_id=floating_ip.ibm_cloud.id, user=user)
    data = {
        "network_interface_id": network_interface_id,
        "floating_ip_id": floating_ip_id
    }
    workflow_root = compose_ibm_resource_detachment_workflow(
        user=user, resource_type=f'{IBMFloatingIP.__name__}-{IBMNetworkInterface.__name__}',
        resource_id=network_interface_id, data=data)

    return workflow_root.to_json()


@ibm_network_interfaces.put('/network_interfaces/<network_interface_id>/floating_ips/<floating_ip_id>')
@authenticate
@output(WorkflowRootOutSchema, status_code=202)
def associate_ibm_network_interface_floating_ip(network_interface_id, floating_ip_id, user):
    """
    Associate a floating IP with a network interface
    This request associates the specified floating IP with the specified network interface, replacing any existing
     association. For this request to succeed, the existing floating IP must not be required by another resource,
     such as a public gateway. A request body is not required, and if supplied, is ignored.
    """
    network_interface = ibmdb.session.query(IBMNetworkInterface).filter_by(id=network_interface_id).first()
    if not network_interface:
        message = f"IBM Network Interface {network_interface_id} not found."
        LOGGER.debug(message)
        abort(404, message)

    floating_ip = ibmdb.session.query(IBMFloatingIP).filter_by(id=floating_ip_id).first()
    if not floating_ip:
        message = f"IBM Floating IP {floating_ip_id} not found."
        LOGGER.debug(message)
        abort(404, message)

    authorize_and_get_ibm_cloud(cloud_id=floating_ip.ibm_cloud.id, user=user)
    data = {
        "network_interface_id": {"id": network_interface_id},
        "floating_ip_id": {"id": floating_ip_id}
    }
    workflow_root = compose_ibm_resource_attachment_workflow(
        user=user, resource_type_name=f'{IBMFloatingIP.__name__}-{IBMNetworkInterface.__name__}',
        resource_id=network_interface_id, data=data
    )

    return workflow_root.to_json()
