import logging

from ibm_cloud_sdk_core import ApiException
from ibm_platform_services import ResourceManagerV2

from ..base_client import BaseClient

LOGGER = logging.getLogger(__name__)


class ResourceGroupsClient(BaseClient):
    """
    Client for Resource Group related APIs
    """

    def __init__(self, cloud_id):
        super(ResourceGroupsClient, self).__init__(cloud_id=cloud_id)
        self.resource_manager_service = ResourceManagerV2(authenticator=self.authenticate_ibm_cloud_account())

    def list_resource_groups(self, account_id=None, date=None, name=None, default=None, include_deleted=None):
        """
        param: account_id:
        param: date:
        param: name:
        param: default:
        param: include_deleted:
        """
        param = {
            "account_id": account_id,
            "date": date,
            "name": name,
            "default": default,
            "include_deleted": include_deleted
        }

        response = dict(self.resource_manager_service.list_resource_groups(**param).get_result())
        return response.get("resources", [])

    def get_resource_group(self, resource_group_id):
        """
        :param resource_group_id:
        :return:
        """
        response = {}
        try:
            response = self.resource_manager_service.get_resource_group(id=resource_group_id).get_result()
        except ApiException as e:
            LOGGER.info("Get Resource Group failed with status code " + str(e.code) + ": " + e.message)

        return response
