import uuid

from sqlalchemy import Boolean, Column, DateTime, Enum, ForeignKey, PrimaryKeyConstraint, String, Table, Text, \
    UniqueConstraint
from sqlalchemy.orm import backref, relationship

from ibm.common.consts import BUCKET_CROSS_REGION_TO_REGIONS_MAPPER, BUCKET_DATA_CENTER_TO_REGION_MAPPER
from ibm.common.utils import return_bucket_region_and_type, return_datetime_object
from ibm.models.base import Base
from ibm.models.ibm.mixins import IBMCloudResourceMixin

ibm_bucket_regions = Table(
    "ibm_bucket_regions", Base.metadata,
    Column("region_id", String(32), ForeignKey("ibm_regions.id", ondelete="CASCADE")),
    Column("bucket_id", String(32), ForeignKey("ibm_cos_buckets.id", ondelete="CASCADE")),
    PrimaryKeyConstraint("region_id", "bucket_id"),
)


class IBMCloudObjectStorage(IBMCloudResourceMixin, Base):
    ID_KEY = "id"
    NAME_KEY = "name"
    GUID_KEY = "guid"
    CRN_KEY = "crn"
    CREATED_AT_KEY = "created_at"
    UPDATED_AT_KEY = "updated_at"
    MIGRATED_KEY = "migrated"
    LOCKED_KEY = "locked"
    RESOURCE_JSON_KEY = "resource_json"

    CRZ_BACKREF_NAME = "cloud_object_storages"

    __tablename__ = "ibm_cloud_object_storages"

    id = Column(String(32), primary_key=True)
    name = Column(String(255), nullable=False)
    guid = Column(String(255), nullable=False)
    crn = Column(Text, nullable=False)
    created_at = Column(DateTime)
    updated_at = Column(DateTime)
    migrated = Column(Boolean)
    locked = Column(Boolean)

    buckets = relationship("IBMCOSBucket", backref="cloud_object_storage", cascade="all, delete-orphan",
                           passive_deletes=True, lazy="dynamic")
    credential_keys = relationship("IBMServiceCredentialKey", backref="cloud_object_storage",
                                   cascade="all, delete-orphan", passive_deletes=True, lazy="dynamic")

    def __init__(self, name, guid, crn, created_at,
                 updated_at=None, migrated=False, locked=False):
        self.id = str(uuid.uuid4().hex)
        self.name = name
        self.guid = guid
        self.crn = crn
        self.created_at = created_at
        self.updated_at = updated_at
        self.migrated = migrated
        self.locked = locked

    def to_json(self):
        """
        Return a JSON representation of the object
        """
        return {
            self.ID_KEY: self.id,
            self.NAME_KEY: self.name,
            self.GUID_KEY: self.guid,
            self.CRN_KEY: self.crn,
            self.CREATED_AT_KEY: str(self.created_at),
            self.UPDATED_AT_KEY: str(self.updated_at),
            self.MIGRATED_KEY: self.migrated,
            self.LOCKED_KEY: self.locked,
            self.IBM_CLOUD_KEY: self.ibm_cloud.to_reference_json()
        }

    def to_reference_json(self):
        return {
            self.ID_KEY: self.id,
            self.NAME_KEY: self.name,
        }

    def validate_json_for_schema(self):
        return {
            self.ID_KEY: self.id,
            self.RESOURCE_JSON_KEY: {
                self.NAME_KEY: self.name,
            }
        }

    def update_from_object(self, obj):
        assert isinstance(obj, self.__class__)

        self.name = obj.name
        self.guid = obj.guid
        self.crn = obj.crn
        self.created_at = obj.created_at
        self.updated_at = obj.updated_at
        self.migrated = obj.migrated
        self.locked = obj.locked

    def dis_params_eq(self, other):
        assert isinstance(other, self.__class__)

        return (
                self.name == other.name
                and self.guid == other.guid
                and self.crn == other.crn
                and self.migrated == other.migrated
        )

    def dis_add_update_db(self, db_session, db_cloud_object_storage, db_cloud):
        existing = db_cloud_object_storage or None
        if not existing:
            self.ibm_cloud = db_cloud
            db_session.commit()
            return

        if not self.dis_params_eq(existing):
            existing.update_from_object(self)

        db_session.commit()

    @classmethod
    def from_ibm_json_body(cls, json_body):
        ibm_cloud_object_storage = cls(
            name=json_body["name"], crn=json_body["crn"],
            created_at=return_datetime_object(json_body["created_at"][:-4] + "Z"),
            updated_at=return_datetime_object(json_body["updated_at"][:-4] + "Z"),
            migrated=json_body["migrated"],
            guid=json_body["guid"],
            locked=json_body["locked"]
        )

        return ibm_cloud_object_storage


class IBMCOSBucket(IBMCloudResourceMixin, Base):
    ID_KEY = "id"
    NAME_KEY = "name"
    CREATED_AT_KEY = "created_at"
    LOCATION_CONSTRAINT_KEY = "location_constraint"
    TYPE_KEY = "type"
    RESILIENCY_KEY = "resiliency"
    CLOUD_OBJECT_STORAGE_KEY = "cloud_object_storage"
    REGIONS_KEY = "regions"
    RESOURCE_JSON_KEY = "resource_json"

    # bucket type
    TYPE_STANDARD = "standard"
    TYPE_SMART = "smart"
    TYPE_FLEX = "flex"
    TYPE_COLD = "cold"
    TYPE_VAULT = "vault"
    TYPE_ONERATE_ACTIVE = "onerate_active"
    ALL_TYPES = [TYPE_STANDARD, TYPE_SMART, TYPE_FLEX, TYPE_COLD, TYPE_VAULT, TYPE_ONERATE_ACTIVE]

    RESILIENCY_CROSS_REGION = "cross-region"
    RESILIENCY_REGIONAL = "regional"
    RESILIENCY_SINGLE_SITE = "single-site"
    ALL_RESILIENCIES = [RESILIENCY_CROSS_REGION, RESILIENCY_REGIONAL, RESILIENCY_SINGLE_SITE]

    CRZ_BACKREF_NAME = "cos_buckets"

    __tablename__ = "ibm_cos_buckets"

    id = Column(String(32), primary_key=True)
    name = Column(String(255), nullable=False)
    created_at = Column(DateTime)
    location_constraint = Column(String(255), nullable=False)
    type_ = Column('type', Enum(*ALL_TYPES), nullable=False)
    resiliency = Column(Enum(*ALL_RESILIENCIES), nullable=False)

    cloud_object_storage_id = Column(String(32), ForeignKey("ibm_cloud_object_storages.id", ondelete="CASCADE"))

    regions = relationship(
        "IBMRegion", secondary=ibm_bucket_regions, lazy="dynamic", backref=backref("cos_buckets", lazy="dynamic"))

    __table_args__ = (
        UniqueConstraint(name, cloud_object_storage_id, "cloud_id",
                         name="uix_ibm_cos_bucket_name_cloud_object_storage_id_cloud_id"),
    )

    def __init__(self, name, created_at, type_=None, location_constraint=None, resiliency=None):
        self.id = str(uuid.uuid4().hex)
        self.name = name
        self.created_at = created_at
        self.type_ = type_
        self.location_constraint = location_constraint
        self.resiliency = resiliency

    def to_json(self):
        """
        Return a JSON representation of the object
        """
        return {
            self.ID_KEY: self.id,
            self.NAME_KEY: self.name,
            self.CREATED_AT_KEY: str(self.created_at),
            self.LOCATION_CONSTRAINT_KEY: self.location_constraint,
            self.TYPE_KEY: self.type_,
            self.RESILIENCY_KEY: self.resiliency,
            self.IBM_CLOUD_KEY: self.ibm_cloud.to_reference_json(),
            self.CLOUD_OBJECT_STORAGE_KEY: self.cloud_object_storage.to_reference_json(),
            self.REGIONS_KEY: [region.to_reference_json() for region in self.regions.all()],
        }

    def to_reference_json(self):
        return {
            self.ID_KEY: self.id,
            self.NAME_KEY: self.name,
        }

    def validate_json_for_schema(self):
        return {
            self.ID_KEY: self.id,
            self.RESOURCE_JSON_KEY: {
                self.NAME_KEY: self.name,
            }
        }

    def update_from_object(self, obj):
        assert isinstance(obj, self.__class__)

        self.name = obj.name
        self.created_at = obj.created_at
        self.location_constraint = obj.location_constraint
        self.type_ = obj.type_

    @classmethod
    def from_ibm_json_body(cls, json_body):
        ibm_cos_bucket = cls(
            name=json_body["Name"],
            created_at=return_datetime_object(json_body["CreationDate"])
        )
        ibm_cos_bucket.location_constraint, ibm_cos_bucket.type_ = \
            return_bucket_region_and_type(json_body["LocationConstraint"])

        if ibm_cos_bucket.location_constraint in BUCKET_CROSS_REGION_TO_REGIONS_MAPPER:
            ibm_cos_bucket.resiliency = cls.RESILIENCY_CROSS_REGION
        elif ibm_cos_bucket.location_constraint in BUCKET_DATA_CENTER_TO_REGION_MAPPER:
            ibm_cos_bucket.resiliency = cls.RESILIENCY_SINGLE_SITE
        else:
            ibm_cos_bucket.resiliency = cls.RESILIENCY_REGIONAL

        return ibm_cos_bucket
