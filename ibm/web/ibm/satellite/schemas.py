from apiflask import Schema
from apiflask.fields import Boolean, List, Nested, String
from apiflask.validators import Length, OneOf, Regexp

from ibm.common.req_resp_schemas.consts import IBM_SATELLITE_RESOURCE_NAME_PATTERN, \
    IBM_UUID_PATTERN
from ibm.common.req_resp_schemas.fields import IPv4CIDR
from ibm.models import IBMSatelliteCluster


class IBMSatelliteClusterWorkloadsOutSchema(Schema):
    class SatellitePVCOutSchema(Schema):
        name = String(required=True, allow_none=False, description="The name of the PVC in Satellite Cluster.")
        size = String(required=True, allow_none=False, description="The size for the PVC in Satellite Cluster.")

    namespace = String(required=True, allow_none=False, description="The namespace in the Satellite Cluster.")
    pod = List(String(description="Pods in the Satellite Cluster."))
    pvc = List(Nested("SatellitePVCOutSchema"))
    svc = List(String(description="Services in the Satellite Cluster."))


class SatelliteIngressSchema(Schema):
    hostname = String(description="Hostname for cluster")
    message = String(description="Message about ingress for cluster")
    secret_name = String(description="Private ingress dns for cluster")
    status = String(description="status of ingress service for cluster")


class IBMSatelliteClusterOutSchema(Schema):
    class SatelliteServiceEndpointsOutSchema(Schema):
        private_service_endpoint_enabled = Boolean(description="Whether or not private endpoint is enabled")
        private_service_endpoint_url = String(description="URL of the private endpoint")
        public_service_endpoint_enabled = Boolean(description="Whether or not public endpoint is enabled")
        public_service_endpoint_url = String(description="URL of the public endpoint")

    id = String(required=True, validate=(Regexp(IBM_UUID_PATTERN), Length(equal=32)))
    name = \
        String(
            required=True, allow_none=False,
            validate=(Regexp(IBM_SATELLITE_RESOURCE_NAME_PATTERN), Length(min=1, max=32)),
            description="The name of the Satellite Cluster"
        )
    pod_subnet = IPv4CIDR(required=True, description="The CIDR block for the subnet of this pod")
    master_kube_version = \
        String(
            required=True, allow_none=False,
            description="Kube version of Cluster."
        )
    state = \
        String(
            required=True, allow_none=False, validate=(Length(min=1, max=32)),
            description="State of the Satellite cluster on IBM."
        )
    provider = \
        String(required=True, allow_none=False, description="Provider for Satellite cluster.")
    cluster_type = \
        String(
            required=True, allow_none=False, validate=(OneOf(IBMSatelliteCluster.ALL_CLUSTER_TYPES_LIST)),
            description="Type of cluster on IBM."
        )
    resource_id = String(required=True, allow_none=False, description="Unique ID on IBM Cloud")
    workloads = Nested("IBMSatelliteClusterWorkloadsOutSchema", many=True)
    ingress = Nested("SatelliteIngressSchema")
    service_endpoint = Nested("SatelliteServiceEndpointsOutSchema")
    ibm_cloud = Nested("IBMCloudRefOutSchema", required=True)
    resource_group = Nested("IBMResourceGroupRefOutSchema", required=True)


class IBMSatelliteClustersListOutSchema(IBMSatelliteClusterOutSchema):
    class Meta:
        exclude = ('workloads',)
