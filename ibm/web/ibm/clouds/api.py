import json
from datetime import datetime

from apiflask import abort, APIBlueprint, auth_required, input, output
from flask import Response

from ibm import LOGGER
from ibm.auth import auth, authenticate, authenticate_api_key
from ibm.middleware import log_cost_activity
from ibm.common.req_resp_schemas.schemas import get_pagination_schema, PaginationQuerySchema, WorkflowRootOutSchema
from ibm.models import IBMCloud, IBMCloudObjectStorage, IBMCloudSetting, IBMCOSBucket, IBMCost, IBMDashboardSetting, \
    IBMIdleResource, IBMLoadBalancerProfile, IBMMonitoringToken, IBMRegion, IBMResourceGroup, \
    IBMRightSizingRecommendation, IBMServiceCredentialKey, IBMTag, IBMVpcNetwork, WorkflowRoot, WorkflowTask
from ibm.web import db as ibmdb
from ibm.web.common.utils import get_paginated_response_json
from .mappers import IBM_DASHBOARD_RESOURCE_TYPE_MAPPER
from .schemas import CredentialOutSchema, DashboardOutListSchema, DashboardUpdateListSchema, IBMCloudInSchema, \
    IBMCloudListQuerySchema, IBMCloudOutSchema, IBMCloudUpdateSchema, IBMDashboardListQuerySchema, \
    IBMMonitoringTokenInSchema

ibm_clouds = APIBlueprint('ibm_clouds', __name__, tag="IBM Clouds")


@ibm_clouds.route('/clouds', methods=['POST'])
@authenticate
@input(IBMCloudInSchema)
@output(WorkflowRootOutSchema, status_code=202)
def create_ibm_cloud(data, user):
    """
    Create IBM Cloud
    This request registers an IBM Cloud with VPC+.
    """

    existing_clouds = ibmdb.session.query(IBMCloud).filter_by(
        user_id=user["id"], project_id=user["project_id"], deleted=False
    ).all()
    for existing_cloud in existing_clouds:
        if existing_cloud.name == data["name"]:
            abort(409, f"IBM Cloud with the name {data['name']} already exists")

        if existing_cloud.api_key == data["api_key"]:
            abort(409, f"IBM Cloud {existing_cloud.id} already exists with the same API Key")

    cloud = IBMCloud(name=data["name"], api_key=data["api_key"], user_id=user["id"], project_id=user["project_id"])
    cloud.settings = IBMCloudSetting()
    if data.get('settings') and data["settings"].get('cost_optimization_enabled'):
        cloud.settings.cost_optimization_enabled = data['settings']['cost_optimization_enabled']

    cloud.metadata_ = user
    ibmdb.session.add(cloud)
    ibmdb.session.commit()

    cloud_workflow_root = WorkflowRoot(
        user_id=user["id"],
        project_id=user["project_id"],
        workflow_name=f"{IBMCloud.__name__} ({data['name']})",
        workflow_nature="ADD"
    )
    validate_cloud_task = WorkflowTask(
        task_type=WorkflowTask.TYPE_VALIDATE, resource_type=IBMCloud.__name__, task_metadata={"cloud_id": cloud.id}
    )
    update_geography_task = WorkflowTask(
        task_type="UPDATE", resource_type="GEOGRAPHY", task_metadata={"cloud_id": cloud.id}
    )
    update_account_id_task = WorkflowTask(
        task_type="SYNC", resource_type=IBMCloud.__name__, task_metadata={"cloud_id": cloud.id}
    )
    update_resource_groups_task = WorkflowTask(
        task_type="UPDATE", resource_type=IBMResourceGroup.__name__, task_metadata={"cloud_id": cloud.id}
    )
    sync_load_balancer_profiles_task = WorkflowTask(
        task_type=WorkflowTask.TYPE_SYNC,
        resource_type=IBMLoadBalancerProfile.__name__, task_metadata={"resource_data": {"cloud_id": cloud.id}}
    )

    cloud_workflow_root.add_next_task(validate_cloud_task)
    validate_cloud_task.add_next_task(update_geography_task)
    validate_cloud_task.add_next_task(update_account_id_task)
    validate_cloud_task.add_next_task(update_resource_groups_task)
    update_geography_task.add_next_task(sync_load_balancer_profiles_task)

    # Callback root for sync tasks
    sync_workflow_root = WorkflowRoot(
        user_id=user["id"], project_id=user["project_id"], root_type=WorkflowRoot.ROOT_TYPE_ON_SUCCESS,
        workflow_name=f"{IBMCloudObjectStorage.__name__} ({cloud.id})", workflow_nature="SYNC"
    )
    sync_cloud_object_storage_task = WorkflowTask(
        task_type=WorkflowTask.TYPE_SYNC, resource_type=IBMCloudObjectStorage.__name__,
        task_metadata={"resource_data": {"cloud_id": cloud.id}}
    )
    initiate_bucket_sync_tasks = WorkflowTask(
        task_type="SYNC-INITIATE", resource_type=IBMCOSBucket.__name__, task_metadata={"cloud_id": cloud.id}
    )
    credential_keys_tasks = WorkflowTask(
        task_type="SYNC", resource_type=IBMServiceCredentialKey.__name__, task_metadata={"resource_data": {
            "cloud_id": cloud.id}}
    )

    sync_workflow_root.add_next_task(sync_cloud_object_storage_task)
    sync_cloud_object_storage_task.add_next_task(initiate_bucket_sync_tasks)
    sync_cloud_object_storage_task.add_next_task(credential_keys_tasks)

    cloud_workflow_root.add_callback_root(sync_workflow_root)

    ibmdb.session.add(cloud_workflow_root)
    ibmdb.session.commit()

    return cloud_workflow_root.to_json(metadata=True)


@ibm_clouds.route('/clouds', methods=['GET'])
@authenticate
@input(IBMCloudListQuerySchema, location='query')
@input(PaginationQuerySchema, location='query')
@output(get_pagination_schema(IBMCloudOutSchema))
def list_ibm_clouds(listing_query_schema, query_params, user):
    """
    List IBM Clouds
    This request lists all IBM Cloud accounts for the project of the authenticated user calling the API.
    """

    status = listing_query_schema.get("status")
    clouds_list_query = ibmdb.session.query(IBMCloud).filter_by(
        user_id=user["id"], project_id=user["project_id"], deleted=False
    )
    if status:
        clouds_list_query = clouds_list_query.filter_by(status=status)

    cloud_page = clouds_list_query.paginate(page=query_params["page"], per_page=query_params["per_page"],
                                            error_out=False)
    if not cloud_page.items:
        return Response(status=204)

    return get_paginated_response_json(
        items=[item.to_json() for item in cloud_page.items],
        pagination_obj=cloud_page
    )


@ibm_clouds.route('/clouds/<cloud_id>', methods=['GET'])
@authenticate
@output(IBMCloudOutSchema)
def get_ibm_cloud(cloud_id, user):
    """
    Get IBM Cloud
    This request returns an IBM Cloud provided its ID.
    """

    cloud = ibmdb.session.query(IBMCloud).filter_by(
        id=cloud_id, user_id=user["id"], project_id=user["project_id"], deleted=False
    ).first()
    if not cloud or cloud.status == IBMCloud.STATUS_ERROR_DELETING:
        abort(404, f"No IBM Cloud with ID {cloud_id} found for the user")

    return cloud.to_json()


@ibm_clouds.route('/clouds/<cloud_id>', methods=['PATCH'])
@auth_required(auth=auth)
@log_cost_activity
@input(IBMCloudUpdateSchema)
@output(WorkflowRootOutSchema, status_code=202)
def update_ibm_cloud(cloud_id, data):
    """
    Update IBM Cloud
    This request updates an IBM Cloud
    """
    user = auth.current_user

    existing_cloud: IBMCloud = ibmdb.session.query(IBMCloud).filter_by(id=cloud_id).first()
    if not existing_cloud:
        message = f"IBM Cloud with the name {data['name']} does not exists."
        abort(404, message)

    existing_cloud.settings = IBMCloudSetting()

    workflow_root = WorkflowRoot(
        user_id=user["id"],
        project_id=user["project_id"],
        workflow_name=f"{IBMCloud.__name__} ({data.get('name') or existing_cloud.name})",
        workflow_nature="ADD"
    )
    consumption_root = WorkflowRoot(
        user_id=user["id"],
        project_id=user["project_id"],
        root_type=WorkflowRoot.ROOT_TYPE_ON_SUCCESS,
        workflow_name=f"{IBMCloud.__name__} ({data.get('name') or existing_cloud.name}) Consumption",
        workflow_nature="ADD"
    )
    consumption_task = WorkflowTask(
        task_type=WorkflowTask.TYPE_CONSUMPTION, resource_type=IBMCost.__name__, task_metadata={
            'cloud_id': existing_cloud.id,
            'email': user.get("email")})
    consumption_root.add_next_task(consumption_task)
    for token in data.get('monitoring_tokens', []):
        kwargs = dict()
        if token["region"].get("id"):
            kwargs["id"] = token["region"]["id"]
        else:
            kwargs["name"] = token["region"]["name"]

        region = ibmdb.session.query(IBMRegion).filter_by(**kwargs, cloud_id=cloud_id).first()
        if not region:
            LOGGER.info(f"No IBM Region found with cloud id {cloud_id}")
            continue

        existing_token = ibmdb.session.query(IBMMonitoringToken).join(IBMRegion).filter_by(
            id=region.id, cloud_id=cloud_id).first()
        if not token.get("token"):
            if existing_token:
                ibmdb.session.delete(existing_token)
                ibmdb.session.commit()
            continue

        new_token = IBMMonitoringToken(token=token["token"])
        if not existing_token:
            new_token.ibm_region = region
        else:
            existing_token.update_token(new_token)

        ibmdb.session.commit()

        workflow_root.add_next_task(WorkflowTask(
            task_type=IBMMonitoringToken.TASK_TYPE_ADD, resource_type=IBMMonitoringToken.__name__,
            task_metadata={"cloud_id": existing_cloud.id, "region_id": region.id, "token": token["token"]}
        ))

    update_ibm_cloud_task = WorkflowTask(
        task_type=WorkflowTask.TYPE_UPDATE, resource_type=IBMCloud.__name__,
        task_metadata={"cloud_id": existing_cloud.id, "data": data, "user": user}
    )
    workflow_root.add_next_task(update_ibm_cloud_task)
    fetch_cost_root = WorkflowRoot(
        user_id=user["id"],
        project_id=user["project_id"],
        root_type=WorkflowRoot.ROOT_TYPE_ON_SUCCESS,
        workflow_name=f"{IBMCloud.__name__} ({data.get('name') or existing_cloud.name}) fetch-cost",
        workflow_nature="ADD"
    )
    fetch_cost_task = WorkflowTask(
        task_type=WorkflowTask.TYPE_FETCH_COST, resource_type=IBMCloud.__name__,
        task_metadata={"cloud_id": existing_cloud.id}
    )
    fetch_cost_root.add_next_task(fetch_cost_task)
    if "api_key" in data and existing_cloud.api_key != data["api_key"]:
        validate_cloud_task = WorkflowTask(
            task_type=WorkflowTask.TYPE_VALIDATE, resource_type=IBMCloud.__name__,
            task_metadata={"cloud_id": existing_cloud.id, "data": data}
        )
        update_ibm_cloud_task.add_next_task(validate_cloud_task)

    if data.get('settings'):
        if data['settings'].get('cost_optimization_enabled') is not None and \
                data['settings']['cost_optimization_enabled'] != existing_cloud.settings.cost_optimization_enabled:
            existing_cloud.settings.cost_optimization_enabled = data['settings']['cost_optimization_enabled']
    workflow_root.add_callback_root(consumption_root)

    if existing_cloud.settings and existing_cloud.settings.cost_optimization_enabled:
        workflow_root.add_callback_root(fetch_cost_root)

    ibmdb.session.add(workflow_root)
    ibmdb.session.commit()

    return workflow_root.to_json(metadata=True)


@ibm_clouds.route('/clouds/<cloud_id>', methods=['DELETE'])
@authenticate
@output(WorkflowRootOutSchema, status_code=202)
def delete_ibm_cloud(cloud_id, user):
    """
    Delete IBM Cloud
    This request deletes an IBM Cloud provided its ID.
    """

    cloud = ibmdb.session.query(IBMCloud).filter_by(
        id=cloud_id, user_id=user["id"], project_id=user["project_id"], deleted=False
    ).first()
    if not cloud:
        abort(404, f"No IBM Cloud with ID {cloud_id} found for the user")

    workflow_root = WorkflowRoot(
        user_id=user["id"],
        project_id=user["project_id"],
        workflow_name=f"{IBMCloud.__name__} ({cloud.name})",
        workflow_nature="DELETE"
    )
    workflow_task = WorkflowTask(
        task_type=WorkflowTask.TYPE_DELETE, resource_type=IBMCloud.__name__, task_metadata={"cloud_id": cloud.id}
    )
    workflow_root.add_next_task(workflow_task)
    cloud.status = IBMCloud.STATUS_DELETING
    cloud.deleted = True
    ibmdb.session.add(workflow_root)
    ibmdb.session.commit()

    return workflow_root.to_json(metadata=True)


@ibm_clouds.route('/clouds/dashboard-settings', methods=['GET'])
@authenticate
@input(IBMDashboardListQuerySchema, location='query')
@output(DashboardOutListSchema)
def list_ibm_cloud_dashboard_settings(listing_query_schema, user):
    """
    List all IBM Cloud Accounts dashboard settings
    The request will list all IBM Cloud Accounts dashboard settings with their counts
    """

    cloud_id = listing_query_schema.get("cloud_id")
    filters = {"id": cloud_id} if cloud_id else {"project_id": user["project_id"]}
    clouds = ibmdb.session.query(IBMCloud).filter_by(**filters).all()
    cloud = None
    if cloud_id:
        cloud = ibmdb.session.query(IBMCloud).filter_by(
            id=cloud_id, user_id=user["id"], project_id=user["project_id"], deleted=False,
            status=IBMCloud.STATUS_VALID
        ).first()
        if not cloud:
            abort(404, f"No IBM Cloud with ID {cloud_id} found for the user or not VALID")

    dashboard_settings = ibmdb.session.query(IBMDashboardSetting).filter_by(user_id=user["id"]).order_by(
        IBMDashboardSetting.order).all()
    if not dashboard_settings:
        for i, resource in enumerate(IBM_DASHBOARD_RESOURCE_TYPE_MAPPER.keys()):
            dashboard_setting = IBMDashboardSetting(
                name=resource, user_id=user["id"], order=i + 1,
                pin_status=IBM_DASHBOARD_RESOURCE_TYPE_MAPPER[resource]["pin_status"])
            ibmdb.session.add(dashboard_setting)
            dashboard_setting.ibm_cloud = cloud or clouds[0]
            ibmdb.session.commit()
            dashboard_settings.append(dashboard_setting)

    dashboard_settings_resp = list()

    for setting in dashboard_settings:
        resource_count = 0
        for cloud in clouds:
            filter_kwargs = {"cloud_id": cloud.id}
            if setting.name == "Custom Images":
                filter_kwargs["visibility"] = "private"

            model = IBM_DASHBOARD_RESOURCE_TYPE_MAPPER[setting.name]['resource_type']
            resource_count += ibmdb.session.query(model).filter_by(**filter_kwargs).count()
        settings_json = setting.to_json()
        settings_json["count"] = resource_count
        dashboard_settings_resp.append(settings_json)
    return {"items": dashboard_settings_resp}


@ibm_clouds.route('/clouds/dashboard-settings', methods=['PATCH'])
@authenticate
@input(DashboardUpdateListSchema)
@output(DashboardOutListSchema)
def update_ibm_cloud_dashboard_setting(data, user):
    """
    Update an IBM Cloud Account Dashboard Setting
    The request will update an IBM Cloud Account Dashboard Setting
    """

    dashboard_settings_list = list()
    for setting in data['items']:
        dashboard_setting = ibmdb.session.query(IBMDashboardSetting).filter(
            IBMDashboardSetting.id == setting['id'], IBMDashboardSetting.user_id == user["id"]).first()
        if not dashboard_setting:
            LOGGER.info(f"No IBM Dashboard Setting with ID {setting['id']}")
            return Response(status=404)

        dashboard_setting.pin_status = setting['pin_status']
        if setting.get("order") is not None:
            dashboard_setting.order = setting['order']

        dashboard_settings_list.append(dashboard_setting.to_json())
        ibmdb.session.commit()

    return Response(json.dumps(dashboard_settings_list), status=200, mimetype="application/json")


@ibm_clouds.get('/clouds/<cloud_id>/cost-optimization/summary')
@authenticate
def get_ibm_cloud_cost_optimization_summary(cloud_id, user):
    """
    Send IBM Cloud Acount Cost Optimization summary
    :param cloud_id: id of the cloud
    :param user: object of the user initiating the request
    :return: Response object from flask package
    """
    cloud = ibmdb.session.query(IBMCloud).filter_by(project_id=user['project_id'], id=cloud_id, deleted=False).first()
    if not cloud:
        LOGGER.info(f"No IBM Cloud account found for project with ID {user['project_id']}")
        return Response(status=404)

    if not (cloud.settings and cloud.settings.cost_optimization_enabled):
        error = f"IBM Cloud cost optimization disabled with Cloud ID {cloud_id}"
        LOGGER.info(error)
        return Response(json.dumps({"error": error}), status=200)

    cloud_cost = None
    today = datetime.today()
    billing_month = datetime(today.year, today.month, 1)
    cost_obj = ibmdb.session.query(IBMCost).filter_by(cloud_id=cloud_id, billing_month=billing_month).first()

    if cost_obj:
        cloud_cost = round(int(cost_obj.billable_cost) / datetime.now().day) * 30
    cost_summary_json = {
        "cost": cloud_cost,
        "recommendations": {
        }
    }
    idle_resources_query = ibmdb.session.query(IBMIdleResource).filter_by(cloud_id=cloud.id)
    estimated_savings = 0
    for idle_resource in idle_resources_query:
        estimated_savings += idle_resource.estimated_savings if idle_resource and idle_resource.estimated_savings else 0

    cost_summary_json["recommendations"]["idle_resources"] = idle_resources_query.count()
    rightsizing_count = ibmdb.session.query(IBMRightSizingRecommendation).filter_by(
        cloud_id=cloud.id)
    cost_summary_json["recommendations"]["rightsizing"] = rightsizing_count.count()

    tags = ibmdb.session.query(IBMTag).filter_by(cloud_id=cloud_id, resource_type='vpc').all()
    tag_resource_ids = [tag.resource_id for tag in tags]
    untagged_vpcs = ibmdb.session.query(IBMVpcNetwork).filter(IBMVpcNetwork.id.not_in(tag_resource_ids),
                                                              IBMVpcNetwork.cloud_id == cloud_id).count()

    cost_summary_json["recommendations"]["tag_vpcs"] = untagged_vpcs
    cost_summary_json["estimated_savings"] = estimated_savings

    return Response(json.dumps(cost_summary_json), status=200, mimetype="application/json")


@ibm_clouds.route('/clouds/<cloud_id>/monitoring-token/validate', methods=['POST'])
@authenticate
@input(IBMMonitoringTokenInSchema)
@output(WorkflowRootOutSchema, status_code=202)
def validate_monitoring_token(cloud_id, data, user):
    """
    This call is to create a task for validating instance monitoring token
    """
    workflow_root = WorkflowRoot(
        user_id=user["id"],
        project_id=user["project_id"],
        workflow_name=f"{IBMCloud.__name__}-{IBMMonitoringToken.__name__}",
        workflow_nature=WorkflowTask.TYPE_VALIDATE
    )

    kwargs = dict()
    if data["region"].get("id"):
        kwargs["id"] = data["region"]["id"]
    else:
        kwargs["name"] = data["region"]["name"]

    region = ibmdb.session.query(IBMRegion).filter_by(**kwargs, cloud_id=cloud_id).first()
    if not region:
        msg = f"No IBM Region found with cloud id {cloud_id}"
        LOGGER.info(msg)
        abort(404, msg)

    workflow_root.add_next_task(WorkflowTask(
        task_type=WorkflowTask.TYPE_VALIDATE, resource_type=IBMMonitoringToken.__name__,
        task_metadata={"region": region.name, "token": data["token"]}
    ))

    ibmdb.session.add(workflow_root)
    ibmdb.session.commit()

    return workflow_root.to_json(metadata=True)


@ibm_clouds.get('/users/<user_id>/clouds/<cloud_id>/credentials/<credential_id>')
@authenticate_api_key
@output(CredentialOutSchema)
def get_ibm_cloud_credentials(user_id, cloud_id, credential_id):
    """
    Get IBM Cloud Account Credentials for provided id
    :param cloud_id: cloud_id for Cloud object
    :param user_id: user_id
    :param credential_id: credential_id
    """
    ibm_cloud = ibmdb.session.query(IBMCloud).filter_by(id=cloud_id, user_id=user_id, deleted=False).first()
    if not ibm_cloud:
        abort(404, f"No IBM Cloud with ID {cloud_id} found for the user")
    ibm_cloud_json = ibm_cloud.to_json()
    service_credential_key = ibm_cloud.service_credential_keys.filter_by(id=credential_id).first()
    if not service_credential_key:
        abort(404, f"No IBM Service Credential Key with ID {credential_id} found for the user")
    ibm_cloud_json["api_key"] = ibm_cloud.api_key
    ibm_cloud_json["access_key_id"] = service_credential_key.access_key_id
    ibm_cloud_json["secret_access_key"] = service_credential_key.secret_access_key
    ibm_cloud_json["ibm_service_credentials"] = service_credential_key.cloud_object_storage.crn
    return ibm_cloud_json
