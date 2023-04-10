import json
import logging

from flask import Blueprint, request, Response

from ibm.web import db as ibmdb
from ibm.auth import authenticate
from ibm.models import IBMCloud, IBMRightSizingRecommendation

LOGGER = logging.getLogger(__name__)

ibm_right_sizing_recommendation = Blueprint('ibm_right_sizing_recommendation', __name__)


@ibm_right_sizing_recommendation.route('/clouds/<cloud_id>/right-sizing-recommendations', methods=['GET'])
@authenticate
def list_ibm_right_sizing_recommendations(cloud_id, user):
    """
    List AWS Right Sizing Recommendations  with  cloud ID
    :param user: object of the user initiating the request
    :param cloud_id: cloud_id for AWSCloud
    :return: Response object from flask package cloud_id
    """
    ibm_cloud = ibmdb.session.query(IBMCloud).filter_by(id=cloud_id, project_id=user["project_id"]).first()
    if not ibm_cloud:
        LOGGER.info(f"No IBM cloud found with ID: {cloud_id}")
        return Response("CLOUD_NOT_FOUND", status=404)

    if ibm_cloud.settings:
        if not ibm_cloud.settings.cost_optimization_enabled:
            error = f"IBM Cloud cost optimization disabled with Cloud ID {cloud_id}"
            LOGGER.info(error)
            return Response(json.dumps({"error": error}), status=200)

    right_sizing_recommendation = IBMRightSizingRecommendation.search_and_filter(request.args, cloud_id)
    if not right_sizing_recommendation.items:
        LOGGER.info(f"No IBM Right Sizing Recommendation for cloud with ID: {cloud_id}")
        return Response("RIGHT_SIZING_RECOMMENDATION_WITH_CLOUD_ID_NOT_FOUND", status=204)

    right_sizing_recommendation_json = {
        "items": [recommendation.to_json() for recommendation in right_sizing_recommendation.items],
        "previous": right_sizing_recommendation.prev_num if right_sizing_recommendation.has_prev else None,
        "next": right_sizing_recommendation.next_num if right_sizing_recommendation.has_next else None,
        "pages": right_sizing_recommendation.pages
    }
    return Response(json.dumps(right_sizing_recommendation_json), status=200, mimetype="application/json")
