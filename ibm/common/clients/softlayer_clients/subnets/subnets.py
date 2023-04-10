import logging

from SoftLayer.exceptions import SoftLayerAPIError
from SoftLayer.managers import NetworkManager, \
    VSManager

from ibm.common.clients.softlayer_clients.base_client import SoftLayerClient
from ibm.common.clients.softlayer_clients.consts import INVALID_API_KEY_CODE, SL_RATE_LIMIT_FAULT_CODE
from ibm.common.clients.softlayer_clients.exceptions import SLAuthError, SLExecuteError, SLRateLimitExceededError
from ibm.common.clients.softlayer_clients.subnets.consts import SUBNET_MASK
from ibm.models.softlayer.resources_models import SoftLayerSubnet

LOGGER = logging.getLogger(__name__)


class SoftlayerSubnetClient(SoftLayerClient):
    """
    Client for Softlayer Subnet related APIs
    """

    def __init__(self, cloud_id):
        super(SoftlayerSubnetClient, self).__init__(cloud_id)
        self.vs_manager = VSManager(client=self.client)

    def list_private_subnets(self, vlan_no=None, network_identifier=None) -> list:
        """List all the private Subnetworks associated with an Account."""

        subnets_list = list()
        try:
            client = NetworkManager(self.client)
            vlans = self.retry.call(client.list_vlans,
                                    filter={"networkVlans": {"subnets": {"addressSpace": {"operation": "PRIVATE"}}}},
                                    mask="mask{subnets}".format(subnets=SUBNET_MASK))

            # TODO: see the use for `vlanNumber`
            for vlan in vlans:
                if vlan_no and vlan_no != vlan.get("vlanNumber"):
                    continue

                vlan_name = "{}-{{}}".format(vlan.get("name") or "subnet-{}".format(vlan.get("vlanNumber")))
                count = 1
                for subnet in vlan.get("subnets", []):
                    sl_subnet = SoftLayerSubnet(
                        name=vlan_name.format(count), vif_id=vlan.get("vlanNumber"),
                        address="{}/{}".format(subnet.get("gateway"), subnet.get("cidr")),
                        network_id=subnet["networkIdentifier"])
                    count += 1
                    if not (network_identifier and network_identifier != sl_subnet.network_id):
                        subnets_list.append(sl_subnet)

        except SoftLayerAPIError as ex:
            if ex.faultCode == SL_RATE_LIMIT_FAULT_CODE:
                raise SLRateLimitExceededError(ex)
            elif ex.faultCode == INVALID_API_KEY_CODE:
                raise SLAuthError(self.cloud_id)
            raise SLExecuteError(ex)

        return subnets_list
