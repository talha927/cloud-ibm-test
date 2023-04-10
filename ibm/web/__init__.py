from apiflask import APIFlask
from flask_compress import Compress
from flask_sqlalchemy import SQLAlchemy

from config import flask_config

compress = Compress()

db = SQLAlchemy()


def create_app(environment):
    app = APIFlask(__name__, title="VPC+ IBM API Docs", version="1.0", redoc_path="/v1/ibm/apidocs",
                   spec_path="/v1/ibm/openapi.json")
    config = flask_config[environment]
    app.config.from_object(config)
    app.logger.setLevel(config.LOGGING_LEVEL_MAPPED)
    compress.init_app(app)
    db.init_app(app)
    db.app = app

    from .ibm.acls import ibm_acls as ibm_acls_blueprint
    from .ibm.address_prefixes import ibm_address_prefixes as ibm_address_prefixes_blueprint
    from .ibm.activity_tracking import ibm_activity_tracking as ibm_activity_tracking_blueprint
    from .ibm.workspaces import workspace as workspace_blueprint
    from .ibm.clouds import ibm_clouds as ibm_clouds_blueprint
    from .ibm.cloud_object_storages import ibm_cloud_object_storages as ibm_cloud_object_storages_blueprint
    from .ibm.transit_gateways import ibm_transit_gateways as ibm_transit_gateways_blueprint
    from .ibm.dedicated_hosts import ibm_dedicated_hosts as ibm_dedicated_hosts_blueprint
    from .ibm.dedicated_hosts.dedicated_host_disks import ibm_dedicated_host_disks as ibm_dedicated_host_disks_blueprint
    from .ibm.dedicated_hosts.dedicated_host_groups import \
        ibm_dedicated_host_groups as ibm_dedicated_host_groups_blueprint
    from .ibm.dedicated_hosts.dedicated_host_profiles import \
        ibm_dedicated_host_profiles as ibm_dedicated_host_profiles_blueprint
    from .ibm.endpoint_gateways import ibm_endpoint_gateways as ibm_endpoint_gateways_blueprint
    from .ibm.floating_ips import ibm_floating_ips as ibm_floating_ips_blueprint
    from .ibm.geography import ibm_geography as ibm_geography_blueprint
    from ibm.web.ibm.vpn_gateways.ike_policies import ibm_ike_policies as ibm_ike_policies_blueprint
    from ibm.web.ibm.vpn_gateways.ipsec_policies import ibm_ipsec_policies as ibm_ipsec_policies_blueprint
    from .ibm.images import ibm_images as ibm_images_blueprint
    from .ibm.instances import ibm_instances as ibm_instances_blueprint
    from .ibm.instances.backups import ibm_instance_backup as ibm_instance_backup_blueprint
    from .ibm.instances.disks import ibm_instance_disks as ibm_instance_disks_blueprint
    from .ibm.instances.profiles import ibm_instance_profiles as ibm_instance_profiles_blueprint
    from .ibm.instances.network_interfaces import ibm_network_interfaces as ibm_network_interfaces_blueprint
    from .ibm.instance_groups import ibm_instance_group_blueprints
    from .ibm.instances.templates import ibm_instance_templates as ibm_instance_templates_blueprint
    from .ibm.instances.volume_attachments import ibm_volume_attachments as ibm_volume_attachments_blueprint
    from .ibm.kubernetes import ibm_kubernetes_clusters as ibm_kubernetes_clusters_blueprint
    from .ibm.draas import ibm_draas as ibm_draas_blueprint
    from .ibm.load_balancers import ibm_load_balancer_blueprints
    from .ibm.placement_groups import ibm_placement_groups as ibm_placement_groups_blueprint
    from .ibm.public_gateways import ibm_public_gateways as ibm_public_gateways_blueprint
    from .ibm.resource_groups import ibm_resource_groups as ibm_resource_groups_blueprint
    from .ibm.routing_tables import ibm_routing_tables as ibm_routing_tables_blueprint
    from .ibm.security_groups import ibm_security_groups as ibm_security_groups_blueprint
    from .ibm.snapshots import ibm_snapshots as ibm_snapshots_blueprint
    from .ibm.ssh_keys import ibm_ssh_keys as ibm_ssh_keys_blueprint
    from .ibm.subnets import ibm_subnets as ibm_subnets_blueprint
    from .ibm.tags import ibm_tags as ibm_tags_blueprint
    from .ibm.volumes import ibm_volumes as ibm_volumes_blueprint
    from .ibm.vpcs import ibm_vpc_networks as ibm_vpc_networks_blueprint
    from .ibm.costs import ibm_costs as ibm_costs_blueprint
    from .ibm.vpn_gateways import ibm_vpn_gateways as ibm_vpn_gateways_blueprint
    from .cloud_translations import cloud_translations as cloud_translations_blueprint
    from .migrations import ibm_migrations as ibm_migrations_blueprint
    from .migrations.content import nas_migrations as nas_migrations_blueprint
    from .rightsizng import ibm_right_sizing_recommendation as ibm_right_sizing_recommendation_blueprint
    from .resource_tracking import ibm_resource_tracking as ibm_resource_tracking_blueprint
    from .release_notes import ibm_release_notes as ibm_release_notes_blueprint
    from .softlayer.accounts import softlayer_account as softlayer_account_blueprint
    from .softlayer.images import softlayer_images as softlayer_images_blueprint
    from .softlayer.instances import softlayer_instances as softlayer_instances_blueprint
    from .softlayer.recommendations import softlayer_recommendations as softlayer_recommendations_blueprint
    from .workflows import ibm_workflows as ibm_workflows_blueprint
    from .ibm.idle_resources import ibm_idle_resources as ibm_idle_resources_blueprint
    from .ibm.resource_controller_data import ibm_resource_controller_data as ibm_resource_controller_data_blueprint
    from .ibm.cost_reporting import ibm_reporting as ibm_reporting_blueprint
    from .ibm.satellite import ibm_satellite_clusters as ibm_satellite_cluster_blueprint
    from .agent import agent as ibm_agent_blueprint

    app.register_blueprint(ibm_agent_blueprint, url_prefix="/v1/ibm")
    app.register_blueprint(ibm_acls_blueprint, url_prefix="/v1/ibm")
    app.register_blueprint(ibm_resource_controller_data_blueprint, url_prefix="/v1/ibm")
    app.register_blueprint(cloud_translations_blueprint, url_prefix="/v1/ibm")
    app.register_blueprint(ibm_address_prefixes_blueprint, url_prefix="/v1/ibm")
    app.register_blueprint(ibm_activity_tracking_blueprint, url_prefix="/v1/ibm")
    app.register_blueprint(workspace_blueprint, url_prefix="/v1/ibm")
    app.register_blueprint(ibm_clouds_blueprint, url_prefix="/v1/ibm")
    app.register_blueprint(ibm_cloud_object_storages_blueprint, url_prefix="/v1/ibm")
    app.register_blueprint(ibm_dedicated_hosts_blueprint, url_prefix="/v1/ibm")
    app.register_blueprint(ibm_dedicated_host_disks_blueprint, url_prefix="/v1/ibm")
    app.register_blueprint(ibm_dedicated_host_groups_blueprint, url_prefix="/v1/ibm")
    app.register_blueprint(ibm_dedicated_host_profiles_blueprint, url_prefix="/v1/ibm")
    app.register_blueprint(ibm_draas_blueprint, url_prefix="/v1/ibm")
    app.register_blueprint(ibm_endpoint_gateways_blueprint, url_prefix="/v1/ibm")
    app.register_blueprint(ibm_floating_ips_blueprint, url_prefix="/v1/ibm")
    app.register_blueprint(ibm_geography_blueprint, url_prefix="/v1/ibm")
    app.register_blueprint(ibm_ike_policies_blueprint, url_prefix="/v1/ibm")
    app.register_blueprint(ibm_ipsec_policies_blueprint, url_prefix="/v1/ibm")
    app.register_blueprint(ibm_images_blueprint, url_prefix="/v1/ibm")
    app.register_blueprint(ibm_instances_blueprint, url_prefix="/v1/ibm")
    app.register_blueprint(ibm_instance_backup_blueprint, url_prefix="/v1/ibm")
    app.register_blueprint(ibm_instance_disks_blueprint, url_prefix="/v1/ibm")
    app.register_blueprint(ibm_instance_profiles_blueprint, url_prefix="/v1/ibm")
    app.register_blueprint(ibm_kubernetes_clusters_blueprint, url_prefix="/v1/ibm")
    app.register_blueprint(ibm_network_interfaces_blueprint, url_prefix="/v1/ibm")
    app.register_blueprint(ibm_instance_templates_blueprint, url_prefix="/v1/ibm")
    app.register_blueprint(ibm_placement_groups_blueprint, url_prefix="/v1/ibm")
    app.register_blueprint(ibm_public_gateways_blueprint, url_prefix="/v1/ibm")
    app.register_blueprint(ibm_resource_groups_blueprint, url_prefix="/v1/ibm")
    app.register_blueprint(ibm_resource_tracking_blueprint, url_prefix="/v1/ibm")
    app.register_blueprint(ibm_release_notes_blueprint, url_prefix="/v1/ibm")
    app.register_blueprint(ibm_routing_tables_blueprint, url_prefix="/v1/ibm")
    app.register_blueprint(ibm_security_groups_blueprint, url_prefix="/v1/ibm")
    app.register_blueprint(ibm_snapshots_blueprint, url_prefix="/v1/ibm")
    app.register_blueprint(ibm_transit_gateways_blueprint, url_prefix="/v1/ibm")
    app.register_blueprint(ibm_tags_blueprint, url_prefix="/v1/ibm")
    # Register Load Balancer and related blueprints
    for blueprint in ibm_load_balancer_blueprints:
        app.register_blueprint(blueprint, url_prefix="/v1/ibm")
    for blueprint in ibm_instance_group_blueprints:
        app.register_blueprint(blueprint, url_prefix="/v1/ibm")
    app.register_blueprint(ibm_ssh_keys_blueprint, url_prefix="/v1/ibm")
    app.register_blueprint(ibm_subnets_blueprint, url_prefix="/v1/ibm")
    app.register_blueprint(ibm_volumes_blueprint, url_prefix="/v1/ibm")
    app.register_blueprint(ibm_volume_attachments_blueprint, url_prefix="/v1/ibm")
    app.register_blueprint(ibm_vpc_networks_blueprint, url_prefix="/v1/ibm")
    app.register_blueprint(ibm_costs_blueprint, url_prefix="/v1/ibm")
    app.register_blueprint(ibm_vpn_gateways_blueprint, url_prefix="/v1/ibm")
    app.register_blueprint(ibm_workflows_blueprint, url_prefix="/v1/ibm")
    app.register_blueprint(softlayer_account_blueprint, url_prefix="/v1/softlayer")
    app.register_blueprint(softlayer_images_blueprint, url_prefix="/v1/softlayer")
    app.register_blueprint(softlayer_instances_blueprint, url_prefix="/v1/softlayer")
    app.register_blueprint(ibm_migrations_blueprint, url_prefix="/v1/softlayer")
    app.register_blueprint(softlayer_recommendations_blueprint, url_prefix="/v1/softlayer")
    app.register_blueprint(nas_migrations_blueprint, url_prefix="/v1/migrate")
    app.register_blueprint(ibm_right_sizing_recommendation_blueprint, url_prefix="/v1/ibm")
    app.register_blueprint(ibm_idle_resources_blueprint, url_prefix="/v1/ibm")
    app.register_blueprint(ibm_reporting_blueprint, url_prefix="/v1/ibm")
    app.register_blueprint(ibm_satellite_cluster_blueprint, url_prefix="/v1/ibm")

    return app
