import logging
from ibm_cloud_sdk_core import ApiException

from ..base_client import BaseClient
from ..consts import VPC_DEFAULT_PAGINATION_LIMIT
from ..exceptions import IBMInvalidRequestError

LOGGER = logging.getLogger(__name__)


class DedicatedHostsClient(BaseClient):
    """
    Client for Dedicated Host APIs
    """

    def __init__(self, cloud_id, region):
        super(DedicatedHostsClient, self).__init__(cloud_id=cloud_id, region=region)

    def list_dedicated_host_groups(self, resource_group_id=None, zone_name=None,
                                   limit=VPC_DEFAULT_PAGINATION_LIMIT):
        """
        List all Dedicated Host Groups
        :param limit: <int> Number of Resources Per Page
        :param resource_group_id:
        :param zone_name:
        :return:
        """
        params = {
            'limit': limit,
            'resource_group_id': resource_group_id,
            'zone_name': zone_name
        }

        response = {}
        try:
            response = self.service.list_dedicated_host_groups(**params).get_result()
        except ApiException as e:
            LOGGER.info("List Dedicated Host Groups failed with status code " + str(e.code) + ": " + e.message)

        return response.get("groups", [])

    def create_dedicated_host_group(self, dedicated_host_group_json):
        """
        Create a Dedicated Host Group
        :param dedicated_host_group_json: <dict> JSON payload for the API
        :return:
        """
        if not isinstance(dedicated_host_group_json, dict):
            raise IBMInvalidRequestError("Parameter 'dedicated_host_group_json' should be a dictionary")

        return self.service.create_dedicated_host_group(**dedicated_host_group_json).get_result()

    def delete_dedicated_host_group(self, dedicated_host_group_id):
        """
        Delete a Dedicated Host Group by ID
        :param dedicated_host_group_id: <string> ID of Dedicated Host Group on IBM
        :return:
        """
        return self.service.delete_dedicated_host_group(id=dedicated_host_group_id)

    def get_dedicated_host_group(self, dedicated_host_group_id):
        """
        Get a Dedicated Host by ID
        :param dedicated_host_group_id: <string> ID of Dedicated Host Group on IBM
        :return:
        """
        if not dedicated_host_group_id:
            raise IBMInvalidRequestError("Parameter 'dedicated_host_group_id' cannot be None.")

        response = {}
        try:
            response = self.service.get_dedicated_host_group(id=dedicated_host_group_id).get_result()
        except ApiException as e:
            LOGGER.info("Get Dedicated Host Group failed with status code " + str(e.code) + ": " + e.message)

        return response

    def update_dedicated_host_group(self, dedicated_host_group_id, updated_dh_group_json):
        """
        Update a dedicated host group by ID
        :param dedicated_host_group_id: <string> ID of Dedicated Host Group on IBM
        :param updated_dh_group_json: <dict> JSON payload for the API
        :return:
        """
        response = {}
        try:
            response = self.service.update_dedicated_host_group(
                id=dedicated_host_group_id, dedicated_host_group_patch=updated_dh_group_json).get_result()
        except ApiException as e:
            LOGGER.info("Update Dedicated Host Group failed with status code " + str(e.code) + ": " + e.message)

        return response

    def list_dedicated_host_profiles(self, limit=VPC_DEFAULT_PAGINATION_LIMIT):
        """
        List all Dedicated Host Profiles
        :param limit: <int> Number of Resources Per Page
        :return:
        """
        params = {
            'limit': limit
        }

        response = {}
        try:
            response = self.service.list_dedicated_host_profiles(**params).get_result()
        except ApiException as e:
            LOGGER.info("List Dedicated Host Profiles failed with status code " + str(e.code) + ": " + e.message)

        return response.get("profiles", [])

    def get_dedicated_host_profile(self, dedicated_host_profile_name):
        """
        Get a Dedicated Host profile by name
        :param dedicated_host_profile_name: <string> Name of the Dedicated Host on IBM
        :return:
        """

        response = {}
        try:
            response = self.service.get_dedicated_host_profile(name=dedicated_host_profile_name)
        except ApiException as e:
            LOGGER.info("Get Dedicated Host Group Profile failed with status code " + str(e.code) + ": " + e.message)

        return response

    def list_dedicated_hosts(self, dedicated_host_group_id=None, resource_group_id=None, zone_name=None,
                             name=None, limit=VPC_DEFAULT_PAGINATION_LIMIT):
        """
        List all Dedicated Hosts
        :param limit: <int> Number of Resources Per Page
        :param dedicated_host_group_id:
        :param resource_group_id
        :param zone_name
        :param name
        :return:
        """
        params = {
            'limit': limit,
            'dedicated_host_group_id': dedicated_host_group_id,
            'resource_group_id': resource_group_id,
            'zone_name': zone_name,
            'name': name
        }

        response = {}
        try:
            response = self.service.list_dedicated_hosts(**params).get_result()
        except ApiException as e:
            LOGGER.info("List Dedicated Hosts failed with status code " + str(e.code) + ": " + e.message)

        return response.get("dedicated_hosts", [])

    def create_dedicated_host(self, dedicated_host_json):
        """
        Create a Dedicated Host
        :param dedicated_host_json: <dict> JSON payload for the API
        :return:
        """
        if not isinstance(dedicated_host_json, dict):
            raise IBMInvalidRequestError("Parameter 'dedicated_host_json' should be a dictionary")

        return self.service.create_dedicated_host(dedicated_host_prototype=dedicated_host_json).get_result()

    def list_dedicated_host_disks(self, dedicated_host_id, limit=VPC_DEFAULT_PAGINATION_LIMIT):
        """
        List all disks of a Dedicated Host
        :param dedicated_host_id: <string> ID of the Dedicated Host on IBM
        :param limit: <int> Number of Resources Per Page
        :return:
        """
        params = {
            'limit': limit,
            "dedicated_host_id": dedicated_host_id
        }

        response = {}
        try:
            response = self.service.list_dedicated_host_disks(**params).get_result()
        except ApiException as e:
            LOGGER.info("List Dedicated Host Disks failed with status code " + str(e.code) + ": " + e.message)

        return response.get("disks", [])

    def get_dedicated_host_disk(self, dedicated_host_id, dedicated_host_disk_id):
        """
        Get a Dedicated Host Disk by ID
        :param dedicated_host_id: <string> ID of the Dedicated Host on IBM
        :param dedicated_host_disk_id: <string> ID of the Dedicated Host Disk on IBM
        :return:
        """
        response = {}
        try:
            response = self.service.get_dedicated_host_disk(dedicated_host_id=dedicated_host_id,
                                                            id=dedicated_host_disk_id).get_result()
        except ApiException as e:
            LOGGER.info("Get Dedicated Host Disk failed with status code " + str(e.code) + ": " + e.message)

        return response

    def update_dedicated_host_disk(self, dedicated_host_id, dedicated_host_disk_id, updated_dh_disk_json):
        """
        Update a Dedicated Host Disk by ID
        :param dedicated_host_id: <string> ID of the Dedicated Host on IBM
        :param dedicated_host_disk_id: <string> ID of the Dedicated Host on IBM
        :param updated_dh_disk_json: <dict> JSON payload for the API
        :return:
        """
        response = {}
        try:
            response = self.service.update_dedicated_host_disk(
                dedicated_host_id=dedicated_host_id,
                id=dedicated_host_disk_id,
                dedicated_host_disk_patch=updated_dh_disk_json).get_result()
        except ApiException as e:
            LOGGER.info("Update Dedicated Host Disk failed with status code " + str(e.code) + ": " + e.message)

        return response

    def delete_dedicated_host(self, dedicated_host_id):
        """
        Delete a Dedicated Host by ID
        :param dedicated_host_id: <string> ID of the Dedicated Host on IBM
        :return:
        """
        return self.service.delete_dedicated_host(id=dedicated_host_id)

    def get_dedicated_host(self, dedicated_host_id):
        """
        Get a Dedicated Host by ID
        :param dedicated_host_id: <string> ID of the Dedicated Host on IBM
        :return:
        """
        return self.service.get_dedicated_host(id=dedicated_host_id).get_result()

    def update_dedicated_host(self, dedicated_host_id, updated_dh_json):
        """
        Update a Dedicated Host by ID
        :param dedicated_host_id: <string> ID of the Dedicated Host on IBM
        :param updated_dh_json: <dict> JSON payload for the API
        :return:
        """
        response = {}
        try:
            response = self.service.update_dedicated_host(id=dedicated_host_id,
                                                          dedicated_host_patch=updated_dh_json).get_result()
        except ApiException as e:
            LOGGER.info("Update Dedicated Host failed with status code " + str(e.code) + ": " + e.message)

        return response
