"""empty message

Revision ID: d37e222074e9
Revises: 8181c8a821df
Create Date: 2023-03-23 17:13:14.304852

"""

# revision identifiers, used by Alembic.
revision = 'd37e222074e9'
down_revision = '8181c8a821df'

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import mysql

def upgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.alter_column('ibm_ike_policy', 'dh_group',
               existing_type=mysql.ENUM('14', '15', '16', '17', '18', '19', '2', '20', '21', '22', '23', '24', '31', '5'),
               nullable=False)
    op.alter_column('ibm_vpn_gateways', 'mode',
               existing_type=mysql.ENUM('route', 'policy'),
               nullable=False)
    # ### end Alembic commands ###


def downgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.alter_column('ibm_vpn_gateways', 'mode',
               existing_type=mysql.ENUM('route', 'policy'),
               nullable=True)
    op.alter_column('ibm_ike_policy', 'dh_group',
               existing_type=mysql.ENUM('14', '15', '16', '17', '18', '19', '2', '20', '21', '22', '23', '24', '31', '5'),
               nullable=True)
    # ### end Alembic commands ###