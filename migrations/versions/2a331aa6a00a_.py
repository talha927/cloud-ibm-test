"""empty message

Revision ID: 2a331aa6a00a
Revises: 25c2af580510
Create Date: 2022-05-30 07:22:06.182719

"""

# revision identifiers, used by Alembic.
revision = '2a331aa6a00a'
down_revision = '25c2af580510'

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import mysql

def upgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.add_column('ibm_instance_group_manager_actions', sa.Column('run_at', sa.DateTime(), nullable=True))
    # ### end Alembic commands ###


def downgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.drop_column('ibm_instance_group_manager_actions', 'run_at')
    # ### end Alembic commands ###