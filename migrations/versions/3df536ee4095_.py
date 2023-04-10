"""empty message

Revision ID: 3df536ee4095
Revises: 314a116713b8
Create Date: 2022-09-29 10:39:56.070992

"""

# revision identifiers, used by Alembic.
revision = '3df536ee4095'
down_revision = '314a116713b8'

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import mysql

def upgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.create_table('ibm_right_sizing_recommendations',
    sa.Column('id', sa.String(length=32), nullable=False),
    sa.Column('region', sa.String(length=32), nullable=False),
    sa.Column('current_instance_type', sa.String(length=512), nullable=True),
    sa.Column('current_instance_resource_details', sa.JSON(), nullable=True),
    sa.Column('monthly_cost', sa.Float(), nullable=False),
    sa.Column('resource_id', sa.String(length=256), nullable=False),
    sa.Column('estimated_monthly_cost', sa.Float(), nullable=True),
    sa.Column('estimated_monthly_savings', sa.Float(), nullable=True),
    sa.Column('recommended_instance_type', sa.String(length=512), nullable=True),
    sa.Column('recommended_instance_resource_details', sa.JSON(), nullable=True),
    sa.Column('rightsizing_reason', sa.JSON(), nullable=True),
    sa.Column('instance_id', sa.String(length=32), nullable=False),
    sa.Column('cloud_id', sa.String(length=32), nullable=False),
    sa.ForeignKeyConstraint(['cloud_id'], ['ibm_clouds.id'], ),
    sa.ForeignKeyConstraint(['instance_id'], ['ibm_instances.id'], ),
    sa.PrimaryKeyConstraint('id')
    )
    # ### end Alembic commands ###


def downgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.drop_table('ibm_right_sizing_recommendations')
    # ### end Alembic commands ###