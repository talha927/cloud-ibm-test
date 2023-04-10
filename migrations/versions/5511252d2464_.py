"""empty message

Revision ID: 5511252d2464
Revises: dda9ee9eba9a
Create Date: 2021-11-11 13:10:50.093339

"""

# revision identifiers, used by Alembic.
revision = '5511252d2464'
down_revision = 'dda9ee9eba9a'

from alembic import op
import sqlalchemy as sa


def upgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.add_column('ibm_instance_profiles', sa.Column('gpu_model', sa.JSON(), nullable=True))
    op.add_column('ibm_instance_profiles', sa.Column('gpu_count', sa.JSON(), nullable=True))
    op.add_column('ibm_instance_profiles', sa.Column('gpu_memory', sa.JSON(), nullable=True))
    op.add_column('ibm_instance_profiles', sa.Column('gpu_manufacturer', sa.JSON(), nullable=True))
    op.add_column('ibm_instance_profiles', sa.Column('total_volume_bandwidth', sa.JSON(), nullable=False))
    # ### end Alembic commands ###


def downgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.drop_column('ibm_instance_profiles', 'total_volume_bandwidth')
    op.drop_column('ibm_instance_profiles', 'gpu_manufacturer')
    op.drop_column('ibm_instance_profiles', 'gpu_memory')
    op.drop_column('ibm_instance_profiles', 'gpu_count')
    op.drop_column('ibm_instance_profiles', 'gpu_model')
    # ### end Alembic commands ###