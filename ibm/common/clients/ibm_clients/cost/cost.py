import datetime

from ibm_cloud_sdk_core.authenticators import IAMAuthenticator
from ibm_platform_services import UsageReportsV4

from ibm.discovery.common.consts import TIME_FORMAT
from ..base_client import BaseClient


class CostClient(BaseClient):
    """
    Client for Resource Group related APIs
    """

    def __init__(self, cloud_id):
        super(CostClient, self).__init__(cloud_id)

    def list_cost_and_usages(self, ibm_api_key, ibm_account_id, billing_month):

        """
        This method make an API call to IBM, to retrieve cost and usage values according to dimension values
        provided as a list
        """
        authenticator = IAMAuthenticator(apikey=ibm_api_key)
        usage_reports_service = UsageReportsV4(authenticator=authenticator)
        response_dict = dict()
        response_dict['summary'] = usage_reports_service.get_account_summary(
            account_id=ibm_account_id, billingmonth=billing_month).get_result()
        offset = None
        response_dict['resources'] = list()

        while True:
            resource_usage = usage_reports_service.get_resource_usage_account(account_id=ibm_account_id,
                                                                              billingmonth=billing_month,
                                                                              limit=200,
                                                                              start=offset).get_result()

            if not isinstance(resource_usage, dict):
                continue
            if resource_usage and resource_usage.get('resources'):
                response_dict['resources'].extend(resource_usage['resources'])
            if resource_usage and resource_usage.get('next') and resource_usage['next'].get('offset'):
                offset = resource_usage['next']['offset']
            else:
                break

        response_dict['last_synced_at'] = datetime.datetime.utcnow().replace(second=0).strftime(TIME_FORMAT)

        return response_dict
