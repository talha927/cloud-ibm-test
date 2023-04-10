"""
This file hosts models for generic tasks tied to resources which run the whole flow
"""
import uuid
from datetime import datetime

from sqlalchemy import Boolean, cast, Column, DateTime, Enum, ForeignKey, JSON, String, Table, type_coerce
from sqlalchemy.ext.hybrid import hybrid_property
from sqlalchemy.orm import backref, deferred, relationship

from ibm.common.billing_utils import log_resource_billing_in_db
from ibm.models.base import Base

workflow_tree_mappings = Table(
    'workflow_tree_mappings', Base.metadata,
    Column("task_id", String(32), ForeignKey("workflow_tasks.id", ondelete="CASCADE")),
    Column("next_task_id", String(32), ForeignKey("workflow_tasks.id", ondelete="CASCADE")),
)

workspace_tree_mappings = Table(
    'workspace_tree_mappings', Base.metadata,
    Column("root_id", String(32), ForeignKey("workflow_roots.id", ondelete="CASCADE")),
    Column("next_root_id", String(32), ForeignKey("workflow_roots.id", ondelete="CASCADE")),
)


class WorkflowsWorkspace(Base):
    """
    This database model holds information for a workspace
    """
    __tablename__ = 'workflows_workspaces'

    ID_KEY = "id"
    NAME_KEY = "name"
    FE_REQUEST_DATA_KEY = "fe_request_data"
    STATUS_KEY = "status"
    CREATED_AT_KEY = "created_at"
    IS_CREATED_KEY = "is_created"
    COMPLETED_AT_KEY = "completed_at"
    RECENTLY_PROVISIONED_ROOTS_KEY = "recently_provisioned_roots"
    ASSOCIATED_ROOTS_KEY = "associated_roots"

    TYPE_KEY = "workspace_type"
    TYPE_SOFTLAYER = "TYPE_SOFTLAYER"
    TYPE_TRANSLATION = "TYPE_TRANSLATION"
    TYPE_RESTORE = "TYPE_RESTORE"
    ALL_WORKSPACE_TYPES = [TYPE_SOFTLAYER, TYPE_TRANSLATION, TYPE_RESTORE]

    SOURCE_CLOUD_KEY = "source_cloud"
    AWS = "AWS"
    IBM = "IBM"
    GCP = "GCP"
    AZURE = "AZURE"
    SOFTLAYER = "SOFTLAYER"
    ON_PREM = "ON_PREM"
    ALL_CLOUDS = [AWS, IBM, SOFTLAYER, GCP, AZURE, ON_PREM]

    # This is the initial status of the Workspace when it is CREATED
    STATUS_ON_HOLD = "ON_HOLD"
    # This is the initial status of the Workspace ready to be picked up
    STATUS_PENDING = "PENDING"
    # The workspace has been initiated, but is not yet picked up by any worker
    STATUS_INITIATED = "INITIATED"
    # At least one of the roots in this workspace is running
    STATUS_RUNNING = "RUNNING"
    # Some roots in the tree were successful but some are still ON_HOLD
    STATUS_ON_HOLD_WITH_SUCCESS = "ON_HOLD_WITH_SUCCESS"
    # Some roots in the workspace were failure but some are still ON_HOLD
    STATUS_ON_HOLD_WITH_FAILURE = "ON_HOLD_WITH_FAILURE"
    # All the roots in the workspace were successful
    STATUS_C_SUCCESSFULLY = "COMPLETED_SUCCESSFULLY"
    # One or more of the roots in the workspace failed
    STATUS_C_W_FAILURE = "COMPLETED_WITH_FAILURE"

    ALL_STATUSES_LIST = [
        STATUS_ON_HOLD, STATUS_PENDING, STATUS_INITIATED, STATUS_RUNNING, STATUS_ON_HOLD_WITH_SUCCESS,
        STATUS_ON_HOLD_WITH_FAILURE, STATUS_C_SUCCESSFULLY, STATUS_C_W_FAILURE
    ]

    DELETION_NOT_ALLOWED_STATUSES = [STATUS_PENDING, STATUS_RUNNING, STATUS_INITIATED]

    id = Column(String(32), primary_key=True)
    name = Column(String(512), nullable=False)
    workspace_type = Column(Enum(*ALL_WORKSPACE_TYPES), nullable=True)
    fe_request_data = deferred(Column(JSON))
    recently_provisioned_roots = Column(JSON)
    user_id = Column(String(32), nullable=False)
    project_id = Column(String(32), nullable=False)
    source_cloud = Column(Enum(*ALL_CLOUDS), nullable=True)
    # DO NOT ACCESS STATUS DIRECTLY
    __status = Column("status", Enum(*ALL_STATUSES_LIST), default=STATUS_ON_HOLD, nullable=False)
    __state = Column("state", Enum(*ALL_STATUSES_LIST), default=STATUS_PENDING, nullable=False)
    executor_running = Column(Boolean, default=False, nullable=False)

    created_at = Column(DateTime, nullable=True)
    # The difference shows time it took for the root to be picked up by a worker
    started_at = Column(DateTime)
    # The difference shows time it took for the root to complete execution
    completed_at = Column(DateTime)

    associated_roots = relationship(
        'WorkflowRoot', backref="workflow_workspace", cascade="all, delete-orphan", passive_deletes=True, lazy='dynamic'
    )

    def __init__(self, name, user_id, project_id, fe_request_data=None, sketch=False, source_cloud=None,
                 workspace_type=None):
        self.id = str(uuid.uuid4().hex)
        self.name = name
        self.fe_request_data = fe_request_data
        self.user_id = user_id
        self.project_id = project_id
        self.created_at = datetime.utcnow() if not sketch else None
        self.source_cloud = source_cloud
        self.workspace_type = workspace_type

    def add_next_root(self, next_root, status=None):
        """
        Add a root to the first group of roots for the workspace
        :param next_root:
        :param status:
        :return:
        """
        assert isinstance(next_root, WorkflowRoot)
        next_root.status = status or WorkflowRoot.STATUS_ON_HOLD
        self.associated_roots.append(next_root)

    @hybrid_property
    def status(self):
        """
        Hybrid property (you can query on this) for status getter
        :return:
        """
        return self.__status

    @status.setter
    def status(self, new_status):
        """
        Hybrid property (you can query on this) for status setter
        :param new_status: <string> status to be set
        """

        if new_status == self.STATUS_PENDING:
            self.created_at = datetime.utcnow()
        elif new_status == self.STATUS_RUNNING:
            self.started_at = datetime.utcnow()
        elif new_status in [self.STATUS_C_SUCCESSFULLY, self.STATUS_C_W_FAILURE]:
            self.completed_at = datetime.utcnow()

        self.__status = new_status

    @property
    def is_created(self):
        return bool(self.created_at)

    @property
    def next_roots(self):
        """
        Property to get next (first group) roots of the workspace task
        :return:
        """
        return self.associated_roots.filter(~WorkflowRoot._previous_roots.any())

    @property
    def deletable(self):
        return self.status not in self.DELETION_NOT_ALLOWED_STATUSES

    @property
    def in_focus_roots(self):
        """
        Property to get roots which are in focus right now (running, failed, completed but not acknowledged, failed but
        not acknowledged)
        :return:
        """
        return self.associated_roots.filter(WorkflowRoot.in_focus).all()

    def get_workflow_root(self, root_id):
        return self.associated_roots.filter(
            cast(WorkflowRoot.fe_request_data["id"], String) == type_coerce(root_id, JSON)).first()

    def to_reference_json(self):
        return {
            self.ID_KEY: self.id,
            self.NAME_KEY: self.name,
            self.STATUS_KEY: self.status,
            self.IS_CREATED_KEY: self.is_created,
            self.RECENTLY_PROVISIONED_ROOTS_KEY: self.recently_provisioned_roots
        }

    def to_json(self, metadata=False):
        resp = {
            self.ID_KEY: self.id,
            self.NAME_KEY: self.name,
            self.FE_REQUEST_DATA_KEY: self.fe_request_data,
            self.STATUS_KEY: self.status,
            self.CREATED_AT_KEY: self.created_at,
            self.IS_CREATED_KEY: self.is_created,
            self.COMPLETED_AT_KEY: self.completed_at,
            self.SOURCE_CLOUD_KEY: self.source_cloud,
            self.TYPE_KEY: self.workspace_type,
            self.RECENTLY_PROVISIONED_ROOTS_KEY: self.recently_provisioned_roots,
            self.ASSOCIATED_ROOTS_KEY: [root.to_json() for root in self.associated_roots.all()]
        }

        if not metadata:
            resp[self.ASSOCIATED_ROOTS_KEY] = [root.to_json() for root in self.associated_roots.all()]

        return resp


class WorkflowRoot(Base):
    """
    This database model holds the information for the root of the workflow tree
    """
    __tablename__ = 'workflow_roots'

    ID_KEY = "id"
    STATUS_KEY = "status"
    ASSOCIATED_TASKS_KEY = "associated_tasks"
    WORKFLOW_NAME_KEY = "workflow_name"
    RESOURCE_TYPE_KEY = "resource_type"
    WORKFLOW_NATURE_KEY = "workflow_nature"
    FE_REQUEST_DATA_KEY = "fe_request_data"
    CREATED_AT_KEY = "created_at"
    COMPLETED_AT_KEY = "completed_at"
    NEXT_ROOT_IDS_KEY = "next_root_ids"
    PREVIOUS_ROOT_IDS_KEY = "previous_root_ids"

    # This is the status of a CALLBACK ROOT when it is CREATED
    STATUS_ON_HOLD = "ON_HOLD"
    # This is the status of a CALLBACK ROOT ready to be picked up (in case of Workspace) by a worker
    STATUS_READY = "READY"
    # This is the status of a CALLBACK ROOT ready to be picked up by a worker
    STATUS_PENDING = "PENDING"
    # The task has been initiated, but is not yet picked up by any worker
    STATUS_INITIATED = "INITIATED"
    # At least one of the tasks in this tree is running
    STATUS_RUNNING = "RUNNING"
    # Some roots in the tree were successful but some are still ON_HOLD
    STATUS_ON_HOLD_WITH_SUCCESS = "ON_HOLD_WITH_SUCCESS"
    # Some roots in the workspace were failure but some are still ON_HOLD
    STATUS_ON_HOLD_WITH_FAILURE = "ON_HOLD_WITH_FAILURE"

    # All the tasks in the tree were successful
    STATUS_C_SUCCESSFULLY = "COMPLETED_SUCCESSFULLY"
    # All the tasks in the tree were successful and the root itself is complete but is waiting for status holding
    #  callbacks to finish (WFC = Waiting for Callbacks)
    STATUS_C_SUCCESSFULLY_WFC = "COMPLETED_SUCCESSFULLY_WFC"
    # One or more of the tasks in the tree failed
    STATUS_C_W_FAILURE = "COMPLETED_WITH_FAILURE"
    # One or more of the tasks in the tree failed and the root itself is complete but is waiting for status holding
    #  callacks to finish (WFC = Waiting for Callbacks)
    STATUS_C_W_FAILURE_WFC = "COMPLETED_WITH_FAILURE_WFC"

    STATUSES_NOT_ALLOWED_FOR_PROVISIONING = [STATUS_RUNNING, STATUS_C_SUCCESSFULLY]

    ALL_STATUSES_LIST = [
        STATUS_ON_HOLD, STATUS_READY, STATUS_PENDING, STATUS_INITIATED, STATUS_RUNNING, STATUS_C_SUCCESSFULLY,
        STATUS_C_SUCCESSFULLY_WFC, STATUS_C_W_FAILURE, STATUS_C_W_FAILURE_WFC, STATUS_ON_HOLD_WITH_FAILURE,
        STATUS_ON_HOLD_WITH_SUCCESS
    ]

    ROOT_TYPE_NORMAL = "NORMAL"
    ROOT_TYPE_ON_SUCCESS = "ON_SUCCESS"
    ROOT_TYPE_ON_FAILURE = "ON_FAILURE"
    ROOT_TYPE_ON_COMPLETE = "ON_COMPLETE"
    ALL_ROOT_TYPES = \
        [ROOT_TYPE_NORMAL, ROOT_TYPE_ON_SUCCESS, ROOT_TYPE_ON_FAILURE, ROOT_TYPE_ON_COMPLETE]

    id = Column(String(32), primary_key=True)
    # DO NOT ACCESS STATUS DIRECTLY
    __status = Column("status", Enum(*ALL_STATUSES_LIST), default=STATUS_PENDING, nullable=False)
    # Any custom name that you would want to give to a task
    workflow_name = Column(String(128))
    root_type = Column(Enum(*ALL_ROOT_TYPES), default=ROOT_TYPE_NORMAL)
    # What is the overall tree doing? CREATE/DELETE/UPDATE
    workflow_nature = Column(String(128))
    # If the root was initiated from an API, store the request data in this column
    fe_request_data = deferred(Column(JSON))
    # This is internal to the Workflow Controller logic, lets forget about this for now
    executor_running = Column(Boolean, default=False, nullable=False)
    in_focus = Column(Boolean, default=False, nullable=False)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow())
    # The difference shows time it took for this task to be initiated by workflow_manger
    initiated_at = Column(DateTime)
    # The difference shows time it took for the first task to be initiated by workflow executor
    started_at = Column(DateTime)
    # The difference shows time it took for the whole tree to execute
    completed_at = Column(DateTime)
    user_id = Column(String(32), nullable=False)
    project_id = Column(String(32), nullable=False)
    # to_json() of the parent root at the time its callback task was initiated
    __parent_root_copy = deferred(Column('parent_root_copy', JSON))
    # Whether or not the parent root should update its status to COMPLETED_SUCCESSFULY/COMPLETED_WITH_FAILURE before
    #  this task is completed
    hold_parent_status_update = Column(Boolean, default=False)

    parent_root_id = Column(String(32), ForeignKey('workflow_roots.id', ondelete="SET NULL"), nullable=True)
    workflows_workspace_id = Column(String(32), ForeignKey('workflows_workspaces.id', ondelete="SET NULL"),
                                    nullable=True)

    associated_tasks = relationship('WorkflowTask', backref="root", cascade="all, delete-orphan", passive_deletes=True,
                                    lazy='dynamic')
    # DO NOT append directly to this relation. Use add_callback_root func
    callback_roots = relationship('WorkflowRoot', backref=backref("parent_root", remote_side=[id]), lazy='dynamic')
    _next_roots = relationship(
        'WorkflowRoot',
        secondary=workspace_tree_mappings,
        primaryjoin=id == workspace_tree_mappings.c.root_id,
        secondaryjoin=id == workspace_tree_mappings.c.next_root_id,
        backref=backref('_previous_roots', lazy='dynamic'),
        lazy='dynamic'
    )

    def __init__(
            self, user_id, project_id, workflow_name=None, workflow_nature=None, fe_request_data=None,
            root_type=ROOT_TYPE_NORMAL
    ):
        self.id = str(uuid.uuid4().hex)
        self.created_at = datetime.utcnow()
        self.root_type = root_type or self.ROOT_TYPE_NORMAL
        self.status = self.STATUS_PENDING if self.root_type == self.ROOT_TYPE_NORMAL else self.STATUS_ON_HOLD
        self.workflow_name = workflow_name
        self.workflow_nature = workflow_nature
        self.fe_request_data = fe_request_data
        self.user_id = user_id
        self.project_id = project_id

    def add_next_root(self, next_root):
        """
        Add subsequent root
        :param next_root: <object of WorkflowRoot> Root that should run if this root is successful
        """
        assert isinstance(next_root, WorkflowRoot)
        if not self.workflow_workspace:
            raise ValueError("Invalid operation add_next_root, {} does not have workflow_workspace".format(self.id))

        next_root.workflow_workspace = self.workflow_workspace
        next_root.status = WorkflowRoot.STATUS_ON_HOLD
        self._next_roots.append(next_root)

    def add_next_task(self, next_task):
        """
        Add a task to the first group of tasks for the workflow
        :param next_task:
        :return:
        """
        assert isinstance(next_task, WorkflowTask)
        self.associated_tasks.append(next_task)

    def add_callback_root(self, callback_root, hold_parent_status_update=False):
        """
        Add a callback workflow for the root
        :param callback_root: <Object: WorkflowRoot> The callback root
        :param hold_parent_status_update: <bool> Whether or not the parent should wait for the callback task to complete
                                          before updating its status
        :return:
        """
        # assert self.root_type == self.ROOT_TYPE_NORMAL
        assert callback_root.root_type in [
            self.ROOT_TYPE_ON_SUCCESS, self.ROOT_TYPE_ON_FAILURE, self.ROOT_TYPE_ON_COMPLETE
        ]
        callback_root.hold_parent_status_update = hold_parent_status_update
        self.callback_roots.append(callback_root)

    @property
    def parent_root_copy(self):
        return self.__parent_root_copy

    def __generate_parent_root_copy(self):
        self.__parent_root_copy = self.parent_root.to_json()

    @property
    def status_holding_callbacks_count(self):
        """
        Returns the number of callback roots that will block the status update to COMPLETED_SUCCESSFULLY or
        COMPLETED_WITH_FAILURE
        :return: <int> number of status holding callbacks
        """
        if self.root_type != WorkflowRoot.ROOT_TYPE_NORMAL:
            return 0

        return self.callback_roots.filter(
            WorkflowRoot.hold_parent_status_update,
            WorkflowRoot.status.in_(
                {
                    WorkflowRoot.STATUS_ON_HOLD,
                    WorkflowRoot.STATUS_PENDING,
                    WorkflowRoot.STATUS_INITIATED,
                    WorkflowRoot.STATUS_RUNNING
                }
            )
        ).count()

    @hybrid_property
    def status(self):
        """
        Hybrid property (you can query on this) for status getter
        :return:
        """
        return self.__status

    @hybrid_property
    def workspace(self):
        """
        Hybrid property (you can query on this) for workspace getter
        :return:
        """
        return bool(self.workflows_workspace_id)

    @status.setter
    def status(self, new_status):
        """
        Hybrid property (you can query on this) for status setter
        :param new_status: <string> status to be set
        """
        if new_status in [self.STATUS_PENDING, self.STATUS_ON_HOLD]:
            if self.status == self.STATUS_ON_HOLD and self.root_type in [
                self.ROOT_TYPE_ON_SUCCESS, self.ROOT_TYPE_ON_FAILURE, self.ROOT_TYPE_ON_COMPLETE
            ]:
                self.__generate_parent_root_copy()

            if not self.created_at:
                self.created_at = datetime.utcnow()
        elif new_status == self.STATUS_INITIATED:
            self.initiated_at = datetime.utcnow()
        elif new_status == self.STATUS_READY and self.status != self.STATUS_RUNNING:
            if not self.previous_roots.count():
                self.workflow_workspace.status = WorkflowsWorkspace.STATUS_PENDING
        elif new_status == self.STATUS_RUNNING:
            self.started_at = datetime.utcnow()
        elif new_status in [
            self.STATUS_C_SUCCESSFULLY_WFC, self.STATUS_C_SUCCESSFULLY, self.STATUS_C_W_FAILURE_WFC,
            self.STATUS_C_W_FAILURE
        ]:
            self.completed_at = datetime.utcnow()

        self.__status = new_status

    @property
    def next_roots(self):
        """
        Property to get next tasks associated with the current task
        :return:
        """
        return self._next_roots

    @property
    def previous_roots(self):
        """
        Property to get previous tasks associated with the current task
        :return:
        """
        return self._previous_roots

    @property
    def is_provisionable(self):
        """
        Property to get previous successful roots associated with the current root
        :return:
        """
        return self.previous_roots.filter(WorkflowRoot.status.in_(
            {WorkflowRoot.STATUS_C_SUCCESSFULLY}
        )).count() == self.previous_roots.count() and self.status not in [self.STATUS_C_SUCCESSFULLY,
                                                                          self.STATUS_RUNNING, self.STATUS_PENDING]

    @property
    def next_tasks(self):
        """
        Property to get next (first group) tasks of the root task
        :return:
        """
        return self.associated_tasks.filter(~WorkflowTask._previous_tasks.any()).all()

    @property
    def in_focus_tasks(self):
        """
        Property to get tasks which are in focus right now (running, failed, completed but not acknowledged, failed but
        not acknowledged)
        :return:
        """
        return self.associated_tasks.filter(WorkflowTask.in_focus).all()

    @property
    def resource_type(self):
        try:
            return self.workflow_name.split(" ")[0]
        except AttributeError:
            return ""

    def to_json(self, metadata=False):
        resp = {
            self.ID_KEY: self.id,
            self.WORKFLOW_NAME_KEY: self.workflow_name,
            self.RESOURCE_TYPE_KEY: self.resource_type,
            self.WORKFLOW_NATURE_KEY: self.workflow_nature,
            self.FE_REQUEST_DATA_KEY: self.fe_request_data,
            self.STATUS_KEY: self.status,
            self.CREATED_AT_KEY: str(self.created_at) if self.created_at else None,
            self.COMPLETED_AT_KEY: str(self.completed_at) if self.completed_at else None,
            self.NEXT_ROOT_IDS_KEY: [next_root.id for next_root in self.next_roots.all()],
            self.PREVIOUS_ROOT_IDS_KEY: [previous_root.id for previous_root in self.previous_roots.all()],
        }

        if not metadata:
            resp[self.ASSOCIATED_TASKS_KEY] = [task.to_json() for task in self.associated_tasks]

        return resp


class WorkflowTask(Base):
    """
    This database model holds information for a task that is tied to a resource
    """
    __tablename__ = 'workflow_tasks'

    ID_KEY = "id"
    STATUS_KEY = "status"
    RESOURCE_ID_KEY = "resource_id"
    RESOURCE_TYPE_KEY = "resource_type"
    TASK_TYPE_KEY = "task_type"
    # TODO: remove this key and avoid sending task_matadata to FE
    TASK_METADATA_KEY = "task_metadata"
    RESULT_KEY = "result"
    MESSAGE_KEY = "message"
    IN_FOCUS_KEY = "in_focus"
    PREVIOUS_TASK_IDS_KEY = "previous_task_ids"
    NEXT_TASK_IDS_KEY = "next_task_ids"

    # When the task is created but not initated yet
    STATUS_PENDING = "PENDING"
    # When the task is initiated, but not picked up by any worker yet
    STATUS_INITIATED = "INITIATED"
    # When the task is executing, IN FOCUS
    STATUS_RUNNING = "RUNNING"
    # When the task needs to wait for something before declaring it successful/failed, IN FOCUS
    STATUS_RUNNING_WAIT = "RUNNING_WAIT"
    # Internal, same as RUNNING_WAIT, IN FOCUS
    STATUS_RUNNING_WAIT_INITIATED = "RUNNING_WAIT_INITIATED"
    # When the task is completed succesfully, IN FOCUS but is set to False when the executor runs again
    STATUS_SUCCESSFUL = "SUCCESSFUL"
    # When the task fails, IN FOCUS
    STATUS_FAILED = "FAILED"
    ALL_STATUSES_LIST = [
        STATUS_PENDING, STATUS_INITIATED, STATUS_RUNNING, STATUS_RUNNING_WAIT, STATUS_RUNNING_WAIT_INITIATED,
        STATUS_SUCCESSFUL, STATUS_FAILED
    ]

    TYPE_ATTACH = "ATTACH"
    TYPE_DETACH = "DETACH"
    TYPE_VALIDATE = "VALIDATE"
    TYPE_CREATE = "CREATE"
    TYPE_DELETE = "DELETE"
    TYPE_SYNC = "SYNC"
    TYPE_DISCOVERY = "DISCOVERY"
    TYPE_UPDATE = "UPDATE"
    TYPE_RESTORE = "RESTORE"
    TYPE_RESTORE_KUBERNETES_CLUSTER = "RESTORE_KUBERNETES_CLUSTER"
    TYPE_MAP = "MAP"
    TYPE_BACKUP = "BACKUP"
    TYPE_ONPREM_BACKUP = "ONPREM_BACKUP"
    TYPE_DELETE_BACKUP = "DELETE_BACKUP"
    TYPE_DELETE_PLAN = "DELETE_PLAN"
    TYPE_TRANSLATE = "TRANSLATE"
    TYPE_EXECUTE_RESTORE = "EXECUTE_RESTORE"
    TYPE_EXECUTE_BACKUP = "EXECUTE_BACKUP"
    TYPE_CONSUMPTION = "CONSUMPTION"
    TYPE_BACKUP_CONSUMPTION = "BACKUP_CONSUMPTION"
    TYPE_RESTORE_CONSUMPTION = "RESTORE_CONSUMPTION"
    TYPE_DELETE_CONSUMPTION = "DELETE_BACKUP_CONSUMPTION"
    TYPE_ENABLE = "ENABLE"
    TYPE_DISABLE = "DISABLE"
    TYPE_SNAPSHOT = "SNAPSHOT"
    TYPE_EXPORT = "EXPORT"
    TYPE_CONVERT = "CONVERT"
    TYPE_START = "START"
    TYPE_STOP = "STOP"
    TYPE_UPDATE_METADATA = "UPDATE_METADATA"
    TYPE_FETCH_COST = "FETCH_COST"

    id = Column(String(32), primary_key=True)
    # Id of the resource the task belongs to. Can be none if it does not belong to any resource
    resource_id = Column(String(32))
    # Type of the resource (or DB Model Name) of the resource of the task it belongs to
    resource_type = Column(String(512), nullable=False)
    task_type = Column(String(512), nullable=False)
    # Store any information regarding the task, grey area to store whatever you like, rough work section
    task_metadata = deferred(Column(JSON))
    # Store result in JSON form, if any
    result = deferred(Column(JSON))
    # DO NOT ACCESS STATUS DIRECTLY
    __status = Column("status", Enum(*ALL_STATUSES_LIST), default=STATUS_PENDING, nullable=False)
    # This column can store any messages that relate to the failure of a task
    message = Column(String(1024))
    # in_focus should only be changed in the workflow_tasks file. DO NOT CHANGE IT ANYWHERE ELSE
    in_focus = Column(Boolean, default=False, nullable=False)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow())
    # The difference shows time it took for this task to be initiated by workflow executor
    initiated_at = Column(DateTime)
    # The difference shows time it took for the task to be picked up by a worker
    started_at = Column(DateTime)
    # The difference shows time it took for the task to complete execution
    completed_at = Column(DateTime)

    _next_tasks = relationship(
        'WorkflowTask',
        secondary=workflow_tree_mappings,
        primaryjoin=id == workflow_tree_mappings.c.task_id,
        secondaryjoin=id == workflow_tree_mappings.c.next_task_id,
        backref=backref('_previous_tasks', lazy='dynamic'),
        lazy='dynamic'
    )

    root_id = Column(String(32), ForeignKey('workflow_roots.id', ondelete="CASCADE"))

    def __init__(self, task_type, resource_type, resource_id=None, task_metadata=None):
        self.id = str(uuid.uuid4().hex)
        self.resource_id = resource_id
        self.resource_type = resource_type
        self.task_type = task_type
        self.task_metadata = task_metadata
        self.created_at = datetime.utcnow()
        self.status = self.STATUS_PENDING

    def add_next_task(self, next_task):
        """
        Add subsequent task
        :param next_task: <object of WorkflowTask> Task that should run if this task is successful
        """
        assert isinstance(next_task, WorkflowTask)
        if not self.root:
            raise ValueError("Invalid operation add_next_task, {} does not have root".format(self.id))

        next_task.root = self.root
        self._next_tasks.append(next_task)

    def add_previous_task(self, previous_task):
        """
        Add pre-req task
        :param previous_task: <object of WorkflowTask> Task which should be successful for this task to run
        """
        assert isinstance(previous_task, WorkflowTask)
        if not self.root:
            raise ValueError("Invalid operation add_previous_task, {} does not have root".format(self.id))

        previous_task.root = self.root
        self._previous_tasks.append(previous_task)

    @hybrid_property
    def status(self):
        """
        Hybrid property (you can query on this) for status getter
        :return:
        """
        return self.__status

    @status.setter
    def status(self, new_status):
        """
        Hybrid property (you can query on this) for status setter
        :param new_status: <string> status to be set
        """
        if new_status == self.STATUS_INITIATED:
            self.initiated_at = datetime.utcnow()
        elif new_status == self.STATUS_RUNNING:
            self.started_at = datetime.utcnow()
        elif new_status == self.STATUS_SUCCESSFUL:
            log_resource_billing_in_db(self)
            self.completed_at = datetime.utcnow()
        elif new_status == WorkflowTask.STATUS_FAILED:
            self.completed_at = datetime.utcnow()

        self.__status = new_status

    @property
    def next_tasks(self):
        """
        Property to get next tasks associated with the current task
        :return:
        """
        return self._next_tasks

    @property
    def previous_tasks(self):
        """
        Property to get previous tasks associated with the current task
        :return:
        """
        return self._previous_tasks

    def to_json(self):
        return {
            self.ID_KEY: self.id,
            self.STATUS_KEY: self.status,
            self.MESSAGE_KEY: self.message,
            self.RESOURCE_ID_KEY: self.resource_id,
            self.RESOURCE_TYPE_KEY: self.resource_type,
            self.TASK_TYPE_KEY: self.task_type,
            self.TASK_METADATA_KEY: self.task_metadata,
            self.RESULT_KEY: self.result,
            self.PREVIOUS_TASK_IDS_KEY: [task.id for task in self.previous_tasks],
            self.NEXT_TASK_IDS_KEY: [task.id for task in self.next_tasks]
        }
