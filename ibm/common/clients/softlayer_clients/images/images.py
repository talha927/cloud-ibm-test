from dateutil import parser
from SoftLayer import ImageManager, SoftLayerAPIError

from ibm.common.clients.softlayer_clients.base_client import SoftLayerClient
from ibm.common.clients.softlayer_clients.consts import INVALID_API_KEY_CODE, SL_RATE_LIMIT_FAULT_CODE
from ibm.common.clients.softlayer_clients.exceptions import SLAuthError, SLExecuteError, SLRateLimitExceededError
from ibm.common.clients.softlayer_clients.images.consts import IDNameImageMask, IMAGE_MASK


class SoftlayerImageClient(SoftLayerClient):
    """
    Client for Softlayer Images related APIs
    """

    def __init__(self, cloud_id):
        super(SoftlayerImageClient, self).__init__(cloud_id)
        self.image_manager = ImageManager(client=self.client)

    def get_classic_image_name(self, image_name):
        """concatenate an integer value if this image already exists"""
        try:
            private_images = self.retry.call(self.image_manager.list_private_images, name=image_name)
            num = 1
            while True:
                if image_name not in [image.get("name") for image in private_images]:
                    return image_name
                image_name = "-".join([image_name, str(num)])
                num += 1

        except SoftLayerAPIError as ex:
            if ex.faultCode == SL_RATE_LIMIT_FAULT_CODE:
                raise SLRateLimitExceededError(ex)
            elif ex.faultCode == INVALID_API_KEY_CODE:
                raise SLAuthError(self.cloud_id)
            raise SLExecuteError(ex)

    def list_private_images_name(self):
        """List all private images don't have any active transaction the Account as List of objects."""
        image_list = list()
        try:
            images = self.retry.call(self.image_manager.list_private_images, mask=IDNameImageMask)
            for image in images:
                if not image.get("children"):
                    continue

                image_child = image["children"][0]
                if image_child.get('transactionId'):
                    continue

                if image_child.get("activeTransaction"):
                    continue

                if not image_child.get("blockDevices"):
                    continue

                block_device = image_child["blockDevices"][0]
                if not block_device.get("diskImage"):
                    continue

                disk_image = block_device.get("diskImage")
                if not disk_image.get('softwareReferences'):
                    continue

                software_reference = disk_image["softwareReferences"][0]
                if not (software_reference.get("softwareDescription") and software_reference.get(
                        "softwareDescription").get("longDescription")):
                    continue

                image_name = software_reference.get("softwareDescription").get("longDescription")
                image_list.append({
                    "classic_image_id": image.get('id'),
                    "classic_image_name": image.get('name'),
                    "operating_systems": [],
                    "image_name": image_name
                })
        except SoftLayerAPIError as ex:
            if ex.faultCode == SL_RATE_LIMIT_FAULT_CODE:
                raise SLRateLimitExceededError(ex)
            elif ex.faultCode == INVALID_API_KEY_CODE:
                raise SLAuthError(self.cloud_id)
            raise SLExecuteError(ex)
        else:
            return image_list

    def list_images(self, mask=IMAGE_MASK):
        """List all private and public images on the Account as Dict."""
        try:
            return {
                "private_images": self.retry.call(self.image_manager.list_private_images, mask=mask),
                "public_images": self.retry.call(self.image_manager.list_public_images, mask=mask),
            }
        except SoftLayerAPIError as ex:
            if ex.faultCode == SL_RATE_LIMIT_FAULT_CODE:
                raise SLRateLimitExceededError(ex)
            elif ex.faultCode == INVALID_API_KEY_CODE:
                raise SLAuthError(self.cloud_id)
            raise SLExecuteError(ex)

    def get_image_by_name(self, image_name, create_date=None):
        """
        Get image on the basis of image name.
        :param image_name: Name of the image.
        :param create_date: Creation Date of image
        :return: Return the filtered image on the basis of above params.
        """
        try:
            # TODO check if we can pass created_date to ibm apis or not
            images = self.retry.call(self.image_manager.list_private_images, name=image_name)
            if not images:
                return
            if not create_date or len(images) == 1:
                return images[0]
            else:
                try:
                    time_list = [
                        abs((parser.parse(image["createDate"]) - parser.parse(create_date)).total_seconds()) for
                        image in images]
                    minimum_index = time_list.index(min(time_list))
                    return images[minimum_index]
                except (parser.ParserError, KeyError, IndexError):
                    return images[0]

        except SoftLayerAPIError as ex:
            if ex.faultCode == SL_RATE_LIMIT_FAULT_CODE:
                raise SLRateLimitExceededError(ex)
            elif ex.faultCode == INVALID_API_KEY_CODE:
                raise SLAuthError(self.cloud_id)
            raise SLExecuteError(ex)

    def get_image_by_id(self, image_id):
        """
        Get image on the basis of image id.
        :param image_id: Classical ID of the image.
        :return: Return the filtered image on the basis of above params.
        """
        try:
            return self.retry.call(self.image_manager.get_image, image_id=image_id)
        except SoftLayerAPIError as ex:
            if ex.faultCode == SL_RATE_LIMIT_FAULT_CODE:
                raise SLRateLimitExceededError(ex)
            elif ex.faultCode == INVALID_API_KEY_CODE:
                raise SLAuthError(self.cloud_id)
            raise SLExecuteError(ex)

    def export_image(self, image_id, cos_url, api_key):
        """
        Export Image template from Classic to specified COS
        :return:
        """
        try:
            self.image_manager = ImageManager(self.client)
            return self.retry.call(self.image_manager.export_image_to_uri, image_id, cos_url, api_key)
        except SoftLayerAPIError as ex:
            if ex.faultCode == SL_RATE_LIMIT_FAULT_CODE:
                raise SLRateLimitExceededError(ex)
            elif ex.faultCode == INVALID_API_KEY_CODE:
                raise SLAuthError(self.cloud_id)
            raise SLExecuteError(ex)

    def delete_image(self, image_id):
        """
        Delete image template from Classical Infrastructure
        :param image_id: Classical Image ID for the image
        :return:
        """
        try:
            self.image_manager = ImageManager(self.client)
            return self.retry.call(self.image_manager.delete_image, image_id)
        except SoftLayerAPIError as ex:
            if ex.faultCode == SL_RATE_LIMIT_FAULT_CODE:
                raise SLRateLimitExceededError(ex)
            elif ex.faultCode == INVALID_API_KEY_CODE:
                raise SLAuthError(self.cloud_id)
            raise SLExecuteError(ex)
