import logging
from ibm_cloud_sdk_core import ApiException

from ..base_client import BaseClient
from ..consts import VPC_DEFAULT_PAGINATION_LIMIT
from ..exceptions import IBMInvalidRequestError

LOGGER = logging.getLogger(__name__)


class EndpointGatewaysClient(BaseClient):
    """
    Client for Endpoint Gateways related APIs
    """

    def __init__(self, cloud_id, region):
        super(EndpointGatewaysClient, self).__init__(cloud_id=cloud_id, region=region)

    def list_endpoint_gateways(self, resource_group_id=None, name=None, limit=VPC_DEFAULT_PAGINATION_LIMIT):
        """
        :param resource_group_id:
        :param name:
        :param limit: Number of Resources Per Page
        :return:
        """
        params = {
            "resource_group_id": resource_group_id,
            "name": name,
            "limit": limit
        }

        response = {}
        try:
            response = self.service.list_endpoint_gateways(**params).get_result()
        except ApiException as e:
            LOGGER.info("List Endpoint Gateways failed with status code " + str(e.code) + ": " + e.message)
        return response.get("endpoint_gateways", [])

    def create_endpoint_gateway(self, endpoint_gateway_json):
        """
        :param endpoint_gateway_json:
        :return:
        """
        if not isinstance(endpoint_gateway_json, dict):
            raise IBMInvalidRequestError("Parameter 'endpoint_gateway_json' should be a dictionary")

        return self.service.create_endpoint_gateway(**endpoint_gateway_json).get_result()

    def list_reserved_ip_bound_to_endpoint_gateway(self, endpoint_gateway_id, sort="address",
                                                   limit=VPC_DEFAULT_PAGINATION_LIMIT):
        """
        :param endpoint_gateway_id:
        :param sort:
        :param limit: Number of Resources Per Page
        :return:
        """
        if not endpoint_gateway_id:
            raise IBMInvalidRequestError("Parameter 'endpoint_gateway_id' cannot be None.")

        params = {
            "sort": sort,
            "limit": limit,
            "endpoint_gateway_id": endpoint_gateway_id
        }

        response = {}
        try:
            response = self.service.list_endpoint_gateway_ips(**params).get_result()
        except ApiException as e:
            LOGGER.info("List Endpoint Gateway IPs failed with status code " + str(e.code) + ": " + e.message)

        return response.get("ips", [])

    def unbind_ip_from_endpoint_gateway(self, endpoint_gateway_id, ip_id):
        """
        :param endpoint_gateway_id:
        :param ip_id:
        :return:
        """
        if not (endpoint_gateway_id and ip_id):
            raise IBMInvalidRequestError("Parameter 'endpoint_gateway_id' and 'ip_id' cannot be None.")

        response = {}
        try:
            response = self.service.remove_endpoint_gateway_ip(endpoint_gateway_id=endpoint_gateway_id, id=ip_id)
        except ApiException as e:
            LOGGER.info("Unbind Endpoint Gateway IP failed with status code " + str(e.code) + ": " + e.message)

        return response

    def get_reserved_ip_bound_to_endpoint_gateway(self, endpoint_gateway_id, ip_id):
        """
        :param endpoint_gateway_id:
        :param ip_id:
        :return:
        """
        if not (endpoint_gateway_id and ip_id):
            raise IBMInvalidRequestError("Parameter 'endpoint_gateway_id' and 'ip_id' cannot be None.")

        response = {}
        try:
            response = self.service.get_endpoint_gateway_ip(endpoint_gateway_id=endpoint_gateway_id,
                                                            id=ip_id).get_result()
        except ApiException as e:
            LOGGER.info("Get Endpoint Gateway IP failed with status code " + str(e.code) + ": " + e.message)

        return response

    def bind_reserved_ip_bound_to_endpoint_gateway(self, endpoint_gateway_id, ip_id):
        """
        :param endpoint_gateway_id:
        :param ip_id:
        :return:
        """
        if not (endpoint_gateway_id and ip_id):
            raise IBMInvalidRequestError("Parameter 'endpoint_gateway_id' and 'ip_id' cannot be None.")

        response = {}
        try:
            response = self.service.add_endpoint_gateway_ip(endpoint_gateway_id=endpoint_gateway_id, id=ip_id)
        except ApiException as e:
            LOGGER.info("Add Endpoint Gateway IP failed with status code " + str(e.code) + ": " + e.message)

        return response

    def delete_endpoint_gateway(self, endpoint_gateway_id):
        """
        :param endpoint_gateway_id:
        :return:
        """
        if not endpoint_gateway_id:
            raise IBMInvalidRequestError("Parameter 'endpoint_gateway_id' cannot be None.")

        return self.service.delete_endpoint_gateway(id=endpoint_gateway_id)

    def get_endpoint_gateway(self, endpoint_gateway_id):
        """
        :param endpoint_gateway_id:
        :return:
        """
        if not endpoint_gateway_id:
            raise IBMInvalidRequestError("Parameter 'endpoint_gateway_id' cannot be None.")

        return self.service.get_endpoint_gateway(id=endpoint_gateway_id).get_result()

    def update_endpoint_gateway(self, endpoint_gateway_id, endpoint_gateway_json):
        """
        :param endpoint_gateway_id:
        :param endpoint_gateway_json:
        :return:
        """
        if not isinstance(endpoint_gateway_json, dict):
            raise IBMInvalidRequestError("Parameter 'endpoint_gateway_json' should be a dictionary")

        if not endpoint_gateway_id:
            raise IBMInvalidRequestError("Parameter 'endpoint_gateway_id' cannot be None.")

        response = {}
        try:
            response = self.service.update_endpoint_gateway(id=endpoint_gateway_id,
                                                            endpoint_gateway_patch=endpoint_gateway_json).get_result()
        except ApiException as e:
            LOGGER.info("Update Endpoint Gateway IP failed with status code " + str(e.code) + ": " + e.message)

        return response
