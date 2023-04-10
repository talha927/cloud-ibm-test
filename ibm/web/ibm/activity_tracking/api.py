from apiflask import APIBlueprint, doc, input, output

from ibm.auth import authenticate
from ibm.models import IBMActivityTracking
from ibm.web import db as ibmdb
from ibm.common.req_resp_schemas.schemas import get_pagination_schema, PaginationQuerySchema
from ibm.web.common.utils import authorize_and_get_ibm_cloud, get_paginated_response_json
from ibm.web.ibm.activity_tracking.schemas import IBMActivityTrackingOutSchema, IBMActivityTrackingSearchSchema

ibm_activity_tracking = APIBlueprint('ibm_activity_tracking', __name__, tag="Activity Tracking")


@ibm_activity_tracking.route("/activity_tracking", methods=["GET"])
@authenticate
@input(PaginationQuerySchema, location='query')
@input(IBMActivityTrackingSearchSchema, location='query')
@output(get_pagination_schema(IBMActivityTrackingOutSchema))
@doc(
    responses={
        204: "No records found"
    }
)
def list_ibm_activity_tracking(pagination_query_params, search_query_params, user):
    """
    List IBM address prefixes
    This request lists all IBM address prefixes.
    """
    cloud_id = search_query_params.get("cloud_id")  # if user wants to check specific cloud account logs
    activity_type = search_query_params.get("activity_type")
    resource_type = search_query_params.get("resource_type")
    user_email = search_query_params.get("user")

    activity_tracking_query = ibmdb.session.query(IBMActivityTracking).filter_by(project_id=user['project_id'])

    if cloud_id:
        authorize_and_get_ibm_cloud(cloud_id=cloud_id, user=user)
        activity_tracking_query = ibmdb.session.query(IBMActivityTracking).filter_by(
            cloud_id=cloud_id, project_id=user['project_id'])

    if activity_type:
        activity_tracking_query = activity_tracking_query.filter_by(activity_type=activity_type)

    if resource_type:
        activity_tracking_query = activity_tracking_query.filter(
            IBMActivityTracking.resource_type.like(f"%{resource_type}%"))

    if user_email:
        activity_tracking_query = activity_tracking_query.filter_by(user=user_email)

    activity_objects = activity_tracking_query.all()
    for activity_object in activity_objects:
        activity_object.detailed_summary = activity_object.root_id

    activity_tracking_page = activity_tracking_query.paginate(
        page=pagination_query_params["page"], per_page=pagination_query_params["per_page"], error_out=False
    )
    if not activity_tracking_page.items:
        return '', 204

    return get_paginated_response_json(
        items=[item.to_json() for item in activity_tracking_page.items],
        pagination_obj=activity_tracking_page
    )
