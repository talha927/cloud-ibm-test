"""empty message

Revision ID: 54b5bbe794e5
Revises: cf82455d500c
Create Date: 2022-06-04 07:31:06.372699

"""

# revision identifiers, used by Alembic.
revision = '54b5bbe794e5'
down_revision = 'cf82455d500c'

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import mysql

def upgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.alter_column('workflows_workspaces', 'created_at',
               existing_type=mysql.DATETIME(),
               nullable=True)
    # ### end Alembic commands ###


def downgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.alter_column('workflows_workspaces', 'created_at',
               existing_type=mysql.DATETIME(),
               nullable=False)
    # ### end Alembic commands ###