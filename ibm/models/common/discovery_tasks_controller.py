from sqlalchemy import Boolean, Column, Enum, String, Integer

from ibm.models.base import Base


class DiscoveryController(Base):

    __tablename__ = 'ibm_discovery_controller'

    SERVICE_NAME_KEY = 'ResourceController'

    id = Column(Integer, primary_key=True)
    service_name = Column(Enum(SERVICE_NAME_KEY), nullable=False)
    flag = Column(Boolean, default=False)
    description = Column(String(250))
