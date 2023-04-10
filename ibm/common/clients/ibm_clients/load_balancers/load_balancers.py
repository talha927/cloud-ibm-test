import logging

from ibm_cloud_sdk_core import ApiException

from ..base_client import BaseClient
from ..consts import VPC_DEFAULT_PAGINATION_LIMIT
from ..exceptions import IBMInvalidRequestError

LOGGER = logging.getLogger(__name__)


class LoadBalancersClient(BaseClient):
    """
    Client for load balancer related APIs
    """

    def __init__(self, cloud_id, region):
        super(LoadBalancersClient, self).__init__(cloud_id=cloud_id, region=region)

    def list_load_balancer_profiles(self, limit=VPC_DEFAULT_PAGINATION_LIMIT):
        """
        :param limit: Number of Resources Per Page
        :return:
        """
        params = {
            "limit": limit
        }

        response = self.service.list_load_balancer_profiles(**params).get_result()
        return response.get("profiles", [])

    def get_load_balancer_profile(self, profile_name):
        """
        :param profile_name:
        :return:
        """

        return self.service.get_load_balancer_profile(name=profile_name).get_result()

    def get_load_balancer_statistics(self, load_balancer_id):
        """
        :param load_balancer_id:
        :return:
        """
        response = {}
        try:
            response = self.service.get_load_balancer_statistics(id=load_balancer_id).get_result()
        except ApiException as e:
            LOGGER.info(
                "List Load Balancer Statistics failed with status code " + str(e.code) + ": " + e.message)

        return response

    def create_load_balancer_listener_policy(self, load_balancer_id, listener_id, policy_json):
        """
        :param load_balancer_id:
        :param listener_id:
        :param policy_json:
        :return:
        """
        if not isinstance(policy_json, dict):
            raise IBMInvalidRequestError("Parameter 'policy_json' should be a dictionary")

        return self.service.create_load_balancer_listener_policy(**policy_json,
                                                                 load_balancer_id=load_balancer_id,
                                                                 listener_id=listener_id).get_result()

    def delete_load_balancer_listener_policy(self, load_balancer_id, listener_id, policy_id):
        """
        :param load_balancer_id:
        :param listener_id:
        :param policy_id:
        :return:
        """
        return self.service.delete_load_balancer_listener_policy(load_balancer_id=load_balancer_id,
                                                                 listener_id=listener_id, id=policy_id)

    def get_load_balancer_listener_policy(self, load_balancer_id, listener_id, policy_id):
        """
        @param load_balancer_id:
        @param listener_id:
        @param policy_id:
        @return:
        """
        return self.service.get_load_balancer_listener_policy(load_balancer_id=load_balancer_id,
                                                              listener_id=listener_id,
                                                              id=policy_id).get_result()

    def update_load_balancer_listener_policy(self, load_balancer_id, listener_id, policy_id, policy_json):
        """
        :param load_balancer_id:
        :param listener_id:
        :param policy_id:
        :param policy_json:
        :return:
        """
        if not isinstance(policy_json, dict):
            raise IBMInvalidRequestError("Parameter 'policy_json' should be a dictionary")

        response = {}
        try:
            response = self.service.update_load_balancer_listener_policy(
                load_balancer_id=load_balancer_id, listener_id=listener_id, id=policy_id,
                load_balancer_listener_policy_patch=policy_json).get_result()
        except ApiException as e:
            LOGGER.info(
                "Update Load Balancer Listener Policy failed with status code " + str(e.code) + ": " + e.message)

        return response

    def list_load_balancer_listener_policy_rules(self, load_balancer_id, listener_id, policy_id,
                                                 limit=VPC_DEFAULT_PAGINATION_LIMIT):
        """
        @param load_balancer_id:
        @param listener_id:
        @param policy_id:
        @param limit:
        @return:
        """
        params = {
            'load_balancer_id': load_balancer_id,
            'listener_id': listener_id,
            'policy_id': policy_id,
            "limit": limit
        }

        response = self.service.list_load_balancer_listener_policy_rules(**params).get_result()
        return response.get("rules", [])

    def create_load_balancer_listener_policy_rule(self, load_balancer_id, listener_id, policy_id, rule_json):
        """
        :param load_balancer_id:
        :param listener_id:
        :param policy_id:
        :param rule_json:
        :return:
        """

        if not isinstance(rule_json, dict):
            raise IBMInvalidRequestError("Parameter 'rule_json' should be a dictionary")

        return self.service.create_load_balancer_listener_policy_rule(**rule_json,
                                                                      load_balancer_id=load_balancer_id,
                                                                      listener_id=listener_id,
                                                                      policy_id=policy_id).get_result()

    def delete_load_balancer_listener_policy_rule(self, load_balancer_id, listener_id, policy_id, rule_id):
        """
        :param load_balancer_id:
        :param listener_id:
        :param policy_id:
        :param rule_id:
        :return:
        """
        return self.service.delete_load_balancer_listener_policy_rule(load_balancer_id=load_balancer_id,
                                                                      listener_id=listener_id,
                                                                      policy_id=policy_id,
                                                                      id=rule_id)

    def get_load_balancer_listener_policy_rule(self, load_balancer_id, listener_id, policy_id, rule_id):
        """
        @param load_balancer_id:
        @param listener_id:
        @param policy_id:
        @param rule_id:
        @return:
        """

        return self.service.get_load_balancer_listener_policy_rule(load_balancer_id=load_balancer_id,
                                                                   listener_id=listener_id,
                                                                   policy_id=policy_id,
                                                                   id=rule_id).get_result()

    def update_load_balancer_listener_policy_rule(self, load_balancer_id, listener_id, policy_id, rule_id,
                                                  rule_json):
        """
        :param load_balancer_id:
        :param listener_id:
        :param policy_id:
        :param rule_id:
        :param rule_json:
        :return:
        """
        if not isinstance(rule_json, dict):
            raise IBMInvalidRequestError("Parameter 'rule_json' should be a dictionary")

        response = {}
        try:
            response = self.service.update_load_balancer_listener_policy_rule(
                load_balancer_id=load_balancer_id, listener_id=listener_id, policy_id=policy_id, id=rule_id,
                load_balancer_listener_policy_rule_patch=rule_json).get_result()
        except ApiException as e:
            LOGGER.info(
                "Update Load Balancer Listener Policy RUle failed with status code " + str(e.code) + ": " + e.message)

        return response

    def list_load_balancers(self, limit=VPC_DEFAULT_PAGINATION_LIMIT):
        """
        :param limit:
        :return:
        """
        params = {
            "limit": limit
        }

        response = {}
        try:
            response = self.service.list_load_balancers(**params).get_result()
        except ApiException as e:
            LOGGER.info("List Load Balancer failed with status code " + str(e.code) + ": " + e.message)

        return response.get("load_balancers", [])

    def create_load_balancer(self, load_balancer_json):
        """
        :param load_balancer_json:
        :return:
        """
        if not isinstance(load_balancer_json, dict):
            raise IBMInvalidRequestError("Parameter 'load_balancer_json' should be a dictionary")

        return self.service.create_load_balancer(**load_balancer_json).get_result()

    def delete_load_balancer(self, load_balancer_id):
        """
        :param load_balancer_id:
        :return:
        """
        return self.service.delete_load_balancer(id=load_balancer_id)

    def get_load_balancer(self, load_balancer_id):
        """
        :param load_balancer_id:
        :return:
        """

        return self.service.get_load_balancer(id=load_balancer_id).get_result()

    def update_load_balancer(self, load_balancer_id, load_balancer_json):
        """
        :param load_balancer_id:
        :param load_balancer_json:
        :return:
        """
        if not isinstance(load_balancer_json, dict):
            raise IBMInvalidRequestError("Parameter 'ssh_key' should be a dictionary")

        response = {}
        try:
            response = self.service.update_load_balancer(id=load_balancer_id,
                                                         load_balancer_patch=load_balancer_json).get_result()
        except ApiException as e:
            LOGGER.info("Update Load Balancer failed with status code " + str(e.code) + ": " + e.message)

        return response

    def list_load_balancer_listeners(self, load_balancer_id):
        """
        :param load_balancer_id:
        :return:
        """
        response = self.service.list_load_balancer_listeners(load_balancer_id=load_balancer_id).get_result()
        return response.get("listeners", [])

    def create_load_balancer_listener(self, load_balancer_id, load_balancer_listener_json):
        """
        :param load_balancer_id:
        :param load_balancer_listener_json:
        :return:
        """
        if not isinstance(load_balancer_listener_json, dict):
            raise IBMInvalidRequestError("Parameter 'load_balancer_listener_json' should be a dictionary")

        return self.service.create_load_balancer_listener(load_balancer_id=load_balancer_id,
                                                          **load_balancer_listener_json).get_result()

    def delete_load_balancer_listener(self, load_balancer_id, listener_id):
        """
        :param load_balancer_id:
        :param listener_id:
        :return:
        """
        return self.service.delete_load_balancer_listener(load_balancer_id=load_balancer_id, id=listener_id)

    def get_load_balancer_listener(self, load_balancer_id, listener_id):
        """
        :param load_balancer_id:
        :param listener_id:
        :return:
        """
        return self.service.get_load_balancer_listener(load_balancer_id=load_balancer_id, id=listener_id).get_result()

    def update_load_balancer_listener(self, load_balancer_id, listener_id, load_balancer_listener_json):
        """
        :param load_balancer_id:
        :param listener_id:
        :param load_balancer_listener_json:
        :return:
        """
        if not isinstance(load_balancer_listener_json, dict):
            raise IBMInvalidRequestError("Parameter 'load_balancer_listener_json' should be a dictionary")

        response = {}
        try:
            response = self.service.update_load_balancer_listener(
                load_balancer_id=load_balancer_id, id=listener_id,
                load_balancer_listener_patch=load_balancer_listener_json).get_result()
        except ApiException as e:
            LOGGER.info("Update Load Balancer Listener failed with status code " + str(e.code) + ": " + e.message)

        return response

    def list_load_balancer_listener_policies(self, load_balancer_id, listener_id):
        """
        :param load_balancer_id:
        :param listener_id:
        :return:
        """
        response = {}
        try:
            response = self.service.list_load_balancer_listener_policies(load_balancer_id=load_balancer_id,
                                                                         listener_id=listener_id).get_result()
        except ApiException as e:
            LOGGER.info("List Listener Policies failed with status code " + str(e.code) + ": " + e.message)

        return response.get("listeners", [])

    def list_load_balancer_pools(self, load_balancer_id):
        """
        :param load_balancer_id:
        :return:
        """
        response = self.service.list_load_balancer_pools(load_balancer_id=load_balancer_id).get_result()
        return response.get("pools", [])

    def create_load_balancer_pool(self, load_balancer_id, load_balancer_pool_json):
        """
        :param load_balancer_id:
        :param load_balancer_pool_json:
        :return:
        """
        if not isinstance(load_balancer_pool_json, dict):
            raise IBMInvalidRequestError("Parameter 'load_balancer_pool_json' should be a dictionary")

        return self.service.create_load_balancer_pool(load_balancer_id=load_balancer_id,
                                                      **load_balancer_pool_json).get_result()

    def delete_load_balancer_pool(self, load_balancer_id, pool_id):
        """
        :param load_balancer_id:
        :param pool_id:
        :return:
        """
        return self.service.delete_load_balancer_pool(load_balancer_id=load_balancer_id, id=pool_id)

    def get_load_balancer_pool(self, load_balancer_id, pool_id):
        """
        :param load_balancer_id:
        :param pool_id:
        :return:
        """
        return self.service.get_load_balancer_pool(load_balancer_id=load_balancer_id, id=pool_id).get_result()

    def update_load_balancer_pool(self, load_balancer_id, pool_id, load_balancer_pool_json):
        """
        :param load_balancer_id:
        :param pool_id:
        :param load_balancer_pool_json:
        :return:
        """
        if not isinstance(load_balancer_pool_json, dict):
            raise IBMInvalidRequestError("Parameter 'load_balancer_listener_json' should be a dictionary")

        response = {}
        try:
            response = self.service.update_load_balancer_pool(load_balancer_id=load_balancer_id, id=pool_id,
                                                              load_balancer_pool_patch=load_balancer_pool_json
                                                              ).get_result()
        except ApiException as e:
            LOGGER.info("Update Load Balancer Pool failed with status code " + str(e.code) + ": " + e.message)

        return response

    def list_load_balancer_pool_members(self, load_balancer_id, pool_id):
        """
        :param load_balancer_id:
        :param pool_id:
        :return:
        """
        response = self.service.list_load_balancer_pool_members(load_balancer_id=load_balancer_id,
                                                                pool_id=pool_id).get_result()
        return response.get("members", [])

    def create_load_balancer_pool_member(self, load_balancer_id, pool_id, pool_member_json):
        """
        :param load_balancer_id:
        :param pool_id:
        :param pool_member_json:
        :return:
        """
        if not isinstance(pool_member_json, dict):
            raise IBMInvalidRequestError("Parameter 'pool_member_json' should be a dictionary")

        return self.service.create_load_balancer_pool_member(**pool_member_json,
                                                             load_balancer_id=load_balancer_id,
                                                             pool_id=pool_id).get_result()

    def delete_load_balancer_pool_member(self, load_balancer_id, pool_id, member_id):
        """
        :param load_balancer_id:
        :param pool_id:
        :param member_id:
        :return:
        """
        return self.service.delete_load_balancer_pool_member(load_balancer_id=load_balancer_id, pool_id=pool_id,
                                                             id=member_id)

    def replace_load_balancer_pool_members(self, load_balancer_id, pool_id, pool_member_list):
        """
         This API call documentation does not specify everything clearly
        :param load_balancer_id:
        :param pool_id:
        :param pool_member_list:
        :return:
        """
        if not isinstance(pool_member_list, list):
            raise IBMInvalidRequestError("Parameter 'pool_member_json' should be a list")

        response = {}
        try:
            response = self.service.replace_load_balancer_pool_members(load_balancer_id=load_balancer_id, id=pool_id,
                                                                       members=pool_member_list
                                                                       ).get_result()
        except ApiException as e:
            LOGGER.info("Replace Load Balancer Pool Member failed with status code " + str(e.code) + ": " + e.message)

        return response
