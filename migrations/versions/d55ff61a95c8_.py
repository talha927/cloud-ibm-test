"""empty message

Revision ID: d55ff61a95c8
Revises: baad9d1bd711
Create Date: 2021-09-23 19:44:59.542065

"""

# revision identifiers, used by Alembic.
revision = 'd55ff61a95c8'
down_revision = 'baad9d1bd711'

from alembic import op
import sqlalchemy as sa


def upgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.create_table('ibm_ssh_keys',
    sa.Column('id', sa.String(length=32), nullable=False),
    sa.Column('created_at', sa.DateTime(), nullable=False),
    sa.Column('name', sa.String(length=255), nullable=False),
    sa.Column('crn', sa.String(length=500), nullable=False),
    sa.Column('href', sa.Text(), nullable=False),
    sa.Column('resource_id', sa.String(length=64), nullable=False),
    sa.Column('status', sa.String(length=50), nullable=False),
    sa.Column('type', sa.Enum('rsa'), nullable=False),
    sa.Column('length', sa.Enum('2048', '4096'), nullable=False),
    sa.Column('public_key', sa.String(length=1024), nullable=False),
    sa.Column('finger_print', sa.String(length=1024), nullable=False),
    sa.Column('resource_group_id', sa.String(length=32), nullable=False),
    sa.Column('region_id', sa.String(length=32), nullable=False),
    sa.Column('cloud_id', sa.String(length=32), nullable=False),
    sa.ForeignKeyConstraint(['cloud_id'], ['ibm_clouds.id'], ),
    sa.ForeignKeyConstraint(['region_id'], ['ibm_regions.id'], ),
    sa.ForeignKeyConstraint(['resource_group_id'], ['ibm_resource_groups.id'], ),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('name', 'region_id', 'cloud_id', name='uix_ibm_ssh_name_region_id_cloud_id')
    )
    op.create_table('ibm_security_groups',
    sa.Column('id', sa.String(length=32), nullable=False),
    sa.Column('resource_id', sa.String(length=64), nullable=False),
    sa.Column('name', sa.String(length=255), nullable=False),
    sa.Column('is_default', sa.Boolean(), nullable=False),
    sa.Column('status', sa.String(length=50), nullable=False),
    sa.Column('crn', sa.String(length=255), nullable=False),
    sa.Column('href', sa.Text(), nullable=False),
    sa.Column('created_at', sa.DateTime(), nullable=False),
    sa.Column('vpc_id', sa.String(length=32), nullable=False),
    sa.Column('resource_group_id', sa.String(length=32), nullable=True),
    sa.Column('region_id', sa.String(length=32), nullable=False),
    sa.Column('cloud_id', sa.String(length=32), nullable=False),
    sa.ForeignKeyConstraint(['cloud_id'], ['ibm_clouds.id'], ),
    sa.ForeignKeyConstraint(['region_id'], ['ibm_regions.id'], ),
    sa.ForeignKeyConstraint(['resource_group_id'], ['ibm_resource_groups.id'], ),
    sa.ForeignKeyConstraint(['vpc_id'], ['ibm_vpc_networks.id'], ),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('name', 'vpc_id', 'region_id', name='uix_ibm_security_group_name_vpc_id_region_id')
    )
    op.create_table('ibm_security_group_rules',
    sa.Column('id', sa.String(length=32), nullable=False),
    sa.Column('resource_id', sa.String(length=64), nullable=False),
    sa.Column('status', sa.String(length=50), nullable=False),
    sa.Column('direction', sa.Enum('inbound', 'outbound'), nullable=False),
    sa.Column('href', sa.Text(), nullable=False),
    sa.Column('rule_type', sa.Enum('address', 'any', 'cidr_block', 'security_group'), nullable=False),
    sa.Column('protocol', sa.Enum('all', 'icmp', 'tcp', 'udp'), nullable=False),
    sa.Column('remote_cidr_block', sa.String(length=255), nullable=True),
    sa.Column('remote_ip_address', sa.String(length=255), nullable=True),
    sa.Column('ip_version', sa.Enum('ipv4'), nullable=True),
    sa.Column('tcp_udp_port_min', sa.Integer(), nullable=True),
    sa.Column('tcp_udp_port_max', sa.Integer(), nullable=True),
    sa.Column('icmp_code', sa.Integer(), nullable=True),
    sa.Column('icmp_type', sa.Integer(), nullable=True),
    sa.Column('security_group_id', sa.String(length=32), nullable=False),
    sa.Column('remote_security_group_id', sa.String(length=32), nullable=True),
    sa.ForeignKeyConstraint(['remote_security_group_id'], ['ibm_security_groups.id'], ),
    sa.ForeignKeyConstraint(['security_group_id'], ['ibm_security_groups.id'], ),
    sa.PrimaryKeyConstraint('id')
    )
    # ### end Alembic commands ###


def downgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.drop_table('ibm_security_group_rules')
    op.drop_table('ibm_security_groups')
    op.drop_table('ibm_ssh_keys')
    # ### end Alembic commands ###