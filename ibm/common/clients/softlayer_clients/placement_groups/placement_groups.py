import logging

from SoftLayer.exceptions import SoftLayerAPIError
from SoftLayer.managers import PlacementManager

from ibm.common.clients.softlayer_clients.base_client import SoftLayerClient
from ibm.common.clients.softlayer_clients.consts import INVALID_API_KEY_CODE, SL_RATE_LIMIT_FAULT_CODE
from ibm.common.clients.softlayer_clients.exceptions import SLAuthError, SLExecuteError, SLRateLimitExceededError
from ibm.common.clients.softlayer_clients.placement_groups.consts import PLACEMENT_GROUP_W_INSTANCES_MASK
from ibm.models.softlayer.resources_models import SoftlayerPlacementGroup

LOGGER = logging.getLogger(__name__)


class SoftlayerPlacementGroupClient(SoftLayerClient):
    """
    Client for Softlayer Placement Group related APIs.
    """

    def __init__(self, cloud_id):
        super(SoftlayerPlacementGroupClient, self).__init__(cloud_id)
        self.pg_manager = PlacementManager(self.client)

    def list_placement_groups(self):
        """List all Placement Groups on the Account"""
        try:
            placement_groups = self.retry.call(
                self.pg_manager.list,
                mask=PLACEMENT_GROUP_W_INSTANCES_MASK
            )

            placement_groups_list = [
                SoftlayerPlacementGroup.from_softlayer_json(placement_group) for placement_group in placement_groups
            ]
        except SoftLayerAPIError as ex:
            LOGGER.info(f"error_message => {ex.reason}")
            if ex.faultCode == SL_RATE_LIMIT_FAULT_CODE:
                raise SLRateLimitExceededError(ex)
            elif ex.faultCode == INVALID_API_KEY_CODE:
                raise SLAuthError(self.cloud_id)
            raise SLExecuteError(ex)
        else:
            return placement_groups_list
