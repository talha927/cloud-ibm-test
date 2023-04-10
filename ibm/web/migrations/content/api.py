import logging

from apiflask import abort, APIBlueprint, input, output

from ibm.auth import authenticate
from ibm.models.migrations import CMModels
from ibm.web import db as ibmdb
from ibm.web.migrations.content.schemas import NASMigrationMetaDataInSchema, NASMigrationMetaDataOutSchema, \
    NASMigrationStartInSchema

LOGGER = logging.getLogger(__name__)

nas_migrations = APIBlueprint('nas_migrations', __name__, tag="NAS Migration(Internal API)")


@nas_migrations.post('/content')
@input(NASMigrationMetaDataInSchema)
def migrate_content(data):
    """task_add_content_migration_meta_data
    Save Block Volume and File Storage in ibmdb in CMModel for the sake of NAS migration
    """
    vsi_id = data.get("instance_id")
    if not vsi_id:
        vsi_id = data["migrator_name"].split("-")[-1]
    cm_object = ibmdb.session.query(CMModels).filter_by(softlayer_vsi_id=vsi_id).first()
    if cm_object:
        cm_object.cm_meta_data = data
    else:
        cm_object = CMModels(softlayer_vsi_id=vsi_id, cm_meta_data=data)
        ibmdb.session.add(cm_object)
    ibmdb.session.commit()
    LOGGER.info(f"VSI: {vsi_id} meta data saved for user: user['id']")
    return '', 200


@nas_migrations.get('/content/<softlayer_vsi_id>')
@output(NASMigrationMetaDataOutSchema)
@authenticate
def get_content_meta_data(softlayer_vsi_id, user):
    """
    Get File Storage and Block Volume Data against VSI Classic ID
    """
    content_data = ibmdb.session.query(CMModels).filter_by(softlayer_vsi_id=softlayer_vsi_id).first()
    if not content_data:
        message = f"Softlayer Instance {softlayer_vsi_id} does not have NAS Migration registered, " \
                  f"First run the script on this VSI"
        LOGGER.debug(message)
        abort(404, message)
    return content_data.to_json()


@nas_migrations.patch('/content/start/<user_id>')
@input(NASMigrationStartInSchema)
def start_content_migration(user_id, data):
    """
    Start NAS Migration with the following three apis (Internal API)
    1): Get IDs of the locations by searching with names
    2): Create a Migration Object
    3): Start Moving the contents for this specific migration object
    """
    from ibm.tasks.ibm.ibm_instance_tasks import task_start_nas_migration
    task_start_nas_migration.si(data=data, user_id=user_id).delay()
    return "", 202
