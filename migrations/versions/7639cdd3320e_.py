"""empty message

Revision ID: 7639cdd3320e
Revises: 4963f81101e6
Create Date: 2021-09-23 18:00:46.352714

"""

# revision identifiers, used by Alembic.
revision = '7639cdd3320e'
down_revision = '4963f81101e6'

from alembic import op
import sqlalchemy as sa


def upgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.create_table('ibm_regions',
    sa.Column('id', sa.String(length=32), nullable=False),
    sa.Column('endpoint', sa.String(length=64), nullable=False),
    sa.Column('href', sa.Text(), nullable=False),
    sa.Column('name', sa.String(length=255), nullable=False),
    sa.Column('ibm_status', sa.Enum('available', 'unavailable'), nullable=False),
    sa.Column('cloud_id', sa.String(length=32), nullable=False),
    sa.ForeignKeyConstraint(['cloud_id'], ['ibm_clouds.id'], ),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('name', 'cloud_id', name='uix_ibm_region_name_cloud_id')
    )
    op.create_table('ibm_zones',
    sa.Column('id', sa.String(length=32), nullable=False),
    sa.Column('href', sa.Text(), nullable=False),
    sa.Column('name', sa.String(length=255), nullable=False),
    sa.Column('ibm_status', sa.Enum('available', 'impaired', 'unavailable'), nullable=False),
    sa.Column('region_id', sa.String(length=32), nullable=False),
    sa.Column('cloud_id', sa.String(length=32), nullable=False),
    sa.ForeignKeyConstraint(['cloud_id'], ['ibm_clouds.id'], ),
    sa.ForeignKeyConstraint(['region_id'], ['ibm_regions.id'], ),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('name', 'region_id', name='uix_ibm_zone_name_region_id')
    )
    # ### end Alembic commands ###


def downgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.drop_table('ibm_zones')
    op.drop_table('ibm_regions')
    # ### end Alembic commands ###