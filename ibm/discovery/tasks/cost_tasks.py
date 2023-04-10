import logging
from calendar import monthrange
from datetime import datetime, date, timedelta

from sqlalchemy import func

from ibm.discovery import get_db_session
from ibm.models import IBMCloud, IBMCost, IBMResourceInstancesCost, IBMResourceInstancesDailyCost
from ibm.tasks.cost_per_tags_tasks.cost_per_tags_tasks import task_run_ibm_cost_per_tags_tracking

LOGGER = logging.getLogger(__name__)


def update_cost(cloud_id, m_ibm_costs):
    """
    Parse IBM cost related data, and store it into DB accordingly
    :param cloud_id:  database id of Cloud table entry
    :param m_ibm_costs:
        [
            {
                "time": "2022-12-08 05:26:38.374680"
                "response": [{
                    "summary": {
                        "month": "2022-12",.....
                        },
                        "resources": [{
                            "month": "2022-12",
                            "usage": [{
                                ......
                                }],
    """
    start_time = datetime.utcnow()

    m_costs_response = []
    m_cost_time = None
    for m_ibm_costs_ in m_ibm_costs:
        m_costs_response = m_ibm_costs_.get('response', [])
        m_cost_time = m_ibm_costs_.get('last_synced_at')
        if m_costs_response:
            break

    for m_cost_response in m_costs_response:
        cost = IBMCost.from_ibm_json_body(json_body=m_cost_response['summary'], cloud_id=cloud_id)
        billing_month = cost.billing_month

        cost_obj = None
        with get_db_session() as db_session:
            cloud = db_session.query(IBMCloud).get(cloud_id)
            assert cloud

            db_cost = db_session.query(IBMCost).filter_by(cloud_id=cloud_id, billing_month=billing_month).first()
            if db_cost:
                db_cost.update_from_obj(cost)
                cost_obj = db_cost
            else:
                cost.ibm_cloud = cloud
                cost_obj = cost
            update_individual_cost(cloud_id=cloud_id, cost_id=cost_obj.id,
                                   m_resources_cost=m_cost_response['resources'],
                                   m_ibm_cost_time=m_cost_time, db_session=db_session)
            db_session.commit()

    LOGGER.info(f"** IBMCost synced in: {(datetime.utcnow() - start_time).total_seconds()}")
    update_idle_resource_cost(cloud_id=cloud_id)
    task_run_ibm_cost_per_tags_tracking(cloud_id=cloud_id)


def update_individual_cost(cloud_id, cost_id, m_resources_cost, m_ibm_cost_time, db_session):
    """
    Update cost of Resource Instances
    :param cloud_id: database id of entry of table "Cloud"
    :param cost_id: database id of entry of table "IBMCost"
    :param m_resources_cost: [{
                            "month": "2022-12",
                            "usage": [{
                                "cost": 8.690458064516127,
                                "unit": "GIGABYTE_MONTH_DISK",
                                "price": [{
                                "price": 0.58,
                                "tier_model": "Granular Tier",
                                "unitQuantity": "1",
                                "quantity_tier": "1"
                                }],
                                "metric": "GIGABYTE_MONTHS_DISK",
                                "quantity": 16.64838709677419,
                                }, ......  #more metrics
                                "resource_id": ""
                                "resource_instance_id": "crn of resource"
                                }]
    :param m_ibm_cost_time: time in format "2022-12-08 05:26:38.374680"
    :param db_session: database session

    """
    for m_resource_cost in m_resources_cost:
        crn = m_resource_cost['resource_instance_id']
        resource_id = m_resource_cost['resource_id']  # Resource ID is service name
        m_month = m_resource_cost['month']
        m_month_datetime = datetime(int(m_month.split('-')[0]), int(m_month.split('-')[1]), 1)

        cost_mtd = 0.0
        for usage_and_cost in m_resource_cost['usage']:
            cost_mtd = round(sum([cost_mtd, float(usage_and_cost['cost'])]))

        esitmated_cost = None
        if resource_id == 'is.floating-ip':
            esitmated_cost = cost_mtd
        else:
            time_now = datetime.now()
            days_passed = time_now.day
            current_date = date.today()
            days_in_month = monthrange(current_date.year, current_date.month)[1]
            utcnow = datetime.utcnow()
            if f'{utcnow.year}-{utcnow.month}' == m_month:
                esitmated_cost = round((cost_mtd / days_passed) * days_in_month)
            else:
                esitmated_cost = round(cost_mtd)

        resource_instance_cost = IBMResourceInstancesCost(resource_id=resource_id, cost=cost_mtd,
                                                          estimated_cost=esitmated_cost, crn=crn)
        db_resource_instance_cost = db_session.query(IBMResourceInstancesCost).filter_by(
            resource_id=resource_id, cloud_id=cloud_id, cost_id=cost_id, crn=crn).first()

        # update Daily Cost
        db_daily_cost_obj = db_session.query(IBMResourceInstancesDailyCost).filter_by(cloud_id=cloud_id,
                                                                                      cost_id=cost_id,
                                                                                      resource_id=resource_id,
                                                                                      crn=crn) \
            .order_by(IBMResourceInstancesDailyCost.created_at.desc()).first()
        db_daily_mtd_cost = db_session.query(func.sum(IBMResourceInstancesDailyCost.daily_cost).label('cost')).\
            filter_by(cloud_id=cloud_id, cost_id=cost_id, resource_id=resource_id, crn=crn).first().cost or 0.0
        current_time_datetime = datetime.strptime(m_ibm_cost_time, "%Y-%m-%d %H:%M:%S")
        if db_daily_cost_obj:
            created_time = str(db_daily_cost_obj.created_at).split('.')[0]
            created_datetime = datetime.strptime(str(created_time), "%Y-%m-%d %H:%M:%S")
            hour_lapsed = (current_time_datetime - created_datetime).total_seconds() / 3600
            if hour_lapsed > 24:
                date_ = db_daily_cost_obj.date + timedelta(days=1)
                if int(date_.month) == int(m_month.split('-')[1]):
                    daily_cost = \
                        IBMResourceInstancesDailyCost(resource_id=resource_id, crn=crn, date=date_,
                                                      daily_cost=round(abs(cost_mtd - db_daily_mtd_cost)))
                    daily_cost.cost_id = cost_id
                    daily_cost.cloud_id = cloud_id
                    db_session.add(daily_cost)
        else:
            current_time_datetime_est = current_time_datetime - timedelta(hours=1)  # Subtracted 1 hour to cater delays
            date_ = None
            if current_time_datetime_est.date().day == 1 and \
                    current_time_datetime_est.date().month == m_month_datetime.month:
                date_ = datetime(m_month_datetime.year, m_month_datetime.month, 1).date()
            else:
                if current_time_datetime_est.date().month == m_month_datetime.month:
                    date_ = current_time_datetime.date()
            if date_:
                daily_cost = IBMResourceInstancesDailyCost(resource_id=resource_id, daily_cost=cost_mtd, crn=crn,
                                                           date=date_)
                daily_cost.cost_id = cost_id
                daily_cost.cloud_id = cloud_id
                db_session.add(daily_cost)

        if db_resource_instance_cost:
            db_resource_instance_cost.update_from_obj(resource_instance_cost)
        else:
            resource_instance_cost.cloud_id = cloud_id
            resource_instance_cost.cost_id = cost_id
            db_session.add(resource_instance_cost)
        db_session.commit()


def update_idle_resource_cost(cloud_id):
    from ibm.models import IBMIdleResource

    with get_db_session() as db_session:
        idle_resources = db_session.query(IBMIdleResource).filter_by(cloud_id=cloud_id).all()
        for idle_resource in idle_resources:
            resource_json = idle_resource.resource_json
            crn = resource_json.get('crn')
            if crn:
                cost = db_session.query(IBMResourceInstancesCost).filter_by(cloud_id=cloud_id, crn=crn).first()
                if cost:
                    idle_resource.estimated_savings = round(cost.estimated_cost)
        db_session.commit()
