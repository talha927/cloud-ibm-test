import logging

from ibm_cloud_sdk_core import ApiException

from ..base_client import BaseClient
from ..consts import VPC_DEFAULT_PAGINATION_LIMIT
from ..exceptions import IBMInvalidRequestError

LOGGER = logging.getLogger(__name__)


class InstancesClient(BaseClient):
    """
    Client for instance related APIs
    """

    def __init__(self, cloud_id, region):
        super(InstancesClient, self).__init__(cloud_id=cloud_id, region=region)

    def list_instance_profiles(self):
        """
        :return:
        """

        response = {}
        try:
            response = self.service.list_instance_profiles().get_result()
        except ApiException as e:
            LOGGER.info("List Instance Profiles failed with status code " + str(e.code) + ": " + e.message)

        return response.get("profiles", [])

    def get_instance_profile(self, instance_profile_name):
        """
        :param instance_profile_name:
        :return:
        """

        response = {}
        try:
            response = self.service.get_instance_profile(name=instance_profile_name)
        except ApiException as e:
            LOGGER.info("Get Instance Profile failed with status code " + str(e.code) + ": " + e.message)

        return response

    def list_instance_templates(self):
        """
        :return:
        """

        response = {}
        try:
            response = self.service.list_instance_templates().get_result()
        except ApiException as e:
            LOGGER.info("List Instance Templates failed with status code " + str(e.code) + ": " + e.message)

        return response.get("templates", [])

    def create_instance_template(self, template_json):
        """
        :param template_json:
        :return:
        """
        if not isinstance(template_json, dict):
            raise IBMInvalidRequestError("Parameter 'template_json' should be a dictionary")

        # TODO: Create schema for input and validate it
        return self.service.create_instance_template(instance_template_prototype=template_json).get_result()

    def delete_instance_template(self, template_id):
        """
        :param template_id:
        :return:
        """
        return self.service.delete_instance_template(id=template_id)

    def get_instance_template(self, template_id):
        """
        :param template_id:
        :return:
        """

        response = {}
        try:
            response = self.service.get_instance_template(id=template_id).get_result()
        except ApiException as e:
            LOGGER.info("get Instance Template failed with status code " + str(e.code) + ": " + e.message)

        return response

    def update_instance_template(self, template_id, template_json):
        """
        :param template_id:
        :param template_json:
        :return:
        """
        if not isinstance(template_json, dict):
            raise IBMInvalidRequestError("Parameter 'template_json' should be a dictionary")

        # TODO: Create schema for input and validate it

        response = {}
        try:
            response = self.service.update_instance_template(
                id=template_id, instance_template_patch=template_json).get_result()
        except ApiException as e:
            LOGGER.info("Update Instance Template failed with status code " + str(e.code) + ": " + e.message)

        return response

    def create_instance_console_access_token(self, instance_id, console_access_token_json):
        """
        :param instance_id:
        :param console_access_token_json:
        :return:
        """
        if not isinstance(console_access_token_json, dict):
            raise IBMInvalidRequestError("Parameter 'console_access_token_json' should be a dictionary")

        # TODO: Create schema for input and validate it

        response = {}
        try:
            response = self.service.create_instance_console_access_token(**console_access_token_json,
                                                                         instance_id=instance_id).get_result()
        except ApiException as e:
            LOGGER.info(
                "Create Instance Console Access Token failed with status code " + str(e.code) + ": " + e.message)

        return response

    def list_instance_disks(self, instance_id):
        """
        :param instance_id:
        :return:
        """

        response = {}
        try:
            response = self.service.list_instance_disks(instance_id=instance_id).get_result()
        except ApiException as e:
            LOGGER.info("List Instance Disk failed with status code " + str(e.code) + ": " + e.message)

        return response.get("disks", [])

    def get_instance_disk(self, instance_id, disk_id):
        """
        :param instance_id:
        :param disk_id:
        :return:
        """

        response = {}
        try:
            response = self.service.get_instance_disk(instance_id=instance_id, id=disk_id)
        except ApiException as e:
            LOGGER.info("Get Instance Disk failed with status code " + str(e.code) + ": " + e.message)

        return response

    def update_instance_disk(self, instance_id, disk_id, disk_json):
        """
        :param instance_id:
        :param disk_id:
        :param disk_json:
        :return:
        """
        if not isinstance(disk_json, dict):
            raise IBMInvalidRequestError("Parameter 'disk_json' should be a dictionary")

        # TODO: Create schema for input and validate it

        response = {}
        try:
            response = self.service.update_instance_disk(instance_id=instance_id, id=disk_id,
                                                         instance_disk_patch=disk_json).get_result()
        except ApiException as e:
            LOGGER.info("Update Instance Disk failed with status code " + str(e.code) + ": " + e.message)

        return response

    def list_instances(self, resource_group_id=None, name=None, vpc_id=None, vpc_crn=None, vpc_name=None,
                       dedicated_host_id=None, dedicated_host_name=None, dedicated_host_crn=None,
                       limit=VPC_DEFAULT_PAGINATION_LIMIT):
        """
        :param resource_group_id:
        :param name:
        :param vpc_id:
        :param vpc_crn:
        :param vpc_name:
        :param dedicated_host_crn:
        :param dedicated_host_id:
        :param dedicated_host_name:
        :param limit: Number of Resources Per Page
        :return:
        """
        params = {
            "resource_group_id": resource_group_id,
            "name": name,
            "vpc_id": vpc_id,
            "vpc_crn": vpc_crn,
            "vpc_name": vpc_name,
            "dedicated_host_id": dedicated_host_id,
            "dedicated_host_crn": dedicated_host_crn,
            "dedicated_host_name": dedicated_host_name,
            "limit": limit
        }

        response = {}
        try:
            response = self.service.list_instances(**params).get_result()
        except ApiException as e:
            LOGGER.info("List Instances failed with status code " + str(e.code) + ": " + e.message)

        return response.get("instances", [])

    def create_instance(self, instance_json):
        """
        :param instance_json:
        :return:
        """
        if not isinstance(instance_json, dict):
            raise IBMInvalidRequestError("Parameter 'instance_json' should be a dictionary")

        # TODO: Create schema for input and validate it

        return self.service.create_instance(instance_prototype=instance_json).get_result()

    def delete_instance(self, instance_id):
        """
        :param instance_id:
        :return:
        """
        return self.service.delete_instance(id=instance_id)

    def get_instance(self, instance_id):
        """
        :param instance_id:
        :return:
        """

        return self.service.get_instance(id=instance_id).get_result()

    def update_instance(self, instance_id, instance_json):
        """
        :param instance_id:
        :param instance_json:
        :return:
        """
        if not isinstance(instance_json, dict):
            raise IBMInvalidRequestError("Parameter 'instance_json' should be a dictionary")

        # TODO: Create schema for input and validate it

        return self.service.update_instance(id=instance_id, instance_patch=instance_json).get_result()

    def get_instance_initialization(self, instance_id):
        """
        :param instance_id:
        :return:
        """

        response = {}
        try:
            response = self.service.get_instance_initialization(id=instance_id).get_result()
        except ApiException as e:
            LOGGER.info("Get Instance Initialization failed with status code " + str(e.code) + ": " + e.message)

        return response

    def create_instance_action(self, instance_id, instance_action_json):
        """
        :param instance_id:
        :param instance_action_json:
        :return:
        """
        if not isinstance(instance_action_json, dict):
            raise IBMInvalidRequestError("Parameter 'instance_action_json' should be a dictionary")

        # TODO: Create schema for input and validate it

        return self.service.create_instance_action(**instance_action_json, instance_id=instance_id).get_result()

    def list_instance_network_interfaces(self, instance_id):
        """
        :param instance_id:
        :return:
        """

        response = {}
        try:
            response = self.service.list_instance_network_interfaces(instance_id=instance_id)
        except ApiException as e:
            LOGGER.info("List Instance Network interfaces failed with status code " + str(e.code) + ": " + e.message)

        return response.get("network_interfaces", [])

    def create_network_interface(self, instance_id, network_interface_json):
        """
        :param instance_id:
        :param network_interface_json:
        :return:
        """
        if not isinstance(network_interface_json, dict):
            raise IBMInvalidRequestError("Parameter 'network_interface_json' should be a dictionary")

        # TODO: Create schema for input and validate it

        return self.service.create_instance_network_interface(**network_interface_json,
                                                              instance_id=instance_id).get_result()

    def delete_instance_network_interface(self, instance_id, network_interface_id):
        """
        :param instance_id:
        :param network_interface_id:
        :return:
        """
        return self.service.delete_instance_network_interface(instance_id=instance_id, id=network_interface_id)

    def get_instance_network_interface(self, instance_id, network_interface_id):
        """
        :param instance_id:
        :param network_interface_id:
        :return:
        """

        return self.service.get_instance_network_interface(instance_id=instance_id,
                                                           id=network_interface_id).get_result()

    def update_instance_network_interface(self, instance_id, network_interface_id, network_interface_json):
        """
        :param instance_id:
        :param network_interface_id:
        :param network_interface_json:
        :return:
        """
        if not isinstance(network_interface_json, dict):
            raise IBMInvalidRequestError("Parameter 'network_interface_json' should be a dictionary")

        # TODO: Create schema for input and validate it

        response = {}
        try:
            response = self.service.update_instance_network_interface(
                instance_id=instance_id,
                id=network_interface_id,
                network_interface_patch=network_interface_json).get_result()
        except ApiException as e:
            LOGGER.info("Update Instance Network interface failed with status code " + str(e.code) + ": " + e.message)

        return response

    def list_instance_network_interface_floating_ips(self, instance_id, network_interface_id):
        """
        :param instance_id:
        :param network_interface_id:
        :return:
        """
        params = {
            "instance_id": instance_id,
            "network_interface_id": network_interface_id
        }

        response = {}
        try:
            response = self.service.list_instance_network_interface_floating_ips(**params).get_result()
        except ApiException as e:
            LOGGER.info(
                "List Instance Floating IPs interfaces failed with status code " + str(e.code) + ": " + e.message)

        return response.get("floating_ips", [])

    def remove_instance_network_interface_floating_ip(self, instance_id, network_interface_id, floating_ip_id):
        """
        :param instance_id:
        :param network_interface_id:
        :param floating_ip_id:
        :return:
        """
        return self.service.remove_instance_network_interface_floating_ip(
            instance_id=instance_id, network_interface_id=network_interface_id, id=floating_ip_id
        )

    def get_instance_network_interface_floating_ip(self, instance_id, network_interface_id, floating_ip_id):
        """
        :param instance_id:
        :param network_interface_id:
        :param floating_ip_id:
        :return:
        """

        response = {}
        try:
            response = self.service.get_instance_network_interface_floating_ip(
                instance_id=instance_id, network_interface_id=network_interface_id, id=floating_ip_id)
        except ApiException as e:
            LOGGER.info("Get Instance Floating IP interface failed with status code " + str(e.code) + ": " + e.message)

        return response

    def add_instance_network_interface_floating_ip(self, instance_id, network_interface_id, floating_ip_id):
        """
        :param instance_id:
        :param network_interface_id:
        :param floating_ip_id:
        :return:
        """
        return self.service.add_instance_network_interface_floating_ip(
            instance_id=instance_id, network_interface_id=network_interface_id, id=floating_ip_id
        ).get_result()

    def list_instance_volume_attachments(self, instance_id):
        """
        :param instance_id:
        :return:
        """

        response = self.service.list_instance_volume_attachments(instance_id=instance_id).get_result()
        return response.get("volume_attachments", [])

    def create_instance_volume_attachment(self, instance_id, volume_attachment_json):
        """
        :param instance_id:
        :param volume_attachment_json:
        :return:
        """
        if not isinstance(volume_attachment_json, dict):
            raise IBMInvalidRequestError("Parameter 'volume_attachment_json' should be a dictionary")

        # TODO: Create schema for input and validate it

        return self.service.create_instance_volume_attachment(**volume_attachment_json,
                                                              instance_id=instance_id).get_result()

    def delete_instance_volume_attachment(self, instance_id, volume_attachment_id):
        """
        :param instance_id:
        :param volume_attachment_id:
        :return:
        """
        return self.service.delete_instance_volume_attachment(instance_id=instance_id, id=volume_attachment_id)

    def get_instance_volume_attachment(self, instance_id, volume_attachment_id):
        """
        :param instance_id:
        :param volume_attachment_id:
        :return:
        """

        return self.service.get_instance_volume_attachment(instance_id=instance_id,
                                                           id=volume_attachment_id).get_result()

    def update_instance_volume_attachment(self, instance_id, volume_attachment_id, volume_attachment_json):
        """
        :param instance_id:
        :param volume_attachment_id:
        :param volume_attachment_json:
        :return:
        """
        if not isinstance(volume_attachment_json, dict):
            raise IBMInvalidRequestError("Parameter 'volume_attachment_json' should be a dictionary")

        # TODO: Create schema for input and validate it

        response = {}
        try:
            response = self.service.update_instance_volume_attachment(
                instance_id=instance_id, id=volume_attachment_id,
                volume_attachment_patch=volume_attachment_json).get_result()
        except ApiException as e:
            LOGGER.info("Update Instance Volume Attachment failed with status code " + str(e.code) + ": " + e.message)

        return response
