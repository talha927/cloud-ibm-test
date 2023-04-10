import logging

from ibm_cloud_sdk_core import ApiException

from ..base_client import BaseClient
from ..consts import VPC_DEFAULT_PAGINATION_LIMIT
from ..exceptions import IBMInvalidRequestError

LOGGER = logging.getLogger(__name__)


class PublicGatewaysClient(BaseClient):
    """
    Client for public gateways related APIs
    """

    def __init__(self, cloud_id, region):
        super(PublicGatewaysClient, self).__init__(cloud_id=cloud_id, region=region)

    def list_public_gateways(self, resource_group_id=None, limit=VPC_DEFAULT_PAGINATION_LIMIT):
        """
        :param resource_group_id:
        :param limit: Number of Resources Per Page
        :return:
        """
        params = {
            "resource_group_id": resource_group_id,
            "limit": limit
        }

        response = {}
        try:
            response = self.service.list_public_gateways(**params).get_result()
        except ApiException as e:
            LOGGER.info("List Public Gateways failed with status code " + str(e.code) + ": " + e.message)

        return response.get("public_gateways", [])

    def create_public_gateway(self, public_gateway_json):
        """
        :param public_gateway_json:
        :return:
        """

        if not isinstance(public_gateway_json, dict):
            raise IBMInvalidRequestError("Parameter 'public_gateway_json' should be a dictionary")

        # TODO: Create schema for input and validate it

        return self.service.create_public_gateway(**public_gateway_json).get_result()

    def delete_public_gateway(self, public_gateway_id):
        """
        :param public_gateway_id:
        :return:
        """
        return self.service.delete_public_gateway(id=public_gateway_id)

    def get_public_gateway(self, public_gateway_id):
        """
        :param public_gateway_id:
        :return:
        """
        return self.service.get_public_gateway(id=public_gateway_id).get_result()

    def update_public_gateway(self, public_gateway_id, public_gateway_json):
        """
        :param public_gateway_id:
        :param public_gateway_json:
        :return:
        """
        if not isinstance(public_gateway_json, dict):
            raise IBMInvalidRequestError("Parameter 'public_gateway_json' should be a dictionary")

        # TODO: Create schema for input and validate it

        response = {}
        try:
            response = self.service.update_public_gateway(id=public_gateway_id,
                                                          placement_group_patch=public_gateway_json).get_result()
        except ApiException as e:
            LOGGER.info("Update Public Gateway failed with status code " + str(e.code) + ": " + e.message)

        return response
