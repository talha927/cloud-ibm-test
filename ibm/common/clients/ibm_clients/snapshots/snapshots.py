import logging

from ibm_cloud_sdk_core import ApiException

from ..base_client import BaseClient
from ..consts import VPC_DEFAULT_PAGINATION_LIMIT
from ..exceptions import IBMInvalidRequestError

LOGGER = logging.getLogger(__name__)


class SnapshotsClient(BaseClient):
    """
    Client for snapshots related APIs
    """

    def __init__(self, cloud_id, region):
        super(SnapshotsClient, self).__init__(cloud_id=cloud_id, region=region)

    def delete_filtered_collection_of_snapshots(self, source_volume_id):
        """
        deletes snapshots with the source volume.
        :param source_volume_id:
        """
        if not source_volume_id:
            raise IBMInvalidRequestError("Parameter 'source_volume_id' cannot be a None")

        return self.service.delete_snapshots(source_volume_id=source_volume_id)

    def list_snapshots(self, resource_group_id=None, name=None, source_volume_id=None, source_volume_crn=None,
                       source_image_id=None, source_image_crn=None, sort="-created_at",
                       limit=VPC_DEFAULT_PAGINATION_LIMIT):
        """
        :param name:
        :param source_volume_id:
        :param source_volume_crn:
        :param resource_group_id:
        :param source_image_id:
        :param source_image_crn:
        :param sort:
        :param limit: Number of Resources Per Page
        :return:
        """
        params = {
            "resource_group_id": resource_group_id,
            "name": name,
            "source_volume_id": source_volume_id,
            "source_volume_crn": source_volume_crn,
            "source_image_id": source_image_id,
            "source_image_crn": source_image_crn,
            "sort": sort,
            "limit": limit
        }

        response = self.service.list_snapshots(**params).get_result()
        return response.get("snapshots", [])

    def create_snapshot(self, snapshot_json):
        """
        :param snapshot_json:
        :return:
        """

        if not isinstance(snapshot_json, dict):
            raise IBMInvalidRequestError("Parameter 'snapshot_json' should be a dictionary")

        return self.service.create_snapshot(snapshot_prototype=snapshot_json).get_result()

    def delete_snapshot(self, snapshot_id):
        """
        :param snapshot_id:
        """
        return self.service.delete_snapshot(id=snapshot_id)

    def get_snapshot(self, snapshot_id):
        """

        :param snapshot_id:
        :return:
        """
        return self.service.get_snapshot(id=snapshot_id).get_result()

    def update_snapshot(self, snapshot_id, snapshot_json):
        """

        :param snapshot_id:
        :param snapshot_json:
        :return:
        """
        if not isinstance(snapshot_json, dict):
            raise IBMInvalidRequestError("Parameter 'snapshot_json' should be a dictionary")

        response = {}
        try:
            response = self.service.update_snapshot(snapshot_id=snapshot_id, snapshot_patch=snapshot_json).get_result()
        except ApiException as e:
            LOGGER.info("Update Snapshot failed with status code " + str(e.code) + ": " + e.message)

        return response
