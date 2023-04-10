"""empty message

Revision ID: bed66d766c12
Revises: 667924baab01
Create Date: 2022-10-24 10:15:28.913571

"""

# revision identifiers, used by Alembic.
revision = 'bed66d766c12'
down_revision = '667924baab01'

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import mysql

def upgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.create_unique_constraint('uix_ibm_resource_id_cloud_id', 'ibm_kubernetes_clusters', ['resource_id', 'cloud_id'])
    # ### end Alembic commands ###


def downgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.drop_constraint('uix_ibm_resource_id_cloud_id', 'ibm_kubernetes_clusters', type_='unique')
    # ### end Alembic commands ###