import uuid

from ibm.models import IBMFloatingIP, IBMImage, IBMInstance, IBMOperatingSystem, IBMSecurityGroup, WorkflowRoot, \
    WorkflowTask
from ibm.web import db as ibmdb
from ibm.web.ibm.instances.consts import InstanceMigrationConsts


def create_ibm_instance_creation_workflow(user, data, db_session=None, sketch=False):
    if not db_session:
        db_session = ibmdb.session

    workflow_name = IBMInstance.__name__
    if data["resource_json"].get("name"):
        workflow_name = ' '.join([workflow_name, data["resource_json"]["name"]])

    workflow_root = WorkflowRoot(
        user_id=user["id"], project_id=user["project_id"], workflow_name=workflow_name, workflow_nature="CREATE",
        fe_request_data=data
    )
    security_group_creation_task = None
    if data.get("migration_json"):
        if data["migration_json"].get("create_vpc_allow_all_security_group"):
            sg_name = "vpc-plus-allow-all"
            sg_dict = {
                "vpc_id": data["resource_json"]["vpc"]["id"],
                "name": sg_name
            }
            sg_obj = db_session.query(IBMSecurityGroup).filter_by(**sg_dict).first()
            if sg_obj:
                s_gp_id = sg_obj.id
            else:
                s_gp_id = str(uuid.uuid4().hex)
                vpc_allow_all_security_group_resource_data = {
                    "ibm_cloud": data["ibm_cloud"],
                    "region": data["region"],
                    "id": s_gp_id,
                    "resource_json": {
                        "name": sg_name,
                        "region": data["region"],
                        "resource_group": data["resource_json"]["resource_group"],
                        "rules": [
                            {
                                "direction": "inbound",
                                "protocol": "all",
                                "ip_version": "ipv4"
                            },
                            {
                                "direction": "outbound",
                                "protocol": "all",
                                "ip_version": "ipv4"
                            }
                        ],
                        "vpc": data["resource_json"]["vpc"]
                    }
                }
                security_group_creation_task = WorkflowTask(
                    task_type=WorkflowTask.TYPE_CREATE, resource_type=IBMSecurityGroup.__name__,
                    task_metadata={"resource_data": vpc_allow_all_security_group_resource_data}
                )
            data["resource_json"]["primary_network_interface"]["security_groups"].append({"id": s_gp_id})

    instance_creation_task = WorkflowTask(
        task_type=WorkflowTask.TYPE_CREATE, resource_type=IBMInstance.__name__, task_metadata={"resource_data": data}
    )
    instance_backup_task = WorkflowTask(
        task_type=WorkflowTask.TYPE_BACKUP, resource_type=IBMInstance.__name__, task_metadata={"resource_data": data}
    )
    snapshot_task = WorkflowTask(
        task_type=WorkflowTask.TYPE_SNAPSHOT, resource_type=IBMInstance.__name__, task_metadata={"resource_data": data}
    )
    snapshot_task2 = WorkflowTask(
        task_type=WorkflowTask.TYPE_SNAPSHOT, resource_type=IBMInstance.__name__,
        task_metadata={"resource_data": data}
    )
    export_task = WorkflowTask(
        task_type=WorkflowTask.TYPE_EXPORT, resource_type=IBMInstance.__name__, task_metadata={"resource_data": data}
    )
    conversion_task = WorkflowTask(
        task_type=WorkflowTask.TYPE_CONVERT, resource_type=IBMImage.__name__, task_metadata={"resource_data": data}
    )
    image_creation_task = WorkflowTask(
        task_type=WorkflowTask.TYPE_CREATE, resource_type=IBMImage.__name__, task_metadata={"resource_data": data}
    )
    if data.get("migration_json"):
        migration_json = data["migration_json"]
        migrate_from = migration_json.get("migrate_from")
        if migrate_from == InstanceMigrationConsts.CLASSIC_VSI:
            os_dict = migration_json["operating_system"]
            os = db_session.query(IBMOperatingSystem).filter_by(**os_dict).first()
            if os and os.family == "Windows Server":
                workflow_root.add_next_task(snapshot_task2)
                snapshot_task2.add_next_task(instance_backup_task)
                instance_backup_task.add_next_task(snapshot_task)
            else:
                workflow_root.add_next_task(snapshot_task)
            snapshot_task.add_next_task(export_task)
            export_task.add_next_task(image_creation_task)
            image_creation_task.add_next_task(instance_creation_task)
        elif migrate_from == InstanceMigrationConsts.CLASSIC_IMAGE:
            workflow_root.add_next_task(export_task)
            export_task.add_next_task(image_creation_task)
            image_creation_task.add_next_task(instance_creation_task)
        elif migrate_from == InstanceMigrationConsts.COS_BUCKET_VMDK:
            workflow_root.add_next_task(conversion_task)
            conversion_task.add_next_task(image_creation_task)
            image_creation_task.add_next_task(instance_creation_task)
        elif migrate_from in [InstanceMigrationConsts.COS_BUCKET_QCOW2, InstanceMigrationConsts.COS_BUCKET_VHD]:
            workflow_root.add_next_task(image_creation_task)
            image_creation_task.add_next_task(instance_creation_task)
        elif data["migration_json"].get(
                "is_volume_migration") and migrate_from == InstanceMigrationConsts.ONLY_VOLUME_MIGRATION:
            workflow_root.add_next_task(snapshot_task)
            snapshot_task.add_next_task(export_task)
            export_task.add_next_task(instance_creation_task)
        else:
            workflow_root.add_next_task(instance_creation_task)
        if security_group_creation_task:
            workflow_root.add_next_task(security_group_creation_task)
            security_group_creation_task.add_next_task(instance_creation_task)
    else:
        workflow_root.add_next_task(instance_creation_task)

    # TODO floating IP support for secondary network interfaces check
    if data["resource_json"]["primary_network_interface"].get("floating_ip"):
        floating_ip_creation_task = WorkflowTask(
            task_type=WorkflowTask.TYPE_CREATE, resource_type=IBMFloatingIP.__name__,
            task_metadata={"resource_data": data}
        )
        instance_creation_task.add_next_task(floating_ip_creation_task)
    if not sketch:
        db_session.add(workflow_root)

    db_session.commit()
    return workflow_root


def update_root_data_and_task_metadata(workflow_root, data, db_session=None):
    """
    This func will update root data and all tasks task_metadata with new data
    """
    if not db_session:
        db_session = ibmdb.session

    workflow_root.fe_request_data = data
    for task in workflow_root.associated_tasks.all():
        task.task_metadata = {"resource_data": data}
