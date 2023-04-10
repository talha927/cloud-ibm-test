import logging

from ibm_cloud_sdk_core import ApiException

from ..base_client import BaseClient

LOGGER = logging.getLogger(__name__)


class GeographyClient(BaseClient):
    """
    Client for geography related APIs
    """

    def __init__(self, cloud_id):
        super(GeographyClient, self).__init__(cloud_id=cloud_id)

    def list_regions(self):
        """
        :return:
        """
        # TODO: Write a robust method for default region (fallback region in case one is not available)
        response = self.service.list_regions().get_result()
        return response.get("regions", [])

    def get_region(self, region):
        """
        :param region:
        :return:
        """

        response = {}
        try:
            response = self.service.get_region(name=region).get_result()
        except ApiException as e:
            LOGGER.info("Get Region failed with status code " + str(e.code) + ": " + e.message)

        return response

    def list_zones_in_region(self, region):
        """
        :param region:
        :return:
        """

        response = self.service.list_region_zones(region_name=region).get_result()
        return response.get("zones", [])

    def get_zone(self, region, zone):
        """
        :param region:
        :param zone:
        :return:
        """

        response = {}
        try:
            response = self.service.get_region_zone(region_name=region, name=zone).get_result()
        except ApiException as e:
            LOGGER.info("Get Zone failed with status code " + str(e.code) + ": " + e.message)

        return response
