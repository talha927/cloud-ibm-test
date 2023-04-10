import logging
from typing import List

from apiflask import abort, APIBlueprint, input, output

from ibm.auth import authenticate
from ibm.common.req_resp_schemas.schemas import get_pagination_schema, IBMRegionalResourceRequiredListQuerySchema, \
    PaginationQuerySchema
from ibm.models import IBMCloud, IBMRegion, WorkflowRoot, WorkflowsWorkspace
from ibm.web import db as ibmdb
from ibm.web.common.utils import authorize_and_get_ibm_cloud, get_paginated_response_json, verify_and_get_region
from .schemas import IBMAllRegionalResourcesOutSchema, IBMExecuteRootsInSchema, IBMExecuteRootsOutSchema, \
    IBMWorkspaceCreationSchema, WorkflowsWorkspaceRefOutSchema, WorkflowsWorkspaceWithRootsOutSchema, \
    WorkspaceTypeQuerySchema
from .utils import update_workspace_workflow

LOGGER = logging.getLogger(__name__)

workspace = APIBlueprint('workspace', __name__, tag="Workspaces")


@workspace.post('/workspaces')
@authenticate
@input(IBMWorkspaceCreationSchema)
@output(WorkflowsWorkspaceWithRootsOutSchema, status_code=202)
def create_workspace(data, user):
    """
    Create Workspace
    This request creates multiple IBM Resources provided their schemas using a single API
    """
    workflows_workspace = \
        ibmdb.session.query(WorkflowsWorkspace).filter_by(
            name=data["name"], user_id=user["id"], project_id=user["project_id"]
        ).first()

    for vpc_json in data.get("vpc_networks", []):
        region_id = vpc_json["region"]["id"]
        region = \
            ibmdb.session.query(IBMRegion).filter_by(id=region_id).join(IBMRegion.ibm_cloud).filter_by(
                user_id=user["id"], project_id=user["project_id"], deleted=False
            ).first()
        if not region:
            message = f"IBM Region {region_id} does not exist"
            LOGGER.debug(message)
            abort(404, message)

        if region.ibm_cloud.status != IBMCloud.STATUS_VALID:
            message = f"IBM Cloud {region.ibm_cloud.name} is not in {IBMCloud.STATUS_VALID} status"
            LOGGER.debug(message)
            abort(404, message)

        if region.vpc_networks.filter_by(name=vpc_json["resource_json"]["name"]).first():
            if vpc_json["status"] != "available":
                message = f"IBMVpcNetwork with name {vpc_json['resource_json']['name']} already exists"
                LOGGER.debug(message)
                abort(409, message)

    backup_id = None
    if data.get("draas_restore_clusters"):
        backup_id = data.get("draas_restore_clusters")[0].get("backup_id")

    if data.get("source_cloud") == WorkflowsWorkspace.SOFTLAYER:
        workspace_type = WorkflowsWorkspace.TYPE_SOFTLAYER
    elif backup_id:
        workspace_type = WorkflowsWorkspace.TYPE_RESTORE
    else:
        workspace_type = WorkflowsWorkspace.TYPE_TRANSLATION

    workflows_workspace = update_workspace_workflow(
        user=user, data=data, source_cloud=data.get("source_cloud"), backup_id=backup_id,
        workspace_type=workspace_type
    )
    return workflows_workspace.to_json()


@workspace.post("/workspaces/<workspace_id>/provision")
@authenticate
def provision_workspace(workspace_id, user):
    """
    Provision Workspace
    This request will start provisioning the workspace: all the roots will be start provisioning.
    :param workspace_id:
    :return:
    """
    workflows_workspace: WorkflowsWorkspace = ibmdb.session.query(WorkflowsWorkspace).filter_by(id=workspace_id).first()
    if not workflows_workspace:
        message = f"WorkflowsWorkspace {workspace_id} not found"
        LOGGER.debug(message)
        abort(404, message)

    for workflow_root in workflows_workspace.associated_roots.filter(
            WorkflowRoot.status.in_((
                    WorkflowRoot.STATUS_ON_HOLD,
            ))).all():
        workflow_root.status = WorkflowRoot.STATUS_READY
        ibmdb.session.commit()

    workflows_workspace.status = WorkflowsWorkspace.STATUS_PENDING
    ibmdb.session.commit()

    return workflows_workspace.to_json()


@workspace.post("/provision-roots")
@authenticate
@input(IBMExecuteRootsInSchema)
@output(IBMExecuteRootsOutSchema)
def provision_roots(data, user):
    """
    Provision one or more roots in a Workspace
    This request will try to execute one or more roots within a Workspace.
    :param data:
    :param user:
    :return:
    """
    roots: List[WorkflowRoot] = ibmdb.session.query(WorkflowRoot).filter(
        WorkflowRoot.id.in_(data["roots"])
    ).all()

    if not roots:
        message = "WorkflowRoot with provided root_ids not found."
        details = {
            "roots": data["roots"]
        }
        abort(404, message, details)

    workflows_workspace: WorkflowsWorkspace = roots[0].workflow_workspace
    for root in roots:
        if root.status in [WorkflowRoot.STATUS_RUNNING, WorkflowRoot.STATUS_C_SUCCESSFULLY]:
            continue

        root.status = WorkflowRoot.STATUS_READY
        ibmdb.session.commit()

    workflows_workspace.status = WorkflowsWorkspace.STATUS_PENDING
    workflows_workspace.recently_provisioned_roots = data["roots"]
    ibmdb.session.commit()

    return {"workspace_id": workflows_workspace.id}


@workspace.get("/workspaces")
@authenticate
@input(WorkspaceTypeQuerySchema, location='query')
@input(PaginationQuerySchema, location='query')
@output(get_pagination_schema(WorkflowsWorkspaceRefOutSchema))
def list_workspaces(workspace_query_params, pagination_query_params, user):
    """
    List Workspaces
    This requests list all Workspaces for a given cloud
    :return:
    """
    workspace_type = workspace_query_params.get("workspace_type")

    workflows_workspaces_query = ibmdb.session.query(WorkflowsWorkspace).filter_by(
        user_id=user["id"], project_id=user["project_id"])
    if workspace_type:
        workflows_workspaces_query = workflows_workspaces_query.filter_by(workspace_type=workspace_type)

    workflows_workspaces_page = workflows_workspaces_query.paginate(
        page=pagination_query_params["page"], per_page=pagination_query_params["per_page"], error_out=False
    )
    if not workflows_workspaces_page.items:
        return '', 204

    return get_paginated_response_json(
        items=[item.to_reference_json() for item in workflows_workspaces_page.items],
        pagination_obj=workflows_workspaces_page
    )


@workspace.get("/workspaces/<workspace_id>")
@authenticate
@output(WorkflowsWorkspaceWithRootsOutSchema)
def get_workspace(workspace_id, user):
    """
    Get Workspace
    This request will get workspaces details provided with `workspace_id`.
    """
    workflows_workspace: WorkflowsWorkspace = ibmdb.session.query(WorkflowsWorkspace).filter_by(id=workspace_id).first()
    if not workflows_workspace:
        message = f"WorkflowsWorkspace {workspace_id} not found"
        LOGGER.debug(message)
        abort(404, message)

    return workflows_workspace.to_json()


@workspace.patch("/workspaces/<workspace_id>")
@authenticate
@input(IBMWorkspaceCreationSchema)
@output(WorkflowsWorkspaceWithRootsOutSchema)
def update_workspace(workspace_id, data, user):
    """
    Update Workspace
    This request will update the workspaces provided with `workspace_id`.
    """
    workflows_workspace: WorkflowsWorkspace = ibmdb.session.query(WorkflowsWorkspace).filter_by(id=workspace_id).first()
    if not workflows_workspace:
        message = f"WorkflowsWorkspace {workspace_id} not found"
        LOGGER.debug(message)
        abort(404, message)

    workflows_workspace = update_workspace_workflow(user, data, workspace_id)

    return workflows_workspace.to_json()


@workspace.delete("/workspaces/<workspace_id>")
@authenticate
def delete_workspace(workspace_id, user):
    """
    Delete Workspace
    This request will delete the workspace provided with the `workspace_id`.
    """
    workflows_workspace: WorkflowsWorkspace = ibmdb.session.query(WorkflowsWorkspace).filter_by(id=workspace_id).first()
    if not workflows_workspace:
        message = f"WorkflowsWorkspace {workspace_id} not found"
        LOGGER.debug(message)
        abort(404, message)

    if not workflows_workspace.deletable:
        message = f"Workspace with ID '{workspace_id}' cannot be deleted while workspace is in" \
                  f" {workflows_workspace.DELETION_NOT_ALLOWED_STATUSES} status"
        LOGGER.debug(message)
        abort(404, message)

    LOGGER. \
        info("""Please note that only workspace will be deleted without affecting the associated resources.""")

    ibmdb.session.delete(workflows_workspace)
    ibmdb.session.commit()

    return {"message": "success", "status": 202}


@workspace.get('/all-regional-resources')
@authenticate
@input(IBMRegionalResourceRequiredListQuerySchema, location='query')
@output(IBMAllRegionalResourcesOutSchema)
def list_ibm_resources(regional_res_query_params, user):
    """
    List all IBM Regional Resources
    This requests list all IBM Regional resources for a given cloud and region
    """
    cloud_id = regional_res_query_params["cloud_id"]
    region_id = regional_res_query_params["region_id"]

    ibm_cloud = authorize_and_get_ibm_cloud(cloud_id=cloud_id, user=user)
    region = verify_and_get_region(ibm_cloud=ibm_cloud, region_id=region_id)

    return {
        "vpc_networks": [vpc_network.validate_json_for_schema() for vpc_network in region.vpc_networks.all()],
        "subnets": [subnets.validate_json_for_schema() for subnets in region.subnets.all()],
        "public_gateways": [public_gateway.validate_json_for_schema() for public_gateway in
                            region.public_gateways.all()],
        "vpn_gateways": [vpn_gateway.validate_json_for_schema() for vpn_gateway in region.vpn_gateways.all()],
        "ike_policies": [ike_policy.validate_json_for_schema() for ike_policy in region.ike_policies.all()],
        "ipsec_policies": [ipsec_policy.validate_json_for_schema() for ipsec_policy in region.ipsec_policies.all()],
        "instances": [instance.validate_json_for_schema() for instance in region.instances.all()],
        "network_acls": [network_acl.validate_json_for_schema() for network_acl in region.network_acls.all()],
        "security_groups": [security_group.validate_json_for_schema() for security_group in
                            region.security_groups.all()],
        "load_balancers": [load_balancer.validate_json_for_schema() for load_balancer in region.load_balancers.all()],
        "dedicated_hosts": [dedicated_host.validate_json_for_schema() for dedicated_host in
                            region.dedicated_hosts.all()],
        "placement_groups": [placement_group.validate_json_for_schema() for placement_group in
                             region.placement_groups.all()],
        "ssh_keys": [ssh_key.validate_json_for_schema() for ssh_key in region.ssh_keys.all()],
        "kubernetes_clusters": [kubernetes_cluster.validate_json_for_schema() for kubernetes_cluster in
                                region.ibm_kubernetes_clusters.all()],
        "draas_restore_clusters": [kubernetes_cluster.validate_json_for_schema() for kubernetes_cluster in
                                   region.ibm_kubernetes_clusters.all()],
        "instance_profiles": [instance_profile.validate_json_for_schema() for instance_profile in
                              region.instance_profiles.all()],
        "images": [image.validate_json_for_schema() for image in region.images.all()],
        "operating_systems": [operating_system.validate_json_for_schema() for operating_system in
                              region.operating_systems.all()],
        "cos_buckets": [cos_bucket.validate_json_for_schema() for cos_bucket in region.cos_buckets.all()],
        "volumes": [volume.validate_json_for_schema() for volume in region.volumes.all()]
    }

# TODO: sequential deletion of Workspace
# How about reversing the tree of workspace and start deletion? :-)
