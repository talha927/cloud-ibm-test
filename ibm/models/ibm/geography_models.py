import uuid

from sqlalchemy import Column, Enum, String, Text
from sqlalchemy.schema import UniqueConstraint
from sqlalchemy.orm import relationship

from ibm.models.base import Base
from ibm.models.ibm.mixins import IBMCloudResourceMixin, IBMRegionalResourceMixin


class IBMRegion(IBMCloudResourceMixin, Base):
    ID_KEY = "id"
    ENDPOINT_KEY = "endpoint"
    HREF_KEY = "href_key"
    NAME_KEY = "name"
    IBM_STATUS_KEY = "status"
    ZONES_KEY = "zones"

    CRZ_BACKREF_NAME = "regions"

    IBM_STATUS_AVAILABLE = "available"
    IBM_STATUS_UNAVAILABLE = "unavailable"
    ALL_STATUSES_LIST = [IBM_STATUS_AVAILABLE, IBM_STATUS_UNAVAILABLE]

    __tablename__ = "ibm_regions"

    id = Column(String(32), primary_key=True)
    endpoint = Column(String(64), nullable=False)
    href = Column(Text, nullable=False)
    name = Column(String(255), nullable=False)
    ibm_status = Column(Enum(*ALL_STATUSES_LIST), nullable=False)

    monitoring_token = relationship(
        "IBMMonitoringToken",
        backref="ibm_region",
        cascade="all, delete-orphan",
        passive_deletes=True,
        uselist=False
    )

    resource_tracking = relationship(
        "IBMResourceTracking",
        backref="region",
        cascade="all, delete-orphan",
        passive_deletes=True,
        lazy="dynamic"
    )

    __table_args__ = (UniqueConstraint(name, "cloud_id", name="uix_ibm_region_name_cloud_id"),)

    def __init__(self, endpoint=None, href=None, name=None, ibm_status=None):
        self.id = str(uuid.uuid4().hex)
        self.endpoint = endpoint
        self.href = href
        self.name = name
        self.ibm_status = ibm_status

    def to_reference_json(self):
        return {
            self.ID_KEY: self.id,
            self.NAME_KEY: self.name
        }

    def to_json(self, with_zones=False):
        json_data = {
            self.ID_KEY: self.id,
            self.NAME_KEY: self.name,
            self.IBM_STATUS_KEY: self.ibm_status
        }
        if with_zones:
            json_data["zones"] = [zone.to_json(region_reference=False) for zone in self.zones.all()]

        return json_data

    def update_from_obj(self, obj):
        assert isinstance(obj, self.__class__)

        self.endpoint = obj.endpoint
        self.href = obj.href
        self.name = obj.name
        self.ibm_status = obj.ibm_status

    @classmethod
    def from_ibm_json_body(cls, json_body):
        return cls(
            endpoint=json_body["endpoint"],
            href=json_body["href"],
            name=json_body["name"],
            ibm_status=json_body["status"],
        )


class IBMZone(IBMRegionalResourceMixin, Base):
    ID_KEY = "id"
    HREF_KEY = "href_key"
    NAME_KEY = "name"
    IBM_STATUS_KEY = "status"

    CRZ_BACKREF_NAME = "zones"

    IBM_STATUS_AVAILABLE = "available"
    IBM_STATUS_IMPAIRED = "impaired"
    IBM_STATUS_UNAVAILABLE = "unavailable"
    ALL_STATUSES_LIST = [IBM_STATUS_AVAILABLE, IBM_STATUS_IMPAIRED, IBM_STATUS_UNAVAILABLE]

    __tablename__ = "ibm_zones"

    id = Column(String(32), primary_key=True)
    href = Column(Text, nullable=False)
    name = Column(String(255), nullable=False)
    ibm_status = Column(Enum(*ALL_STATUSES_LIST), nullable=False)

    __table_args__ = (UniqueConstraint(name, "region_id", name="uix_ibm_zone_name_region_id"),)

    def __init__(self, href=None, name=None, ibm_status=None):
        self.id = str(uuid.uuid4().hex)
        self.href = href
        self.name = name
        self.ibm_status = ibm_status

    def to_reference_json(self):
        return {
            self.ID_KEY: self.id,
            self.NAME_KEY: self.name
        }

    def to_json(self, region_reference=True):
        json_data = {
            self.ID_KEY: self.id,
            self.NAME_KEY: self.name,
            self.IBM_STATUS_KEY: self.ibm_status
        }
        if region_reference:
            json_data["region"] = self.region.to_reference_json()

        return json_data

    def to_json_body(self):
        return {
            "name": self.name
        }

    def update_from_obj(self, obj):
        assert isinstance(obj, self.__class__)

        self.href = obj.href
        self.name = obj.name
        self.ibm_status = obj.ibm_status

    @classmethod
    def from_ibm_json_body(cls, json_body):
        return cls(
            href=json_body["href"],
            name=json_body["name"],
            ibm_status=json_body["status"],
        )
