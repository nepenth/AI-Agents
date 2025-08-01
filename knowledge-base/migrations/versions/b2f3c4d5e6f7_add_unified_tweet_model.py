"""Add unified tweet model for single source of truth architecture

Revision ID: b2f3c4d5e6f7
Revises: a1b2c3d4e5f6
Create Date: 2025-07-29 12:00:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = 'b2f3c4d5e6f7'
down_revision = 'a1b2c3d4e5f6'
branch_labels = None
depends_on = None

def get_json_type():
    """Get appropriate JSON type for the database."""
    try:
        # Try PostgreSQL JSONB first (best performance)
        return postgresql.JSONB(astext_type=sa.Text())
    except:
        try:
            # Fall back to standard JSON
            return sa.JSON()
        except:
            # Final fallback to Text for SQLite
            return sa.Text()

def upgrade():
    # Create unified_tweet table
    op.create_table('unified_tweet',
        # === PRIMARY IDENTIFICATION ===
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('tweet_id', sa.String(length=50), nullable=False),
        sa.Column('bookmarked_tweet_id', sa.String(length=50), nullable=False),
        
        # === PIPELINE PROCESSING FLAGS ===
        sa.Column('urls_expanded', sa.Boolean(), nullable=True),
        sa.Column('cache_complete', sa.Boolean(), nullable=True),
        sa.Column('media_processed', sa.Boolean(), nullable=True),
        sa.Column('categories_processed', sa.Boolean(), nullable=True),
        sa.Column('kb_item_created', sa.Boolean(), nullable=True),
        sa.Column('kb_item_written_to_disk', sa.Boolean(), nullable=True),
        sa.Column('processing_complete', sa.Boolean(), nullable=True),
        
        # === CONTENT DATA (ALL JSON) ===
        sa.Column('raw_tweet_data', get_json_type(), nullable=True),
        sa.Column('thread_tweets', get_json_type(), nullable=True),
        sa.Column('is_thread', sa.Boolean(), nullable=True),
        sa.Column('full_text', sa.Text(), nullable=True),
        sa.Column('urls_expanded_data', get_json_type(), nullable=True),
        sa.Column('media_files', get_json_type(), nullable=True),
        sa.Column('image_descriptions', get_json_type(), nullable=True),
        
        # === CATEGORIZATION DATA ===
        sa.Column('main_category', sa.String(length=100), nullable=True),
        sa.Column('sub_category', sa.String(length=100), nullable=True),
        sa.Column('categories_raw_response', get_json_type(), nullable=True),
        
        # === KNOWLEDGE BASE DATA ===
        sa.Column('kb_title', sa.Text(), nullable=True),
        sa.Column('kb_display_title', sa.Text(), nullable=True),
        sa.Column('kb_description', sa.Text(), nullable=True),
        sa.Column('kb_content', sa.Text(), nullable=True),
        sa.Column('kb_item_name', sa.Text(), nullable=True),
        sa.Column('kb_file_path', sa.Text(), nullable=True),
        sa.Column('kb_media_paths', get_json_type(), nullable=True),
        
        # === METADATA ===
        sa.Column('source', sa.String(length=50), nullable=True),
        sa.Column('source_url', sa.Text(), nullable=True),
        
        # === ERROR TRACKING ===
        sa.Column('processing_errors', get_json_type(), nullable=True),
        sa.Column('retry_count', sa.Integer(), nullable=True),
        sa.Column('last_error', sa.Text(), nullable=True),
        sa.Column('kbitem_error', sa.Text(), nullable=True),
        sa.Column('llm_error', sa.Text(), nullable=True),
        
        # === REPROCESSING CONTROLS ===
        sa.Column('force_reprocess_pipeline', sa.Boolean(), nullable=True),
        sa.Column('force_recache', sa.Boolean(), nullable=True),
        sa.Column('reprocess_requested_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('reprocess_requested_by', sa.String(length=100), nullable=True),
        sa.Column('recategorization_attempts', sa.Integer(), nullable=True),
        
        # === RUNTIME FLAGS (for backward compatibility) ===
        sa.Column('cache_succeeded_this_run', sa.Boolean(), nullable=True),
        sa.Column('media_succeeded_this_run', sa.Boolean(), nullable=True),
        sa.Column('llm_succeeded_this_run', sa.Boolean(), nullable=True),
        sa.Column('kbitem_succeeded_this_run', sa.Boolean(), nullable=True),
        sa.Column('db_synced', sa.Boolean(), nullable=True),
        
        # === TIMESTAMPS ===
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=True),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=True),
        sa.Column('cached_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('processed_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('kb_generated_at', sa.DateTime(timezone=True), nullable=True),
        
        # Constraints
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('tweet_id')
    )
    
    # Create indexes for performance
    op.create_index('ix_unified_tweet_tweet_id', 'unified_tweet', ['tweet_id'])
    op.create_index('ix_unified_tweet_main_category', 'unified_tweet', ['main_category'])
    op.create_index('ix_unified_tweet_processing_flags', 'unified_tweet', 
                   ['cache_complete', 'media_processed', 'categories_processed', 'kb_item_created'])
    op.create_index('ix_unified_tweet_reprocessing', 'unified_tweet', 
                   ['force_reprocess_pipeline', 'force_recache'])

def downgrade():
    # Drop indexes
    op.drop_index('ix_unified_tweet_reprocessing', table_name='unified_tweet')
    op.drop_index('ix_unified_tweet_processing_flags', table_name='unified_tweet')
    op.drop_index('ix_unified_tweet_main_category', table_name='unified_tweet')
    op.drop_index('ix_unified_tweet_tweet_id', table_name='unified_tweet')
    
    # Drop table
    op.drop_table('unified_tweet')