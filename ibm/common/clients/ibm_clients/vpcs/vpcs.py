import logging

from ibm_cloud_sdk_core import ApiException

from ..base_client import BaseClient
from ..consts import VPC_DEFAULT_PAGINATION_LIMIT
from ..exceptions import IBMInvalidRequestError

LOGGER = logging.getLogger(__name__)


class VPCsClient(BaseClient):
    """
    Client for VPC related tasks
    """

    def __init__(self, cloud_id, region):
        super(VPCsClient, self).__init__(cloud_id=cloud_id, region=region)

    def list_vpcs(self, resource_group_id=None, classic_access=None, limit=VPC_DEFAULT_PAGINATION_LIMIT):
        """
        :param resource_group_id:
        :param classic_access:
        :param limit: Number of Resources Per Page
        :return:
        """
        params = {
            "resource_group_id": resource_group_id,
            "classic_access": classic_access,
            "limit": limit
        }

        response = {}
        try:
            response = self.service.list_vpcs(**params).get_result()
        except ApiException as e:
            LOGGER.info("List VPCs failed with status code " + str(e.code) + ": " + e.message)
        return response.get("vpcs", [])

    def create_vpc(self, vpc_json):
        """
        :param vpc_json:
        :return:
        """
        if not isinstance(vpc_json, dict):
            raise IBMInvalidRequestError("Parameter 'vpc_json' should be a dictionary")

        # TODO: Create schema for input and validate it

        return self.service.create_vpc(**vpc_json).get_result()

    def delete_vpc(self, vpc_id):
        """
        :param vpc_id:
        :return:
        """

        return self.service.delete_vpc(id=vpc_id)

    def get_vpc(self, vpc_id):
        """
        :param vpc_id:
        :return:
        """
        return self.service.get_vpc(id=vpc_id).get_result()

    def update_vpc(self, vpc_id, vpc_json):
        """
        :param vpc_id:
        :param vpc_json:
        :return:
        """
        if not isinstance(vpc_json, dict):
            raise IBMInvalidRequestError("Parameter 'vpc_json' should be a dictionary")

        # TODO: Create schema for input and validate it

        response = {}
        try:
            response = self.service.update_vpc(id=vpc_id, vpc_patch=vpc_json).get_result()
        except ApiException as e:
            LOGGER.info("Update VPC failed with status code " + str(e.code) + ": " + e.message)

        return response

    def get_vpcs_default_network_acl(self, vpc_id):
        """
        :param vpc_id:
        :return:
        """
        return self.service.get_vpc_default_network_acl(id=vpc_id).get_result()

    def get_vpcs_default_security_group(self, vpc_id):
        """
        :param vpc_id:
        :return:
        """
        return self.service.get_vpc_default_security_group(id=vpc_id).get_result()

    def list_address_prefixes(self, vpc_id, limit=VPC_DEFAULT_PAGINATION_LIMIT):
        """
        :param vpc_id:
        :param limit:
        :return:
        """
        params = {
            "vpc_id": vpc_id,
            "limit": limit
        }
        response = self.service.list_vpc_address_prefixes(**params).get_result()
        return response.get("address_prefixes", [])

    def create_address_prefix(self, vpc_id, address_prefix_json):
        """
        :param vpc_id:
        :param address_prefix_json:
        :return:
        """
        if not isinstance(address_prefix_json, dict):
            raise IBMInvalidRequestError("Parameter 'address_prefix_json' should be a dictionary")

        # TODO: Create schema for input and validate it

        return self.service.create_vpc_address_prefix(**address_prefix_json, vpc_id=vpc_id).get_result()

    def delete_address_prefix(self, vpc_id, address_prefix_id):
        """
        :param vpc_id:
        :param address_prefix_id:
        :return:
        """
        return self.service.delete_vpc_address_prefix(vpc_id=vpc_id, id=address_prefix_id)

    def get_address_prefix(self, vpc_id, address_prefix_id):
        """
        :param vpc_id:
        :param address_prefix_id:
        :return:
        """
        response = {}
        try:
            response = self.service.get_vpc_address_prefix(vpc_id=vpc_id, id=address_prefix_id).get_result()
        except ApiException as e:
            LOGGER.info("Get Address Prefix failed with status code " + str(e.code) + ": " + e.message)

        return response

    def update_address_prefix(self, vpc_id, address_prefix_id, address_prefix_json):
        """
        :param vpc_id:
        :param address_prefix_id:
        :param address_prefix_json:
        :return:
        """
        if not isinstance(address_prefix_json, dict):
            raise IBMInvalidRequestError("Parameter 'address_prefix_json' should be a dictionary")

        # TODO: Create schema for input and validate it

        response = {}
        try:
            response = self.service.update_vpc_address_prefix(vpc_id=vpc_id, id=address_prefix_id,
                                                              address_prefix_patch=address_prefix_json).get_result()
        except ApiException as e:
            LOGGER.info("Update Address Prefix failed with status code " + str(e.code) + ": " + e.message)

        return response

    def list_vpc_routing_tables(self, vpc_id, limit=VPC_DEFAULT_PAGINATION_LIMIT):
        """
        :param vpc_id:
        :param limit:
        :return:
        """
        params = {
            "vpc_id": vpc_id,
            "limit": limit
        }

        response = {}
        try:
            response = self.service.list_vpc_routing_tables(**params).get_result()
        except ApiException as e:
            LOGGER.info("List VPC Routing Tables failed with status code " + str(e.code) + ": " + e.message)

        return response.get("routing_tables", [])

    def create_vpc_routing_table(self, vpc_id, routing_table_json):
        """
        :param vpc_id:
        :param routing_table_json:
        :return:
        """

        if not isinstance(routing_table_json, dict):
            raise IBMInvalidRequestError("Parameter 'routing_table_json' should be a dictionary")

        # TODO: Create schema for input and validate it

        return self.service.create_vpc_routing_table(**routing_table_json, vpc_id=vpc_id).get_result()

    def delete_vpc_routing_table(self, vpc_id, routing_table_id):
        """
        :param vpc_id:
        :param routing_table_id:
        :return:
        """
        return self.service.delete_vpc_routing_table(vpc_id=vpc_id, id=routing_table_id)

    def get_vpc_routing_table(self, vpc_id, routing_table_id):
        """
        :param vpc_id:
        :param routing_table_id:
        :return:
        """
        return self.service.get_vpc_routing_table(vpc_id=vpc_id, id=routing_table_id).get_result()

    def update_vpc_routing_table(self, vpc_id, routing_table_id, routing_table_json):
        """
        :param vpc_id:
        :param routing_table_id:
        :param routing_table_json:
        :return:
        """
        if not isinstance(routing_table_json, dict):
            raise IBMInvalidRequestError("Parameter 'routing_table_json' should be a dictionary")

        # TODO: Create schema for input and validate it

        response = {}
        try:
            response = self.service.update_vpc_routing_table(vpc_id=vpc_id, id=routing_table_id,
                                                             routing_table_patch=routing_table_json).get_result()
        except ApiException as e:
            LOGGER.info("Update VPC Routing Table failed with status code " + str(e.code) + ": " + e.message)

        return response

    def get_vpc_default_routing_table(self, vpc_id):
        """
        :param vpc_id:
        :return:
        """

        return self.service.get_vpc_default_routing_table(id=vpc_id).get_result()

    def list_vpc_routing_table_routes(self, vpc_id, routing_table_id, limit=VPC_DEFAULT_PAGINATION_LIMIT):
        """
        :param vpc_id:
        :param routing_table_id:
        :param limit:
        :return:
        """
        params = {
            "limit": limit,
            "vpc_id": vpc_id,
            "routing_table_id": routing_table_id
        }

        response = self.service.list_vpc_routing_table_routes(**params).get_result()
        return response.get("routes", [])

    def create_vpc_routing_table_routes(self, vpc_id, routing_table_id, routes_json):
        """
        :param vpc_id:
        :param routing_table_id:
        :param routes_json:
        :return:
        """

        if not isinstance(routes_json, dict):
            raise IBMInvalidRequestError("Parameter 'routes_json' should be a dictionary")

        # TODO: Create schema for input and validate it

        response = {}
        try:
            response = self.service.create_vpc_routing_table_route(**routes_json,
                                                                   vpc_id=vpc_id,
                                                                   routing_table_id=routing_table_id).get_result()
        except ApiException as e:
            LOGGER.info("Create VPC Routing Table Rout failed with status code " + str(e.code) + ": " + e.message)

        return response

    def delete_vpc_routing_table_route(self, vpc_id, routing_table_id, route_id):
        """
        :param vpc_id:
        :param routing_table_id:
        :param route_id:
        :return:
        """
        response = {}
        try:
            response = self.service.delete_vpc_routing_table_route(vpc_id=vpc_id,
                                                                   routing_table_id=routing_table_id, id=route_id)
        except ApiException as e:
            LOGGER.info("Delete VPC Routing Table Rout failed with status code " + str(e.code) + ": " + e.message)

        return response

    def get_vpc_routing_table_route(self, vpc_id, routing_table_id, route_id):
        """
        :param vpc_id:
        :param routing_table_id:
        :param route_id:
        :return:
        """
        response = {}
        try:
            response = self.service.get_vpc_routing_table_route(vpc_id=vpc_id, routing_table_id=routing_table_id,
                                                                id=route_id).get_result()
        except ApiException as e:
            LOGGER.info("Get VPC Routing Table Rout failed with status code " + str(e.code) + ": " + e.message)

        return response

    def update_vpc_routing_table_route(self, vpc_id, routing_table_id, route_id, route_json):
        """
        :param vpc_id:
        :param routing_table_id:
        :param route_id:
        :param route_json:
        :return:
        """
        if not isinstance(route_json, dict):
            raise IBMInvalidRequestError("Parameter 'route_json' should be a dictionary")

        # TODO: Create schema for input and validate it

        response = {}
        try:
            response = self.service.get_vpc_routing_table_route(vpc_id=vpc_id, routing_table_id=routing_table_id,
                                                                id=route_id, route_patch=route_json)
        except ApiException as e:
            LOGGER.info("Update VPC Routing Table Rout failed with status code " + str(e.code) + ": " + e.message)

        return response
