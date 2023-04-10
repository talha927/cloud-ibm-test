"""
Base client to inherit for all the clients
"""
import json

import requests
import xmltodict
from ibm_cloud_sdk_core.authenticators import IAMAuthenticator
from ibm_vpc import VpcV1
from requests.exceptions import ConnectionError, ReadTimeout, RequestException

from ibm import get_db_session, LOGGER
from ibm.models import IBMCloud
from .consts import VPC_RESOURCE_REQUIRED_PARAMS
from .exceptions import IBMAuthError, IBMConnectError, IBMExecuteError, IBMInvalidRequestError
from .session_context import get_requests_session
from .urls import AUTH_URL, GLOBAL_SEARCH_BASE_URL, PRIVATE_CATALOG_BASE_URL, RESOURCE_BASE_URL, VPC_SERVICE_URL


class BaseClient:
    """
    Parent Class for all  the clients
    """

    def __init__(self, cloud_id, region=None):
        self.cloud_id = cloud_id
        self.region = region
        self.service = VpcV1(authenticator=self.authenticate_ibm_cloud_account())
        if region:
            self.service.set_service_url(VPC_SERVICE_URL.format(region=region))

    def authenticate_ibm_cloud_account(self):
        """
        Authenticate IBM Cloud account and return IAM token
        :return:
        """

        with get_db_session() as db_session:
            cloud = db_session.query(IBMCloud).filter_by(id=self.cloud_id).first()
            if not cloud:
                raise IBMInvalidRequestError("Cloud not found")

            return IAMAuthenticator(apikey=cloud.api_key)

    def authenticate_cloud_account(self, api_key):
        """
        Authenticate IBM Cloud account and return IAM token
        :return:
        """
        req = requests.Request(
            "POST",
            AUTH_URL,
            params={
                "grant_type": "urn:ibm:params:oauth:grant-type:apikey",
                "apikey": api_key,
                "client_id": "bx",
                "client_secret": "bx"
            },
            headers={
                "Content-Type": "application/x-www-form-urlencoded",
                "Accept": "application/json"
            }
        )
        return self._execute_request(req, "AUTH")

    def _paginate_resource(self, request, request_type, resource):
        resource_list = []

        response = self._execute_request(request, request_type)
        resource_list.extend(response.get(resource, []))

        while 'next' in response and response['next'].get('href'):
            request.url = response['next']['href']
            response = self._execute_request(request, request_type)
            resource_list.extend(response.get(resource, []))

        return {resource: resource_list}

    def _paginate_global_resource(self, request, request_type, resource):
        resource_list = []

        response = self._execute_request(request, request_type)
        resource_list.extend(response.get(resource, []))

        while 'next' in response:
            request.url = response['next']
            response = self._execute_request(request, request_type)
            resource_list.extend(response.get(resource, []))

        return {resource: resource_list}

    def _paginate_resource_controller_resource(self, request, request_type, resource):
        resource_list = []

        response = self._execute_request(request, request_type)
        resource_list.extend(response.get(resource, []))
        while response.get("next_url"):
            request.url = RESOURCE_BASE_URL + response['next_url']
            response = self._execute_request(request, request_type)
            resource_list.extend(response.get(resource, []))

        return {resource: resource_list}

    def _paginate_private_catalog_resource(self, request, request_type, resource):
        resource_list = []

        response = self._execute_request(request, request_type)
        resource_list.extend(response.get(resource, []))
        while "next" in response:
            request.url = PRIVATE_CATALOG_BASE_URL + response['next']
            response = self._execute_request(request, request_type)
            resource_list.extend(response.get(resource, []))

        return {resource: resource_list}

    def _paginate_global_search_resources(self, request, request_type, resource):
        resource_list = []

        response = self._execute_request(request, request_type)
        resource_list.extend(response.get(resource, []))
        while response.get("more_data"):
            request.url = GLOBAL_SEARCH_BASE_URL + response['token']
            response = self._execute_request(request, request_type)
            resource_list.extend(response.get(resource, []))

        return {resource: resource_list}

    def _execute_request(self, request, request_type):
        assert request_type in ["AUTH", "VPC_RESOURCE", "RESOURCE_GROUP", "KUBERNETES", "KUBERNETES_CONFIG", "COS",
                                "GLOBAL_CATALOG", "RESOURCE_INSTANCES", "PRIVATE_CATALOG", "CLASSIC_KUBERNETES",
                                "ACCOUNT_DETAILS", "TRANSIT_GATEWAY", "TAG_RESOURCE"]
        assert isinstance(request, requests.Request)

        auth_resp = None
        auth_required = False
        api_key = None
        access_token = None
        with get_db_session() as session:
            cloud = session.query(IBMCloud).get(self.cloud_id)
            if not cloud:
                raise IBMInvalidRequestError("Cloud not found")

            auth_required = cloud.auth_required
            api_key = cloud.api_key
            access_token = cloud.credentials.access_token if cloud.credentials else None
            refresh_token = cloud.credentials.refresh_token if cloud.credentials else None

        if request_type in ["VPC_RESOURCE", "RESOURCE_GROUP", "KUBERNETES", "KUBERNETES_CONFIG", "COS",
                            "RESOURCE_INSTANCES", "GLOBAL_CATALOG", "PRIVATE_CATALOG", "CLASSIC_KUBERNETES",
                            "ACCOUNT_DETAILS", "TRANSIT_GATEWAY", "TAG_RESOURCE"]:
            if auth_required:
                LOGGER.info("Authenticating Cloud {}".format(self.cloud_id))
                auth_resp = self.authenticate_cloud_account(api_key)
                refresh_token = " ".join([auth_resp.get("token_type"), auth_resp.get("refresh_token")])
                access_token = " ".join([auth_resp.get("token_type"), auth_resp.get("access_token")])

            if request_type in ["VPC_RESOURCE", "TRANSIT_GATEWAY"]:
                if request.params:
                    request.params.update(VPC_RESOURCE_REQUIRED_PARAMS)
                else:
                    request.params = VPC_RESOURCE_REQUIRED_PARAMS

            if request_type in ["KUBERNETES_CONFIG", "ACCOUNT_DETAILS"]:
                if request.headers:
                    request.headers.update({"X-Auth-Refresh-Token": refresh_token})
                else:
                    request.headers = {"X-Auth-Refresh-Token": refresh_token}

            if request.headers:
                request.headers.update({"Authorization": access_token})
            else:
                request.headers = {"Authorization": access_token}

        if auth_resp:
            with get_db_session() as session:
                cloud = session.query(IBMCloud).get(self.cloud_id)
                if not cloud:
                    raise IBMInvalidRequestError("Cloud not found")

                cloud.update_from_auth_response(auth_resp)
                session.commit()

        try:
            with get_requests_session() as req_session:
                request = req_session.prepare_request(request)
                response = req_session.send(request, timeout=30)
        except (ConnectionError, ReadTimeout, RequestException):
            raise IBMConnectError(self.cloud_id)

        # TODO: enhance this response. needs R&D.
        if request_type == "CLASSIC_KUBERNETES":
            if response.status_code == 403:
                return "Free tier cluster"

        if response.status_code == 401:
            raise IBMAuthError(self.cloud_id)
        elif response.status_code in [400, 403, 404, 408, 409]:
            raise IBMExecuteError(response)
        elif not str(response.status_code).startswith('2'):
            raise IBMExecuteError(response)

        try:
            if request_type == "COS":
                response_json = json.loads(json.dumps(xmltodict.parse(response.content)))
                return response_json

            response_json = response.json()
        except Exception:
            response_json = {}
        return response_json
