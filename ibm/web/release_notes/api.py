import logging

from apiflask import abort, APIBlueprint, input, output
from flask import Response

from ibm.auth import authenticate, authorize_admin
from ibm.common.req_resp_schemas.schemas import get_pagination_schema, PaginationQuerySchema
from ibm.models import IBMReleaseNote
from ibm.web import db as ibmdb
from ibm.web.common.utils import get_paginated_response_json
from .schemas import IBMReleaseNoteInSchema, IBMReleaseNoteOutSchema, UpdateIBMReleaseNoteSchema

LOGGER = logging.getLogger(__name__)

ibm_release_notes = APIBlueprint('ibm_release_notes', __name__, tag="Release Notes")


@ibm_release_notes.route('/release_notes', methods=['GET'])
@authenticate
@input(PaginationQuerySchema, location='query')
@output(get_pagination_schema(IBMReleaseNoteOutSchema))
def list_ibm_release_notes(pagination_query_params, user):
    """
    List IBM Release Notes.
    """
    release_notes_page = ibmdb.session.query(IBMReleaseNote).paginate(
        page=pagination_query_params["page"], per_page=pagination_query_params["per_page"], error_out=False
    )
    if not release_notes_page.items:
        return '', 204

    return get_paginated_response_json(
        items=[item.to_json() for item in release_notes_page.items],
        pagination_obj=release_notes_page
    )


@ibm_release_notes.route('/release_notes/<release_note_id>', methods=['GET'])
@authenticate
@authorize_admin
@output(IBMReleaseNoteOutSchema)
def get_release_note(release_note_id, user):
    """
    Get IBM Release Note
    This request returns an IBM Release Note provided its ID.
    """
    release_note = ibmdb.session.query(IBMReleaseNote).filter_by(id=release_note_id).first()
    if not release_note:
        message = f"IBM Release Note {release_note} does not exist"
        LOGGER.debug(message)
        abort(404, message)

    return release_note.to_json()


@ibm_release_notes.route('/release_notes', methods=['POST'])
@authenticate
@authorize_admin
@input(IBMReleaseNoteInSchema)
def add_release_note(data, user):
    """ Add a new release note """
    release_note = IBMReleaseNote(
        title=data['title'], body=data['body'], url=data.get('url', None), version=data.get('version', None))
    ibmdb.session.add(release_note)
    ibmdb.session.commit()
    return release_note.to_json()


@ibm_release_notes.route('/release_notes/<release_note_id>', methods=['DELETE'])
@authenticate
@authorize_admin
def delete_release_note(release_note_id, user):
    release_note = ibmdb.session.query(IBMReleaseNote).filter_by(id=release_note_id).first()
    if not release_note:
        message = f"IBM Release Note {release_note} does not exist"
        LOGGER.debug(message)
        abort(404, message)

    ibmdb.session.delete(release_note)
    ibmdb.session.commit()
    return Response(status=202)


@ibm_release_notes.route('/release_notes/<release_note_id>', methods=['PATCH'])
@authenticate
@authorize_admin
@input(UpdateIBMReleaseNoteSchema)
def update_release_note(release_note_id, data, user):
    """ Update existing release note """
    release_note = ibmdb.session.query(IBMReleaseNote).filter_by(id=release_note_id).first()
    if not release_note:
        message = f"IBM Release Note {release_note} does not exist"

        LOGGER.debug(message)
        abort(404, message)

    if data.get('title'):
        release_note.title = data['title']

    if data.get('body'):
        release_note.body = data['body']

    if data.get('url'):
        release_note.url = data['url']

    if data.get('version'):
        release_note.version = data['version']

    ibmdb.session.commit()
    return release_note.to_json()
