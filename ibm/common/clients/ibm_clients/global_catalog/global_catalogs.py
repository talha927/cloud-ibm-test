import logging
from ibm_platform_services import GlobalCatalogV1

from ..base_client import BaseClient
from ..consts import VPC_DEFAULT_PAGINATION_LIMIT
from ..urls import GLOBAL_CATALOG_SERVICE_URL

LOGGER = logging.getLogger(__name__)


class GlobalCatalogsClient(BaseClient):
    """
    Client for Global Catalog related APIs
    """

    def __init__(self, cloud_id):
        super(GlobalCatalogsClient, self).__init__(cloud_id=cloud_id)
        self.service_global_catalog = GlobalCatalogV1(authenticator=self.authenticate_ibm_cloud_account())
        # TODO confirm this line
        self.service_global_catalog.DEFAULT_SERVICE_URL = GLOBAL_CATALOG_SERVICE_URL

    def return_parent_catalog_entries(self, account=None, include=None, keywords=None, sort_by=None, descending=None,
                                      languages=None, catalog=None, complete=None, offset=0,
                                      limit=VPC_DEFAULT_PAGINATION_LIMIT):
        """
        Returns parent catalog entries
        :param account: This changes the scope of the request regardless of the authorization header
        :param include: To include other properties, you must add this parameter. To include specific metadata fields,
         separate each field with a colon (:), for example GET /?include=metadata.ui:metadata.pricing.
        :param keywords: Searches the catalog entries for keywords
        :param sort_by: The field on which the output is sorted
        :param descending: Sets the sort order
        :param languages: Return the data strings in a specified language.
        :param catalog: Boolean. Checks to see if a catalog's object is visible
        :param complete: Boolean. Returns all available fields for all languages
        :param offset: Useful for pagination, specifies index (origin 0) of first item to return in response
        :param limit: Useful for pagination, specifies the maximum number of items to return in the response
        :return:
        """
        assert (limit <= 200), "Max limit is 200."
        params = {
            "account": account,
            "include": include,
            "q": keywords,
            "sort-by": sort_by,
            "descending": descending,
            "languages": languages,
            "catalog": catalog,
            "complete": complete,
            "_offset": offset,
            "_limit": limit
        }

        response = dict(self.service_global_catalog.list_catalog_entries(**params).get_result())
        return response.get("resources", [])
