from .recommendations_tasks import generate_classic_recommendations_task, sync_classic_network_gateways_task, \
    sync_classic_virtual_guest_bandwidth_usage_task, sync_classic_virtual_guest_cpu_usage_task, \
    sync_classic_virtual_guest_memory_usage_task, sync_classic_virtual_guests_usage_task

__all__ = [
    "sync_classic_virtual_guest_memory_usage_task",
    "sync_classic_virtual_guests_usage_task",
    "sync_classic_virtual_guest_cpu_usage_task",
    "sync_classic_network_gateways_task",
    "generate_classic_recommendations_task",
    "sync_classic_virtual_guest_bandwidth_usage_task"
]
