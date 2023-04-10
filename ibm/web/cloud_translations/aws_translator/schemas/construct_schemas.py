from marshmallow import EXCLUDE, Schema
from marshmallow.fields import Nested


class AWSVpcConstructSchema(Schema):
    vpcs = Nested("AWSVpcSchema", required=True, many=True, unknown=EXCLUDE)
    subnets = Nested("AWSSubnetSchema", required=False, many=True, unknown=EXCLUDE)
    security_groups = Nested("AWSSecurityGroupSchema", required=False, many=True, unknown=EXCLUDE)
    acls = Nested("AWSAclSchema", required=False, many=True, unknown=EXCLUDE)
    elastic_ips = Nested("AWSElasticIpSchema", required=False, many=True, unknown=EXCLUDE)
    nat_gateways = Nested("AWSNatGatewaySchema", required=False, many=True, unknown=EXCLUDE)
    route_tables = Nested("AWSRouteTableSchema", required=False, many=True, unknown=EXCLUDE)
    network_interfaces = Nested("AWSNetworkInterfaceSchema", required=False, many=True, unknown=EXCLUDE)
    instances = Nested("AWSInstanceSchema", required=False, many=True, unknown=EXCLUDE)
    eks_clusters = Nested("AWSEksClusterSchema", required=False, many=True, unknown=EXCLUDE)
    internet_gateways = Nested("AWSInternetGatewaySchema", required=False, many=True, unknown=EXCLUDE)
    volumes = Nested("AWSVolumeSchema", required=False, many=True, unknown=EXCLUDE)
    load_balancers = Nested("AWSLoadBalancerSchema", required=False, many=True, unknown=EXCLUDE)
    listeners = Nested("AWSListenerSchema", required=False, many=True, unknown=EXCLUDE)
    target_groups = Nested("AWSTargetGroupSchema", required=False, many=True, unknown=EXCLUDE)
    virtual_private_gateways = Nested("AWSVirtualPrivateGatewaySchema", required=False, many=True, unknown=EXCLUDE)
    vpn_connections = Nested("AWSVPNConnectionSchema", required=False, many=True, unknown=EXCLUDE)

    class Meta:
        unknown = EXCLUDE
