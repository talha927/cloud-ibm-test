import logging

from ibm_cloud_sdk_core import ApiException

from ..base_client import BaseClient
from ..consts import VPC_DEFAULT_PAGINATION_LIMIT
from ..exceptions import IBMInvalidRequestError

LOGGER = logging.getLogger(__name__)


class PlacementGroupsClient(BaseClient):
    """
    Client for Placement Groups APIs
    """

    def __init__(self, cloud_id, region):
        super(PlacementGroupsClient, self).__init__(cloud_id=cloud_id, region=region)

    def list_placement_groups(self, limit=VPC_DEFAULT_PAGINATION_LIMIT):
        """
        List all Placement Groups
        :param limit:
        :return:
        """
        params = {
            'limit': limit,
        }

        response = {}
        try:
            response = self.service.list_placement_groups(**params).get_result()
        except ApiException as e:
            LOGGER.info("List Placement Groups failed with status code " + str(e.code) + ": " + e.message)

        return response.get("placement_groups", [])

    def create_placement_group(self, placement_group_json):
        """
        Create a Placement Group
        :param placement_group_json:
        :return:
        """
        if not isinstance(placement_group_json, dict):
            raise IBMInvalidRequestError("Parameter 'placement_group_json' should be a dictionary")

        return self.service.create_placement_group(**placement_group_json).get_result()

    def delete_placement_group(self, placement_group_id):
        """
        Delete a Placement Group by ID
        :param placement_group_id:
        :return:
        """
        return self.service.delete_placement_group(id=placement_group_id)

    def get_placement_group(self, placement_group_id):
        """
        Get a Placement Group by ID
        :param placement_group_id:
        :return:
        """
        return self.service.get_placement_group(id=placement_group_id).get_result()

    def update_placement_group(self, placement_group_id, placement_group_json):
        """
        Update a Placement Group by ID
        :param placement_group_id:
        :param placement_group_json:
        :return:
        """
        return self.service.update_placement_group(
            id=placement_group_id, placement_group_patch=placement_group_json).get_result()
