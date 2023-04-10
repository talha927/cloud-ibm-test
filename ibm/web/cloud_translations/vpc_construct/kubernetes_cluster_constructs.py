class KubernetesCluster:
    ID_KEY = "id"
    NAME_KEY = "name"
    MANAGED_VIEW_KEY = "managed_view"
    MASTER_KUBE_VERSION_KEY = "master_kube_version"
    VPC_KEY = "vpc"
    DISABLE_PUBLIC_SERVICE_ENDPOINT_KEY = "disable_public_service_endpoint"
    CLUSTER_TYPE_KEY = "cluster_type"
    IBM_CLOUD_KEY = "ibm_cloud"
    REGION_KEY = "region"
    WORKER_POOLS_KEY = "worker_pools"
    RESOURCE_GROUP_KEY = "resource_group"
    RESOURCE_JSON_KEY = "resource_json"

    def __init__(self, id_, name, region, master_kube_version, resource_group, vpc, disable_public_service_endpoint):
        self.id = id_
        self.name = name
        self.region = region
        self.master_kube_version = master_kube_version
        self.disable_public_service_endpoint = disable_public_service_endpoint
        self.cluster_type = "kubernetes"
        self.vpc = vpc
        self.resource_group = resource_group
        self.worker_pools = []

    def to_json(self):
        return {
            self.ID_KEY: self.id,
            self.RESOURCE_JSON_KEY: self.to_resource_json(),
            self.IBM_CLOUD_KEY: self.region.cloud.to_reference_json(),
            self.MANAGED_VIEW_KEY: True,
            self.REGION_KEY: self.region.to_reference_json(),
        }

    def to_resource_json(self):
        return {
            self.NAME_KEY: self.name,
            self.MASTER_KUBE_VERSION_KEY: self.master_kube_version,
            self.VPC_KEY: self.vpc.to_reference_json(),
            self.DISABLE_PUBLIC_SERVICE_ENDPOINT_KEY: self.disable_public_service_endpoint,
            self.CLUSTER_TYPE_KEY: self.cluster_type,
            self.RESOURCE_GROUP_KEY: self.resource_group.to_reference_json(),
            self.WORKER_POOLS_KEY: [worker_pool.to_json() for worker_pool in self.worker_pools]
        }

    def to_reference_json(self):
        return {
            self.ID_KEY: self.id,
            self.NAME_KEY: self.name
        }

    @property
    def region(self):
        return self.__region

    @region.setter
    def region(self, region):
        from ibm.web.cloud_translations.vpc_construct import Region

        assert isinstance(region, Region)

        self.__region = region
        if self not in region.cloud.kubernetes_clusters:
            region.cloud.kubernetes_clusters.append(self)
            region.cloud.translated_resources[self.id] = self
