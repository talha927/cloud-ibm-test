from contextlib import contextmanager
from typing import ContextManager

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.orm.session import Session as _Session

from config import MangosIBMGRPCClientConfigs, SQLAlchemyConfig
from ibm.common.logger import get_logger
from mangos_grpc_client.ibm import create_mangos_client

mangos_ibm = create_mangos_client(MangosIBMGRPCClientConfigs)

Session = sessionmaker(
    bind=create_engine(
        SQLAlchemyConfig.SQLALCHEMY_DATABASE_URI,
        pool_recycle=SQLAlchemyConfig.SQLALCHEMY_POOL_RECYCLE,
        pool_timeout=SQLAlchemyConfig.SQLALCHEMY_POOL_TIMEOUT,
        pool_size=SQLAlchemyConfig.SQLALCHEMY_POOL_SIZE,
        max_overflow=SQLAlchemyConfig.SQLALCHEMY_MAX_OVERFLOW,
    )
)
LOGGER = get_logger()


@contextmanager
def get_db_session() -> ContextManager[_Session]:
    session = Session()
    try:
        yield session
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()
