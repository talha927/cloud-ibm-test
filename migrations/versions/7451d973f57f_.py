"""empty message

Revision ID: 7451d973f57f
Revises: 2342618d6c81
Create Date: 2022-06-27 11:24:09.759687

"""

# revision identifiers, used by Alembic.
revision = '7451d973f57f'
down_revision = '2342618d6c81'

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import mysql

def upgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.add_column('workflows_workspaces', sa.Column('recently_provisioned_roots', sa.JSON(), nullable=True))
    # ### end Alembic commands ###


def downgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.drop_column('workflows_workspaces', 'recently_provisioned_roots')
    # ### end Alembic commands ###