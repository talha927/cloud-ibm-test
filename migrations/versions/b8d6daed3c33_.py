"""empty message

Revision ID: b8d6daed3c33
Revises: 609df09ab230
Create Date: 2022-08-22 17:27:14.968120

"""

# revision identifiers, used by Alembic.
revision = 'b8d6daed3c33'
down_revision = '609df09ab230'

from alembic import op
from sqlalchemy.dialects import mysql


def upgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.alter_column('ibm_subnets', 'routing_table_id',
                    existing_type=mysql.VARCHAR(length=32),
                    nullable=True)
    # ### end Alembic commands ###


def downgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.alter_column('ibm_vpn_gateways', 'mode',
                    existing_type=mysql.ENUM('route', 'policy'),
                    nullable=True)
    # ### end Alembic commands ###
