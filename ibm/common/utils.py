import base64
import hashlib
import ibm_boto3
import re
import uuid

from copy import deepcopy
from datetime import datetime, timezone
from random import randrange, randint
from Crypto.Cipher import AES
from Crypto.Random import get_random_bytes
from dateutil.relativedelta import relativedelta
from ibm_botocore.client import Config
from ipcalc import Network

from config import ConsumptionClientConfig, SubscriptionClientConfig
from ibm import LOGGER
from ibm.common.consts import CLOUD_LESS_RESOURCE_LIST, CREATED_AT_FORMAT, CREATED_AT_FORMAT_WITH_MILLI_SECONDS, \
    IBM_NAME_KEY_VALUE_LIST, MONTHS_STR_TO_INT


def get_name_from_url(url):
    return url.split("/")[5]


def is_valid_uuid(val):
    # TODO: Remove this function.
    try:
        uuid.UUID(str(val))
        LOGGER.debug(f"'{val}' is not a valid UUID. Please check it out.")
        return True
    except ValueError:
        return False


def get_resource_by_name_or_id(cloud_id, resource_type, db_session, name_id_dict, previous_resources=None,
                               region_id=None):
    if not previous_resources:
        previous_resources = dict()

    message = None
    query_param_dict = {**name_id_dict}
    if resource_type.__name__ not in CLOUD_LESS_RESOURCE_LIST:
        query_param_dict["cloud_id"] = cloud_id

    if hasattr(resource_type, 'region_id') and region_id:
        query_param_dict["region_id"] = region_id
    resource = previous_resources.get(query_param_dict.get("id")) or db_session.query(resource_type).filter_by(
        **query_param_dict).first()
    if not resource:
        if "id" in name_id_dict and "name" in name_id_dict:
            message = f"{resource_type.__name__} with ID: '{name_id_dict['id']}' and" \
                      f" NAME: '{name_id_dict['name']}' not found. Please make sure ID and NAME are correct."
            return resource, message
        elif "id" in name_id_dict and "name" not in name_id_dict:
            message = f"{resource_type.__name__} with ID: {name_id_dict['id']} not found."
            return resource, message

        elif "name" in name_id_dict and "id" not in name_id_dict:
            message = f"{resource_type.__name__} with NAME: {name_id_dict['name']} not found."
            return resource, message

    return resource, message


def verify_and_yield_references(cloud_id, resource_schema, data, db_session, previous_resources=None, region_id=None):
    if not previous_resources:
        previous_resources = dict()

    for key in resource_schema.REF_KEY_TO_RESOURCE_TYPE_MAPPER:
        if key not in data:
            continue

        assert isinstance(data[key], (dict, list))

        if isinstance(data[key], dict):
            resource, message = \
                get_resource_by_name_or_id(
                    cloud_id=cloud_id, resource_type=resource_schema.REF_KEY_TO_RESOURCE_TYPE_MAPPER[key],
                    db_session=db_session, name_id_dict=data[key], previous_resources=previous_resources,
                    region_id=region_id
                )
            yield key, data[key].get("id"), resource, message
        else:
            for name_id_dict in data[key]:
                assert isinstance(name_id_dict, dict)
                resource, message = get_resource_by_name_or_id(
                    cloud_id=cloud_id, resource_type=resource_schema.REF_KEY_TO_RESOURCE_TYPE_MAPPER[key],
                    db_session=db_session, name_id_dict=name_id_dict, previous_resources=previous_resources,
                    region_id=region_id
                )
                yield key, name_id_dict.get("id"), resource, message


def update_id_or_name_references(cloud_id, resource_json, resource_schema, db_session, previous_resources=None,
                                 region_id=None):
    """
    This is a function in Python that updates either the id or name references of a resource in a JSON object based on
     the resource's schema and existing information in a database.

    cloud_id: The identifier of the cloud to which the resource belongs.
    resource_json: A JSON object representing the resource to be updated.
    resource_schema: The schema of the resource, which defines its structure and allowed values.
    db_session: A database session object used to retrieve existing resources.
    previous_resources: An optional dictionary of previously retrieved resources, to avoid making redundant
    database queries.
    The function uses a generator to check the references in the JSON object against the existing resources in the
    database. If the generator returns a message, a ValueError is raised with the message.
    If the generator returns a key, resource, and message, the function updates the relevant reference in the JSON
    object. If the reference is a dictionary, the function updates either the id or name field depending on the
    value of key in the IBM_NAME_KEY_VALUE_LIST. If the reference is a list, the function iterates over the list to
    find a matching resource and updates the relevant field in the same way as for a dictionary.
    """
    if not previous_resources:
        previous_resources = dict()

    generator = \
        verify_and_yield_references(
            cloud_id=cloud_id, resource_schema=resource_schema, data=resource_json, db_session=db_session,
            previous_resources=previous_resources, region_id=region_id
        )
    if not generator:
        return

    for key, id_, resource, message in generator:
        if message:
            raise ValueError(message)
        if isinstance(resource_json[key], dict):
            if key in IBM_NAME_KEY_VALUE_LIST:
                resource_json[key]["name"] = resource.name
                resource_json[key].pop("id", None)
            else:
                resource_json[key]["id"] = resource.resource_id
                resource_json[key].pop("name", None)
        elif isinstance(resource_json[key], list):
            for ref_index, ref_resource in enumerate(resource_json[key]):
                if key in IBM_NAME_KEY_VALUE_LIST:
                    # TODO this may create problems when there are a list of resources with names' references
                    if ref_resource.get("name") == resource.name or ref_resource.get("id") == resource.id:
                        resource_json[key][ref_index]["name"] = resource.name
                        resource_json[key][ref_index].pop("id", None)
                else:
                    if resource_json[key][ref_index]["id"] == id_:
                        resource_json[key][ref_index]["id"] = resource.resource_id
                        resource_json[key][ref_index].pop("name", None)


def return_datetime_object(datetime_value):
    from datetime import datetime
    try:
        return datetime.strptime(datetime_value, CREATED_AT_FORMAT)
    except ValueError:
        try:
            return datetime.strptime(datetime_value, CREATED_AT_FORMAT_WITH_MILLI_SECONDS)
        except ValueError:
            if datetime_value[-1] == 'Z':
                return datetime.strptime(
                    datetime_value[0:23] + datetime_value[27:], CREATED_AT_FORMAT_WITH_MILLI_SECONDS)


def camel_to_snake_case(camel_case_string: str):
    """
    Converts camel case strings to snake case. E.g camelCaseString will be converted to camel_case_string
    @param camel_case_string: <string> A camel case string e.g aCamelCaseString
    @return:
    """
    shorthands_replacement_dict = {
        "_u_r_l": "_url"
    }

    output_string = re.sub("([A-Z])", "_\\1", camel_case_string).lower().lstrip("_")
    for shorthand in shorthands_replacement_dict:
        output_string = output_string.replace(shorthand, shorthands_replacement_dict[shorthand], -1)
    return output_string


def dict_keys_camel_to_snake_case(dict_with_camel_keys: dict):
    """
    Converts a dictionary with camel case keys to a dictionary with snake case keys.
    e.g {"aCamelCaseKey": "value"} will be converted to {"a_camel_case_key": "value"}
    it DOES NOT change keys of nested dictionaries, only changes on the first level

    @param dict_with_camel_keys: <dict> a dictionary with camel keys
    @return:
    """
    response_dict = {}
    for key, value in deepcopy(dict_with_camel_keys).items():
        response_dict[camel_to_snake_case(key)] = value

    return response_dict


def return_bucket_region_and_type(location_constraint):
    location = location_constraint.rsplit("-", 1)
    return location[0], location[1]


def get_cos_object_name(cloud_id, bucket_name, object_name, region_name):
    """concatenate an integer value if this object already exist in this bucket"""
    from ibm.common.clients.ibm_clients import COSClient
    cos_client = COSClient(cloud_id=cloud_id)
    cos_objects = [
        cos_object["Key"] for cos_object in cos_client.list_cos_bucket_objects(region=region_name, bucket=bucket_name)
    ]

    while True:
        found = [object_name in img for img in cos_objects]
        if not any(found):
            return object_name
        else:
            object_name = object_name + str(randint(1, 1000))


def is_private_ip(ip):
    try:
        network = Network(ip)
        if network.info() == "PRIVATE":
            return ip
    except ValueError:
        return


def get_network(ip_range):
    """
    Get network from provided IP
    :param ip_range:
    :return:
    """
    try:
        ip = Network(ip_range)
        network = "{}/{}".format(str(ip.network()), str(ip.subnet()))
    except ValueError as e:
        LOGGER.debug(e)
        return
    return network


def remove_duplicates(seq: list) -> list:
    """
    Remove all the duplicates from a list with Preserving order.
    With using set on list, the order is not preserved while duplicates are removed.
    :param seq: A list
    :return:
    """
    seen = set()
    seen_add = seen.add
    return [x for x in seq if not (x in seen or seen_add(x))]


def transform_ibm_name(name):
    """
    This method transform a given string into IBM allowed string names. It does so by
    1) Check for special characters
    2) Check for names starting with Numbers
    3) Checks for more than one consecutive hyphens within a given string
    4) Check for first character to be an upper case character or number and then transforms accordingly.
    :return:
    """
    try:
        ibm_name = name.lower().translate({ord(name_string): "-" for name_string in r" !@#$%^&*()[]{};:,./<>?\|`~-=_+"})
        while "--" in ibm_name:
            ibm_name = ibm_name.replace("--", "-")

        if ibm_name and ibm_name[0].isdigit():
            ibm_name = f"ibm-{ibm_name}"

        return ibm_name

    except Exception as ex:
        LOGGER.debug(ex)
        return name


def encrypt_api_key(api_key):
    """Encrypt api_key"""
    from config import EncryptionConfig

    if not api_key:
        return ""

    try:
        salt = get_random_bytes(EncryptionConfig.SALT_LENGTH)
        iv = get_random_bytes(EncryptionConfig.BLOCK_SIZE)

        derived_secret = hashlib.pbkdf2_hmac(
            hash_name='sha256', password=EncryptionConfig.SECRET.encode(), salt=salt,
            iterations=EncryptionConfig.DERIVATION_ROUNDS
        )
        length = 16 - (len(api_key) % 16)
        api_key += chr(length) * length
        cipher = AES.new(derived_secret, AES.MODE_CBC, iv)
        return base64.b64encode(cipher.encrypt(str.encode(api_key)) + iv + salt)
    except Exception as e:
        LOGGER.info(f"Exception raised while encrypting: {api_key} Exception message: {e}")
        return api_key


def decrypt_api_key(api_key):
    """Decrypt api_key"""
    from config import EncryptionConfig

    if not api_key:
        return ""

    try:
        secret_key = base64.b64decode(api_key)
        start_iv = len(secret_key) - EncryptionConfig.BLOCK_SIZE - EncryptionConfig.SALT_LENGTH
        start_salt = len(secret_key) - EncryptionConfig.SALT_LENGTH
        data, iv, salt = (
            secret_key[:start_iv],
            secret_key[start_iv:start_salt],
            secret_key[start_salt:],
        )
        derived_secret = hashlib.pbkdf2_hmac(
            hash_name="sha256", password=EncryptionConfig.SECRET.encode(), salt=salt,
            iterations=EncryptionConfig.DERIVATION_ROUNDS
        )

        derived_secret = derived_secret[:EncryptionConfig.KEY_SIZE]
        cipher = AES.new(derived_secret, AES.MODE_CBC, iv)
        secret_key = cipher.decrypt(data)
        length = secret_key[-1]
        return secret_key[:-length].decode("utf-8")
    except Exception as e:
        LOGGER.info(f"Exception raised while decrypting: {api_key} Exception message: {e}")
        return api_key


def validate_ip_in_range(subnet_ip, address_prefix):
    try:
        ips = Network(address_prefix)
        if subnet_ip in ips:
            return True
    except ValueError as e:
        LOGGER.debug(e)
        return


def is_private(ip):
    try:
        network = Network(ip)
        if network.info() == "PRIVATE":
            return True
        return False
    except ValueError:
        return


def calculate_address_range(from_address, to_address):
    """
    Calculate Address Range for addresses extracted from Vyatta Gateway
    :return:
    """
    address_list = list()
    try:
        address_prefix = ".".join(from_address.split("-")[0].split(".")[:-2])
        from_address_split = from_address.split(".")
        to_address_split = to_address.split(".")

        from_address_3rd_octet = int(from_address_split[2])
        from_address_4th_octet = int(from_address_split[3])
        to_address_3rd_octet = int(to_address_split[2])
        to_address_4th_octet = int(to_address_split[3])

        for octet_3 in range(from_address_3rd_octet, to_address_3rd_octet + 1):
            if octet_3 not in [from_address_3rd_octet, to_address_3rd_octet]:
                for octet_4 in range(0, 256):
                    address_list.append(
                        address_prefix + "." + str(octet_3) + "." + str(octet_4)
                    )
            elif octet_3 == from_address_3rd_octet and octet_3 == to_address_3rd_octet:
                for octet_4 in range(from_address_4th_octet, to_address_4th_octet + 1):
                    address_list.append(
                        address_prefix + "." + str(octet_3) + "." + str(octet_4)
                    )
            elif octet_3 == from_address_3rd_octet:
                for octet_4 in range(from_address_4th_octet, 256):
                    address_list.append(
                        address_prefix + "." + str(octet_3) + "." + str(octet_4)
                    )
            elif octet_3 == to_address_3rd_octet:
                for octet_4 in range(0, to_address_4th_octet + 1):
                    address_list.append(
                        address_prefix + "." + str(octet_3) + "." + str(octet_4)
                    )
    except ValueError:
        return

    return address_list


def get_months_date_interval(months=-6):
    """
    Return last three month's datetime interval to calculate recommendations
    """
    start_date = datetime.today() + relativedelta(months=months)
    end_date = datetime.now(timezone.utc)

    return start_date.timestamp(), end_date.timestamp()


def get_month_interval(month_name=None):
    from dateutil.relativedelta import relativedelta

    utcnow = datetime.utcnow()
    current_month = datetime(utcnow.year, utcnow.month, 1)
    if month_name:
        month_datetime = current_month.replace(month=MONTHS_STR_TO_INT[month_name.lower()])
        if month_datetime > current_month:
            month_datetime = month_datetime - relativedelta(years=1)
        return month_datetime, month_datetime + relativedelta(months=1)
    else:
        return current_month, current_month + relativedelta(months=1)


def calculate_average(records):
    """
    Returns average of records provided as list
    sum(items) / count(items)
    """
    total = {}
    for item in records:
        counter, date_time, item_type = item.values()
        total[item_type] = [x + y for x, y in zip(total.get(item_type, [0, 0]), [counter, 1])]

    # average of each item_type
    averages = {}
    for item, value in total.items():
        average = round(value[0] / value[1], 2)
        averages[item] = average

    return averages


def init_consumption_client():
    """
    INIT method for Consumption Client
    """
    from consumption_client import Configuration, ApiClient, ConsumptionApi

    configuration = Configuration()
    configuration.host = ConsumptionClientConfig.CONSUMPTION_APP_URL
    configuration.api_key['X-API-Key'] = ConsumptionClientConfig.CONSUMPTION_APP_API_KEY
    return ConsumptionApi(ApiClient(configuration))


def init_subscription_client():
    """
    INIT method for Subscription Client
    """
    from subscription_client import Configuration, ApiClient

    configuration = Configuration()
    configuration.host = SubscriptionClientConfig.SUBSCRIPTION_APP_URL
    configuration.api_key['X-API-Key'] = SubscriptionClientConfig.SUBSCRIPTION_APP_API_KEY
    return ApiClient(configuration)


def initialize_cos_client(ibm_api_key_id, ibm_service_instance_id, region):
    """
    initiates cos client with the provided configs
    :return:
    """
    from ibm.common.clients.ibm_clients.urls import AUTH_URL, BUCKETS_BASE_URL

    return ibm_boto3.client(
        service_name='s3', ibm_api_key_id=ibm_api_key_id,
        ibm_service_instance_id=ibm_service_instance_id,
        ibm_auth_endpoint=AUTH_URL,
        config=Config(signature_version="oauth"),
        endpoint_url=BUCKETS_BASE_URL.format(region=region))


def get_volume_attachment_dict(capacity, zone_dict, name, index_):
    """
    Get ibm volume attachments and ibm volume const dictionaries
    """
    volume_name = f"{name}{randrange(100)}{index_}"[-62:]

    volume_attachment = {'delete_volume_on_instance_delete': True,
                         'volume': {'name': volume_name, 'capacity': int(capacity), 'zone': zone_dict,
                                    'encryption': 'provider_managed',
                                    'profile': {'name': 'general-purpose'},
                                    }
                         }
    return volume_attachment
