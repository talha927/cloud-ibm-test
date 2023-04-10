# Please maintain the order of the below metrics as the response data will be in this order.
METRICS = [
    {"id": "ibm_resource_name"},
    {"id": "ibm_is_instance_cpu_usage_percentage", "aggregations": {"time": "avg", "group": "avg"}},
    {"id": "ibm_is_instance_memory_usage_percentage", "aggregations": {"time": "avg", "group": "avg"}},
]

METRICS_FOR_IDLE_INSTANCES = [
    {"id": "ibm_resource_name"},
    {"id": "ibm_is_instance_cpu_usage_percentage", "aggregations": {"time": "avg", "group": "avg"}},
    {"id": "ibm_is_instance_network_in_bytes", "aggregations": {"time": "avg", "group": "avg"}},
    {"id": "ibm_is_instance_network_out_bytes", "aggregations": {"time": "avg", "group": "avg"}},
]

MONITORING_INSTANCE_URL = "https://{region_name}.monitoring.cloud.ibm.com"
