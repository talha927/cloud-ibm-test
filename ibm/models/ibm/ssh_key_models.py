import logging
import uuid
from datetime import datetime

from sqlalchemy import Column, DateTime, Enum, ForeignKey, String, Text
from sqlalchemy.schema import UniqueConstraint

from ibm.common.consts import CREATED, CREATED_AT_FORMAT, DUMMY_CLOUD_ID, DUMMY_CLOUD_NAME, DUMMY_REGION_ID, \
    DUMMY_REGION_NAME, DUMMY_RESOURCE_GROUP_ID, DUMMY_RESOURCE_GROUP_NAME
from ibm.models.base import Base
from ibm.models.ibm.mixins import IBMRegionalResourceMixin

LOGGER = logging.getLogger(__name__)


class IBMSshKey(IBMRegionalResourceMixin, Base):
    ID_KEY = "id"
    NAME_KEY = "name"
    TYPE_KEY = "type"
    PUBLIC_KEY = "public_key"
    FINGER_PRINT_KEY = "finger_print"
    STATUS_KEY = "status"
    CLOUD_ID_KEY = "cloud_id"
    MESSAGE_KEY = "message"
    LENGTH_KEY = "length"
    HREF_KEY = "href"
    CRN_KEY = "crn"
    CREATED_AT_KEY = "created_at"
    RESOURCE_GROUP_KEY = "resource_group"
    RESOURCE_JSON_KEY = "resource_json"

    CRZ_BACKREF_NAME = "ssh_keys"

    # SSH_KEY LENGTHS
    KEY_LENGTH_1024 = "1024"
    KEY_LENGTH_2048 = "2048"
    KEY_LENGTH_4096 = "4096"

    # ENCRYPTION TYPE
    ENCRYPTION_TYPE_RSA = "rsa"

    __tablename__ = "ibm_ssh_keys"

    id = Column(String(32), primary_key=True)
    created_at = Column(DateTime, default=datetime.utcnow(), nullable=False)
    name = Column(String(255), nullable=False)
    crn = Column(String(500), nullable=False)
    href = Column(Text, nullable=False)
    resource_id = Column(String(64), nullable=False)
    status = Column(String(50), nullable=False)
    type_ = Column('type', Enum(ENCRYPTION_TYPE_RSA), default=ENCRYPTION_TYPE_RSA, nullable=False)
    length = Column(Enum(KEY_LENGTH_1024, KEY_LENGTH_2048, KEY_LENGTH_4096), nullable=False)
    public_key = Column(String(1024), nullable=False)
    finger_print = Column(String(1024), nullable=False)

    resource_group_id = Column(String(32), ForeignKey("ibm_resource_groups.id", ondelete="CASCADE"))

    __table_args__ = (UniqueConstraint(resource_id, "cloud_id", name="uix_ibm_ssh_resource_id_cloud_id"),)

    def __init__(self, name, type_, public_key, length=None, finger_print=None, status=CREATED, resource_id=None,
                 crn=None, href=None, created_at=None):
        self.id = str(uuid.uuid4().hex)
        self.name = name
        self.status = status
        self.resource_id = resource_id
        self.crn = crn
        self.href = href
        self.length = length
        self.finger_print = finger_print
        self.type_ = type_ or self.ENCRYPTION_TYPE_RSA
        self.public_key = public_key
        self.created_at = created_at

    def to_reference_json(self):
        return {
            self.ID_KEY: self.id,
            self.NAME_KEY: self.name
        }

    def to_template_json(self):
        resource_json = {
            self.NAME_KEY: self.name,
            self.PUBLIC_KEY: self.public_key,
            self.RESOURCE_GROUP_KEY: {self.ID_KEY: self.resource_group_id},
        }

        resource_data = {
            self.ID_KEY: self.id,
            self.IBM_CLOUD_KEY: {self.ID_KEY: self.cloud_id},
            self.REGION_KEY: {self.ID_KEY: self.region_id},
            self.RESOURCE_JSON_KEY: resource_json
        }

        return resource_data

    def validate_json_for_schema(self):
        return {
            self.ID_KEY: self.id,
            self.RESOURCE_JSON_KEY: {
                self.NAME_KEY: self.name,
                self.PUBLIC_KEY: self.public_key
            }
        }

    def to_json(self):
        return {
            self.ID_KEY: self.id,
            self.NAME_KEY: self.name,
            self.STATUS_KEY: self.status,
            self.LENGTH_KEY: self.length,
            self.FINGER_PRINT_KEY: self.finger_print,
            self.PUBLIC_KEY: self.public_key,
            self.TYPE_KEY: self.type_,
            self.CREATED_AT_KEY: self.created_at,
            self.CRN_KEY: self.crn,
            self.HREF_KEY: self.href,
            self.RESOURCE_GROUP_KEY: self.resource_group.to_reference_json(),
            self.REGION_KEY: self.region.to_reference_json(),
            self.IBM_CLOUD_KEY: self.ibm_cloud.to_reference_json(),
        }

    def to_json_body(self):
        obj = {"name": self.name, "public_key": self.public_key, "type": self.type_}
        if self.ibm_resource_group:
            obj["resource_group"] = {"id": self.ibm_resource_group.resource_id}
        return obj

    @classmethod
    def from_ibm_json_body(cls, json_body):
        return cls(
            name=json_body["name"], public_key=json_body["public_key"], status="CREATED",
            resource_id=json_body["id"], type_=json_body["type"], length=str(json_body["length"]),
            finger_print=json_body["fingerprint"], crn=json_body["crn"], href=json_body["href"],
            created_at=datetime.strptime(json_body["created_at"], CREATED_AT_FORMAT))

    def from_softlayer_to_ibm(self):
        resource_json = {
            self.NAME_KEY: self.name,
            self.PUBLIC_KEY: self.public_key,
            self.RESOURCE_GROUP_KEY: {
                "id": DUMMY_RESOURCE_GROUP_ID,
                "name": DUMMY_RESOURCE_GROUP_NAME
            },
        }
        ssh_key_schema = {
            self.ID_KEY: self.id,
            "ibm_cloud": {
                "id": DUMMY_CLOUD_ID,
                "name": DUMMY_CLOUD_NAME
            },
            "region": {
                "id": DUMMY_REGION_ID,
                "name": DUMMY_REGION_NAME
            },
            "resource_json": resource_json
        }

        return ssh_key_schema

    def update_from_object(self, other):
        assert isinstance(other, self.__class__)

        self.name = other.name
        self.resource_id = other.resource_id
        self.crn = other.crn
        self.href = other.href
        self.status = other.status
        self.type_ = other.type_
        self.length = other.length
        self.public_key = other.public_key
        self.finger_print = other.finger_print

    def dis_params_eq(self, other):
        assert isinstance(other, self.__class__)

        return (self.name == other.name and self.resource_id == other.resource_id and
                self.public_key == other.public_key and self.finger_print == other.finger_print)

    def dis_add_update_db(self, session, db_ssh_key, db_cloud, db_resource_group, db_region):
        # db_ssh_keys_id_obj_dict = dict()
        # db_ssh_keys_name_obj_dict = dict()
        # for db_ssh_key in db_ssh_keys:
        #     try:
        #         db_ssh_keys_id_obj_dict[db_ssh_key.resource_id] = db_ssh_key
        #         db_ssh_keys_name_obj_dict[db_ssh_key.name] = db_ssh_key
        #     except orm.exc.ObjectDeletedError as ex:
        #         LOGGER.warning(ex)

        existing = db_ssh_key or None
        # if self.resource_id not in db_ssh_keys_id_obj_dict and self.name in db_ssh_keys_name_obj_dict:
        #     # Creation Pending / Creating
        #     existing = db_ssh_keys_name_obj_dict[self.name]
        # elif self.resource_id in db_ssh_keys_id_obj_dict:
        #     # Created. Update everything including name
        #     existing = db_ssh_keys_id_obj_dict[self.resource_id]
        # else:
        #     existing = None

        if not existing:
            self.ibm_cloud = db_cloud
            self.resource_group = db_resource_group
            self.region = db_region
            session.add(self)
            session.commit()
            return
        # except orm.exc.ObjectDeletedError as ex:
        #     LOGGER.warning(ex)
        #     return

        if not self.dis_params_eq(existing):
            existing.update_from_object(self)
            existing.resource_group = db_resource_group
            existing.region = db_region
        # except orm.exc.ObjectDeletedError as ex:
        #     LOGGER.warning(ex)

        session.commit()
