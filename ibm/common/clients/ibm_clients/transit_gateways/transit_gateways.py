import logging

from ibm_cloud_networking_services import TransitGatewayApisV1
from ibm_cloud_sdk_core import ApiException

from ..base_client import BaseClient
from ..consts import TRANSIT_GATEWAY_DEFAULT_PAGINATION_LIMIT, TRANSIT_GATEWAY_PARAMS
from ..exceptions import IBMInvalidRequestError

LOGGER = logging.getLogger(__name__)


class TransitGatewaysClient(BaseClient):
    """
        Client for Transit Gateways related APIs
        """

    def __init__(self, cloud_id, region=None):
        super(TransitGatewaysClient, self).__init__(cloud_id=cloud_id, region=region)
        self.transit_gateway_service = TransitGatewayApisV1(
            version=TRANSIT_GATEWAY_PARAMS["version"], authenticator=self.authenticate_ibm_cloud_account()
        )

    def create_transit_gateway(self, transit_gateway_json):
        """
        :param transit_gateway_json:
        :return:
        """

        if not isinstance(transit_gateway_json, dict):
            raise IBMInvalidRequestError("Parameter 'transit-gateway_json' should be a dictionary")

        return self.transit_gateway_service.create_transit_gateway(**transit_gateway_json).get_result()

    def list_transit_gateways(self, limit=TRANSIT_GATEWAY_DEFAULT_PAGINATION_LIMIT):
        """
        :param limit: Number of Resources Per Page:
        :return:
        """
        params = {
            "limit": limit
        }

        response = {}
        try:
            response = self.transit_gateway_service.list_transit_gateways(**params).get_result()
        except ApiException as e:
            message = ("List Transit gateways failed with status code " + str(e.code) + ": " + e.message)
            raise ApiException(message=message, code=e.code)

        return response.get("transit_gateways", [])

    def delete_transit_gateway(self, transit_gateway_id):
        """
        :param transit_gateway_id:
        """

        return self.transit_gateway_service.delete_transit_gateway(id=transit_gateway_id)

    def get_transit_gateway(self, transit_gateway_id):
        """
        :param transit_gateway_id:
        :return:
        """

        return self.transit_gateway_service.get_transit_gateway(id=transit_gateway_id).get_result()

    def create_transit_gateway_connection(self, transit_gateway_id, transit_gateway_connection_json):
        """
        :param transit_gateway_id:
        :param transit_gateway_connection_json:
        :return:
        """

        if not isinstance(transit_gateway_connection_json, dict):
            raise IBMInvalidRequestError("Parameter 'transit-gateway_connection_json' should be a dictionary")

        return self.transit_gateway_service.create_transit_gateway_connection(
            transit_gateway_id=transit_gateway_id, **transit_gateway_connection_json).get_result()

    def delete_transit_gateway_connection(self, transit_gateway_id, connection_id):
        """
        :param transit_gateway_id:
        :param connection_id:
        """

        return self.transit_gateway_service.delete_transit_gateway_connection(transit_gateway_id=transit_gateway_id,
                                                                              id=connection_id)

    def list_transit_gateway_connections(self, transit_gateway_id):
        """
        :param transit_gateway_id:
        :return:
        """

        response = {}
        try:
            response = self.transit_gateway_service.list_transit_gateway_connections(
                transit_gateway_id=transit_gateway_id).get_result()
        except ApiException as e:
            message = ("List Transit Gateways Connections failed with status code " + str(e.code) + ": " + e.message)
            LOGGER.info(message)
            raise ApiException(message=message, code=e.code)

        return response.get("connections", [])

    def get_transit_gateway_connection(self, transit_gateway_id, connection_id):
        """
        :param transit_gateway_id:
        :param connection_id:
        :return:
        """

        return self.transit_gateway_service.get_transit_gateway_connection(transit_gateway_id=transit_gateway_id,
                                                                           id=connection_id).get_result()

    def create_transit_gateway_connection_prefix_filter(self, transit_gateway_id, connection_id,
                                                        transit_gateway_connection_prefix_filter_json):
        """
        :param transit_gateway_id:
        :param connection_id:
        :param transit_gateway_connection_prefix_filter_json:
        :return:
        """

        if not isinstance(transit_gateway_connection_prefix_filter_json, dict):
            raise IBMInvalidRequestError("Parameter 'transit-gateway_connection_prefix_filter_json'"
                                         " should be a dictionary")

        return self.transit_gateway_service.create_transit_gateway_connection_prefix_filter(
            transit_gateway_id=transit_gateway_id,
            id=connection_id,
            **transit_gateway_connection_prefix_filter_json).get_result()

    def list_transit_gateway_connection_prefix_filters(self, transit_gateway_id, connection_id):
        """
        :param transit_gateway_id:
        :param connection_id:
        :return:
        """

        response = {}
        try:
            response = self.transit_gateway_service.list_transit_gateway_connection_prefix_filters(
                transit_gateway_id=transit_gateway_id, id=connection_id).get_result()
        except ApiException as e:
            message = ("List Transit Gateways Connection Prefix Filter failed with status code " + str(e.code) + ": "
                       + e.message)
            LOGGER.info(message)
            raise ApiException(message=message, code=e.code)

        return response.get("prefix_filters", [])

    def delete_transit_gateway_connection_prefix_filter(self, transit_gateway_id, connection_id, filter_id):
        """
        :param transit_gateway_id:
        :param connection_id:
        :param filter_id:
        """

        return self.transit_gateway_service.delete_transit_gateway_connection_prefix_filter(
            transit_gateway_id=transit_gateway_id, id=connection_id, filter_id=filter_id)

    def get_transit_gateway_connection_prefix_filter(self, transit_gateway_id, connection_id, filter_id):
        """
        :param transit_gateway_id:
        :param connection_id:
        :param filter_id:
        :return:
        """
        response = {}
        try:
            response = self.transit_gateway_service.get_transit_gateway_connection_prefix_filter(
                transit_gateway_id=transit_gateway_id,
                id=connection_id,
                filter_id=filter_id).get_result()
        except ApiException as e:
            LOGGER.info("Getting Of Transit Gateway Connection Prefix Filter Failed with status code " + str(e.code) +
                        ": " + e.message)
        return response

    def list_transit_gateway_route_reports(self, transit_gateway_id):
        """
        :param transit_gateway_id:
        :return:
        """
        response = {}
        try:
            response = self.transit_gateway_service.list_transit_gateway_route_reports(
                transit_gateway_id=transit_gateway_id).get_result()
        except ApiException as e:
            LOGGER.info("List Transit Gateways Route Reports failed with status code " + str(e.code) + ": " +
                        e.message)

        return response.get("route_reports", [])

    def create_transit_gateway_route_report(self, transit_gateway_id):
        """
        :param transit_gateway_id:
        :return:
                """
        return self.transit_gateway_service.create_transit_gateway_route_report(
            transit_gateway_id=transit_gateway_id).get_result()

    def get_transit_gateway_route_report(self, transit_gateway_id, id):
        """
        :param transit_gateway_id:
        :param id:
        :return:
        """
        return self.transit_gateway_service.get_transit_gateway_route_report(
            transit_gateway_id=transit_gateway_id, id=id).get_result()

    def delete_transit_gateway_route_report(self, transit_gateway_id, id):
        """
        :param transit_gateway_id:
        :param id:
        :return:
        """
        return self.transit_gateway_service.delete_transit_gateway_route_report(
            transit_gateway_id=transit_gateway_id, id=id).get_result()
