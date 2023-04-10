from datetime import datetime


def get_current_billing_month():
    """
    Get current billing month to calculate IBM cost e.g. 2022-03
    """
    today = datetime.today()
    current_billing_month = datetime(today.year, today.month, 1).strftime('%Y-%m')
    return current_billing_month


def get_latest_billing_month_from_db(cost):
    db_date = cost.billing_month
    date_in_month = datetime(db_date.year, db_date.month, 1).strftime('%Y-%m')
    return date_in_month
