"""empty message

Revision ID: 475ace644cfb
Revises: 31fd4df9c318
Create Date: 2022-07-22 04:43:17.515799

"""

# revision identifiers, used by Alembic.
revision = '475ace644cfb'
down_revision = '31fd4df9c318'

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import mysql


new_type = sa.Enum("standard","smart", "flex", "cold", "vault", name="type")
old_type = sa.Enum("standard","smart", name="type")


def upgrade():
    op.alter_column('ibm_cos_buckets', u'type', type_=new_type,
                    existing_type=old_type)


def downgrade():
    op.alter_column('ibm_cos_buckets', u'type', type_=old_type,
                    existing_type=new_type)
