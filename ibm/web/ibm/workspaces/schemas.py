import uuid

from marshmallow import INCLUDE, Schema
from marshmallow.fields import Boolean, DateTime, Dict, List, Nested, String
from marshmallow.validate import Length, OneOf, Regexp

from ibm.common.req_resp_schemas.consts import DATE_TIME_FORMAT, IBM_UUID_PATTERN
from ibm.models import WorkflowsWorkspace


class IBMWorkspaceAttachDetachSchema(Schema):
    network_interface = Nested("OptionalIDNameSchema")
    routing_table = Nested("OptionalIDNameSchema")
    public_gateway = Nested("OptionalIDNameSchema")
    network_acl = Nested("OptionalIDNameSchema")
    floating_ip = Nested("OptionalIDNameSchema")
    subnet = Nested("OptionalIDNameSchema")
    type = String(required=True, validate=OneOf(["ATTACH", "DETACH"]))


class IBMWorkspaceCreationSchema(Schema):
    vpc_networks = Nested("IBMVpcNetworkInSchema", many=True, unknown=INCLUDE)
    address_prefixes = Nested("IBMAddressPrefixInSchema", many=True, unknown=INCLUDE)
    subnets = Nested("IBMSubnetInSchema", many=True, unknown=INCLUDE)
    network_acls = Nested("IBMAclInSchema", many=True, unknown=INCLUDE)
    load_balancers = Nested("IBMLoadBalancerInSchema", many=True, unknown=INCLUDE)
    public_gateways = Nested("IBMPublicGatewayInSchema", many=True, unknown=INCLUDE)
    routing_tables = Nested("IBMRoutingTableInSchema", many=True, unknown=INCLUDE)
    security_groups = Nested("IBMSecurityGroupInSchema", many=True, unknown=INCLUDE)
    placement_groups = Nested("IBMPlacementGroupInSchema", many=True, unknown=INCLUDE)
    ssh_keys = Nested("IBMSshKeyInSchema", many=True, unknown=INCLUDE)
    instances = Nested("IBMInstanceInSchema", many=True, unknown=INCLUDE)
    dedicated_hosts = Nested("IBMDedicatedHostInSchema", many=True, unknown=INCLUDE)
    dedicated_host_groups = Nested("IBMDedicatedHostGroupInSchema", many=True, unknown=INCLUDE)
    floating_ips = Nested("IBMInstanceInSchema", many=True, unknown=INCLUDE)
    endpoint_gateways = Nested("IBMEndpointGatewayInSchema", many=True, unknown=INCLUDE)
    vpn_gateways = Nested("IBMVpnGatewayInSchema", many=True, unknown=INCLUDE)
    ike_policies = Nested("IBMIKEPoliciesInSchema", many=True, unknown=INCLUDE)
    ipsec_policies = Nested("IBMIPSecPoliciesInSchema", many=True, unknown=INCLUDE)
    kubernetes_clusters = Nested("IBMKubernetesClusterInSchema", many=True, unknown=INCLUDE)
    draas_restore_clusters = Nested("DRaaSIKSRestoreInSchema", many=True, unknown=INCLUDE)
    name = String(validate=Length(min=1, max=128), description="Any custom name for the workspace", required=True)
    restore_clusters = Nested("ClusterRestoreInSchema", many=True, unknown=INCLUDE)
    source_cloud = String(required=False, validate=OneOf(WorkflowsWorkspace.ALL_CLOUDS))
    workspace_type = String(required=False, validate=OneOf(WorkflowsWorkspace.ALL_WORKSPACE_TYPES))
    attachments_detachments = Nested(IBMWorkspaceAttachDetachSchema, many=True)


class IBMExecuteRootsInSchema(Schema):
    roots = List(
        String(), required=True
    )


class IBMExecuteRootsOutSchema(Schema):
    workspace_id = String(required=True, allow_none=False, example=uuid.uuid4().hex,
                          validate=(Regexp(IBM_UUID_PATTERN), Length(equal=32)))


class WorkspaceTypeQuerySchema(Schema):
    workspace_type = String(required=False, allow_none=True, validate=OneOf(WorkflowsWorkspace.ALL_WORKSPACE_TYPES))


class WorkflowsWorkspaceOutSchema(Schema):
    id = String(required=True, validate=Length(equal=32))
    name = String(required=True, allow_none=True, validate=Length(max=128))
    fe_request_data = Dict(required=True, allow_none=True)
    recently_provisioned_roots = List(String, required=True)
    status = String(required=True, validate=OneOf(WorkflowsWorkspace.ALL_STATUSES_LIST))
    source_cloud = String(required=True, validate=OneOf(WorkflowsWorkspace.ALL_CLOUDS))
    workspace_type = String(required=True, validate=OneOf(WorkflowsWorkspace.ALL_WORKSPACE_TYPES))
    created_at = DateTime(required=True, format=DATE_TIME_FORMAT)
    is_created = Boolean(required=True)
    completed_at = DateTime(required=True, allow_none=True, format=DATE_TIME_FORMAT)


class WorkflowsWorkspaceRefOutSchema(WorkflowsWorkspaceOutSchema):
    class Meta:
        fields = ("id", "name", "status", "is_created", "recently_provisioned_roots")


class WorkflowsWorkspaceWithRootsOutSchema(WorkflowsWorkspaceOutSchema):
    associated_roots = List(Nested("WorkflowRootWithTasksOutSchema"), validate=Length(min=1))


class IBMAllRegionalResourcesOutSchema(Schema):
    vpc_networks = Nested("IBMVpcNetworkValidateJsonOutSchema", many=True, required=True,
                          description="List of all VPCs for the provided region")
    subnets = Nested("IBMSubnetValidateJsonOutSchema", many=True, required=True,
                     description="List of all Subnets for the provided region")
    public_gateways = Nested("IBMPublicGatewayValidateJsonOutSchema", many=True, required=True,
                             description="List of all Public Gateways for the provided region")
    vpn_gateways = Nested("IBMVpnGatewayValidateJsonOutSchema", many=True, required=True,
                          description="List of all VPN Gateways for the provided region")
    ike_policies = Nested("IBMIKEPolicyValidateJsonOutSchema", many=True, required=True,
                          description="List of all IKE Policies for the provided region")
    ipsec_policies = Nested("IBMIPSecPolicyValidateJsonOutSchema", many=True, required=True,
                            description="List of all IPSEC POLICIES for the provided region")
    instances = Nested("IBMInstanceValidateJsonOutSchema", many=True, required=True,
                       description="List of all Instances for the provided region")
    network_acls = Nested("IBMAclValidateJsonOutSchema", many=True, required=True,
                          description="List of all ACLs for the provided region")
    security_groups = Nested("IBMSecurityGroupValidateJsonOutSchema", many=True, required=True,
                             description="List of all Security Groups for the provided region")
    load_balancers = Nested("IBMLoadBalancerValidateJsonOutSchema", many=True, required=True,
                            description="List of all Load Balancers for the provided region")
    dedicated_hosts = Nested("IBMDedicatedHostValidateJsonOutSchema", many=True, required=True,
                             description="List of all Dedicated Hosts for the provided region")
    placement_groups = Nested("IBMPlacementGroupValidateJsonOutSchema", many=True, required=True,
                              description="List of all Placement Groups for the provided region")
    ssh_keys = Nested("IBMSshKeyValidateJsonOutSchema", many=True, required=True,
                      description="List of all SSH Keys for the provided region")
    kubernetes_clusters = Nested("IBMKubernetesClusterValidateJsonOutSchema", many=True, required=True,
                                 description="List of all IKS for the provided region")
    draas_restore_clusters = Nested("DRaaSClusterValidateJsonOutSchema", many=True, required=True,
                                    description="List of all DRaaS IKS for the provided region")
    instance_profiles = Nested("IBMInstanceProfileValidateJsonOutSchema", many=True, required=True,
                               description="List of all Instance Profiles for the provided region")
    images = Nested("IBMImageValidateJsonOutSchema", many=True, required=True,
                    description="List of all Images for the provided region")
    operating_systems = Nested("IBMOperatingSystemValidateJsonOutSchema", many=True, required=True,
                               description="List of all Operating Systems for the provided region")
    cos_buckets = Nested("IBMCosBucketValidateJsonOutSchema", many=True, required=True,
                         description="List of all Cos Buckets for the provided region")
    volumes = Nested("IBMVolumeValidateJsonOutSchema", many=True, required=True,
                     description="List of all volumes for the provided region")
    tags = Nested("IBMTagValidateJsonOutSchema", many=True, required=True,
                  description="List of all tags for the provided region")
