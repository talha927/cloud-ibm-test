"""empty message

Revision ID: 31fd4df9c318
Revises: ef01ca0797d0
Create Date: 2022-07-19 14:24:38.038023

"""

# revision identifiers, used by Alembic.
revision = '31fd4df9c318'
down_revision = 'ef01ca0797d0'

from alembic import op
from sqlalchemy.dialects import mysql


def upgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.alter_column('ibm_kubernetes_clusters', 'ibm_state',
                    existing_type=mysql.ENUM('normal', 'deploying', 'deleting', 'deploy_failed', 'pending', 'warning'),
                    type_=mysql.ENUM('normal', 'deploying', 'deleting', 'deploy_failed', 'pending', 'warning',
                                     'critical'))  # ### end Alembic commands ###


def downgrade():
    # ### commands auto generated by Alembic - please adjust! ### # ### end Alembic commands ###
    op.alter_column('ibm_kubernetes_clusters', 'ibm_state',
                    existing_type=mysql.ENUM('normal', 'deploying', 'deleting', 'deploy_failed', 'pending', 'warning',
                                             'critical'), existing_nullable=False,
                    type_=mysql.ENUM('normal', 'deploying', 'deleting', 'deploy_failed', 'pending', 'warning'), )
