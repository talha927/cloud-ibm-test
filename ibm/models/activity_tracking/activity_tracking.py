import logging
import uuid
from datetime import datetime
from ibm.web import db as ibmdb
from sqlalchemy import Column, DateTime, JSON, String

from ibm.models.base import Base
from ibm.models.ibm.mixins import IBMCloudResourceMixin

LOGGER = logging.getLogger(__name__)


class IBMActivityTracking(IBMCloudResourceMixin, Base):
    ID_KEY = 'id'
    USER_KEY = "user"
    PROJECT_ID_KEY = "project_id"
    RESOURCE_NAME_KEY = 'resource_name'
    RESOURCE_TYPE_KEY = 'resource_type'
    ACTIVITY_TYPE_KEY = 'activity_type'
    STARTED_AT_KEY = 'started_at'
    SUMMARY_KEY = 'summary'
    DETAILED_SUMMARY_KEY = 'detailed_summary'
    ROOT_ID_KEY = "root_id"

    # Activity types
    CREATION = "creation"
    DELETION = "deletion"
    DISABLED_COST = "disabled cost"
    ENABLED_COST = "enabled cost"
    BACKUP = "backup"
    RESTORE = "restore"
    STOP = "stop"
    START = "start"
    ALL_ACTIVITY_TYPES = [CREATION, DELETION, DISABLED_COST, ENABLED_COST, BACKUP, RESTORE, STOP, START]

    # Resource Types
    VPCS_KEY = "vpcs"
    SUBNETS_KEY = "subnets"
    SECURITY_GROUPS_KEY = "security_groups"
    INSTANCES_KEY = "instances"
    KUBERNETES_CLUSTERS = "kubernetes_clusters"
    IMAGES = "images"
    NETWORK_ACLS = "network_acls"
    VPN_GATEWAYS = "vpn_gateways"
    LOAD_BALANCERS = "load_balancers"
    SSH_KEYS = "ssh_keys"
    ADDRESS_PREFIXES = "address_prefixes"
    PUBLIC_GATEWAYS = "public_gateways"
    ROUTING_TABLES = "routing_tables"
    PLACEMENT_GROUPS = "placement_groups"
    ENDPOINT_GATEWAYS = "endpoint_gateways"
    DEDICATED_HOSTS = "dedicated_hosts"
    INSTANCE_GROUPS = "instance_groups"
    ALL_RESOURCES = [VPCS_KEY, SUBNETS_KEY, SECURITY_GROUPS_KEY, INSTANCES_KEY, KUBERNETES_CLUSTERS,
                     IMAGES, NETWORK_ACLS, VPN_GATEWAYS, LOAD_BALANCERS, SSH_KEYS, ADDRESS_PREFIXES,
                     PUBLIC_GATEWAYS, ROUTING_TABLES, PLACEMENT_GROUPS, ENDPOINT_GATEWAYS, DEDICATED_HOSTS,
                     INSTANCE_GROUPS]

    CRZ_BACKREF_NAME = "ibm_activity_tracking"

    __tablename__ = "ibm_activity_tracking"

    id = Column(String(32), primary_key=True)
    user = Column(String(64), nullable=False)
    project_id = Column(String(32), nullable=False)
    resource_name = Column(String(64), nullable=False)
    resource_type = Column(String(128), nullable=False)
    activity_type = Column(String(64), nullable=False)
    started_at = Column(DateTime, default=datetime.utcnow(), nullable=False)
    summary = Column(String(256), nullable=False)
    _detailed_summary = Column(JSON)
    root_id = Column(String(32), nullable=False)

    def __init__(self, user, project_id, resource_name, resource_type, activity_type, summary, root_id):
        self.id = str(uuid.uuid4().hex)
        self.started_at = datetime.utcnow()
        self.user = user
        self.project_id = project_id
        self.resource_name = resource_name
        self.resource_type = resource_type
        self.activity_type = activity_type
        self.summary = summary
        self.root_id = root_id

    @property
    def detailed_summary(self):
        return self._detailed_summary

    @detailed_summary.setter
    def detailed_summary(self, root):
        from ibm.models import WorkflowRoot, WorkflowsWorkspace
        if isinstance(root, str):      # if root is root_id
            root_obj = ibmdb.session.query(WorkflowRoot).filter_by(id=root).first()
            if root_obj:
                self._detailed_summary = root_obj.to_json()
                ibmdb.session.commit()
            else:
                workspace_obj = ibmdb.session.query(WorkflowsWorkspace).filter_by(id=root).first()
                if workspace_obj:
                    json = workspace_obj.to_json()
                    self._detailed_summary = {"id": json["id"],
                                              "name": json["name"],
                                              "status": json["status"]}
        if isinstance(root, dict):     # if root is root_json
            self._detailed_summary = root

    def update_db(self, obj):
        self.user = obj.user
        self.project_id = obj.project_id
        self.resource_name = obj.resource_name
        self.resource_type = obj.resource_type
        self.activity_type = obj.activity_type
        self.started_at = obj.started_at
        self.summary = obj.summary
        self.detailed_summary = obj.detailed_summary
        self.root_id = obj.root_id

    def to_json(self):
        return {
            self.ID_KEY: self.id,
            self.USER_KEY: self.user,
            self.PROJECT_ID_KEY: self.project_id,
            self.RESOURCE_NAME_KEY: self.resource_name,
            self.RESOURCE_TYPE_KEY: self.resource_type,
            self.ACTIVITY_TYPE_KEY: self.activity_type,
            self.STARTED_AT_KEY: self.started_at,
            self.SUMMARY_KEY: self.summary,
            self.DETAILED_SUMMARY_KEY: self.detailed_summary,
            self.ROOT_ID_KEY: self.root_id
        }
