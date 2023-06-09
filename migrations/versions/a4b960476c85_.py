"""empty message

Revision ID: a4b960476c85
Revises: 522ca0951e12
Create Date: 2023-03-08 04:52:16.807029

"""

# revision identifiers, used by Alembic.
revision = 'a4b960476c85'
down_revision = '522ca0951e12'

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import mysql

def upgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.create_table('on_prem_clusters',
    sa.Column('id', sa.String(length=32), nullable=False),
    sa.Column('name', sa.String(length=255), nullable=False),
    sa.Column('server_ip', sa.String(length=255), nullable=False),
    sa.Column('client_certificate_data', sa.Text(), nullable=False),
    sa.Column('client_key_data', sa.Text(), nullable=False),
    sa.Column('worker_count', sa.Integer(), nullable=True),
    sa.Column('kube_version', sa.String(length=255), nullable=True),
    sa.Column('created_at', sa.DateTime(), nullable=True),
    sa.Column('cos', sa.JSON(), nullable=True),
    sa.Column('workloads', sa.JSON(), nullable=True),
    sa.Column('kube_config', sa.JSON(), nullable=True),
    sa.Column('cluster_type', sa.Enum('openshift', 'kubernetes'), nullable=True),
    sa.Column('agent_id', sa.String(length=100), nullable=False),
    sa.Column('region_id', sa.String(length=32), nullable=True),
    sa.Column('cloud_id', sa.String(length=32), nullable=True),
    sa.ForeignKeyConstraint(['cloud_id'], ['ibm_clouds.id'], ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['region_id'], ['ibm_regions.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id')
    )

    # ### end Alembic commands ###


def downgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.drop_table('on_prem_clusters')
    # ### end Alembic commands ###