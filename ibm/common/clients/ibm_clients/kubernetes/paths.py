KUBERNETES_BASE_URL = "https://containers.cloud.ibm.com/global"

CREATE_KUBERNETES_CLUSTER_PATH = "vpc/createCluster"
CREATE_KUBERNETES_CLUSTER_WORKERPOOL_PATH = "vpc/createWorkerPool"

# Classic cluster paths
LIST_CLASSIC_KUBERNETES_CLUSTERS_PATH = "classic/getClusters"
GET_CLASSIC_KUBERNETES_CLUSTERS_WORKER_POOLS_PATH = "/clusters/{cluster}/workerpools"

# IBM Kubernetes Managed View Paths
LIST_ALL_KUBERNETES_CLUSTER_PATH = "vpc/getClusters"
LIST_ZONE_FLAVORS_FOR_CLUSTER_CREATION = "getFlavors"
LIST_ALL_LOCATIONS = "locations"
GET_KUBERNETES_KUBE_VERSIONS = "getVersions"
GET_KUBERNETES_CLUSTER_DETAIL_PATH = "vpc/getCluster"
GET_KUBERNETES_CLUSTERS_WORKER_POOL_PATH = "vpc/getWorkerPools"
GET_CLASSIC_KUBERNETES_CLUSTERS_SUBNET_PATH = "/clusters/{cluster}/subnets"
GET_KUBERNETES_CLUSTER_KUBE_CONFIG = "getKubeconfig"

KUBERNETES_CLUSTER_URL_TEMPLATE = ''.join([KUBERNETES_BASE_URL, "/v2/",
                                           "{path}"])
CLASSIC_KUBERNETES_CLUSTERS_URL_TEMPLATE = ''.join([KUBERNETES_BASE_URL, "/v1/",
                                                    "{path}"])

DELETE_KUBERNETES_CLUSTER_WITH_RESOURCES = \
    "{kubernetes_base_url}/v1/clusters/{cluster}"
