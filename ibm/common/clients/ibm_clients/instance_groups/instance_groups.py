import logging

from ibm_cloud_sdk_core import ApiException

from ..base_client import BaseClient
from ..consts import VPC_DEFAULT_PAGINATION_LIMIT
from ..exceptions import IBMInvalidRequestError

LOGGER = logging.getLogger(__name__)


class InstanceGroupsClient(BaseClient):
    """
    Client for Instance Group APIs
    """

    def __init__(self, cloud_id, region):
        super(InstanceGroupsClient, self).__init__(cloud_id=cloud_id, region=region)

    def list_instance_groups(self, limit=VPC_DEFAULT_PAGINATION_LIMIT):
        """
        List all Instance Groups
        :param limit: <int> Number of Resources Per Page
        :return:
        """
        params = {
            'limit': limit
        }

        response = {}
        try:
            response = self.service.list_instance_groups(**params).get_result()
        except ApiException as e:
            LOGGER.info("List Instance Groups failed with status code " + str(e.code) + ": " + e.message)

        return response.get("instance_groups", [])

    def create_instance_group(self, instance_group_json):
        """
        Create an Instance Group
        :param instance_group_json: <dict> JSON payload for the API
        :return:
        """
        if not isinstance(instance_group_json, dict):
            raise IBMInvalidRequestError("Parameter 'instance_group_json' should be a dictionary")

        return self.service.create_instance_group(**instance_group_json).get_result()

    def delete_instance_group(self, instance_group_resource_id):
        """
        Delete an Instance Group by ID
        :param instance_group_resource_id: <string> ID of Instance Group on IBM
        :return:
        """
        return self.service.delete_instance_group(id=instance_group_resource_id)

    def get_instance_group(self, instance_group_resource_id):
        """
        Get an Instance Group by ID
        :param instance_group_resource_id: <string> ID of Instance Group on IBM
        :return:
        """
        if not instance_group_resource_id:
            raise IBMInvalidRequestError("Parameter 'instance_group_resource_id' cannot be None.")

        return self.service.get_instance_group(id=instance_group_resource_id).get_result()

    def update_instance_group(self, instance_group_resource_id, updated_instance_group_json):
        """
        Update an Instance Group by ID
        :param instance_group_resource_id: <string> ID of Instance Group on IBM
        :param updated_instance_group_json: <dict> JSON payload for the API
        :return:
        """
        if not isinstance(updated_instance_group_json, dict):
            raise IBMInvalidRequestError("Parameter 'updated_instance_group_json' should be a dictionary")

        return self.service.update_instance_group(id=instance_group_resource_id,
                                                  instance_group_patch=updated_instance_group_json).get_result()

    def delete_instance_group_load_balancer(self, instance_group_id):
        """
        Delete an Instance Group Load Balancer by ID
        :param instance_group_id: <string> ID of Instance Group on IBM
        :return:
        """
        response = {}
        try:
            response = self.service.delete_instance_group_load_balancer(id=instance_group_id).get_result()
        except ApiException as e:
            LOGGER.info("Delete Instance Group Load Balancer failed with status code " + str(e.code) + ": " + e.message)

        return response

    def list_instance_group_managers(self, instance_group_id, limit=VPC_DEFAULT_PAGINATION_LIMIT):
        """
        List all Instance Group Managers
        :param instance_group_id: <string> ID of Instance Group on IBM
        :param limit: <int> Number of Resources Per Page
        :return:
        """
        params = {
            'limit': limit,
            "instance_group_id": instance_group_id
        }

        response = {}
        try:
            response = self.service.list_instance_group_managers(**params).get_result()
        except ApiException as e:
            LOGGER.info("List Instance Group Managers failed with status code " + str(e.code) + ": " + e.message)

        return response.get("managers", [])

    def create_instance_group_manager(self, instance_group_id, instance_group_manager_prototype):
        """
        Create an Instance Group Manager
        :param instance_group_id: <string> ID of Instance Group on IBM
        :param instance_group_manager_prototype: <dict> JSON payload for the API
        :return:
        """
        if not isinstance(instance_group_manager_prototype, dict):
            raise IBMInvalidRequestError("Parameter 'instance_group_manager_json' should be a dictionary")
        if not instance_group_id:
            raise IBMInvalidRequestError("Parameter 'instance_group_id' cannot be None.")

        return self.service.create_instance_group_manager(
            instance_group_manager_prototype=instance_group_manager_prototype,
            instance_group_id=instance_group_id).get_result()

    def delete_instance_group_manager(self, instance_group_id, instance_group_manager_id):
        """
        Delete an Instance Group Manager by ID
        :param instance_group_id: <string> ID of Instance Group on IBM
        :param instance_group_manager_id: <string> ID of Instance Group Manager on IBM
        :return:
        """
        return self.service.delete_instance_group_manager(instance_group_id=instance_group_id,
                                                          id=instance_group_manager_id)

    def get_instance_group_manager(self, instance_group_id, instance_group_manager_resource_id):
        """
        Get an Instance Group Manager by ID
        :param instance_group_id: <string> ID of the Instance Group on IBM
        :param instance_group_manager_resource_id: <string> ID of the Instance Group Manager on IBM
        :return:
        """
        return self.service.get_instance_group_manager(instance_group_id=instance_group_id,
                                                       id=instance_group_manager_resource_id).get_result()

    def update_instance_group_manager(self, instance_group_id, instance_group_manager_id, instance_group_manager_json):
        """
        Update an Instance Group Manager by ID
        :param instance_group_id: <string> ID of the Instance Group on IBM
        :param instance_group_manager_id: <string> ID of the Instance Group Manager on IBM
        :param instance_group_manager_json: <dict> JSON payload for the API
        :return:
        """
        if not isinstance(instance_group_manager_json, dict):
            raise IBMInvalidRequestError("Parameter 'instance_group_manager_json' should be a dictionary")

        return self.service.update_instance_group_manager(
            instance_group_id=instance_group_id, id=instance_group_manager_id,
            instance_group_manager_patch=instance_group_manager_json).get_result()

    def list_instance_group_manager_actions(
            self, instance_group_id, instance_group_manager_id, limit=VPC_DEFAULT_PAGINATION_LIMIT):
        """
        List all Instance Group Manager Actions
        :param instance_group_id: <string> ID of Instance Group on IBM
        :param instance_group_manager_id: <string> ID of Instance Group Manager on IBM
        :param limit: <int> Number of Resources Per Page
        :return:
        """
        params = {
            "limit": limit,
            "instance_group_id": instance_group_id,
            "instance_group_manager_id": instance_group_manager_id
        }

        if not (instance_group_id and instance_group_manager_id):
            raise IBMInvalidRequestError(
                "Parameter 'instance_group_id' and 'instance_group_manager_id' cannot be None.")

        response = {}
        try:
            response = self.service.list_instance_group_manager_actions(**params).get_result()
        except ApiException as e:
            LOGGER.info("List Instance Group Manager Actions failed with status code " + str(e.code) + ": " + e.message)

        return response.get("actions", [])

    def create_instance_group_manager_action(
            self, instance_group_id, instance_group_manager_id, instance_group_manager_action_prototype):
        """
        Create an Instance Group Manager Action
        :param instance_group_id: <string> ID of Instance Group on IBM
        :param instance_group_manager_id: <string> ID of Instance Group Manager on IBM
        :param instance_group_manager_action_prototype: <dict> JSON payload for the API
        :return:
        """
        if not isinstance(instance_group_manager_action_prototype, dict):
            raise IBMInvalidRequestError("Parameter 'instance_group_manager_action_json' should be a dictionary")

        return self.service.create_instance_group_manager_action(
            instance_group_manager_action_prototype=instance_group_manager_action_prototype,
            instance_group_id=instance_group_id,
            instance_group_manager_id=instance_group_manager_id).get_result()

    def delete_instance_group_manager_action(
            self, instance_group_id, instance_group_manager_id, instance_group_manager_action_id):
        """
        Delete an Instance Group Manager Action by ID
        :param instance_group_id: <string> ID of Instance Group on IBM
        :param instance_group_manager_id: <string> ID of Instance Group Manager on IBM
        :param instance_group_manager_action_id: <string> ID of Instance Group Manager Action on IBM
        :return:
        """
        return self.service.delete_instance_group_manager_action(
            instance_group_id=instance_group_id,
            instance_group_manager_id=instance_group_manager_id,
            id=instance_group_manager_action_id)

    def get_instance_group_manager_action(
            self, instance_group_id, instance_group_manager_id, instance_group_manager_action_id):
        """
        Get an Instance Group Manager action by ID
        :param instance_group_id: <string> ID of the Instance Group on IBM
        :param instance_group_manager_id: <string> ID of Instance Group Manager on IBM
        :param instance_group_manager_action_id: <string> ID of the Instance Group Manager Action on IBM
        :return:
        """
        return self.service.get_instance_group_manager_action(
            instance_group_id=instance_group_id,
            instance_group_manager_id=instance_group_manager_id,
            id=instance_group_manager_action_id).get_result()

    def update_instance_group_manager_action(self, instance_group_id, instance_group_manager_id,
                                             instance_group_manager_action_id, instance_group_manager_action_json):
        """
        Update an Instance Group Manager Action by ID
        :param instance_group_id: <string> ID of the Instance Group on IBM
        :param instance_group_manager_action_id: <string> ID of the Instance Group Manager on IBM
        :param instance_group_manager_id: <string> ID of Instance Group Manager Action on IBM
        :param instance_group_manager_action_json: <dict> JSON payload for the API
        :return:
        """
        if not isinstance(instance_group_manager_action_json, dict):
            raise IBMInvalidRequestError("Parameter 'instance_group_manager_action_json' should be a dictionary")

        response = {}
        try:
            response = self.service.update_instance_group_manager_action(
                instance_group_id=instance_group_id,
                instance_group_manager_id=instance_group_manager_id,
                id=instance_group_manager_action_id,
                instance_group_manager_action_patch=instance_group_manager_action_json).get_result()
        except ApiException as e:
            LOGGER.info(
                "Update Instance Group Manager Action failed with status code " + str(e.code) + ": " + e.message)

        return response

    def list_instance_group_manager_policies(
            self, instance_group_id, instance_group_manager_id, limit=VPC_DEFAULT_PAGINATION_LIMIT):
        """
        List all Instance Group Manager Policies
        :param instance_group_id: <string> ID of Instance Group on IBM
        :param instance_group_manager_id: <string> ID of Instance Group Manager on IBM
        :param limit: <int> Number of Resources Per Page
        :return:
        """
        params = {
            "instance_group_id": instance_group_id,
            "instance_group_manager_id": instance_group_manager_id,
            "limit": limit
        }

        response = {}
        try:
            response = self.service.list_instance_group_manager_policies(**params).get_result()
        except ApiException as e:
            LOGGER.info(
                "List Instance Group Manager Policies failed with status code " + str(e.code) + ": " + e.message)

        return response.get("policies", [])

    def create_instance_group_manager_policy(
            self, instance_group_id, instance_group_manager_id, instance_group_manager_policy_prototype):
        """
        Create an Instance Group Manager Policy
        :param instance_group_id: <string> ID of Instance Group on IBM
        :param instance_group_manager_id: <string> ID of Instance Group Manager on IBM
        :param instance_group_manager_policy_prototype: <dict> JSON payload for the API
        :return:
        """
        if not isinstance(instance_group_manager_policy_prototype, dict):
            raise IBMInvalidRequestError("Parameter 'instance_group_manager_policy_json' should be a dictionary")

        return self.service.create_instance_group_manager_policy(
            instance_group_manager_policy_prototype=instance_group_manager_policy_prototype,
            instance_group_id=instance_group_id,
            instance_group_manager_id=instance_group_manager_id).get_result()

    def delete_instance_group_manager_policy(
            self, instance_group_id, instance_group_manager_id, instance_group_manager_policy_id):
        """
        Delete an Instance Group Manager Policy by ID
        :param instance_group_id: <string> ID of Instance Group on IBM
        :param instance_group_manager_id: <string> ID of Instance Group Manager on IBM
        :param instance_group_manager_policy_id: <string> ID of Instance Group Manager policy on IBM
        :return:
        """
        return self.service.delete_instance_group_manager_policy(
            instance_group_id=instance_group_id,
            instance_group_manager_id=instance_group_manager_id,
            id=instance_group_manager_policy_id)

    def get_instance_group_manager_policy(
            self, instance_group_id, instance_group_manager_id, instance_group_manager_policy_id):
        """
        Get an Instance Group Manager policy by ID
        :param instance_group_id: <string> ID of the Instance Group on IBM
        :param instance_group_manager_id: <string> ID of Instance Group Manager on IBM
        :param instance_group_manager_policy_id: <string> ID of the Instance Group Manager Policy on IBM
        :return:
        """
        return self.service.get_instance_group_manager_policy(instance_group_id=instance_group_id,
                                                              instance_group_manager_id=instance_group_manager_id,
                                                              id=instance_group_manager_policy_id).get_result()

    def update_instance_group_manager_policy(self, instance_group_id, instance_group_manager_id,
                                             instance_group_manager_policy_id, instance_group_manager_policy_json):
        """
        Update an Instance Group Manager Policy by ID
        :param instance_group_id: <string> ID of the Instance Group on IBM
        :param instance_group_manager_id: <string> ID of Instance Group Manager on IBM
        :param instance_group_manager_policy_id: <string> ID of the Instance Group Manager Policy on IBM
        :param instance_group_manager_policy_json: <dict> JSON payload for the API
        :return:
        """

        if not isinstance(instance_group_manager_policy_json, dict):
            raise IBMInvalidRequestError("Parameter 'instance_group_manager_policy_json' should be a dictionary")

        response = {}
        try:
            response = self.service.update_instance_group_manager_policy(
                instance_group_id=instance_group_id,
                instance_group_manager_id=instance_group_manager_id,
                id=instance_group_manager_policy_id,
                instance_group_manager_policy_patch=instance_group_manager_policy_json).get_result()
        except ApiException as e:
            LOGGER.info(
                "Update Instance Group Manager Policy failed with status code " + str(e.code) + ": " + e.message)

        return response

    def delete_all_instance_group_memberships(self, instance_group_id):
        """
        Delete all Instance Group Memberships
        :param instance_group_id: <string> ID of Instance Group on IBM
        :return:
        """
        response = {}
        try:
            response = self.service.delete_instance_group_memberships(instance_group_id=instance_group_id)
        except ApiException as e:
            LOGGER.info(
                "Delete all Instance Group Manager Policies failed with status code " + str(e.code) + ": " + e.message)

        return response

    def list_instance_group_memberships(self, instance_group_id, limit=VPC_DEFAULT_PAGINATION_LIMIT):
        """
        List all Instance Group Memberships
        :param instance_group_id: <string> ID of Instance Group on IBM
        :param limit: <int> Number of Resources Per Page
        :return:
        """
        params = {
            "instance_group_id": instance_group_id,
            "limit": limit
        }
        response = self.service.list_instance_group_memberships(**params).get_result()
        return response.get("memberships", [])

    def delete_instance_group_membership(self, instance_group_id, instance_group_membership_id):
        """
        Delete an Instance Group Membership by ID
        :param instance_group_id: <string> ID of Instance Group on IBM
        :param instance_group_membership_id: <string> ID of Instance Group Membership on IBM
        :return:
        """
        return self.service.delete_instance_group_membership(instance_group_id=instance_group_id,
                                                             id=instance_group_membership_id)

    def get_instance_group_membership(self, instance_group_id, instance_group_membership_id):
        """
        Get an Instance Group Membership by ID
        :param instance_group_id: <string> ID of Instance Group on IBM
        :param instance_group_membership_id: <string> ID of Instance Group Membership on IBM
        :return:
        """
        return self.service.get_instance_group_membership(instance_group_id=instance_group_id,
                                                          id=instance_group_membership_id).get_result()

    def update_instance_group_membership(
            self, instance_group_id, instance_group_membership_id, instance_group_membership_json):
        """
        Update an Instance Group Membership by ID
        :param instance_group_id: <string> ID of Instance Group on IBM
        :param instance_group_membership_id: <string> ID of Instance Group Membership on IBM
        :param instance_group_membership_json: <dict> JSON payload for the API
        :return:
        """

        if not isinstance(instance_group_membership_json, dict):
            raise IBMInvalidRequestError("Parameter 'instance_group_membership_json' should be a dictionary")

        response = {}
        try:
            response = self.service.update_instance_group_membership(
                instance_group_id=instance_group_id,
                id=instance_group_membership_id,
                instance_group_membership_patch=instance_group_membership_json).get_result()
        except ApiException as e:
            LOGGER.info("Update Instance Group Membership failed with status code " + str(e.code) + ": " + e.message)

        return response
