import logging

import requests
from ibm_cloud_sdk_core import ApiException

from .paths import ATTACH_ACL_TO_SUBNET_PATH, ATTACH_ROUTING_TABLE_TO_SUBNET_PATH
from ..base_client import BaseClient
from ..consts import VPC_DEFAULT_PAGINATION_LIMIT
from ..exceptions import IBMInvalidRequestError
from ..urls import VPC_URL_TEMPLATE

LOGGER = logging.getLogger(__name__)


class SubnetsClient(BaseClient):
    """
    Client for subnet related APIs
    """

    def __init__(self, cloud_id, region):
        super(SubnetsClient, self).__init__(cloud_id=cloud_id, region=region)

    def list_subnets(self, resource_group_id=None, routing_table_id=None, routing_table_name=None,
                     limit=VPC_DEFAULT_PAGINATION_LIMIT):
        """
        :param resource_group_id:
        :param routing_table_id:
        :param routing_table_name:
        :param limit: Number of Resources Per Page
        :return:
        """
        params = {
            "resource_group_id": resource_group_id,
            "routing_table_id": routing_table_id,
            "routing_table_name": routing_table_name,
            "limit": limit
        }

        response = {}
        try:
            response = self.service.list_subnets(**params).get_result()
        except ApiException as e:
            LOGGER.info("List Subnets failed with status code " + str(e.code) + ": " + e.message)

        return response.get("subnets", [])

    def create_subnet(self, subnet_json):
        """
        :param subnet_json:
        :return:
        """

        # TODO: Create schema for input and validate it
        return self.service.create_subnet(subnet_prototype=subnet_json).get_result()

    def delete_subnet(self, subnet_id):
        """
        :param subnet_id:
        :return:
        """
        return self.service.delete_subnet(id=subnet_id)

    def get_subnet(self, subnet_id):
        """
        :param subnet_id:
        :return:
        """
        return self.service.get_subnet(id=subnet_id).get_result()

    def update_subnet(self, subnet_id, subnet_json):
        """
        :param subnet_id:
        :param subnet_json:
        :return:
        """
        # TODO: Create schema for input and validate it
        response = {}
        try:
            response = self.service.update_subnet(subnet_id=subnet_id, subnet_patch=subnet_json).get_result()
        except ApiException as e:
            LOGGER.info("Update Subnets failed with status code " + str(e.code) + ": " + e.message)

        return response

    def get_routing_table_attached_to_subnet(self, subnet_id):
        """
        :param subnet_id:
        :return:
        """
        return self.service.get_subnet_routing_table(id=subnet_id).get_result()

    def attach_routing_table_to_subnet(self, region, subnet_id, routing_table_json):
        """
        :param region:
        :param subnet_id:
        :param routing_table_json:
        :return:
        """
        request = requests.Request(
            "PUT",
            VPC_URL_TEMPLATE.format(region=region,
                                    path=ATTACH_ROUTING_TABLE_TO_SUBNET_PATH.format(subnet_id=subnet_id)),
            json=routing_table_json
        )

        response = self._execute_request(request, "VPC_RESOURCE")

        return response

    def list_reserved_ips_in_subnet(self, subnet_id, limit=VPC_DEFAULT_PAGINATION_LIMIT):
        """
        :param subnet_id:
        :param limit: Number of Resources Per Page
        :return:
        """
        params = {
            "subnet_id": subnet_id,
            "limit": limit
        }

        response = {}
        try:
            response = self.service.list_subnet_reserved_ips(**params).get_result()
        except ApiException as e:
            LOGGER.info("List Subnet Reserved IPs failed with status code " + str(e.code) + ": " + e.message)

        return response.get("reserved_ips", [])

    def reserve_ip_in_subnet(self, subnet_id, reserve_ip_json):
        """
        :param subnet_id:
        :param reserve_ip_json:
        :return:
        """
        if not isinstance(reserve_ip_json, dict):
            raise IBMInvalidRequestError("Parameter 'reserve_ip_json' should be a dictionary")

        # TODO: Create schema for input and validate it

        return self.service.create_subnet_reserved_ip(subnet_id=subnet_id, **reserve_ip_json).get_result()

    def release_subnet_reserved_ip(self, subnet_id, reserved_ip_id):
        """
        :param subnet_id:
        :param reserved_ip_id:
        :return:
        """

        return self.service.delete_subnet_reserved_ip(subnet_id=subnet_id, id=reserved_ip_id)

    def get_subnet_reserved_ip(self, subnet_id, reserved_ip_id):
        """
        :param subnet_id:
        :param reserved_ip_id:
        :return:
        """
        response = {}
        try:
            response = self.service.get_subnet_reserved_ip(subnet_id=subnet_id, id=reserved_ip_id).get_result()
        except ApiException as e:
            LOGGER.info("Get Subnet Reserved IP failed with status code " + str(e.code) + ": " + e.message)

        return response

    def update_subnet_reserved_ip(self, subnet_id, reserved_ip_id, reserved_ip_json):
        """
        :param subnet_id:
        :param reserved_ip_id:
        :param reserved_ip_json:
        :return:
        """
        # TODO: Create schema for input and validate it
        response = {}
        try:
            response = self.service.update_subnet_reserved_ip(subnet_id=subnet_id, id=reserved_ip_id,
                                                              reserved_ip_patch=reserved_ip_json).get_result()
        except ApiException as e:
            LOGGER.info("Update Subnet Reserved IP failed with status code " + str(e.code) + ": " + e.message)

        return response

    def get_attached_network_acl_to_subnet(self, subnet_id):
        """
        :param subnet_id:
        :return:
        """
        response = {}
        try:
            response = self.service.get_subnet_network_acl(subnet_id=subnet_id).get_result()
        except ApiException as e:
            LOGGER.info("Get Subnet Network ACL failed with status code " + str(e.code) + ": " + e.message)

        return response

    def attach_acl_to_subnet(self, region, subnet_id, attach_subnet_json):
        """
        :param region:
        :param subnet_id:
        :param attach_subnet_json:
        :return:
        """
        request = requests.Request(
            "PUT",
            VPC_URL_TEMPLATE.format(region=region, path=ATTACH_ACL_TO_SUBNET_PATH.format(subnet_id=subnet_id)),
            json=attach_subnet_json
        )

        response = self._execute_request(request, "VPC_RESOURCE")

        return response

    def detach_pg_from_subnet(self, subnet_id):
        """
        :param subnet_id:
        :return:
        """
        return self.service.unset_subnet_public_gateway(id=subnet_id)

    def get_attached_pg_to_subnet(self, subnet_id):
        """
        :param subnet_id:
        :return:
        """
        return self.service.get_subnet_public_gateway(id=subnet_id).get_result()

    def attach_pg_to_subnet(self, subnet_id, attach_pg_json):
        """
        :param subnet_id:
        :param attach_pg_json:
        :return:
        """
        return self.service.set_subnet_public_gateway(id=subnet_id, public_gateway_identity=attach_pg_json).get_result()
