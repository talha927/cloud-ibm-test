import uuid
from datetime import datetime, timedelta

from sqlalchemy import Boolean, Column, DateTime, Enum, ForeignKey, JSON, String, Text
from sqlalchemy.orm import deferred, relationship

from ibm.common.utils import decrypt_api_key, encrypt_api_key, return_datetime_object
from ibm.models.base import Base
from ibm.models.ibm.mixins import IBMCloudResourceMixin
from ibm.web import db


class IBMCloud(Base):
    ID_KEY = "id"
    NAME_KEY = "name"
    STATUS_KEY = "status"
    VPC_NETWORK_KEY = "vpc_networks"
    RESOURCE_GROUP_KEY = "resource_groups"
    NETWORK_ACL_KEY = "network_acls"
    SECURITY_GROUP_KEY = "security_groups"
    PUBLIC_GATEWAY_KEY = "public_gateways"
    VPNS_KEY = "vpn_gateways"
    LOAD_BALANCERS_KEY = "load_balancers"
    IKE_POLICY_KEY = "ike_policies"
    IPSEC_POLICY_KEY = "ipsec_policies"
    INSTANCES_KEY = "instances"
    SSH_KEY = "ssh_keys"
    IMAGES_KEY = "images"
    SERVICE_CREDENTIALS_KEY = "service_credentials"
    TOTAL_COST_KEY = "total_cost"
    MONITORING_TOKENS_KEY = "monitoring_tokens"
    SETTINGS_KEY = "settings"

    ENABLE = 'ENABLE'
    DISABLE = 'DISABLE'

    STATUS_AUTHENTICATING = "AUTHENTICATING"
    STATUS_VALID = "VALID"
    STATUS_INVALID = "INVALID"
    STATUS_DELETING = "DELETING"
    STATUS_ERROR_DELETING = "ERROR_DELETING"
    STATUS_ERROR_DUPLICATE_RESOURCE_GROUPS = "ERROR_DUPLICATE_RESOURCE_GROUPS"
    ALL_STATUSES = [
        STATUS_AUTHENTICATING, STATUS_VALID, STATUS_INVALID, STATUS_ERROR_DUPLICATE_RESOURCE_GROUPS, STATUS_DELETING
    ]

    __tablename__ = "ibm_clouds"

    id = Column(String(32), primary_key=True)
    name = Column(String(255), nullable=False)
    __api_key = Column('api_key', String(500), nullable=False)
    api_key_id = Column(String(500))
    account_id = Column(String(255), nullable=True)
    deleted = Column(Boolean, default=False, nullable=False)
    status = Column(Enum(*ALL_STATUSES), nullable=False)
    metadata_ = deferred(Column("metadata", JSON, nullable=True))
    added_in_mangos = Column(Boolean, nullable=False, default=False)

    user_id = Column(String(32), nullable=False)
    project_id = Column(String(32), nullable=False)

    service_credentials = relationship(
        "IBMServiceCredentials",
        backref="ibm_cloud",
        cascade="all, delete-orphan",
        passive_deletes=True,
        uselist=False
    )

    credentials = relationship(
        "IBMCredentials",
        backref="ibm_cloud",
        cascade="all, delete-orphan",
        passive_deletes=True,
        uselist=False,
        single_parent=True
    )
    settings = relationship('IBMCloudSetting', backref='ibm_cloud', cascade='all, delete-orphan', uselist=False)

    # image_conversion_tasks = relationship(
    #     "ImageConversionTask",
    #     backref="ibm_cloud",
    #     cascade="all, delete-orphan",
    #     lazy="dynamic"
    # )
    # transit_gateways = relationship(
    #     "TransitGateway",
    #     backref="ibm_cloud",
    #     cascade="all, delete-orphan",
    #     lazy="dynamic",
    # )

    def __init__(self, name, api_key, user_id, project_id):
        self.id = str(uuid.uuid4().hex)
        self.name = name
        self.api_key = api_key
        self.status = self.STATUS_AUTHENTICATING
        self.user_id = user_id
        self.project_id = project_id

    @property
    def api_key(self):
        return decrypt_api_key(self.__api_key)

    @api_key.setter
    def api_key(self, unencrypted_api_key):
        self.__api_key = encrypt_api_key(unencrypted_api_key)

    def to_json(self):
        from ibm.web.ibm.clouds.utils import get_current_billing_month, get_latest_billing_month_from_db

        monitoring_tokens = []
        for region in self.regions.all():
            if not region.monitoring_token:
                continue

            monitoring_tokens.append(region.monitoring_token.to_json())

        return {
            self.ID_KEY: self.id,
            self.NAME_KEY: self.name,
            self.STATUS_KEY: self.status,
            self.SERVICE_CREDENTIALS_KEY: True if self.service_credentials else False,
            self.TOTAL_COST_KEY: round(sum(
                [cost.billable_cost for cost in self.costs.all()
                 if get_latest_billing_month_from_db(cost) == get_current_billing_month()])),
            self.MONITORING_TOKENS_KEY: monitoring_tokens,
            self.SETTINGS_KEY: self.settings.to_json() if self.settings else {}
        }

    def to_reference_json(self):
        return {
            self.ID_KEY: self.id,
            self.NAME_KEY: self.name
        }

    def to_json_body(self):
        return {
            "grant_type": "urn:ibm:params:oauth:grant-type:apikey",
            "apikey": decrypt_api_key(self.api_key),
        }

    def update_from_auth_response(self, auth_response):
        if not self.credentials:
            self.credentials = IBMCredentials(auth_response)
        else:
            self.credentials.access_token = " ".join(
                [auth_response.get("token_type"), auth_response.get("access_token")])
            self.credentials.expiration_date = datetime.utcnow() + timedelta(seconds=auth_response.get("expires_in"))

    @property
    def auth_required(self):
        if not self.credentials:
            return True

        if not (self.credentials.access_token and self.credentials.expiration_date):
            return True
        if (self.credentials.expiration_date - datetime.utcnow()).total_seconds() < 120:
            return True
        return False

    def update_token(self, credentials):
        self.credentials.access_token = credentials.access_token
        self.credentials.expiration_date = credentials.expiration_date
        db.session.commit()


class IBMServiceCredentials(Base):
    __tablename__ = "ibm_service_credentials"

    RESOURCE_INSTANCE_ID_KEY = "resource_instance_id"

    id = Column(String(32), primary_key=True)
    resource_instance_id = Column(String(1000), nullable=False)

    cloud_id = Column(String(32), ForeignKey("ibm_clouds.id", ondelete="CASCADE"))

    def __init__(self, resource_instance_id):
        self.id = str(uuid.uuid4().hex)
        self.resource_instance_id = resource_instance_id


class IBMCredentials(Base):
    ID_KEY = "id"
    ACCESS_TOKEN_KEY = "access_token"
    REFRESH_TOKEN_KEY = "refresh_token"
    EXPIRATION_DATE_KEY = "expiration_date"

    __tablename__ = "ibm_credentials"

    id = Column(String(32), primary_key=True)
    access_token = Column(Text, nullable=False)
    refresh_token = Column(Text)
    expiration_date = Column(DateTime)

    cloud_id = Column(String(32), ForeignKey("ibm_clouds.id", ondelete="CASCADE"))

    def __init__(self, credentials):
        self.id = str(uuid.uuid4().hex)
        self.access_token = " ".join(
            [credentials.get("token_type"), credentials.get("access_token")]
        )
        self.refresh_token = credentials.get("refresh_token")
        self.expiration_date = datetime.now() + timedelta(
            seconds=credentials.get("expires_in")
        )

    def update_token(self, credentials):
        self.access_token = credentials.access_token
        self.expiration_date = credentials.expiration_date
        db.session.commit()

    def is_token_expired(self):
        if (self.expiration_date - datetime.now()).total_seconds() < 120:
            return True

    def to_json(self):
        return {
            self.ID_KEY: self.id,
            self.ACCESS_TOKEN_KEY: self.access_token,
            self.REFRESH_TOKEN_KEY: self.refresh_token,
            self.EXPIRATION_DATE_KEY: self.expiration_date,
        }


class IBMServiceCredentialKey(Base, IBMCloudResourceMixin):
    ID_KEY = "id"
    GUID_KEY = "guid"
    CREATED_AT_KEY = "created_at"
    UPDATED_AT_KEY = "updated_at"
    NAME_KEY = "name"
    CRN_KEY = "crn"
    ROLE_KEY = "role"
    IAM_ROLE_CRN_KEY = "iam_role_crn"
    STATE_KEY = "state"
    MIGRATED_KEY = "migrated"
    CREDENTIAL_KEY = "credentials"
    COS_HMAC_KEY = "cos_hmac_keys"
    API_KEY = "apikey"
    IS_HMAC_KEY = "is_hmac"
    ACCESS_KEY_ID = "access_key_id"
    SECRET_ACCESS_KEY = "secret_access_key"
    IAM_SERVICE_ID_CRN_KEY = "iam_service_id_crn"
    CLOUD_OBJECT_STORAGE_KEY = "cloud_object_storage"

    # role consts
    ROLE_READER = "reader"
    ROLE_WRITER = "writer"
    ROLE_MANAGER = "manager"
    ROLE_CONTENT_READER = "content_reader"
    ROLE_OBJECT_WRITER = "object_writer"
    ROLE_OBJECT_MANAGER = "object_manager"
    ROLES_LIST = [ROLE_READER, ROLE_WRITER, ROLE_MANAGER, ROLE_CONTENT_READER, ROLE_OBJECT_WRITER, ROLE_OBJECT_MANAGER]

    CRZ_BACKREF_NAME = "service_credential_keys"

    __tablename__ = "ibm_service_credential_keys"

    id = Column(String(32), primary_key=True)
    guid = Column(String(255), nullable=False)
    created_at = Column(DateTime)
    updated_at = Column(DateTime)
    name = Column(String(255), nullable=False)
    crn = Column(String(255), nullable=False)
    role = Column(Enum(*ROLES_LIST), nullable=False)
    iam_role_crn = Column(String(255), nullable=False)
    state = Column(String(255), nullable=False)
    migrated = Column(Boolean, nullable=False)
    _api_key = Column('api_key', String(500), nullable=False)
    is_hmac = Column(Boolean, nullable=False)
    _access_key_id = Column("access_key_id", String(255))
    _secret_access_key = Column("secret_access_key", String(255))
    iam_service_id_crn = Column(String(255))

    cloud_object_storage_id = Column(String(32), ForeignKey("ibm_cloud_object_storages.id", ondelete="CASCADE"))
    resource_group_id = Column(String(32), ForeignKey("ibm_resource_groups.id", ondelete="CASCADE"))

    def __init__(self, guid, created_at, name, crn, state, migrated, iam_role_crn, role=None, is_hmac=None,
                 iam_service_id_crn=None, updated_at=None, ):
        self.id = str(uuid.uuid4().hex)
        self.guid = guid
        self.created_at = created_at
        self.updated_at = updated_at
        self.name = name
        self.crn = crn
        self.role = role
        self.iam_role_crn = iam_role_crn
        self.state = state
        self.migrated = migrated
        self.is_hmac = is_hmac
        self.iam_service_id_crn = iam_service_id_crn

    @property
    def api_key(self):
        return decrypt_api_key(self._api_key)

    @api_key.setter
    def api_key(self, unencrypted_api_key):
        self._api_key = encrypt_api_key(unencrypted_api_key)

    @property
    def access_key_id(self):
        return decrypt_api_key(self._access_key_id)

    @access_key_id.setter
    def access_key_id(self, unencrypted_access_key_id):
        self._access_key_id = encrypt_api_key(unencrypted_access_key_id)

    @property
    def secret_access_key(self):
        return decrypt_api_key(self._secret_access_key)

    @secret_access_key.setter
    def secret_access_key(self, unencrypted_secret_access_key):
        self._secret_access_key = encrypt_api_key(unencrypted_secret_access_key)

    def to_json(self):
        """
        Return a JSON representation of the object
        """
        return {
            self.ID_KEY: self.id,
            self.GUID_KEY: self.guid,
            self.CREATED_AT_KEY: self.created_at,
            self.UPDATED_AT_KEY: self.updated_at,
            self.NAME_KEY: self.name,
            self.CRN_KEY: self.crn,
            self.ROLE_KEY: self.role,
            self.IAM_ROLE_CRN_KEY: self.iam_role_crn,
            self.STATE_KEY: self.state,
            self.MIGRATED_KEY: self.migrated,
            self.IS_HMAC_KEY: self.is_hmac,
            self.CREDENTIAL_KEY: {
                self.API_KEY: self.api_key,
                self.COS_HMAC_KEY: {
                    self.ACCESS_KEY_ID: self.access_key_id,
                    self.SECRET_ACCESS_KEY: self.secret_access_key,
                },
            },
            self.IAM_SERVICE_ID_CRN_KEY: self.iam_service_id_crn,
            self.CLOUD_OBJECT_STORAGE_KEY: self.cloud_object_storage.to_reference_json(),
            self.IBM_CLOUD_KEY: self.ibm_cloud.to_reference_json(),
        }

    def return_credential_role(self):
        role = self.iam_role_crn.rsplit(":")[-1]
        if role == "Reader":
            return self.ROLE_READER
        elif role == "Writer":
            return self.ROLE_WRITER
        elif role == "Manager":
            return self.ROLE_MANAGER
        elif role == "ContentReader":
            return self.ROLE_CONTENT_READER
        elif role == "ObjectWriter":
            return self.ROLE_OBJECT_WRITER
        elif role == "ObjectManager":
            return self.ROLE_OBJECT_MANAGER

    def to_reference_json(self):
        return {
            self.ID_KEY: self.id,
            self.NAME_KEY: self.name
        }

    @classmethod
    def from_ibm_json_body(cls, json_body):
        ibm_service_key = IBMServiceCredentialKey(
            guid=json_body["guid"],
            created_at=return_datetime_object(json_body["created_at"]),
            updated_at=return_datetime_object(json_body["updated_at"]),
            name=json_body["name"],
            crn=json_body["crn"],
            iam_role_crn=json_body["role"],
            state=json_body["state"],
            migrated=json_body["migrated"],
            iam_service_id_crn=json_body.get("iam_serviceid_crn")
        )
        ibm_service_key.role = ibm_service_key.return_credential_role()
        ibm_service_key.api_key = json_body["credentials"]["apikey"]
        if json_body["credentials"].get("cos_hmac_keys"):
            ibm_service_key.is_hmac = True
            ibm_service_key.access_key_id = json_body["credentials"]["cos_hmac_keys"]["access_key_id"]
            ibm_service_key.secret_access_key = json_body["credentials"]["cos_hmac_keys"]["secret_access_key"]
        else:
            ibm_service_key.is_hmac = False

        return ibm_service_key


class IBMMonitoringToken(Base):
    ID_KEY = "id"
    TOKEN_KEY = "token"
    REGION_KEY = "region"
    STATUS_KEY = "status"
    TASK_TYPE_ADD = "ADD"

    STATUS_AUTHENTICATING = "AUTHENTICATING"
    STATUS_VALID = "VALID"
    STATUS_INVALID = "INVALID"
    ALL_STATUSES = [STATUS_AUTHENTICATING, STATUS_VALID, STATUS_INVALID]

    __tablename__ = "ibm_monitoring_tokens"

    id = Column(String(32), primary_key=True)
    __token = Column('token', Text, nullable=False)
    status = Column(Enum(*ALL_STATUSES), nullable=False)

    region_id = Column(String(32), ForeignKey("ibm_regions.id", ondelete="CASCADE"))

    def __init__(self, token):
        self.id = str(uuid.uuid4().hex)
        self.token = token
        self.status = self.STATUS_AUTHENTICATING

    @property
    def token(self):
        return decrypt_api_key(self.__token)

    @token.setter
    def token(self, unencrypted_token):
        self.__token = encrypt_api_key(unencrypted_token)

    def update_token(self, obj):
        self.token = obj.token
        self.status = self.STATUS_AUTHENTICATING

    def to_json(self):
        return {
            self.ID_KEY: self.id,
            self.TOKEN_KEY: self.token,
            self.STATUS_KEY: self.status,
            self.REGION_KEY: self.ibm_region.to_reference_json()
        }


class IBMCloudSetting(Base):
    ID_KEY = "id"
    CLOUD_ID_KEY = "cloud_id"
    COST_OPTIMIZATION_ENABLED_KEY = "cost_optimization_enabled"
    COST_OPTIMIZATION_UPDATE_TIME_KEY = "cost_optimization_update_time"

    __tablename__ = "ibm_cloud_settings"

    id = Column(String(32), primary_key=True)
    cost_optimization_update_time = Column(DateTime, nullable=False)
    cost_optimization_enabled = Column(Boolean, default=False, nullable=False)
    cloud_id = Column(String(32), ForeignKey("ibm_clouds.id", ondelete="SET NULL"), nullable=True)

    def __init__(self, cost_optimization_enabled=False, cloud_id=None):
        self.id = str(uuid.uuid4().hex)
        self.cost_optimization_update_time = datetime.utcnow()
        self.cost_optimization_enabled = cost_optimization_enabled
        self.cloud_id = cloud_id

    def to_json(self):
        json_data = {
            self.ID_KEY: self.id,
            self.CLOUD_ID_KEY: self.cloud_id,
            self.COST_OPTIMIZATION_ENABLED_KEY: self.cost_optimization_enabled
        }

        return json_data

    def cost_opt_enabled(self, status: bool):
        self.cost_optimization_enabled = status
        self.cost_optimization_update_time = datetime.utcnow()
