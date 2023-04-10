DATE_TIME_FORMAT = "%Y-%m-%d %H:%M:%S"
IBM_HREF_PATTERN = r"/^http(s)?:\/\/([^\/?#]*)([^?#]*)(\\?([^#]*))?(#(.*))?$/"
IBM_RESOURCE_NAME_PATTERN = "^([a-z]|[a-z][-a-z0-9]*[a-z0-9])$"
IBM_POOL_SESSION_PERSISTENCE_COOKIE_NAME_PATTERN = "^[-A-Za-z0-9!#$%&'*+.^_`~|]+$"
IBM_UUID_PATTERN = "^[0-9a-f]{32}$"
IBM_ZONE_NAME_PATTERN = "^([a-z]|[a-z][-a-z0-9]*[a-z0-9]|[0-9][-a-z0-9]*([a-z]|[-a-z][-a-z0-9]*[a-z0-9]))$"
IBM_URL_PATH_PATTERN = r"^\/(([a-zA-Z0-9-._~!$&'()*+,;=:@]|%[a-fA-F0-9]{2})+(\/([a-zA-Z0-9-._~!$&'()*+," \
                       r";=:@]|%[a-fA-F0-9]{2})*)*)?(\?([a-zA-Z0-9-._~!$&'()*+,;=:@\/?]|%[a-fA-F0-9]{2})*)?$"
IBM_NESTED_ID_STRING_PATTERN = r'^({"id":)\s?"[0-9a-f]{32}("})$'
IBM_KUBERNETES_RESOURCE_NAME_PATTERN = r"^[a-z0-9]([-a-z0-9]*[a-z0-9])?(\.[a-z0-9]([-a-z0-9]*[a-z0-9])?)*"
IBM_SATELLITE_RESOURCE_NAME_PATTERN = r"^[a-z0-9]([-a-z0-9]*[a-z0-9])?(\.[a-z0-9]([-a-z0-9]*[a-z0-9])?)*"
COS_IMAGE_PATTERN = r"^cos:\/\/([^\/?#]*)([^?#]*)$"
CRON_SPEC_PATTERN = r"^((((\d+,)+\d+|([\d\*]+(\/|-)\d+)|\d+|\*) ?){5,7})$"
