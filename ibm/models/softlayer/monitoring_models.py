class SoftLayerInstanceMonitoring:
    USED_MEMORY_KEY = "used_memory"
    TOTAL_MEMORY_KEY = "total_memory"
    CPU_USAGE_KEY = "cpu_usage"
    INBOUND_BANDWIDTH_USAGE_KEY = "inbound_bandwidth_usage"
    OUTBOUND_BANDWIDTH_USAGE_KEY = "outbound_bandwidth_usage"

    def __init__(
            self, used_memory=None, total_memory=None, cpu_usage=None, inbound_bandwidth_usage=None,
            outbound_bandwidth_usage=None):
        self.used_memory = used_memory
        self.total_memory = total_memory
        self.cpu_usage = cpu_usage
        self.inbound_bandwidth_usage = inbound_bandwidth_usage
        self.outbound_bandwidth_usage = outbound_bandwidth_usage

    def to_json(self):
        return {
            self.USED_MEMORY_KEY: self.used_memory,
            self.TOTAL_MEMORY_KEY: self.total_memory,
            self.CPU_USAGE_KEY: self.cpu_usage,
            self.INBOUND_BANDWIDTH_USAGE_KEY: self.inbound_bandwidth_usage,
            self.OUTBOUND_BANDWIDTH_USAGE_KEY: self.outbound_bandwidth_usage
        }
