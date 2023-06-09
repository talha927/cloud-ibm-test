"""empty message

Revision ID: 5dcc396b211e
Revises: 97a3c41e3803
Create Date: 2023-02-06 06:54:01.040410

"""

# revision identifiers, used by Alembic.
revision = '5dcc396b211e'
down_revision = '97a3c41e3803'

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import mysql

def upgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.add_column('disaster_recovery_backups', sa.Column('is_volume', sa.Boolean(), nullable=True))
    # ### end Alembic commands ###


def downgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.drop_column('disaster_recovery_backups', 'is_volume')
    # ### end Alembic commands ###