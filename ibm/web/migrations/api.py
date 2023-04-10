import json
import logging

from apiflask import abort, APIBlueprint, input, output

from ibm.auth import authenticate
from ibm.common.req_resp_schemas.schemas import WorkflowRootOutSchema
from ibm.models import SoftlayerCloud
from ibm.web import db as ibmdb
from ibm.web.common.utils import compose_ibm_sync_resource_workflow
from ibm.web.migrations.schemas import IBMMigrationFileInSchema, IBMMigrationInSchema

LOGGER = logging.getLogger(__name__)
ibm_migrations = APIBlueprint('ibm_migrations', __name__, tag="IBM Migrate VPC")


@ibm_migrations.route('/migrate/vpcs', methods=['POST'])
@input(IBMMigrationInSchema, location="form")
@input(IBMMigrationFileInSchema, location="files")
@output(WorkflowRootOutSchema, status_code=202)
@authenticate
def migrate_vpc(data, file, user):
    """
    Migrate VYATTA-5600 config file to VPC schema
    :param data: Payload for migration. Includes softlayer cloud id and config file. data format:
     {"softlayer_cloud": {"id": "450fe65cd3af4dc18e1a29dc703ae71c"}} <-- required,
     {"ibm_cloud": {"id": "450fe65cd3af4dc18e1a29dc703ae71c"}, "config_file": .txt format vyatta file } <-- optional
    :param file: Payload for migration. Includes softlayer config file
    :param user: object of the user initiating the request
    :return: Response object from flask package
    """
    softlayer_cloud = json.loads(data["softlayer_cloud"])
    config_file = file.get('config_file')

    if not ibmdb.session.query(SoftlayerCloud).filter_by(id=softlayer_cloud.get("id")).first():
        abort(400, "SOFTLAYER_CLOUD_NOT_FOUND")

    configs = None
    if config_file:
        if not config_file.filename.lower().endswith('.txt'):
            abort(422, "FILE_FORMAT_NOT_SUPPORTED")

        configs = config_file.read()
        if not configs:
            abort(422, "EMPTY_FILE_DETECTED")

        configs = configs.decode('utf-8')

    p_data = {"config_file": configs, "user": user}
    data["softlayer_cloud"] = softlayer_cloud

    workflow_root = compose_ibm_sync_resource_workflow(user=user, resource_type=SoftlayerCloud, data=data,
                                                       p_data=p_data)

    return workflow_root.to_json()
