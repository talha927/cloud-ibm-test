import logging

from SoftLayer.exceptions import SoftLayerAPIError
from SoftLayer.managers import LoadBalancerManager, VSManager

from ibm.common.clients.softlayer_clients.base_client import SoftLayerClient
from ibm.common.clients.softlayer_clients.consts import INVALID_API_KEY_CODE, SL_RATE_LIMIT_FAULT_CODE
from ibm.common.clients.softlayer_clients.exceptions import SLAuthError, SLExecuteError, SLRateLimitExceededError
from ibm.common.clients.softlayer_clients.load_balancer.consts import LOAD_BALANCER_MASK
from ibm.models.softlayer.resources_models import SoftLayerBackendPool, SoftLayerListener, SoftLayerLoadBalancer, \
    SoftLayerPoolHealthMonitor, SoftLayerPoolMember

LOGGER = logging.getLogger(__name__)


class SoftlayerLoadBalancerClient(SoftLayerClient):
    """
    Client for Softlayer Load balancers related APIs
    """

    def __init__(self, cloud_id):
        super(SoftlayerLoadBalancerClient, self).__init__(cloud_id)
        self.vs_manager = VSManager(client=self.client)

    def list_load_balancers(self, vs_instances=None) -> list:
        """Returns a list of IBM Cloud Load balancers"""
        load_balancers_list = list()
        try:
            client = LoadBalancerManager(client=self.client)
            load_balancers = self.retry.call(client.get_lbaas, mask=LOAD_BALANCER_MASK)

        except SoftLayerAPIError as ex:
            if ex.faultCode == SL_RATE_LIMIT_FAULT_CODE:
                raise SLRateLimitExceededError(ex)
            elif ex.faultCode == INVALID_API_KEY_CODE:
                raise SLAuthError(self.cloud_id)
            raise SLExecuteError(ex)

        private_ip_to_instance_dict = {}
        private_ips = []
        for instance in vs_instances:
            for interface in instance.network_interfaces:
                private_ip_to_instance_dict[interface.private_ip] = instance
                private_ips.append(interface.private_ip)

        for lb in load_balancers:
            pools_list, subnets_list = list(), list()
            sl_load_balancer = SoftLayerLoadBalancer(lb["name"], lb["isPublic"], lb["address"], lb["isDataLogEnabled"])
            for listener in lb.get("listeners", []):
                #  TODO:
                #   We don't have support for HTTPS LBs for now. HTTPS LBs use certificate_instance.
                if listener.get("protocol").lower() == "https":
                    continue

                sl_listener = SoftLayerListener(
                    protocol=listener.get("protocol"), port=listener.get("protocolPort"),
                    connection_limit=listener.get("connectionLimit"))

                if listener.get("defaultPool"):
                    sl_pool = SoftLayerBackendPool(
                        port=listener["defaultPool"].get("protocolPort"),
                        protocol=listener["defaultPool"].get("protocol"),
                        algorithm=listener["defaultPool"].get("loadBalancingAlgorithm"))

                    if listener["defaultPool"].get("sessionAffinity"):
                        sl_pool.session_persistence = listener["defaultPool"]["sessionAffinity"].get("type")
                    if listener["defaultPool"].get("healthMonitor"):
                        sl_health_monitor = SoftLayerPoolHealthMonitor(
                            listener["defaultPool"]["healthMonitor"].get("maxRetries"),
                            listener["defaultPool"]["healthMonitor"].get("timeout"),
                            listener["defaultPool"]["healthMonitor"].get("monitorType"),
                            listener["defaultPool"]["healthMonitor"].get("urlPath"),
                            listener["defaultPool"]["healthMonitor"].get("interval"))
                        sl_pool.health_monitor = sl_health_monitor

                    for member in listener["defaultPool"].get("members", []):
                        sl_pool_mem = SoftLayerPoolMember(
                            weight=member.get("weight"), port=listener.get("protocolPort"),
                            ip=member.get("address"))

                        if not member.get("address") in private_ips:
                            continue

                        instance = private_ip_to_instance_dict.get(member.get("address"))
                        if instance:
                            for network_interface in instance.network_interfaces:
                                if not network_interface.subnet:
                                    continue

                                subnets_list.append(network_interface.subnet)
                                sl_pool_mem.network_interface = network_interface

                        sl_pool.pool_members.append(sl_pool_mem)
                    sl_listener.backend_pool = sl_pool
                    pools_list.append(sl_pool)
                sl_load_balancer.listeners.append(sl_listener)

            sl_load_balancer.pools = pools_list
            sl_load_balancer.subnets = subnets_list
            load_balancers_list.append(sl_load_balancer)

        return load_balancers_list
