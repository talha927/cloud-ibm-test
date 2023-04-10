"""empty message

Revision ID: f658b81e0004
Revises: c3ee5869d109
Create Date: 2021-09-23 22:55:31.141472

"""

# revision identifiers, used by Alembic.
revision = 'f658b81e0004'
down_revision = 'c3ee5869d109'

from alembic import op
import sqlalchemy as sa


def upgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.create_table('ibm_instance_templates',
    sa.Column('id', sa.String(length=32), nullable=False),
    sa.Column('name', sa.String(length=255), nullable=False),
    sa.Column('resource_id', sa.String(length=64), nullable=False),
    sa.Column('created_at', sa.DateTime(), nullable=False),
    sa.Column('href', sa.Text(), nullable=False),
    sa.Column('crn', sa.String(length=255), nullable=False),
    sa.Column('user_data', sa.Text(), nullable=True),
    sa.Column('resource_group_id', sa.String(length=32), nullable=False),
    sa.Column('vpc_id', sa.String(length=32), nullable=True),
    sa.Column('placement_target_dh_id', sa.String(length=32), nullable=True),
    sa.Column('placement_target_dh_group_id', sa.String(length=32), nullable=True),
    sa.Column('placement_target_placement_group_id', sa.String(length=32), nullable=True),
    sa.Column('instance_profile_id', sa.String(length=32), nullable=True),
    sa.Column('image_id', sa.String(length=32), nullable=True),
    sa.Column('zone_id', sa.String(length=32), nullable=False),
    sa.Column('region_id', sa.String(length=32), nullable=False),
    sa.Column('cloud_id', sa.String(length=32), nullable=False),
    sa.ForeignKeyConstraint(['cloud_id'], ['ibm_clouds.id'], ),
    sa.ForeignKeyConstraint(['image_id'], ['ibm_images.id'], ),
    sa.ForeignKeyConstraint(['instance_profile_id'], ['ibm_instance_profiles.id'], ),
    sa.ForeignKeyConstraint(['placement_target_dh_group_id'], ['ibm_dedicated_host_groups.id'], ),
    sa.ForeignKeyConstraint(['placement_target_dh_id'], ['ibm_dedicated_hosts.id'], ),
    sa.ForeignKeyConstraint(['placement_target_placement_group_id'], ['ibm_placement_groups.id'], ),
    sa.ForeignKeyConstraint(['region_id'], ['ibm_regions.id'], ),
    sa.ForeignKeyConstraint(['resource_group_id'], ['ibm_resource_groups.id'], ),
    sa.ForeignKeyConstraint(['vpc_id'], ['ibm_vpc_networks.id'], ),
    sa.ForeignKeyConstraint(['zone_id'], ['ibm_zones.id'], ),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('name', 'region_id', 'cloud_id', name='uix_ibm_instance_template_name_region_id_cloud_id')
    )
    op.create_table('ibm_volume_prototypes',
    sa.Column('id', sa.String(length=32), nullable=False),
    sa.Column('iops', sa.Integer(), nullable=True),
    sa.Column('name', sa.String(length=255), nullable=True),
    sa.Column('capacity', sa.Integer(), nullable=True),
    sa.Column('encryption_key_crn', sa.String(length=255), nullable=True),
    sa.Column('volume_profile_id', sa.String(length=32), nullable=False),
    sa.Column('source_snapshot_id', sa.String(length=32), nullable=True),
    sa.ForeignKeyConstraint(['source_snapshot_id'], ['ibm_snapshots.id'], ),
    sa.ForeignKeyConstraint(['volume_profile_id'], ['ibm_volume_profiles.id'], ),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_table('ibm_instance_template_keys',
    sa.Column('instance_template_id', sa.String(length=32), nullable=False),
    sa.Column('key_id', sa.String(length=32), nullable=False),
    sa.ForeignKeyConstraint(['instance_template_id'], ['ibm_instance_templates.id'], ),
    sa.ForeignKeyConstraint(['key_id'], ['ibm_ssh_keys.id'], ),
    sa.PrimaryKeyConstraint('instance_template_id', 'key_id')
    )
    op.create_table('ibm_network_interface_prototypes',
    sa.Column('id', sa.String(length=32), nullable=False),
    sa.Column('name', sa.String(length=255), nullable=True),
    sa.Column('allow_ip_spoofing', sa.Boolean(), nullable=True),
    sa.Column('primary_ipv4_address', sa.String(length=15), nullable=True),
    sa.Column('is_primary', sa.Boolean(), nullable=False),
    sa.Column('instance_template_id', sa.String(length=32), nullable=False),
    sa.Column('subnet_id', sa.String(length=32), nullable=False),
    sa.ForeignKeyConstraint(['instance_template_id'], ['ibm_instance_templates.id'], ),
    sa.ForeignKeyConstraint(['subnet_id'], ['ibm_subnets.id'], ),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_table('ibm_volume_attachment_prototypes',
    sa.Column('id', sa.String(length=32), nullable=False),
    sa.Column('name', sa.String(length=255), nullable=True),
    sa.Column('delete_volume_on_instance_delete', sa.Boolean(), nullable=True),
    sa.Column('is_boot', sa.Boolean(), nullable=False),
    sa.Column('instance_template_id', sa.String(length=32), nullable=True),
    sa.Column('provisioned_volume_id', sa.String(length=32), nullable=True),
    sa.Column('volume_prototype_id', sa.String(length=32), nullable=True),
    sa.ForeignKeyConstraint(['instance_template_id'], ['ibm_instance_templates.id'], ),
    sa.ForeignKeyConstraint(['provisioned_volume_id'], ['ibm_volumes.id'], ),
    sa.ForeignKeyConstraint(['volume_prototype_id'], ['ibm_volume_prototypes.id'], ),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_table('ibm_network_interface_protoypes_security_groups',
    sa.Column('network_interface_prototype_id', sa.String(length=32), nullable=False),
    sa.Column('security_group_id', sa.String(length=32), nullable=False),
    sa.ForeignKeyConstraint(['network_interface_prototype_id'], ['ibm_network_interface_prototypes.id'], ),
    sa.ForeignKeyConstraint(['security_group_id'], ['ibm_security_groups.id'], ),
    sa.PrimaryKeyConstraint('network_interface_prototype_id', 'security_group_id')
    )
    # ### end Alembic commands ###


def downgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.drop_table('ibm_network_interface_protoypes_security_groups')
    op.drop_table('ibm_volume_attachment_prototypes')
    op.drop_table('ibm_network_interface_prototypes')
    op.drop_table('ibm_instance_template_keys')
    op.drop_table('ibm_volume_prototypes')
    op.drop_table('ibm_instance_templates')
    # ### end Alembic commands ###