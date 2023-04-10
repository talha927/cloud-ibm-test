import logging

from SoftLayer.exceptions import SoftLayerAPIError
from SoftLayer.managers import NetworkManager, VSManager

from ibm.common.clients.softlayer_clients.base_client import SoftLayerClient
from ibm.common.clients.softlayer_clients.consts import INVALID_API_KEY_CODE, SL_RATE_LIMIT_FAULT_CODE
from ibm.common.clients.softlayer_clients.exceptions import SLAuthError, SLExecuteError, SLRateLimitExceededError
from ibm.models.softlayer.resources_models import SoftLayerSecurityGroup, SoftLayerSecurityGroupRule

LOGGER = logging.getLogger(__name__)


class SoftlayerSecurityGroupClient(SoftLayerClient):
    """
    Client for Softlayer security group related APIs
    """

    def __init__(self, cloud_id):
        super(SoftlayerSecurityGroupClient, self).__init__(cloud_id)
        self.vs_manager = VSManager(client=self.client)

    def list_security_groups(self) -> list:
        """List all the Security Groups within an Account."""
        sl_security_groups_list = list()
        try:
            security_groups = self.retry.call(
                NetworkManager(self.client).list_securitygroups, mask="mask{mask}".format(
                    mask="[networkComponentBindings, rules]"))
            for security_group in security_groups:
                sl_security_group = SoftLayerSecurityGroup(name=security_group["name"])
                for rule in security_group.get("rules", []):
                    if rule["ethertype"] == "IPv6":
                        continue

                    sl_security_group_rule = SoftLayerSecurityGroupRule(
                        direction=rule["direction"], protocol=rule.get("protocol", "all"),
                        port_max=rule.get("portRangeMax"), port_min=rule.get("portRangeMin"))

                    if rule.get("remoteIp") and "/" in rule.get("remoteIp"):
                        sl_security_group_rule.rule_type = "cidr_block"
                        sl_security_group_rule.cidr_block = rule.get("remoteIp")

                    elif rule.get("remoteIp"):
                        sl_security_group_rule.rule_type = "address"
                        sl_security_group_rule.address = rule.get("remoteIp")

                    sl_security_group.rules.append(sl_security_group_rule)
                sl_security_groups_list.append(sl_security_group)

        except SoftLayerAPIError as ex:
            if ex.faultCode == SL_RATE_LIMIT_FAULT_CODE:
                raise SLRateLimitExceededError(ex)
            elif ex.faultCode == INVALID_API_KEY_CODE:
                raise SLAuthError(self.cloud_id)
            raise SLExecuteError(ex)
        else:
            return sl_security_groups_list
