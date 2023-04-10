import logging

from ibm_cloud_sdk_core import ApiException
from ibm_platform_services import ResourceControllerV2

from ..base_client import BaseClient
from ..consts import VPC_DEFAULT_PAGINATION_LIMIT
from ..urls import RESOURCE_CONTROLLER_SERVICE_URL

LOGGER = logging.getLogger(__name__)


class ResourceInstancesClient(BaseClient):
    """
    Client for Resource Instances related APIs
    """

    def __init__(self, cloud_id):
        super(ResourceInstancesClient, self).__init__(cloud_id=cloud_id)
        self.resource_controller_service = ResourceControllerV2(authenticator=self.authenticate_ibm_cloud_account())

    def list_resource_instances(self, guid=None, name=None, resource_group_id=None, resource_id=None, updated_from=None,
                                resource_plan_id=None, type_=None, sub_type=None, limit=VPC_DEFAULT_PAGINATION_LIMIT):
        """
        :param guid: guid of the instance
        :param name: name of the instance
        :param resource_group_id: resource group id for the listing resource of a resource group
        :param resource_id: The unique id of the offering
        :param resource_plan_id: The unique ID of the plan associated with the offering.
        :param type_:
        :param sub_type:
        :param limit: Number of Resources Per Page
        :param updated_from: When resources were last updated range. Start date inclusive filter.
        :return:
        """
        assert (limit <= 100), "Max limit is 100."
        params = {
            "guid": guid,
            "name": name,
            "resource_group_id": resource_group_id,
            "resource_id": resource_id,
            "resource_plan_id": resource_plan_id,
            "type": type_,
            "sub_type": sub_type,
            "limit": limit,
            'updated_from': updated_from
        }
        self.resource_controller_service.DEFAULT_SERVICE_URL = RESOURCE_CONTROLLER_SERVICE_URL.format()
        response = {}
        try:
            response = self.resource_controller_service.list_resource_instances(**params).get_result()
        except ApiException as e:
            LOGGER.info("List Resource Instances failed with status code " + str(e.code) + ": " + e.message)

        return response.get("resources", [])

    def list_resource_keys(self, guid=None, name=None, resource_group_id=None, resource_id=None, updated_from=None,
                           updated_to=None, limit=VPC_DEFAULT_PAGINATION_LIMIT):
        """
        :param guid: guid of the key
        :param name: name of the key
        :param resource_group_id: resource group id for the listing resource of a resource group
        :param resource_id: The unique id of the offering
        :param updated_from:
        :param updated_to:
        :param limit: Number of Resources Per Page
        :return:
        """
        assert (limit <= 100), "Max limit is 100."
        params = {
            "guid": guid,
            "name": name,
            "resource_group_id": resource_group_id,
            "resource_id": resource_id,
            "limit": limit,
            "updated_from": updated_from,
            "updated_to": updated_to
        }
        response = dict(self.resource_controller_service.list_resource_keys(**params).get_result())
        return response.get("resources", [])
