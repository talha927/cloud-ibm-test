import uuid
from datetime import datetime

from sqlalchemy import Boolean, Column, DateTime, Enum, ForeignKey, Integer, String, Text
from sqlalchemy.orm import relationship
from sqlalchemy.schema import UniqueConstraint

from ibm.common.consts import CREATED
from ibm.common.utils import return_datetime_object
from ibm.models.base import Base
from ibm.models.ibm.mixins import IBMCloudResourceMixin, IBMRegionalResourceMixin


class IBMInstanceGroup(IBMRegionalResourceMixin, Base):
    ID_KEY = "id"
    RESOURCE_ID_KEY = "resource_id"
    CREATED_AT_KEY = "created_at"
    HREF_KEY = "href"
    CRN_KEY = "crn"
    INSTANCE_TEMPLATE_KEY = "instance_template"
    MANAGERS_KEY = "managers"
    MEMBERSHIP_COUNT_KEY = "membership_count"
    NAME_KEY = "name"
    RESOURCE_GROUP_KEY = "resource_group"
    SUBNETS_KEY = "subnets"
    UPDATED_AT_KEY = "updated_at"
    VPC_KEY = "vpc"
    APPLICATION_PORT_KEY = "application_port"
    LOAD_BALANCER_POOL_KEY = "load_balancer_pool"
    LOAD_BALANCER_KEY = "load_balancer"
    STATUS_KEY = "status"
    MEMBERSHIPS_KEY = "memberships"
    ASSOCIATED_RESOURCES_KEY = "associated_resources"

    CRZ_BACKREF_NAME = "instance_groups"

    # status consts
    STATUS_DELETING = "deleting"
    STATUS_HEALTHY = "healthy"
    STATUS_SCALING = "scaling"
    STATUS_UNHEALTHY = "unhealthy"
    ALL_STATUSES_LIST = [
        STATUS_DELETING, STATUS_HEALTHY, STATUS_SCALING, STATUS_UNHEALTHY
    ]

    __tablename__ = "ibm_instance_groups"

    id = Column(String(32), primary_key=True)
    name = Column(String(255), nullable=False)
    resource_id = Column(String(64), nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow(), nullable=False)
    href = Column(Text, nullable=False)
    crn = Column(String(255), nullable=False)
    updated_at = Column(DateTime, nullable=False)
    application_port = Column(Integer)
    membership_count = Column(Integer, nullable=False)
    status = Column(String(50), nullable=False)

    instance_template_id = Column(String(32), ForeignKey("ibm_instance_templates.id", ondelete="CASCADE"))
    resource_group_id = Column(String(32), ForeignKey("ibm_resource_groups.id", ondelete="CASCADE"))
    vpc_id = Column(String(32), ForeignKey("ibm_vpc_networks.id", ondelete="CASCADE"))
    load_balancer_pool_id = Column(String(32), ForeignKey("ibm_pools.id", ondelete="SET NULL"), nullable=True)
    load_balancer_id = Column(String(32), ForeignKey("ibm_load_balancers.id", ondelete="SET NULL"), nullable=True)

    managers = relationship("IBMInstanceGroupManager", backref="instance_group", lazy="dynamic",
                            cascade="all, delete-orphan", passive_deletes=True)
    subnets = relationship("IBMSubnet", backref="instance_group", lazy="dynamic")
    memberships = relationship("IBMInstanceGroupMembership", backref="instance_group", lazy="dynamic",
                               cascade="all, delete-orphan", passive_deletes=True)

    __table_args__ = (
        UniqueConstraint(name, "region_id", "cloud_id", name="uix_ibm_instance_group_name_region_id_cloud_id"),
    )

    def __init__(self, name, resource_id, created_at, href, crn,  updated_at, membership_count=None,
                 application_port=None, status=None):
        self.id = str(uuid.uuid4().hex)
        self.name = name
        self.resource_id = resource_id
        self.created_at = created_at
        self.href = href
        self.crn = crn
        self.updated_at = updated_at
        self.application_port = application_port
        self.membership_count = membership_count
        self.status = status

    def to_reference_json(self):
        return {
            self.ID_KEY: self.id,
            self.NAME_KEY: self.name,
        }

    def to_json(self):
        return {
            self.ID_KEY: self.id,
            self.NAME_KEY: self.name,
            self.RESOURCE_ID_KEY: self.resource_id,
            self.CREATED_AT_KEY: self.created_at,
            self.HREF_KEY: self.href,
            self.CRN_KEY: self.crn,
            self.STATUS_KEY: self.status,
            self.UPDATED_AT_KEY: self.updated_at,
            self.APPLICATION_PORT_KEY: self.application_port,
            self.MEMBERSHIP_COUNT_KEY: self.membership_count,
            self.REGION_KEY: self.region.to_reference_json(),
            self.MANAGERS_KEY: [manager.to_json() for manager in self.managers.all()],
            self.IBM_CLOUD_KEY: self.ibm_cloud.to_reference_json(),
            self.RESOURCE_GROUP_KEY: self.resource_group.to_reference_json(),
            self.MEMBERSHIPS_KEY: [membership.to_json() for membership in self.memberships.all()],
            self.ASSOCIATED_RESOURCES_KEY: {
                self.VPC_KEY: self.vpc_network.to_reference_json(),
                self.INSTANCE_TEMPLATE_KEY: self.instance_template.to_reference_json(),
                self.LOAD_BALANCER_POOL_KEY: self.ibm_pool.to_reference_json() if self.ibm_pool else {},
                self.LOAD_BALANCER_KEY: self.load_balancer.to_reference_json() if self.load_balancer else {},
                self.SUBNETS_KEY:
                    [subnet.to_reference_json() for subnet in self.subnets.all()]
            }
        }

    @classmethod
    def from_ibm_json_body(cls, json_body):
        return cls(
            name=json_body["name"],
            resource_id=json_body["id"],
            created_at=return_datetime_object(json_body["created_at"]),
            href=json_body["href"],
            crn=json_body["crn"],
            updated_at=return_datetime_object(json_body["updated_at"]),
            application_port=json_body.get("application_port"),
            status=json_body['status'],
            membership_count=json_body["membership_count"]
        )


class IBMInstanceGroupManager(IBMCloudResourceMixin, Base):
    ID_KEY = "id"
    NAME_KEY = "name"
    RESOURCE_ID_KEY = "resource_id"
    CREATED_AT_KEY = "created_at"
    HREF_KEY = "href"
    MANAGEMENT_ENABLED_KEY = "management_enabled"
    UPDATED_AT_KEY = "updated_at"
    AGGREGATION_WINDOW_KEY = "aggregation_window"
    COOLDOWN_KEY = "cooldown"
    MANAGER_TYPE_KEY = "manager_type"
    MAX_MEMBERSHIP_COUNT_KEY = "max_membership_count"
    MIN_MEMBERSHIP_COUNT_KEY = "min_membership_count"
    POLICIES_KEY = "policies"
    ACTIONS_KEY = "actions"
    INSTANCE_GROUP_KEY = "instance_group"
    STATUS_KEY = "status"

    CRZ_BACKREF_NAME = "instance_group_managers"

    # manager type consts
    MANAGER_TYPE_AUTOSCALE = "autoscale"
    MANAGER_TYPE_SCHEDULED = "scheduled"
    ALL_MANAGERS_TYPE_LIST = [
        MANAGER_TYPE_AUTOSCALE, MANAGER_TYPE_SCHEDULED
    ]

    __tablename__ = "ibm_instance_group_managers"

    id = Column(String(32), primary_key=True)
    name = Column(String(255), nullable=False)
    resource_id = Column(String(64), nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow(), nullable=False)
    href = Column(Text, nullable=False)
    management_enabled = Column(Boolean, nullable=False, default=True)
    manager_type = Column(Enum(*ALL_MANAGERS_TYPE_LIST), nullable=False)
    updated_at = Column(DateTime, nullable=False)
    status = Column(String(50), nullable=False)

    instance_group_id = Column(String(32), ForeignKey("ibm_instance_groups.id", ondelete="CASCADE"))

    policies = relationship("IBMInstanceGroupManagerPolicy", backref="instance_group_manager", lazy="dynamic",
                            cascade="all, delete-orphan", passive_deletes=True)
    actions = relationship("IBMInstanceGroupManagerAction", backref="instance_group_manager", lazy="dynamic",
                           cascade="all, delete-orphan", passive_deletes=True)
    auto_scale_prototype = \
        relationship(
            "IBMInstanceGroupManagerAutoScalePrototype", backref="instance_group_manager", cascade="all, delete-orphan",
            passive_deletes=True, uselist=False
        )

    __table_args__ = (
        UniqueConstraint(name, instance_group_id, name="uix_ibm_instance_group_manager_name_instance_group_id"),
    )

    def __init__(
            self, name, resource_id, created_at, href, management_enabled, updated_at, manager_type=None,
            status=CREATED
    ):
        self.id = str(uuid.uuid4().hex)
        self.name = name
        self.resource_id = resource_id
        self.created_at = created_at
        self.href = href
        self.management_enabled = management_enabled
        self.updated_at = updated_at
        self.manager_type = manager_type
        self.status = status

    def to_reference_json(self):
        return {
            self.ID_KEY: self.id,
            self.NAME_KEY: self.name,
            self.POLICIES_KEY: [policy.to_reference_json() for policy in self.policies.all()],
            self.ACTIONS_KEY: [action.to_reference_json() for action in self.actions.all()]
        }

    def update_from_obj(self, obj):
        self.name = obj.name
        self.management_enabled = obj.management_enabled
        self.updated_at = obj.updated_at

    def to_json(self, parent_reference=True):
        json_data = {
            self.ID_KEY: self.id,
            self.NAME_KEY: self.name,
            self.RESOURCE_ID_KEY: self.resource_id,
            self.CREATED_AT_KEY: self.created_at,
            self.HREF_KEY: self.href,
            self.MANAGEMENT_ENABLED_KEY: self.management_enabled,
            self.UPDATED_AT_KEY: self.updated_at,
            self.MANAGER_TYPE_KEY: self.manager_type,
            self.STATUS_KEY: self.status
        }

        if self.manager_type == self.MANAGER_TYPE_AUTOSCALE:
            json_data[self.AGGREGATION_WINDOW_KEY] = self.auto_scale_prototype.aggregation_window
            json_data[self.COOLDOWN_KEY] = self.auto_scale_prototype.cooldown
            json_data[self.MAX_MEMBERSHIP_COUNT_KEY] = self.auto_scale_prototype.max_membership_count
            json_data[self.MIN_MEMBERSHIP_COUNT_KEY] = self.auto_scale_prototype.min_membership_count
            json_data[self.POLICIES_KEY] = [policy.to_json(parent_reference=False) for policy in self.policies.all()]

        elif self.manager_type == self.MANAGER_TYPE_SCHEDULED:
            json_data[self.ACTIONS_KEY] = [action.to_json(parent_reference=False) for action in self.actions.all()]

        if parent_reference:
            json_data[self.INSTANCE_GROUP_KEY] = self.instance_group.to_reference_json()

        return json_data

    @classmethod
    def from_ibm_json_body(cls, json_body):
        ibm_instance_group_manager = cls(
            name=json_body["name"],
            resource_id=json_body["id"],
            created_at=return_datetime_object(json_body["created_at"]),
            href=json_body["href"],
            updated_at=return_datetime_object(json_body["updated_at"]),
            management_enabled=json_body["management_enabled"],
            manager_type=json_body["manager_type"],
        )

        if json_body["manager_type"] == IBMInstanceGroupManager.MANAGER_TYPE_AUTOSCALE:
            ibm_instance_group_manager.auto_scale_prototype = \
                IBMInstanceGroupManagerAutoScalePrototype.from_ibm_json_body(json_body=json_body)

        return ibm_instance_group_manager


class IBMInstanceGroupManagerAutoScalePrototype(Base):
    ID_KEY = "id"
    AGGREGATION_WINDOW_KEY = "aggregation_window"
    COOLDOWN_KEY = "cooldown"
    MAX_MEMBERSHIP_COUNT_KEY = "max_membership_count"
    MIN_MEMBERSHIP_COUNT_KEY = "min_membership_count"
    POLICIES_KEY = "policies"

    __tablename__ = "ibm_instance_group_manager_autoscale_prototypes"

    id = Column(String(32), primary_key=True)
    aggregation_window = Column(Integer, nullable=False)
    cooldown = Column(Integer, nullable=False)
    max_membership_count = Column(Integer, nullable=False)
    min_membership_count = Column(Integer, nullable=False)

    manager_id = Column(String(32), ForeignKey("ibm_instance_group_managers.id", ondelete="CASCADE"))

    def __init__(self, aggregation_window, cooldown, max_membership_count, min_membership_count):
        self.id = str(uuid.uuid4().hex)
        self.aggregation_window = aggregation_window
        self.cooldown = cooldown
        self.max_membership_count = max_membership_count
        self.min_membership_count = min_membership_count

    def to_json(self):
        return {
            self.ID_KEY: self.id,
            self.AGGREGATION_WINDOW_KEY: self.aggregation_window,
            self.COOLDOWN_KEY: self.cooldown,
            self.MAX_MEMBERSHIP_COUNT_KEY: self.max_membership_count,
            self.MIN_MEMBERSHIP_COUNT_KEY: self.min_membership_count,
            self.POLICIES_KEY: [policy.to_reference_json() for policy in self.policies.all()]
        }

    def update_from_obj(self, obj):
        self.aggregation_window = obj.aggregation_window
        self.cooldown = obj.cooldown
        self.max_membership_count = obj.max_membership_count
        self.min_membership_count = obj.min_membership_count

    @classmethod
    def from_ibm_json_body(cls, json_body):
        return cls(
            aggregation_window=json_body.get("aggregation_window"), cooldown=json_body.get("cooldown"),
            max_membership_count=json_body.get("max_membership_count"),
            min_membership_count=json_body.get("min_membership_count")
        )


class IBMInstanceGroupManagerAction(Base):
    ID_KEY = "id"
    NAME_KEY = "name"
    RESOURCE_ID_KEY = "resource_id"
    CREATED_AT_KEY = "created_at"
    HREF_KEY = "href"
    AUTO_DELETE_KEY = "auto_delete"
    AUTO_DELETE_TIMEOUT_KEY = "auto_delete_timeout"
    RESOURCE_TYPE_KEY = "resource_type"
    UPDATED_AT_KEY = "updated_at"
    ACTION_TYPE_KEY = "action_type"
    CRON_SPEC_KEY = "cron_spec"
    LAST_APPLIED_AT_KEY = "last_applied_at"
    NEXT_RUN_AT_KEY = "next_run_at"
    RUN_AT_KEY = "run_at"
    GROUP_MEMBERSHIP_COUNT_KEY = "group_membership_count"
    MANAGER_KEY = "manager"
    MAX_MEMBERSHIP_COUNT_KEY = "max_membership_count"
    MIN_MEMBERSHIP_COUNT_KEY = "min_membership_count"
    INSTANCE_GROUP_MANAGER_KEY = "instance_group_manager"
    STATUS_KEY = "status"

    CRZ_BACKREF_NAME = "instance_group_manager_actions"

    # resource type consts
    RESOURCE_TYPE_INSTANCE_GROUP_MANAGER_ACTION = "instance_group_manager_action"
    ALL_RESOURCE_TYPES_LIST = [
        RESOURCE_TYPE_INSTANCE_GROUP_MANAGER_ACTION
    ]
    # status consts
    STATUS_ACTIVE = "active"
    STATUS_COMPLETED = "completed"
    STATUS_FAILED = "failed"
    STATUS_INCOMPATIBLE = "incompatible"
    STATUS_OMITTED = "omitted"
    ALL_STATUSES_LIST = [
        STATUS_ACTIVE, STATUS_COMPLETED, STATUS_FAILED, STATUS_INCOMPATIBLE, STATUS_OMITTED
    ]

    # action type consts
    ACTION_TYPE_SCHEDULED = "scheduled"
    ALL_ACTION_TYPES_LIST = [
        ACTION_TYPE_SCHEDULED
    ]

    __tablename__ = "ibm_instance_group_manager_actions"

    id = Column(String(32), primary_key=True)
    name = Column(String(255), nullable=False)
    resource_id = Column(String(64), nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow(), nullable=False)
    href = Column(Text, nullable=False)
    auto_delete = Column(Boolean, nullable=False)
    auto_delete_timeout = Column(Integer, nullable=False)
    resource_type = \
        Column(Enum(*ALL_RESOURCE_TYPES_LIST), default=RESOURCE_TYPE_INSTANCE_GROUP_MANAGER_ACTION, nullable=False)
    updated_at = Column(DateTime, nullable=False)
    action_type = Column(Enum(*ALL_ACTION_TYPES_LIST), nullable=False)
    status = Column(String(50), nullable=False)
    group_membership_count = Column(Integer)  # TODO Remove this Column
    last_applied_at = Column(DateTime)
    cron_spec = Column(String(64))
    next_run_at = Column(DateTime)
    run_at = Column(DateTime)

    manager_id = Column(String(32), ForeignKey("ibm_instance_group_managers.id", ondelete="CASCADE"))

    __table_args__ = (
        UniqueConstraint(name, manager_id, name="uix_ibm_instance_group_manager_action_name_manager_id"),
    )

    def __init__(self, name, resource_id, created_at, href, auto_delete, auto_delete_timeout,
                 resource_type, updated_at, action_type, cron_spec=None, last_applied_at=None,
                 next_run_at=None, group_membership_count=None, run_at=None, status=None
                 ):
        self.id = str(uuid.uuid4().hex)
        self.name = name
        self.resource_id = resource_id
        self.created_at = created_at
        self.href = href
        self.auto_delete = auto_delete
        self.auto_delete_timeout = auto_delete_timeout
        self.resource_type = resource_type
        self.updated_at = updated_at
        self.action_type = action_type
        self.cron_spec = cron_spec
        self.last_applied_at = last_applied_at
        self.next_run_at = next_run_at
        self.group_membership_count = group_membership_count
        self.run_at = run_at
        self.status = status

    def to_reference_json(self):
        return {
            self.ID_KEY: self.id,
            self.NAME_KEY: self.name,
        }

    def update_from_obj(self, obj):
        self.auto_delete = obj.auto_delete
        self.auto_delete_timeout = obj.auto_delete_timeout
        self.resource_type = obj.resource_type
        self.status = obj.status
        self.updated_at = obj.updated_at
        self.action_type = obj.action_type
        self.cron_spec = obj.cron_spec
        self.last_applied_at = obj.last_applied_at
        self.next_run_at = obj.next_run_at
        self.run_at = obj.run_at
        self.group_membership_count = obj.group_membership_count

    def to_json(self, parent_reference=True):
        json_data = {
            self.ID_KEY: self.id,
            self.NAME_KEY: self.name,
            self.RESOURCE_ID_KEY: self.resource_id,
            self.CREATED_AT_KEY: self.created_at,
            self.HREF_KEY: self.href,
            self.AUTO_DELETE_KEY: self.auto_delete,
            self.AUTO_DELETE_TIMEOUT_KEY: self.auto_delete_timeout,
            self.RESOURCE_TYPE_KEY: self.resource_type,
            self.STATUS_KEY: self.status,
            self.UPDATED_AT_KEY: self.updated_at,
            self.ACTION_TYPE_KEY: self.action_type,
            self.CRON_SPEC_KEY: self.cron_spec,
            self.LAST_APPLIED_AT_KEY: self.last_applied_at,
            self.NEXT_RUN_AT_KEY: self.next_run_at,
            self.RUN_AT_KEY: self.run_at,
            self.GROUP_MEMBERSHIP_COUNT_KEY: self.group_membership_count,
        }

        if parent_reference:
            json_data[self.INSTANCE_GROUP_MANAGER_KEY] = self.instance_group_manager.to_reference_json()

        return json_data

    @classmethod
    def from_ibm_json_body(cls, json_body):
        return cls(
            name=json_body["name"],
            resource_id=json_body["id"],
            created_at=return_datetime_object(json_body["created_at"]),
            href=json_body["href"],
            updated_at=return_datetime_object(json_body["updated_at"]),
            auto_delete=json_body["auto_delete"],
            auto_delete_timeout=json_body["auto_delete_timeout"],
            resource_type=json_body["resource_type"],
            action_type=json_body["action_type"],
            cron_spec=json_body.get("manager_type"),
            last_applied_at=json_body.get("last_applied_at"),
            next_run_at=return_datetime_object(json_body.get("next_run_at")),
            status=json_body["status"],
            run_at=return_datetime_object(json_body.get("run_at")) if json_body.get("run_at") else None,
            group_membership_count=json_body.get("group")["membership_count"] if json_body.get(
                "group_membership_count") else None
        )


class IBMInstanceGroupManagerPolicy(Base):
    ID_KEY = "id"
    NAME_KEY = "name"
    RESOURCE_ID_KEY = "resource_id"
    CREATED_AT_KEY = "created_at"
    HREF_KEY = "href"
    UPDATED_AT_KEY = "updated_at"
    METRIC_TYPE_KEY = "metric_type"
    METRIC_VALUE_KEY = "metric_value"
    POLICY_TYPE_KEY = "policy_type"
    INSTANCE_GROUP_MANAGER_KEY = "instance_group_manager"
    STATUS_KEY = "status"

    CRZ_BACKREF_NAME = "instance_group_manager_policies"

    # metric type consts
    METRIC_TYPE_CPU = "cpu"
    METRIC_TYPE_MEMORY = "memory"
    METRIC_TYPE_NETWORK_IN = "network_in"
    METRIC_TYPE_NETWORK_OUT = "network_out"

    ALL_METRIC_TYPES_LIST = [
        METRIC_TYPE_CPU, METRIC_TYPE_MEMORY, METRIC_TYPE_NETWORK_IN, METRIC_TYPE_NETWORK_OUT
    ]

    # policy type consts
    POLICY_TYPE_TARGET = "target"
    ALL_POLICY_TYPES_LIST = [
        POLICY_TYPE_TARGET
    ]

    __tablename__ = "ibm_instance_group_manager_policies"

    id = Column(String(32), primary_key=True)
    name = Column(String(255), nullable=False)
    resource_id = Column(String(64), nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow(), nullable=False)
    href = Column(Text, nullable=False)
    updated_at = Column(DateTime, nullable=False)
    metric_type = Column(Enum(*ALL_METRIC_TYPES_LIST), nullable=False)
    metric_value = Column(Integer, nullable=False)
    policy_type = Column(Enum(*ALL_POLICY_TYPES_LIST), default=POLICY_TYPE_TARGET, nullable=False)
    status = Column(String(50), nullable=False)

    manager_id = Column(String(32), ForeignKey("ibm_instance_group_managers.id", ondelete="CASCADE"))

    __table_args__ = (
        UniqueConstraint(name, manager_id, name="uix_ibm_instance_group_manager_policy_name_manager_id"),
    )

    def __init__(
            self, name, resource_id, created_at, href, updated_at, metric_type, metric_value, policy_type,
            status=CREATED
    ):
        self.id = str(uuid.uuid4().hex)
        self.name = name
        self.resource_id = resource_id
        self.created_at = created_at
        self.href = href
        self.updated_at = updated_at
        self.metric_type = metric_type
        self.metric_value = metric_value
        self.policy_type = policy_type
        self.status = status

    def to_reference_json(self):
        return {
            self.ID_KEY: self.id,
            self.NAME_KEY: self.name,
        }

    def to_json(self, parent_reference=True):
        json_data = {
            self.ID_KEY: self.id,
            self.NAME_KEY: self.name,
            self.RESOURCE_ID_KEY: self.resource_id,
            self.CREATED_AT_KEY: self.created_at,
            self.HREF_KEY: self.href,
            self.UPDATED_AT_KEY: self.updated_at,
            self.METRIC_TYPE_KEY: self.metric_type,
            self.METRIC_VALUE_KEY: self.metric_value,
            self.POLICY_TYPE_KEY: self.policy_type,
            self.STATUS_KEY: self.status
        }

        if parent_reference:
            json_data[self.INSTANCE_GROUP_MANAGER_KEY] = self.instance_group_manager.to_reference_json()

        return json_data

    @classmethod
    def from_ibm_json_body(cls, json_body):
        return cls(
            name=json_body["name"],
            resource_id=json_body["id"],
            created_at=return_datetime_object(json_body["created_at"]),
            href=json_body["href"],
            updated_at=return_datetime_object(json_body["updated_at"]),
            metric_type=json_body["metric_type"],
            metric_value=json_body["metric_value"],
            policy_type=json_body["policy_type"],
        )


class IBMInstanceGroupMembership(Base):
    ID_KEY = "id"
    NAME_KEY = "name"
    RESOURCE_ID_KEY = "resource_id"
    CREATED_AT_KEY = "created_at"
    HREF_KEY = "href"
    DELETE_INSTANCE_ON_MEMBERSHIP_DELETE_KEY = "delete_instance_on_membership_delete"
    INSTANCE_KEY = "instance"
    INSTANCE_TEMPLATE_KEY = "instance_template"
    UPDATED_AT_KEY = "updated_at"
    POOL_MEMBER_KEY = "pool_member"
    STATUS_KEY = "status"
    INSTANCE_GROUP_ID_KEY = "instance_group_id"
    INSTANCE_ID_KEY = "instance_id"
    INSTANCE_TEMPLATE_ID_KEY = "instance_template_id"
    POOL_MEMBER_ID_KEY = "pool_member_id"

    CRZ_BACKREF_NAME = "instance_group_memberships"
    # status consts
    STATUS_DELETING = "deleting"
    STATUS_FAILED = "failed"
    STATUS_HEALTHY = "healthy"
    STATUS_PENDING = "pending"
    STATUS_UNHEALTHY = "unhealthy"

    ALL_STATUSES_LIST = [
        STATUS_DELETING, STATUS_FAILED, STATUS_HEALTHY, STATUS_PENDING, STATUS_UNHEALTHY
    ]

    __tablename__ = "ibm_instance_group_memberships"

    id = Column(String(32), primary_key=True)
    name = Column(String(255), nullable=False)
    resource_id = Column(String(64), nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow(), nullable=False)
    href = Column(Text, nullable=False)
    delete_instance_on_membership_delete = Column(Boolean, nullable=False)
    updated_at = Column(DateTime, nullable=False)
    status = Column(String(50), nullable=False)

    instance_group_id = Column(String(32), ForeignKey("ibm_instance_groups.id", ondelete="CASCADE"))
    instance_id = Column(String(32), ForeignKey("ibm_instances.id", ondelete="CASCADE"))
    instance_template_id = Column(String(32), ForeignKey("ibm_instance_templates.id", ondelete="CASCADE"))
    pool_member_id = Column(String(32), ForeignKey("ibm_pool_members.id", ondelete="SET NULL"), nullable=True)

    __table_args__ = (
        UniqueConstraint(name, instance_group_id, name="uix_ibm_instance_group_membership_name_instance_group_id"),
    )

    def __init__(
            self, name, resource_id, created_at, href, delete_instance_on_membership_delete,
            updated_at, status=None
    ):
        self.id = str(uuid.uuid4().hex)
        self.name = name
        self.resource_id = resource_id
        self.created_at = created_at
        self.href = href
        self.delete_instance_on_membership_delete = delete_instance_on_membership_delete
        self.updated_at = updated_at
        self.status = status

    def to_reference_json(self):
        return {
            self.ID_KEY: self.id,
            self.NAME_KEY: self.name,
        }

    def to_json(self, parent_reference=True):
        json_data = {
            self.ID_KEY: self.id,
            self.NAME_KEY: self.name,
            self.RESOURCE_ID_KEY: self.resource_id,
            self.CREATED_AT_KEY: self.created_at,
            self.HREF_KEY: self.href,
            self.DELETE_INSTANCE_ON_MEMBERSHIP_DELETE_KEY: self.delete_instance_on_membership_delete,
            self.STATUS_KEY: self.status,
            self.UPDATED_AT_KEY: self.updated_at,
            self.INSTANCE_KEY: self.instances.to_reference_json() if self.instances else {},
            self.INSTANCE_TEMPLATE_KEY: self.instance_template.to_reference_json() if self.instance_template else {},
            self.POOL_MEMBER_ID_KEY: self.pool_member.to_reference_json() if self.pool_member else {},
        }

        if parent_reference:
            json_data[self.INSTANCE_GROUP_ID_KEY] = self.instance_group.to_reference_json()

        return json_data

    @classmethod
    def from_ibm_json_body(cls, json_body):
        ibm_instance_group_manager = cls(
            name=json_body["name"],
            resource_id=json_body["id"],
            created_at=return_datetime_object(json_body["created_at"]),
            href=json_body["href"],
            updated_at=return_datetime_object(json_body["updated_at"]),
            delete_instance_on_membership_delete=json_body["delete_instance_on_membership_delete"],
            status=json_body["status"],
        )
        return ibm_instance_group_manager
