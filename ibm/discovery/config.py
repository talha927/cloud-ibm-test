import os


class MYSQLConfig:
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
    SQLALCHEMY_DATABASE_URI = MYSQLConfig.MYSQLDB_URL
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


class IBMRabbitMQConfigs:
    IBM_RABBIT_PARAMS = {
        "RABBIT_ENV_RABBITMQ_USER": os.environ.get("RABBIT_ENV_RABBITMQ_USER", "guest"),
        "RABBIT_ENV_RABBITMQ_PASSWORD": os.environ.get("RABBIT_ENV_RABBITMQ_PASSWORD", "guest"),
        "RABBIT_ENV_RABBITMQ_HOST": os.environ.get("RABBIT_ENV_RABBITMQ_HOST", "vpcplus_ibm-rabbitmq"),
        "RABBIT_ENV_RABBITMQ_PORT": os.environ.get("RABBIT_ENV_RABBITMQ_PORT", "5672"),
    }

    IBM_RABBIT_URL = "amqp://{RABBIT_ENV_RABBITMQ_USER}:{RABBIT_ENV_RABBITMQ_PASSWORD}@{RABBIT_ENV_RABBITMQ_HOST}:{" \
                     "RABBIT_ENV_RABBITMQ_PORT}//".format(**IBM_RABBIT_PARAMS)


class RedisConfigs:
    REDIS_PARAMS = {
        "REDIS_HOST": os.environ.get("REDIS_HOST", "vpcplus_ibm-redis"),
        "REDIS_PORT": os.environ.get("REDIS_PORT", "6379"),
        "REDIS_DB_NUMBER": os.environ.get("REDIS_DB_NUMBER", "0"),
    }

    REDIS_URL = "redis://{REDIS_HOST}:{REDIS_PORT}/{REDIS_DB_NUMBER}".format(
        **REDIS_PARAMS
    )


class BrokerConfigs:
    BROKER_NAME = os.environ.get("BROKER_NAME", "redis")
