import os

from config import IAMConfig
from config import TranslationConfig

AUTH_LINK = f"{IAMConfig.AUTH_LINK}v1/users/verify"
SUBSCRIPTION_APP_HOST = os.environ.get('SUBSCRIPTION_APP_HOST', 'http://subscription-svc:8000')
SUBSCRIPTION_LINK = f"{SUBSCRIPTION_APP_HOST}/v1/subscriptions?status=ACTIVE&project_id="
SUBSCRIPTION_STATUS_PAYLOAD = {
    "code": "403",
    "message": "Your tenant does not have any service instance on IBM cloud",
    "message_type": "NO_SUBSCRIPTION"
}
INVALID_REQUEST_METHOD = {
    "code": "400",
    "message": "Request methods other than POST, DELETE and PATCH not implemented.",
    "message_type": "UNKNOWN_REQUEST_TYPE"
}

# TASK Status
PENDING = "PENDING"
IN_PROGRESS = "IN_PROGRESS"
SUCCESS = "SUCCESS"
FAILED = "FAILED"
CANCELLED = "CANCELLED"
BACKGROUND = "BACKGROUND"
COMPLETED = "COMPLETED"

# Cloud Constant
AWS_CLOUD = "AWS"
IBM_CLOUD = "IBM"

# ACTIONS
# TASK Status
ADD = "ADD"
CREATE = "CREATE"
DELETE = "DELETE"
UPDATE = "UPDATE"

CREATED = "CREATED"
VALID = "VALID"

# On_Prem Cluster
ONPREM = "ONPREM"
CERTS = "CERTS"

# VPC, Firewall, Instance status
CREATING = "CREATING"
UPDATING = "UPDATING"
UPDATED = "UPDATED"
DELETING = "DELETING"
DELETED = "DELETED"
ERROR_CREATING = "ERROR_CREATING"
ERROR_DELETING = "ERROR_DELETING"
ERROR_UPDATING = "ERROR_UPDATING"
CREATION_PENDING = "CREATION_PENDING"
UPDATION_PENDING = "UPDATION_PENDING"

HOST_COUNT_TO_CIDR_BLOCK_MAPPER = {
    "8": "/29",
    "16": "/28",
    "32": "/27",
    "64": "/26",
    "128": "/25",
    "256": "/24",
    "512": "/23",
    "1024": "/22",
    "2048": "/21",
    "4096": "/20",
}

# Dictionary of Classical Image to Vpc Image
NOT_SUPPORTED_OS = "NOT_SUPPORTED_OS"  # means this OS is not supported in VPC Gen2
classical_vpc_image_dictionary = {
    # operatingSystem[softwareDescription[longDescription]]
    "Ubuntu 20.04-64 Minimal for VSI": ["ibm-ubuntu-20"],
    "Ubuntu 18.04-64 Minimal for VSI": ["ibm-ubuntu-18-"],
    "Ubuntu 18.04-64 LAMP for VSI": ["ibm-ubuntu-18-"],
    "Ubuntu 16.04-64 Minimal for VSI": [NOT_SUPPORTED_OS],
    "Ubuntu 16.04-64 LAMP for VSI": [NOT_SUPPORTED_OS],

    'CentOS 8.0-64 Minimal for VSI': [NOT_SUPPORTED_OS],
    'CentOS 7.0-64 Minimal for VSI': ["ibm-centos-7-"],
    "CentOS 7.0-64 LAMP for VSI": ["ibm-centos-7-"],
    "CentOS 6.0-64 Minimal for VSI": [NOT_SUPPORTED_OS],
    "CentOS 6.0-64 LAMP for VSI": [NOT_SUPPORTED_OS],

    "Redhat EL 8.0-64 Minimal for VSI": ["ibm-redhat-8-"],

    "Redhat EL 7.0-64 Minimal for VSI": ["ibm-redhat-7-"],
    "Redhat EL 7.0-64 LAMP for VSI": ["ibm-redhat-7-"],
    "Redhat EL 6.0-64 Minimal for VSI": [NOT_SUPPORTED_OS],
    "Redhat EL 6.0-64 LAMP for VSI": [NOT_SUPPORTED_OS],

    "Microsoft Windows 2022 FULL STD 64 bit 2022 FULL STD x64": ["ibm-windows-server-2022-full-standard-amd64"],
    "Microsoft Windows 2019 FULL STD 64 bit 2019 FULL STD x64": ["ibm-windows-server-2019-full-standard-amd64"],
    "Microsoft Windows 2016 FULL STD 64 bit 2016 FULL STD x64": ["ibm-windows-server-2016-full-standard-amd64"],
    "Microsoft Windows 2012 FULL STD 64 bit 2012 FULL STD x64": ["ibm-windows-server-2012-full-standard-amd64"],
    "Microsoft Windows 2012 R2 FULL STD 64 bit 2012 R2 FULL STD x64": [
        "ibm-windows-server-2012-r2-full-standard-amd64"
    ],

    "Debian 10.0.0-64 Minimal for VSI": ["ibm-debian-10-"],
    "Debian 9.0.0-64 Minimal for VSI": ["ibm-debian-9-"],
    "Debian 9.0.0-64 LAMP for VSI": ["ibm-debian-9-"],
    "Debian 8.0.0-64 Minimal for VSI": [NOT_SUPPORTED_OS],
    "Debian 8.0.0-64 LAMP for VSI": [NOT_SUPPORTED_OS],
    "Debian 7.0.0-64 Minimal for VSI": [NOT_SUPPORTED_OS],
}

PRIVATE_KEY_NAME = "{}-{}"

# Bucket geography
# TODO: Replace these mappers with dynamic flow using APIs.
BUCKET_CROSS_REGION_TO_REGIONS_MAPPER = {
    "ap": ["jp-osa", "au-syd", "jp-tok"],
    "eu": ["eu-de", "eu-gb"],
    "us": ["us-south", "br-sao", "ca-tor", "us-east"]
}

BUCKET_DATA_CENTER_TO_REGION_MAPPER = {
    "ams03": "eu-de",
    "che01": "jp-tok",
    "hkg02": "jp-tok",
    "mex01": "us-south",
    "mil01": "eu-de",
    "mon01": "us-east",
    "par01": "eu-de",
    "sjc04": "us-south",
    "seo01": "jp-tok",
    "sng01": "jp-tok"
}

# qcow2 format string
QCOW2 = "qcow2"
COS_FILE_EXTENSIONS = ["vhd", "vmdk", "qcow2"]

CREATED_AT_FORMAT = '%Y-%m-%dT%H:%M:%SZ'
CREATED_AT_FORMAT_WITH_MILLI_SECONDS = '%Y-%m-%dT%H:%M:%S.%fZ'
BILLING_MONTH_FORMAT = '%Y-%m'
CLOUD_LESS_RESOURCE_LIST = ["IBMLoadBalancerProfile"]
IBM_NAME_KEY_VALUE_LIST = ["zone", "region", "profile", "operating_system", "dedicated_host_profile"]

OPENSHIFT_OS = "RHEL"
IBM_COS_BUCKET_HREF = "cos://{region}/{bucket}/{object}"

BLOCK_STORAGE_TYPE = "ibm.io/ibmc-block"
DUMMY_PROFILE_ID = "dummy-profile-id"
DUMMY_PROFILE_NAME = "dummy-profile-name"
DUMMY_COS_ID = "dummy-cos-id"
DUMMY_COS_NAME = "dummy-cos-name"
DUMMY_COS_BUCKET_ID = "dummy-cos_bucket-id"
DUMMY_COS_BUCKET_NAME = "dummy-cos_bucket-name"
DUMMY_ACCESS_KEY_ID = "dummy-access-key-id"
DUMMY_CLOUD_NAME = "dummy-cloud-name"
DUMMY_CLOUD_ID = "dummy-cloud-id"
DUMMY_REGION_NAME = "dummy-region-name"
DUMMY_REGION_ID = "dummy-region-id"
DUMMY_ZONE_NAME = "dummy-zone-name"
DUMMY_ZONE_ID = "dummy-zone-id"
DUMMY_RESOURCE_GROUP_NAME = "dummy-resource-group-name"
DUMMY_RESOURCE_GROUP_ID = "dummy-resource-group-id"
DUMMY_BACKUP_ID = "dummy-backup-id"

# url path for AWS translation
AWS_TRANSLATION_URL_TEMPLATE = "v1/aws/clouds/{cloud_id}/{resource_type}s/{resource_id}/construct"

# url path for AWS Cloud Credentials
GET_AWS_CLOUD_CREDENTIAL_URL_TEMPLATE = "v1/aws/users/{user_id}/clouds/{cloud_id}/credentials"

# url path for AWS Backup
GET_AWS_BACKUP_URL_TEMPLATE = "v1/aws/users/{user_id}/clouds/{cloud_id}/draas-backups/{backup_id}"

# request headers for AWS, GCP
AWS_HEADER = {'X-Api-Key': TranslationConfig.AWS_ENV_X_API_KEY}

MONTHS_STR_TO_INT = {
    "january": 1,
    "february": 2,
    "march": 3,
    "april": 4,
    "may": 5,
    "june": 6,
    "july": 7,
    "august": 8,
    "september": 9,
    "october": 10,
    "november": 11,
    "december": 12
}

INT_MONTH_TO_STR = {
    1: "january",
    2: "february",
    3: "march",
    4: "april",
    5: "may",
    6: "june",
    7: "july",
    8: "august",
    9: "september",
    10: "october",
    11: "november",
    12: "december"
}
