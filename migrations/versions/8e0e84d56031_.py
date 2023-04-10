"""empty message

Revision ID: 8e0e84d56031
Revises: fb1009b64a8a
Create Date: 2021-09-23 18:59:31.297773

"""

# revision identifiers, used by Alembic.
revision = '8e0e84d56031'
down_revision = 'fb1009b64a8a'

from alembic import op
import sqlalchemy as sa


def upgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.create_table('ibm_ike_policy',
    sa.Column('id', sa.String(length=32), nullable=False),
    sa.Column('resource_id', sa.String(length=64), nullable=False),
    sa.Column('authentication_algorithm', sa.Enum('md5', 'sha1', 'sha256', 'sha512'), nullable=False),
    sa.Column('created_at', sa.DateTime(), nullable=False),
    sa.Column('dh_group', sa.Enum('2', '5', '14', '19'), nullable=False),
    sa.Column('encryption_algorithm', sa.Enum('triple_des', 'aes128', 'aes256'), nullable=False),
    sa.Column('href', sa.Text(), nullable=False),
    sa.Column('ike_version', sa.Enum('1', '2'), nullable=False),
    sa.Column('key_lifetime', sa.Integer(), nullable=False),
    sa.Column('name', sa.String(length=255), nullable=False),
    sa.Column('negotiation_mode', sa.Enum('negotiation_mode'), nullable=False),
    sa.Column('resource_type', sa.Enum('ike_policy'), nullable=False),
    sa.Column('status', sa.String(length=50), nullable=False),
    sa.Column('resource_group_id', sa.String(length=32), nullable=False),
    sa.Column('region_id', sa.String(length=32), nullable=False),
    sa.Column('cloud_id', sa.String(length=32), nullable=False),
    sa.ForeignKeyConstraint(['cloud_id'], ['ibm_clouds.id'], ),
    sa.ForeignKeyConstraint(['region_id'], ['ibm_regions.id'], ),
    sa.ForeignKeyConstraint(['resource_group_id'], ['ibm_resource_groups.id'], ),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('name', 'region_id', 'cloud_id', name='uix_ibm_ike_policy_name_region_id_cloud_id')
    )
    op.create_table('ibm_ipsec_policy',
    sa.Column('id', sa.String(length=32), nullable=False),
    sa.Column('resource_id', sa.String(length=64), nullable=False),
    sa.Column('authentication_algorithm', sa.Enum('md5', 'sha1', 'sha256', 'sha512'), nullable=False),
    sa.Column('created_at', sa.DateTime(), nullable=False),
    sa.Column('encapsulation_mode', sa.Enum('tunnel'), nullable=False),
    sa.Column('encryption_algorithm', sa.Enum('triple_des', 'aes128', 'aes256'), nullable=False),
    sa.Column('href', sa.Text(), nullable=False),
    sa.Column('key_lifetime', sa.Integer(), nullable=False),
    sa.Column('name', sa.String(length=255), nullable=False),
    sa.Column('pfs', sa.Enum('group_2', 'group_5', 'group_14', 'group_19', 'disabled'), nullable=False),
    sa.Column('resource_type', sa.Enum('ipsec_policy'), nullable=False),
    sa.Column('transform_protocol', sa.Enum('esp'), nullable=False),
    sa.Column('status', sa.String(length=50), nullable=False),
    sa.Column('resource_group_id', sa.String(length=32), nullable=False),
    sa.Column('region_id', sa.String(length=32), nullable=False),
    sa.Column('cloud_id', sa.String(length=32), nullable=False),
    sa.ForeignKeyConstraint(['cloud_id'], ['ibm_clouds.id'], ),
    sa.ForeignKeyConstraint(['region_id'], ['ibm_regions.id'], ),
    sa.ForeignKeyConstraint(['resource_group_id'], ['ibm_resource_groups.id'], ),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('name', 'region_id', 'cloud_id', name='uix_ibm_ipsec_policy_name_region_id_cloud_id')
    )
    op.create_table('ibm_vpn_gateways',
    sa.Column('id', sa.String(length=32), nullable=False),
    sa.Column('resource_id', sa.String(length=64), nullable=False),
    sa.Column('created_at', sa.DateTime(), nullable=False),
    sa.Column('crn', sa.String(length=255), nullable=False),
    sa.Column('href', sa.Text(), nullable=False),
    sa.Column('name', sa.String(length=255), nullable=False),
    sa.Column('resource_type', sa.Enum('vpn_gateway'), nullable=False),
    sa.Column('ibm_status', sa.Enum('available', 'deleting', 'failed', 'pending'), nullable=False),
    sa.Column('status', sa.String(length=50), nullable=False),
    sa.Column('mode', sa.Enum('route', 'policy'), nullable=False),
    sa.Column('vpc_id', sa.String(length=32), nullable=False),
    sa.Column('subnet_id', sa.String(length=32), nullable=False),
    sa.Column('resource_group_id', sa.String(length=32), nullable=False),
    sa.Column('region_id', sa.String(length=32), nullable=False),
    sa.Column('cloud_id', sa.String(length=32), nullable=False),
    sa.ForeignKeyConstraint(['cloud_id'], ['ibm_clouds.id'], ),
    sa.ForeignKeyConstraint(['region_id'], ['ibm_regions.id'], ),
    sa.ForeignKeyConstraint(['resource_group_id'], ['ibm_resource_groups.id'], ),
    sa.ForeignKeyConstraint(['subnet_id'], ['ibm_subnets.id'], ),
    sa.ForeignKeyConstraint(['vpc_id'], ['ibm_vpc_networks.id'], ),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('name', 'vpc_id', 'cloud_id', name='uix_ibm_vpn_gateway_vpc_cloud_id')
    )
    op.create_table('ibm_vpn_connections',
    sa.Column('id', sa.String(length=32), nullable=False),
    sa.Column('resource_id', sa.String(length=64), nullable=False),
    sa.Column('admin_state_up', sa.Boolean(), nullable=False),
    sa.Column('authentication_mode', sa.Enum('psk'), nullable=False),
    sa.Column('created_at', sa.DateTime(), nullable=False),
    sa.Column('dead_peer_detection', sa.JSON(), nullable=False),
    sa.Column('href', sa.Text(), nullable=False),
    sa.Column('mode', sa.Enum('policy', 'route'), nullable=False),
    sa.Column('name', sa.String(length=255), nullable=False),
    sa.Column('local_cidrs', sa.JSON(), nullable=True),
    sa.Column('peer_address', sa.String(length=255), nullable=False),
    sa.Column('peer_cidrs', sa.JSON(), nullable=True),
    sa.Column('psk', sa.String(length=255), nullable=False),
    sa.Column('resource_type', sa.Enum('vpn_gateway_connection'), nullable=False),
    sa.Column('ibm_status', sa.Enum('up', 'down'), nullable=False),
    sa.Column('status', sa.String(length=50), nullable=False),
    sa.Column('routing_protocol', sa.Enum('none'), nullable=False),
    sa.Column('tunnels', sa.JSON(), nullable=True),
    sa.Column('ike_policy_id', sa.String(length=32), nullable=True),
    sa.Column('ipsec_policy_id', sa.String(length=32), nullable=True),
    sa.Column('vpn_gateway_id', sa.String(length=32), nullable=False),
    sa.ForeignKeyConstraint(['ike_policy_id'], ['ibm_ike_policy.id'], ),
    sa.ForeignKeyConstraint(['ipsec_policy_id'], ['ibm_ipsec_policy.id'], ),
    sa.ForeignKeyConstraint(['vpn_gateway_id'], ['ibm_vpn_gateways.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('name', 'vpn_gateway_id', name='uix_ibm_vpn_connection_name_vpn_gateway_id')
    )
    op.create_table('ibm_vpn_gateway_members',
    sa.Column('id', sa.String(length=32), nullable=False),
    sa.Column('public_ip', sa.String(length=15), nullable=False),
    sa.Column('role', sa.Enum('active', 'standby'), nullable=False),
    sa.Column('ibm_status', sa.Enum('available', 'failed', 'pending', 'deleting'), nullable=False),
    sa.Column('private_ip', sa.String(length=15), nullable=True),
    sa.Column('vpn_gateway_id', sa.String(length=32), nullable=False),
    sa.ForeignKeyConstraint(['vpn_gateway_id'], ['ibm_vpn_gateways.id'], ),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('role', 'vpn_gateway_id', name='uix_ibm_vpn_gateway_member_role_vpn_gateway_id')
    )
    op.add_column('ibm_routing_table_routes', sa.Column('next_hop_vpn_gateway_connection_id', sa.String(length=32), nullable=True))
    op.create_foreign_key('ibm_routing_table_routes_ibfk_5', 'ibm_routing_table_routes', 'ibm_vpn_connections', ['next_hop_vpn_gateway_connection_id'], ['id'])
    # ### end Alembic commands ###


def downgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.drop_constraint('ibm_routing_table_routes_ibfk_5', 'ibm_routing_table_routes', type_='foreignkey')
    op.drop_column('ibm_routing_table_routes', 'next_hop_vpn_gateway_connection_id')
    op.drop_table('ibm_vpn_gateway_members')
    op.drop_table('ibm_vpn_connections')
    op.drop_table('ibm_vpn_gateways')
    op.drop_table('ibm_ipsec_policy')
    op.drop_table('ibm_ike_policy')
    # ### end Alembic commands ###