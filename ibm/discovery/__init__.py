from contextlib import contextmanager

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from ibm.discovery.celery_app import create_celery_app
from ibm.discovery.config import SQLAlchemyConfig

engine = create_engine(
    SQLAlchemyConfig.SQLALCHEMY_DATABASE_URI,
    pool_recycle=SQLAlchemyConfig.SQLALCHEMY_POOL_RECYCLE,
    pool_timeout=SQLAlchemyConfig.SQLALCHEMY_POOL_TIMEOUT,
    pool_size=SQLAlchemyConfig.SQLALCHEMY_POOL_SIZE,
    max_overflow=SQLAlchemyConfig.SQLALCHEMY_MAX_OVERFLOW,
)

Session = sessionmaker(bind=engine)

# Create celery app
celery_app = create_celery_app()


def dispose_connection_pool():
    """ensure the parent process's database connections are not touched
    in the new connection pool"""
    engine.dispose(close=False)


@contextmanager
def get_db_session():
    session = Session()
    try:
        yield session
        session.commit()
    except Exception as e:
        session.rollback()
        raise e
    finally:
        session.close()


__all__ = [
    "get_db_session",
    "celery_app",
    "dispose_connection_pool"
]
