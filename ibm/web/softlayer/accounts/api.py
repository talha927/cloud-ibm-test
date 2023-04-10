import logging

from apiflask import abort, APIBlueprint, input, output

from ibm.auth import authenticate
from ibm.common.req_resp_schemas.schemas import get_pagination_schema, PaginationQuerySchema, WorkflowRootOutSchema
from ibm.models import SoftlayerCloud, WorkflowRoot, WorkflowTask
from ibm.web import db as ibmdb
from ibm.web.common.utils import get_paginated_response_json
from ibm.web.softlayer.accounts.schemas import SoftLayerAccountInSchema, SoftLayerAccountOutSchema, \
    SoftLayerAccountQuerySchema, SoftLayerAccountUpdateSchema

LOGGER = logging.getLogger(__name__)
softlayer_account = APIBlueprint('softlayer_account', __name__, tag="SoftLayerAccounts")


@softlayer_account.post("/accounts")
@authenticate
@input(SoftLayerAccountInSchema)
@output(WorkflowRootOutSchema, status_code=202)
def create_softlayer_account(data, user):
    """
    Create Softlayer Account
    This request creates a Softlayer account
    """
    existing_clouds = ibmdb.session.query(SoftlayerCloud).filter_by(
        user_id=user["id"], project_id=user["project_id"]
    ).all()
    for existing_cloud in existing_clouds:
        if existing_cloud.name == data["name"]:
            abort(409, f"IBM Cloud with the name {data['name']} already exists")

        if existing_cloud.api_key == data["api_key"]:
            abort(409, f"IBM Cloud {existing_cloud.id} already exists with the same API Key")

    softlayer_cloud_account = SoftlayerCloud(
        name=data['name'], username=data['username'], api_key=data['api_key'],
        project_id=user["project_id"]
    )
    softlayer_cloud_account.user_id = user["id"]
    ibmdb.session.add(softlayer_cloud_account)
    ibmdb.session.commit()

    workflow_root = WorkflowRoot(
        user_id=user["id"],
        project_id=user["project_id"],
        workflow_name=f"{SoftlayerCloud.__name__} ({data['name']})",
        workflow_nature="ADD"
    )
    validate_cloud_task = WorkflowTask(
        task_type=WorkflowTask.TYPE_VALIDATE, resource_type=SoftlayerCloud.__name__,
        task_metadata={"softlayer_cloud_id": softlayer_cloud_account.id}
    )
    workflow_root.add_next_task(validate_cloud_task)
    ibmdb.session.add(workflow_root)
    ibmdb.session.commit()
    return workflow_root.to_json()


@softlayer_account.get('/accounts')
@authenticate
@input(SoftLayerAccountQuerySchema, location='query')
@input(PaginationQuerySchema, location='query')
@output(get_pagination_schema(SoftLayerAccountOutSchema))
def list_softlayer_account(regional_res_query_params, pagination_query_params, user):
    """
    List Softlayer Clouds
    This requests list all Softlayer Clouds for a given user
    """
    status = regional_res_query_params.get("status")

    accounts_query = ibmdb.session.query(SoftlayerCloud).filter_by(
        user_id=user["id"], project_id=user["project_id"]
    )
    if status:
        accounts_query = accounts_query.filter_by(status=status)
    account_page = accounts_query.paginate(
        page=pagination_query_params["page"], per_page=pagination_query_params["per_page"],
        error_out=False
    )
    if not account_page.items:
        return '', 204

    return get_paginated_response_json(
        items=[item.to_json() for item in account_page.items],
        pagination_obj=account_page
    )


@softlayer_account.get('/accounts/<account_id>')
@authenticate
@output(SoftLayerAccountOutSchema)
def get_softlayer_cloud(account_id, user):
    """
    Get Softlayer Account
    This request returns a Softlayer account its ID
    """
    account = ibmdb.session.query(SoftlayerCloud).filter_by(
        id=account_id, user_id=user["id"], project_id=user["project_id"]
    ).first()
    if not account:
        message = f"Softlayer Account {account_id} does not exist"
        LOGGER.debug(message)
        abort(404, message)

    return account.to_json()


@softlayer_account.delete('/accounts/<account_id>')
@authenticate
def delete_softlayer_cloud(account_id, user):
    """
    Delete Softlayer Account
    This request delete a Softlayer account its ID
    """
    account = ibmdb.session.query(SoftlayerCloud).filter_by(
        id=account_id, user_id=user["id"], project_id=user["project_id"]
    ).first()
    if not account:
        message = f"Softlayer Account {account_id} does not exist"
        LOGGER.debug(message)
        abort(404, message)

    ibmdb.session.delete(account)
    ibmdb.session.commit()
    message = f"Softlayer Account {account_id} deleted Successfully"
    LOGGER.info(message)
    return message, 204


@softlayer_account.patch('/accounts/<account_id>')
@authenticate
@input(SoftLayerAccountUpdateSchema, location='json')
@output(WorkflowRootOutSchema, status_code=202)
def update_softlayer_account(account_id, data, user):
    """
    Update Softlayer Account
    This request updates a Softlayer Account
    """
    softlayer_cloud_account = ibmdb.session.query(SoftlayerCloud).filter_by(
        id=account_id, user_id=user["id"], project_id=user["project_id"],
    ).first()
    if not softlayer_cloud_account:
        message = f"Softlayer Account {account_id} does not exist"
        LOGGER.debug(message)
        abort(404, message)

    if data.get("name"):
        softlayer_cloud_account.name = data["name"]

    if data.get("username"):
        softlayer_cloud_account.username = data["username"]

    if data.get("api_key"):
        softlayer_cloud_account.api_key = data["api_key"]
    softlayer_cloud_account.status = SoftlayerCloud.STATUS_AUTHENTICATING
    ibmdb.session.commit()

    workflow_root = WorkflowRoot(
        user_id=user["id"],
        project_id=user["project_id"],
        workflow_name=f"{SoftlayerCloud.__name__} ({data['name']})",
        workflow_nature="ADD"
    )
    validate_cloud_task = WorkflowTask(
        task_type=WorkflowTask.TYPE_VALIDATE, resource_type=SoftlayerCloud.__name__,
        task_metadata={"softlayer_cloud_id": softlayer_cloud_account.id}
    )
    workflow_root.add_next_task(validate_cloud_task)
    ibmdb.session.add(workflow_root)
    ibmdb.session.commit()
    return workflow_root.to_json()
