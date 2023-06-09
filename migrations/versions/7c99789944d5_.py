"""empty message

Revision ID: 7c99789944d5
Revises: bed66d766c12
Create Date: 2022-10-13 11:15:40.295813

"""

# revision identifiers, used by Alembic.
revision = '7c99789944d5'
down_revision = 'bed66d766c12'

from alembic import op
import sqlalchemy as sa


def upgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.create_table('ibm_release_notes',
    sa.Column('id', sa.String(length=32), nullable=False),
    sa.Column('title', sa.String(length=255), nullable=False),
    sa.Column('body', sa.JSON(), nullable=False),
    sa.Column('release_date', sa.DateTime(), nullable=False),
    sa.Column('url', sa.String(length=255), nullable=True),
    sa.Column('version', sa.String(length=32), nullable=True),
    sa.PrimaryKeyConstraint('id')
    )
    # ### end Alembic commands ###


def downgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.drop_table('ibm_release_notes')
    # ### end Alembic commands ###