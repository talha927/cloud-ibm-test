import logging

from ibm_cloud_sdk_core import ApiException

from ..base_client import BaseClient
from ..consts import VPC_DEFAULT_PAGINATION_LIMIT

LOGGER = logging.getLogger(__name__)


class VPNsClient(BaseClient):
    """
    Client for VPN related APIs
    """

    def __init__(self, cloud_id, region):
        super(VPNsClient, self).__init__(cloud_id=cloud_id, region=region)

    def list_ike_policies(self, limit=VPC_DEFAULT_PAGINATION_LIMIT):
        """
        :param limit: Number of Resources Per Page
        :return:
        """
        params = {
            "limit": limit
        }

        response = {}
        try:
            response = self.service.list_ike_policies(**params).get_result()
        except ApiException as e:
            LOGGER.info("List IKE Policies failed with status code " + str(e.code) + ": " + e.message)

        return response.get("ike_policies", [])

    def create_ike_policy(self, ike_policy_json):
        """
        :param ike_policy_json:
        :return:
        """

        return self.service.create_ike_policy(**ike_policy_json).get_result()

    def delete_ike_policy(self, ike_policy_id):
        """
        :param ike_policy_id:
        :return:
        """
        return self.service.delete_ike_policy(id=ike_policy_id)

    def get_ike_policy(self, ike_policy_id):
        """
        :param ike_policy_id:
        :return:
        """
        response = {}
        try:
            response = self.service.get_ike_policy(id=ike_policy_id).get_result()
        except ApiException as e:
            LOGGER.info("Get IKE Policy failed with status code " + str(e.code) + ": " + e.message)

        return response

    def update_ike_policy(self, ike_policy_id, ike_policy_json):
        """
        :param ike_policy_id:
        :param ike_policy_json:
        :return:
        """
        # TODO use schema to check payload

        response = {}
        try:
            response = self.service.update_ike_policy(id=ike_policy_id, ike_policy_patch=ike_policy_json).get_result()
        except ApiException as e:
            LOGGER.info("Update IKE Policy failed with status code " + str(e.code) + ": " + e.message)

        return response

    def list_conn_using_specified_ike_policy(self, ike_policy_id):
        """
        :param ike_policy_id:
        :return:
        """
        response = {}
        try:
            response = self.service.list_ike_policy_connections(ike_policy_id=ike_policy_id).get_result()
        except ApiException as e:
            LOGGER.info("List Connection using specified IKE Policies failed with status code " + str(
                e.code) + ": " + e.message)

        return response

    def list_ipsec_policies(self, limit=VPC_DEFAULT_PAGINATION_LIMIT):
        """
        :param limit: Number of Resources Per Page
        :return:
        """
        params = {
            "limit": limit
        }

        response = {}
        try:
            response = self.service.list_ipsec_policies(**params).get_result()
        except ApiException as e:
            LOGGER.info("List IPSEC Policies failed with status code " + str(e.code) + ": " + e.message)

        return response.get("ipsec_policies", [])

    def create_ipsec_policy(self, ipsec_policy_json):
        """
        :param ipsec_policy_json:
        :return:
        """
        return self.service.create_ipsec_policy(**ipsec_policy_json).get_result()

    def delete_ipsec_policy(self, ipsec_policy_id):
        """
        :param ipsec_policy_id:
        :return:
        """
        return self.service.delete_ipsec_policy(id=ipsec_policy_id)

    def get_ipsec_policy(self, ipsec_policy_id):
        """
        :param ipsec_policy_id:
        :return:
        """
        response = {}
        try:
            response = self.service.get_ipsec_policy(id=ipsec_policy_id).get_result()
        except ApiException as e:
            LOGGER.info("Get IPSEC Policy failed with status code " + str(e.code) + ": " + e.message)

        return response

    def update_ipsec_policy(self, ipsec_policy_id, ipsec_policy_json):
        """
        :param ipsec_policy_id:
        :param ipsec_policy_json:
        :return:
        """
        # TODO use schema to check payload

        response = {}
        try:
            response = self.service.update_ipsec_policy(id=ipsec_policy_id,
                                                        i_psec_policy_patch=ipsec_policy_json).get_result()
        except ApiException as e:
            LOGGER.info("Update IPSEC Policy failed with status code " + str(e.code) + ": " + e.message)

        return response

    def list_conn_using_specified_ipsec_policy(self, ipsec_policy_id):
        """
        :param ipsec_policy_id:
        :return:
        """
        response = {}
        try:
            response = self.service.list_ipsec_policy_connections(ipsec_policy_id=ipsec_policy_id).get_result()
        except ApiException as e:
            LOGGER.info("List Connection using specified IPSEC Policies failed with status code " + str(
                e.code) + ": " + e.message)

        return response

    def list_vpn_gateways(self, resource_group_id=None, limit=VPC_DEFAULT_PAGINATION_LIMIT):
        """
        :param resource_group_id:
        :param limit: Number of Resources Per Page
        :return:
        """
        params = {
            "resource_group_id": resource_group_id,
            "limit": limit
        }

        response = {}
        try:
            response = self.service.list_vpn_gateways(**params).get_result()
        except ApiException as e:
            LOGGER.info("List VPN Gateways failed with status code " + str(e.code) + ": " + e.message)

        return response.get("vpn_gateways", [])

    def create_vpn_gateway(self, vpn_gateway_json):
        """
        :param vpn_gateway_json:
        :return:
        """

        # TODO use schema to check payload

        return self.service.create_vpn_gateway(vpn_gateway_prototype=vpn_gateway_json).get_result()

    def delete_vpn_gateway(self, vpn_gateway_id):
        """
        :param vpn_gateway_id:
        :return:
        """
        return self.service.delete_vpn_gateway(id=vpn_gateway_id)

    def get_vpn_gateway(self, vpn_gateway_id):
        """
        :param vpn_gateway_id:
        :return:
        """
        return self.service.get_vpn_gateway(id=vpn_gateway_id).get_result()

    def update_vpn_gateway(self, vpn_gateway_id, vpn_gateway_json):
        """
        :param vpn_gateway_id:
        :param vpn_gateway_json:
        :return:
        """
        # TODO use schema to check payload
        response = {}
        try:
            response = self.service.update_vpn_gateway(id=vpn_gateway_id,
                                                       vpn_gateway_patch=vpn_gateway_json).get_result()
        except ApiException as e:
            LOGGER.info("Update VPN Gateway failed with status code " + str(e.code) + ": " + e.message)

        return response

    def list_vpn_gateway_connections(self, vpn_gateway_id, status=None):
        """
        :param vpn_gateway_id:
        :param status:
        :return:
        """
        params = {
            "vpn_gateway_id": vpn_gateway_id,
            "status": status
        }
        response = {}
        try:
            response = self.service.list_vpn_gateway_connections(**params).get_result()
        except ApiException as e:
            LOGGER.info("List VPN Gateway Connections failed with status code " + str(e.code) + ": " + e.message)

        return response.get("connections", [])

    def create_vpn_connection(self, vpn_gateway_id, connection_json):
        """
        :param vpn_gateway_id:
        :param connection_json:
        :return:
        """

        # TODO use schema to check payload

        return self.service.create_vpn_gateway_connection(vpn_gateway_connection_prototype=connection_json,
                                                          vpn_gateway_id=vpn_gateway_id).get_result()

    def delete_vpn_connection(self, vpn_gateway_id, connection_id):
        """
        :param vpn_gateway_id:
        :param connection_id:
        :return:
        """
        return self.service.delete_vpn_gateway_connection(vpn_gateway_id=vpn_gateway_id, id=connection_id)

    def get_vpn_connection(self, vpn_gateway_id, connection_id):
        """
        :param vpn_gateway_id:
        :param connection_id:
        :return:
        """
        return self.service.get_vpn_gateway_connection(vpn_gateway_id=vpn_gateway_id, id=connection_id).get_result()

    def update_vpn_connection(self, vpn_gateway_id, connection_id, vpn_connection_json):
        """
        :param vpn_gateway_id:
        :param connection_id:
        :param vpn_connection_json:
        :return:
        """
        # TODO use schema to check payload
        response = {}
        try:
            response = self.service.update_vpn_gateway_connection(
                vpn_gateway_id=vpn_gateway_id, id=connection_id,
                vpn_gateway_connection_patch=vpn_connection_json).get_result()
        except ApiException as e:
            LOGGER.info("Update VPN Gateway Connection failed with status code " + str(e.code) + ": " + e.message)

        return response

    def list_local_cidrs(self, vpn_gateway_id, connection_id):
        """
        :param vpn_gateway_id:
        :param connection_id:
        :return:
        """
        params = {
            "vpn_gateway_id": vpn_gateway_id,
            "connection_id": connection_id
        }
        response = {}
        try:
            response = self.service.list_vpn_gateway_connection_local_cidrs(**params).get_result()
        except ApiException as e:
            LOGGER.info("List VPN Local CIDRs failed with status code " + str(e.code) + ": " + e.message)

        return response.get("local_cidrs", [])

    def remove_local_cidr(self, vpn_gateway_id, connection_id, prefix_address, prefix_length):
        """
        :param vpn_gateway_id:
        :param connection_id:
        :param prefix_address:
        :param prefix_length:
        :return:
        """
        response = {}
        try:
            response = self.service.remove_vpn_gateway_connection_local_cidr(
                vpn_gateway_id=vpn_gateway_id, id=connection_id,
                cidr_prefix=prefix_address, prefix_length=prefix_length)
        except ApiException as e:
            LOGGER.info("Remove VPN Local CIDR failed with status code " + str(e.code) + ": " + e.message)

        return response

    def check_specific_local_cidr(self, vpn_gateway_id, connection_id, prefix_address, prefix_length):
        """
        :param vpn_gateway_id:
        :param connection_id:
        :param prefix_address:
        :param prefix_length:
        :return:
        """
        response = {}
        try:
            response = self.service.check_vpn_gateway_connection_local_cidr(
                vpn_gateway_id=vpn_gateway_id, id=connection_id,
                cidr_prefix=prefix_address, prefix_length=prefix_length)
        except ApiException as e:
            LOGGER.info("Check VPN Local CIDR failed with status code " + str(e.code) + ": " + e.message)

        return response

    def set_local_cidr(self, vpn_gateway_id, connection_id, prefix_address, prefix_length):
        """
        :param vpn_gateway_id:
        :param connection_id:
        :param prefix_address:
        :param prefix_length:
        :return:
        """
        response = {}
        try:
            response = self.service.add_vpn_gateway_connection_local_cidr(
                vpn_gateway_id=vpn_gateway_id, id=connection_id,
                cidr_prefix=prefix_address, prefix_length=prefix_length)
        except ApiException as e:
            LOGGER.info("Add VPN Local CIDR failed with status code " + str(e.code) + ": " + e.message)

        return response

    def list_peer_cidr(self, vpn_gateway_id, connection_id):
        """
        :param vpn_gateway_id:
        :param connection_id:
        :return:
        """
        params = {
            "vpn_gateway_id": vpn_gateway_id,
            "connection_id": connection_id
        }

        response = {}
        try:
            response = self.service.list_vpn_gateway_connection_peer_cidrs(**params).get_result()
        except ApiException as e:
            LOGGER.info("List VPN Peer CIDRs failed with status code " + str(e.code) + ": " + e.message)

        return response.get("peer_cidrs", [])

    def remove_peer_cidr(self, vpn_gateway_id, connection_id, prefix_address, prefix_length):
        """
        :param vpn_gateway_id:
        :param connection_id:
        :param prefix_address:
        :param prefix_length:
        :return:
        """
        response = {}
        try:
            response = self.service.remove_vpn_gateway_connection_peer_cidr(
                vpn_gateway_id=vpn_gateway_id, id=connection_id,
                cidr_prefix=prefix_address, prefix_length=prefix_length)
        except ApiException as e:
            LOGGER.info("Remove VPN Peer CIDRs failed with status code " + str(e.code) + ": " + e.message)

        return response

    def check_specific_peer_cidr(self, vpn_gateway_id, connection_id, prefix_address, prefix_length):
        """
        :param vpn_gateway_id:
        :param connection_id:
        :param prefix_address:
        :param prefix_length:
        :return:
        """
        response = {}
        try:
            response = self.service.check_vpn_gateway_connection_peer_cidr(
                vpn_gateway_id=vpn_gateway_id, id=connection_id,
                cidr_prefix=prefix_address, prefix_length=prefix_length)
        except ApiException as e:
            LOGGER.info("Check VPN Peer CIDRs failed with status code " + str(e.code) + ": " + e.message)

        return response

    def set_peer_cidr(self, vpn_gateway_id, connection_id, prefix_address, prefix_length):
        """
        :param vpn_gateway_id:
        :param connection_id:
        :param prefix_address:
        :param prefix_length:
        :return:
        """
        response = {}
        try:
            response = self.service.add_vpn_gateway_connection_peer_cidr(
                vpn_gateway_id=vpn_gateway_id, id=connection_id,
                cidr_prefix=prefix_address, prefix_length=prefix_length)
        except ApiException as e:
            LOGGER.info("Add VPN Peer CIDRs failed with status code " + str(e.code) + ": " + e.message)

        return response
