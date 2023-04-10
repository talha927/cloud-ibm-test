SYNC_QUEUE = "sync_queue"

# cos query param
COS_SERVICE_QUERY_PARAM = "kind:iaas cloud-object-storage"
LANGUAGE = "en-us"

# global-search-tagging request_body for vpe targets
REQUEST_BODY_VPE_GLOBAL_SEARCH = {
    "query": "doc.extensions.virtual_private_endpoints.endpoints.ip_address:*",
    "fields": [
        "name",
        "region",
        "family",
        "type",
        "crn",
        "tags",
        "organization_guid",
        "doc.extensions",
        "doc.resource_group_id",
        "doc.space_guid",
        "resource_id",
        "service_name"
    ]
}
# private-catalog query for vpe targets
VPE_TARGETS_QUERY_PARAM = "kind: vpe AND svc"
LOCATION_GLOBAL = "global"
