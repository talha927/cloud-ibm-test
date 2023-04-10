from ibm.common.clients.softlayer_clients.base_client import SoftLayerClient
from .consts import NETWORK_GATEWAY_MASK


class SoftlayerNetworkGatewayClient(SoftLayerClient):
    """
    Client for Softlayer Network Gateway related APIs related to Hardware, VLANs etc
    """

    def __init__(self, cloud_id):
        super(SoftlayerNetworkGatewayClient, self).__init__(cloud_id)

    def get_network_gateways(self):
        """
        This method gets the basic data for each softlayer network gateway on an account
        """
        return self.client.call('Account', 'getNetworkGateways', mask=NETWORK_GATEWAY_MASK)
