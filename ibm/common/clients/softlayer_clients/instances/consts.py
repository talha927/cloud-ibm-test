VPC_MIGRATE = "Task for VPC migration initiated by user: email '{}'"
IBM_CLOUD = "IBM"
UNIT = "unit"
SIZE = "size"
BLOCK_DEVICE = "block_device"

# IBM consts
BALANCED_INSTANCE_PROFILE_NAME = "bx2-{cpu}x{memory}"
COMPUTE_INSTANCE_PROFILE_NAME = "cx2-{cpu}x{memory}"
MEMORY_INSTANCE_PROFILE_NAME = "mx2-{cpu}x{memory}"

BALANCED = "BALANCED"
COMPUTE = "COMPUTE"
MEMORY = "MEMORY"
VENDOR_DICTIONARY = {
    "Ubuntu": "Canonical",
    "CentOS": "CentOS",
    "Redhat": "RedHat",
    "Debian": "Debian",
    "Microsoft": "Microsoft",
}

# TODO scaleMember keyword for autoscaling.. for now I have removed as account issue
VIRTUAL_SERVER_MASK = (
    "mask[datacenter.longName, id, dedicatedHost[id, name], placementGroup[id, name], status, type, "
    "allowedNetworkStorage[storageType], operatingSystem[softwareLicense[softwareDescription[name, manufacturer, "
    "version, longDescription]]],fullyQualifiedDomainName, hostname, dedicatedAccountHostOnlyFlag, maxCpu, maxCpuUnits,"
    "maxMemory, networkComponents[name, networkVlan, primarySubnet, maxSpeed, speed, port, primaryIpAddress, "
    "securityGroupBindings[securityGroup[rules[remoteGroup[description]]]]], regionalGroup[name], "
    "sshKeys[fingerprint, key, label], firewallServiceComponent[rules, status],blockDevices[diskImage]]"
)

GET_INSTANCE_MASK = (
    'id,'
    'globalIdentifier,'
    'fullyQualifiedDomainName,'
    'hostname,'
    'domain,'
    'createDate,'
    'modifyDate,'
    'provisionDate,'
    'notes,'
    'dedicatedAccountHostOnlyFlag,'
    'transientGuestFlag,'
    'privateNetworkOnlyFlag,'
    'primaryBackendIpAddress,'
    'primaryIpAddress,'
    '''networkComponents[id, status, speed, maxSpeed, name,
                         macAddress, primaryIpAddress, port,
                         primarySubnet[addressSpace],
                         securityGroupBindings[
                            securityGroup[id, name]]],'''
    'lastKnownPowerState.name,'
    'powerState,'
    'status,'
    'maxCpu,'
    'maxMemory,'
    'datacenter,'
    'activeTransaction[id, transactionStatus[friendlyName,name]],'
    'lastTransaction[transactionStatus],'
    'lastOperatingSystemReload.id,'
    'blockDevices,'
    'blockDeviceTemplateGroup[id, name, globalIdentifier],'
    'postInstallScriptUri,'
    '''operatingSystem[passwords[username,password],
                       softwareLicense.softwareDescription[
                           manufacturer,name,version,
                           referenceCode]],'''
    '''softwareComponents[
        passwords[username,password,notes],
        softwareLicense[softwareDescription[
                            manufacturer,name,version,
                            referenceCode]]],'''
    'hourlyBillingFlag,'
    'userData,'
    '''billingItem[id,nextInvoiceTotalRecurringAmount,
                   package[id,keyName],
                   children[categoryCode,nextInvoiceTotalRecurringAmount],
                   orderItem[id,
                             order.userRecord[username],
                             preset.keyName]],'''
    'tagReferences[id,tag[name,id]],'
    'networkVlans[id,vlanNumber,networkSpace],'
    'dedicatedHost.id,'
    'placementGroup.id'
)

INSTANCE_ONLY_ID_NAME_MASK = "mask[hostname, id, status]"

VSI_ID_HOSTNAME_ONLY_MASK = "mask[id, hostname]"
DEDICATED_HOST_WO_INSTANCES_MASK = "mask[cpuCount, diskCapacity, id, memoryCapacity, name, datacenter, guests[id]]"
DEDICATED_HOST_W_INSTANCES_MASK = "mask[cpuCount, diskCapacity, id, memoryCapacity, name, datacenter, guests]"
