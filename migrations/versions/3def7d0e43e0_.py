"""empty message

Revision ID: 3def7d0e43e0
Revises: 85278b9fadd7
Create Date: 2022-01-16 16:16:25.871287

"""

# revision identifiers, used by Alembic.
revision = '3def7d0e43e0'
down_revision = '85278b9fadd7'

from alembic import op
import sqlalchemy as sa


def upgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.add_column('ibm_routing_table_routes', sa.Column('action', sa.Enum('delegate', 'delegate_vpc', 'deliver', 'drop'), nullable=True))
    # ### end Alembic commands ###


def downgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.drop_column('ibm_routing_table_routes', 'action')
    # ### end Alembic commands ###