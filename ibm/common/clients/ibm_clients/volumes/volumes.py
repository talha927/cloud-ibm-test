import logging

from ibm_cloud_sdk_core import ApiException

from ..base_client import BaseClient
from ..consts import VPC_DEFAULT_PAGINATION_LIMIT
from ..exceptions import IBMInvalidRequestError

LOGGER = logging.getLogger(__name__)


class VolumesClient(BaseClient):
    """
    Client for volumes related APIs
    """

    def __init__(self, cloud_id, region):
        super(VolumesClient, self).__init__(cloud_id=cloud_id, region=region)

    def list_volume_profiles(self, limit=VPC_DEFAULT_PAGINATION_LIMIT):
        """
        :param limit: Number of Resources Per Page
        :return:
        """
        params = {
            "limit": limit
        }

        response = {}
        try:
            response = self.service.list_volume_profiles(**params).get_result()
        except ApiException as e:
            LOGGER.info("List Volume Profiles failed with status code " + str(e.code) + ": " + e.message)

        return response.get("profiles", [])

    def get_volume_profile(self, volume_profile_name):
        """
        :param volume_profile_name:
        :return:
        """
        response = {}
        try:
            response = self.service.get_volume_profile(name=volume_profile_name).get_result()
        except ApiException as e:
            LOGGER.info("Get Volume Profile failed with status code " + str(e.code) + ": " + e.message)

        return response

    def list_volumes(self, name=None, zone=None, limit=VPC_DEFAULT_PAGINATION_LIMIT):
        """
        :param name:
        :param zone:
        :param limit: Number of Resources Per Page
        :return:
        """
        params = {
            "name": name,
            "zone_name": zone,
            "limit": limit
        }

        response = {}
        try:
            response = self.service.list_volumes(**params).get_result()
        except ApiException as e:
            LOGGER.info("List Volumes failed with status code " + str(e.code) + ": " + e.message)

        return response.get("volumes", [])

    def create_volume(self, volume_json):
        """
        :param volume_json:
        :return:
        """

        if not isinstance(volume_json, dict):
            raise IBMInvalidRequestError("Parameter 'volume_json' should be a dictionary")

        return self.service.create_volume(volume_prototype=volume_json).get_result()

    def delete_volume(self, volume_id):
        """
        :param volume_id:
        :return:
        """
        return self.service.delete_volume(id=volume_id)

    def get_volume(self, volume_id):
        """
        :param volume_id:
        :return:
        """
        return self.service.get_volume(id=volume_id).get_result()

    def update_volume(self, volume_id, volume_json):
        """
        :param volume_id:
        :param volume_json:
        :return:
        """
        if not isinstance(volume_json, dict):
            raise IBMInvalidRequestError("Parameter 'volume_json' should be a dictionary")

        response = {}
        try:
            response = self.service.update_volume(id=volume_id, volume_patch=volume_json).get_result()
        except ApiException as e:
            LOGGER.info("Update Volume failed with status code " + str(e.code) + ": " + e.message)

        return response
