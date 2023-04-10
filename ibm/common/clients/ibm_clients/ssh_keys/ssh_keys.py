import logging

from ibm_cloud_sdk_core import ApiException

from ..base_client import BaseClient
from ..consts import VPC_DEFAULT_PAGINATION_LIMIT
from ..exceptions import IBMInvalidRequestError

LOGGER = logging.getLogger(__name__)


class SSHKeysClient(BaseClient):
    """
    Client for ssh keys related APIs
    """

    def __init__(self, cloud_id, region):
        super(SSHKeysClient, self).__init__(cloud_id=cloud_id, region=region)

    def list_ssh_keys(self, limit=VPC_DEFAULT_PAGINATION_LIMIT):
        """
        :param limit:
        :return:
        """

        response = {}
        try:
            response = self.service.list_keys(limit=limit).get_result()
        except ApiException as e:
            LOGGER.info("List SSH Keys failed with status code " + str(e.code) + ": " + e.message)

        return response.get("keys", [])

    def create_ssh_key(self, key_json):
        """
        :param key_json:
        :return:
        """
        if not isinstance(key_json, dict):
            raise IBMInvalidRequestError("Parameter 'key_json' should be a dictionary")

        return self.service.create_key(**key_json).get_result()

    def delete_ssh_key(self, key_id):
        """
        :param key_id:
        :return:
        """
        return self.service.delete_key(id=key_id)

    def get_ssh_key(self, key_id):
        """
        :param key_id:
        :return:
        """
        response = {}
        try:
            response = self.service.get_key(id=key_id).get_result()
        except ApiException as e:
            LOGGER.info("Get SSH Key failed with status code " + str(e.code) + ": " + e.message)

        return response

    def update_ssh_key(self, key_id, key_json):
        """
        :param key_id:
        :param key_json:
        :return:
        """
        if not isinstance(key_json, dict):
            raise IBMInvalidRequestError("Parameter 'key_json' should be a dictionary")

        response = {}
        try:
            response = self.service.update_key(id=key_id).get_result()
        except ApiException as e:
            LOGGER.info("Update SSH Key failed with status code " + str(e.code) + ": " + e.message)

        return response
