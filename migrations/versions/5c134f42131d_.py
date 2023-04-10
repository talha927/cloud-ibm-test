"""empty message

Revision ID: 5c134f42131d
Revises: 05dbc3c1c8c7
Create Date: 2023-02-17 10:43:02.996871

"""

# revision identifiers, used by Alembic.
revision = '5c134f42131d'
down_revision = 'e5aea7db20c4'

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import mysql

def upgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.add_column('workflows_workspaces', sa.Column('workspace_type', sa.Enum('TYPE_SOFTLAYER', 'TYPE_TRANSLATION',
                                                                              'TYPE_RESTORE'), nullable=True))
    # ### end Alembic commands ###


def downgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.drop_column('workflows_workspaces', 'workspace_type')
    # ### end Alembic commands ###