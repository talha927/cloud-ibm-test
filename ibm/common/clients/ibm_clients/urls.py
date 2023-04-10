from .consts import GLOBAL_CATALOG_VERSION, GLOBAL_SEARCH_VERSION, GLOBAL_TAG_VERSION, PRIVATE_CATALOG_VERSION, \
    RESOURCE_CONTROLLER_VERSION, RESOURCE_MANAGER_MAJOR_VERSION, TRANSIT_GATEWAY_VERSION, VPC_MAJOR_VERSION

AUTH_URL = "https://iam.cloud.ibm.com/identity/token"

IAM_URL = "https://iam.cloud.ibm.com"

VPC_BASE_URL = "https://{region}.iaas.cloud.ibm.com"
VPC_URL_TEMPLATE = ''.join([VPC_BASE_URL, "/", VPC_MAJOR_VERSION, "/", "{path}"])
ACCOUNT_DETAILS_URL_TEMPLATE = ''.join([IAM_URL, "/", VPC_MAJOR_VERSION, "/", "{path}"])

VPC_SERVICE_URL = ''.join([VPC_BASE_URL, "/", VPC_MAJOR_VERSION])

RESOURCE_BASE_URL = "https://resource-controller.cloud.ibm.com"
RESOURCE_MANAGER_SERVICE_URL = ''.join([RESOURCE_BASE_URL, "/", RESOURCE_MANAGER_MAJOR_VERSION])
RESOURCE_CONTROLLER_SERVICE_URL = ''.join([RESOURCE_BASE_URL, "/", RESOURCE_CONTROLLER_VERSION])

GLOBAL_CATALOG_BASE_URL = "https://globalcatalog.cloud.ibm.com/api"
GLOBAL_CATALOG_SERVICE_URL = ''.join([GLOBAL_CATALOG_BASE_URL, "/", GLOBAL_CATALOG_VERSION])

BUCKETS_BASE_URL = "https://s3.{region}.cloud-object-storage.appdomain.cloud"
BUCKETS_URL_TEMPLATE = "".join([BUCKETS_BASE_URL, "/", "{path}"])

GLOBAL_SEARCH_BASE_URL = "https://api.global-search-tagging.cloud.ibm.com"
GLOBAL_SEARCH_URL_TEMPLATE = ''.join(
    [GLOBAL_SEARCH_BASE_URL, "/", GLOBAL_SEARCH_VERSION, "/", "resources", "/", "{path}"])

PRIVATE_CATALOG_BASE_URL = "https://cm.globalcatalog.cloud.ibm.com"
PRIVATE_CATALOG_URL_TEMPLATE = ''.join(
    [PRIVATE_CATALOG_BASE_URL, "/", "api", "/", PRIVATE_CATALOG_VERSION, "/", "{path}"])

TRANSIT_GATEWAY_BASE_URL = "https://transit.cloud.ibm.com"
TRANSIT_GATEWAY_URL_TEMPLATE = ''.join([TRANSIT_GATEWAY_BASE_URL, TRANSIT_GATEWAY_VERSION])

GLOBAL_TAG_BASE_URL = "https://tags.global-search-tagging.cloud.ibm.com"
GLOBAL_TAG_URL_TEMPLATE = ''.join([GLOBAL_TAG_BASE_URL, "/", GLOBAL_TAG_VERSION, "/", "{path}"])
GLOBAL_TAG_SERVICE_URL = ''.join([GLOBAL_TAG_BASE_URL, "/", GLOBAL_TAG_VERSION])
