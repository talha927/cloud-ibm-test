class WorkerPool:
    ID_KEY = "id"
    NAME_KEY = "name"
    DISK_ENCRYPTION_KEY = "disk_encryption"
    FLAVOR_KEY = "flavor"
    WORKER_COUNT_KEY = "worker_count"
    WORKER_ZONES_KEY = "worker_zones"
    IBM_CLOUD_KEY = "ibm_cloud"
    ZONE_KEY = "zone"
    RESOURCE_JSON_KEY = "resource_json"

    def __init__(self, id_, name, disk_encryption, flavor, worker_count, cluster):
        self.id = id_
        self.name = name
        self.disk_encryption = disk_encryption
        self.flavor = flavor
        self.worker_count = worker_count
        self.cluster = cluster
        self.worker_zones = []

    def to_json(self):
        return {
            self.NAME_KEY: self.name,
            self.DISK_ENCRYPTION_KEY: self.disk_encryption,
            self.FLAVOR_KEY: self.flavor,
            self.WORKER_COUNT_KEY: self.worker_count,
            self.WORKER_ZONES_KEY: [worker_zone.to_json() for worker_zone in self.worker_zones]
        }

    def to_reference_json(self):
        return {
            self.ID_KEY: self.id,
            self.NAME_KEY: self.name
        }

    @property
    def cluster(self):
        return self.__cluster

    @cluster.setter
    def cluster(self, cluster):
        from ibm.web.cloud_translations.vpc_construct import KubernetesCluster

        assert isinstance(cluster, KubernetesCluster)

        self.__cluster = cluster
        if self not in cluster.worker_pools:
            cluster.worker_pools.append(self)
