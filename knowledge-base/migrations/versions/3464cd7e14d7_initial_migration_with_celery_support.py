"""Initial migration with Celery support

Revision ID: 3464cd7e14d7
Revises: 
Create Date: 2025-07-09 16:10:24.075259

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '3464cd7e14d7'
down_revision = None
branch_labels = None
depends_on = None


def upgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.create_table('celery_task_state',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('task_id', sa.String(length=36), nullable=False),
    sa.Column('celery_task_id', sa.String(length=36), nullable=True),
    sa.Column('task_type', sa.String(length=100), nullable=False),
    sa.Column('status', sa.String(length=20), nullable=False),
    sa.Column('current_phase_id', sa.String(length=50), nullable=True),
    sa.Column('current_phase_message', sa.Text(), nullable=True),
    sa.Column('progress_percentage', sa.Integer(), nullable=True),
    sa.Column('preferences', sa.JSON(), nullable=True),
    sa.Column('result_data', sa.JSON(), nullable=True),
    sa.Column('error_message', sa.Text(), nullable=True),
    sa.Column('traceback', sa.Text(), nullable=True),
    sa.Column('created_at', sa.DateTime(), nullable=True),
    sa.Column('started_at', sa.DateTime(), nullable=True),
    sa.Column('updated_at', sa.DateTime(), nullable=True),
    sa.Column('completed_at', sa.DateTime(), nullable=True),
    sa.PrimaryKeyConstraint('id')
    )
    with op.batch_alter_table('celery_task_state', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_celery_task_state_celery_task_id'), ['celery_task_id'], unique=False)
        batch_op.create_index(batch_op.f('ix_celery_task_state_status'), ['status'], unique=False)
        batch_op.create_index(batch_op.f('ix_celery_task_state_task_id'), ['task_id'], unique=True)
        batch_op.create_index(batch_op.f('ix_celery_task_state_task_type'), ['task_type'], unique=False)

    with op.batch_alter_table('agent_state', schema=None) as batch_op:
        batch_op.add_column(sa.Column('current_task_id', sa.String(length=36), nullable=True))
        batch_op.add_column(sa.Column('task_queue_size', sa.Integer(), nullable=True))
        batch_op.create_foreign_key('fk_agent_state_current_task_id', 'celery_task_state', ['current_task_id'], ['task_id'])

    with op.batch_alter_table('subcategory_synthesis', schema=None) as batch_op:
        batch_op.alter_column('synthesis_short_name',
               existing_type=sa.VARCHAR(length=50),
               type_=sa.String(length=255),
               existing_nullable=True)

    # ### end Alembic commands ###


def downgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    with op.batch_alter_table('subcategory_synthesis', schema=None) as batch_op:
        batch_op.alter_column('synthesis_short_name',
               existing_type=sa.String(length=255),
               type_=sa.VARCHAR(length=50),
               existing_nullable=True)

    with op.batch_alter_table('agent_state', schema=None) as batch_op:
        batch_op.drop_constraint('fk_agent_state_current_task_id', type_='foreignkey')
        batch_op.drop_column('task_queue_size')
        batch_op.drop_column('current_task_id')

    with op.batch_alter_table('celery_task_state', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_celery_task_state_task_type'))
        batch_op.drop_index(batch_op.f('ix_celery_task_state_task_id'))
        batch_op.drop_index(batch_op.f('ix_celery_task_state_status'))
        batch_op.drop_index(batch_op.f('ix_celery_task_state_celery_task_id'))

    op.drop_table('celery_task_state')
    # ### end Alembic commands ###
