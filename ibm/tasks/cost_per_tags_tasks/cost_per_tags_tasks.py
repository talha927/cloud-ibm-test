import logging

from sqlalchemy import func, and_
from sqlalchemy.orm import aliased

from ibm import get_db_session
from ibm.models import IBMCloud, IBMCost, IBMCostPerTag, IBMResourceInstancesCost, IBMTag

LOGGER = logging.getLogger(__name__)


def task_run_ibm_cost_per_tags_tracking(cloud_id=None):
    """
    This is a scheduled task which runs after 12 am , and retrieves the data from IBMTag and IBMResourceInstancesCost
    for IBMCostPerTag.
    """
    with get_db_session() as db_session:
        if cloud_id:
            ibm_clouds = db_session.query(IBMCloud).filter_by(id=cloud_id).all()
        else:
            ibm_clouds = db_session.query(IBMCloud).all()

        for ibm_cloud in ibm_clouds:
            cloud_settings = ibm_cloud.settings
            if not (cloud_settings and cloud_settings.cost_optimization_enabled):
                continue

            cloud_id = ibm_cloud.id
            costs = db_session.query(IBMCost).filter_by(cloud_id=cloud_id).order_by(IBMCost.billing_month.desc()).\
                limit(2).all()
            # Create alias for IBMTag
            ibm_tag_alias = aliased(IBMTag)

            for cost_obj in costs:
                # Join IBMTag and IBMResourceInstancesCost on the crn column and group the results by name
                query = (
                    db_session.query(ibm_tag_alias.name, func.sum(IBMResourceInstancesCost.cost))
                    .join(IBMResourceInstancesCost, and_(ibm_tag_alias.resource_crn == IBMResourceInstancesCost.crn,
                                                         IBMResourceInstancesCost.cost_id == cost_obj.id))
                    .group_by(ibm_tag_alias.name)
                    .all()
                )
                for name, cost in query:
                    cost = round(cost)
                    # Check if an IBMCostPerTag object with the same name and month already exists
                    month = cost_obj.billing_month
                    existing_cost_per_tag = db_session.query(IBMCostPerTag)\
                        .filter_by(name=name, cloud_id=cloud_id, date=month).first()

                    if existing_cost_per_tag:
                        # Update the cost of the existing object
                        existing_cost_per_tag.cost = cost

                    else:
                        cost_per_tag = IBMCostPerTag(name=name, cost=cost, date=month)
                        cost_per_tag.cloud_id = cloud_id
                        db_session.add(cost_per_tag)

                db_session.commit()
