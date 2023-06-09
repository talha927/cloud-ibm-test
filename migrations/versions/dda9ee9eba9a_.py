"""empty message

Revision ID: dda9ee9eba9a
Revises: feac18492e5a
Create Date: 2021-11-11 05:12:13.273825

"""

# revision identifiers, used by Alembic.
revision = 'dda9ee9eba9a'
down_revision = 'feac18492e5a'

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import mysql

def upgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.alter_column('ibm_subnets', 'network_acl_id',
               existing_type=mysql.VARCHAR(length=32),
               nullable=False)
    op.alter_column('ibm_subnets', 'resource_group_id',
               existing_type=mysql.VARCHAR(length=32),
               nullable=False)
    op.alter_column('ibm_subnets', 'routing_table_id',
               existing_type=mysql.VARCHAR(length=32),
               nullable=False)
    # ### end Alembic commands ###


def downgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.alter_column('ibm_subnets', 'routing_table_id',
               existing_type=mysql.VARCHAR(length=32),
               nullable=True)
    op.alter_column('ibm_subnets', 'resource_group_id',
               existing_type=mysql.VARCHAR(length=32),
               nullable=True)
    op.alter_column('ibm_subnets', 'network_acl_id',
               existing_type=mysql.VARCHAR(length=32),
               nullable=True)
    # ### end Alembic commands ###