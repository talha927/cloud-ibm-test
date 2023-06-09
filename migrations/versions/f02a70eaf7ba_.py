"""empty message

Revision ID: f02a70eaf7ba
Revises: 4d74f698895b
Create Date: 2021-12-23 09:20:02.403026

"""

# revision identifiers, used by Alembic.
revision = 'f02a70eaf7ba'
down_revision = '4d74f698895b'

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import mysql

def upgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.alter_column('ibm_images', 'resource_group_id',
               existing_type=mysql.VARCHAR(length=32),
               nullable=True)
    # ### end Alembic commands ###


def downgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.alter_column('ibm_images', 'resource_group_id',
               existing_type=mysql.VARCHAR(length=32),
               nullable=False)
    # ### end Alembic commands ###