import logging

from apiflask import abort
from sqlalchemy.orm.exc import StaleDataError

from ibm.common.utils import verify_and_yield_references
from ibm.models import IBMCloud, IBMInstance, IBMKubernetesCluster, IBMLoadBalancer, IBMPublicGateway, \
    IBMSubnet, IBMTag, IBMVpcNetwork, IBMVpnGateway, IBMZone, WorkflowRoot, WorkflowTask, IBMTransitGateway, \
    IBMTransitGatewayConnection, IBMVpnConnection
from ibm.web import db as ibmdb

LOGGER = logging.getLogger(__name__)


def get_paginated_response_json(items, pagination_obj):
    return {
        "items": items,
        "previous_page": pagination_obj.prev_num if pagination_obj.has_prev else None,
        "next_page": pagination_obj.next_num if pagination_obj.has_next else None,
        "total_pages": pagination_obj.pages
    }


def create_ibm_resource_creation_workflow(user, resource_type, data, db_session=None, validate=True, sketch=False,
                                          status=False):
    if not db_session:
        db_session = ibmdb.session

    workflow_name = resource_type.__name__
    if data["resource_json"].get("name"):
        workflow_name = ' '.join([workflow_name, data["resource_json"]["name"]])

    workflow_root = WorkflowRoot(
        user_id=user["id"], project_id=user["project_id"], workflow_name=workflow_name, workflow_nature="CREATE",
        fe_request_data=data
    )

    creation_task = WorkflowTask(
        task_type=WorkflowTask.TYPE_CREATE, resource_type=resource_type.__name__, task_metadata={"resource_data": data}
    )
    workflow_root.add_next_task(creation_task)
    for tag in data.get('tags', []):
        tag_task = WorkflowTask(
            task_type=WorkflowTask.TYPE_CREATE, resource_type=IBMTag.__name__,
            task_metadata={"resource_data": tag})
        creation_task.add_next_task(tag_task)

    if validate:
        validation_task = WorkflowTask(task_type=WorkflowTask.TYPE_VALIDATE, resource_type=resource_type.__name__,
                                       task_metadata={"resource_data": data})
        creation_task.add_previous_task(validation_task)
    if status:
        workflow_root.status = WorkflowRoot.STATUS_C_SUCCESSFULLY
        creation_task.status = WorkflowTask.STATUS_SUCCESSFUL

    if resource_type == IBMVpnGateway:
        ibm_cloud_id = data["ibm_cloud"]["id"]
        region_id = data["region"]["id"]
        for connection_data in data["resource_json"].get("connections", []):
            connection_data = {
                "ibm_cloud": {"id": ibm_cloud_id},
                "region": {"id": region_id},
                "vpn_gateway": {"name": data["resource_json"]["name"]},
                "resource_json": connection_data
            }

            conn_creation_task = WorkflowTask(
                task_type=WorkflowTask.TYPE_CREATE, resource_type=IBMVpnConnection.__name__,
                task_metadata={"resource_data": connection_data}
            )

            creation_task.add_next_task(conn_creation_task)
    if not sketch:
        db_session.add(workflow_root)

    db_session.commit()
    return workflow_root


def create_kubernetes_restore_workflow(user, resource_type, data, db_session=None, sketch=False):
    if not db_session:
        db_session = ibmdb.session

    resource_id_or_name = f"{data['cluster']['name'] if data['cluster'].get('name') else data['cluster']['id']}"
    workflow_name = f"{resource_type.__name__} {resource_id_or_name}"
    workflow_root = WorkflowRoot(
        user_id=user["id"], project_id=user["project_id"], workflow_name=workflow_name, workflow_nature="RESTORE",
        fe_request_data=data
    )
    restore_task = WorkflowTask(
        task_type=WorkflowTask.TYPE_RESTORE, resource_type=resource_type.__name__,
        task_metadata={"resource_data": data}
    )
    workflow_root.add_next_task(restore_task)

    if not sketch:
        db_session.add(workflow_root)

    db_session.commit()
    return workflow_root


def compose_ibm_sync_resource_workflow(user, resource_type, data=None, p_data=None):
    """
    This function can use be used for `SYNC` workflows creation.
    :param user:
    :param resource_type:
    :param data:
    :param p_data: private/sensitive data that should be a part of taskmetadata but should not be returned to FE.
    :return:
    """

    workflow_name = resource_type if isinstance(resource_type, str) else resource_type.__name__
    resource_data = data if data else None
    task_metadata = {"resource_data": {**resource_data, **p_data}} if p_data \
        else {"resource_data": resource_data}

    workflow_root = WorkflowRoot(
        user_id=user["id"], project_id=user["project_id"], workflow_name=workflow_name, workflow_nature="SYNC",
        fe_request_data=data
    )
    task = WorkflowTask(
        task_type="SYNC",
        resource_type=resource_type if isinstance(resource_type, str) else resource_type.__name__,
        task_metadata=task_metadata,
    )
    workflow_root.add_next_task(task)

    ibmdb.session.add(workflow_root)
    ibmdb.session.commit()
    return workflow_root


def compose_ibm_resource_deletion_workflow(user, resource_type, resource_id, data=None):
    workflow_root = WorkflowRoot(
        user_id=user["id"],
        project_id=user["project_id"],
        workflow_name=f"{resource_type.__name__} ({resource_id})",
        workflow_nature="DELETE"
    )
    deletion_task = WorkflowTask(
        task_type=WorkflowTask.TYPE_DELETE, resource_type=resource_type.__name__, resource_id=resource_id,
        task_metadata={"resource_id": resource_id}
    )
    if data:
        deletion_task.task_metadata = {"task_metadata": data}
    workflow_root.add_next_task(deletion_task)
    ibmdb.session.add(workflow_root)
    ibmdb.session.commit()
    return workflow_root


def compose_ibm_vpc_deletion_workflow(user, resource_type, resource_id, db_session=None):
    db_session = db_session if db_session else ibmdb.session
    vpc = db_session.query(IBMVpcNetwork).filter_by(id=resource_id).first()
    workflow_name = f"{resource_type.__name__} {vpc.name}",
    # Delete workspace as well
    workflow_root = db_session.query(WorkflowRoot).filter_by(workflow_name=workflow_name).first()
    if workflow_root:
        if workflow_root.workspace:
            try:
                db_session.delete(workflow_root.workflow_workspace)
                db_session.commit()
            except StaleDataError:
                ibmdb.session.rollback()
    workflow_root = WorkflowRoot(
        user_id=user["id"],
        project_id=user["project_id"],
        workflow_name=workflow_name,
        workflow_nature="DELETE"
    )
    vpc_deletion_task = WorkflowTask(
        task_type=WorkflowTask.TYPE_DELETE, resource_type=IBMVpcNetwork.__name__, resource_id=resource_id
    )
    workflow_root.add_next_task(vpc_deletion_task)

    instances_id_tasks_dict, cluster_id_tasks_dict, lb_id_tasks_dict, subnet_id_tasks_dict = {}, {}, {}, {}

    for subnet in vpc.subnets.all():
        if subnet.id in subnet_id_tasks_dict:
            continue

        subnet_deletion_task = WorkflowTask(
            task_type=WorkflowTask.TYPE_DELETE, resource_type=IBMSubnet.__name__, resource_id=subnet.id,
            task_metadata={"resource_id": subnet.id}
        )
        vpc_deletion_task.add_previous_task(subnet_deletion_task)
        subnet_id_tasks_dict[subnet.id] = subnet_deletion_task

        for load_balancer in subnet.load_balancers.all():
            if load_balancer.id in lb_id_tasks_dict:
                continue
            load_balancer_deletion_task = WorkflowTask(
                task_type=WorkflowTask.TYPE_DELETE, resource_type=IBMLoadBalancer.__name__,
                resource_id=load_balancer.id
            )
            subnet_deletion_task.add_previous_task(load_balancer_deletion_task)
            lb_id_tasks_dict[load_balancer.id] = load_balancer_deletion_task

        for network_interface in subnet.network_interfaces.all():
            if network_interface.instance.id in instances_id_tasks_dict:
                continue

            instance_deletion_task = WorkflowTask(
                task_type=WorkflowTask.TYPE_DELETE, resource_type=IBMInstance.__name__,
                resource_id=network_interface.instance.id
            )

            subnet_deletion_task.add_previous_task(instance_deletion_task)
            instances_id_tasks_dict[network_interface.instance.id] = instance_deletion_task

        for cluster in vpc.kubernetes_clusters.all():
            if cluster.id in cluster_id_tasks_dict:
                continue
            cluster_deletion_task = WorkflowTask(
                task_type=WorkflowTask.TYPE_DELETE, resource_type=IBMKubernetesCluster.__name__,
                resource_id=cluster.id
            )
            subnet_deletion_task.add_previous_task(cluster_deletion_task)
            cluster_id_tasks_dict[cluster.id] = cluster_deletion_task

        for vpn_gateway in subnet.vpn_gateways.all():
            if vpn_gateway.status == IBMVpnGateway.STATUS_PENDING:
                message = "You can not delete a vpn gateway having status pending on ibm cloud"
                LOGGER.debug(message)
                abort(400, message)
            vpn_gateway_deletion_task = WorkflowTask(
                task_type=WorkflowTask.TYPE_DELETE, resource_type=IBMVpnGateway.__name__,
                resource_id=vpn_gateway.id
            )
            subnet_deletion_task.add_previous_task(vpn_gateway_deletion_task)

    for instance in vpc.instances.all():
        if instance.id in instances_id_tasks_dict:
            continue
        instance_deletion_task = WorkflowTask(
            task_type=WorkflowTask.TYPE_DELETE, resource_type=IBMInstance.__name__,
            resource_id=instance.id
        )
        vpc_deletion_task.add_previous_task(instance_deletion_task)
        instances_id_tasks_dict[instance.id] = instance_deletion_task

    for public_gateway in vpc.public_gateways.all():
        public_gateway_deletion_task = WorkflowTask(
            task_type=WorkflowTask.TYPE_DELETE, resource_type=IBMPublicGateway.__name__,
            resource_id=public_gateway.id
        )
        vpc_deletion_task.add_previous_task(public_gateway_deletion_task)

        for subnet in public_gateway.subnets.all():
            task_metadata = {
                "subnet": {
                    "id": subnet.id
                },
                "region": {
                    "id": subnet.region.id
                }
            }
            pg_subnet_detachment_task = WorkflowTask(
                task_type=WorkflowTask.TYPE_DETACH, resource_type=f'{IBMSubnet.__name__}-{IBMPublicGateway.__name__}',
                resource_id=subnet.id, task_metadata={"resource_data": task_metadata}
            )
            public_gateway_deletion_task.add_previous_task(pg_subnet_detachment_task)

    db_session.add(workflow_root)
    db_session.commit()
    return workflow_root


def compose_ibm_resource_attachment_workflow(
        user, data, resource_id=None, resource_type=None, resource_type_name=None, db_session=None, sketch=False
):
    if not db_session:
        db_session = ibmdb.session

    if not resource_type_name:
        resource_type_name = resource_type.__name__

    workflow_root = WorkflowRoot(
        user_id=user["id"],
        project_id=user["project_id"],
        workflow_name=f"{resource_type_name} ({resource_id})",
        workflow_nature=WorkflowTask.TYPE_ATTACH
    )
    attach_task = WorkflowTask(
        task_type=WorkflowTask.TYPE_ATTACH, resource_type=resource_type_name, resource_id=resource_id,
        task_metadata={"resource_data": data}
    )
    workflow_root.add_next_task(attach_task)

    if not sketch:
        db_session.add(workflow_root)

    db_session.commit()
    return workflow_root


def compose_ibm_resource_detachment_workflow(user, resource_type, resource_id, data):
    workflow_name = resource_type if isinstance(resource_type, str) else resource_type.__name__
    workflow_root = WorkflowRoot(
        user_id=user["id"],
        project_id=user["project_id"],
        workflow_name=workflow_name,
        workflow_nature="DETACH"
    )
    detach_task = WorkflowTask(
        task_type=WorkflowTask.TYPE_DETACH,
        resource_type=resource_type if isinstance(resource_type, str) else resource_type.__name__,
        resource_id=resource_id,
        task_metadata={"resource_data": data}
    )
    workflow_root.add_next_task(detach_task)
    ibmdb.session.add(workflow_root)
    ibmdb.session.commit()
    return workflow_root


def authorize_and_get_ibm_cloud(cloud_id, user):
    ibm_cloud = \
        ibmdb.session.query(IBMCloud).filter_by(
            id=cloud_id, user_id=user["id"], project_id=user["project_id"], deleted=False
        ).first()
    if not ibm_cloud:
        message = f"IBM Cloud {cloud_id} not found"
        LOGGER.debug(message)
        abort(404, message)
    if ibm_cloud.status != IBMCloud.STATUS_VALID:
        message = f"IBM Cloud {ibm_cloud.name} is not in {IBMCloud.STATUS_VALID} status"
        LOGGER.debug(message)
        abort(404, message)

    return ibm_cloud


def verify_and_get_region(ibm_cloud, region_id):
    region = ibm_cloud.regions.filter_by(id=region_id).first()
    if not region:
        message = f"IBM Region {region_id} does not exist"
        LOGGER.debug(message)
        abort(404, message)

    return region


def verify_and_get_zone(cloud_id, zone_id):
    zone = ibmdb.session.query(IBMZone).filter_by(id=zone_id, cloud_id=cloud_id).first()
    if not zone:
        message = f"IBM Zone {zone_id} does not exist"
        LOGGER.debug(message)
        abort(404, message)

    return zone


def verify_references(cloud_id, body_schema, resource_schema, data):
    body_ref_generator = verify_and_yield_references(
        cloud_id=cloud_id, resource_schema=body_schema, data=data, db_session=ibmdb.session
    )
    for _, _, _, message in body_ref_generator:
        if message:
            abort(404, message)

    resource_ref_generator = verify_and_yield_references(
        cloud_id=cloud_id, resource_schema=resource_schema, data=data["resource_json"],
        db_session=ibmdb.session
    )
    for _, _, _, message in resource_ref_generator:
        if message:
            abort(404, message)


def verify_nested_references(cloud_id, nested_resource_schema, data):
    resource_ref_generator = verify_and_yield_references(
        cloud_id=cloud_id, resource_schema=nested_resource_schema, data=data,
        db_session=ibmdb.session
    )
    for _, _, _, message in resource_ref_generator:
        if message:
            abort(404, message)


def compose_ibm_transit_gateway_deletion_workflow(user, resource_type, resource_id, db_session=None):
    db_session = db_session if db_session else ibmdb.session
    transit_gateway = db_session.query(IBMTransitGateway).filter_by(id=resource_id).first()
    workflow_name = f"{resource_type.__name__} {transit_gateway.name}",
    # Delete workspace as well
    workflow_root = db_session.query(WorkflowRoot).filter_by(workflow_name=workflow_name).first()
    if workflow_root:
        if workflow_root.workspace:
            try:
                db_session.delete(workflow_root.workflow_workspace)
                db_session.commit()
            except StaleDataError:
                ibmdb.session.rollback()
    workflow_root = WorkflowRoot(
        user_id=user["id"],
        project_id=user["project_id"],
        workflow_name=workflow_name,
        workflow_nature="DELETE"
    )
    transit_gateway_deletion_task = WorkflowTask(
        task_type=WorkflowTask.TYPE_DELETE, resource_type=IBMTransitGateway.__name__, resource_id=resource_id,
        task_metadata={"resource_id": resource_id}
    )
    workflow_root.add_next_task(transit_gateway_deletion_task)

    connection_id_tasks_dict = {}

    for connection in transit_gateway.connections.all():
        if connection.id in connection_id_tasks_dict:
            continue

        connection_deletion_task = WorkflowTask(
            task_type=WorkflowTask.TYPE_DELETE, resource_type=IBMTransitGatewayConnection.__name__,
            resource_id=connection.id, task_metadata={"resource_id": connection.id}
        )
        transit_gateway_deletion_task.add_previous_task(connection_deletion_task)
        connection_id_tasks_dict[connection.id] = connection_deletion_task

    db_session.add(workflow_root)
    db_session.commit()
    return workflow_root
