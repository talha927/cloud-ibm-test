"""empty message

Revision ID: 7de3158dd33e
Revises: f876524fb5ff
Create Date: 2022-02-23 07:22:52.258213

"""

# revision identifiers, used by Alembic.
revision = '7de3158dd33e'
down_revision = 'f876524fb5ff'

from alembic import op
import sqlalchemy as sa


def upgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.alter_column('ibm_subnet_reserved_ips', 'target_id',
                    existing_type=sa.String(length=32),
                    nullable=True)
    # ### end Alembic commands ###


def downgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.alter_column('ibm_subnet_reserved_ips', 'target_id',
                    existing_type=sa.String(length=32),
                    nullable=False)
    # ### end Alembic commands ###