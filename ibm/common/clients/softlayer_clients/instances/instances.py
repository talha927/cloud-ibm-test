from SoftLayer import SoftLayerAPIError
from SoftLayer.managers import VSManager

from ibm.common.clients.softlayer_clients.base_client import SoftLayerClient
from ibm.common.clients.softlayer_clients.consts import INVALID_API_KEY_CODE, SL_RATE_LIMIT_FAULT_CODE
from ibm.common.clients.softlayer_clients.exceptions import SLAuthError, SLExecuteError, SLRateLimitExceededError
from ibm.common.clients.softlayer_clients.instances.consts import GET_INSTANCE_MASK, VIRTUAL_SERVER_MASK
from ibm.common.clients.softlayer_clients.instances.utils import get_auto_scale_group, get_ibm_instance_profile, \
    list_network_attached_storages
from ibm.models.softlayer.resources_models import SoftLayerImage, SoftLayerInstance, SoftLayerInstanceProfile, \
    SoftLayerNetworkInterface, SoftLayerSecurityGroup, SoftLayerSecurityGroupRule, SoftLayerSshKey, SoftLayerVolume


class SoftlayerInstanceClient(SoftLayerClient):
    """
    Client for Softlayer Instance related APIs
    """

    def __init__(self, cloud_id):
        super(SoftlayerInstanceClient, self).__init__(cloud_id)
        self.vs_manager = VSManager(client=self.client)

    def __parse_to_softlayer(self, vs_instance, subnets=None, address=None, ssh_keys_required=True,
                             security_groups_required=True):
        from ibm.common.clients.softlayer_clients import SoftlayerSubnetClient
        if not (vs_instance["status"].get("keyName") == "ACTIVE" and vs_instance.get("operatingSystem")):
            return

        sl_instance = SoftLayerInstance.from_softlayer_json(instance_json=vs_instance)
        sl_instance.auto_scale_group = get_auto_scale_group(vs_instance)
        sl_instance.network_attached_storages = list_network_attached_storages(
            vs_instance.get('allowedNetworkStorage'))
        instance_profile, family = get_ibm_instance_profile(vs_instance["maxCpu"], vs_instance["maxMemory"])
        sl_instance.instance_profile = SoftLayerInstanceProfile(
            name=instance_profile, family=family, max_cpu=vs_instance['maxCpu'], max_memory=vs_instance['maxMemory'])

        os = vs_instance["operatingSystem"]["softwareLicense"]["softwareDescription"]
        sl_instance.image = SoftLayerImage.from_softlayer_json(operating_system=os)

        if ssh_keys_required:
            sl_instance.ssh_keys.extend([
                SoftLayerSshKey.from_softlayer_json(ssh_key).to_ibm() for ssh_key in vs_instance.get("sshKeys", [])
            ])
        volume_index = 0
        for volume in vs_instance.get("blockDevices", []):
            if not volume.get("diskImage"):
                continue

            SWAP = "SWAP" in volume["diskImage"].get("description", "")
            MB = "MB" == volume["diskImage"].get("units")
            CLOUD_INIT_DISK = 64 == volume["diskImage"].get("capacity")
            if not ((CLOUD_INIT_DISK and MB) or SWAP):
                volume_name = volume['diskImage']['name'] if volume['bootableFlag'] \
                    else f"{sl_instance.name}-{volume['diskImage'].get('name')}"
                sl_instance.volume_attachments.append(
                    SoftLayerVolume.from_softlayer_json(name=volume_name, volume_json=volume,
                                                        volume_index=volume_index))
                volume_index += 1

        for network in vs_instance.get("networkComponents", []):
            if not network.get("primarySubnet"):
                continue

            interface_name = "{name}{port}".format(name=network.get("name"), port=network.get("port"))
            sl_interface = SoftLayerNetworkInterface(interface_name, network.get("primaryIpAddress"))

            if interface_name == "eth0":
                sl_interface.is_primary = True
            if network["primarySubnet"].get("addressSpace") == "PUBLIC":
                sl_interface.is_public_interface = True

            if subnets:
                attached_subnet = [
                    subnet for subnet in subnets
                    if subnet.vif_id == network["networkVlan"].get("vlanNumber") and subnet.network_id == network[
                        "primarySubnet"].get("networkIdentifier")]
            else:
                subnet_client = SoftlayerSubnetClient(self.cloud_id)
                attached_subnet = subnet_client.list_private_subnets(
                    vlan_no=network["networkVlan"].get("vlanNumber"),
                    network_identifier=network["primarySubnet"].get("networkIdentifier"))

            if attached_subnet:
                sl_interface.subnet = attached_subnet[0]
            if security_groups_required:
                for security_group in network.get("securityGroupBindings", []):
                    if not security_group.get("securityGroup"):
                        continue

                    if not security_group["securityGroup"].get("name"):
                        continue

                    sl_security_group = SoftLayerSecurityGroup(name=security_group["securityGroup"]["name"])
                    for rule in security_group["securityGroup"].get("rules", []):
                        if rule["ethertype"] == "IPv6":
                            continue

                        sl_security_group_rule = SoftLayerSecurityGroupRule(
                            direction=rule["direction"], protocol=rule.get("protocol", "all"),
                            port_max=rule.get("portRangeMax"), port_min=rule.get("portRangeMin"),
                            address=network["primaryIpAddress"])

                        sl_security_group.rules.append(sl_security_group_rule)
                    sl_interface.security_groups.append(sl_security_group)
                sl_instance.network_interfaces.append(sl_interface)
            else:
                sl_instance.network_interfaces.append(sl_interface)
        if not (address and address not in [interface.private_ip
                                            for interface in sl_instance.network_interfaces]):
            return sl_instance

    def list_instances(self, mask=VIRTUAL_SERVER_MASK, to_ibm=False):
        """Retrieve a list of all virtual servers on the Account."""
        instances_list = []
        try:
            instances = self.retry.call(self.vs_manager.list_instances, mask=mask)
        except SoftLayerAPIError as ex:
            if ex.faultCode == SL_RATE_LIMIT_FAULT_CODE:
                raise SLRateLimitExceededError(ex)
            elif ex.faultCode == INVALID_API_KEY_CODE:
                raise SLAuthError(self.cloud_id)
            raise SLExecuteError(ex)
        if not to_ibm:
            return instances
        for instance in instances:
            instance_obj = self.__parse_to_softlayer(instance, subnets=False, address=False,
                                                     ssh_keys_required=False,
                                                     security_groups_required=False)
            if instance_obj:
                instances_list.append(instance_obj)
        return instances_list

    def get_instance_by_id(self, instance_id, mask=GET_INSTANCE_MASK, to_ibm=False):
        """
        Get a softlayer instance, with provided ID
        :return:
        """
        try:
            instance = self.retry.call(self.vs_manager.get_instance, instance_id=instance_id, mask=mask)
            if to_ibm:
                instance = self.__parse_to_softlayer(
                    vs_instance=instance, subnets=False, address=False, ssh_keys_required=False,
                    security_groups_required=False
                )
                softlayer_instance = {"volume_attachments": []}
                softlayer_instance["original_image"] = instance.image.to_json()
                softlayer_instance["network_attached_storages"] = instance.network_attached_storages
                softlayer_instance["instance_type"] = instance.instance_type
                softlayer_instance["data_center"] = instance.data_center
                softlayer_instance["instance_id"] = instance.instance_id
                softlayer_instance["name"] = instance.name
                softlayer_instance["instance_profile"] = instance.instance_profile.to_json()

                for v in instance.to_ibm().volume_attachments.all():
                    if v.type_ == "boot":
                        softlayer_instance["boot_volume_attachment"] = v.to_json_body()
                    if v.type_ == "data":
                        softlayer_instance["volume_attachments"].append(v.to_json_body())
                return softlayer_instance

        except SoftLayerAPIError as ex:
            if ex.faultCode == SL_RATE_LIMIT_FAULT_CODE:
                raise SLRateLimitExceededError(ex)
            elif ex.faultCode == INVALID_API_KEY_CODE:
                raise SLAuthError(self.cloud_id)
            raise SLExecuteError(ex)
        else:
            return instance

    def create_instance(self, instance_body):
        """
        Create SoftLayer Instance
        return:
        """
        try:
            return self.retry.call(self.vs_manager.create_instance, **instance_body)
        except SoftLayerAPIError as ex:
            if ex.faultCode == SL_RATE_LIMIT_FAULT_CODE:
                raise SLRateLimitExceededError(ex)
            elif ex.faultCode == INVALID_API_KEY_CODE:
                raise SLAuthError(self.cloud_id)
            raise SLExecuteError(ex)

    def wait_instance_for_ready(self, instance_id, limit=10):
        try:
            return self.vs_manager.wait_for_ready(instance_id, limit=limit)
        except SoftLayerAPIError as ex:
            if ex.faultCode == SL_RATE_LIMIT_FAULT_CODE:
                return False
            elif ex.faultCode == INVALID_API_KEY_CODE:
                raise SLAuthError(self.cloud_id)
            raise SLExecuteError(ex)

    def capture_image(self, instance_id, image_name, additional_disks=False, notes=None):
        """
        Create and capture image template of an image belonging to classical VSI
        :return:
        """
        try:
            return self.retry.call(self.vs_manager.capture, instance_id, image_name, additional_disks, notes)
        except SoftLayerAPIError as ex:
            if ex.faultCode == SL_RATE_LIMIT_FAULT_CODE:
                raise SLRateLimitExceededError(ex)
            elif ex.faultCode == INVALID_API_KEY_CODE:
                raise SLAuthError(self.cloud_id)
            raise SLExecuteError(ex)

    def delete_instance(self, instance_id):
        """
        Delete instance from Classical Infrastructure
        :param instance_id: Classical Instance ID for the image
        :return:
        """
        try:
            return self.retry.call(self.vs_manager.cancel_instance, instance_id)
        except SoftLayerAPIError as ex:
            if ex.faultCode == SL_RATE_LIMIT_FAULT_CODE:
                raise SLRateLimitExceededError(ex)
            elif ex.faultCode == INVALID_API_KEY_CODE:
                raise SLAuthError(self.cloud_id)
            raise SLExecuteError(ex)

    def list_virtual_servers(self, address=None, subnets=None, ssh_keys_required=True,
                             security_groups_required=True):
        """Retrieve a list of all virtual servers on the Account."""
        details = {'address': address, 'subnets': subnets, 'ssh_keys_required': ssh_keys_required,
                   'security_groups_required': security_groups_required}
        instances_list = []
        self.vs_manager = VSManager(client=self.client)
        try:
            instances = self.retry.call(self.vs_manager.list_instances, mask=VIRTUAL_SERVER_MASK)
        except SoftLayerAPIError as ex:
            if ex.faultCode == SL_RATE_LIMIT_FAULT_CODE:
                raise SLRateLimitExceededError(ex)
            elif ex.faultCode == INVALID_API_KEY_CODE:
                raise SLAuthError(self.cloud_id)
            raise SLExecuteError(ex)
        else:
            for instance in instances:
                instance_obj = self.__parse_to_softlayer(instance, **details)
                if instance_obj:
                    instances_list.append(instance_obj)
            return instances_list
