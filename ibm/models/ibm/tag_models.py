import uuid

from sqlalchemy import Column, String

from ibm.models.base import Base
from ibm.models.ibm.mixins import IBMCloudResourceMixin


class IBMTag(IBMCloudResourceMixin, Base):
    ID_KEY = "id"
    NAME_KEY = "tag_name"
    RESOURCE_ID_KEY = "resource_id"
    RESOURCE_TYPE_KEY = "resource_type"
    TAG_TYPE_KEY = "tag_type"

    __tablename__ = "ibm_tags"

    id = Column(String(32), primary_key=True)
    name = Column(String(500), nullable=False)
    tag_type = Column(String(50), nullable=False, default="user")
    resource_id = Column(String(32), nullable=False)
    resource_crn = Column(String(255), nullable=False)
    resource_type = Column(String(32), nullable=False)

    CRZ_BACKREF_NAME = "tags"

    def __init__(self, name, tag_type, resource_id=None, resource_type=None, resource_crn=None):
        self.id = str(uuid.uuid4().hex)
        self.name = name
        self.tag_type = tag_type
        self.resource_id = resource_id
        self.resource_crn = resource_crn
        self.resource_type = resource_type

    @classmethod
    def from_ibm_json_body(cls, json_body):
        return cls(
            name=json_body["name"],
            tag_type="user",
            resource_crn=json_body["crn"]
            )

    def to_json(self):
        return {
            self.ID_KEY: self.id,
            self.NAME_KEY: self.name,
            self.TAG_TYPE_KEY: self.tag_type,
            self.RESOURCE_ID_KEY: self.resource_id,
            self.RESOURCE_TYPE_KEY: self.resource_type,
            self.IBM_CLOUD_KEY: self.ibm_cloud.to_reference_json() if self.ibm_cloud else None
        }

    def to_reference_json(self):
        return {
            self.ID_KEY: self.id,
            self.NAME_KEY: self.name
        }
