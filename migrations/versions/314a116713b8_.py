"""empty message

Revision ID: 314a116713b8
Revises: d8ffa03d07a7
Create Date: 2022-09-27 10:58:28.333942

"""

# revision identifiers, used by Alembic.
revision = '314a116713b8'
down_revision = 'd8ffa03d07a7'

import sqlalchemy as sa
from alembic import op


def upgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.add_column('ibm_instances', sa.Column('usage', sa.JSON(), nullable=False))
    # ### end Alembic commands ###


def downgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.drop_column('ibm_instances', 'usage')
    # ### end Alembic commands ###
