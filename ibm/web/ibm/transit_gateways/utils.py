from ibm.models import IBMTransitGateway, WorkflowTask, IBMTransitGatewayConnection, \
    IBMTransitGatewayConnectionPrefixFilter, WorkflowRoot
from ibm.web import db


def create_ibm_transit_gateway_creation_workflow(data, user, cloud_id, db_session=None, sketch=False):
    """
    Workflow for Transit Gateway, Transit Gateway Connection and Transit Gateway Connection Prefix Filter Creation Tasks
    """
    if not db_session:
        db_session = db.session

    workflow_name = IBMTransitGateway.__name__
    if data["resource_json"].get("name"):
        workflow_name = ' '.join([workflow_name, data["resource_json"]["name"]])

    workflow_root = WorkflowRoot(
        user_id=user["id"], project_id=user["project_id"], workflow_name=workflow_name, workflow_nature="CREATE",
        fe_request_data=data
    )

    tg_creation_task = WorkflowTask(
        task_type=WorkflowTask.TYPE_CREATE, resource_type=IBMTransitGateway.__name__,
        task_metadata={"resource_data": data}
    )
    workflow_root.add_next_task(tg_creation_task)
    connection_tasks_obj_dict = dict()
    for connection_data in data.get("connections", []):
        conn_creation_task = WorkflowTask(
            task_type=WorkflowTask.TYPE_CREATE, resource_type=IBMTransitGatewayConnection.__name__,
            task_metadata={"resource_data": connection_data}
        )
        tg_creation_task.add_next_task(conn_creation_task)
        connection_tasks_obj_dict[connection_data["id"]] = conn_creation_task

    for prefix_filter_data in data.get("prefix_filters", []):
        prefix_creation_task = WorkflowTask(
            task_type=WorkflowTask.TYPE_CREATE, resource_type=IBMTransitGatewayConnectionPrefixFilter.__name__,
            task_metadata={"resource_data": prefix_filter_data}
        )
        tg_creation_task.add_next_task(prefix_creation_task)
        conn_creation_task = connection_tasks_obj_dict[prefix_filter_data["transit_gateway_connection"]["id"]]
        conn_creation_task.add_next_task(prefix_creation_task)

    if not sketch:
        db_session.add(workflow_root)

    db_session.commit()
    return workflow_root


def create_ibm_transit_gateway_connection_creation_workflow(data, user, cloud_id, db_session=None, sketch=False):
    """
    Workflow for Transit Gateway Connection and Transit Gateway Connection Prefix Filter Creation Tasks
    """
    if not db_session:
        db_session = db.session

    workflow_name = IBMTransitGatewayConnection.__name__
    if data["resource_json"].get("name"):
        workflow_name = ' '.join([workflow_name, data["resource_json"]["name"]])

    workflow_root = WorkflowRoot(
        user_id=user["id"], project_id=user["project_id"], workflow_name=workflow_name, workflow_nature="CREATE",
        fe_request_data=data
    )

    conn_creation_task = WorkflowTask(
        task_type=WorkflowTask.TYPE_CREATE, resource_type=IBMTransitGatewayConnection.__name__,
        task_metadata={"resource_data": data}
    )
    workflow_root.add_next_task(conn_creation_task)
    connection_tasks_obj_dict = dict()
    for prefix_filter_data in data.get("prefix_filters", []):
        prefix_creation_task = WorkflowTask(
            task_type=WorkflowTask.TYPE_CREATE, resource_type=IBMTransitGatewayConnectionPrefixFilter.__name__,
            task_metadata={"resource_data": prefix_filter_data}
        )
        conn_creation_task.add_next_task(prefix_creation_task)
        connection_tasks_obj_dict[prefix_filter_data["id"]] = prefix_creation_task

    if not sketch:
        db_session.add(workflow_root)

    db_session.commit()
    return workflow_root
