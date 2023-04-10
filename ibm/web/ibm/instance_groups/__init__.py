from .api import ibm_instance_groups
from .instance_group_manager_actions import \
    ibm_instance_group_manager_actions as ibm_instance_group_manager_actions_blueprint
from .instance_group_manager_policies import \
    ibm_instance_group_manager_policies as ibm_instance_group_manager_policies_blueprint
from .instance_group_managers import ibm_instance_group_managers as ibm_instance_group_managers_blueprint
from .instance_group_memberships import ibm_instance_group_memberships as ibm_instance_group_memberships_blueprint

ibm_instance_group_blueprints = [
    ibm_instance_groups,
    ibm_instance_group_manager_actions_blueprint,
    ibm_instance_group_manager_policies_blueprint,
    ibm_instance_group_managers_blueprint,
    ibm_instance_group_memberships_blueprint
]

__all__ = ["ibm_instance_group_blueprints"]
