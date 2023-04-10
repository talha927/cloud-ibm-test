"""empty message

Revision ID: e938594e9639
Revises: ccc2eafeb22b
Create Date: 2022-11-28 20:42:06.042042

"""

# revision identifiers, used by Alembic.
revision = 'e938594e9639'
down_revision = 'ccc2eafeb22b'

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import mysql

def upgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.drop_constraint('ibm_tags_ibfk_2', 'ibm_tags', type_='foreignkey')
    op.drop_column('ibm_tags', 'region_id')
    # ### end Alembic commands ###


def downgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.add_column('ibm_tags', sa.Column('region_id', mysql.VARCHAR(length=32), nullable=False))
    op.create_foreign_key('ibm_tags_ibfk_2', 'ibm_tags', 'ibm_regions', ['region_id'], ['id'])
    # ### end Alembic commands ###