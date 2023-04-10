"""empty message

Revision ID: 56ef3d13056d
Revises: d55ff61a95c8
Create Date: 2021-09-23 20:27:44.083230

"""

# revision identifiers, used by Alembic.
revision = '56ef3d13056d'
down_revision = 'd55ff61a95c8'

from alembic import op
import sqlalchemy as sa


def upgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.create_table('ibm_placement_groups',
    sa.Column('id', sa.String(length=32), nullable=False),
    sa.Column('created_at', sa.DateTime(), nullable=False),
    sa.Column('crn', sa.String(length=255), nullable=False),
    sa.Column('href', sa.Text(), nullable=False),
    sa.Column('resource_id', sa.String(length=255), nullable=False),
    sa.Column('lifecycle_state', sa.Enum('deleting', 'failed', 'pending', 'stable', 'updating', 'waiting', 'suspended'), nullable=False),
    sa.Column('name', sa.String(length=255), nullable=False),
    sa.Column('resource_type', sa.Enum('placement_group'), nullable=False),
    sa.Column('strategy', sa.Enum('placement_group'), nullable=False),
    sa.Column('resource_group_id', sa.String(length=32), nullable=False),
    sa.Column('region_id', sa.String(length=32), nullable=False),
    sa.Column('cloud_id', sa.String(length=32), nullable=False),
    sa.ForeignKeyConstraint(['cloud_id'], ['ibm_clouds.id'], ),
    sa.ForeignKeyConstraint(['region_id'], ['ibm_regions.id'], ),
    sa.ForeignKeyConstraint(['resource_group_id'], ['ibm_resource_groups.id'], ),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('name', 'region_id', 'cloud_id', name='uix_ibm_placement_groups_name_region_id_cloud_id')
    )
    # ### end Alembic commands ###


def downgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.drop_table('ibm_placement_groups')
    # ### end Alembic commands ###