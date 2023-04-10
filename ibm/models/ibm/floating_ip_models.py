import uuid
from datetime import datetime

from sqlalchemy import Column, DateTime, ForeignKey, String
from sqlalchemy.schema import UniqueConstraint

from ibm import get_db_session as db
from ibm.common.consts import CREATED_AT_FORMAT
from ibm.models.base import Base
from ibm.models.ibm.mixins import IBMZonalResourceMixin


class IBMFloatingIP(IBMZonalResourceMixin, Base):
    ID_KEY = "id"
    RESOURCE_ID_KEY = "resource_id"
    NAME_KEY = "name"
    STATUS_KEY = "status"
    ADDRESS_KEY = "address"
    CRN_KEY = "crn"
    HREF_KEY = "href"
    CREATED_AT_KEY = "created_at"
    TARGET_KEY = "target"
    INSTANCE_KEY = "instance"
    RESOURCE_GROUP_KEY = "resource_group"
    RESOURCE_TYPE_KEY = "resource_type"
    ESTIMATED_SAVINGS = "estimated_savings"
    COST_KEY = "cost"
    RESOURCE_TYPE_FLOATING_IP_KEY = "Floating IP"

    CRZ_BACKREF_NAME = "floating_ips"

    # ibm status consts
    STATUS_AVAILABLE = "available"
    STATUS_DELETING = "deleting"
    STATUS_FAILED = "failed"
    STATUS_PENDING = "pending"
    STATUSES_LIST = [STATUS_AVAILABLE, STATUS_DELETING, STATUS_FAILED, STATUS_PENDING]

    __tablename__ = "ibm_floating_ips"

    id = Column(String(32), primary_key=True)
    resource_id = Column(String(64), nullable=False)
    name = Column(String(255), nullable=False)
    status = Column(String(50), nullable=False)
    address = Column(String(255), nullable=False)
    crn = Column(String(255), nullable=False)
    href = Column(String(255), nullable=False)
    created_at = Column(DateTime, nullable=False)

    resource_group_id = Column(String(32), ForeignKey("ibm_resource_groups.id", ondelete="CASCADE"))
    public_gateway_id = Column(String(32), ForeignKey("ibm_public_gateways.id", ondelete="SET NULL"), nullable=True)
    network_interface_id = Column(String(32), ForeignKey("ibm_network_interfaces.id", ondelete="SET NULL"),
                                  nullable=True)

    __table_args__ = (
        UniqueConstraint(
            name, "resource_id", "zone_id", "cloud_id",
            name="uix_ibm_floating_ip_name_resource_id_zone_id_cloud_id"),
    )

    def __init__(
            self, resource_id=None, name=None, status=None, address=None, crn=None, href=None,
            created_at=None
    ):
        self.id = str(uuid.uuid4().hex)
        self.resource_id = resource_id
        self.name = name
        self.status = status
        self.address = address
        self.crn = crn
        self.href = href
        self.created_at = created_at

    def get_target_json(self):
        target = self.public_gateway if self.public_gateway else self.network_interface
        if not target:
            return {}

        resource_type = target.resource_type
        json_data = {
            self.ID_KEY: target.id,
            self.RESOURCE_ID_KEY: target.resource_id,
            self.NAME_KEY: target.name,
            self.RESOURCE_TYPE_KEY: resource_type
        }
        if resource_type == "network_interface":
            json_data[self.INSTANCE_KEY] = target.instance.to_reference_json()

        return json_data

    def to_reference_json(self):
        return {
            self.ID_KEY: self.id,
            self.NAME_KEY: self.name,
            self.ZONE_KEY: self.zone.to_reference_json(),
        }

    def dis_params_eq(self, other):
        assert isinstance(other, self.__class__)
        return (self.name == other.name and self.address == other.address and self.resource_id == other.resource_id and
                self.status == other.status)

    def dis_add_update_db(
            self, db_session, db_floating_ips, db_cloud, db_resource_group, db_network_interface,
            db_public_gateway, db_zone
    ):
        if not db_resource_group:
            return
        db_floating_ips_id_obj_dict = dict()
        db_floating_ips_name_obj_dict = dict()
        for db_floating_ip in db_floating_ips:
            db_floating_ips_id_obj_dict[db_floating_ip.resource_id] = db_floating_ip
            db_floating_ips_name_obj_dict[db_floating_ip.name] = db_floating_ip

        if self.resource_id not in db_floating_ips_id_obj_dict and self.name in db_floating_ips_name_obj_dict:
            # Creation Pending / Creating
            existing = db_floating_ips_name_obj_dict[self.name]
        elif self.resource_id in db_floating_ips_id_obj_dict:
            # Created. Update everything including name
            existing = db_floating_ips_id_obj_dict[self.resource_id]
        else:
            existing = None

        if not existing:
            self.ibm_cloud = db_cloud
            self.resource_group = db_resource_group
            self.network_interface = db_network_interface
            self.public_gateway = db_public_gateway
            self.zone = db_zone
            db_session.add(self)
            db_session.commit()
            return

        if not self.dis_params_eq(existing):
            existing.update_from_object(self)
            existing.resource_group = db_resource_group
            existing.network_interface = db_network_interface
            existing.public_gateway = db_public_gateway
            existing.zone = db_zone

        db_session.commit()

    def update_from_object(self, other):
        assert isinstance(other, self.__class__)

        self.name = other.name
        self.status = other.status
        self.address = other.address
        self.resource_id = other.resource_id

    def to_json(self):
        return {
            self.ID_KEY: self.id,
            self.RESOURCE_ID_KEY: self.resource_id,
            self.NAME_KEY: self.name,
            self.STATUS_KEY: self.status,
            self.ADDRESS_KEY: self.address,
            self.CRN_KEY: self.crn,
            self.HREF_KEY: self.href,
            self.CREATED_AT_KEY: self.created_at,
            self.TARGET_KEY: self.get_target_json(),
            self.IBM_CLOUD_KEY: self.ibm_cloud.to_reference_json(),
            self.RESOURCE_GROUP_KEY: self.resource_group.to_reference_json(),
            self.REGION_KEY: self.region.to_reference_json(),
            self.ZONE_KEY: self.zone.to_reference_json(),
        }

    def to_idle_json(self, session=None):
        from ibm.models.ibm.cost_models import IBMResourceInstancesCost

        session = session if session else db.session

        cost_obj = IBMResourceInstancesCost.get_cost(self.crn, self.cloud_id, session)
        return {
            self.STATUS_KEY: self.status,
            self.ADDRESS_KEY: self.address,
            self.CRN_KEY: self.crn,
            self.HREF_KEY: self.href,
            self.RESOURCE_TYPE_KEY: self.RESOURCE_TYPE_FLOATING_IP_KEY,
            self.RESOURCE_ID_KEY: self.resource_id,
            self.IBM_CLOUD_KEY: self.cloud_id,
            self.ESTIMATED_SAVINGS: cost_obj.estimated_cost if cost_obj else None,
            self.COST_KEY: cost_obj.estimated_cost if cost_obj else None
        }

    def to_json_body(self):
        json_data = {"name": self.name}

        if self.resource_group_id:
            json_data["resource_group"] = {"id": self.ibm_resource_group.resource_id}

        if self.ibm_public_gateway:
            json_data["target"] = {self.ID_KEY: self.ibm_public_gateway.resource_id}
        elif self.ibm_network_interface:
            json_data["target"] = {self.ID_KEY: self.ibm_network_interface.resource_id}
        else:
            json_data["zone"] = {"name": self.zone}

        return json_data

    @classmethod
    def from_ibm_json_body(cls, json_body):
        """
        This method is for the purpose of creating a model object out of a JSON. This JSON can be from ibm cloud
        """
        return IBMFloatingIP(
            resource_id=json_body["id"],
            name=json_body["name"],
            status=json_body["status"],
            address=json_body["address"],
            crn=json_body["crn"],
            href=json_body["href"],
            created_at=datetime.strptime(json_body["created_at"], CREATED_AT_FORMAT),
        )
