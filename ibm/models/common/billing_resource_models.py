import datetime
import uuid

from sqlalchemy import Column, DateTime, Enum, JSON, String

from ibm.models.base import Base


class BillingResource(Base):
    ID_KEY = "id"
    PERFORMED_AT_KEY = "performed_at"
    RESOURCE_TYPE_KEY = "resource_type"
    RESOURCE_DATA_KEY = "resource_data"
    ACTION_KEY = "action"

    CLOUD_TYPE_IBM = "IBM"

    ACTION_ADD = "ADD"
    ACTION_UPDATE = "UPDATE"
    ACTION_DELETE = "DELETE"
    ACTION_CREATE = "CREATE"
    ACTION_SYNC = "SYNC"

    ACTIONS_LIST = [ACTION_ADD, ACTION_UPDATE, ACTION_DELETE, ACTION_CREATE, ACTION_SYNC]

    __tablename__ = "billing_resources"

    id = Column(String(32), primary_key=True)
    performed_at = Column(DateTime, default=datetime.datetime.utcnow())
    resource_type = Column(String(255), nullable=False)
    resource_data = Column(JSON)
    action = Column(String(32), nullable=False)
    cloud_type = Column(Enum(CLOUD_TYPE_IBM), nullable=True, default=CLOUD_TYPE_IBM)

    cloud_id = Column(String(32))
    user_id = Column(String(32))
    project_id = Column(String(32))

    def __init__(self, resource_type, resource_data, action=ACTION_ADD, cloud_type=CLOUD_TYPE_IBM, cloud_id=None,
                 user_id=None, project_id=None):
        self.id = str(uuid.uuid4().hex)
        self.performed_at = datetime.datetime.utcnow()
        self.resource_type = resource_type
        self.resource_data = resource_data
        self.action = action
        self.cloud_type = cloud_type
        self.cloud_id = cloud_id
        self.user_id = user_id
        self.project_id = project_id

    def to_json(self):
        return {
            self.ID_KEY: self.id,
            self.PERFORMED_AT_KEY: self.performed_at,
            self.RESOURCE_TYPE_KEY: self.resource_type,
            self.RESOURCE_DATA_KEY: self.resource_data,
            self.ACTION_KEY: self.action,
        }
