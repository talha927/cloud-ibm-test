import logging
import random
from copy import deepcopy

from apiflask import abort

from ibm.models import IBMInstance, IBMSnapshot, IBMVpcNetwork, WorkflowRoot, WorkflowTask
from ibm.web import db as ibmdb

LOGGER = logging.getLogger(__name__)


def create_instance_backup_and_delete(user, data, instance_id, db_session=None, delete_instance=True,
                                      root_type=None):
    """
    Create Instance Snapshot and associated Volumes' Snapshots then delete the VM
    """
    if not db_session:
        db_session = ibmdb.session
    ibm_instance = db_session.query(IBMInstance).filter_by(id=instance_id).first()
    if not ibm_instance:
        return
    workflow_name = f"{IBMSnapshot.__name__} {ibm_instance.name}"
    workflow_root = WorkflowRoot(
        user_id=user["id"], project_id=user["project_id"], workflow_name=workflow_name, workflow_nature="CREATE",
        fe_request_data=data
    )
    if root_type:
        workflow_root.root_type = root_type
    if delete_instance:
        deletion_task = WorkflowTask(
            task_type=WorkflowTask.TYPE_DELETE, resource_type=IBMInstance.__name__, resource_id=ibm_instance.id,
            task_metadata={"resource_id": ibm_instance.id}
        )
    resource_data = deepcopy(data)
    resource_data.pop("instance", None)
    resource_data.pop("resource_group", None)
    boot_volume_attachment = ibm_instance.volume_attachments.filter_by(type_="boot").first()
    if not (boot_volume_attachment and boot_volume_attachment.volume):
        abort(404, f"No boot volume for Instance ID: {data['instance']}")
    source_volume = boot_volume_attachment.volume.id
    resource_json = {
        "resource_group": data["resource_group"],
        "source_volume": {"id": source_volume},
        "name": f"snapshot-{ibm_instance.name[:49]}-{random.randint(9, 999)}"
    }
    resource_data["resource_json"] = resource_json
    primary_snapshot_task = WorkflowTask(
        task_type=WorkflowTask.TYPE_CREATE, resource_type=IBMSnapshot.__name__,
        task_metadata={"resource_data": deepcopy(resource_data)}
    )
    volume_snapshot_task_id_mapping_dict = {"boot_volume_snapshot_task": primary_snapshot_task.id}
    workflow_root.add_next_task(primary_snapshot_task)
    if delete_instance:
        primary_snapshot_task.add_next_task(deletion_task)
    ind = 0
    for volume_attachment in ibm_instance.volume_attachments.filter_by(type_="data").all():
        ind += 1
        source_volume = volume_attachment.volume
        name = f"snapshot-{ibm_instance.name[:16]}-{source_volume.id}-{random.randint(0, 9999)}-{ind}"[:62]
        resource_json = {
            "resource_group": data["resource_group"],
            "source_volume": {"id": deepcopy(source_volume.id)},
            "name": f"s{name}t"
        }
        resource_data["resource_json"] = deepcopy(resource_json)
        create_secondary_snapshot_task = WorkflowTask(
            task_type=WorkflowTask.TYPE_CREATE, resource_type=IBMSnapshot.__name__,
            task_metadata={"resource_data": deepcopy(resource_data)}
        )
        workflow_root.add_next_task(create_secondary_snapshot_task)
        volume_snapshot_task_id_mapping_dict[source_volume.name] = create_secondary_snapshot_task.id
        if delete_instance:
            create_secondary_snapshot_task.add_next_task(deletion_task)
    db_session.add(workflow_root)
    db_session.commit()
    return workflow_root, volume_snapshot_task_id_mapping_dict


def create_instances_backup_workflow(user, vpc_id, backup_task_id, db_session=None, delete_instance=True):
    """Create Instances Backup workflows and then update the VPC Restore data for instances with Snapshot references"""
    if not db_session:
        db_session = ibmdb.session

    ibm_vpc = db_session.query(IBMVpcNetwork).filter_by(id=vpc_id).first()
    if not ibm_vpc:
        LOGGER.info(f"No IBMVpcNetwork found for ID: '{vpc_id}' in db")
        return

    if not ibm_vpc.instances.count():
        LOGGER.info(f"IBMVpcNetwork ID: {vpc_id} don't has instances")

    backup_task: WorkflowTask = db_session.query(WorkflowTask).filter_by(id=backup_task_id).first()
    if not backup_task:
        LOGGER.info(f"No WorkflowTask found for ID: {backup_task_id} in db")
        return

    backup_root = backup_task.root

    metadata = {"vpc_id": vpc_id, "backup_root": backup_root.id, "backup_task_id": backup_task_id}

    instances_to_be_updated_dict = {}
    create_snapshots_roots = []
    for instance in ibm_vpc.instances.all():
        LOGGER.info(f"IBMInstance: {instance.name} backup task is creating")
        data = {
            "instance": {"id": instance.id},
            "resource_group": {"id": instance.resource_group.id},
            "region": {"id": instance.region.id},
            "ibm_cloud": {"id": instance.cloud_id}
        }
        snapshot_root, volume_snapshot_task_id_mapping_dict = create_instance_backup_and_delete(
            user, data, instance.id, db_session=db_session, delete_instance=delete_instance,
            root_type=WorkflowRoot.ROOT_TYPE_ON_SUCCESS,
        )
        instances_to_be_updated_dict[instance.id] = volume_snapshot_task_id_mapping_dict
        backup_root.add_callback_root(snapshot_root)
        create_snapshots_roots.append(snapshot_root)

    update_backup_metadata_root = WorkflowRoot(
        user_id=user["id"], project_id=user["project_id"], workflow_name="IBMInstance Restore",
        workflow_nature="UPDATE", root_type=WorkflowRoot.ROOT_TYPE_ON_SUCCESS,
        fe_request_data=metadata
    )
    update_backup_metadata_task = WorkflowTask(
        task_type=WorkflowTask.TYPE_UPDATE_METADATA, resource_type=IBMInstance.__name__, resource_id=vpc_id,
    )
    metadata["instances"] = instances_to_be_updated_dict
    update_backup_metadata_task.task_metadata = metadata

    update_backup_metadata_root.add_next_task(update_backup_metadata_task)
    update_backup_metadata_root.root_type = WorkflowRoot.ROOT_TYPE_ON_SUCCESS
    for w_r in create_snapshots_roots:
        w_r.add_callback_root(update_backup_metadata_root)

    db_session.add(update_backup_metadata_root)
    db_session.commit()
