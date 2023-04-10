"""empty message

Revision ID: 7da8006eb6f1
Revises: 5dcc396b211e
Create Date: 2023-02-02 07:29:29.445003

"""

# revision identifiers, used by Alembic.
revision = '7da8006eb6f1'
down_revision = '5dcc396b211e'

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import mysql


def upgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.create_unique_constraint('uix_ibm_cos_bucket_name_cloud_object_storage_id_cloud_id', 'ibm_cos_buckets',
                                ['name', 'cloud_object_storage_id', 'cloud_id'])
    # ### end Alembic commands ###


def downgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.drop_constraint('uix_ibm_cos_bucket_name_cloud_object_storage_id_cloud_id', 'ibm_cos_buckets', type_='unique')
    # ### end Alembic commands ###
