"""empty message

Revision ID: ae4b032cc160
Revises: 2a331aa6a00a
Create Date: 2022-06-09 16:37:04.015378

"""

# revision identifiers, used by Alembic.
revision = 'ae4b032cc160'
down_revision = '2a331aa6a00a'

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import mysql

def upgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.alter_column('ibm_load_balancer_profiles', 'cloud_id' ,existing_type=mysql.VARCHAR(length=32), nullable=True)
    op.drop_index('uix_load_balancer_profile_name_cloud_id', table_name='ibm_load_balancer_profiles')
    op.drop_constraint('ibm_load_balancer_profiles_ibfk_1', 'ibm_load_balancer_profiles', type_='foreignkey')
    op.create_unique_constraint('uc_load_balancer_profile_name', 'ibm_load_balancer_profiles', ['name'])
    op.drop_column('ibm_load_balancer_profiles', 'cloud_id')
    # ### end Alembic commands ###


def downgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.add_column('ibm_load_balancer_profiles', sa.Column('cloud_id', mysql.VARCHAR(length=32), nullable=False))
    op.drop_constraint('uc_load_balancer_profile_name', 'ibm_load_balancer_profiles', type_='unique')
    op.create_foreign_key('ibm_load_balancer_profiles_ibfk_1', 'ibm_load_balancer_profiles', 'ibm_clouds', ['cloud_id'], ['id'])
    op.create_index('uix_load_balancer_profile_name_cloud_id', 'ibm_load_balancer_profiles', ['name', 'cloud_id'], unique=False)
    op.alter_column('ibm_load_balancer_profiles', 'cloud_id', existing_type=mysql.VARCHAR(length=32), nullable=False)

    # ### end Alembic commands ###