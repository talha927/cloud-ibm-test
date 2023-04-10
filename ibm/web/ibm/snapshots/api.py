import logging

from apiflask import abort, APIBlueprint, input, output

from ibm.auth import authenticate
from ibm.common.req_resp_schemas.schemas import get_pagination_schema, PaginationQuerySchema, WorkflowRootOutSchema
from ibm.models import IBMSnapshot, IBMVolume
from ibm.web import db as ibmdb
from ibm.web.common.utils import authorize_and_get_ibm_cloud, compose_ibm_resource_deletion_workflow, \
    create_ibm_resource_creation_workflow, get_paginated_response_json, verify_and_get_region, verify_references
from .schemas import IBMSnapshotInSchema, IBMSnapshotOutSchema, IBMSnapshotResourceSchema, IBMVolumeQuerySchema, \
    UpdateIBMSnapshotSchema

LOGGER = logging.getLogger(__name__)
ibm_snapshots = APIBlueprint('ibm_snapshots', __name__, tag="IBM Block Storage Snapshots")


@ibm_snapshots.post('/snapshots')
@authenticate
@input(IBMSnapshotInSchema)
@output(WorkflowRootOutSchema, status_code=202)
def create_ibm_snapshot(data, user):
    """
    Create an IBM Snapshot
    This request registers an IBM Snapshot with VPC+.
    """
    cloud_id = data["ibm_cloud"]["id"]
    region_id = data["region"]["id"]

    ibm_cloud = authorize_and_get_ibm_cloud(cloud_id=cloud_id, user=user)
    verify_and_get_region(ibm_cloud=ibm_cloud, region_id=region_id)

    verify_references(
        cloud_id=cloud_id, body_schema=IBMSnapshotInSchema, resource_schema=IBMSnapshotResourceSchema, data=data
    )

    workflow_root = create_ibm_resource_creation_workflow(
        user=user, resource_type=IBMSnapshot, data=data, validate=True
    )
    return workflow_root.to_json()


@ibm_snapshots.get('/snapshots')
@authenticate
@input(IBMVolumeQuerySchema, location='query')
@input(PaginationQuerySchema, location='query')
@output(get_pagination_schema(IBMSnapshotOutSchema))
def list_ibm_snapshots(volume_res_query_params, pagination_query_params, user):
    """
    List IBM Snapshots
    This request lists all IBM Snapshots for the project of the authenticated user calling the API.
    """
    cloud_id = volume_res_query_params["cloud_id"]
    region_id = volume_res_query_params.get("region_id")
    source_volume_id = volume_res_query_params.get("source_volume_id")
    bootable = volume_res_query_params.get("bootable")

    ibm_cloud = authorize_and_get_ibm_cloud(cloud_id=cloud_id, user=user)
    snapshots_query = ibmdb.session.query(IBMSnapshot).filter_by(cloud_id=cloud_id)

    if bootable in [True, False]:
        snapshots_query = snapshots_query.filter_by(bootable=bootable)

    if region_id:
        verify_and_get_region(ibm_cloud=ibm_cloud, region_id=region_id)
        snapshots_query = snapshots_query.filter_by(region_id=region_id)

    if source_volume_id:
        volume = ibmdb.session.query(IBMVolume).filter_by(id=source_volume_id).first()
        if not volume:
            message = f"IBM Volume {source_volume_id} not found."
            LOGGER.debug(message)
            abort(404, message)

        snapshots_query = snapshots_query.filter_by(source_volume_id=source_volume_id)

    snapshot_page = snapshots_query.paginate(
        page=pagination_query_params["page"], per_page=pagination_query_params["per_page"], error_out=False
    )
    if not snapshot_page.items:
        return '', 204

    return get_paginated_response_json(
        items=[item.to_json() for item in snapshot_page.items],
        pagination_obj=snapshot_page
    )


@ibm_snapshots.get('/snapshots/<snapshot_id>')
@authenticate
@output(IBMSnapshotOutSchema)
def get_ibm_snapshot(snapshot_id, user):
    """
    Get an IBM Snapshot
    This request returns an IBM Snapshot provided its ID.
    """
    snapshot = ibmdb.session.query(IBMSnapshot).filter_by(
        id=snapshot_id
    ).join(IBMSnapshot.ibm_cloud).filter_by(
        user_id=user["id"], project_id=user["project_id"], deleted=False
    ).first()
    if not snapshot:
        message = f"IBM Snapshot with ID {snapshot_id} does not exist"
        LOGGER.debug(message)
        abort(404, message)

    return snapshot.to_json()


@ibm_snapshots.delete('/snapshots/<snapshot_id>')
@authenticate
@output(WorkflowRootOutSchema, status_code=202)
def delete_ibm_snapshot(snapshot_id, user):
    """
    Delete an IBM Snapshot
    This request deletes an IBM Snapshot provided its ID.
    """
    snapshot: IBMSnapshot = ibmdb.session.query(IBMSnapshot).filter_by(id=snapshot_id) \
        .join(IBMSnapshot.ibm_cloud).filter_by(user_id=user["id"], project_id=user["project_id"], deleted=False) \
        .first()
    if not snapshot:
        message = f"IBM Snapshot {snapshot_id} does not exist"
        LOGGER.debug(message)
        abort(404, message)

    return compose_ibm_resource_deletion_workflow(
        user=user, resource_type=IBMSnapshot, resource_id=snapshot_id
    ).to_json(metadata=True)


@ibm_snapshots.delete('volumes/<volume_id>/snapshots')
@authenticate
@output(WorkflowRootOutSchema, status_code=202)
def delete_volume_attached_snapshots(volume_id, user):
    """
    Delete IBM Snapshots attached with Source Volume.
    This request deletes IBM Snapshots attached with source volume provided its ID.
    """
    volume: IBMVolume = ibmdb.session.query(IBMVolume).filter_by(id=volume_id) \
        .join(IBMVolume.ibm_cloud).filter_by(user_id=user["id"], project_id=user["project_id"], deleted=False).first()
    if not volume:
        message = f"IBM Volume {volume} does not exist"
        LOGGER.debug(message)
        abort(404, message)

    if not volume.source_snapshot:
        message = f"No Snapshots attached with Volume {volume_id}"
        LOGGER.debug(message)
        abort(404, message)

    authorize_and_get_ibm_cloud(cloud_id=volume.ibm_cloud.id, user=user)

    return compose_ibm_resource_deletion_workflow(
        user=user, resource_type=IBMVolume, resource_id=volume_id
    ).to_json(metadata=True)


@ibm_snapshots.patch('/snapshots/<snapshot_id>')
@authenticate
@input(UpdateIBMSnapshotSchema)
@output(WorkflowRootOutSchema, status_code=202)
def update_ibm_snapshot(snapshot_id, data, user):
    """
    Update an IBM Snapshot
    This request updates an IBM Snapshot provided its ID.
    """
    abort(404)
