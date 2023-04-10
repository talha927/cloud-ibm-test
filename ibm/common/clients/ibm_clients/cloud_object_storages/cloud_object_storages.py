"""
This file contains Client for S3 Buckets related APIs
"""
import requests

from ibm.common.consts import COS_FILE_EXTENSIONS, IBM_COS_BUCKET_HREF
from .paths import LIST_BUCKET_OBJECTS_PATH, LIST_BUCKETS_PATH
from ..base_client import BaseClient
from ..urls import BUCKETS_URL_TEMPLATE


class COSClient(BaseClient):
    """
    Client for S3 Buckets related APIs
    """

    def __init__(self, cloud_id):
        super(COSClient, self).__init__(cloud_id)

    def list_cos_buckets(self, region, ibm_service_instance_id, extended=None):
        """
        :param region:
        :param ibm_service_instance_id:
        :param extended:
        :return:
        """
        params = {
            "extended": extended
        }

        request = requests.Request(
            "GET", BUCKETS_URL_TEMPLATE.format(region=region, path=LIST_BUCKETS_PATH), params=params
        )
        request.headers = {"ibm-service-instance-id": ibm_service_instance_id}

        response = self._execute_request(request, "COS")
        if not response["ListAllMyBucketsResult"].get("Buckets"):
            return list()

        if isinstance(response["ListAllMyBucketsResult"]["Buckets"]["Bucket"], dict):
            buckets = list()
            buckets.append(response["ListAllMyBucketsResult"]["Buckets"]["Bucket"])
            return buckets

        return response["ListAllMyBucketsResult"]["Buckets"]["Bucket"]

    def list_cos_bucket_objects(self, region, bucket, list_type=2, delimiter=None,
                                encoding_type=None, max_keys=1000, prefix=None, continuation_token=None,
                                fetch_owner=False, start_after=None):
        """
        :param region:
        :param list_type: Possible values include [2]. Used for v2 api.
        :param bucket:
        :param delimiter:
        :param encoding_type:
        :param prefix:
        :param max_keys:
        :param continuation_token:
        :param fetch_owner:
        :param start_after:
        :return:
        """
        assert list_type == 2, "List type value not accepted. Possible values [2]."

        params = {
            "list-type": list_type,
            "delimiter": delimiter,
            "encoding-type": encoding_type,
            "max-keys": max_keys,
            "continuation-token": continuation_token,
            "fetch-owner": fetch_owner,
            "start-after": start_after,
            "prefix": prefix,
        }

        request = requests.Request(
            "GET", BUCKETS_URL_TEMPLATE.format(region=region, path=LIST_BUCKET_OBJECTS_PATH.format(bucket=bucket)),
            params=params
        )

        response = self._execute_request(request, "COS")
        bucket_objects = list()
        if response["ListBucketResult"].get("Contents"):
            bucket_objects = response["ListBucketResult"]["Contents"]
            if not isinstance(bucket_objects, list):
                bucket_objects = [bucket_objects]

        for bucket_object in bucket_objects:
            bucket_object["href"] = IBM_COS_BUCKET_HREF.format(region=region, bucket=bucket,
                                                               object=bucket_object["Key"])
            object_type = bucket_object["Key"].rsplit(".", 1)[-1]
            if object_type not in COS_FILE_EXTENSIONS:
                object_type = None

            bucket_object["object_type"] = object_type

        return bucket_objects

    def create_cos_bucket(self, region, ibm_service_instance_id, bucket_name):
        """
        :param region:
        :param ibm_service_instance_id:
        :param bucket_name: should not start with cosv1- or account- or less than 3 char
        :return:
        """
        "https://s3.{region}.cloud-object-storage.appdomain.cloud"
        request = requests.Request(
            "PUT", f"https://s3.{region}.cloud-object-storage.appdomain.cloud/{bucket_name}"
        )

        request.headers = {"ibm-service-instance-id": ibm_service_instance_id}

        response = self._execute_request(request, "COS")
        return response

    def delete_cos_bucket(self, region, ibm_service_instance_id, bucket_name):
        """
        :param region:
        :param ibm_service_instance_id:
        :param bucket_name: should not start with cosv1- or account- or less than 3 char
        :return:
        """
        request = requests.Request(
            "DELETE", f"https://s3.{region}.cloud-object-storage.appdomain.cloud/{bucket_name}"
        )

        request.headers = {"ibm-service-instance-id": ibm_service_instance_id}

        response = self._execute_request(request, "COS")
        return response
