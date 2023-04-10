import logging

from SoftLayer.exceptions import SoftLayerAPIError
from SoftLayer.managers import SshKeyManager, VSManager

from ibm.common.clients.softlayer_clients.base_client import SoftLayerClient
from ibm.common.clients.softlayer_clients.consts import INVALID_API_KEY_CODE, SL_RATE_LIMIT_FAULT_CODE
from ibm.common.clients.softlayer_clients.exceptions import SLAuthError, SLExecuteError, SLRateLimitExceededError

LOGGER = logging.getLogger(__name__)


class SoftlayerSshKeyClient(SoftLayerClient):
    """
    Client for Softlayer SSH Keys related APIs
    """

    def __init__(self, cloud_id):
        super(SoftlayerSshKeyClient, self).__init__(cloud_id)
        self.vs_manager = VSManager(client=self.client)

    def list_ssh_keys(self) -> list:
        """Lists all Ssl Keys on the Account."""
        try:
            client = SshKeyManager(self.client)
            return self.retry.call(client.list_keys)
        except SoftLayerAPIError as ex:
            if ex.faultCode == SL_RATE_LIMIT_FAULT_CODE:
                raise SLRateLimitExceededError(ex)
            elif ex.faultCode == INVALID_API_KEY_CODE:
                raise SLAuthError(self.cloud_id)
            raise SLExecuteError(ex)
