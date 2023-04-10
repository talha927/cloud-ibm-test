import logging

from SoftLayer.exceptions import SoftLayerAPIError
from SoftLayer.managers import SSLManager, VSManager

from ibm.common.clients.softlayer_clients.base_client import SoftLayerClient
from ibm.common.clients.softlayer_clients.consts import INVALID_API_KEY_CODE, SL_RATE_LIMIT_FAULT_CODE
from ibm.common.clients.softlayer_clients.exceptions import SLAuthError, SLExecuteError, SLRateLimitExceededError

LOGGER = logging.getLogger(__name__)


class SoftlayerSslCertClient(SoftLayerClient):
    """
    Client for Softlayer SSl Certs related APIs
    """

    def __init__(self, cloud_id):
        super(SoftlayerSslCertClient, self).__init__(cloud_id)
        self.vs_manager = VSManager(client=self.client)

    def list_ssl_certs(self) -> dict:
        """A list of dictionaries representing the requested SSL certs."""
        try:
            client = SSLManager(self.client)
            return self.retry.call(client.list_certs)
        except SoftLayerAPIError as ex:
            if ex.faultCode == SL_RATE_LIMIT_FAULT_CODE:
                raise SLRateLimitExceededError(ex)
            elif ex.faultCode == INVALID_API_KEY_CODE:
                raise SLAuthError(self.cloud_id)
            raise SLExecuteError(ex)
