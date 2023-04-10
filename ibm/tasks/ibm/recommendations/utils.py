import math

from ibm.common.clients.softlayer_clients.instances.consts import BALANCED_INSTANCE_PROFILE_NAME, \
    COMPUTE_INSTANCE_PROFILE_NAME, MEMORY_INSTANCE_PROFILE_NAME
from .consts import ALLOWED_THRESHOLD, LOWEST_INSTANCE_PROFILE, VPC_GEN2_INSTANCE_PROFILES_COST_SHEET
from ibm.models.ibm.instance_models import IBMInstanceProfile


def get_cost_saving_instance_profile(instance_profile, low_memory_usage=False, low_cpu_usage=False):
    """
    Recommend instance profile which best suits the requirements of application and save costs accordingly.
    """

    if isinstance(instance_profile, IBMInstanceProfile):
        memory_dict, cpu_dict = instance_profile.memory, instance_profile.vcpu_count
        memory = memory_dict['value']
        cpu = cpu_dict['value']
    else:
        memory, cpu = instance_profile.max_memory, instance_profile.max_cpu
        memory = math.ceil(memory / 1024)

    if low_memory_usage:
        index = ALLOWED_THRESHOLD.index(memory)
        memory = ALLOWED_THRESHOLD[index - 1]

    if low_cpu_usage:
        index = ALLOWED_THRESHOLD.index(cpu)
        cpu = ALLOWED_THRESHOLD[index - 1]

    if memory == cpu:
        return

    cpu = 2 if cpu < 2 else cpu
    memory = 4 if memory < 4 else memory

    instance_profile = BALANCED_INSTANCE_PROFILE_NAME
    if memory / cpu == 2:
        instance_profile = COMPUTE_INSTANCE_PROFILE_NAME

    elif memory / cpu == 4:
        instance_profile = BALANCED_INSTANCE_PROFILE_NAME

    elif memory / cpu == 8:
        instance_profile = MEMORY_INSTANCE_PROFILE_NAME

    recommended_instance_profile = instance_profile.format(memory=memory, cpu=cpu)
    return recommended_instance_profile


def get_potential_cost_savings(instance_profile, recommended_instance_profile):
    """
    Get Potential Costs Savings in percentage for recommended profile
    """
    instance_profile_cost = VPC_GEN2_INSTANCE_PROFILES_COST_SHEET[instance_profile]
    recommended_instance_profile_cost = VPC_GEN2_INSTANCE_PROFILES_COST_SHEET[recommended_instance_profile]
    return ((instance_profile_cost - recommended_instance_profile_cost) / instance_profile_cost) * 100


def generate_network_gateway_recommendations(softlayer_network_gateway):
    """
    Generate recommendations for network gateway
    """
    recommendations = list()
    if not softlayer_network_gateway.status == "ACTIVE":
        recommendations.append(f"{softlayer_network_gateway.name} is in Stopped State, IBM charges for "
                               f"stopped gateway appliances too, you can remove it or move to VPC to save "
                               f"extra cost.")

    if softlayer_network_gateway.public_vlan and softlayer_network_gateway.private_vlan:
        recommendations.append(f"{softlayer_network_gateway.name} is discovered in your infrastructure, "
                               f"ACLs/Security Groups can be used as a replacement of Firewall rules, "
                               f"Subnets can be used as a replacement of VLANs and VPC IPSEC VPN can be as "
                               f"a replacement of IPSEC VPN, Move to VPC to save extra Cost.")

    return recommendations


def generate_virtual_server_recommendations(softlayer_instance):
    """
    Generate recommendations and come up with potential savings plan for softlayer instance
    """
    recommendations = list()
    low_memory_usage, low_cpu_usage = False, False
    recommended_instance_profile, potential_savings = None, None

    if not softlayer_instance.status == "ACTIVE":
        recommendations.append(
            f"{softlayer_instance.name} is in Stopped State, IBM charges for stopped instances too, you can "
            f"take snapshot and remove it to save extra cost.")

    if softlayer_instance.monitoring_info.used_memory:
        memory_usage = (softlayer_instance.monitoring_info.used_memory / int(
            softlayer_instance.monitoring_info.total_memory)) * 100
        if memory_usage <= 45:
            low_memory_usage = True

    if softlayer_instance.monitoring_info.cpu_usage:
        for cpu_avg in softlayer_instance.monitoring_info.cpu_usage.keys():
            if softlayer_instance.monitoring_info.cpu_usage[cpu_avg] <= 20:
                low_cpu_usage = True
                break

    if softlayer_instance.instance_profile.name == LOWEST_INSTANCE_PROFILE:
        return recommendations, recommended_instance_profile, potential_savings

    if softlayer_instance.name.startswith("kube-"):
        return recommendations, recommended_instance_profile, potential_savings

    if low_memory_usage or low_cpu_usage:
        recommended_instance_profile = get_cost_saving_instance_profile(
            softlayer_instance.instance_profile, low_memory_usage, low_cpu_usage)
        if not recommended_instance_profile:
            return recommendations, recommended_instance_profile, potential_savings

        potential_savings = get_potential_cost_savings(
            softlayer_instance.instance_profile.name, recommended_instance_profile)

        if low_memory_usage:
            recommendations.append(
                "Memory Usage is less than 45%, Lower the Instance Profile to save extra cost")

        if low_cpu_usage:
            recommendations.append(
                "CPU Usage is less than 20% per CPU, Lower the Instance Profile to save extra cost")

    return recommendations, recommended_instance_profile, potential_savings
