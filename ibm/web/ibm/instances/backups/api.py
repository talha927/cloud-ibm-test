import logging

from apiflask import abort, APIBlueprint, input, output

from ibm.auth import authenticate
from ibm.common.req_resp_schemas.schemas import WorkflowRootOutSchema
from ibm.models import IBMInstance
from ibm.web import db as ibmdb
from .schemas import IBMInstanceBackupInSchema
from .utils import create_instance_backup_and_delete

LOGGER = logging.getLogger(__name__)

ibm_instance_backup = APIBlueprint('ibm_instance_backup', __name__, tag="IBM Instance Backup")


@ibm_instance_backup.post('/instances/backup')
@authenticate
@input(IBMInstanceBackupInSchema)
@output(WorkflowRootOutSchema, status_code=202)
def create_ibm_instance_backup(data, user):
    """
    Create INSTANCE and Associated Block Storage Volumes' Snapshots.
    return:
    """
    ibm_instance = ibmdb.session.query(IBMInstance).filter_by(**data["instance"]).first()
    if not ibm_instance:
        abort(404, f"No Instance found for ID: {data['instance']}")
    workflow_root, volume_snapshot_task_id_mapping_dict = create_instance_backup_and_delete(
        user=user, data=data, instance_id=ibm_instance.id, delete_instance=False
    )
    return workflow_root.to_json()
