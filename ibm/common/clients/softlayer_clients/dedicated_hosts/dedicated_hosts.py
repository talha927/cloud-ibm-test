import logging
from typing import Dict, List

from SoftLayer.exceptions import SoftLayerAPIError
from SoftLayer.managers import DedicatedHostManager, VSManager

from ibm.common.clients.softlayer_clients.base_client import SoftLayerClient
from ibm.common.clients.softlayer_clients.consts import INVALID_API_KEY_CODE, SL_RATE_LIMIT_FAULT_CODE
from ibm.common.clients.softlayer_clients.dedicated_hosts.conts import DEDICATED_HOST_W_INSTANCES_MASK, \
    DEDICATED_HOST_WO_INSTANCES_MASK
from ibm.common.clients.softlayer_clients.exceptions import SLAuthError, SLExecuteError, SLRateLimitExceededError

LOGGER = logging.getLogger(__name__)


class SoftlayerDedicateHostClient(SoftLayerClient):
    """
    Client for Softlayer Dedicated Host related APIs
    """

    def __init__(self, cloud_id):
        super(SoftlayerDedicateHostClient, self).__init__(cloud_id)
        self.vs_manager = VSManager(client=self.client)

    def list_dedicated_hosts(self, instances=False, raw=False) -> List[Dict]:
        """List all Dedicated Hosts on the Account as Dict."""
        from ibm.models.softlayer.resources_models import SoftLayerDedicatedHost
        try:
            client = DedicatedHostManager(self.client)
            dedicated_hosts = self.retry.call(
                client.list_instances,
                mask=DEDICATED_HOST_W_INSTANCES_MASK if instances else DEDICATED_HOST_WO_INSTANCES_MASK
            )
            dedicated_hosts_list = dedicated_hosts
            if not raw:
                dedicated_hosts_list = [
                    SoftLayerDedicatedHost.from_softlayer_json(dedicated_host) for dedicated_host in dedicated_hosts
                ]
        except SoftLayerAPIError as ex:
            LOGGER.info(f"error_message => {ex.reason}")
            if ex.faultCode == SL_RATE_LIMIT_FAULT_CODE:
                raise SLRateLimitExceededError(ex)
            elif ex.faultCode == INVALID_API_KEY_CODE:
                raise SLAuthError(self.cloud_id)
            raise SLExecuteError(ex)
        else:
            return dedicated_hosts_list
