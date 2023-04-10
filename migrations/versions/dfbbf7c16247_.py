"""empty message

Revision ID: dfbbf7c16247
Revises: c042664dd260
Create Date: 2022-09-15 07:59:28.415600

"""

# revision identifiers, used by Alembic.
revision = 'dfbbf7c16247'
down_revision = 'c042664dd260'

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import mysql

def upgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.create_table('ibm_tags',
    sa.Column('id', sa.String(length=32), nullable=False),
    sa.Column('name', sa.String(length=500), nullable=False),
    sa.Column('tag_type', sa.String(length=50), nullable=False),
    sa.Column('resource_id', sa.String(length=32), nullable=False),
    sa.Column('resource_type', sa.String(length=32), nullable=False),
    sa.Column('region_id', sa.String(length=32), nullable=False),
    sa.Column('cloud_id', sa.String(length=32), nullable=False),
    sa.ForeignKeyConstraint(['cloud_id'], ['ibm_clouds.id'], ),
    sa.ForeignKeyConstraint(['region_id'], ['ibm_regions.id'], ),
    sa.PrimaryKeyConstraint('id')
    )
    # ### end Alembic commands ###


def downgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.drop_table('ibm_tags')
    # ### end Alembic commands ###