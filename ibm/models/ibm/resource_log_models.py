import json
import uuid
from datetime import datetime

from sqlalchemy import Column, DateTime, Enum, JSON, String

from ibm.models import IBMRegionalResourceMixin
from ibm.models.base import Base


class IBMResourceLog(IBMRegionalResourceMixin, Base):
    # status consts
    STATUS_ADDED = "added"
    STATUS_DELETED = "deleted"
    STATUS_UPDATED = "updated"

    CRZ_BACKREF_NAME = "resource_logs"

    __tablename__ = "ibm_resource_logs"

    id = Column(String(32), primary_key=True)
    resource_id = Column(String(255), nullable=False)
    resource_type = Column(String(255), nullable=False)
    performed_at = Column(DateTime, nullable=False)
    data = Column(JSON)
    status = Column(Enum(STATUS_ADDED, STATUS_DELETED, STATUS_UPDATED), nullable=False)

    def __init__(self, resource_id, status, resource_type, data, region=None):
        self.id = str(uuid.uuid4().hex)
        self.data = json.dumps(data, default=str)
        self.resource_id = resource_id
        self.status = status
        self.resource_type = resource_type
        self.performed_at = datetime.utcnow().replace(second=0, microsecond=0)
        if region:
            self.region = region
