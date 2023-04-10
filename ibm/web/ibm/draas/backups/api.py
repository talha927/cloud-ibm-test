import logging
from datetime import datetime

from apiflask import abort, input, output
from sqlalchemy.orm import undefer

from ibm.auth import authenticate
from ibm.common.req_resp_schemas.schemas import get_pagination_schema, IBMResourceQuerySchema, PaginationQuerySchema, \
    WorkflowRootOutSchema
from ibm.middleware import log_draas_activity
from ibm.models import DisasterRecoveryBackup, DisasterRecoveryResourceBlueprint, DisasterRecoveryScheduledPolicy, \
    IBMKubernetesCluster, WorkflowRoot, \
    WorkflowTask
from ibm.web import db as ibmdb
from ibm.web.common.utils import authorize_and_get_ibm_cloud, compose_ibm_resource_deletion_workflow, \
    get_paginated_response_json
from ibm.web.ibm.draas import ibm_draas
from .consts import DRAAS_RESOURCE_TO_BACKUP_404, RESOURCE_TYPE_IBM_VPC_NETWORK, RESOURCE_TYPE_IKS
from .schemas import DisasterRecoveryBackupInSchema, DisasterRecoveryBackupOutSchema, \
    DisasterRecoveryBlueprintOutSchema, DisasterRecoveryBlueprintQuerySchema
from .utils import create_ibm_draas_backup_workflow
from ..utils import DRAAS_RESOURCE_TYPE_TO_MODEL_MAPPER
from ...instances.backups.utils import create_instances_backup_workflow

LOGGER = logging.getLogger(__name__)


@ibm_draas.route('/draas_blueprints', methods=['GET'])
@authenticate
@input(DisasterRecoveryBlueprintQuerySchema, location='query')
@input(PaginationQuerySchema, location='query')
@output(get_pagination_schema(DisasterRecoveryBlueprintOutSchema))
def list_draas_blueprints(blueprint_query_params, pagination_query_params, user):
    """
    List Disaster Recovery Blueprints
    This request list all Disaster Recovery Blueprints for a given cloud
    """
    cloud_id = blueprint_query_params["cloud_id"]
    authorize_and_get_ibm_cloud(cloud_id=cloud_id, user=user)
    resource_type = blueprint_query_params["resource_type"]

    blueprints_query = ibmdb.session.query(DisasterRecoveryResourceBlueprint).filter_by(
        cloud_id=cloud_id, resource_type=resource_type)

    blueprints_page = blueprints_query.paginate(
        page=pagination_query_params["page"], per_page=pagination_query_params["per_page"], error_out=False
    )

    if not blueprints_page.items:
        message = f"No Disaster Recovery Blueprints found with ID: {cloud_id}"
        LOGGER.debug(message)
        return '', 204

    return get_paginated_response_json(
        items=[item.to_json(data=True) for item in blueprints_page.items],
        pagination_obj=blueprints_page
    )


@ibm_draas.route('draas_blueprints/<blueprint_id>', methods=['GET'])
@authenticate
@output(DisasterRecoveryBlueprintOutSchema)
def get_blueprint(blueprint_id, user):
    """
    Get a Disaster Recovery Blueprint
    This request get a Disaster Recovery Blueprint for a given blueprint_id
    """

    draas_blueprint = ibmdb.session.query(DisasterRecoveryResourceBlueprint).filter_by(id=blueprint_id).first()
    if not draas_blueprint:
        message = f"No Disaster recovery Blueprint found with ID {blueprint_id}"
        LOGGER.debug(message)
        abort(404, message)

    if draas_blueprint.resource_type == RESOURCE_TYPE_IBM_VPC_NETWORK:
        return draas_blueprint.to_json(data=True)
    elif draas_blueprint.resource_type == RESOURCE_TYPE_IKS:
        kubernetes_cluster = ibmdb.session.query(IBMKubernetesCluster).filter_by(
            id=draas_blueprint.resource_id
        ).options(undefer("workloads")).first()
        if not kubernetes_cluster:
            message = f"IBM Kubernetes Cluster {draas_blueprint.resource_id} does not exist"
            LOGGER.debug(message)
            abort(404, message)

        draas_blueprints = draas_blueprint.to_json(data=True)
        draas_blueprints["resource_metadata"] = kubernetes_cluster.ibm_draas_json()
        return draas_blueprints


@ibm_draas.delete('/draas_blueprints/<blueprint_id>')
@authenticate
@output(WorkflowRootOutSchema, status_code=202)
def delete_draas_blueprint(blueprint_id, user):
    """
    Delete a Disaster Recovery Blueprint
    This request deletes a Disaster Recovery Blueprint for a given blueprint_id
    """

    draas_blueprint = ibmdb.session.query(DisasterRecoveryResourceBlueprint).filter_by(
        id=blueprint_id).first()

    if not draas_blueprint:
        message = f"No Disaster Recovery Blueprint found with ID {blueprint_id}"
        LOGGER.debug(message)
        abort(404, message)

    delete_workflow_root = compose_ibm_resource_deletion_workflow(
        user=user, resource_type=DisasterRecoveryResourceBlueprint,
        resource_id=blueprint_id
    )

    return delete_workflow_root.to_json(metadata=True)


@ibm_draas.get('/draas_blueprints/<blueprint_id>/backups')
@authenticate
@input(IBMResourceQuerySchema, location='query')
@input(PaginationQuerySchema, location='query')
@output(get_pagination_schema(DisasterRecoveryBackupOutSchema))
def list_draas_backups(blueprint_id, res_query_params, pagination_query_params, user):
    """
    List all Disaster Recovery Backups
    This request lists all Disaster Recovery Backups for a given blueprint_id
    """
    cloud_id = res_query_params["cloud_id"]
    authorize_and_get_ibm_cloud(cloud_id=cloud_id, user=user)

    blueprint = ibmdb.session.query(DisasterRecoveryResourceBlueprint).filter_by(id=blueprint_id).first()
    if not blueprint:
        message = f"No Disaster recovery Blueprint found with ID {blueprint_id}"
        LOGGER.debug(message)
        abort(404, message)

    # TODO: check if we can do this by doing 'blueprint.backups' ?
    backups_query = ibmdb.session.query(DisasterRecoveryBackup).filter_by(
        disaster_recovery_resource_blueprint_id=blueprint.id)
    backups_query_page = backups_query.paginate(
        page=pagination_query_params["page"], per_page=pagination_query_params["per_page"], error_out=False
    )
    if not backups_query_page.items:
        message = f"No Disaster Recovery Backups found for Blueprint with ID: {blueprint_id}"
        LOGGER.debug(message)
        return '', 204

    return get_paginated_response_json(
        items=[item.to_json() for item in backups_query_page.items],
        pagination_obj=backups_query_page
    )


@ibm_draas.route('/draas_backups', methods=['POST'])
@authenticate
@log_draas_activity
@input(DisasterRecoveryBackupInSchema)
@output(WorkflowRootOutSchema, status_code=202)
def create_draas_backup(data, user):
    """
    Create Disaster Recovery Backup
    This request creates a Disaster Recovery Backup
    """
    ibm_cloud = authorize_and_get_ibm_cloud(cloud_id=data["ibm_cloud"]["id"], user=user)

    if data["resource_type"] == RESOURCE_TYPE_IKS:
        kubernetes_cluster = ibmdb.session.query(IBMKubernetesCluster).filter_by(
            id=data["resource_id"]
        ).first()
        if not kubernetes_cluster:
            message = f'IBM Kubernetes Cluster {data["resource_id"]} does not exist'
            LOGGER.debug(message)
            abort(404, message)

        task_metadata = {
            "ibm_cloud": {
                "id": data["ibm_cloud"]["id"],
            },
            "cos_bucket_id": data["cos_bucket_id"],
            "cloud_object_storage_id": data["cloud_object_storage_id"],
            "cos_access_keys_id": data["cos_access_keys_id"],
            "cluster_id": data["resource_id"],
            "description": data.get("description"),
            "blueprint_name": kubernetes_cluster.name,
            "backup_name": data["name"] + f"-{datetime.now().strftime('%d-%m-%Y-%H.%M.%S')}",
            "resource_json": kubernetes_cluster.backup_json(namespaces=data["namespaces"]),
            "resource_type": data["resource_type"],
            "region": {
                "id": data["region"]["id"],
            },
            "namespaces": data["namespaces"],
            "scheduled_policy": data.get("scheduled_policy"),
            "user": user
        }

        workflow_root = create_ibm_draas_backup_workflow(data=task_metadata, user=user)
        return workflow_root.to_json(metadata=True)

    elif data["resource_type"] == RESOURCE_TYPE_IBM_VPC_NETWORK:
        resource_id = data["resource_id"]
        resource_type = data["resource_type"]
        resource_model = DRAAS_RESOURCE_TYPE_TO_MODEL_MAPPER[resource_type]
        db_resource = ibmdb.session.query(resource_model).filter_by(id=resource_id).first()
        if not db_resource:
            msg = DRAAS_RESOURCE_TO_BACKUP_404.format(**data)
            LOGGER.info(msg)
            abort(404, msg)

        metadata = {
            "resource_id": db_resource.id,
            "resource_type": data["resource_type"],
            "name": data["name"],
            "region": {"id": db_resource.region.id, "name": db_resource.region.name},
            "vpc": {"id": db_resource.id, "name": db_resource.name},
            "resource_group": {"id": db_resource.resource_group.id, "name": db_resource.resource_group.name}
        }

        scheduled_policy_state = DisasterRecoveryResourceBlueprint.SCHEDULED_POLICY_ACTIVE_STATE if \
            data.get("scheduled_policy") else DisasterRecoveryResourceBlueprint.SCHEDULED_POLICY_INACTIVE_STATE
        draas_resource_blueprint: DisasterRecoveryResourceBlueprint = \
            ibmdb.session.query(DisasterRecoveryResourceBlueprint).filter_by(resource_id=db_resource.id).first()
        if not draas_resource_blueprint:
            draas_resource_blueprint = DisasterRecoveryResourceBlueprint(
                resource_id=db_resource.id,
                name=data["name"],
                resource_type=data["resource_type"],
                resource_metadata=metadata,
                user_id=user["id"],
                description=data.get("description"),
                scheduled_policy_state=scheduled_policy_state
            )
            draas_resource_blueprint.ibm_cloud = ibm_cloud
            ibmdb.session.commit()

        scheduled_policy = data.get("scheduled_policy")
        if scheduled_policy:
            if scheduled_policy.get("id"):
                db_scheduled_policy = ibmdb.session.query(DisasterRecoveryScheduledPolicy).filter_by(
                    id=scheduled_policy["id"]
                ).first()
                draas_resource_blueprint.disaster_recovery_scheduled_policy = db_scheduled_policy
            elif scheduled_policy.get("scheduled_cron_pattern"):
                db_scheduled_policy = DisasterRecoveryScheduledPolicy(
                    scheduled_cron_pattern=scheduled_policy["scheduled_cron_pattern"],
                    backup_count=scheduled_policy.get("backup_count"), description=scheduled_policy.get("description")
                )
                db_scheduled_policy.ibm_cloud = ibm_cloud
                draas_resource_blueprint.disaster_recovery_scheduled_policy = db_scheduled_policy
                ibmdb.session.commit()

        backup_workflow_root = WorkflowRoot(
            workflow_name=f"{resource_type} {data['name']}",
            workflow_nature="BACKUP",
            project_id=user["project_id"],
            user_id=user["id"]
        )
        backup_task = WorkflowTask(
            resource_type=data["resource_type"],
            task_type=WorkflowTask.TYPE_BACKUP,
            task_metadata={'draas_resource_blueprint_id': draas_resource_blueprint.id,
                           "email": user.get("email"),
                           "project_id": user.get("project_id"),
                           "is_volume": data.get("instances_data") or False}
        )
        backup_workflow_root.add_next_task(backup_task)
        ibmdb.session.add(backup_workflow_root)
        ibmdb.session.commit()

        if data.get("instances_data"):
            create_instances_backup_workflow(
                user=user, vpc_id=resource_id, backup_task_id=backup_task.id, db_session=None, delete_instance=False
            )
        return backup_workflow_root.to_json(metadata=True)


@ibm_draas.route('/draas_backups/<backup_id>', methods=['GET'])
@authenticate
@output(DisasterRecoveryBackupOutSchema, status_code=202)
def get_draas_backup(backup_id, user):
    """
    Get Disaster Recovery Backup
    This request gets a Disaster Recovery Backup for a given backup_id
    """

    draas_backup = ibmdb.session.query(DisasterRecoveryBackup).filter_by(id=backup_id).first()
    if not draas_backup:
        message = f"No Disaster Recovery Backup found with ID {backup_id}"
        LOGGER.debug(message)
        abort(404, message)

    return draas_backup.to_json()


@ibm_draas.route('/draas_backups/<backup_id>', methods=['DELETE'])
@authenticate
@log_draas_activity
@output(WorkflowRootOutSchema, status_code=202)
def delete_draas_backup(backup_id, user):
    """
    Delete Disaster Recovery Backup
    This request deletes Disaster Recovery Backups for a given backup_id
    """

    draas_backup = ibmdb.session.query(DisasterRecoveryBackup).filter_by(id=backup_id).first()
    if not draas_backup:
        message = f"No Disaster Recovery Backup found with ID {backup_id}"
        LOGGER.debug(message)
        abort(404, message)

    delete_workflow_root = compose_ibm_resource_deletion_workflow(
        user=user, resource_type=DisasterRecoveryBackup,
        resource_id=backup_id
    )
    return delete_workflow_root.to_json(metadata=True)
