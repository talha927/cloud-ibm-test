"""empty message

Revision ID: ff07799f0639
Revises: None
Create Date: 2021-09-23 12:22:31.353728

"""

# revision identifiers, used by Alembic.
revision = 'ff07799f0639'
down_revision = None

from alembic import op
import sqlalchemy as sa


def upgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.create_table('workflow_roots',
    sa.Column('id', sa.String(length=32), nullable=False),
    sa.Column('status', sa.Enum('ON_HOLD', 'PENDING', 'INITIATED', 'RUNNING', 'COMPLETED_SUCCESSFULLY', 'COMPLETED_SUCCESSFULLY_WFC', 'COMPLETED_WITH_FAILURE', 'COMPLETED_WITH_FAILURE_WFC'), nullable=False),
    sa.Column('workflow_name', sa.String(length=128), nullable=True),
    sa.Column('root_type', sa.Enum('NORMAL', 'ON_SUCCESS', 'ON_FAILURE', 'ON_COMPLETE'), nullable=True),
    sa.Column('workflow_nature', sa.String(length=128), nullable=True),
    sa.Column('fe_request_data', sa.JSON(), nullable=True),
    sa.Column('executor_running', sa.Boolean(), nullable=False),
    sa.Column('created_at', sa.DateTime(), nullable=False),
    sa.Column('initiated_at', sa.DateTime(), nullable=True),
    sa.Column('started_at', sa.DateTime(), nullable=True),
    sa.Column('completed_at', sa.DateTime(), nullable=True),
    sa.Column('user_id', sa.String(length=32), nullable=False),
    sa.Column('project_id', sa.String(length=32), nullable=False),
    sa.Column('parent_root_copy', sa.JSON(), nullable=True),
    sa.Column('hold_parent_status_update', sa.Boolean(), nullable=True),
    sa.Column('parent_root_id', sa.String(length=32), nullable=True),
    sa.ForeignKeyConstraint(['parent_root_id'], ['workflow_roots.id'], ),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_table('workflow_tasks',
    sa.Column('id', sa.String(length=32), nullable=False),
    sa.Column('resource_id', sa.String(length=32), nullable=True),
    sa.Column('resource_type', sa.String(length=512), nullable=False),
    sa.Column('task_type', sa.String(length=512), nullable=False),
    sa.Column('task_metadata', sa.JSON(), nullable=True),
    sa.Column('status', sa.Enum('PENDING', 'INITIATED', 'RUNNING', 'RUNNING_WAIT', 'RUNNING_WAIT_INITIATED', 'SUCCESSFUL', 'FAILED'), nullable=False),
    sa.Column('message', sa.String(length=1024), nullable=True),
    sa.Column('in_focus', sa.Boolean(), nullable=False),
    sa.Column('created_at', sa.DateTime(), nullable=False),
    sa.Column('initiated_at', sa.DateTime(), nullable=True),
    sa.Column('started_at', sa.DateTime(), nullable=True),
    sa.Column('completed_at', sa.DateTime(), nullable=True),
    sa.Column('root_id', sa.String(length=32), nullable=False),
    sa.ForeignKeyConstraint(['root_id'], ['workflow_roots.id'], ),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_table('workflow_tree_mappings',
    sa.Column('task_id', sa.String(length=32), nullable=False),
    sa.Column('next_task_id', sa.String(length=32), nullable=False),
    sa.ForeignKeyConstraint(['next_task_id'], ['workflow_tasks.id'], ),
    sa.ForeignKeyConstraint(['task_id'], ['workflow_tasks.id'], )
    )
    # ### end Alembic commands ###


def downgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.drop_table('workflow_tree_mappings')
    op.drop_table('workflow_tasks')
    op.drop_table('workflow_roots')
    # ### end Alembic commands ###