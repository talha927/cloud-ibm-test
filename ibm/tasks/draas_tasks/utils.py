import json
import uuid
from datetime import datetime
from typing import Dict

from ibm import get_db_session
from ibm.models import (
    IBMDedicatedHost, IBMDedicatedHostGroup, IBMKubernetesCluster, IBMPlacementGroup, IBMVpcNetwork
)
from ibm.models.agent.agent_models import OnPremCluster

DRAAS_RESOURCE_TYPE_TO_MODEL_MAPPER = {
    IBMKubernetesCluster.__name__: IBMKubernetesCluster,
    IBMVpcNetwork.__name__: IBMVpcNetwork
}

DRAAS_RESOURCE_TYPE_TO_KEY_MAPPER = {
    IBMKubernetesCluster.__name__: "kubernetes_clusters",
    IBMVpcNetwork.__name__: "vpc_networks"
}


def get_empty_workspace_payload_dict():
    return {
        "vpc_networks": [],
        "placement_groups": [],
        "subnets": [],
        "address_prefixes": [],
        "dedicated_hosts": [],
        "dedicated_host_groups": [],
        "floating_ips": [],
        "endpoint_gateways": [],
        "ike_policies": [],
        "instances": [],
        "kubernetes_clusters": [],
        "load_balancers": [],
        "routing_tables": [],
        "network_acls": [],
        "security_groups": [],
        "public_gateways": [],
        "ssh_keys": [],
        "vpn_gateways": []
    }


def construct_workspace_payload(vpc_name, resource_id):
    """This function does two things:
    - constructs payload that can be passed to POST /v1/ibm/workspaces to create workspace.
    - get the associated_resources of a `IBMVpcNetwork`

    {
        'vpc_networks': [{...}],
        'address_prefixes': [{...}],
        'security_groups': [{...}],
        'network_acls': [{...}],
        'routing_tables': [{...}],
        ...
    }
    """
    workspace_payload = get_empty_workspace_payload_dict()

    with get_db_session() as db_session:
        with db_session.no_autoflush:
            vpc_network = db_session.query(IBMVpcNetwork).filter_by(id=resource_id).first()
            if not vpc_network:
                return

            workspace_payload["vpc_networks"] = [vpc_network.to_template_json(vpc_name=vpc_name)]
            workspace_payload["address_prefixes"] = \
                [add_prefix.to_template_json() for add_prefix in vpc_network.address_prefixes.all()]
            workspace_payload["security_groups"] = \
                [sec_grp.to_template_json() for sec_grp in vpc_network.security_groups.all()]
            workspace_payload["network_acls"] = [network_acl.to_template_json() for network_acl in
                                                 vpc_network.acls.all()]
            workspace_payload["routing_tables"] = \
                [r_table.to_template_json() for r_table in vpc_network.routing_tables.all()]
            workspace_payload["public_gateways"] = [p.to_template_json() for p in vpc_network.public_gateways.all()]
            workspace_payload["subnets"] = [s.to_template_json() for s in vpc_network.subnets.all()]

            for instance in vpc_network.instances.all():
                workspace_payload["instances"].append(instance.to_template_json())
                workspace_payload["ssh_keys"] = [s.to_template_json() for s in instance.ssh_keys.all()]

                placement_target = instance.placement_target
                if isinstance(placement_target, IBMDedicatedHost):
                    workspace_payload["dedicated_hosts"].append(placement_target.to_template_json())
                elif isinstance(placement_target, IBMDedicatedHostGroup):
                    workspace_payload["dedicated_host_groups"].append(placement_target.to_template_json())
                elif isinstance(placement_target, IBMPlacementGroup):
                    workspace_payload["placement_groups"].append(placement_target.to_template_json())

            return workspace_payload, vpc_network.to_json(db_session)["associated_resources"]


def update_payload_with_new_ids(json_data: Dict) -> Dict:
    """
    Update the workspace payload with new IDs.
    A backup of VPC is just like a workspace_payload which you can provision as a whole. But the only problem
    is a backup should have IDs of the vpc, subnet and other resources which are not in the DB. Since Workspace
    payload requires every resource to have ID, this function update the existing backup with newly generated IDs.
    """
    old_id_to_new_id_mapper = {}

    for resource_type, resource_list in json_data.items():
        if not isinstance(resource_list, list):
            continue

        for item in resource_list:
            old_id_to_new_id_mapper[item["id"]] = str(uuid.uuid4().hex)

    str_json_dict = json.dumps(json_data)

    for old_id, new_id in old_id_to_new_id_mapper.items():
        str_json_dict = str_json_dict.replace(old_id, new_id)

    return json.loads(str_json_dict)


def generate_timestamped_backup_name(name):
    timestamp = datetime.now().strftime('%d-%m-%Y-%H.%M.%S')
    return f"{name}_{timestamp}"


def get_consumption_resource_from_db(session, cloud_id, resource_type, resource_id):
    """
    Loads a row from DB based on resource_type and resource_id
    """
    IBM_NAME_TO_MODEL_MAPPER = {
        IBMVpcNetwork.__name__: IBMVpcNetwork,
        "IKS": IBMKubernetesCluster,
        "ONPREM": OnPremCluster
    }
    resource = session.query(IBM_NAME_TO_MODEL_MAPPER[resource_type]).filter_by(id=resource_id,
                                                                                cloud_id=cloud_id).first()
    return resource
