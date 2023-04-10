import uuid

from sqlalchemy import Column, Enum, String

from ibm.common.utils import decrypt_api_key, encrypt_api_key
from ibm.models.base import Base


class SoftlayerCloud(Base):
    ID_KEY = "id"
    NAME_KEY = "name"
    STATUS_KEY = "status"
    USERNAME_KEY = "username"

    # STATUS
    STATUS_AUTHENTICATING = "AUTHENTICATING"
    STATUS_INVALID = "INVALID"
    STATUS_VALID = "VALID"
    ALL_STATUSES = [STATUS_AUTHENTICATING, STATUS_INVALID, STATUS_VALID]

    __tablename__ = 'softlayer_clouds'

    id = Column(String(32), primary_key=True)
    name = Column(String(255), nullable=False)
    status = Column(String(50), Enum(*ALL_STATUSES), nullable=False)
    username = Column(String(255), nullable=False)
    __api_key = Column('api_key', String(500), nullable=False)

    user_id = Column(String(32), nullable=False)
    project_id = Column(String(32), nullable=False)

    def __init__(self, name, username, api_key, project_id):
        self.id = str(uuid.uuid4().hex)
        self.name = name
        self.username = username
        self.api_key = api_key
        self.status = self.STATUS_AUTHENTICATING
        self.project_id = project_id

    @property
    def api_key(self):
        return decrypt_api_key(self.__api_key)

    @api_key.setter
    def api_key(self, unencrypted_api_key):
        self.__api_key = encrypt_api_key(unencrypted_api_key)

    def to_json(self):
        return {
            self.ID_KEY: self.id,
            self.NAME_KEY: self.name,
            self.STATUS_KEY: self.status,
            self.USERNAME_KEY: self.username
        }
