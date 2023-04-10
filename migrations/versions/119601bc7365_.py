"""empty message

Revision ID: 119601bc7365
Revises: d57adec6ee15
Create Date: 2022-03-11 05:52:06.683625

"""

# revision identifiers, used by Alembic.
revision = '119601bc7365'
down_revision = 'd57adec6ee15'

from alembic import op
import sqlalchemy as sa


def upgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.create_table('ibm_costs',
    sa.Column('id', sa.String(length=32), nullable=False),
    sa.Column('account_id', sa.String(length=255), nullable=False),
    sa.Column('billing_month', sa.DateTime(), nullable=False),
    sa.Column('billable_cost', sa.Float(), nullable=False),
    sa.Column('non_billable_cost', sa.Float(), nullable=False),
    sa.Column('billing_country_code', sa.String(length=255), nullable=False),
    sa.Column('billing_currency_code', sa.String(length=255), nullable=False),
    sa.Column('cloud_id', sa.String(length=32), nullable=False),
    sa.ForeignKeyConstraint(['cloud_id'], ['ibm_clouds.id'], ),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_table('ibm_individual_resource_costs',
    sa.Column('id', sa.String(length=32), nullable=False),
    sa.Column('resource_id', sa.String(length=255), nullable=False),
    sa.Column('billable_cost', sa.Float(), nullable=False),
    sa.Column('non_billable_cost', sa.Float(), nullable=False),
    sa.Column('resource_name', sa.String(length=255), nullable=True),
    sa.Column('cost_id', sa.String(length=32), nullable=False),
    sa.ForeignKeyConstraint(['cost_id'], ['ibm_costs.id'], ),
    sa.PrimaryKeyConstraint('id')
    )
    # ### end Alembic commands ###


def downgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.drop_table('ibm_individual_resource_costs')
    op.drop_table('ibm_costs')
    # ### end Alembic commands ###