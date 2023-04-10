import json
import logging
from collections import OrderedDict

from apiflask import APIBlueprint
from flask import request, Response
from flask_sqlalchemy import Pagination
from sqlalchemy import func

from config import PaginationConfig
from ibm.auth import authenticate
from ibm.common.consts import MONTHS_STR_TO_INT
from ibm.common.utils import get_month_interval
from ibm.models import IBMCost, IBMCloud, IBMResourceTracking, IBMResourceInstancesCost, \
    IBMResourceInstancesDailyCost as DailyCost, IBMRightSizingRecommendation, IBMIdleResource
from ibm.web import db as ibmdb

LOGGER = logging.getLogger(__name__)

ibm_resource_tracking = APIBlueprint('ibm_resource_tracking', __name__, tag="IBM Resource Tracking")


@ibm_resource_tracking.get('/clouds/<cloud_id>/resource-tracking')
@authenticate
def list_ibm_resource_tracking(cloud_id, user):
    """
       List IBM Resource Tracking with  cloud ID
       :param user: object of the user initiating the request
       :param cloud_id: cloud_id for IBMCloud
       :return: Response object from flask package
    """
    ibm_cloud = ibmdb.session.query(IBMCloud).filter_by(id=cloud_id, project_id=user["project_id"]).first()
    if not ibm_cloud:
        LOGGER.info(f"No IBM cloud found with ID: {cloud_id}")
        return Response("CLOUD_NOT_FOUND", status=404)

    if not (ibm_cloud.settings and ibm_cloud.settings.cost_optimization_enabled):
        error = f"IBM Cloud cost optimization disabled with Cloud ID {cloud_id}"
        LOGGER.info(error)
        return Response(json.dumps({"error": error}), status=200)

    resource_tracking = IBMResourceTracking.search_and_filter(request.args, cloud_id)
    if not resource_tracking.items:
        LOGGER.info(f"No IBM Tracking Resources for cloud with ID: {cloud_id}")
        return Response("IDLE_RESOURCES_WITH_CLOUD_ID_NOT_FOUND", status=204)

    month = request.args.get('month')
    if month and month.lower() not in MONTHS_STR_TO_INT.keys():
        return Response(status=400)

    resource_tracking_json = {
        "items": [resource.to_json() for resource in resource_tracking.items],
        "previous": resource_tracking.prev_num if resource_tracking.has_prev else None,
        "next": resource_tracking.next_num if resource_tracking.has_next else None,
        "pages": resource_tracking.pages
    }
    return Response(json.dumps(resource_tracking_json), status=200, mimetype="application/json")


@ibm_resource_tracking.get('/clouds/<cloud_id>/cost-tracking')
@authenticate
def list_ibm_cost_tracking(cloud_id, user):
    """
       List IBM Cost Tracking with  cloud ID
       :param user: object of the user initiating the request
       :param cloud_id: cloud_id for IBMCloud
       :return: Response object from flask package
    """
    ibm_cloud = ibmdb.session.query(IBMCloud).filter_by(id=cloud_id, project_id=user["project_id"]).first()
    if not ibm_cloud:
        LOGGER.info(f"No IBM cloud found with ID: {cloud_id}")
        return Response("CLOUD_NOT_FOUND", status=404)

    if not (ibm_cloud.settings and ibm_cloud.settings.cost_optimization_enabled):
        error = f"IBM Cloud cost optimization disabled with Cloud ID {cloud_id}"
        LOGGER.info(error)
        return Response(json.dumps({"error": error}), status=200)

    month = request.args.get('month')
    if month and month.lower() not in MONTHS_STR_TO_INT.keys():
        return Response(status=400)

    start, end = get_month_interval(month)
    granularity = request.args.get('granularity')
    if granularity and granularity == 'monthly':
        monthly_cost_obj = ibmdb.session.query(func.sum(IBMCost.billable_cost).label('total_cost'),
                                               func.date(IBMCost.billing_month).label('date')). \
            filter_by(cloud_id=cloud_id).group_by(IBMCost.billing_month)
        if not monthly_cost_obj:
            return Response(status=204)
        monthly_costs = [{str(cost.date): cost.total_cost} for cost in monthly_cost_obj]
        monthly_costs_dict = dict(cost_obj for monthly_cost in monthly_costs for cost_obj in monthly_cost.items())

        monthly_savings = ibmdb.session.query(
            func.date_format(func.date(IBMResourceTracking.action_taken_at), "%Y%-%m%-%01").label('date'),
            func.sum(IBMResourceTracking.estimated_savings).label('savings')) \
            .filter_by(cloud_id=cloud_id).group_by(
            IBMResourceTracking.action_taken_at).all()
        monthly_savings_costs = [{monthly_saving.date: monthly_saving.savings} for monthly_saving in monthly_savings]
        monthly_savings_dict = dict(
            cost_obj for monthly_saving in monthly_savings_costs for cost_obj in monthly_saving.items())

        monthly_savings_trend = []
        for key, value in monthly_costs_dict.items():
            estim_savings = monthly_savings_dict.get(key, 0.0)
            monthly_savings_trend.append({'date': str(key), 'cost': value, 'optimized_cost': abs(value - estim_savings),
                                          'savings': estim_savings})
            if monthly_savings_dict.get(key) is not None:
                monthly_savings_dict.pop(key)

        for key, value in monthly_savings_dict.items():
            monthly_savings_trend.append({'date': str(key), 'cost': 0.0, 'optimized_cost': 0.0, 'savings': value})

        return Response(json.dumps(monthly_savings_trend), status=200, mimetype="application/json")

    cost_obj = ibmdb.session.query(IBMCost).filter_by(cloud_id=cloud_id, billing_month=start).first()
    if not cost_obj:
        return Response(status=204)

    daily_cost = ibmdb.session.query(DailyCost.date.label('date'), func.sum(DailyCost.daily_cost).label('cost')). \
        filter_by(cost_id=cost_obj.id).group_by(DailyCost.date).all()

    daily_savings = ibmdb.session.query(func.date(IBMResourceTracking.action_taken_at).label('date'),
                                        func.sum(IBMResourceTracking.estimated_savings).label('savings')) \
        .filter_by(cloud_id=cloud_id).filter(IBMResourceTracking.action_taken_at >= start,
                                             IBMResourceTracking.action_taken_at < end).group_by(
        IBMResourceTracking.action_taken_at).all()
    if not (daily_cost or daily_savings):
        LOGGER.info(f"No IBM Cost Tracking for cloud with ID: {cloud_id}")
        return Response("COST_TRACKING_WITH_CLOUD_ID_NOT_FOUND", status=204)

    daily_cost_dict = dict((x, y) for x, y in daily_cost)
    daily_savings_dict = dict((x, y) for x, y in daily_savings)

    daily_savings_trend = {}
    for key, value in daily_cost_dict.items():
        estim_savings = daily_savings_dict.get(key, 0.0)
        daily_savings_trend[str(key)] = \
            {'date': str(key), 'cost': value, 'optimized_cost': abs(value - estim_savings), 'savings': estim_savings}
        if daily_savings_dict.get(key) is not None:
            daily_savings_dict.pop(key)

    for key, value in daily_savings_dict.items():
        daily_savings_trend[str(key)] = {'date': str(key), 'cost': 0.0, 'optimized_cost': 0.0, 'savings': value}

    daily_savings_trend = dict(OrderedDict(sorted(daily_savings_trend.items())))
    return Response(json.dumps(list(daily_savings_trend.values())), status=200, mimetype="application/json")


@ibm_resource_tracking.get('/clouds/<cloud_id>/resources-cost')
@authenticate
def list_ibm_resources_cost(cloud_id, user):
    """
       List IBM Resources Cost with cloud ID
       :param user: object of the user initiating the request
       :param cloud_id: cloud_id for IBMCloud
       :return: Response object from flask package
    """
    ibm_cloud = ibmdb.session.query(IBMCloud).filter_by(id=cloud_id, project_id=user["project_id"]).first()
    if not ibm_cloud:
        LOGGER.info(f"No IBM cloud found with ID: {cloud_id}")
        return Response("CLOUD_NOT_FOUND", status=404)

    if not (ibm_cloud.settings and ibm_cloud.settings.cost_optimization_enabled):
        error = f"IBM Cloud cost optimization disabled with Cloud ID {cloud_id}"
        LOGGER.info(error)
        return Response(json.dumps({"error": error}), status=200)

    month = request.args.get('month')
    if month and month.lower() not in MONTHS_STR_TO_INT.keys():
        return Response(status=400)

    start, end = get_month_interval(month)
    cost_obj = ibmdb.session.query(IBMCost).filter_by(cloud_id=cloud_id, billing_month=start).first()
    if not cost_obj:
        return Response(status=204)

    total_cost = cost_obj.billable_cost

    costs = ibmdb.session.query(
        IBMResourceInstancesCost.resource_id, func.sum(IBMResourceInstancesCost.cost).label('cost')).group_by(
        IBMResourceInstancesCost.resource_id).filter_by(cloud_id=cloud_id, cost_id=cost_obj.id).all()

    cost_by_resource = list()
    total_resources_cost = 0.0
    for cost in costs:
        name = IBMResourceInstancesCost.resource_id_resource_type_mapper.get(cost.resource_id, "Others")
        if name != 'Others':
            cost_by_resource.append({"name": name, "cost": cost.cost})
            total_resources_cost = total_resources_cost + cost.cost

    if total_cost != total_resources_cost:
        cost_by_resource.append({"name": "Others", "cost": total_cost - total_resources_cost})

    cost_by_resource = {
        "total_cost": total_cost,
        "cost_by_resource": cost_by_resource
    }

    return Response(json.dumps(cost_by_resource), status=200, mimetype="application/json")


@ibm_resource_tracking.get('/clouds/<cloud_id>/saving-recommendation-cost')
@authenticate
def list_ibm_recommendation_cost(cloud_id, user):
    """
       List IBM Resources Cost with cloud ID
       :param user: object of the user initiating the request
       :param cloud_id: cloud_id for IBMCloud
       :return: Response object from flask package
    """
    ibm_cloud = ibmdb.session.query(IBMCloud).filter_by(id=cloud_id, project_id=user["project_id"]).first()
    if not ibm_cloud:
        LOGGER.info(f"No IBM cloud found with ID: {cloud_id}")
        return Response("CLOUD_NOT_FOUND", status=404)

    if not (ibm_cloud.settings and ibm_cloud.settings.cost_optimization_enabled):
        error = f"IBM Cloud cost optimization disabled with Cloud ID {cloud_id}"
        LOGGER.info(error)
        return Response(json.dumps({"error": error}), status=200)

    month = request.args.get('month')
    if month and month.lower() not in MONTHS_STR_TO_INT.keys():
        return Response(status=400)

    start, end = get_month_interval(month)
    right_sizing_saving = ibmdb.session.query(func.sum(IBMRightSizingRecommendation.estimated_monthly_savings).label(
        'right_sizing_saving')).filter_by(cloud_id=cloud_id).filter(
        IBMRightSizingRecommendation.created_at >= start,
        IBMRightSizingRecommendation.created_at < end).first().right_sizing_saving or 0.0

    rightsizing_achieved_savings = ibmdb.session.query(func.sum(IBMResourceTracking.estimated_savings).label(
        'savings')).filter_by(cloud_id=cloud_id, action_type=IBMResourceTracking.RIGHT_SIZED).filter(
        IBMResourceTracking.action_taken_at >= start, IBMResourceTracking.action_taken_at < end).first().savings or 0.0

    idle_resource_saving = ibmdb.session.query(
        func.sum(IBMIdleResource.estimated_savings).label('idle_resource_saving')).filter_by(
        cloud_id=cloud_id).filter(
        IBMIdleResource.created_at >= start,
        IBMIdleResource.created_at < end).first().idle_resource_saving or 0.0

    idle_resource_achieved_savings = ibmdb.session.query(func.sum(IBMResourceTracking.estimated_savings).label(
        'savings')).filter_by(cloud_id=cloud_id, action_type=IBMResourceTracking.DELETED).filter(
        IBMResourceTracking.action_taken_at >= start, IBMResourceTracking.action_taken_at < end).first().savings or 0.0

    total_cost = right_sizing_saving + idle_resource_saving + rightsizing_achieved_savings + \
        idle_resource_achieved_savings
    if total_cost == 0.0:
        LOGGER.info(f"No Savings by Recommendation for cloud with ID: {cloud_id}")
        return Response("SAVINGS_BY_RECOMMENDATION_WITH_CLOUD_ID_NOT_FOUND", status=204)

    savings_by_recommendations = {
        "total_cost": total_cost,
        "savings_by_recommendations": [
            {
                "name": "Rightsizing",
                "cost": right_sizing_saving + rightsizing_achieved_savings
            },
            {
                "name": "Idle Resources",
                "cost": idle_resource_saving + idle_resource_achieved_savings
            },
        ]
    }

    return Response(json.dumps(savings_by_recommendations), status=200, mimetype="application/json")


@ibm_resource_tracking.route('/clouds/<cloud_id>/recommendations_activity', methods=['GET'])
@authenticate
def list_ibm_recommendation_count(cloud_id, user):
    ibm_cloud = ibmdb.session.query(IBMCloud).filter_by(id=cloud_id, project_id=user["project_id"]).first()
    if not ibm_cloud:
        LOGGER.info(f"No IBM cloud found with ID: {cloud_id}")
        return Response("CLOUD_NOT_FOUND", status=404)

    if not (ibm_cloud.settings and ibm_cloud.settings.cost_optimization_enabled):
        error = f"IBM Cloud cost optimization disabled with Cloud ID {cloud_id}"
        LOGGER.info(error)
        return Response(json.dumps({"error": error}), status=200)

    month = request.args.get('month')
    if month and month.lower() not in MONTHS_STR_TO_INT.keys():
        return Response(status=400)

    start, end = get_month_interval(month)
    right_sizing_saving = ibmdb.session.query(func.sum(IBMRightSizingRecommendation.estimated_monthly_savings).label(
        'right_sizing_saving')).filter_by(cloud_id=cloud_id).filter(
        IBMRightSizingRecommendation.created_at < end).first().right_sizing_saving or 0.0
    right_sizing_recomm_count = ibmdb.session.query(IBMRightSizingRecommendation).filter_by(cloud_id=cloud_id).filter(
        IBMRightSizingRecommendation.created_at < end).count() or 0

    idle_resource_saving = ibmdb.session.query(func.sum(IBMIdleResource.estimated_savings).label(
        'idle_resource_saving')).filter_by(cloud_id=cloud_id).filter(
        IBMIdleResource.created_at < end).first().idle_resource_saving or 0.0
    idle_resource_count = ibmdb.session.query(IBMIdleResource).filter_by(cloud_id=cloud_id).filter(
        IBMIdleResource.created_at < end).count() or 0

    savings_achieved = ibmdb.session.query(
        func.sum(IBMResourceTracking.estimated_savings).label("estimated_savings")).filter_by(cloud_id=cloud_id). \
        filter(IBMResourceTracking.action_taken_at >= start, IBMResourceTracking.action_taken_at < end).first(). \
        estimated_savings or 0.0

    savings = right_sizing_saving + idle_resource_saving + savings_achieved
    count = right_sizing_recomm_count + idle_resource_count

    actions_taken_at = ibmdb.session.query(IBMResourceTracking).filter_by(
        cloud_id=cloud_id).filter(IBMResourceTracking.action_taken_at >= start,
                                  IBMResourceTracking.action_taken_at < end).count()

    savings_by_recommendations = {
        "realized_savings": savings,
        "potential_savings": abs(right_sizing_saving + idle_resource_saving),
        "recommendations":
            {
                "actions_pending": count,
                "actions_taken": actions_taken_at
            }
    }

    return Response(json.dumps(savings_by_recommendations), status=200)


@ibm_resource_tracking.route('/clouds/<cloud_id>/recommendations_activity/<type_>', methods=['GET'])
@authenticate
def list_ibm_recommendations(cloud_id, type_, user):
    ibm_cloud = ibmdb.session.query(IBMCloud).filter_by(id=cloud_id, project_id=user["project_id"]).first()
    if not ibm_cloud:
        LOGGER.info(f"No IBM cloud found with ID: {cloud_id}")
        return Response("CLOUD_NOT_FOUND", status=404)

    if not (ibm_cloud.settings and ibm_cloud.settings.cost_optimization_enabled):
        error = f"IBM Cloud cost optimization disabled with Cloud ID {cloud_id}"
        LOGGER.info(error)
        return Response(json.dumps({"error": error}), status=200)

    if type_ not in ['actions-pending', 'actions-taken']:
        return Response(status=400)

    month = request.args.get('month')
    if month and month.lower() not in MONTHS_STR_TO_INT.keys():
        return Response(status=400)

    start_page = request.args.get('start', 1, type=int)
    limit_page = request.args.get('limit', PaginationConfig.DEFAULT_ITEMS_PER_PAGE, type=int)

    start, end = get_month_interval(month)
    if type_ == 'actions-pending':
        right_sizing_recomm = ibmdb.session.query(IBMRightSizingRecommendation).filter_by(cloud_id=cloud_id).filter(
            IBMRightSizingRecommendation.created_at < end).all()
        idle_resource_recomm = ibmdb.session.query(IBMIdleResource).filter_by(cloud_id=cloud_id).filter(
            IBMIdleResource.created_at < end).all()

        recommendations_list = right_sizing_recomm + idle_resource_recomm
        recommendations_items = recommendations_list[(start_page - 1) * limit_page:start_page * limit_page]
        recommendations = Pagination(None, start_page, limit_page, len(recommendations_list), recommendations_items)

        if not recommendations.items:
            return Response(status=204)

        recommendations_json = {
            "items": [recommendation.to_reporting_json() for recommendation in recommendations.items],
            "previous": recommendations.prev_num if recommendations.has_prev else None,
            "next": recommendations.next_num if recommendations.has_next else None,
            "pages": recommendations.pages
        }
        return Response(json.dumps(recommendations_json), status=200)

    else:
        applied_recommendations = ibmdb.session.query(IBMResourceTracking).filter_by(cloud_id=cloud_id).filter(
            IBMResourceTracking.action_taken_at >= start, IBMResourceTracking.action_taken_at < end).all()
        if not applied_recommendations:
            return Response(status=204)
        return Response(json.dumps([recommendation.to_reporting_json() for recommendation in applied_recommendations]),
                        status=200)
