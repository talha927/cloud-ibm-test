import math
from typing import Dict, List

from ibm.common.clients.softlayer_clients.instances.consts import (
    BALANCED, BALANCED_INSTANCE_PROFILE_NAME, COMPUTE,
    COMPUTE_INSTANCE_PROFILE_NAME, MEMORY,
    MEMORY_INSTANCE_PROFILE_NAME
)


def get_ibm_instance_profile(cpu, memory):
    """
    Map IBM instance profile from classic instance profile
    :return:
    """
    instance_profile, family = BALANCED_INSTANCE_PROFILE_NAME, BALANCED
    check = math.ceil(memory / 1024)
    if check % 2 != 0:
        memory = 4096

    memory = int(memory / 1024)
    cpu = 2 if cpu < 2 else cpu
    memory = 4 if memory < 4 else memory

    if memory == cpu:
        memory = memory + cpu

    if memory / cpu == 2:
        family = COMPUTE
        instance_profile = COMPUTE_INSTANCE_PROFILE_NAME

    elif memory / cpu == 4:
        family = BALANCED
        instance_profile = BALANCED_INSTANCE_PROFILE_NAME

    elif memory / cpu == 8:
        family = MEMORY
        instance_profile = MEMORY_INSTANCE_PROFILE_NAME

    instance_profile = instance_profile.format(memory=memory, cpu=cpu)
    return instance_profile, family


def get_auto_scale_group(instance):
    """
    Get Instance's Auto Group
    @param instance:
    @return:
    """
    if instance.get('scaleMember') and instance['scaleMember'].get('scaleGroup'):
        return instance['scaleMember']['scaleGroup'].get('name')


def list_network_attached_storages(allowed_network_storages: List) -> List[Dict]:
    storage_list = []
    for network_storage in allowed_network_storages:
        storage_list.append({
            "type": network_storage['storageType'].get('keyName'),
            "username": network_storage['username'],
            "capacityGB": network_storage['capacityGb']
        })

    return storage_list
