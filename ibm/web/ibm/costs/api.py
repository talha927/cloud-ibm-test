import json
import logging

from apiflask import APIBlueprint, doc, input, output
from flask import request

from ibm.auth import authenticate, Response
from ibm.common.consts import MONTHS_STR_TO_INT
from ibm.common.req_resp_schemas.schemas import IBMResourceQuerySchema
from ibm.common.utils import get_month_interval
from ibm.models import IBMCloud, IBMCost, IBMCostPerTag, IBMResourcesCost
from ibm.web import db as ibmdb
from ibm.web.common.utils import authorize_and_get_ibm_cloud
from .schemas import IBMCostSchema, IBMCostOutSchema

LOGGER = logging.getLogger(__name__)

ibm_costs = APIBlueprint('ibm_costs', __name__, tag="IBM Pricing")


@ibm_costs.route("/costs", methods=["GET"])
@authenticate
@input(IBMResourceQuerySchema, location='query')
@output(IBMCostOutSchema)
@doc(
    responses={
        204: "No records found"
    }
)
def get_ibm_cloud_account_cost_by_cloud_id(cloud_query_params, user):
    """
    Get an IBM Cloud Account with its costs incurred
    """
    cloud_id = cloud_query_params["cloud_id"]

    ibm_cloud = authorize_and_get_ibm_cloud(cloud_id=cloud_id, user=user)
    if not (ibm_cloud.settings and ibm_cloud.settings.cost_optimization_enabled):
        error = f"IBM Cloud cost optimization disabled with Cloud ID {cloud_id}"
        LOGGER.info(error)
        return Response(json.dumps({"error": error}), status=200)

    costs = ibmdb.session.query(IBMCost).filter_by(cloud_id=cloud_id).all()

    for cost in costs:
        return cost.to_json()


@ibm_costs.route('/clouds/costs', methods=['GET'])
@authenticate
@input(IBMCostSchema, location='query')
@output(IBMCostOutSchema)
def get_ibm_cloud_account_cost(cloud_query_params, user):
    """
    Get IBM Cloud Cost
    """
    cloud_id = cloud_query_params.get("cloud_id")
    cost_per_tags = cloud_query_params.get("cost_per_tags")
    if cloud_id:
        clouds = ibmdb.session.query(IBMCloud).filter_by(user_id=user["id"], id=cloud_id).all()
    else:
        clouds = ibmdb.session.query(IBMCloud).filter_by(user_id=user["id"]).all()
    if not clouds:
        LOGGER.info(f"No IBM Cloud accounts found for user with ID {user['id']}")
        return Response(status=204)

    if len(clouds) == 1 and not (clouds[0].settings and clouds[0].settings.cost_optimization_enabled):
        error = f"IBM Cloud cost optimization disabled with Cloud ID {cloud_id}"
        LOGGER.info(error)
        return Response(json.dumps({"error": error}), status=200)

    cost_summary_list = list()
    month = request.args.get('month')
    if month and month.lower() not in MONTHS_STR_TO_INT.keys():
        return Response(status=400)

    start, end = get_month_interval(month)
    for cloud in clouds:
        cost_obj = ibmdb.session.query(IBMCost).filter_by(cloud_id=cloud.id, billing_month=start).first()
        if not cost_obj:
            continue

        top_cost_per_tags = []
        if cost_per_tags:
            top_cost_per_tags = ibmdb.session.query(IBMCostPerTag).filter_by(date=start, cloud_id=cloud_id).\
                order_by(IBMCostPerTag.cost.desc()).limit(10).all()
            top_cost_per_tags = [top_cost_per_tag.to_reference_json() for top_cost_per_tag in top_cost_per_tags]

        resource_costs = ibmdb.session.query(IBMResourcesCost).filter_by(cloud_id=cloud.id, cost_id=cost_obj.id).all()
        ibm_cost = []
        for cost in resource_costs:
            ibm_cost.append({"name": cost.resource_name, "cost": cost.billable_cost})

        cost_summary_list.append({
            "cloud": {
                "id": cloud.id,
                "name": cloud.name
            },
            "details": top_cost_per_tags if cost_per_tags else ibm_cost,
            "total_cost": cost_obj.billable_cost
        })

    return Response(json.dumps(cost_summary_list), status=200, mimetype="application/json")
