import logging
import uuid

from sqlalchemy import Column, DateTime, ForeignKey, String

from ibm.models.base import Base

LOGGER = logging.getLogger(__name__)


class TTLInterval(Base):
    ID_KEY = "id"
    EXPIRES_AT_KEY = "expires_at"

    __tablename__ = 'ttl_intervals'

    id = Column(String(32), primary_key=True)
    expires_at = Column(DateTime, nullable=False)

    vpc_id = Column(String(32), ForeignKey("ibm_vpc_networks.id", ondelete="CASCADE"))

    def __init__(self, expires_at):
        self.id = str(uuid.uuid4().hex)
        self.expires_at = expires_at

    def to_json(self):
        return {
            self.ID_KEY: self.id,
            self.EXPIRES_AT_KEY: self.expires_at
        }

    def to_reference_json(self):
        return {
            self.ID_KEY: self.id,
            self.EXPIRES_AT_KEY: self.expires_at
        }
