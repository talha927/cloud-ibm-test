import logging

from ibm_cloud_sdk_core import ApiException
from ibm_platform_services import GlobalTaggingV1

from ..base_client import BaseClient
from ..consts import VPC_DEFAULT_PAGINATION_LIMIT
from ..urls import GLOBAL_TAG_SERVICE_URL

LOGGER = logging.getLogger(__name__)


class TagsClient(BaseClient):
    """
    Client for Global Tag related API
    """

    def __init__(self, cloud_id):
        super(TagsClient, self).__init__(cloud_id)
        self.global_tagging_service = GlobalTaggingV1(authenticator=self.authenticate_ibm_cloud_account())
        self.global_tagging_service.DEFAULT_SERVICE_URL = GLOBAL_TAG_SERVICE_URL.format()

    def list_tags(self, tag_type="user", limit=VPC_DEFAULT_PAGINATION_LIMIT, attached_to=None):
        """
        Lists all tags in a billing account. Use the attached_to parameter to return the list of
        tags attached to the specified resource.
        """
        params = {
            "limit": limit,
            "tag_type": tag_type,
            "attached_to": attached_to
        }
        response = {}
        try:
            response = self.global_tagging_service.list_tags(**params).get_result()
        except ApiException as e:
            LOGGER.info("List Global Tags failed with status code " + str(e.code) + ": " + e.message)

        return response.get("items", [])

    def attach_tag(self, tag_json, tag_type="user"):
        """
        Attaches one or more tags to one or more resources.
        """
        try:
            return self.global_tagging_service.attach_tag(**tag_json, tag_type=tag_type).get_result()
        except ApiException as e:
            LOGGER.info("Create Global Tags failed with status code " + str(e.code) + ": " + e.message)
            return

    def detach_tag(self, tag_json, tag_type="user"):
        """
        Detaches one or more tags from one or more resources.
        """
        return self.global_tagging_service.detach_tag(**tag_json, tag_type=tag_type)
