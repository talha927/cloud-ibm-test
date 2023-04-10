"""empty message

Revision ID: 2e021ba9f5f2
Revises: 9737b29697ac
Create Date: 2022-01-10 06:38:38.968605

"""

# revision identifiers, used by Alembic.
revision = '2e021ba9f5f2'
down_revision = '9737b29697ac'

import sqlalchemy as sa
from alembic import op


def upgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.create_table('ibm_kubernetes_clusters',
                    sa.Column('id', sa.String(length=32), nullable=False),
                    sa.Column('name', sa.String(length=32), nullable=False),
                    sa.Column('pod_subnet', sa.String(length=255), nullable=True),
                    sa.Column('service_subnet', sa.String(length=255), nullable=True),
                    sa.Column('master_kube_version', sa.String(length=255), nullable=False),
                    sa.Column('disable_public_service_endpoint', sa.Boolean(), nullable=False),
                    sa.Column('state', sa.String(length=255), nullable=True),
                    sa.Column('ibm_status', sa.Enum('normal', 'deploying', 'deleting', 'failed', 'pending'),
                              nullable=True),
                    sa.Column('provider', sa.String(length=50), nullable=False),
                    sa.Column('cluster_type', sa.Enum('openshift', 'kubernetes'), nullable=True),
                    sa.Column('resource_id', sa.String(length=64), nullable=False),
                    sa.Column('workloads', sa.JSON(), nullable=True),
                    sa.Column('ingress', sa.JSON(), nullable=True),
                    sa.Column('service_endpoint', sa.JSON(), nullable=True),
                    sa.Column('resource_group_id', sa.String(length=32), nullable=True),
                    sa.Column('vpc_id', sa.String(length=32), nullable=False),
                    sa.Column('region_id', sa.String(length=32), nullable=False),
                    sa.Column('cloud_id', sa.String(length=32), nullable=False),
                    sa.ForeignKeyConstraint(['cloud_id'], ['ibm_clouds.id'], ),
                    sa.ForeignKeyConstraint(['region_id'], ['ibm_regions.id'], ),
                    sa.ForeignKeyConstraint(['resource_group_id'], ['ibm_resource_groups.id'], ),
                    sa.ForeignKeyConstraint(['vpc_id'], ['ibm_vpc_networks.id'], ),
                    sa.PrimaryKeyConstraint('id')
                    )
    op.create_table('ibm_kubernetes_cluster_worker_pools',
                    sa.Column('id', sa.String(length=32), nullable=False),
                    sa.Column('name', sa.String(length=32), nullable=False),
                    sa.Column('disk_encryption', sa.Boolean(), nullable=False),
                    sa.Column('flavor', sa.String(length=255), nullable=False),
                    sa.Column('worker_count', sa.String(length=32), nullable=False),
                    sa.Column('resource_id', sa.String(length=64), nullable=False),
                    sa.Column('kubernetes_cluster_id', sa.String(length=32), nullable=False),
                    sa.ForeignKeyConstraint(['kubernetes_cluster_id'], ['ibm_kubernetes_clusters.id'], ),
                    sa.PrimaryKeyConstraint('id')
                    )
    op.create_table('ibm_kubernetes_cluster_worker_pool_zones',
                    sa.Column('id', sa.String(length=32), nullable=False),
                    sa.Column('name', sa.String(length=32), nullable=False),
                    sa.Column('private_vlan', sa.String(length=255), nullable=True),
                    sa.Column('worker_pool_id', sa.String(length=32), nullable=True),
                    sa.ForeignKeyConstraint(['worker_pool_id'], ['ibm_kubernetes_cluster_worker_pools.id'], ),
                    sa.PrimaryKeyConstraint('id')
                    )
    op.create_table('ibm_kubernetes_cluster_zone_subnets',
                    sa.Column('zone_id', sa.String(length=32), nullable=False),
                    sa.Column('subnets_id', sa.String(length=32), nullable=False),
                    sa.ForeignKeyConstraint(['subnets_id'], ['ibm_subnets.id'], ),
                    sa.ForeignKeyConstraint(['zone_id'], ['ibm_kubernetes_cluster_worker_pool_zones.id'], ),
                    sa.PrimaryKeyConstraint('zone_id', 'subnets_id')
                    )

    # ### end Alembic commands ###


def downgrade():
    # ### commands auto generated by Alembic - please adjust! ###

    op.drop_table('ibm_kubernetes_cluster_zone_subnets')
    op.drop_table('ibm_kubernetes_cluster_worker_pool_zones')
    op.drop_table('ibm_kubernetes_cluster_worker_pools')
    op.drop_table('ibm_kubernetes_clusters')
    # ### end Alembic commands ###
