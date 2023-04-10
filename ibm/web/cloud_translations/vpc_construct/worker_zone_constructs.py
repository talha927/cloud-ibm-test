class WorkerZone:
    SUBNETS_KEY = "subnets"
    ZONES_KEY = "zones"

    def __init__(self, subnet, worker_pool):
        self.subnet = subnet
        self.worker_pool = worker_pool

    def to_json(self):
        return {
            self.ZONES_KEY: self.subnet.zone,
            self.SUBNETS_KEY: self.subnet.to_reference_json()
        }

    @property
    def worker_pool(self):
        return self.__worker_pool

    @worker_pool.setter
    def worker_pool(self, worker_pool):
        from ibm.web.cloud_translations.vpc_construct import WorkerPool

        assert isinstance(worker_pool, WorkerPool)

        self.__worker_pool = worker_pool
        if self not in worker_pool.worker_zones:
            worker_pool.worker_zones.append(self)
