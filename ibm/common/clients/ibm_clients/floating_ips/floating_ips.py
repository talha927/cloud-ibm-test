import logging

from ibm_cloud_sdk_core import ApiException

from ..base_client import BaseClient
from ..consts import VPC_DEFAULT_PAGINATION_LIMIT
from ..exceptions import IBMInvalidRequestError

LOGGER = logging.getLogger(__name__)


class FloatingIPsClient(BaseClient):
    """
    Client for floating ip related APIs
    """

    def __init__(self, cloud_id, region):
        super(FloatingIPsClient, self).__init__(cloud_id=cloud_id, region=region)

    def list_floating_ips(self, resource_group_id=None, limit=VPC_DEFAULT_PAGINATION_LIMIT):
        """
        :param resource_group_id:
        :param limit: Number of Resources Per Page
        :return:
        """
        params = {
            "resource_group_id": resource_group_id,
            'limit': limit
        }

        response = {}
        try:
            response = self.service.list_floating_ips(**params).get_result()
        except ApiException as e:
            LOGGER.info("List Floating IPs failed with status code " + str(e.code) + ": " + e.message)

        return response.get("floating_ips", [])

    def reserve_floating_ip(self, floating_ip_json):
        """
        :param floating_ip_json:
        :return:
        """
        if not isinstance(floating_ip_json, dict):
            raise IBMInvalidRequestError("Parameter 'floating_ip_json' should be a dictionary")

        # TODO: Create schema for input and validate it

        return self.service.create_floating_ip(floating_ip_prototype=floating_ip_json).get_result()

    def release_floating_ip(self, floating_ip_id):
        """
        :param floating_ip_id:
        :return:
        """

        return self.service.delete_floating_ip(id=floating_ip_id)

    def get_floating_ip(self, floating_ip_id):
        """
        :param floating_ip_id:
        :return:
        """

        return self.service.get_floating_ip(id=floating_ip_id).get_result()

    def update_floating_ip(self, floating_ip_id, floating_ip_json):
        """
        :param floating_ip_id:
        :param floating_ip_json
        :return:
        """
        if not isinstance(floating_ip_json, dict):
            raise IBMInvalidRequestError("Parameter 'floating_ip_json' should be a dictionary")

        # TODO: Create schema for input and validate it

        response = {}
        try:
            response = self.service.update_floating_ip(id=floating_ip_id,
                                                       floating_ip_patch=floating_ip_json).get_result()
        except ApiException as e:
            LOGGER.info("Update Floating IPs failed with status code " + str(e.code) + ": " + e.message)

        return response
