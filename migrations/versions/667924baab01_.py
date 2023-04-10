"""empty message

Revision ID: 667924baab01
Revises: 9704abaa163d
Create Date: 2022-10-22 08:49:58.883235

"""

# revision identifiers, used by Alembic.
revision = '667924baab01'
down_revision = '9704abaa163d'

import sqlalchemy as sa
from alembic import op


def upgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.add_column('ibm_dashboard_settings', sa.Column('order', sa.Integer(), nullable=True))
    # ### end Alembic commands ###


def downgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.drop_column('ibm_dashboard_settings', 'order')
    # ### end Alembic commands ###
