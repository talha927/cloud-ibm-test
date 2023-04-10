import logging

from ibm_cloud_sdk_core import ApiException

from ..base_client import BaseClient
from ..consts import VPC_DEFAULT_PAGINATION_LIMIT
from ..exceptions import IBMInvalidRequestError

LOGGER = logging.getLogger(__name__)


class ImagesClient(BaseClient):
    """
    Client for images related APIs
    """

    def __init__(self, cloud_id, region):
        super(ImagesClient, self).__init__(cloud_id=cloud_id, region=region)

    def list_images(self, visibility=None, name=None, resource_group_id=None,
                    limit=VPC_DEFAULT_PAGINATION_LIMIT):
        """
        :param visibility:
        :param name:
        :param resource_group_id:
        :param limit: Number of Resources Per Page
        :return:
        """
        if visibility and visibility not in ["private", "public"]:
            raise IBMInvalidRequestError("Parameter 'visibility' should be one of ['private', 'public']")

        params = {
            "visibility": visibility,
            "name": name,
            "resource_group_id": resource_group_id,
            "limit": limit
        }

        response = self.service.list_images(**params).get_result()
        return response.get("images", [])

    def create_image(self, image_json):
        """
        :param image_json:
        :return:
        """
        if not isinstance(image_json, dict):
            raise IBMInvalidRequestError("Parameter 'image_json' should be a dictionary")

        # TODO: Create schema for input and validate it

        return self.service.create_image(image_prototype=image_json).get_result()

    def delete_image(self, image_id):
        """
        :param image_id:
        :return:
        """
        return self.service.delete_image(id=image_id)

    def get_image(self, image_id):
        """
        :param image_id:
        :return:
        """
        return self.service.get_image(id=image_id).get_result()

    def update_image(self, image_id, image_json):
        """
        :param image_id:
        :param image_json:
        :return:
        """
        response = {}
        try:
            response = self.service.update_image(id=image_id, image_patch=image_json).get_result()
        except ApiException as e:
            LOGGER.info("Update Image failed with status code " + str(e.code) + ": " + e.message)

        return response

    def list_operating_systems(self, limit=VPC_DEFAULT_PAGINATION_LIMIT):
        """
        :param limit: Number of Resources Per Page
        :return:
        """
        params = {
            "limit": limit
        }

        response = {}
        try:
            response = self.service.list_operating_systems(**params).get_result()
        except ApiException as e:
            LOGGER.info("List Operating Systems failed with status code " + str(e.code) + ": " + e.message)

        return response.get("operating_systems", [])

    def get_operating_system(self, operating_system_name):
        """
        :param operating_system_name:
        :return:
        """

        response = {}
        try:
            response = self.service.get_operating_system(name=operating_system_name).get_result()
        except ApiException as e:
            LOGGER.info("Get Operating System failed with status code " + str(e.code) + ": " + e.message)

        return response
