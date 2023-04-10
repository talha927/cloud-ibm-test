from apiflask import Schema
from apiflask.fields import Boolean, Integer, List, Nested, String
from apiflask.validators import Length, OneOf, Regexp

from ibm.common.req_resp_schemas.consts import IBM_KUBERNETES_RESOURCE_NAME_PATTERN, \
    IBM_UUID_PATTERN
from ibm.common.req_resp_schemas.fields import IPv4CIDR
from ibm.models import IBMKubernetesCluster, IBMResourceGroup, IBMSubnet, IBMVpcNetwork, IBMZone


class IBMKubernetesClusterWorkloadsOutSchema(Schema):
    class PVCOutSchema(Schema):
        name = String(required=True, allow_none=False, description="The name of the PVC in Kubernetes Cluster.")
        size = String(required=True, allow_none=False, description="The size for the PVC in Kubernetes Cluster.")
        phase = String(required=True, allow_none=False, description="The phase for the PVC in Kubernetes Cluster.")
        type = String(
            required=True, allow_none=False, description="The provisioner type for the PVC in Kubernetes Cluster."
        )
        namespace = String(
            required=False, allow_none=False, description="The namespace for the PVC in Kubernetes Cluster."
        )

    namespace = String(required=True, allow_none=False, description="The namespace in the Kubernetes Cluster.")
    pod = List(String(description="Pods in the Kubernetes Cluster."))
    pvc = List(Nested("PVCOutSchema"))
    svc = List(String(description="Services in the Kubernetes Cluster."))


class WorkerZonesOutSchema(Schema):
    id = String(required=True, validate=(Regexp(IBM_UUID_PATTERN), Length(equal=32)))
    name = String(description="Name of Zone", required=True)
    private_vlan = String(required=True)
    subnets = Nested("IBMSubnetRefOutSchema", many=True, required=True)


class IBMKubernetesClusterWorkerPoolOutSchema(Schema):
    id = String(required=True, validate=(Regexp(IBM_UUID_PATTERN), Length(equal=32)))
    name = String(required=True, allow_none=False, description="The name of the workerpool in kubernetes cluster.")
    status = String(required=True)
    disk_encryption = Boolean(required=True)
    flavor = String(description="Flavor of the WorkerPool", required=True)
    worker_count = Integer(required=True, allow_none=False, description="The worker count of workerpool in Cluster.")
    resource_id = String(required=True, allow_none=False, description="Unique ID on IBM Cloud")
    kubernetes_cluster = Nested("IBMKubernetesClusterRefOutSchema", required=True)
    worker_zones = Nested("WorkerZonesOutSchema", many=True, required=True)


class IngressSchema(Schema):
    hostname = String(description="Hostname for cluster")
    message = String(description="Message about ingress for cluster")
    secret_name = String(description="Private ingress dns for cluster")
    status = String(description="status of ingress service for cluster")


class IBMKubernetesClusterOutSchema(Schema):
    class ServiceEndpointsOutSchema(Schema):
        private_service_endpoint_enabled = Boolean(description="Whether or not private endpoint is enabled")
        private_service_endpoint_url = String(description="URL of the private endpoint")
        public_service_endpoint_enabled = Boolean(description="Whether or not public endpoint is enabled")
        public_service_endpoint_url = String(description="URL of the public endpoint")

    id = String(required=True, validate=(Regexp(IBM_UUID_PATTERN), Length(equal=32)))
    name = \
        String(
            required=True, allow_none=False,
            validate=(Regexp(IBM_KUBERNETES_RESOURCE_NAME_PATTERN), Length(min=1, max=32)),
            description="The name of the Kubernetes Cluster"
        )
    pod_subnet = IPv4CIDR(required=True, description="The CIDR block for the subnet of this pod")
    master_kube_version = \
        String(
            required=True, allow_none=False,
            description="Kube version of Cluster."
        )
    disable_public_service_endpoint = Boolean(required=True)
    status = \
        String(
            required=True, allow_none=False, validate=(OneOf(IBMKubernetesCluster.STATES_LIST)),
            description="Status of the kubernetes cluster on IBM."
        )
    provider = \
        String(required=True, allow_none=False, description="Infrastructure for kubernetes cluster.")
    cluster_type = \
        String(
            required=True, allow_none=False, validate=(OneOf(IBMKubernetesCluster.ALL_CLUSTER_TYPES_LIST)),
            description="Type of cluster on IBM."
        )
    resource_id = String(required=True, allow_none=False, description="Unique ID on IBM Cloud")
    workloads = Nested("IBMKubernetesClusterWorkloadsOutSchema", many=True)
    ingress = Nested("IngressSchema")
    service_endpoint = Nested("ServiceEndpointsOutSchema")
    ibm_cloud = Nested("IBMCloudRefOutSchema", required=True)
    resource_group = Nested("IBMResourceGroupRefOutSchema", required=True)
    region = Nested("IBMRegionRefOutSchema", required=True, description="The region for the Kubernetes Cluster.")
    # TODO: revisit after worker pools schema
    worker_pools = Nested("IBMKubernetesClusterWorkerPoolOutSchema", required=True, many=True)
    associated_resources = Nested("IBMClustersAssociatedResourcesOutSchema", required=True)


class IBMClustersAssociatedResourcesOutSchema(Schema):
    vpc = Nested("IBMVpcNetworkRefOutSchema", required=True)


class IBMKubernetesClusterRefOutSchema(IBMKubernetesClusterOutSchema):
    class Meta:
        fields = ("id", "name", "cluster_type", "master_kube_version")


class IBMKubernetesClusterValidateJsonResourceSchema(Schema):
    class Meta:
        fields = ("name", "cluster_type", "master_kube_version")


class IBMKubernetesClusterValidateJsonOutSchema(Schema):
    id = String(
        required=True, allow_none=False, validate=[Length(equal=32), Regexp(IBM_UUID_PATTERN)],
        description="Unique ID of the IBM IKS"
    )
    resource_json = Nested(IBMKubernetesClusterValidateJsonResourceSchema, required=True)


class IBMKubernetesClustersListOutSchema(IBMKubernetesClusterOutSchema):
    class Meta:
        exclude = ('workloads',)


class IBMKubernetesClusterWorkerPoolZoneInSchema(Schema):
    REF_KEY_TO_RESOURCE_TYPE_MAPPER = {
        "zones": IBMZone,
        "subnets": IBMSubnet
    }
    id = String(required=False, validate=(Regexp(IBM_UUID_PATTERN), Length(equal=32)))
    zones = Nested("OptionalIDNameSchemaWithoutValidation", required=True,
                   description="The zone where worker pool resides")
    # TODO: Is is this a list of subnets?
    subnets = Nested("OptionalIDNameSchemaWithoutValidation", required=True,
                     description="The subnet where worker pool resides")


class IBMKubernetesClusterWorkerPoolInSchema(Schema):
    name = String(
        required=True, allow_none=False,
        validate=(Length(min=1, max=32), Regexp(IBM_KUBERNETES_RESOURCE_NAME_PATTERN)),
        description="User defined unique name of the worker pool"
    )
    disk_encryption = Boolean(required=True)
    flavor = String(required=True, description="Worker nodes flavor of IBM Kubernetes Cluster")
    worker_count = Integer(required=True, description="The total number of worker nodes in the worker pool")
    worker_zones = List(Nested("IBMKubernetesClusterWorkerPoolZoneInSchema", required=True))


class PVCSchema(Schema):
    name = String(required=False, description="Name for PVC")
    size = String(required=False, description="Size for PVC")
    phase = String(required=False, description="Phase for PVC")
    type = String(required=False, description="Type for PVC")


class IBMKubernetesClusterWorkloadsInSchema(Schema):
    namespace = String(required=False, description="Namespaces for cluster")
    pod = List(String(required=False, description="Pod for cluster"))
    svc = List(String(required=False, description="SVCs for cluster"))
    pvc = Nested("PVCSchema", many=True, required=False, description="PVC for cluster")


class IBMKubernetesClusterResourceSchema(Schema):
    REF_KEY_TO_RESOURCE_TYPE_MAPPER = {
        "vpc": IBMVpcNetwork,
        "resource_group": IBMResourceGroup
    }

    disable_public_service_endpoint = Boolean(required=True)
    classic_cluster_name = String(description="Name of classic cluster. Required for Migration only.")
    classic_cluster_ingress_hostname = String(
        description="Ingress Hostname of classic cluster. Required for Migration only.")

    ingress = Nested("IngressSchema", required=False,
                     description="Cluster's Ingress Details. Required for Migration only.")

    name = String(
        required=True, allow_none=False,
        validate=(Length(min=1, max=32), Regexp(IBM_KUBERNETES_RESOURCE_NAME_PATTERN)),
        description="User defined unique name of the cluster"
    )
    pod_subnet = IPv4CIDR(
        allow_none=False, example="172.17.0.0/18", type='CIDR', description="IPv4 CIDR block of pod subnet")
    service_subnet = IPv4CIDR(
        allow_none=False, example="172.21.0.0/16", type='CIDR', description="IPv4 CIDR block of service subnet")
    master_kube_version = String(
        required=True, allow_none=False, description="Version of Cluster."
    )
    provider = String(
        allow_none=False,
        validate=(Length(min=1, max=32)), description="IBM infrastructure for the cluster to be provisioned"
    )
    cluster_type = String(
        required=True, allow_none=False,
        validate=(OneOf(IBMKubernetesCluster.ALL_CLUSTER_TYPES_LIST)),
        description="Orchestration type of IBM kubernetes cluster."
    )
    resource_id = String(
        allow_none=False, description="Classic Kubernetes cluster ID on IBM cloud. Required for Migration only."
    )
    vpc = Nested("OptionalIDNameSchemaWithoutValidation", required=True,
                 description="The VPC the cluster is to be a part of")
    resource_group = Nested("OptionalIDNameSchemaWithoutValidation", required=True,
                            description="The resource group to use.")

    worker_pools = List(Nested("IBMKubernetesClusterWorkerPoolInSchema", required=True))
    # add description for migration
    workloads = List(Nested("IBMKubernetesClusterWorkloadsInSchema", required=False))


class IBMKubernetesClusterInSchema(Schema):
    REF_KEY_TO_RESOURCE_TYPE_MAPPER = {}

    ibm_cloud = Nested("OptionalIDNameSchemaWithoutValidation", required=True)
    region = Nested("OptionalIDNameSchemaWithoutValidation", required=True)
    cos_bucket_id = String(
        allow_none=False, validate=(Regexp(IBM_UUID_PATTERN), Length(equal=32)),
        description="ID of the IBM COS Bucket."
    )
    cloud_object_storage_id = String(
        allow_none=False, validate=(Regexp(IBM_UUID_PATTERN), Length(equal=32)),
        description="ID of the IBM COS."
    )
    cos_access_keys_id = String(
        allow_none=False, validate=(Regexp(IBM_UUID_PATTERN), Length(equal=32)),
        description="ID of the IBM COS Access Keys."
    )
    managed_view = Boolean(required=True)
    resource_json = Nested("IBMKubernetesClusterResourceSchema", required=True)


class IBMMultiZoneDiscoverySchema(Schema):
    REF_KEY_TO_RESOURCE_TYPE_MAPPER = {}

    softlayer_cloud = Nested("OptionalIDNameSchemaWithoutValidation", required=True)
    ibm_cloud = Nested("OptionalIDNameSchemaWithoutValidation", required=True)


class IBMZonesList(Schema):
    ibm_cloud = Nested("OptionalIDNameSchemaWithoutValidation", required=True)
    zones = List(String(
        allow_none=False, validate=(Regexp(IBM_UUID_PATTERN), Length(equal=32)),
        description="IDs of the IBM Zones."
    ))
