import logging
from datetime import datetime

LOGGER = logging.getLogger(__name__)


def update_instance_groups(cloud_id, region_name, m_instance_groups):
    start_time = datetime.utcnow()
    LOGGER.info("** Instance Groups synced in:{}".format((datetime.utcnow() - start_time).total_seconds()))


def update_instance_group_managers(cloud_id, region_name, m_instance_group_managers):
    start_time = datetime.utcnow()
    LOGGER.info("** Instance Group Managers synced in:{}".format((datetime.utcnow() - start_time).total_seconds()))


def update_instance_group_manager_actions(cloud_id, region_name, m_instance_group_manager_actions):
    start_time = datetime.utcnow()
    LOGGER.info("** Instance Group Manager Actions in:{}".format((datetime.utcnow() - start_time).total_seconds()))


def update_instance_group_manager_policies(cloud_id, region_name, m_instance_group_manager_policies):
    start_time = datetime.utcnow()
    LOGGER.info(
        "** Instance Group Manager Policies synced in:{}".format((datetime.utcnow() - start_time).total_seconds()))


def update_instance_group_memberships(cloud_id, region_name, m_instance_group_memberships):
    start_time = datetime.utcnow()
    LOGGER.info("** Instance Group Memberships synced in:{}".format((datetime.utcnow() - start_time).total_seconds()))


def update_instance_templates(cloud_id, region_name, m_instance_templates):
    start_time = datetime.utcnow()
    LOGGER.info("** Instance Templates synced in:{}".format((datetime.utcnow() - start_time).total_seconds()))
