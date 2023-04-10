import logging
from functools import wraps
from ibm.common.utils import get_name_from_url
from flask import request, Response, json
from ibm import get_db_session
from ibm.web import db as ibmdb
from ibm.auth import auth
from ibm.web.common.consts import ACTIVITY_TYPE_MAPPER, ACTION_TYPE_MAPPER, AGGREGATED_RESOURCE_LIST, \
    AGGREGATED_TYPE_RESOURCE_OBJECT_MAPPER, RESOURCE_TYPE_OBJECT_MAPPER, DRAAS_RESOURCE_TYPE_OBJECT_MAPPER
from ibm.models import IBMCloud, DisasterRecoveryBackup, IBMKubernetesCluster
from ibm.models.activity_tracking import IBMActivityTracking
from ibm.common.consts import INVALID_REQUEST_METHOD

LOGGER = logging.getLogger(__name__)


def log_activity(func):
    """Log Creation, Deletion Activity Request"""

    @wraps(func)
    def before_request(*args, **kwargs):
        """
        :args: list of arguments
        :kwargs: Dict of arguments
        """
        request_method = request.method
        if request_method in ["POST", "DELETE"]:
            user_email = kwargs['user']['email']
            project_id = kwargs['user']['project_id']
            activity_type = ACTIVITY_TYPE_MAPPER[request_method]
            cloud_id = None
            resource_name = None
            resource_class = None
            summary = None

            api_base_url = request.base_url
            resource_type = get_name_from_url(api_base_url)

            # If resource type not added for logging then return.
            if resource_type not in IBMActivityTracking.ALL_RESOURCES and resource_type not \
                    in AGGREGATED_RESOURCE_LIST:
                message = f"Resource type {resource_type} not added"
                LOGGER.error(message)
                return func(*args, **kwargs)

            if resource_type not in AGGREGATED_RESOURCE_LIST:
                displayed_resource_type = RESOURCE_TYPE_OBJECT_MAPPER[resource_type][1]

            # If Resource is an aggregated resource type
            url_length = len(api_base_url.split("/"))
            if resource_type in AGGREGATED_RESOURCE_LIST and url_length == 7 or url_length == 8:
                aggregated_resource = api_base_url.split("/")[6]
                displayed_resource_type = AGGREGATED_TYPE_RESOURCE_OBJECT_MAPPER[resource_type][aggregated_resource][1]
                resource_class = AGGREGATED_TYPE_RESOURCE_OBJECT_MAPPER[resource_type][aggregated_resource][0]

            if request_method == "POST":
                json_body = request.json
                resource_name = json_body["resource_json"]["name"]
                cloud_id = json_body["ibm_cloud"]["id"]
                summary = "Created {displayed_resource_type} " \
                          "with name {resource_name} for cloud account {cloud_name}"

            if request_method == "DELETE":
                resource_id = api_base_url.split("/")[-1]
                if not resource_class:
                    resource_class = RESOURCE_TYPE_OBJECT_MAPPER[resource_type][0]
                resource = ibmdb.session.query(resource_class).filter_by(id=resource_id).first()
                if not resource:
                    return func(*args, **kwargs)
                resource_name = resource.name
                summary = "Deleted {displayed_resource_type} " \
                          "with name {resource_name} for cloud account {cloud_name}"

                cloud_id = resource.cloud_id
                if not resource_name:
                    return Response("Resource name not found in Schema", status=404)

            cloud = ibmdb.session.query(IBMCloud).filter_by(id=cloud_id, deleted=False).first()
            cloud_name = cloud.name
            summary = summary.format(
                displayed_resource_type=displayed_resource_type, resource_name=resource_name, cloud_name=cloud_name)

            with get_db_session() as db_session:

                view_response = func(*args, **kwargs)
                if view_response[1] != 202:
                    message = f"Invalid Status code received {view_response[1]}"
                    LOGGER.error(message)
                    return view_response

                detailed_summary = json.loads(view_response[0].data.decode('utf-8'))
                activity_tracking = IBMActivityTracking(
                    user=user_email,
                    project_id=project_id,
                    resource_name=resource_name,
                    resource_type=displayed_resource_type,
                    activity_type=activity_type,
                    summary=summary,
                    root_id=detailed_summary['id']
                )
                activity_tracking.cloud_id = cloud_id
                activity_tracking.detailed_summary = detailed_summary
                db_session.add(activity_tracking)
                db_session.commit()
                return view_response
        else:
            return Response(json.dumps(INVALID_REQUEST_METHOD), status=403, mimetype="application/json")

    return before_request


def log_cost_activity(func):
    """Log Cost Activity Request"""

    @wraps(func)
    def before_request(*args, **kwargs):
        """
        :args: list of arguments
        :kwargs: Dict of arguments
        """
        request_method = request.method
        if request_method in ["PATCH"]:
            user = auth.current_user
            json_body = request.json
            if not json_body:
                return func(*args, **kwargs)

            user_email = user['email']
            project_id = user['project_id']
            api_base_url = request.base_url
            resource_type = get_name_from_url(api_base_url)
            resource_type = RESOURCE_TYPE_OBJECT_MAPPER[resource_type][1]
            resource_id = api_base_url.split("/")[-1]
            existing_cloud = ibmdb.session.query(IBMCloud).filter_by(id=resource_id, deleted=False).first()
            activity_type = None
            if not existing_cloud:
                return func(*args, **kwargs)

            resource_name = existing_cloud.name
            existing_cost_setting = existing_cloud.settings.cost_optimization_enabled
            cost_setting = json_body.get("settings", {}).get("cost_optimization_enabled")
            if cost_setting is not None and cost_setting != existing_cost_setting:
                if cost_setting is True:
                    activity_type = "enabled cost"
                elif cost_setting is False:
                    activity_type = "disabled cost"

            elif activity_type is None:
                return func(*args, **kwargs)

            summary = f"{activity_type.capitalize()} for cloud account {resource_name}"
            with get_db_session() as db_session:

                view_response = func(*args, **kwargs)
                if view_response[1] != 202:
                    message = f"Invalid Status code received {view_response[1]}"
                    LOGGER.error(message)
                    return view_response

                detailed_summary = json.loads(view_response[0].data.decode('utf-8'))

                activity_tracking = IBMActivityTracking(
                    user=user_email,
                    project_id=project_id,
                    resource_name=resource_name,
                    resource_type=resource_type,
                    activity_type=activity_type,
                    summary=summary,
                    root_id=detailed_summary['id']
                )
                activity_tracking.cloud_id = resource_id
                activity_tracking.detailed_summary = detailed_summary
                db_session.add(activity_tracking)
                db_session.commit()
                return view_response
        else:
            return Response(json.dumps(INVALID_REQUEST_METHOD), status=403, mimetype="application/json")

    return before_request


def log_draas_activity(func):
    """Log Draas Activity Request"""

    @wraps(func)
    def before_request(*args, **kwargs):
        """
        :args: list of arguments
        :kwargs: Dict of arguments
        """
        request_method = request.method
        api_base_url = request.base_url
        user_email = kwargs['user']['email']
        project_id = kwargs['user']['project_id']
        resource_type = get_name_from_url(api_base_url)
        if request_method not in ["POST", "DELETE"] and resource_type != "draas_backups":
            message = f"Invalid method for resource {resource_type}"
            LOGGER.error(message)
            return func(*args, **kwargs)

        if request_method == "POST":
            json_body = request.json
            draas_resource_type = json_body["resource_type"]
            draas_resource_type_schema_key = DRAAS_RESOURCE_TYPE_OBJECT_MAPPER[draas_resource_type][1]
            displayed_resource_type = DRAAS_RESOURCE_TYPE_OBJECT_MAPPER[draas_resource_type][2]
            draas_resource_meta = json_body[draas_resource_type_schema_key]
            cloud_id = draas_resource_meta["ibm_cloud"]["id"]
            resource_id = draas_resource_meta["resource_id"]
            backup_name = draas_resource_meta["name"]
            resource_class = DRAAS_RESOURCE_TYPE_OBJECT_MAPPER[draas_resource_type][0]
            resource = ibmdb.session.query(resource_class).filter_by(id=resource_id, cloud_id=cloud_id).first()
            if not resource:
                message = f"Resource Type with ID {resource_id} doesn't exist"
                LOGGER.error(message)
                return func(*args, **kwargs)
            resource_name = resource.name
            summary = f"Created backup for {resource_name}({displayed_resource_type}) with " \
                      f"backup name {backup_name}"

        if request_method == "DELETE":
            backup_id = api_base_url.split("/")[-1]
            backup = ibmdb.session.query(DisasterRecoveryBackup).filter_by(id=backup_id).first()
            backup_name = backup.name
            blueprint = backup.disaster_recovery_resource_blueprint
            cloud_id = blueprint.cloud_id
            resource_id = blueprint.resource_id
            resource_type = blueprint.resource_type
            resource_class = DRAAS_RESOURCE_TYPE_OBJECT_MAPPER[resource_type][0]
            resource = ibmdb.session.query(resource_class).filter_by(id=resource_id).first()
            if not resource:
                message = f"Resource Type with ID {resource_id} doesn't exist"
                LOGGER.error(message)
                return func(*args, **kwargs)
            resource_name = resource.name
            displayed_resource_type = DRAAS_RESOURCE_TYPE_OBJECT_MAPPER[resource_type][2]
            summary = f"Deleted backup for {resource_name}({displayed_resource_type}) with " \
                      f"backup name {backup_name}"

        with get_db_session() as db_session:
            view_response = func(*args, **kwargs)
            if view_response[1] != 202:
                message = f"Invalid Status code received {view_response[1]}"
                LOGGER.error(message)
                return view_response

            detailed_summary = json.loads(view_response[0].data.decode('utf-8'))

            activity_tracking = IBMActivityTracking(
                user=user_email,
                project_id=project_id,
                resource_name=resource_name,
                resource_type=displayed_resource_type,
                activity_type=IBMActivityTracking.BACKUP,
                summary=summary,
                root_id=detailed_summary['id']
            )
            activity_tracking.cloud_id = cloud_id
            activity_tracking.detailed_summary = detailed_summary
            db_session.add(activity_tracking)
            db_session.commit()
            return view_response

    return before_request


def log_restore_activity(func):
    """Log Draas Activity Request"""

    @wraps(func)
    def before_request(*args, **kwargs):
        """
        :args: list of arguments
        :kwargs: Dict of arguments
        """
        request_method = request.method
        api_base_url = request.base_url
        activity_type = api_base_url.split('/')[-1]

        if request_method != "POST" and activity_type != "restore":
            message = f"Activity type {activity_type} not implemented"
            LOGGER.error(message)
            return func(*args, **kwargs)

        backup_id = api_base_url.split('/')[6]
        user_email = kwargs['user']['email']
        project_id = kwargs['user']['project_id']
        json_body = request.json
        resource_type = json_body['resource_type']
        if resource_type == "IKS":
            restore_schema = json_body['iks_restore_schema']
            if restore_schema['restore_type'] == "TYPE_EXISTING_IKS":
                schema = restore_schema['restore_type_existing_iks']
                cloud_id = schema['ibm_cloud']['id']
                target_cluster_id = schema['ibm_cluster_target']['id']

                target_cluster = ibmdb.session.query(IBMKubernetesCluster).filter_by(
                    id=target_cluster_id, cloud_id=cloud_id).first()
                if not target_cluster:
                    message = f"Target Cluster with ID {target_cluster_id} doesn't exist"
                    LOGGER.error(message)
                    return func(*args, **kwargs)

                displayed_resource_type = DRAAS_RESOURCE_TYPE_OBJECT_MAPPER[resource_type][2]
                resource_name = target_cluster.name

                backup = ibmdb.session.query(DisasterRecoveryBackup).filter_by(id=backup_id).first()
                if not backup:
                    message = f"backup with ID {backup_id} doesn't exist"
                    LOGGER.error(message)
                    return func(*args, **kwargs)
                backup_name = backup.name.split("_")[0]
                summary = f"Restored {backup_name}({displayed_resource_type}) " \
                          f"into cluster {resource_name}"

        elif resource_type == "IBMVpcNetwork":
            restore_schema = json_body['vpc_restore_schema']
            cloud_id = restore_schema["ibm_cloud"]["id"]
            restore_region = restore_schema["region"]['name']

            backup = ibmdb.session.query(DisasterRecoveryBackup).filter_by(id=backup_id).first()
            if not backup:
                message = f"backup with ID {backup_id} doesn't exist"
                LOGGER.error(message)
                return func(*args, **kwargs)
            backup_name = backup.name.split("_")[0]
            resource_name = backup_name
            displayed_resource_type = DRAAS_RESOURCE_TYPE_OBJECT_MAPPER[resource_type][2]
            summary = f"Restored {backup_name}({displayed_resource_type}) " \
                      f"into region {restore_region}"

        with get_db_session() as db_session:
            view_response = func(*args, **kwargs)

            detailed_summary = view_response
            if detailed_summary.get("created_at"):
                detailed_summary.pop("created_at")
            activity_tracking = IBMActivityTracking(
                user=user_email,
                project_id=project_id,
                resource_name=resource_name,
                resource_type=displayed_resource_type,
                activity_type=IBMActivityTracking.RESTORE,
                summary=summary,
                root_id=detailed_summary['id']
            )
            activity_tracking.cloud_id = cloud_id
            activity_tracking.detailed_summary = detailed_summary
            db_session.add(activity_tracking)
            db_session.commit()
            return view_response

    return before_request


def log_instance_activity(func):
    """Log Draas Activity Request"""

    @wraps(func)
    def before_request(*args, **kwargs):
        """
        :args: list of arguments
        :kwargs: Dict of arguments
        """
        request_method = request.method
        user_email = kwargs['user']['email']
        project_id = kwargs['user']['project_id']
        api_base_url = request.base_url
        resource_type = api_base_url.split('/')[-1]
        json_body = request.json
        if not json_body:
            return func(*args, **kwargs)

        if request_method != "PATCH" and resource_type != IBMActivityTracking.INSTANCES_KEY:
            message = f"Resource type {resource_type} not implemented"
            LOGGER.error(message)
            return func(*args, **kwargs)

        resource_id = json_body["instance_ids"][0]
        resource = ibmdb.session.query(RESOURCE_TYPE_OBJECT_MAPPER[resource_type][0]).filter_by(id=resource_id).first()
        resource_name = resource.name
        vpc = resource.vpc_network
        vpc_name = vpc.name
        displayed_resource_type = RESOURCE_TYPE_OBJECT_MAPPER[resource_type][1]
        activity_type = json_body['action']
        instances_no = len(json_body["instance_ids"])
        displayed_action_type = ACTION_TYPE_MAPPER[activity_type]
        cloud_id = json_body["ibm_cloud"]["id"]
        cloud_name = json_body["ibm_cloud"]["name"]
        if instances_no > 1:
            summary = f" {displayed_action_type} {displayed_resource_type}s in vpc({vpc_name}) for cloud {cloud_name}"
        else:
            summary = f"{displayed_action_type} {displayed_resource_type}({resource_name}) " \
                      f"in vpc({vpc_name})for cloud {cloud_name}"
        with get_db_session() as db_session:
            view_response = func(*args, **kwargs)

            detailed_summary = view_response
            activity_tracking = IBMActivityTracking(
                user=user_email,
                project_id=project_id,
                resource_name=resource_name,
                resource_type=displayed_resource_type,
                activity_type=activity_type,
                summary=summary,
                root_id=detailed_summary['id']
            )
            activity_tracking.cloud_id = cloud_id
            activity_tracking.detailed_summary = detailed_summary
            db_session.add(activity_tracking)
            db_session.commit()
        return view_response

    return before_request
