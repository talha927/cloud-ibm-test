import json
import logging

from apiflask import APIBlueprint, input
from sqlalchemy import and_, extract, func

from ibm.auth import authenticate, Response
from ibm.common.consts import INT_MONTH_TO_STR, MONTHS_STR_TO_INT
from ibm.common.utils import get_month_interval
from ibm.models import IBMCloud, IBMCost, IBMResourceInstancesCost, IBMIdleResource, IBMResourceControllerData, \
    IBMResourceTracking, IBMRightSizingRecommendation
from ibm.web import db as ibmdb
from .schemas import IBMCostReportingQuerySchema

LOGGER = logging.getLogger(__name__)

ibm_reporting = APIBlueprint('ibm_reporting', __name__, tag="IBM Reporting")


@ibm_reporting.route('/cost_reporting', methods=['GET'])
@authenticate
@input(IBMCostReportingQuerySchema, location='query')
def get_ibm_cloud_report(cloud_query_params, user):
    """
    Get IBM Cloud Cost Report
    """
    cloud_id = cloud_query_params.get("cloud_id")
    month = cloud_query_params.get("month")

    if cloud_id:
        cloud = ibmdb.session.query(IBMCloud).filter_by(user_id=user["id"], id=cloud_id).first()
    else:
        cloud = ibmdb.session.query(IBMCloud).filter_by(user_id=user["id"]).all()
    if not cloud:
        LOGGER.info(f"No IBM Cloud accounts found for user with ID {user['id']}")
        return Response(status=404)

    if month and month.lower() not in MONTHS_STR_TO_INT.keys():
        return Response(status=400)

    start, end = get_month_interval(month)
    month = start.month
    year = start.year

    cost_obj = ibmdb.session.query(IBMCost).filter_by(cloud_id=cloud_id, billing_month=start).first()
    if not cost_obj:
        LOGGER.info(f"No IBM Cloud Cost with ID {cloud_id} not found")
        return Response(status=204)

    resource_instances_cost_crns_sq = \
        ibmdb.session.query(IBMResourceInstancesCost.crn).filter_by(cost_id=cost_obj.id).subquery()

    idle_resource_saving = ibmdb.session.query(func.sum(IBMIdleResource.estimated_savings).label(
        'idle_resource_saving')).filter(and_(extract('month', IBMIdleResource.created_at) == month,
                                             extract('year', IBMIdleResource.created_at) == year)).filter_by(
        cloud_id=cloud_id).all()

    right_sizing_saving = ibmdb.session.query(func.sum(IBMRightSizingRecommendation.estimated_monthly_savings).label(
        'right_sizing_saving')).filter_by(cloud_id=cloud_id).filter(
        and_(extract('month', IBMRightSizingRecommendation.created_at) == month,
             extract('year', IBMRightSizingRecommendation.created_at) == year)).filter_by(
        cloud_id=cloud_id).all()

    savings_achieved = ibmdb.session.query(
        func.sum(IBMResourceTracking.estimated_savings).label("estimated_savings")).filter(
        and_(extract('month', IBMResourceTracking.action_taken_at) == month,
             extract('year', IBMResourceTracking.action_taken_at) == year)).filter_by(cloud_id=cloud_id).all()

    idle_resource_saving = idle_resource_saving[0][0] if idle_resource_saving[0][0] else 0.0
    right_sizing_saving = right_sizing_saving[0][0] if right_sizing_saving[0][0] else 0.0
    savings_achieved = savings_achieved[0][0] if savings_achieved[0][0] else 0.0
    savings = idle_resource_saving + right_sizing_saving

    ibm_resources_created_this_month_json = []
    ibm_resources_deleted_this_month_json = []
    older_resources_costed_this_month_json = []
    ibm_resources = ibmdb.session.query(IBMResourceControllerData).filter_by(cloud_id=cloud_id).\
        filter(IBMResourceControllerData.crn.in_(resource_instances_cost_crns_sq)).all()
    for ibm_resource in ibm_resources:
        if ibm_resource.created_at and ibm_resource.created_at > start and ibm_resource.created_at < end:
            ibm_resources_created_this_month_json.append(ibm_resource.to_reporting_json(month=start))
        elif ibm_resource.deleted_at and ibm_resource.deleted_at > start and ibm_resource.deleted_at < end:
            ibm_resources_deleted_this_month_json.append(ibm_resource.to_reporting_json(month=start))
        else:
            older_resources_costed_this_month_json.append(ibm_resource.to_reporting_json(month=start))

    right_sizing_recommendation_count = ibmdb.session.query(IBMRightSizingRecommendation).filter(
        and_(extract('month', IBMRightSizingRecommendation.created_at) == month,
             extract('year', IBMRightSizingRecommendation.created_at) == year)).filter_by(
        cloud_id=cloud_id).count() or 0

    idle_resource_recommendation_count = ibmdb.session.query(IBMIdleResource).filter(
        and_(extract('month', IBMIdleResource.created_at) == month,
             extract('year', IBMIdleResource.created_at) == year)).filter_by(cloud_id=cloud_id).count() or 0

    total_recommendation_generated = right_sizing_recommendation_count + idle_resource_recommendation_count

    actions_taken_at = ibmdb.session.query(IBMResourceTracking).filter(
        and_(extract('month', IBMResourceTracking.action_taken_at) == month,
             extract('year', IBMResourceTracking.action_taken_at) == year)).filter_by(cloud_id=cloud_id).count()

    cost_report_json = {
        "summary": {
            "cloud_id": cloud_id,
            "name": cloud.name,
            "month": INT_MONTH_TO_STR[month],
            "recommendations": {
                "total_recommendations": total_recommendation_generated,
                "action_taken": actions_taken_at,
                "actions_pending": total_recommendation_generated-actions_taken_at,
                "cost": cost_obj.billable_cost,
                "realized_savings": savings,
                "potential_savings": savings - savings_achieved,
            },
        },
        "details": {
            "resources_created_this_month": ibm_resources_created_this_month_json,
            "resources_deleted_this_month": ibm_resources_deleted_this_month_json,
            "older_resources": older_resources_costed_this_month_json
        }
    }

    return Response(json.dumps(cost_report_json), status=200, mimetype="application/json")
