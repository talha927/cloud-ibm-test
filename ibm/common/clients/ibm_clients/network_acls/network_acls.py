import logging

from ibm_cloud_sdk_core import ApiException

from ..base_client import BaseClient
from ..consts import VPC_DEFAULT_PAGINATION_LIMIT
from ..exceptions import IBMInvalidRequestError

LOGGER = logging.getLogger(__name__)


class NetworkACLsClient(BaseClient):
    """
    Client for network ACL related APIs
    """

    def __init__(self, cloud_id, region):
        super(NetworkACLsClient, self).__init__(cloud_id=cloud_id, region=region)

    def list_network_acls(self, resource_group_id=None, limit=VPC_DEFAULT_PAGINATION_LIMIT):
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
            response = self.service.list_network_acls(**params).get_result()
        except ApiException as e:
            LOGGER.info("List Network ACLs failed with status code " + str(e.code) + ": " + e.message)

        return response.get("network_acls", [])

    def create_network_acl(self, network_acl_json):
        """
        :param network_acl_json:
        :return:
        """
        if not isinstance(network_acl_json, dict):
            raise IBMInvalidRequestError("Parameter 'network_acl_json' should be a dictionary")

        return self.service.create_network_acl(network_acl_prototype=network_acl_json).get_result()

    def delete_network_acl(self, network_acl_id):
        """
        :param network_acl_id:
        :return:
        """
        return self.service.delete_network_acl(id=network_acl_id)

    def get_network_acl(self, network_acl_id):
        """
        :param network_acl_id:
        :return:
        """
        response = {}
        try:
            self.service.get_network_acl(id=network_acl_id).get_result()
        except ApiException as e:
            LOGGER.info("Get Network ACL failed with status code " + str(e.code) + ": " + e.message)

        return response

    def update_network_acl(self, network_acl_id, network_acl_name):
        """
        :param network_acl_id:
        :param network_acl_name:
        :return:
        """

        response = {}
        try:
            self.service.update_network_acl(id=network_acl_id, name=network_acl_name).get_result()
        except ApiException as e:
            LOGGER.info("Update Network ACL failed with status code " + str(e.code) + ": " + e.message)

        return response

    def list_network_acl_rules(self, network_acl_id, direction=None, limit=VPC_DEFAULT_PAGINATION_LIMIT):
        """
        :param network_acl_id:
        :param direction:
        :param limit: Number of Resources Per Page
        :return:
        """
        if direction and direction not in ["inbound", "outbound"]:
            raise IBMInvalidRequestError("Parameter 'direction' should be one of ['inbound', 'outbound']")

        params = {
            "network_acl_id": network_acl_id,
            "direction": direction,
            "limit": limit
        }

        response = {}
        try:
            response = self.service.list_network_acl_rules(**params).get_result()
        except ApiException as e:
            LOGGER.info("List Network ACL Rules failed with status code " + str(e.code) + ": " + e.message)

        return response.get("rules", [])

    def create_network_acl_rule(self, network_acl_id, network_acl_rule_json):
        """
        :param network_acl_id:
        :param network_acl_rule_json:
        :return:
        """
        if not isinstance(network_acl_rule_json, dict):
            raise IBMInvalidRequestError("Parameter 'network_acl_rule_json' should be a dictionary")

        return self.service.create_network_acl_rule(**network_acl_rule_json, network_acl_id=network_acl_id).get_result()

    def delete_network_acl_rule(self, network_acl_id, network_acl_rule_id):
        """
        :param network_acl_id:
        :param network_acl_rule_id:
        :return:
        """
        return self.service.delete_network_acl_rule(network_acl_id=network_acl_id, id=network_acl_rule_id)

    def get_network_acl_rule(self, network_acl_id, network_acl_rule_id):
        """
        :param network_acl_id:
        :param network_acl_rule_id:
        :return:
        """
        response = {}
        try:
            response = self.service.get_network_acl_rule(network_acl_id=network_acl_id,
                                                         id=network_acl_rule_id).get_result()
        except ApiException as e:
            LOGGER.info("Get Network ACL Rule failed with status code " + str(e.code) + ": " + e.message)

        return response

    def update_network_acl_rule(self, network_acl_id, network_acl_rule_id, network_acl_rule_json):
        """
        :param network_acl_id:
        :param network_acl_rule_id:
        :param network_acl_rule_json:
        :return:
        """
        if not isinstance(network_acl_rule_json, dict):
            raise IBMInvalidRequestError("Parameter 'network_acl_rule_json' should be a dictionary")

        response = {}
        try:
            response = self.service.update_network_acl_rule(network_acl_id=network_acl_id,
                                                            id=network_acl_rule_id,
                                                            network_acl_rule_patch=network_acl_rule_json).get_result()
        except ApiException as e:
            LOGGER.info("Update Network ACL Rule failed with status code " + str(e.code) + ": " + e.message)

        return response
