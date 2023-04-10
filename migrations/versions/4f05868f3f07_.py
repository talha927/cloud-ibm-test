"""empty message

Revision ID: 4f05868f3f07
Revises: 57ca7b892613
Create Date: 2021-12-09 10:44:40.872419

"""

# revision identifiers, used by Alembic.
revision = '4f05868f3f07'
down_revision = '57ca7b892613'

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import mysql

def upgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.add_column('ibm_load_balancer_profiles', sa.Column('route_mode_supported_type', sa.Enum('fixed', 'dependent'), nullable=False))
    op.add_column('ibm_load_balancer_profiles', sa.Column('route_mode_supported_value', sa.Boolean(), nullable=True))
    op.add_column('ibm_load_balancers', sa.Column('route_mode', sa.Boolean(), nullable=False))
    op.alter_column('ibm_load_balancer_profiles', 'security_groups_supported_type',
                    existing_type=mysql.ENUM('fixed', 'dependent'),
                    nullable=True)
    # ### end Alembic commands ###


def downgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.alter_column('ibm_load_balancer_profiles', 'security_groups_supported_type',
                    existing_type=mysql.ENUM('fixed', 'dependent'),
                    nullable=False)
    op.drop_column('ibm_load_balancers', 'route_mode')
    op.drop_column('ibm_load_balancer_profiles', 'route_mode_supported_value')
    op.drop_column('ibm_load_balancer_profiles', 'route_mode_supported_type')
    # ### end Alembic commands ###