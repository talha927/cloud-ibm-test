from ibm.models import IBMFloatingIP, IBMInstance, IBMSecurityGroup, IBMSnapshot, IBMSshKey, IBMSubnet, IBMVpcNetwork

IBM_TAG_TO_RESOURCE_MAPPER = {
    "vpc": IBMVpcNetwork,
    "instance": IBMInstance,
    "key": IBMSshKey,
    "floating-ip": IBMFloatingIP,
    "subnet": IBMSubnet,
    "snapshot": IBMSnapshot,
    "security-group": IBMSecurityGroup
}
