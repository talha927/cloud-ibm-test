LOAD_BALANCER_MASK = (
    "mask[healthMonitors, l7Pools, listeners[defaultPool[healthMonitor, members, sessionAffinity]], "
    "members, sslCiphers, datacenter]"
)
