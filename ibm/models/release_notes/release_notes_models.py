import uuid
from datetime import datetime

from sqlalchemy import Column, DateTime, JSON, String

from ibm.models.base import Base


class IBMReleaseNote(Base):
    ID_KEY = "id"
    TITLE_KEY = "title"
    BODY_KEY = "body"
    RELEASE_DATE_KEY = "release_date"
    VERSION_KEY = "version"
    URL_KEY = "url"

    __tablename__ = "ibm_release_notes"

    id = Column(String(32), primary_key=True)
    title = Column(String(255), nullable=False)
    body = Column(JSON, nullable=False)
    release_date = Column(DateTime, nullable=False)
    url = Column(String(255), nullable=True)
    version = Column(String(32), nullable=True)

    def __init__(self, title, body, url=None, version=None):
        self.id = str(uuid.uuid4().hex)
        self.title = title
        self.body = body
        self.release_date = datetime.utcnow()
        self.url = url
        self.version = version

    def to_json(self):
        return {
            self.ID_KEY: self.id,
            self.TITLE_KEY: self.title,
            self.BODY_KEY: self.body,
            self.RELEASE_DATE_KEY: self.release_date,
            self.URL_KEY: self.url,
            self.VERSION_KEY: self.version
        }
