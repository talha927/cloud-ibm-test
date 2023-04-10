import logging
from copy import deepcopy

from sqlalchemy.orm.exc import StaleDataError

from ibm.models import IBMAddressPrefix, IBMDedicatedHost, IBMDedicatedHostGroup, IBMFloatingIP, IBMIKEPolicy, \
    IBMIPSecPolicy, IBMKubernetesCluster, IBMLoadBalancer, IBMNetworkAcl, IBMNetworkInterface, IBMPlacementGroup, \
    IBMPublicGateway, IBMRoutingTable, IBMSecurityGroup, IBMSshKey, IBMSubnet, IBMVpcNetwork, IBMVpnGateway, \
    WorkflowRoot, WorkflowsWorkspace, WorkflowTask
from ibm.web import db as ibmdb
from ibm.web.common.utils import compose_ibm_resource_attachment_workflow, create_ibm_resource_creation_workflow, \
    create_kubernetes_restore_workflow
from ibm.web.ibm.draas.restores.utils import ibm_draas_restore_workflow
from ibm.web.ibm.instances.utils import create_ibm_instance_creation_workflow, update_root_data_and_task_metadata
from ibm.web.ibm.kubernetes.utils import create_ibm_kubernetes_cluster_migration_workflow

LOGGER = logging.getLogger(__name__)


def get_attachment_resource_name(attachment_obj):
    """
    Return the name of the attachment detachment task from task_mapper.Mapper
    """
    from ibm.tasks.tasks_mapper import MAPPER
    assert isinstance(attachment_obj, dict)
    type_key = attachment_obj["type"]
    attachment_obj.pop("type")
    # This dictionary can b directly get from models as well but fow now these are only few that's why no generic
    # method was introduced
    resources_dict = {
        IBMPublicGateway.CRZ_BACKREF_NAME[:-1]: IBMPublicGateway.__name__,
        IBMSubnet.CRZ_BACKREF_NAME[:-1]: IBMSubnet.__name__,
        IBMRoutingTable.CRZ_BACKREF_NAME[:-1]: IBMRoutingTable.__name__,
        IBMNetworkAcl.CRZ_BACKREF_NAME[:-1]: IBMNetworkAcl.__name__,
        IBMNetworkInterface.CRZ_BACKREF_NAME[:-1]: IBMNetworkInterface.__name__,
        IBMFloatingIP.CRZ_BACKREF_NAME[:-1]: IBMFloatingIP.__name__,
    }
    resources = list(attachment_obj.keys())
    try:
        # This line is jut to check the KeyError on models names order
        MAPPER[f"{resources_dict[resources[0]]}-{resources_dict[resources[1]]}"][type_key]["RUN"]
        task_name = f"{resources_dict[resources[0]]}-{resources_dict[resources[1]]}"
    except KeyError:
        task_name = f"{resources_dict[resources[1]]}-{resources_dict[resources[0]]}"
    return task_name


def create_workspace_workflow(user, data, db_session=None, sketch=False, backup_id=None,
                              source_cloud=None, workspace_type=None):
    if not source_cloud:
        source_cloud = "IBM"
    workspace = WorkflowsWorkspace(name=data["name"], fe_request_data=deepcopy(data), user_id=user["id"],
                                   project_id=user["project_id"], sketch=sketch, source_cloud=source_cloud,
                                   workspace_type=workspace_type)
    roots = []
    if not db_session:
        db_session = ibmdb.session
    vpc_id_to_root_dict = {}

    for vpc_data in data.get("vpc_networks", []):
        vpc_workflow_root = \
            create_ibm_resource_creation_workflow(
                user=user, resource_type=IBMVpcNetwork, data=vpc_data, db_session=db_session, validate=False,
                sketch=True
            )
        roots.append(vpc_workflow_root)
        workspace.add_next_root(vpc_workflow_root)

        vpc_id_to_root_dict[vpc_data["id"]] = vpc_workflow_root

    address_prefix_workflow_roots = []
    for address_prefix_data in data.get("address_prefixes", []):
        address_prefix_workflow_root = \
            create_ibm_resource_creation_workflow(
                user=user, resource_type=IBMAddressPrefix, data=address_prefix_data, db_session=db_session,
                validate=False, sketch=True
            )

        address_prefix_workflow_roots.append(address_prefix_workflow_root)
        if address_prefix_data["vpc"]["id"] not in vpc_id_to_root_dict:
            workspace.add_next_root(address_prefix_workflow_root)
            continue

        vpc_workflow_root = vpc_id_to_root_dict[address_prefix_data["vpc"]["id"]]
        vpc_workflow_root.add_next_root(address_prefix_workflow_root)

    network_acl_id_to_workflow_roots_dict = {}
    for network_acl_data in data.get("network_acls", []):
        network_acl_workflow_root = \
            create_ibm_resource_creation_workflow(
                user=user, resource_type=IBMNetworkAcl, data=network_acl_data, db_session=db_session, validate=False,
                sketch=True
            )

        network_acl_id_to_workflow_roots_dict[network_acl_data["id"]] = network_acl_workflow_root
        if network_acl_data["resource_json"]["vpc"]["id"] not in vpc_id_to_root_dict:
            workspace.add_next_root(network_acl_workflow_root)
        else:
            vpc_workflow_root = vpc_id_to_root_dict[network_acl_data["resource_json"]["vpc"]["id"]]
            vpc_workflow_root.add_next_root(network_acl_workflow_root)

    # TODO: network_interface is supported, check for the public_gateway support. (regarding FloatingIP)
    public_gateway_id_to_workflow_roots_dict = {}
    for public_gateway_data in data.get("public_gateways", []):
        public_gateway_workflow = \
            create_ibm_resource_creation_workflow(
                user=user, resource_type=IBMPublicGateway, data=public_gateway_data, db_session=db_session,
                validate=False, sketch=True
            )

        public_gateway_id_to_workflow_roots_dict[public_gateway_data["id"]] = public_gateway_workflow
        if public_gateway_data["resource_json"]["vpc"]["id"] not in vpc_id_to_root_dict:
            workspace.add_next_root(public_gateway_workflow)
            continue

        vpc_workflow_root = vpc_id_to_root_dict[public_gateway_data["resource_json"]["vpc"]["id"]]
        vpc_workflow_root.add_next_root(public_gateway_workflow)

    subnet_id_to_workflow_roots_dict = {}
    for subnet_data in data.get("subnets", []):
        subnet_workflow_root = \
            create_ibm_resource_creation_workflow(
                user=user, resource_type=IBMSubnet, data=subnet_data, db_session=db_session, validate=False,
                sketch=True
            )

        subnet_id_to_workflow_roots_dict[subnet_data["id"]] = subnet_workflow_root

        previous_root_found = bool(address_prefix_workflow_roots)
        for address_prefix_workflow_root in address_prefix_workflow_roots:
            address_prefix_workflow_root.add_next_root(subnet_workflow_root)

        if subnet_data["resource_json"]["vpc"]["id"] not in vpc_id_to_root_dict:
            previous_root_found = True
        else:
            vpc_workflow_root = vpc_id_to_root_dict[subnet_data["resource_json"]["vpc"]["id"]]
            vpc_workflow_root.add_next_root(subnet_workflow_root)

        if subnet_data["resource_json"].get("public_gateway", {}).get("id") in public_gateway_id_to_workflow_roots_dict:
            public_gateway_id = subnet_data["resource_json"]["public_gateway"]["id"]
            public_gateway_id_to_workflow_roots_dict[public_gateway_id].add_next_root(subnet_workflow_root)

        if subnet_data["resource_json"].get("network_acl", {}).get("id") in network_acl_id_to_workflow_roots_dict:
            network_acl_id = subnet_data["resource_json"]["network_acl"]["id"]
            network_acl_id_to_workflow_roots_dict[network_acl_id].add_next_root(subnet_workflow_root)

        if not previous_root_found:
            workspace.add_next_root(subnet_workflow_root)

    security_group_id_to_workflow_roots_dict = {}
    rule_sg_id_to_parent_sg_workflow_roots_dict = {}
    for security_group_data in data.get("security_groups", []):
        security_group_workflow = \
            create_ibm_resource_creation_workflow(
                user=user, resource_type=IBMSecurityGroup, data=security_group_data, db_session=db_session,
                validate=False, sketch=True
            )

        security_group_id_to_workflow_roots_dict[security_group_data["id"]] = security_group_workflow

        if security_group_data["resource_json"]["vpc"]["id"] not in vpc_id_to_root_dict:
            workspace.add_next_root(security_group_workflow)
            continue

        for rule_json in security_group_data["resource_json"].get("rules", []):
            rule_sg_json = rule_json.get("remote", {}).get("security_group", {})
            if rule_sg_json:
                rule_security_group_workflow = security_group_id_to_workflow_roots_dict.get(rule_sg_json["id"])
                if not rule_security_group_workflow:
                    rule_sg_id_to_parent_sg_workflow_roots_dict[rule_sg_json["id"]] = security_group_workflow
                    continue

                workspace.add_next_root(rule_security_group_workflow)
                rule_security_group_workflow.add_next_root(security_group_workflow)

        vpc_workflow_root = vpc_id_to_root_dict[security_group_data["resource_json"]["vpc"]["id"]]
        vpc_workflow_root.add_next_root(security_group_workflow)

    for rule_sec_grp_id, p_sec_grp_root in rule_sg_id_to_parent_sg_workflow_roots_dict.items():
        rule_security_group_workflow = security_group_id_to_workflow_roots_dict[rule_sec_grp_id]
        workspace.add_next_root(rule_security_group_workflow)
        rule_security_group_workflow.add_next_root(p_sec_grp_root)

    routing_table_id_to_workflow_roots_dict = {}
    for routing_table_data in data.get("routing_tables", []):
        routing_table_workflow = \
            create_ibm_resource_creation_workflow(
                user=user, resource_type=IBMRoutingTable, data=routing_table_data, db_session=db_session,
                validate=False, sketch=True
            )

        routing_table_id_to_workflow_roots_dict[routing_table_data["id"]] = routing_table_workflow
        if routing_table_data["vpc"]["id"] not in vpc_id_to_root_dict:
            workspace.add_next_root(routing_table_workflow)
            continue

        vpc_workflow_root = vpc_id_to_root_dict[routing_table_data["vpc"]["id"]]
        vpc_workflow_root.add_next_root(routing_table_workflow)

    placement_group_id_to_workflow_roots_dict = {}
    for placement_group_data in data.get("placement_groups", []):
        placement_group_workflow = \
            create_ibm_resource_creation_workflow(
                user=user, resource_type=IBMPlacementGroup, data=placement_group_data, db_session=db_session,
                validate=False, sketch=True
            )
        placement_group_id_to_workflow_roots_dict[placement_group_data["id"]] = placement_group_workflow
        workspace.add_next_root(placement_group_workflow)

    ssh_key_id_to_workflow_roots_dict = {}
    for ssh_key_data in data.get("ssh_keys", []):
        ssh_key_workflow = \
            create_ibm_resource_creation_workflow(
                user=user, resource_type=IBMSshKey, data=ssh_key_data, db_session=db_session, validate=False,
                sketch=True
            )
        ssh_key_id_to_workflow_roots_dict[ssh_key_data["id"]] = ssh_key_workflow
        workspace.add_next_root(ssh_key_workflow)

    dedicated_host_group_id_to_workflow_roots_dict = {}
    for dedicated_host_group_data in data.get("dedicated_host_groups", []):
        dedicated_host_group_workflow = \
            create_ibm_resource_creation_workflow(
                user=user, resource_type=IBMDedicatedHostGroup, data=dedicated_host_group_data, db_session=db_session,
                validate=False, sketch=True
            )
        workspace.add_next_root(dedicated_host_group_workflow)
        dedicated_host_group_id_to_workflow_roots_dict[dedicated_host_group_data["id"]] = dedicated_host_group_workflow

    dedicated_host_id_to_workflow_roots_dict = {}
    for dedicated_host_data in data.get("dedicated_hosts", []):
        dedicated_host_workflow = \
            create_ibm_resource_creation_workflow(
                user=user, resource_type=IBMDedicatedHost, data=dedicated_host_data, db_session=db_session,
                validate=False, sketch=True
            )
        dedicated_host_id_to_workflow_roots_dict[dedicated_host_data["id"]] = dedicated_host_workflow
        dh_group = dedicated_host_data["resource_json"].get("group")
        if not dh_group or dh_group["id"] not in dedicated_host_group_id_to_workflow_roots_dict:
            workspace.add_next_root(dedicated_host_workflow)
            continue

        dedicated_host_group_workflow = \
            dedicated_host_group_id_to_workflow_roots_dict[
                dedicated_host_data["resource_json"]["group"]["id"]
            ]
        dedicated_host_group_workflow.add_next_root(dedicated_host_workflow)

    instance_id_to_workflow_roots_dict = {}
    network_interface_id_to_instance_workflow_roots_dict = {}
    for instance_data in data.get("instances", []):
        instance_workflow = create_ibm_instance_creation_workflow(
            user=user, data=instance_data, db_session=db_session, sketch=True
        )

        instance_id_to_workflow_roots_dict[instance_data["id"]] = instance_workflow
        previous_root_found = False
        for ssh_key_data in instance_data["resource_json"].get("keys", []):
            if ssh_key_data.get("id") not in ssh_key_id_to_workflow_roots_dict:
                continue

            previous_root_found = True
            ssh_key_id_to_workflow_roots_dict[ssh_key_data["id"]].add_next_root(instance_workflow)

        placement_target = instance_data["resource_json"].get("placement_target", {})
        if "dedicated_host_group" in placement_target:
            dedicated_host_group_id = placement_target["dedicated_host_group"]["id"]
            if dedicated_host_group_id in dedicated_host_group_id_to_workflow_roots_dict:
                previous_root_found = True
                dedicated_host_group_workflow = dedicated_host_group_id_to_workflow_roots_dict[dedicated_host_group_id]
                dedicated_host_group_workflow.add_next_root(instance_workflow)
        elif "dedicated_host" in placement_target:
            dedicated_host_id = placement_target["dedicated_host"]["id"]
            if dedicated_host_id in dedicated_host_id_to_workflow_roots_dict:
                previous_root_found = True
                dedicated_host_workflow = dedicated_host_id_to_workflow_roots_dict[dedicated_host_id]
                dedicated_host_workflow.add_next_root(instance_workflow)

        elif "placement_group" in placement_target:
            placement_group_group_id = placement_target["placement_group"]["id"]
            placement_group_workflow = placement_group_id_to_workflow_roots_dict[placement_group_group_id]
            placement_group_workflow.add_next_root(instance_workflow)

        for network_interface_json in instance_data["resource_json"].get("network_interfaces", []):
            if network_interface_json["subnet"]["id"] in subnet_id_to_workflow_roots_dict:
                previous_root_found = True
                subnet_id_to_workflow_roots_dict[network_interface_json["subnet"]["id"]].add_next_root(
                    instance_workflow)
                network_interface_id_to_instance_workflow_roots_dict[network_interface_json["id"]] = instance_workflow

            for security_group in network_interface_json.get("security_groups", []):
                sec_grp_id = security_group["id"]
                if sec_grp_id in security_group_id_to_workflow_roots_dict:
                    previous_root_found = True
                    security_group_id_to_workflow_roots_dict[sec_grp_id].add_next_root(instance_workflow)

        primary_network_interface = instance_data["resource_json"]["primary_network_interface"]
        if primary_network_interface["subnet"]["id"] in subnet_id_to_workflow_roots_dict:
            previous_root_found = True
            subnet_workflow_root = subnet_id_to_workflow_roots_dict[primary_network_interface["subnet"]["id"]]
            network_interface_id_to_instance_workflow_roots_dict[primary_network_interface["id"]] = instance_workflow
            subnet_workflow_root.add_next_root(instance_workflow)

        for security_group in primary_network_interface.get("security_groups", []):
            sec_grp_id = security_group["id"]
            if sec_grp_id in security_group_id_to_workflow_roots_dict:
                previous_root_found = True
                security_group_id_to_workflow_roots_dict[sec_grp_id].add_next_root(instance_workflow)

        if instance_data["resource_json"]["vpc"]["id"] in vpc_id_to_root_dict:
            previous_root_found = True
            vpc_workflow_root = vpc_id_to_root_dict[instance_data["resource_json"]["vpc"]["id"]]
            vpc_workflow_root.add_next_root(instance_workflow)

        if not previous_root_found:
            workspace.add_next_root(instance_workflow)

    floating_ip_id_to_workflow_roots_dict = {}
    for floating_ip_data in data.get("floating_ips", []):
        floating_ip_workflow = \
            create_ibm_resource_creation_workflow(
                user=user, resource_type=IBMFloatingIP, data=floating_ip_data, db_session=db_session, validate=False,
                sketch=True
            )

        floating_ip_id_to_workflow_roots_dict[floating_ip_data["id"]] = floating_ip_workflow
        if floating_ip_data["resource_json"]["target"]["id"] \
                not in network_interface_id_to_instance_workflow_roots_dict:
            workspace.add_next_root(floating_ip_workflow)
            continue

        instance_workflow = \
            network_interface_id_to_instance_workflow_roots_dict[
                floating_ip_data["resource_json"]["target"]["id"]
            ]
        # TODO: network_interface is supported, check for the public_gateway support.
        instance_workflow.add_next_root(floating_ip_workflow)

    load_balancer_id_to_workflow_roots_dict = {}
    for load_balancer_data in data.get("load_balancers", []):
        load_balancer_workflow_root = \
            create_ibm_resource_creation_workflow(
                user=user, resource_type=IBMLoadBalancer, data=load_balancer_data, db_session=db_session,
                validate=False, sketch=True
            )

        load_balancer_id_to_workflow_roots_dict[load_balancer_data["id"]] = load_balancer_workflow_root

        previous_root_found = False
        for subnet_data in load_balancer_data["resource_json"].get("subnets", []):
            if subnet_data["id"] not in subnet_id_to_workflow_roots_dict:
                continue

            previous_root_found = True
            subnet_id_to_workflow_roots_dict[subnet_data["id"]].add_next_root(load_balancer_workflow_root)

        for sec_grp_data in load_balancer_data["resource_json"].get("security_groups", []):
            if sec_grp_data["id"] not in security_group_id_to_workflow_roots_dict:
                continue

            previous_root_found = True
            security_group_id_to_workflow_roots_dict[sec_grp_data["id"]].add_next_root(load_balancer_workflow_root)

        for pool_data in load_balancer_data["resource_json"].get("pools", []):
            for member_data in pool_data.get("members", []):
                if member_data["target"]["id"] not in [instance_id_to_workflow_roots_dict,
                                                       network_interface_id_to_instance_workflow_roots_dict]:
                    continue
                previous_root_found = True
                if member_data["target"]["type"] == "instance":
                    instance_id_to_workflow_roots_dict[member_data["target"]["id"]].add_next_root(
                        load_balancer_workflow_root)
                elif member_data["target"]["type"] == "network_interface":
                    network_interface_id_to_instance_workflow_roots_dict[member_data["target"]["id"]].add_next_root(
                        load_balancer_workflow_root)

        if not previous_root_found:
            workspace.add_next_root(load_balancer_workflow_root)

    ipsec_policy_id_to_workflow_roots_dict = {}
    for ipsec_policy_data in data.get("ipsec_policies", []):
        ipsec_policy_workflow = \
            create_ibm_resource_creation_workflow(
                user=user, resource_type=IBMIPSecPolicy, data=ipsec_policy_data, db_session=db_session, validate=False,
                sketch=True
            )
        workspace.add_next_root(ipsec_policy_workflow)
        ipsec_policy_id_to_workflow_roots_dict[ipsec_policy_data["id"]] = ipsec_policy_workflow

    ike_policy_id_to_workflow_roots_dict = {}
    for ike_policy_data in data.get("ike_policies", []):
        ike_policy_workflow = \
            create_ibm_resource_creation_workflow(
                user=user, resource_type=IBMIKEPolicy, data=ike_policy_data, db_session=db_session, validate=False,
                sketch=True
            )
        workspace.add_next_root(ike_policy_workflow)
        ike_policy_id_to_workflow_roots_dict[ike_policy_data["id"]] = ike_policy_workflow

    vpn_gateway_id_to_workflow_roots_dict = {}
    for vpn_gateway_data in data.get("vpn_gateways", []):
        vpn_gateway_workflow = \
            create_ibm_resource_creation_workflow(
                user=user, resource_type=IBMVpnGateway, data=vpn_gateway_data, db_session=db_session, validate=False,
                sketch=True
            )

        vpn_gateway_id_to_workflow_roots_dict[vpn_gateway_data["id"]] = vpn_gateway_workflow

        previous_root_found = False
        if "subnet" in vpn_gateway_data["resource_json"]:
            subnet_id = vpn_gateway_data["resource_json"]["subnet"]["id"]
            if subnet_id not in subnet_id_to_workflow_roots_dict:
                continue

            previous_root_found = True
            subnet_workflow_root = subnet_id_to_workflow_roots_dict[subnet_id]
            subnet_workflow_root.add_next_root(vpn_gateway_workflow)

        for connection_data in vpn_gateway_data["resource_json"].get("connections", []):
            ipsec_policy = connection_data.get("ipsec_policy")
            if ipsec_policy and ipsec_policy["id"] in ipsec_policy_id_to_workflow_roots_dict:
                previous_root_found = True
                ipsec_policy_workflow = ipsec_policy_id_to_workflow_roots_dict[ipsec_policy["id"]]
                ipsec_policy_workflow.add_next_root(vpn_gateway_workflow)

            ike_policy = connection_data.get("ike_policy")
            if ike_policy and ike_policy["id"] in ike_policy_id_to_workflow_roots_dict:
                previous_root_found = True
                ike_policy_workflow = ike_policy_id_to_workflow_roots_dict[ike_policy["id"]]
                ike_policy_workflow.add_next_root(vpn_gateway_workflow)

        if not previous_root_found:
            workspace.add_next_root(vpn_gateway_workflow)

    kubernetes_id_to_workflow_roots_dict = {}
    for kubernetes_data in data.get("kubernetes_clusters", []):
        kubernetes_workflow = \
            create_ibm_kubernetes_cluster_migration_workflow(
                data=kubernetes_data, user=user, db_session=db_session, sketch=sketch
            )

        kubernetes_id_to_workflow_roots_dict[kubernetes_data["id"]] = kubernetes_workflow

        previous_root_found = False
        if kubernetes_data["resource_json"]["vpc"]["id"] in vpc_id_to_root_dict:
            vpc_workflow_root = vpc_id_to_root_dict[kubernetes_data["resource_json"]["vpc"]["id"]]
            vpc_workflow_root.add_next_root(kubernetes_workflow)
            previous_root_found = True

        for worker_pool_data in kubernetes_data["resource_json"].get("worker_pools", []):
            for zone_data in worker_pool_data.get("worker_zones", []):
                if zone_data["subnets"]["id"] not in subnet_id_to_workflow_roots_dict:
                    continue

                previous_root_found = True
                subnet_workflow_root = subnet_id_to_workflow_roots_dict[zone_data["subnets"]["id"]]
                subnet_workflow_root.add_next_root(kubernetes_workflow)

        if not previous_root_found:
            workspace.add_next_root(kubernetes_workflow)

    draas_restore_kubernetes_id_to_workflow_roots_dict = {}
    for kubernetes_data in data.get("draas_restore_clusters", []):
        backup_id = kubernetes_data.get("backup_id")
        kubernetes_workflow = \
            ibm_draas_restore_workflow(
                data=kubernetes_data, user=user, db_session=db_session, sketch=sketch, backup_id=backup_id
            )
        draas_restore_kubernetes_id_to_workflow_roots_dict[kubernetes_data["backup_id"]] = kubernetes_workflow

        previous_root_found = False
        if kubernetes_data["resource_json"]["vpc"]["id"] in vpc_id_to_root_dict:
            vpc_workflow_root = vpc_id_to_root_dict[kubernetes_data["resource_json"]["vpc"]["id"]]
            vpc_workflow_root.add_next_root(kubernetes_workflow)
            previous_root_found = True

        for worker_pool_data in kubernetes_data["resource_json"].get("worker_pools", []):
            for zone_data in worker_pool_data.get("worker_zones", []):
                if zone_data["subnets"]["id"] not in subnet_id_to_workflow_roots_dict:
                    continue

                previous_root_found = True
                subnet_workflow_root = subnet_id_to_workflow_roots_dict[zone_data["subnets"]["id"]]
                subnet_workflow_root.add_next_root(kubernetes_workflow)

        if not previous_root_found:
            workspace.add_next_root(kubernetes_workflow)

    for restore_cluster in data.get("restore_clusters", []):
        restore_cluster_workflow = \
            create_kubernetes_restore_workflow(
                resource_type=IBMKubernetesCluster, data=restore_cluster, user=user,
                db_session=db_session, sketch=True
            )

        previous_root_found = False
        if restore_cluster["cluster"]["id"] in kubernetes_id_to_workflow_roots_dict:
            cluster_workflow_root = kubernetes_id_to_workflow_roots_dict[restore_cluster["cluster"]["id"]]
            cluster_workflow_root.add_next_root(restore_cluster_workflow)
            previous_root_found = True

        if not previous_root_found:
            workspace.add_next_root(restore_cluster_workflow)
    if "attachments_detachments" in data:
        attachment_root_mapper_dict = {
            "subnet": subnet_id_to_workflow_roots_dict,
            "floating_ip": floating_ip_id_to_workflow_roots_dict,
            "network_acl": network_acl_id_to_workflow_roots_dict,
            "routing_table": routing_table_id_to_workflow_roots_dict,
            "public_gateway": public_gateway_id_to_workflow_roots_dict,
            "network_interface": network_interface_id_to_instance_workflow_roots_dict
        }
    for attach_detach_dict in data.get("attachments_detachments", []):
        attach_detach_task = \
            compose_ibm_resource_attachment_workflow(
                resource_type_name=get_attachment_resource_name(attach_detach_dict), data=attach_detach_dict, user=user,
                db_session=db_session, sketch=sketch
            )
        previous_root_found = False
        for key_, value_ in attachment_root_mapper_dict.items():
            if attach_detach_dict.get(key_, {}).get("id") in value_:
                base_workflow_root = value_[attach_detach_dict[key_]["id"]]
                base_workflow_root.add_next_root(attach_detach_task)
                previous_root_found = True

        if not previous_root_found:
            workspace.add_next_root(base_workflow_root)

    if not sketch:
        db_session.add(workspace)

    db_session.commit()
    return workspace


def get_resource_ids(data: dict, key: str):
    return [obj["id"] for obj in data.get(key, [])]


def update_workspace_workflow(user, data, workspace_id=None, db_session=None, source_cloud=None, backup_id=None,
                              workspace_type=None):
    if not db_session:
        db_session = ibmdb.session

    workspace: WorkflowsWorkspace = db_session.query(WorkflowsWorkspace).filter_by(id=workspace_id).first()
    if not workspace:
        workspace = WorkflowsWorkspace(name=data["name"], fe_request_data=deepcopy(data), user_id=user["id"],
                                       project_id=user["project_id"], source_cloud=source_cloud,
                                       workspace_type=workspace_type)
        db_session.add(workspace)
        db_session.commit()

    fe_request_data = deepcopy(workspace.fe_request_data)

    vpc_id_to_root_dict = {}
    roots_in_use_ids = set()  # roots other than these are just stale entries. e.g. might be old roots.
    for vpc_data in data.get("vpc_networks", []):
        if vpc_data.get("status") in ["available", "CREATED"]:
            continue

        if vpc_data["id"] in get_resource_ids(fe_request_data, "vpc_networks"):
            vpc_workflow_root: WorkflowRoot = workspace.get_workflow_root(root_id=vpc_data["id"])
            if not vpc_workflow_root:
                vpc_workflow_root = create_ibm_resource_creation_workflow(
                    user=user, resource_type=IBMVpcNetwork, data=vpc_data, db_session=db_session, validate=False,
                    status=True, sketch=True
                )
                workspace.add_next_root(vpc_workflow_root)
            resource_name = vpc_data["resource_json"]["name"]
            vpc_workflow_root.workflow_name = f"{IBMVpcNetwork.__name__} {resource_name}"
            vpc_workflow_root.fe_request_data = vpc_data
        else:
            vpc_workflow_root = \
                create_ibm_resource_creation_workflow(
                    user=user, resource_type=IBMVpcNetwork, data=vpc_data, db_session=db_session, validate=False,
                    sketch=True
                )
        workspace.add_next_root(vpc_workflow_root, vpc_workflow_root.status)
        roots_in_use_ids.add(vpc_workflow_root.id)
        vpc_id_to_root_dict[vpc_data["id"]] = vpc_workflow_root

    address_prefix_workflow_roots = []
    for address_prefix_data in data.get("address_prefixes", []):
        if address_prefix_data.get("status") in ["available", "CREATED"]:
            continue
        if address_prefix_data["id"] in get_resource_ids(fe_request_data, "address_prefixes") and not backup_id:
            address_prefix_workflow_root = workspace.get_workflow_root(root_id=address_prefix_data["id"])
            if not address_prefix_workflow_root:
                address_prefix_workflow_root = create_ibm_resource_creation_workflow(
                    user=user, resource_type=IBMAddressPrefix, data=address_prefix_data, db_session=db_session,
                    validate=False, status=True
                )
                vpc_workflow_root = vpc_id_to_root_dict.get(address_prefix_data["vpc"]["id"])
                if vpc_workflow_root:
                    vpc_workflow_root.add_next_root(address_prefix_workflow_root)
                else:
                    workspace.add_next_root(address_prefix_workflow_root)

            resource_name = address_prefix_data["resource_json"]["name"]
            address_prefix_workflow_root.workflow_name = f"{IBMAddressPrefix.__name__} {resource_name}"
            address_prefix_workflow_root.fe_request_data = address_prefix_data
        else:
            address_prefix_workflow_root = \
                create_ibm_resource_creation_workflow(
                    user=user, resource_type=IBMAddressPrefix, data=address_prefix_data, db_session=db_session,
                    validate=False, sketch=True
                )
            if address_prefix_data["vpc"]["id"] not in vpc_id_to_root_dict:
                workspace.add_next_root(address_prefix_workflow_root)
                continue

            vpc_workflow_root = vpc_id_to_root_dict[address_prefix_data["vpc"]["id"]]
            vpc_workflow_root.add_next_root(address_prefix_workflow_root)

        roots_in_use_ids.add(address_prefix_workflow_root.id)
        address_prefix_workflow_roots.append(address_prefix_workflow_root)

    subnet_id_to_workflow_roots_dict = {}
    for subnet_data in data.get("subnets", []):
        if subnet_data.get("status") in ["available", "CREATED"]:
            continue

        public_gateway_id = subnet_data["resource_json"].get("public_gateway", {}).get("id")
        if public_gateway_id and not db_session.query(WorkflowTask).filter(
                WorkflowTask.resource_id == public_gateway_id).first():
            subnet_data["resource_json"].pop("public_gateway")

        if subnet_data["id"] in get_resource_ids(fe_request_data, "subnets"):
            subnet_workflow_root = workspace.get_workflow_root(root_id=subnet_data["id"])
            if not subnet_workflow_root:
                subnet_workflow_root = \
                    create_ibm_resource_creation_workflow(
                        user=user, resource_type=IBMSubnet, data=subnet_data, db_session=db_session, validate=False,
                        status=True
                    )
                for address_prefix_workflow_root in address_prefix_workflow_roots:
                    address_prefix_workflow_root.add_next_root(subnet_workflow_root)
                vpc_workflow_root = vpc_id_to_root_dict.get(subnet_data["resource_json"]["vpc"]["id"])
                if vpc_workflow_root:
                    vpc_workflow_root.add_next_root(subnet_workflow_root)
                else:
                    workspace.add_next_root(subnet_workflow_root)
            resource_name = subnet_data["resource_json"]["name"]
            subnet_workflow_root.workflow_name = f"{IBMSubnet.__name__} {resource_name}"
            subnet_workflow_root.fe_request_data = subnet_data
        else:
            subnet_workflow_root = \
                create_ibm_resource_creation_workflow(
                    user=user, resource_type=IBMSubnet, data=subnet_data, db_session=db_session, validate=False,
                    sketch=True
                )

            previous_root_found = bool(address_prefix_workflow_roots)
            for address_prefix_workflow_root in address_prefix_workflow_roots:
                address_prefix_workflow_root.add_next_root(subnet_workflow_root)

            if subnet_data["resource_json"]["vpc"]["id"] not in vpc_id_to_root_dict:
                previous_root_found = True
            else:
                vpc_workflow_root = vpc_id_to_root_dict[subnet_data["resource_json"]["vpc"]["id"]]
                vpc_workflow_root.add_next_root(subnet_workflow_root)

            if not previous_root_found:
                workspace.add_next_root(subnet_workflow_root)

        roots_in_use_ids.add(subnet_workflow_root.id)
        subnet_id_to_workflow_roots_dict[subnet_data["id"]] = subnet_workflow_root

    network_acl_id_to_workflow_roots_dict = {}
    for network_acl_data in data.get("network_acls", []):
        if network_acl_data["id"] in get_resource_ids(fe_request_data, "network_acls"):
            network_acl_workflow_root = workspace.get_workflow_root(root_id=network_acl_data["id"])
            if not network_acl_workflow_root:
                network_acl_workflow_root = \
                    create_ibm_resource_creation_workflow(
                        user=user, resource_type=IBMNetworkAcl, data=network_acl_data, db_session=db_session,
                        validate=False, sketch=True
                    )
                if not network_acl_data["resource_json"].get("subnets"):
                    if network_acl_data["resource_json"]["vpc"]["id"] not in vpc_id_to_root_dict:
                        workspace.add_next_root(network_acl_workflow_root)
                    else:
                        vpc_workflow_root = vpc_id_to_root_dict[network_acl_data["resource_json"]["vpc"]["id"]]
                        vpc_workflow_root.add_next_root(network_acl_workflow_root)

                for subnet_data in network_acl_data["resource_json"].get("subnets", []):
                    subnet_id_to_workflow_roots_dict[subnet_data["id"]].add_next_root(network_acl_workflow_root)

            resource_name = network_acl_data["resource_json"]["name"]
            network_acl_workflow_root.workflow_name = f"{IBMNetworkAcl.__name__} {resource_name}"
            network_acl_workflow_root.fe_request_data = network_acl_data

        else:
            network_acl_workflow_root = \
                create_ibm_resource_creation_workflow(
                    user=user, resource_type=IBMNetworkAcl, data=network_acl_data, db_session=db_session,
                    validate=False, sketch=True
                )
            if not network_acl_data["resource_json"].get("subnets"):
                if network_acl_data["resource_json"]["vpc"]["id"] not in vpc_id_to_root_dict:
                    workspace.add_next_root(network_acl_workflow_root)
                else:
                    vpc_workflow_root = vpc_id_to_root_dict[network_acl_data["resource_json"]["vpc"]["id"]]
                    vpc_workflow_root.add_next_root(network_acl_workflow_root)

            for subnet_data in network_acl_data["resource_json"].get("subnets", []):
                subnet_id_to_workflow_roots_dict[subnet_data["id"]].add_next_root(network_acl_workflow_root)

        roots_in_use_ids.add(network_acl_workflow_root.id)
        network_acl_id_to_workflow_roots_dict[network_acl_data["id"]] = network_acl_workflow_root

    security_group_id_to_workflow_roots_dict = {}
    for security_group_data in data.get("security_groups", []):
        if security_group_data["id"] in get_resource_ids(fe_request_data, "security_groups"):
            security_group_workflow = workspace.get_workflow_root(root_id=security_group_data["id"])
            if not security_group_workflow:
                security_group_workflow = \
                    create_ibm_resource_creation_workflow(
                        user=user, resource_type=IBMSecurityGroup, data=security_group_data, db_session=db_session,
                        validate=False, sketch=True
                    )
                if security_group_data["resource_json"]["vpc"]["id"] not in vpc_id_to_root_dict:
                    workspace.add_next_root(security_group_workflow)
                else:
                    vpc_workflow_root = vpc_id_to_root_dict[security_group_data["resource_json"]["vpc"]["id"]]
                    vpc_workflow_root.add_next_root(security_group_workflow)
            resource_name = security_group_data["resource_json"]["name"]
            security_group_workflow.workflow_name = f"{IBMSecurityGroup.__name__} {resource_name}"
            security_group_workflow.fe_request_data = security_group_data
        else:
            security_group_workflow = \
                create_ibm_resource_creation_workflow(
                    user=user, resource_type=IBMSecurityGroup, data=security_group_data, db_session=db_session,
                    validate=False, sketch=True
                )

            if security_group_data["resource_json"]["vpc"]["id"] not in vpc_id_to_root_dict:
                workspace.add_next_root(security_group_workflow)
                continue

            vpc_workflow_root = vpc_id_to_root_dict[security_group_data["resource_json"]["vpc"]["id"]]
            vpc_workflow_root.add_next_root(security_group_workflow)

        roots_in_use_ids.add(security_group_workflow.id)
        security_group_id_to_workflow_roots_dict[security_group_data["id"]] = security_group_workflow

    public_gateway_id_to_workflow_roots_dict = {}
    for public_gateway_data in data.get("public_gateways", []):
        if public_gateway_data.get("status") in ["available", "CREATED"]:
            continue
        if public_gateway_data["id"] in get_resource_ids(fe_request_data, "public_gateways"):
            public_gateway_workflow = workspace.get_workflow_root(root_id=public_gateway_data["id"])
            if not public_gateway_workflow:
                public_gateway_workflow = \
                    create_ibm_resource_creation_workflow(
                        user=user, resource_type=IBMPublicGateway, data=public_gateway_data, db_session=db_session,
                        validate=False, status=True
                    )
                vpc_workflow_root = vpc_id_to_root_dict.get(public_gateway_data["resource_json"]["vpc"]["id"])
                if vpc_workflow_root:
                    vpc_workflow_root.add_next_root(public_gateway_workflow)
                else:
                    workspace.add_next_root(public_gateway_workflow)
            resource_name = public_gateway_data["resource_json"]["name"]
            public_gateway_workflow.workflow_name = f"{IBMPublicGateway.__name__} {resource_name}"
            public_gateway_workflow.fe_request_data = public_gateway_data
        else:
            public_gateway_workflow = \
                create_ibm_resource_creation_workflow(
                    user=user, resource_type=IBMPublicGateway, data=public_gateway_data, db_session=db_session,
                    validate=False, sketch=True
                )
            if public_gateway_data["resource_json"]["vpc"]["id"] not in vpc_id_to_root_dict:
                workspace.add_next_root(public_gateway_workflow)
                continue

            vpc_workflow_root = vpc_id_to_root_dict[public_gateway_data["resource_json"]["vpc"]["id"]]
            vpc_workflow_root.add_next_root(public_gateway_workflow)

        roots_in_use_ids.add(public_gateway_workflow.id)
        public_gateway_id_to_workflow_roots_dict[public_gateway_data["id"]] = public_gateway_workflow

    routing_table_id_to_workflow_roots_dict = {}
    for routing_table_data in data.get("routing_tables", []):
        if routing_table_data["id"] in get_resource_ids(fe_request_data, "routing_tables"):
            routing_table_workflow = workspace.get_workflow_root(root_id=routing_table_data["id"])
            if not routing_table_workflow:
                routing_table_workflow = \
                    create_ibm_resource_creation_workflow(
                        user=user, resource_type=IBMRoutingTable, data=routing_table_data, db_session=db_session,
                        validate=False, sketch=True
                    )

                if routing_table_data["vpc"]["id"] not in vpc_id_to_root_dict:
                    workspace.add_next_root(routing_table_workflow)
                    continue

                vpc_workflow_root = vpc_id_to_root_dict[routing_table_data["vpc"]["id"]]
                vpc_workflow_root.add_next_root(routing_table_workflow)

            resource_name = routing_table_data["resource_json"]["name"]
            routing_table_workflow.workflow_name = f"{IBMRoutingTable.__name__} {resource_name}"
            routing_table_workflow.fe_request_data = routing_table_data
        else:
            routing_table_workflow = \
                create_ibm_resource_creation_workflow(
                    user=user, resource_type=IBMRoutingTable, data=routing_table_data, db_session=db_session,
                    validate=False, sketch=True
                )

            if routing_table_data["vpc"]["id"] not in vpc_id_to_root_dict:
                workspace.add_next_root(routing_table_workflow)
                continue

            vpc_workflow_root = vpc_id_to_root_dict[routing_table_data["resource_json"]["vpc"]["id"]]
            vpc_workflow_root.add_next_root(routing_table_workflow)

        roots_in_use_ids.add(routing_table_workflow.id)
        routing_table_id_to_workflow_roots_dict[routing_table_data["id"]] = routing_table_workflow

    placement_group_id_to_workflow_roots_dict = {}
    for placement_group_data in data.get("placement_groups", []):
        if placement_group_data["id"] in get_resource_ids(fe_request_data, "placement_groups"):
            placement_group_workflow = workspace.get_workflow_root(root_id=placement_group_data["id"])
            if not placement_group_workflow:
                placement_group_workflow = \
                    create_ibm_resource_creation_workflow(
                        user=user, resource_type=IBMPlacementGroup, data=placement_group_data, db_session=db_session,
                        validate=False, sketch=True
                    )
                workspace.add_next_root(placement_group_workflow)

            resource_name = placement_group_data["resource_json"]["name"]
            placement_group_workflow.workflow_name = f"{IBMPlacementGroup.__name__} {resource_name}"
            placement_group_workflow.fe_request_data = placement_group_data
        else:
            placement_group_workflow = \
                create_ibm_resource_creation_workflow(
                    user=user, resource_type=IBMPlacementGroup, data=placement_group_data, db_session=db_session,
                    validate=False, sketch=True
                )
            workspace.add_next_root(placement_group_workflow)

        roots_in_use_ids.add(placement_group_workflow.id)
        placement_group_id_to_workflow_roots_dict[placement_group_data["id"]] = placement_group_workflow

    ssh_key_id_to_workflow_roots_dict = {}
    for ssh_key_data in data.get("ssh_keys", []):
        if ssh_key_data["id"] in get_resource_ids(fe_request_data, "ssh_keys"):
            ssh_key_workflow = workspace.get_workflow_root(root_id=ssh_key_data["id"])
            if not ssh_key_workflow:
                ssh_key_workflow = \
                    create_ibm_resource_creation_workflow(
                        user=user, resource_type=IBMSshKey, data=ssh_key_data, db_session=db_session, validate=False,
                        sketch=True
                    )
                workspace.add_next_root(ssh_key_workflow)

            resource_name = ssh_key_data["resource_json"]["name"]
            ssh_key_workflow.workflow_name = f"{IBMSshKey.__name__} {resource_name}"
            ssh_key_workflow.fe_request_data = ssh_key_data
        else:
            ssh_key_workflow = \
                create_ibm_resource_creation_workflow(
                    user=user, resource_type=IBMSshKey, data=ssh_key_data, db_session=db_session, validate=False,
                    sketch=True
                )
            workspace.add_next_root(ssh_key_workflow)

        roots_in_use_ids.add(ssh_key_workflow.id)
        ssh_key_id_to_workflow_roots_dict[ssh_key_data["id"]] = ssh_key_workflow

    dedicated_host_group_id_to_workflow_roots_dict = {}
    for dh_group_data in data.get("dedicated_host_groups", []):
        if dh_group_data["id"] in get_resource_ids(fe_request_data, "dedicated_host_groups"):
            dedicated_host_group_workflow = workspace.get_workflow_root(root_id=dh_group_data["id"])
            if not dedicated_host_group_workflow:
                dedicated_host_group_workflow = \
                    create_ibm_resource_creation_workflow(
                        user=user, resource_type=IBMDedicatedHostGroup, data=dh_group_data, db_session=db_session,
                        validate=False, sketch=True
                    )
                workspace.add_next_root(dedicated_host_group_workflow)

            resource_name = dh_group_data["resource_json"]["name"]
            dedicated_host_group_workflow.workflow_name = f"{IBMDedicatedHostGroup.__name__} {resource_name}"
            dedicated_host_group_workflow.fe_request_data = dh_group_data
        else:
            dedicated_host_group_workflow = \
                create_ibm_resource_creation_workflow(
                    user=user, resource_type=IBMDedicatedHostGroup, data=dh_group_data, db_session=db_session,
                    validate=False, sketch=True
                )
            workspace.add_next_root(dedicated_host_group_workflow)

        roots_in_use_ids.add(dedicated_host_group_workflow.id)
        dedicated_host_group_id_to_workflow_roots_dict[dh_group_data["id"]] = dedicated_host_group_workflow

    dedicated_host_id_to_workflow_roots_dict = {}
    for dedicated_host_data in data.get("dedicated_hosts", []):
        if dedicated_host_data["id"] in get_resource_ids(fe_request_data, "dedicated_hosts"):
            dedicated_host_workflow = workspace.get_workflow_root(root_id=dedicated_host_data["id"])
            if not dedicated_host_workflow:
                dedicated_host_workflow = \
                    create_ibm_resource_creation_workflow(
                        user=user, resource_type=IBMDedicatedHost, data=dedicated_host_data, db_session=db_session,
                        validate=False, sketch=True
                    )
                dh_group = dedicated_host_data["resource_json"].get("group")
                if dh_group and dh_group["id"] in dedicated_host_group_id_to_workflow_roots_dict:
                    dedicated_host_group_workflow = \
                        dedicated_host_group_id_to_workflow_roots_dict[
                            dedicated_host_data["resource_json"]["group"]["id"]
                        ]
                    dedicated_host_group_workflow.add_next_root(dedicated_host_workflow)
                workspace.add_next_root(dedicated_host_workflow)

            resource_name = dedicated_host_data["resource_json"]["name"]
            dedicated_host_workflow.workflow_name = f"{IBMDedicatedHost.__name__} {resource_name}"
            dedicated_host_workflow.fe_request_data = dedicated_host_data
        else:
            dedicated_host_workflow = \
                create_ibm_resource_creation_workflow(
                    user=user, resource_type=IBMDedicatedHost, data=dedicated_host_data, db_session=db_session,
                    validate=False, sketch=True
                )
            dh_group = dedicated_host_data["resource_json"].get("group")
            if dh_group and dh_group["id"] in dedicated_host_group_id_to_workflow_roots_dict:
                dedicated_host_group_workflow = \
                    dedicated_host_group_id_to_workflow_roots_dict[
                        dedicated_host_data["resource_json"]["group"]["id"]
                    ]
                dedicated_host_group_workflow.add_next_root(dedicated_host_workflow)
            workspace.add_next_root(dedicated_host_workflow)

        roots_in_use_ids.add(dedicated_host_workflow.id)
        dedicated_host_id_to_workflow_roots_dict[dedicated_host_data["id"]] = dedicated_host_workflow

    instance_id_to_workflow_roots_dict = {}
    network_interface_id_to_instance_workflow_roots_dict = {}
    for instance_data in data.get("instances", []):
        if instance_data["id"] not in get_resource_ids(fe_request_data, "instances"):
            continue
        instance_workflow = workspace.get_workflow_root(root_id=instance_data["id"])
        if instance_workflow and instance_workflow.status in [
            WorkflowRoot.STATUS_RUNNING, WorkflowRoot.STATUS_C_SUCCESSFULLY,
            WorkflowRoot.STATUS_C_SUCCESSFULLY
        ]:
            continue
        elif instance_workflow and instance_workflow.status in [
            WorkflowRoot.STATUS_C_W_FAILURE, WorkflowRoot.STATUS_C_W_FAILURE_WFC
        ]:
            update_root_data_and_task_metadata(
                workflow_root=instance_workflow, data=instance_data, db_session=db_session
            )
        else:
            instance_workflow = create_ibm_instance_creation_workflow(
                user=user, data=instance_data, db_session=db_session, sketch=True
            )
        previous_root_found = False
        for ssh_key_data in instance_data["resource_json"]["keys"]:
            if ssh_key_data["id"] not in ssh_key_id_to_workflow_roots_dict:
                continue

            previous_root_found = True
            ssh_key_id_to_workflow_roots_dict[ssh_key_data["id"]].add_next_root(instance_workflow)

        placement_target = instance_data["resource_json"].get("placement_target", {})
        if "dedicated_host_group" in placement_target:
            dedicated_host_group_id = placement_target["dedicated_host_group"]["id"]
            if dedicated_host_group_id in dedicated_host_group_id_to_workflow_roots_dict:
                previous_root_found = True
                dedicated_host_group_workflow = dedicated_host_group_id_to_workflow_roots_dict[
                    dedicated_host_group_id]
                dedicated_host_group_workflow.add_next_root(instance_workflow)
        elif "dedicated_host" in placement_target:
            dedicated_host_id = placement_target["dedicated_host"]["id"]
            if dedicated_host_id in dedicated_host_id_to_workflow_roots_dict:
                previous_root_found = True
                dedicated_host_workflow = dedicated_host_id_to_workflow_roots_dict[dedicated_host_id]
                dedicated_host_workflow.add_next_root(instance_workflow)
        elif "placement_group" in placement_target:
            placement_group_group_id = placement_target["placement_group"]["id"]
            placement_group_workflow = placement_group_id_to_workflow_roots_dict[placement_group_group_id]
            placement_group_workflow.add_next_root(instance_workflow)

        for network_interface_json in instance_data["resource_json"].get("network_interfaces", []):
            if network_interface_json["subnet"]["id"] in subnet_id_to_workflow_roots_dict:
                subnet_id_to_workflow_roots_dict[network_interface_json["subnet"]["id"]].add_next_root(
                    instance_workflow)
                previous_root_found = True
                network_interface_id_to_instance_workflow_roots_dict[
                    network_interface_json["id"]] = instance_workflow

            for security_group in network_interface_json.get("security_groups", []):
                sec_grp_id = security_group["id"]
                if sec_grp_id in security_group_id_to_workflow_roots_dict:
                    previous_root_found = True
                    security_group_id_to_workflow_roots_dict[sec_grp_id].add_next_root(instance_workflow)

        primary_network_interface = instance_data["resource_json"]["primary_network_interface"]
        if primary_network_interface["subnet"]["id"] in subnet_id_to_workflow_roots_dict:
            previous_root_found = True
            subnet_workflow_root = subnet_id_to_workflow_roots_dict[primary_network_interface["subnet"]["id"]]
            network_interface_id_to_instance_workflow_roots_dict[
                primary_network_interface["id"]] = instance_workflow
            subnet_workflow_root.add_next_root(instance_workflow)

        for security_group in primary_network_interface.get("security_groups", []):
            sec_grp_id = security_group["id"]
            if sec_grp_id in security_group_id_to_workflow_roots_dict:
                previous_root_found = True
                security_group_id_to_workflow_roots_dict[sec_grp_id].add_next_root(instance_workflow)

        if instance_data["resource_json"]["vpc"]["id"] in vpc_id_to_root_dict:
            previous_root_found = True
            vpc_workflow_root = vpc_id_to_root_dict[instance_data["resource_json"]["vpc"]["id"]]
            vpc_workflow_root.add_next_root(instance_workflow)

        if not previous_root_found:
            workspace.add_next_root(instance_workflow)

        roots_in_use_ids.add(instance_workflow.id)
        instance_id_to_workflow_roots_dict[instance_data["id"]] = instance_workflow

    floating_ip_id_to_workflow_roots_dict = {}
    for floating_ip_data in data.get("floating_ips", []):
        if floating_ip_data["id"] in get_resource_ids(fe_request_data, "floating_ips"):
            floating_ip_workflow = workspace.get_workflow_root(root_id=floating_ip_data["id"])
            if not floating_ip_workflow:
                floating_ip_workflow = \
                    create_ibm_resource_creation_workflow(
                        user=user, resource_type=IBMFloatingIP, data=floating_ip_data, db_session=db_session,
                        validate=False, sketch=True
                    )

                if floating_ip_data["resource_json"]["target"]["id"] \
                        not in network_interface_id_to_instance_workflow_roots_dict:
                    workspace.add_next_root(floating_ip_workflow)
                    continue

                instance_workflow = \
                    network_interface_id_to_instance_workflow_roots_dict[
                        floating_ip_data["resource_json"]["target"]["id"]
                    ]
                # TODO: network_interface is supported, check for the public_gateway support.
                instance_workflow.add_next_root(floating_ip_workflow)

            resource_name = floating_ip_data["resource_json"]["name"]
            floating_ip_workflow.workflow_name = f"{IBMFloatingIP.__name__} {resource_name}"
            floating_ip_workflow.fe_request_data = floating_ip_data
        else:
            floating_ip_workflow = \
                create_ibm_resource_creation_workflow(
                    user=user, resource_type=IBMFloatingIP, data=floating_ip_data, db_session=db_session,
                    validate=False, sketch=True
                )

            if floating_ip_data["resource_json"]["target"]["id"] \
                    not in network_interface_id_to_instance_workflow_roots_dict:
                workspace.add_next_root(floating_ip_workflow)
                continue

            instance_workflow = \
                network_interface_id_to_instance_workflow_roots_dict[
                    floating_ip_data["resource_json"]["target"]["id"]
                ]
            # TODO: network_interface is supported, check for the public_gateway support.
            instance_workflow.add_next_root(floating_ip_workflow)

        roots_in_use_ids.add(floating_ip_workflow.id)
        floating_ip_id_to_workflow_roots_dict[floating_ip_data["id"]] = floating_ip_workflow

    load_balancer_id_to_workflow_roots_dict = {}
    for load_balancer_data in data.get("load_balancers", []):
        if load_balancer_data["id"] in get_resource_ids(fe_request_data, "load_balancers"):
            load_balancer_workflow_root = workspace.get_workflow_root(root_id=load_balancer_data["id"])
            if not load_balancer_workflow_root:
                load_balancer_workflow_root = \
                    create_ibm_resource_creation_workflow(
                        user=user, resource_type=IBMLoadBalancer, data=load_balancer_data, db_session=db_session,
                        validate=False, sketch=True
                    )

                previous_root_found = False
                for subnet_data in load_balancer_data["resource_json"].get("subnets", []):
                    if subnet_data["id"] not in subnet_id_to_workflow_roots_dict:
                        continue

                    previous_root_found = True
                    subnet_id_to_workflow_roots_dict[subnet_data["id"]].add_next_root(load_balancer_workflow_root)

                for sec_grp_data in load_balancer_data["resource_json"].get("security_groups", []):
                    if sec_grp_data["id"] not in security_group_id_to_workflow_roots_dict:
                        continue

                    previous_root_found = True
                    security_group_id_to_workflow_roots_dict[sec_grp_data["id"]].add_next_root(
                        load_balancer_workflow_root)

                for pool_data in load_balancer_data["resource_json"].get("pools", []):
                    for member_data in pool_data.get("members", []):
                        if member_data["target"]["id"] not in [instance_id_to_workflow_roots_dict,
                                                               network_interface_id_to_instance_workflow_roots_dict]:
                            continue

                        previous_root_found = True
                        if member_data["target"]["type"] == "instance":
                            instance_id_to_workflow_roots_dict[member_data["target"]["id"]].add_next_root(
                                load_balancer_workflow_root)
                        elif member_data["target"]["type"] == "network_interface":
                            network_interface_id_to_instance_workflow_roots_dict[
                                member_data["target"]["id"]].add_next_root(
                                load_balancer_workflow_root)

                if not previous_root_found:
                    workspace.add_next_root(load_balancer_workflow_root)

            resource_name = load_balancer_data["resource_json"]["name"]
            load_balancer_workflow_root.workflow_name = f"{IBMLoadBalancer.__name__} {resource_name}"
            load_balancer_workflow_root.fe_request_data = load_balancer_data
        else:
            load_balancer_workflow_root = \
                create_ibm_resource_creation_workflow(
                    user=user, resource_type=IBMLoadBalancer, data=load_balancer_data, db_session=db_session,
                    validate=False, sketch=True
                )

            previous_root_found = False
            for subnet_data in load_balancer_data["resource_json"].get("subnets", []):
                if subnet_data["id"] not in subnet_id_to_workflow_roots_dict:
                    continue

                previous_root_found = True
                subnet_id_to_workflow_roots_dict[subnet_data["id"]].add_next_root(load_balancer_workflow_root)

            for sec_grp_data in load_balancer_data["resource_json"].get("security_groups", []):
                if sec_grp_data["id"] not in security_group_id_to_workflow_roots_dict:
                    continue

                previous_root_found = True
                security_group_id_to_workflow_roots_dict[sec_grp_data["id"]].add_next_root(load_balancer_workflow_root)

            for pool_data in load_balancer_data["resource_json"].get("pools", []):
                for member_data in pool_data.get("members", []):
                    if member_data["target"]["id"] not in [instance_id_to_workflow_roots_dict,
                                                           network_interface_id_to_instance_workflow_roots_dict]:
                        continue

                    previous_root_found = True
                    if member_data["target"]["type"] == "instance":
                        instance_id_to_workflow_roots_dict[member_data["target"]["id"]].add_next_root(
                            load_balancer_workflow_root)
                    elif member_data["target"]["type"] == "network_interface":
                        network_interface_id_to_instance_workflow_roots_dict[member_data["target"]["id"]].add_next_root(
                            load_balancer_workflow_root)

            if not previous_root_found:
                workspace.add_next_root(load_balancer_workflow_root)

        roots_in_use_ids.add(load_balancer_workflow_root.id)
        load_balancer_id_to_workflow_roots_dict[load_balancer_data["id"]] = load_balancer_workflow_root

    ipsec_policy_id_to_workflow_roots_dict = {}
    for ipsec_policy_data in data.get("ipsec_policies", []):
        if ipsec_policy_data["id"] in get_resource_ids(fe_request_data, "ipsec_policies"):
            ipsec_policy_workflow = workspace.get_workflow_root(root_id=ipsec_policy_data["id"])
            if not ipsec_policy_workflow:
                ipsec_policy_workflow = \
                    create_ibm_resource_creation_workflow(
                        user=user, resource_type=IBMIPSecPolicy, data=ipsec_policy_data, db_session=db_session,
                        validate=False, sketch=True
                    )
                workspace.add_next_root(ipsec_policy_workflow)

            resource_name = ipsec_policy_data["resource_json"]["name"]
            ipsec_policy_workflow.workflow_name = f"{IBMIPSecPolicy.__name__} {resource_name}"
            ipsec_policy_workflow.fe_request_data = ipsec_policy_data
        else:
            ipsec_policy_workflow = \
                create_ibm_resource_creation_workflow(
                    user=user, resource_type=IBMIPSecPolicy, data=ipsec_policy_data, db_session=db_session,
                    validate=False, sketch=True
                )
            workspace.add_next_root(ipsec_policy_workflow)

        roots_in_use_ids.add(ipsec_policy_workflow.id)
        ipsec_policy_id_to_workflow_roots_dict[ipsec_policy_data["id"]] = ipsec_policy_workflow

    ike_policy_id_to_workflow_roots_dict = {}
    for ike_policy_data in data.get("ike_policies", []):
        if ike_policy_data["id"] in get_resource_ids(fe_request_data, "ike_policies"):
            ike_policy_workflow = workspace.get_workflow_root(root_id=ike_policy_data["id"])
            if not ike_policy_workflow:
                ike_policy_workflow = \
                    create_ibm_resource_creation_workflow(
                        user=user, resource_type=IBMIKEPolicy, data=ike_policy_data, db_session=db_session,
                        validate=False, sketch=True
                    )
                workspace.add_next_root(ike_policy_workflow)

            resource_name = ike_policy_data["resource_json"]["name"]
            ike_policy_workflow.workflow_name = f"{IBMIKEPolicy.__name__} {resource_name}"
            ike_policy_workflow.fe_request_data = ike_policy_data
        else:
            ike_policy_workflow = \
                create_ibm_resource_creation_workflow(
                    user=user, resource_type=IBMIKEPolicy, data=ike_policy_data, db_session=db_session, validate=False,
                    sketch=True
                )
            workspace.add_next_root(ike_policy_workflow)
        roots_in_use_ids.add(ike_policy_workflow.id)
        ike_policy_id_to_workflow_roots_dict[ike_policy_data["id"]] = ike_policy_workflow

    vpn_gateway_id_to_workflow_roots_dict = {}
    for vpn_gateway_data in data.get("vpn_gateways", []):
        if vpn_gateway_data["id"] in get_resource_ids(fe_request_data, "vpn_gateways"):
            vpn_gateway_workflow = workspace.get_workflow_root(root_id=vpn_gateway_data["id"])
            if not vpn_gateway_workflow:
                vpn_gateway_workflow = \
                    create_ibm_resource_creation_workflow(
                        user=user, resource_type=IBMVpnGateway, data=vpn_gateway_data, db_session=db_session,
                        validate=False, sketch=True
                    )

                previous_root_found = False
                if "subnet" in vpn_gateway_data["resource_json"]:
                    subnet_id = vpn_gateway_data["resource_json"]["subnet"]["id"]
                    if subnet_id not in subnet_id_to_workflow_roots_dict:
                        continue

                    previous_root_found = True
                    subnet_workflow_root = subnet_id_to_workflow_roots_dict[subnet_id]
                    subnet_workflow_root.add_next_root(vpn_gateway_workflow)

                for connection_data in vpn_gateway_data["resource_json"].get("connections", []):
                    ipsec_policy = connection_data.get("ipsec_policy")
                    if ipsec_policy and ipsec_policy["id"] in ipsec_policy_id_to_workflow_roots_dict:
                        previous_root_found = True
                        ipsec_policy_workflow = ipsec_policy_id_to_workflow_roots_dict[ipsec_policy["id"]]
                        ipsec_policy_workflow.add_next_root(vpn_gateway_workflow)

                    ike_policy = connection_data.get("ike_policy")
                    if ike_policy and ike_policy["id"] in ike_policy_id_to_workflow_roots_dict:
                        previous_root_found = True
                        ike_policy_workflow = ike_policy_id_to_workflow_roots_dict[ike_policy["id"]]
                        ike_policy_workflow.add_next_root(vpn_gateway_workflow)

                if not previous_root_found:
                    workspace.add_next_root(vpn_gateway_workflow)

            resource_name = vpn_gateway_data["resource_json"]["name"]
            vpn_gateway_workflow.workflow_name = f"{IBMVpnGateway.__name__} {resource_name}"
            vpn_gateway_workflow.fe_request_data = vpn_gateway_data
        else:
            vpn_gateway_workflow = \
                create_ibm_resource_creation_workflow(
                    user=user, resource_type=IBMVpnGateway, data=vpn_gateway_data, db_session=db_session,
                    validate=False, sketch=True
                )

            previous_root_found = False
            if "subnet" in vpn_gateway_data["resource_json"]:
                subnet_id = vpn_gateway_data["resource_json"]["subnet"]["id"]
                if subnet_id not in subnet_id_to_workflow_roots_dict:
                    continue

                previous_root_found = True
                subnet_workflow_root = subnet_id_to_workflow_roots_dict[subnet_id]
                subnet_workflow_root.add_next_root(vpn_gateway_workflow)

            for connection_data in vpn_gateway_data["resource_json"].get("connections", []):
                ipsec_policy = connection_data.get("ipsec_policy")
                if ipsec_policy and ipsec_policy["id"] in ipsec_policy_id_to_workflow_roots_dict:
                    previous_root_found = True
                    ipsec_policy_workflow = ipsec_policy_id_to_workflow_roots_dict[ipsec_policy["id"]]
                    ipsec_policy_workflow.add_next_root(vpn_gateway_workflow)

                ike_policy = connection_data.get("ike_policy")
                if ike_policy and ike_policy["id"] in ike_policy_id_to_workflow_roots_dict:
                    previous_root_found = True
                    ike_policy_workflow = ike_policy_id_to_workflow_roots_dict[ike_policy["id"]]
                    ike_policy_workflow.add_next_root(vpn_gateway_workflow)

            if not previous_root_found:
                workspace.add_next_root(vpn_gateway_workflow)

        roots_in_use_ids.add(vpn_gateway_workflow.id)
        vpn_gateway_id_to_workflow_roots_dict[vpn_gateway_data["id"]] = vpn_gateway_workflow

    attachment_w_root_ids_dict = {}
    for attach_detach_dict in data.get("attachments_detachments", []):
        attachment_root_mapper_dict = {
            "subnet": subnet_id_to_workflow_roots_dict,
            "floating_ip": floating_ip_id_to_workflow_roots_dict,
            "network_acl": network_acl_id_to_workflow_roots_dict,
            "routing_table": routing_table_id_to_workflow_roots_dict,
            "public_gateway": public_gateway_id_to_workflow_roots_dict,
            "network_interface": network_interface_id_to_instance_workflow_roots_dict
        }
        attach_detach_root = \
            compose_ibm_resource_attachment_workflow(
                resource_type_name=get_attachment_resource_name(deepcopy(attach_detach_dict)),
                data=deepcopy(attach_detach_dict), user=user, db_session=db_session
            )
        for resource_type, resource_root_dict in attachment_root_mapper_dict.items():
            if attach_detach_dict.get(resource_type, {}).get("id") in resource_root_dict:
                attachment_w_root_ids_dict[attach_detach_dict[resource_type]["id"]] = attach_detach_root
                base_workflow_root = resource_root_dict[attach_detach_dict[resource_type]["id"]]
                base_workflow_root.add_next_root(attach_detach_root)

        workspace.add_next_root(attach_detach_root)
        roots_in_use_ids.add(attach_detach_root.id)

    kubernetes_id_to_workflow_roots_dict = {}
    for kubernetes_data in data.get("kubernetes_clusters", []):
        if kubernetes_data["id"] in get_resource_ids(fe_request_data, "kubernetes"):
            kubernetes_workflow = workspace.get_workflow_root(root_id=kubernetes_data["id"])
            if not kubernetes_workflow:
                kubernetes_workflow = \
                    create_ibm_kubernetes_cluster_migration_workflow(
                        data=kubernetes_data, user=user, db_session=db_session, sketch=True
                    )

                previous_root_found = False
                if kubernetes_data["resource_json"]["vpc"]["id"] in vpc_id_to_root_dict:
                    vpc_workflow_root = vpc_id_to_root_dict[kubernetes_data["resource_json"]["vpc"]["id"]]
                    vpc_workflow_root.add_next_root(kubernetes_workflow)
                    previous_root_found = True

                for worker_pool_data in kubernetes_data["resource_json"].get("worker_pools", []):
                    for zone_data in worker_pool_data.get("worker_zones", []):
                        if zone_data["subnets"]["id"] not in subnet_id_to_workflow_roots_dict:
                            continue

                        previous_root_found = True
                        subnet_workflow_root = subnet_id_to_workflow_roots_dict[zone_data["subnets"]["id"]]
                        subnet_workflow_root.add_next_root(kubernetes_workflow)

                        if zone_data["subnets"]["id"] in attachment_w_root_ids_dict:
                            subnet_public_gateway_attachment_root = attachment_w_root_ids_dict[
                                zone_data["subnets"]["id"]]
                            subnet_public_gateway_attachment_root.add_next_root(kubernetes_workflow)

                if not previous_root_found:
                    workspace.add_next_root(kubernetes_workflow)

            resource_name = kubernetes_data["resource_json"]["name"]
            kubernetes_workflow.workflow_name = f"{IBMKubernetesCluster.__name__} {resource_name}"
            kubernetes_workflow.fe_request_data = kubernetes_data
        else:
            kubernetes_workflow = \
                create_ibm_kubernetes_cluster_migration_workflow(
                    data=kubernetes_data, user=user, db_session=db_session, sketch=True
                )

            previous_root_found = False
            if kubernetes_data["resource_json"]["vpc"]["id"] in vpc_id_to_root_dict:
                vpc_workflow_root = vpc_id_to_root_dict[kubernetes_data["resource_json"]["vpc"]["id"]]
                vpc_workflow_root.add_next_root(kubernetes_workflow)
                previous_root_found = True

            for worker_pool_data in kubernetes_data["resource_json"].get("worker_pools", []):
                for zone_data in worker_pool_data.get("worker_zones", []):
                    if zone_data["subnets"]["id"] not in subnet_id_to_workflow_roots_dict:
                        continue

                    previous_root_found = True
                    subnet_workflow_root = subnet_id_to_workflow_roots_dict[zone_data["subnets"]["id"]]
                    subnet_workflow_root.add_next_root(kubernetes_workflow)

                    if zone_data["subnets"]["id"] in attachment_w_root_ids_dict:
                        subnet_public_gateway_attachment_root = attachment_w_root_ids_dict[zone_data["subnets"]["id"]]
                        subnet_public_gateway_attachment_root.add_next_root(kubernetes_workflow)

            if not previous_root_found:
                workspace.add_next_root(kubernetes_workflow)

        roots_in_use_ids.add(kubernetes_workflow.id)
        kubernetes_id_to_workflow_roots_dict[kubernetes_data["id"]] = kubernetes_workflow
    draas_restore_kubernetes_id_to_workflow_roots_dict = {}
    draas_restore = False
    for restore_cluster in data.get("restore_clusters", []):
        restore_cluster_workflow = \
            create_kubernetes_restore_workflow(
                resource_type=IBMKubernetesCluster, data=restore_cluster, user=user,
                db_session=db_session, sketch=True
            )

        previous_root_found = False
        if restore_cluster["cluster"]["id"] in kubernetes_id_to_workflow_roots_dict:
            cluster_workflow_root = kubernetes_id_to_workflow_roots_dict[restore_cluster["cluster"]["id"]]
            cluster_workflow_root.add_next_root(restore_cluster_workflow)
            previous_root_found = True

        if not previous_root_found:
            workspace.add_next_root(restore_cluster_workflow)

        roots_in_use_ids.add(restore_cluster_workflow.id)
    for kubernetes_data in data.get("draas_restore_clusters", []):
        draas_restore = True
        backup_id = kubernetes_data.get("backup_id")
        kubernetes_workflow = \
            ibm_draas_restore_workflow(
                data=kubernetes_data, user=user, db_session=db_session, backup_id=backup_id
            )
        draas_restore_kubernetes_id_to_workflow_roots_dict[kubernetes_data["backup_id"]] = kubernetes_workflow

        previous_root_found = False
        if kubernetes_data["resource_json"]["vpc"]["id"] in vpc_id_to_root_dict:
            vpc_workflow_root = vpc_id_to_root_dict[kubernetes_data["resource_json"]["vpc"]["id"]]
            vpc_workflow_root.add_next_root(kubernetes_workflow)
            previous_root_found = True

        for worker_pool_data in kubernetes_data["resource_json"].get("worker_pools", []):
            for zone_data in worker_pool_data.get("worker_zones", []):
                if zone_data["subnets"]["id"] not in subnet_id_to_workflow_roots_dict:
                    continue

                previous_root_found = True
                subnet_workflow_root = subnet_id_to_workflow_roots_dict[zone_data["subnets"]["id"]]
                subnet_workflow_root.add_next_root(kubernetes_workflow)
        if not previous_root_found:
            workspace.add_next_root(kubernetes_workflow)

    if draas_restore:
        if "attachments_detachments" in data:
            attachment_root_mapper_dict = {
                "subnet": subnet_id_to_workflow_roots_dict,
                "floating_ip": floating_ip_id_to_workflow_roots_dict,
                "network_acl": network_acl_id_to_workflow_roots_dict,
                "routing_table": routing_table_id_to_workflow_roots_dict,
                "public_gateway": public_gateway_id_to_workflow_roots_dict,
                "network_interface": network_interface_id_to_instance_workflow_roots_dict
            }
        for attach_detach_dict in data.get("attachments_detachments", []):
            attach_detach_task = \
                compose_ibm_resource_attachment_workflow(
                    resource_type_name=get_attachment_resource_name(attach_detach_dict), data=attach_detach_dict,
                    user=user,
                    db_session=db_session)
            previous_root_found = False
            for key_, value_ in attachment_root_mapper_dict.items():
                if attach_detach_dict.get(key_, {}).get("id") in value_:
                    base_workflow_root = value_[attach_detach_dict[key_]["id"]]
                    base_workflow_root.add_next_root(attach_detach_task)
                    previous_root_found = True

            if not previous_root_found:
                workspace.add_next_root(base_workflow_root)

        db_session.add(workspace)

        db_session.commit()
        return workspace

    workspace.fe_request_data = deepcopy(data)

    workspace.name = data["name"]
    workspace_stale_associated_roots = \
        workspace.associated_roots.filter(~WorkflowRoot.id.in_(roots_in_use_ids)).filter(
            WorkflowRoot.status != WorkflowRoot.STATUS_RUNNING).all()
    db_session.commit()
    for row in workspace_stale_associated_roots:
        try:
            db_session.delete(row)
            db_session.commit()
        except StaleDataError:
            # TODO need to check this, why is this issue occurring, temp fix
            db_session.rollback()
    if workspace.status == WorkflowsWorkspace.STATUS_C_SUCCESSFULLY:
        workspace.status = WorkflowsWorkspace.STATUS_ON_HOLD_WITH_SUCCESS
    elif workspace.status == WorkflowsWorkspace.STATUS_C_W_FAILURE:
        workspace.status = WorkflowsWorkspace.STATUS_ON_HOLD_WITH_FAILURE

    db_session.commit()
    return workspace
