import logging
import os

BASEDIR = os.path.abspath(os.path.dirname(__file__))


class PaginationConfig:
    DEFAULT_ITEMS_PER_PAGE = 10
    MAX_ITEMS_PER_PAGE = 50


class EncryptionConfig:
    SALT_LENGTH = 32
    DERIVATION_ROUNDS = 100000
    BLOCK_SIZE = 16
    KEY_SIZE = 32
    SECRET = "nw2FrNshF"


class DatabaseConfig:
    IBM_DB_PARAMS = {
        "IBM_DB_MYSQL_USER": os.environ.get("ENV_IBM_DB_MYSQL_USER", "root"),
        "IBM_DB_MYSQL_PASSWORD": os.environ.get("ENV_IBM_DB_MYSQL_PASSWORD", "admin123"),
        "IBM_DB_HOST": os.environ.get("ENV_IBM_DB_HOST", "mysqldb"),
        "IBM_DB_PORT": os.environ.get("ENV_IBM_DB_PORT", "3306"),
        "IBM_DB_NAME": os.environ.get("ENV_IBM_DB_NAME", "ibmdb")
    }

    MYSQLDB_URL = "mysql+mysqldb://{IBM_DB_MYSQL_USER}:{IBM_DB_MYSQL_PASSWORD}@{IBM_DB_HOST}:{IBM_DB_PORT}/{" \
                  "IBM_DB_NAME}".format(**IBM_DB_PARAMS)


class SQLAlchemyConfig:
    SQLALCHEMY_DATABASE_URI = DatabaseConfig.MYSQLDB_URL
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    SQLALCHEMY_POOL_RECYCLE = int(os.environ.get("SQLALCHEMY_POOL_RECYCLE", "400"))
    SQLALCHEMY_POOL_TIMEOUT = int(os.environ.get("SQLALCHEMY_POOL_TIMEOUT", "450"))
    SQLALCHEMY_POOL_SIZE = int(os.environ.get("SQLALCHEMY_POOL_SIZE", "5"))
    SQLALCHEMY_MAX_OVERFLOW = int(os.environ.get("SQLALCHEMY_MAX_OVERFLOW", "0"))
    SQLALCHEMY_ENGINE_OPTIONS = {
        "pool_recycle": SQLALCHEMY_POOL_RECYCLE,
        "pool_timeout": SQLALCHEMY_POOL_TIMEOUT,
        "pool_size": SQLALCHEMY_POOL_SIZE,
        "max_overflow": SQLALCHEMY_MAX_OVERFLOW
    }


class RedisConfig:
    REDIS_PARAMS = {
        "REDIS_HOST": os.environ.get("REDIS_HOST", "vpcplus_ibm-redis"),
        "REDIS_PORT": os.environ.get("REDIS_PORT", "6379"),
        "REDIS_DB_NUMBER": os.environ.get("REDIS_DB_NUMBER", "0"),
    }

    REDIS_URL = "redis://{REDIS_HOST}:{REDIS_PORT}/{REDIS_DB_NUMBER}".format(
        **REDIS_PARAMS
    )


class BrokerConfig:
    BROKER_NAME = os.environ.get("BROKER_NAME", "redis")


class VeleroConfig:
    VELERO_API_KEY = os.environ.get("ENV_DRASS_VELERO_API_KEY", "mykey123")
    VELERO_PARAMS = {
        "VELERO_HOST": os.environ.get("ENV_DRASS_VELERO_HOST", "https://vpc-kube-migration.wanclouds.net"),
        "VELERO_VERSION": os.environ.get("ENV_DRASS_VELERO_VERSION", "/v1/kube/task"),
    }
    VELERO_HEADERS = {'x-api-key': VELERO_API_KEY}
    VELERO_URL = "{VELERO_HOST}{VELERO_VERSION}".format(**VELERO_PARAMS)


class ImageConversionConfig:
    # TODO: should not be hard coded like this
    SL_USERNAME = os.environ.get("SL_USERNAME", "danny@wanclouds")
    SL_API_KEY = os.environ.get("SL_API_KEY", "9f9473d44da206bfaf96a673369e84124606cdde6d7f69194c28c21604edaef9")
    WEBHOOK_BASE_URL = os.environ.get(
        "WEBHOOK_BASE_URL", "{protocol}://{server_ip}/{api_version}/ibm/image_conversion/"
    )


class WorkerConfig:
    VPCPLUS_LINK = os.environ.get("VPCPLUS_LINK", "https://migrate-test.wanclouds.net/")
    DB_MIGRATION_API_KEY = os.environ.get("DB_MIGRATION_API_KEY", "abc123!")
    DB_MIGRATION_CONTROLLER_HOST = os.environ.get("DB_MIGRATION_CONTROLLER_HOST",
                                                  "https://draas-dev.wanclouds.net/")
    DB_MIGRATION_INSTANCE_TYPE = os.environ.get("DB_MIGRATION_INSTANCE_TYPE", "vpc")


class WebConfig:
    AUTH_LINK = os.environ.get("AUTH_LINK", "http://auth_svc:8081/")
    ADMIN_APPROVAL_REQUIRED = eval(os.environ.get("ADMIN_APPROVAL_REQUIRED", "False"))
    IS_MULTI_TENANCY_ENABLE = eval(os.environ.get('IS_MULTI_TENANCY_ENABLE', "False"))
    VPCPLUS_LINK = os.environ.get("VPCPLUS_LINK", "https://migrate-test.wanclouds.net/")
    DB_MIGRATION_API_KEY = os.environ.get("DB_MIGRATION_API_KEY", "abc123!")
    DB_MIGRATION_CONTROLLER_HOST = os.environ.get("DB_MIGRATION_CONTROLLER_HOST",
                                                  "https://draas-dev.wanclouds.net/")
    DB_MIGRATION_INSTANCE_TYPE = os.environ.get("DB_MIGRATION_INSTANCE_TYPE", "vpc")


class SyncWorkerConfig:
    VPCPLUS_LINK = os.environ.get("VPCPLUS_LINK", "https://migrate-test.wanclouds.net/")


class IAMConfig:
    AUTH_LINK = os.environ.get("AUTH_LINK", "http://auth_svc:8081/")


class IBMSyncConfigs:
    ENV_PROD = os.environ.get("ENV_PROD", "false")


class FlaskConfig:
    __LOGGING_LEVEL_MAPPER = {
        "CRITICAL": logging.CRITICAL,
        "FATAL": logging.CRITICAL,
        "ERROR": logging.ERROR,
        "WARNING": logging.WARNING,
        "WARN": logging.WARNING,
        "INFO": logging.INFO,
        "DEBUG": logging.DEBUG,
    }
    try:
        LOGGING_LEVEL = os.environ.get("LOGGING_LEVEL", "DEBUG")
        LOGGING_LEVEL_MAPPED = __LOGGING_LEVEL_MAPPER[LOGGING_LEVEL]
    except KeyError:
        raise ValueError(f"LOGGING_LEVEL should be one of {list(__LOGGING_LEVEL_MAPPER.keys())}")

    SECRET_KEY = os.environ.get("SECRET_KEY", "my_precious_aws")
    PRESERVE_CONTEXT_ON_EXCEPTION = False
    MAX_CONTENT_LENGTH = 2048 * 2048


class MangosGRPCClientConfigs:
    GRPC_MAX_MESSAGE_SIZE = 100 * 1024 * 1024
    CERTS_PATH = os.environ.get("CERTS_PATH", "{}/deployment/certs".format(BASEDIR))


class MangosIBMGRPCClientConfigs(MangosGRPCClientConfigs):
    MANGOS_GRPC_HOST = os.environ.get("ENV_MANGOS_IBM_GRPC_HOST", "mangos_ibm-rpc")
    MANGOS_GRPC_PORT = int(os.environ.get("ENV_MANGOS_IBM_GRPC_PORT", "50051"))
    USE_TLS = os.environ.get("USE_TLS", "true")
    ENV_MANGOS_IBM_GRPC_API_KEY = os.environ.get("ENV_MANGOS_IBM_GRPC_API_KEY", "eb967d3e-be2c-411a-9a5c-a83c5bd79136")
    MANGOS_GRPC_URL = "{}:{}".format(MANGOS_GRPC_HOST, MANGOS_GRPC_PORT)


class FlaskDevelopmentConfig(FlaskConfig, SQLAlchemyConfig):
    # Flask Configs
    DEBUG = True
    USE_SSL = os.environ["OAUTHLIB_INSECURE_TRANSPORT"] = "1"

    # Port is not a flask env variable but is used in a custom logic to set the port for the flask server
    PORT = 8081


class TranslationConfig:
    AWS_ENV_X_API_KEY = os.environ.get("AWS_ENV_X_API_KEY", "96c7062d-9cee-4696-aaf7-b913e4dd33fe")
    VPCPLUS_LINK = os.environ.get("VPCPLUS_LINK", "https://migrate-test.wanclouds.net/")


class ConsumptionClientConfig:
    # For local testing use https://ibm-draas.wanclouds.net/
    CONSUMPTION_APP_HOST = os.environ.get("ENV_CONSUMPTION_APP_HOST", "https://draas.wanclouds.net/")
    CONSUMPTION_APP_VERSION = os.environ.get("ENV_CONSUMPTION_APP_VERSION", "v1/consumption")
    CONSUMPTION_APP_API_KEY = os.environ.get("ENV_CONSUMPTION_APP_API_KEY", "testKey123")
    CONSUMPTION_APP_URL = f"{CONSUMPTION_APP_HOST}/{CONSUMPTION_APP_VERSION}"


class SubscriptionClientConfig:
    # For local testing use https://ibm-draas.wanclouds.net/
    SUBSCRIPTION_APP_HOST = os.environ.get("ENV_SUBSCRIPTION_APP_HOST", "https://draas.wanclouds.net/")
    SUBSCRIPTION_APP_VERSION = os.environ.get("ENV_SUBSCRIPTION_APP_VERSION", "v1")
    SUBSCRIPTION_APP_API_KEY = os.environ.get("ENV_SUBSCRIPTION_APP_API_KEY", "testKey123")
    SUBSCRIPTION_APP_URL = f"{SUBSCRIPTION_APP_HOST}/{SUBSCRIPTION_APP_VERSION}"


class IBMSecurityConfig:
    IBM_ENV_X_API_KEY = os.environ.get("IBM_ENV_X_API_KEY", "drass_api_key")


class IBMCostConfig:
    IBM_COST_ANALYZER_SCHEDULER = int(os.environ.get("IBM_COST_ANALYZER_SCHEDULER", "24"))


flask_config = {
    "development": FlaskDevelopmentConfig,
    "default": FlaskDevelopmentConfig,
}
