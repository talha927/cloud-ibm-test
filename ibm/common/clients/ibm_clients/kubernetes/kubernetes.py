"""
This file contains Client for Kubernetes related tasks
"""
import requests

from .paths import CLASSIC_KUBERNETES_CLUSTERS_URL_TEMPLATE, CREATE_KUBERNETES_CLUSTER_PATH, \
    CREATE_KUBERNETES_CLUSTER_WORKERPOOL_PATH, DELETE_KUBERNETES_CLUSTER_WITH_RESOURCES, \
    GET_CLASSIC_KUBERNETES_CLUSTERS_SUBNET_PATH, GET_CLASSIC_KUBERNETES_CLUSTERS_WORKER_POOLS_PATH, \
    GET_KUBERNETES_CLUSTER_DETAIL_PATH, GET_KUBERNETES_CLUSTER_KUBE_CONFIG, GET_KUBERNETES_CLUSTERS_WORKER_POOL_PATH, \
    GET_KUBERNETES_KUBE_VERSIONS, KUBERNETES_BASE_URL, KUBERNETES_CLUSTER_URL_TEMPLATE, \
    LIST_ALL_KUBERNETES_CLUSTER_PATH, LIST_ALL_LOCATIONS, LIST_CLASSIC_KUBERNETES_CLUSTERS_PATH, \
    LIST_ZONE_FLAVORS_FOR_CLUSTER_CREATION
from ..base_client import BaseClient
from ..exceptions import IBMInvalidRequestError


class KubernetesClient(BaseClient):
    """
    Client for IKS Cluster related APIs
    """

    def __init__(self, cloud_id):
        super(KubernetesClient, self).__init__(cloud_id=cloud_id)

    def create_kubernetes_cluster(self, cluster_json):
        """

        :param cluster_json:
        :return:
        """

        headers = {"X-Auth-Resource-Group": cluster_json['resource_group']}

        if not isinstance(cluster_json, dict):
            raise IBMInvalidRequestError("Parameter 'cluster_json' should be a dictionary")

        request = requests.Request(
            "POST",
            KUBERNETES_CLUSTER_URL_TEMPLATE.format(
                path=CREATE_KUBERNETES_CLUSTER_PATH), json=cluster_json, headers=headers)

        response = self._execute_request(request, "KUBERNETES")

        return response

    def create_kubernetes_cluster_worker_pool(self, worker_pool_json):
        """

        :param worker_pool_json:
        :return:
        """

        request = requests.Request(
            "POST",
            KUBERNETES_CLUSTER_URL_TEMPLATE.format(
                path=CREATE_KUBERNETES_CLUSTER_WORKERPOOL_PATH), json=worker_pool_json)

        self._execute_request(request, "KUBERNETES")

    def get_all_locations(self):
        """

        :param None:
        :return: Lists all Locations available
        """
        request = requests.Request(
            "GET",
            CLASSIC_KUBERNETES_CLUSTERS_URL_TEMPLATE.format(
                path=LIST_ALL_LOCATIONS
            )
        )

        response = self._execute_request(request, "KUBERNETES")

        return response

    def get_kubernetes_kube_versions(self):
        """

        :param None:
        :return: Lists Kubernetes and Openshift Kube Versions
        """
        request = requests.Request(
            "GET",
            KUBERNETES_CLUSTER_URL_TEMPLATE.format(
                path=GET_KUBERNETES_KUBE_VERSIONS
            )
        )

        response = self._execute_request(request, "KUBERNETES")

        return response

    def list_kubernetes_zone_flavours(self, zone):
        """

        :param zone: Availability zone in a region
        :return: Lists all Flavors available for cluster creation
        """
        params = {
            "zone": zone,
            "provider": "vpc-gen2"
        }

        request = requests.Request(
            "GET",
            KUBERNETES_CLUSTER_URL_TEMPLATE.format(
                path=LIST_ZONE_FLAVORS_FOR_CLUSTER_CREATION,
            ),
            params=params
        )

        response = self._execute_request(request, "KUBERNETES")

        return response

    def list_kubernetes_clusters(self, location=None, resource_group=None):
        """

        :param location:
        :param resource_group:
        :return: Lists all KUBERNETES Clusters
        """
        params = {
            "provider": "vpc-gen2"
        }

        if location:
            params["location"] = location

        request = requests.Request(
            "GET",
            KUBERNETES_CLUSTER_URL_TEMPLATE.format(
                path=LIST_ALL_KUBERNETES_CLUSTER_PATH
            ),
            params=params
        )
        if resource_group:
            request.headers = {"X-Auth-Resource-Group": resource_group}

        response = self._execute_request(request, "KUBERNETES")

        return response

    def get_kubernetes_cluster_detail(self, cluster, resource_group=None, show_resources=None):
        """

        :param resource_group: resource group of the cluster
        :param cluster: cluster's resource_id or name
        :param show_resources:
        :return: KUBERNETES cluster's details
        """
        params = {
            "cluster": cluster,
        }
        if show_resources is not None:
            params["showResources"] = show_resources

        request = requests.Request(
            "GET",
            KUBERNETES_CLUSTER_URL_TEMPLATE.format(
                path=GET_KUBERNETES_CLUSTER_DETAIL_PATH
            ),
            params=params
        )
        if resource_group:
            request.headers = {"X-Auth-Resource-Group": resource_group}

        response = self._execute_request(request, "KUBERNETES")

        return response

    def get_kubernetes_cluster_worker_pool(self, cluster, region=None, resource_group=None):
        """

        :param region: cluster region
        :param resource_group: resource group of the cluster
        :param cluster: cluster id or name
        :return: KUBERNETES cluster's worker-pool
        """
        params = {
            "cluster": cluster,
        }
        request = requests.Request(
            "GET",
            KUBERNETES_CLUSTER_URL_TEMPLATE.format(
                path=GET_KUBERNETES_CLUSTERS_WORKER_POOL_PATH),
            params=params
        )
        if region:
            request.headers = {"X-Region": region}
        if resource_group:
            if request.headers:
                request.headers.update({"X-Auth-Resource-Group": resource_group})
            else:
                request.headers = {"X-Auth-Resource-Group": resource_group}

        response = self._execute_request(request, "KUBERNETES")

        return response

    def get_kubernetes_cluster_kube_config(self, cluster, endpoint_type=None, format_of_kube_config=None, admin=True,
                                           network=None, resource_group=None):
        """

        :param cluster: cluster id or name
        :param endpoint_type: default is public, but private and link can also be passed, if available on cluster
        :param format_of_kube_config: json, yaml or zip
        :param admin: true or false
        :param network:
        :param resource_group: resource group of the cluster (optional)
        :return: KUBERNETES cluster kube-config
        """
        params = {
            "cluster": cluster,
        }
        if endpoint_type is not None:
            params["endpointType"] = endpoint_type
        if format_of_kube_config is not None:
            params["format"] = format_of_kube_config
        if admin is not None and type(admin) is bool:
            params["admin"] = admin
        if network is not None and (admin is True and format_of_kube_config.lower() == "zip"):
            params["network"] = network

        request = requests.Request(
            "GET",
            KUBERNETES_CLUSTER_URL_TEMPLATE.format(path=GET_KUBERNETES_CLUSTER_KUBE_CONFIG),
            params=params
        )

        if resource_group:
            request.headers = {"X-Auth-Resource-Group": resource_group}

        response = self._execute_request(request, "KUBERNETES_CONFIG")

        return response

    def delete_kubernetes_cluster(self, cluster, delete_resources=None, resource_group=None):
        """

        :param cluster: cluster id or name
        :param delete_resources: true if delete other resources such as VLANs, subnets, storage
        :param resource_group: resource group of the cluster (optional)
        :return: Deletes Kubernetes cluster from IBM
        """
        params = {}
        if delete_resources:
            params["deleteResources"] = delete_resources

        request = requests.Request(
            "DELETE",
            DELETE_KUBERNETES_CLUSTER_WITH_RESOURCES.format(
                kubernetes_base_url=KUBERNETES_BASE_URL,
                cluster=cluster,
            ),
            params=params
        )

        if resource_group:
            request.headers = {"X-Auth-Resource-Group": resource_group}

        response = self._execute_request(request, "KUBERNETES")

        return response

    def list_kubernetes_classic_clusters(self):
        """
        :return: Lists all KUBERNETES Classic Clusters
        """
        request = requests.Request(
            "GET",
            KUBERNETES_CLUSTER_URL_TEMPLATE.format(
                path=LIST_CLASSIC_KUBERNETES_CLUSTERS_PATH
            )
        )

        response = self._execute_request(request, "KUBERNETES")

        return response

    def get_cluster_subnets(self, cluster, resource_group):
        """
        This request retrieves vlans in which classic Kubernetes clusters are provisioned
        """
        request = requests.Request(
            "GET",
            CLASSIC_KUBERNETES_CLUSTERS_URL_TEMPLATE.format(
                path=GET_CLASSIC_KUBERNETES_CLUSTERS_SUBNET_PATH.format(cluster=cluster))
        )
        request.headers = {'X-Auth-Resource-Group': resource_group}
        response = self._execute_request(request, "CLASSIC_KUBERNETES")

        return response

    def get_classic_kubernetes_cluster_worker_pool(self, cluster):
        """
        :param cluster: cluster id or name
        :return: CLASSIC KUBERNETES cluster's worker-pool
        """
        request = requests.Request(
            "GET",
            CLASSIC_KUBERNETES_CLUSTERS_URL_TEMPLATE.format(
                path=GET_CLASSIC_KUBERNETES_CLUSTERS_WORKER_POOLS_PATH.format(cluster=cluster)),
        )
        response = self._execute_request(request, "KUBERNETES")

        return response
