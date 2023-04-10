"""empty message

Revision ID: 93d2a693a6ab
Revises: d79fc8b34aa1
Create Date: 2022-04-27 11:03:31.184966

"""

# revision identifiers, used by Alembic.
revision = '93d2a693a6ab'
down_revision = 'd79fc8b34aa1'

from alembic import op
import sqlalchemy as sa


def upgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.add_column('ibm_dashboard_settings', sa.Column('cloud_id', sa.String(length=32), nullable=False))
    op.create_foreign_key("cloud_constraint_name", 'ibm_dashboard_settings', 'ibm_clouds', ['cloud_id'], ['id'])
    # ### end Alembic commands ###


def downgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.drop_constraint("cloud_constraint_name", 'ibm_dashboard_settings', type_='foreignkey')
    op.drop_column('ibm_dashboard_settings', 'cloud_id')
    # ### end Alembic commands ###