"""
This file contains Client for IBM Cloud Account Details related APIs
"""
import requests

from .paths import GET_ACCOUNT_DETAILS_PATH
from ..base_client import BaseClient
from ..urls import ACCOUNT_DETAILS_URL_TEMPLATE


class CloudAccountDetailsClient(BaseClient):
    """
    Client for Dedicated Host APIs
    """

    def __init__(self, cloud_id):
        super(CloudAccountDetailsClient, self).__init__(cloud_id)

    def get_account_details(self, api_key_id):
        """
        Get IBM Account Details by API KEY ID
        :param api_key_id: <string> ID of API KEY ID on IBM
        :return:
        """
        request = requests.Request(
            "GET",
            ACCOUNT_DETAILS_URL_TEMPLATE.format(
                path=GET_ACCOUNT_DETAILS_PATH.format(api_key_id=api_key_id)
            )
        )

        response = self._execute_request(request, "ACCOUNT_DETAILS")

        return response
