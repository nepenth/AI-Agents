"""Add enhanced task management models

Revision ID: add_enhanced_task_management
Revises: d1ec40203de8
Create Date: 2025-07-23 20:40:00.000000

"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = 'ef11a31d1ecc'
down_revision = 'd1ec40203de8'
branch_labels = None
depends_on = None


def upgrade():
    # Add new columns to celery_task_state table (SQLite compatible)
    op.add_column('celery_task_state', sa.Column('items_processed', sa.Integer(), nullable=False, default=0))
    op.add_column('celery_task_state', sa.Column('items_failed', sa.Integer(), nullable=False, default=0))
    op.add_column('celery_task_state', sa.Column('execution_duration', sa.String(length=50), nullable=True))
    op.add_column('celery_task_state', sa.Column('is_active', sa.Boolean(), nullable=False, default=True))
    op.add_column('celery_task_state', sa.Column('is_archived', sa.Boolean(), nullable=False, default=False))
    
    # Create indexes for new columns
    op.create_index('ix_celery_task_state_is_active', 'celery_task_state', ['is_active'])
    op.create_index('ix_celery_task_state_is_archived', 'celery_task_state', ['is_archived'])
    
    # Create job_history table
    op.create_table('job_history',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('task_id', sa.String(length=36), nullable=False),
        sa.Column('job_type', sa.String(length=50), nullable=False),
        sa.Column('trigger_source', sa.String(length=100), nullable=True),
        sa.Column('execution_summary', sa.JSON(), nullable=True),
        sa.Column('phase_results', sa.JSON(), nullable=True),
        sa.Column('performance_metrics', sa.JSON(), nullable=True),
        sa.Column('user_preferences', sa.JSON(), nullable=True),
        sa.Column('system_info', sa.JSON(), nullable=True),
        sa.Column('tags', sa.JSON(), nullable=True),
        sa.Column('notes', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['task_id'], ['celery_task_state.task_id'], ),
        sa.PrimaryKeyConstraint('id')
    )
    
    # Create indexes for job_history
    op.create_index('ix_job_history_task_id', 'job_history', ['task_id'])
    op.create_index('ix_job_history_job_type', 'job_history', ['job_type'])
    op.create_index('ix_job_history_created_at', 'job_history', ['created_at'])
    
    # Update existing records to set default values (SQLite compatible)
    op.execute("UPDATE celery_task_state SET items_processed = 0 WHERE items_processed IS NULL")
    op.execute("UPDATE celery_task_state SET items_failed = 0 WHERE items_failed IS NULL")
    op.execute("UPDATE celery_task_state SET is_active = 1 WHERE is_active IS NULL")  # SQLite uses 1 for TRUE
    op.execute("UPDATE celery_task_state SET is_archived = 0 WHERE is_archived IS NULL")  # SQLite uses 0 for FALSE


def downgrade():
    # Drop job_history table
    op.drop_index('ix_job_history_created_at', table_name='job_history')
    op.drop_index('ix_job_history_job_type', table_name='job_history')
    op.drop_index('ix_job_history_task_id', table_name='job_history')
    op.drop_table('job_history')
    
    # Drop indexes from celery_task_state
    op.drop_index('ix_celery_task_state_is_archived', table_name='celery_task_state')
    op.drop_index('ix_celery_task_state_is_active', table_name='celery_task_state')
    
    # Drop new columns from celery_task_state
    op.drop_column('celery_task_state', 'is_archived')
    op.drop_column('celery_task_state', 'is_active')
    op.drop_column('celery_task_state', 'execution_duration')
    op.drop_column('celery_task_state', 'items_failed')
    op.drop_column('celery_task_state', 'items_processed')