"""
This file contains Client for private catalog related APIs
"""
import requests

from .paths import LIST_OBJECTS_PATH
from ..base_client import BaseClient
from ..consts import VPC_DEFAULT_PAGINATION_LIMIT
from ..urls import PRIVATE_CATALOG_URL_TEMPLATE


class PrivateCatalogsClient(BaseClient):
    """
    Client for private catalog related APIs
    """

    def __init__(self, cloud_id):
        super(PrivateCatalogsClient, self).__init__(cloud_id=cloud_id)

    def list_objects_across_catalogs(self, query, offset=0, collapse=None, digest=True,
                                     limit=VPC_DEFAULT_PAGINATION_LIMIT):
        """

        :param query:
        :param offset:
        :param collapse:
        :param digest:
        :param limit: Number of Resources Per Page
        :return:
        """
        params = {
            "query": query,
            "offset": offset,
            "collapse": collapse,
            "digest": digest,
            "limit": limit
        }

        request = requests.Request(
            "GET", PRIVATE_CATALOG_URL_TEMPLATE.format(path=LIST_OBJECTS_PATH), params=params
        )

        response = self._paginate_private_catalog_resource(request, "PRIVATE_CATALOG", "resources")

        return response["resources"]
