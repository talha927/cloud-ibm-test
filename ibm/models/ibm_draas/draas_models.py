import uuid
from datetime import datetime

from sqlalchemy import Boolean, Column, DateTime, Enum, ForeignKey, JSON, String, TEXT, Integer
from sqlalchemy.orm import deferred, relationship

from ibm.models.base import Base
from ibm.models.ibm.mixins import IBMCloudResourceMixin


class DisasterRecoveryResourceBlueprint(IBMCloudResourceMixin, Base):
    ID_KEY = "id"
    NAME_KEY = "name"
    DESCRIPTION_KEY = "description"
    RESOURCE_TYPE_KEY = "resource_type"
    RESOURCE_ID_KEY = "resource_id"
    BACKUPS_KEY = "backups"
    CREATED_AT_KEY = "created_at"
    RESOURCE_METADATA_KEY = "resource_metadata"
    CRZ_BACKREF_NAME = "disaster_recovery_resource_blueprints"

    RESOURCE_TYPE_KUBERNETES_CLUSTER = "IBMKubernetesCluster"
    RESOURCE_TYPE_VPC_NETWORK = "IBMVpcNetwork"
    RESOURCE_TYPES_LIST = [RESOURCE_TYPE_KUBERNETES_CLUSTER, RESOURCE_TYPE_VPC_NETWORK]

    # Scheduled policy states
    SCHEDULED_POLICY_ACTIVE_STATE = "ACTIVE"
    SCHEDULED_POLICY_INACTIVE_STATE = "INACTIVE"
    SCHEDULED_POLICY_STATES = [SCHEDULED_POLICY_ACTIVE_STATE, SCHEDULED_POLICY_INACTIVE_STATE]

    __tablename__ = "disaster_recovery_resource_blueprints"

    id = Column(String(32), primary_key=True)
    name = Column(String(255), nullable=False)
    description = Column(TEXT, nullable=True)
    resource_type = Column(String(255), nullable=False)
    resource_id = Column(String(64), nullable=False)
    resource_metadata = deferred(Column(JSON, nullable=False))
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    scheduled_policy_state = Column(Enum(*SCHEDULED_POLICY_STATES), default=SCHEDULED_POLICY_INACTIVE_STATE,
                                    nullable=False)
    last_backup_taken_at = Column(DateTime)
    next_backup_scheduled_at = Column(DateTime)
    user_id = Column(String(32), nullable=False)

    draas_scheduled_policy_id = Column(String(32), ForeignKey("disaster_recovery_scheduled_policies.id",
                                                              ondelete="SET NULL"), nullable=True)

    backups = relationship(
        "DisasterRecoveryBackup",
        backref="disaster_recovery_resource_blueprint",
        cascade="all, delete-orphan",
        passive_deletes=True,
        lazy="dynamic"
    )

    def __init__(self, resource_id, name, resource_type, user_id, next_backup_scheduled_at=None, description=None,
                 last_backup_taken_at=None, resource_metadata=None, scheduled_policy_state=None):
        super().__init__()
        self.id = str(uuid.uuid4().hex)
        self.resource_id = resource_id
        self.name = name
        self.scheduled_policy_state = \
            scheduled_policy_state or DisasterRecoveryResourceBlueprint.SCHEDULED_POLICY_INACTIVE_STATE
        self.resource_type = resource_type
        self.user_id = user_id
        self.description = description
        self.next_backup_scheduled_at = next_backup_scheduled_at
        self.last_backup_taken_at = last_backup_taken_at
        self.resource_metadata = resource_metadata or {}

    def to_json(self, data=False):
        return {
            self.ID_KEY: self.id,
            self.NAME_KEY: self.name,
            self.DESCRIPTION_KEY: self.description,
            self.RESOURCE_TYPE_KEY: self.resource_type,
            self.RESOURCE_ID_KEY: self.resource_id,
            self.RESOURCE_METADATA_KEY: self.resource_metadata if data else {},
            self.CREATED_AT_KEY: self.created_at,
            self.BACKUPS_KEY: [backup.to_json() for backup in self.backups.all()] if data else [],
            self.IBM_CLOUD_KEY: self.ibm_cloud.to_reference_json()
        }

    def to_reference_json(self):
        return {
            self.ID_KEY: self.id,
            self.NAME_KEY: self.name
        }


class DisasterRecoveryBackup(Base):
    ID_KEY = "id"
    NAME_KEY = "name"
    STARTED_AT_KEY = "started_at"
    COMPLETED_AT_KEY = "completed_at"
    SCHEDULE_KEY = "scheduled"
    BACKUP_METADATA_KEY = "backup_metadata"
    ASSOCIATED_RESOURCES_KEY = "associated_resources"
    STATUS_KEY = "status"
    DRAAS_BLUEPRINT_KEY = "draas_blueprint"
    IS_VOLUME_KEY = "is_volume"

    # backup states
    DELETING = "DELETING"
    SUCCESS = "SUCCESS"
    DRAAS_BACKUP_STATUSES_LIST = [DELETING, SUCCESS]

    __tablename__ = "disaster_recovery_backups"

    id = Column(String(32), primary_key=True)
    status = Column(Enum(*DRAAS_BACKUP_STATUSES_LIST), default=SUCCESS, nullable=False)
    name = Column(String(255), nullable=False)
    started_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    completed_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    scheduled = Column(Boolean, nullable=False)
    backup_metadata = deferred(Column(JSON, nullable=False))
    is_volume = Column(Boolean, default=False)

    disaster_recovery_resource_blueprint_id = Column(String(32), ForeignKey("disaster_recovery_resource_blueprints.id",
                                                                            ondelete="CASCADE"))

    def __init__(self, name, backup_metadata, is_volume=False, started_at=None, scheduled=False):
        self.id = str(uuid.uuid4().hex)
        self.name = name
        self.backup_metadata = backup_metadata
        self.started_at = started_at or datetime.utcnow()
        self.scheduled = scheduled
        self.is_volume = is_volume

    def to_json(self):
        json_dict = {
            self.ID_KEY: self.id,
            self.NAME_KEY: self.name,
            self.STATUS_KEY: self.status,
            self.BACKUP_METADATA_KEY: self.backup_metadata,
            self.DRAAS_BLUEPRINT_KEY: self.disaster_recovery_resource_blueprint.to_reference_json(),
            self.STARTED_AT_KEY: self.started_at,
            self.COMPLETED_AT_KEY: self.completed_at,
            self.SCHEDULE_KEY: self.scheduled,
            self.IS_VOLUME_KEY: self.is_volume
        }

        if self.backup_metadata.get("associated_resources"):
            json_dict[self.BACKUP_METADATA_KEY] = self.backup_metadata["associated_resources"]

        return json_dict


class DisasterRecoveryScheduledPolicy(IBMCloudResourceMixin, Base):
    ID_KEY = "id"
    BACKUP_COUNT_KEY = "backup_count"
    DESCRIPTION_KEY = "description"
    DISASTER_RECOVERY_RESOURCE_BLUEPRINTS = "disaster_recovery_resource_blueprints"
    SCHEDULED_CRON_PATTERN_KEY = "scheduled_cron_pattern"

    CRZ_BACKREF_NAME = "disaster_recovery_scheduled_policies"
    __tablename__ = "disaster_recovery_scheduled_policies"

    id = Column(String(32), primary_key=True)
    backup_count = Column(Integer, default=1, nullable=False)
    scheduled_cron_pattern = Column(String(150))
    description = Column(TEXT)

    draas_resource_blueprints = relationship(
        "DisasterRecoveryResourceBlueprint", backref="disaster_recovery_scheduled_policy", lazy="dynamic")

    def __init__(self, scheduled_cron_pattern, backup_count=None, description=None):
        self.id = str(uuid.uuid4().hex)
        self.backup_count = backup_count or 1
        self.scheduled_cron_pattern = scheduled_cron_pattern
        self.description = description or ""

    def to_json(self):
        return {
            self.ID_KEY: self.id,
            self.BACKUP_COUNT_KEY: self.backup_count,
            self.DESCRIPTION_KEY: self.description,
            self.DISASTER_RECOVERY_RESOURCE_BLUEPRINTS: [draas_resource_blueprint.to_reference_json() for
                                                         draas_resource_blueprint in self.draas_resource_blueprints],
            self.SCHEDULED_CRON_PATTERN_KEY: self.scheduled_cron_pattern
        }
