"""Add seven-phase pipeline models and update content models

Revision ID: 002_pipeline_models
Revises: 001_initial_schema
Create Date: 2024-01-01 12:00:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = '002_pipeline_models'
down_revision = '001_initial_schema'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Update content_items table - remove generated_files, rename media_files to media_content
    op.drop_column('content_items', 'generated_files')
    op.alter_column('content_items', 'media_files', new_column_name='media_content')
    
    # Update knowledge_items table - remove file paths, add new content fields
    op.drop_column('knowledge_items', 'markdown_path')
    op.drop_column('knowledge_items', 'media_paths')
    op.add_column('knowledge_items', sa.Column('markdown_content', sa.Text(), nullable=True))
    op.add_column('knowledge_items', sa.Column('readme_section', sa.Text(), nullable=True))
    
    # Create readme_content table
    op.create_table('readme_content',
        sa.Column('id', sa.String(), nullable=False),
        sa.Column('content_type', sa.String(), nullable=False),
        sa.Column('category', sa.String(), nullable=True),
        sa.Column('subcategory', sa.String(), nullable=True),
        sa.Column('title', sa.String(), nullable=False),
        sa.Column('content', sa.Text(), nullable=False),
        sa.Column('item_count', sa.Integer(), nullable=False),
        sa.Column('file_path', sa.String(), nullable=False),
        sa.Column('content_hash', sa.String(), nullable=True),
        sa.Column('is_stale', sa.Boolean(), nullable=False),
        sa.Column('generation_model_used', sa.String(), nullable=True),
        sa.Column('generation_prompt', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_readme_content_content_type'), 'readme_content', ['content_type'], unique=False)
    op.create_index(op.f('ix_readme_content_category'), 'readme_content', ['category'], unique=False)
    op.create_index(op.f('ix_readme_content_subcategory'), 'readme_content', ['subcategory'], unique=False)
    op.create_index(op.f('ix_readme_content_file_path'), 'readme_content', ['file_path'], unique=False)
    op.create_index(op.f('ix_readme_content_is_stale'), 'readme_content', ['is_stale'], unique=False)
    op.create_index(op.f('ix_readme_content_created_at'), 'readme_content', ['created_at'], unique=False)
    
    # Create git_sync_operations table
    op.create_table('git_sync_operations',
        sa.Column('id', sa.String(), nullable=False),
        sa.Column('operation_type', sa.String(), nullable=False),
        sa.Column('commit_message', sa.String(), nullable=True),
        sa.Column('commit_hash', sa.String(), nullable=True),
        sa.Column('branch_name', sa.String(), nullable=True),
        sa.Column('remote_url', sa.String(), nullable=True),
        sa.Column('files_changed', sa.JSON(), nullable=False),
        sa.Column('files_added', sa.JSON(), nullable=False),
        sa.Column('files_deleted', sa.JSON(), nullable=False),
        sa.Column('files_modified', sa.JSON(), nullable=False),
        sa.Column('status', sa.String(), nullable=False),
        sa.Column('error_message', sa.Text(), nullable=True),
        sa.Column('error_code', sa.String(), nullable=True),
        sa.Column('duration_seconds', sa.Float(), nullable=True),
        sa.Column('bytes_transferred', sa.Integer(), nullable=True),
        sa.Column('config', sa.JSON(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('started_at', sa.DateTime(), nullable=True),
        sa.Column('completed_at', sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_git_sync_operations_operation_type'), 'git_sync_operations', ['operation_type'], unique=False)
    op.create_index(op.f('ix_git_sync_operations_commit_hash'), 'git_sync_operations', ['commit_hash'], unique=False)
    op.create_index(op.f('ix_git_sync_operations_status'), 'git_sync_operations', ['status'], unique=False)
    op.create_index(op.f('ix_git_sync_operations_created_at'), 'git_sync_operations', ['created_at'], unique=False)
    
    # Create pipeline_executions table
    op.create_table('pipeline_executions',
        sa.Column('id', sa.String(), nullable=False),
        sa.Column('config', sa.JSON(), nullable=False),
        sa.Column('models_override', sa.JSON(), nullable=True),
        sa.Column('current_phase', sa.Integer(), nullable=False),
        sa.Column('phase_status', sa.JSON(), nullable=False),
        sa.Column('status', sa.String(), nullable=False),
        sa.Column('progress_percentage', sa.Integer(), nullable=False),
        sa.Column('items_fetched', sa.Integer(), nullable=False),
        sa.Column('items_processed', sa.Integer(), nullable=False),
        sa.Column('synthesis_generated', sa.Integer(), nullable=False),
        sa.Column('embeddings_created', sa.Integer(), nullable=False),
        sa.Column('readme_files_generated', sa.Integer(), nullable=False),
        sa.Column('git_commits_made', sa.Integer(), nullable=False),
        sa.Column('error_message', sa.String(), nullable=True),
        sa.Column('error_phase', sa.Integer(), nullable=True),
        sa.Column('retry_count', sa.Integer(), nullable=False),
        sa.Column('total_duration_seconds', sa.Float(), nullable=True),
        sa.Column('phase_durations', sa.JSON(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('started_at', sa.DateTime(), nullable=True),
        sa.Column('completed_at', sa.DateTime(), nullable=True),
        sa.Column('paused_at', sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_pipeline_executions_current_phase'), 'pipeline_executions', ['current_phase'], unique=False)
    op.create_index(op.f('ix_pipeline_executions_status'), 'pipeline_executions', ['status'], unique=False)
    op.create_index(op.f('ix_pipeline_executions_created_at'), 'pipeline_executions', ['created_at'], unique=False)


def downgrade() -> None:
    # Drop new tables
    op.drop_table('pipeline_executions')
    op.drop_table('git_sync_operations')
    op.drop_table('readme_content')
    
    # Revert knowledge_items table changes
    op.drop_column('knowledge_items', 'readme_section')
    op.drop_column('knowledge_items', 'markdown_content')
    op.add_column('knowledge_items', sa.Column('media_paths', sa.JSON(), nullable=False))
    op.add_column('knowledge_items', sa.Column('markdown_path', sa.String(), nullable=True))
    
    # Revert content_items table changes
    op.alter_column('content_items', 'media_content', new_column_name='media_files')
    op.add_column('content_items', sa.Column('generated_files', sa.JSON(), nullable=False))