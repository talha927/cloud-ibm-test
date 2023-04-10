"""empty message

Revision ID: 4d74f698895b
Revises: 09b647a5b674
Create Date: 2021-12-01 11:22:00.885666

"""

# revision identifiers, used by Alembic.
revision = '4d74f698895b'
down_revision = '09b647a5b674'

from alembic import op
from sqlalchemy.dialects import mysql


def upgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.alter_column(
        'ibm_ike_policy', 'negotiation_mode',
        type_=mysql.ENUM('main'),
        existing_type=mysql.ENUM('negotiation_mode'),
        nullable=False
    )
    # ### end Alembic commands ###


def downgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.alter_column(
        'ibm_ike_policy', 'negotiation_mode',
        type_=mysql.ENUM('negotiation_mode'),
        existing_type=mysql.ENUM('main'),
        nullable=False
    )
    # ### end Alembic commands ###
