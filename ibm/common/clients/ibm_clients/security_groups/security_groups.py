import logging

from ibm_cloud_sdk_core import ApiException

from ..base_client import BaseClient
from ..consts import VPC_DEFAULT_PAGINATION_LIMIT
from ..exceptions import IBMInvalidRequestError

LOGGER = logging.getLogger(__name__)


class SecurityGroupsClient(BaseClient):
    """
    Client for security group related APIs
    """

    def __init__(self, cloud_id, region):
        super(SecurityGroupsClient, self).__init__(cloud_id=cloud_id, region=region)

    def list_security_groups(self, resource_group_id=None, vpc_id=None, vpc_crn=None, vpc_name=None,
                             limit=VPC_DEFAULT_PAGINATION_LIMIT):
        """
        :param resource_group_id:
        :param vpc_id:
        :param vpc_crn:
        :param vpc_name:
        :param limit: Number of Resources Per Page
        :return:
        """
        params = {
            "resource_group_id": resource_group_id,
            "vpc_id": vpc_id,
            "vpc_crn": vpc_crn,
            "vpc_name": vpc_name,
            "limit": limit
        }

        response = {}
        try:
            response = self.service.list_security_groups(**params).get_result()
        except ApiException as e:
            LOGGER.info("List Security Groups failed with status code " + str(e.code) + ": " + e.message)

        return response.get("security_groups", [])

    def create_security_group(self, security_group_json):
        """
        :param security_group_json:
        :return:
        """
        # TODO set schema to validate payload
        if not isinstance(security_group_json, dict):
            raise IBMInvalidRequestError("Parameter 'security_group_json' should be a dictionary")

        return self.service.create_security_group(**security_group_json).get_result()

    def delete_security_group(self, security_group_id):
        """
        :param security_group_id:
        :return:
        """
        return self.service.delete_security_group(id=security_group_id).get_result()

    def get_security_group(self, security_group_id):
        """
        :param security_group_id:
        :return:
        """
        response = {}
        try:
            response = self.service.get_security_group(id=security_group_id).get_result()
        except ApiException as e:
            LOGGER.info("Get Security Group failed with status code " + str(e.code) + ": " + e.message)

        return response

    def update_security_group(self, security_group_id, security_group_json):
        """
        :param security_group_id:
        :param security_group_json:
        :return:
        """
        # TODO set schema to validate payload

        response = {}
        try:
            response = self.service.update_security_group(id=security_group_id,
                                                          security_group_patch=security_group_json).get_result()
        except ApiException as e:
            LOGGER.info("Update Security Group failed with status code " + str(e.code) + ": " + e.message)

        return response

    def list_security_group_rules(self, security_group_id):
        """
        :param security_group_id:
        :return:
        """

        response = {}
        try:
            response = self.service.list_security_group_rules(security_group_id=security_group_id).get_result()
        except ApiException as e:
            LOGGER.info("List Security Group Rules failed with status code " + str(e.code) + ": " + e.message)

        return response.get("rules", [])

    def create_security_group_rule(self, security_group_id, rule_json):
        """
        :param security_group_id:
        :param rule_json:
        :return:
        """

        # TODO set schema to validate payload
        return self.service.create_security_group_rule(security_group_id=security_group_id,
                                                       security_group_rule_prototype=rule_json).get_result()

    def delete_security_group_rules(self, security_group_id, rule_id):
        """
        :param security_group_id:
        :param rule_id:
        :return:
        """
        return self.service.delete_security_group_rule(security_group_id=security_group_id, id=rule_id)

    def get_security_group_rule(self, security_group_id, rule_id):
        """
        :param security_group_id:
        :param rule_id:
        :return:
        """
        response = {}
        try:
            response = self.service.get_security_group_rule(security_group_id=security_group_id,
                                                            id=rule_id).get_result()
        except ApiException as e:
            LOGGER.info("Get Security Group Rule failed with status code " + str(e.code) + ": " + e.message)

        return response

    def update_security_group_rule(self, security_group_id, rule_id, sec_group_rule_json):
        """
        :param security_group_id:
        :param rule_id:
        :param sec_group_rule_json:
        :return:
        """
        # TODO set schema to validate payload
        response = {}
        try:
            response = self.service.update_security_group_rule(
                security_group_id=security_group_id, id=rule_id,
                security_group_rule_patch=sec_group_rule_json).get_result()
        except ApiException as e:
            LOGGER.info("Update Security Group Rule failed with status code " + str(e.code) + ": " + e.message)

        return response

    def list_security_group_targets(self, security_group_id, limit=VPC_DEFAULT_PAGINATION_LIMIT):
        """
        :param security_group_id:
        :param limit: Number of Resources Per Page
        :return:
        """
        params = {
            "limit": limit,
            "security_group_id": security_group_id
        }

        response = {}
        try:
            response = self.service.list_security_group_targets(**params).get_result()
        except ApiException as e:
            LOGGER.info("List Security Group Targets failed with status code " + str(e.code) + ": " + e.message)

        return response.get("targets", [])

    def delete_security_group_target(self, security_group_id, target_id):
        """
        :param security_group_id:
        :param target_id:
        :return:
        """
        return self.service.delete_security_group_target_binding(security_group_id=security_group_id, id=target_id)

    def get_security_group_target(self, security_group_id, target_id):
        """
        :param security_group_id:
        :param target_id:
        :return:
        """
        response = {}
        try:
            response = self.service.get_security_group_target(security_group_id=security_group_id,
                                                              id=target_id).get_result()
        except ApiException as e:
            LOGGER.info("Get Security Group Target failed with status code " + str(e.code) + ": " + e.message)

        return response

    def add_security_group_target(self, security_group_id, target_id):
        """
        :param security_group_id:
        :param target_id:
        :return:
        """
        # TODO set schema to validate payload
        return self.service.create_security_group_target_binding(security_group_id=security_group_id,
                                                                 id=target_id).get_result()
