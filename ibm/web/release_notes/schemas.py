from marshmallow import Schema
from marshmallow.fields import Date, Dict, String
from marshmallow.validate import Length, Regexp

from ibm.common.req_resp_schemas.consts import IBM_UUID_PATTERN


class IBMReleaseNoteInSchema(Schema):
    title = String(validate=Length(max=255), required=True, allow_none=False,
                   description="Title given to a Release Note")
    body = Dict(
        required=True, allow_none=True,
        description="Further description of release note and its explanation regarding feature or bug")
    url = String(validate=Length(max=255))
    version = String(validate=Length(max=32), description="Version tracking of release notes")


class IBMReleaseNoteOutSchema(Schema):
    id = String(
        required=True, allow_none=False, validate=[Length(equal=32), Regexp(IBM_UUID_PATTERN)],
        description="Unique ID of the Release Note"
    )
    title = String(validate=Length(max=255), required=True, allow_none=False,
                   description="Title given to a Release Note")
    body = Dict(
        required=True, allow_none=True,
        description="Further description of release note and its explanation regarding feature or bug")
    release_date = Date()
    url = String(validate=Length(max=255))
    version = String(validate=Length(max=32), description="Version tracking of release notes")


class UpdateIBMReleaseNoteSchema(Schema):
    title = String(validate=Length(max=255), description="Title given to a Release Note")
    body = Dict(description="Further description of release note and its explanation regarding feature or bug")
    url = String(validate=Length(max=255))
    version = String(validate=Length(max=32), description="Version tracking of release notes")
