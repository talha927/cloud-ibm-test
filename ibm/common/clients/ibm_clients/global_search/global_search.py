"""
This file contains Client for Global Seach related APIs
"""
import requests

from .paths import SEARCH_PATH
from ..base_client import BaseClient
from ..consts import VPC_DEFAULT_PAGINATION_LIMIT
from ..urls import GLOBAL_SEARCH_URL_TEMPLATE


class GlobalSearchClient(BaseClient):
    """
    Client for Global Seach related APIs
    """

    def __init__(self, cloud_id):
        super(GlobalSearchClient, self).__init__(cloud_id=cloud_id)

    def find_instance_of_resources(self, request_body, transaction_id=None, account_id=None, timeout=0, offset=0,
                                   sort=None, provider="ghost", limit=VPC_DEFAULT_PAGINATION_LIMIT):
        """
        :param request_body:
        :param transaction_id:
        :param account_id:
        :param timeout:
        :param offset:
        :param sort:
        :param provider:
        :param limit: Number of Resources Per Page
        :return:
        """
        assert provider in ["ghost", "ims"]
        assert (limit <= 1000 or limit >= 1), "limit values are accepted between 1 and 1000."
        assert (timeout <= 600000 or limit >= 0), "timeout values are accepted between 0 and 600000."
        params = {
            "transaction-id": transaction_id,
            "account_id": account_id,
            "timeout": timeout,
            "offset": offset,
            "sort": sort,
            "provider": provider,
            "limit": limit
        }

        request = requests.Request(
            "POST", GLOBAL_SEARCH_URL_TEMPLATE.format(path=SEARCH_PATH), params=params, json=request_body
        )

        response = self._paginate_global_search_resources(request, "GLOBAL_CATALOG", "items")

        return response["items"]
