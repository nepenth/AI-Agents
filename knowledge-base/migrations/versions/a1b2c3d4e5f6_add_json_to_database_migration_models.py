"""Add JSON to database migration models

Revision ID: a1b2c3d4e5f6
Revises: ef11a31d1ecc
Create Date: 2025-01-25 12:00:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = 'a1b2c3d4e5f6'
down_revision = 'ef11a31d1ecc'
branch_labels = None
depends_on = None


def get_json_type():
    """Get the appropriate JSON type for the current database."""
    bind = op.get_bind()
    if bind.dialect.name == 'postgresql':
        return postgresql.JSONB(astext_type=sa.Text())
    else:
        return sa.JSON()


def upgrade():
    # Create tweet_cache table (replaces tweet_cache.json)
    op.create_table('tweet_cache',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('tweet_id', sa.String(length=50), nullable=False),
        sa.Column('bookmarked_tweet_id', sa.String(length=50), nullable=False),
        sa.Column('is_thread', sa.Boolean(), nullable=True),
        sa.Column('thread_tweets', get_json_type(), nullable=True),
        sa.Column('all_downloaded_media_for_thread', get_json_type(), nullable=True),
        
        # Processing flags
        sa.Column('urls_expanded', sa.Boolean(), nullable=True),
        sa.Column('media_processed', sa.Boolean(), nullable=True),
        sa.Column('cache_complete', sa.Boolean(), nullable=True),
        sa.Column('categories_processed', sa.Boolean(), nullable=True),
        sa.Column('kb_item_created', sa.Boolean(), nullable=True),
        
        # Manual reprocessing controls
        sa.Column('force_reprocess_pipeline', sa.Boolean(), nullable=True),
        sa.Column('force_recache', sa.Boolean(), nullable=True),
        sa.Column('reprocess_requested_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('reprocess_requested_by', sa.String(length=100), nullable=True),
        
        # Categorization data
        sa.Column('main_category', sa.String(length=100), nullable=True),
        sa.Column('sub_category', sa.String(length=100), nullable=True),
        sa.Column('item_name_suggestion', sa.Text(), nullable=True),
        sa.Column('categories', get_json_type(), nullable=True),
        
        # Knowledge base integration
        sa.Column('kb_item_path', sa.Text(), nullable=True),
        sa.Column('kb_media_paths', get_json_type(), nullable=True),
        
        # Content and metadata
        sa.Column('raw_json_content', get_json_type(), nullable=True),
        sa.Column('display_title', sa.Text(), nullable=True),
        sa.Column('source', sa.String(length=50), nullable=True),
        sa.Column('image_descriptions', get_json_type(), nullable=True),
        sa.Column('full_text', sa.Text(), nullable=True),
        
        # Processing metadata
        sa.Column('recategorization_attempts', sa.Integer(), nullable=True),
        
        # Runtime flags
        sa.Column('cache_succeeded_this_run', sa.Boolean(), nullable=True),
        sa.Column('media_succeeded_this_run', sa.Boolean(), nullable=True),
        sa.Column('llm_succeeded_this_run', sa.Boolean(), nullable=True),
        sa.Column('kbitem_succeeded_this_run', sa.Boolean(), nullable=True),
        
        # Error tracking
        sa.Column('kbitem_error', sa.Text(), nullable=True),
        sa.Column('llm_error', sa.Text(), nullable=True),
        
        # Additional fields
        sa.Column('db_synced', sa.Boolean(), nullable=True),
        
        # Timestamps
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text("datetime('now')") if op.get_bind().dialect.name == 'sqlite' else sa.text('now()'), nullable=True),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text("datetime('now')") if op.get_bind().dialect.name == 'sqlite' else sa.text('now()'), nullable=True),
        
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('tweet_id')
    )
    
    # Create indexes for tweet_cache
    op.create_index('ix_tweet_cache_tweet_id', 'tweet_cache', ['tweet_id'])
    op.create_index('idx_tweet_cache_processing_flags', 'tweet_cache', ['cache_complete', 'media_processed', 'categories_processed', 'kb_item_created'])
    op.create_index('idx_tweet_cache_reprocessing_flags', 'tweet_cache', ['force_reprocess_pipeline', 'force_recache'])
    op.create_index('idx_tweet_cache_categories', 'tweet_cache', ['main_category', 'sub_category'])
    op.create_index('idx_tweet_cache_source', 'tweet_cache', ['source'])
    op.create_index('idx_tweet_cache_updated_at', 'tweet_cache', ['updated_at'])
    op.create_index('idx_tweet_cache_reprocess_requested', 'tweet_cache', ['reprocess_requested_at'])
    
    # Create database-specific indexes
    bind = op.get_bind()
    if bind.dialect.name == 'postgresql':
        # PostgreSQL: Create GIN indexes for JSONB fields and full-text search
        op.execute('CREATE INDEX idx_tweet_cache_thread_tweets ON tweet_cache USING gin (thread_tweets)')
        op.execute('CREATE INDEX idx_tweet_cache_full_text ON tweet_cache USING gin (to_tsvector(\'english\', full_text))')
    else:
        # SQLite: Create regular indexes (SQLite doesn't support GIN indexes)
        op.create_index('idx_tweet_cache_full_text', 'tweet_cache', ['full_text'])
    
    # Create tweet_processing_queue table (replaces processed_tweets.json and unprocessed_tweets.json)
    op.create_table('tweet_processing_queue',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('tweet_id', sa.String(length=50), nullable=False),
        sa.Column('status', sa.String(length=20), nullable=False),
        sa.Column('processing_phase', sa.String(length=50), nullable=True),
        sa.Column('priority', sa.Integer(), nullable=True),
        sa.Column('retry_count', sa.Integer(), nullable=True),
        sa.Column('last_error', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text("datetime('now')") if op.get_bind().dialect.name == 'sqlite' else sa.text('now()'), nullable=True),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text("datetime('now')") if op.get_bind().dialect.name == 'sqlite' else sa.text('now()'), nullable=True),
        sa.Column('processed_at', sa.DateTime(timezone=True), nullable=True),
        
        sa.ForeignKeyConstraint(['tweet_id'], ['tweet_cache.tweet_id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('tweet_id')
    )
    
    # Create indexes for tweet_processing_queue
    op.create_index('ix_tweet_processing_queue_tweet_id', 'tweet_processing_queue', ['tweet_id'])
    op.create_index('idx_tweet_processing_queue_status', 'tweet_processing_queue', ['status'])
    op.create_index('idx_tweet_processing_queue_phase', 'tweet_processing_queue', ['processing_phase'])
    op.create_index('idx_tweet_processing_queue_priority', 'tweet_processing_queue', ['priority', 'created_at'])
    
    # Create category_hierarchy table (replaces categories.json)
    op.create_table('category_hierarchy',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('main_category', sa.String(length=100), nullable=False),
        sa.Column('sub_category', sa.String(length=100), nullable=False),
        sa.Column('display_name', sa.String(length=200), nullable=True),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('sort_order', sa.Integer(), nullable=True),
        sa.Column('is_active', sa.Boolean(), nullable=True),
        sa.Column('item_count', sa.Integer(), nullable=True),
        sa.Column('last_updated', sa.DateTime(timezone=True), server_default=sa.text("datetime('now')") if op.get_bind().dialect.name == 'sqlite' else sa.text('now()'), nullable=True),
        
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('main_category', 'sub_category', name='uq_category_hierarchy_main_sub')
    )
    
    # Create indexes for category_hierarchy
    op.create_index('idx_category_hierarchy_main', 'category_hierarchy', ['main_category'])
    op.create_index('idx_category_hierarchy_active', 'category_hierarchy', ['is_active'])
    
    # Create processing_statistics table (replaces processing_stats.json)
    op.create_table('processing_statistics',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('phase_name', sa.String(length=100), nullable=False),
        sa.Column('metric_name', sa.String(length=100), nullable=False),
        sa.Column('metric_value', sa.Numeric(), nullable=True),
        sa.Column('metric_unit', sa.String(length=50), nullable=True),
        sa.Column('total_items_processed', sa.Integer(), nullable=True),
        sa.Column('total_duration_seconds', sa.Numeric(), nullable=True),
        sa.Column('avg_time_per_item_seconds', sa.Numeric(), nullable=True),
        sa.Column('run_id', sa.String(length=36), nullable=True),
        sa.Column('recorded_at', sa.DateTime(timezone=True), server_default=sa.text("datetime('now')") if op.get_bind().dialect.name == 'sqlite' else sa.text('now()'), nullable=True),
        
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('phase_name', 'metric_name', 'run_id', name='uq_processing_stats_phase_metric_run')
    )
    
    # Create indexes for processing_statistics
    op.create_index('idx_processing_statistics_phase', 'processing_statistics', ['phase_name'])
    op.create_index('idx_processing_statistics_run', 'processing_statistics', ['run_id'])
    op.create_index('idx_processing_statistics_recorded', 'processing_statistics', ['recorded_at'])
    
    # Create runtime_statistics table (replaces latest_run_stats.json)
    op.create_table('runtime_statistics',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('run_id', sa.String(length=36), nullable=False),
        sa.Column('processed_count', sa.Integer(), nullable=True),
        sa.Column('success_count', sa.Integer(), nullable=True),
        sa.Column('error_count', sa.Integer(), nullable=True),
        sa.Column('skipped_count', sa.Integer(), nullable=True),
        sa.Column('media_processed', sa.Integer(), nullable=True),
        sa.Column('cache_hits', sa.Integer(), nullable=True),
        sa.Column('cache_misses', sa.Integer(), nullable=True),
        sa.Column('network_errors', sa.Integer(), nullable=True),
        sa.Column('retry_count', sa.Integer(), nullable=True),
        sa.Column('success_rate', sa.Numeric(precision=5, scale=2), nullable=True),
        sa.Column('cache_hit_rate', sa.Numeric(precision=5, scale=2), nullable=True),
        sa.Column('error_rate', sa.Numeric(precision=5, scale=2), nullable=True),
        sa.Column('average_retries', sa.Numeric(precision=10, scale=2), nullable=True),
        sa.Column('start_time', sa.DateTime(timezone=True), nullable=True),
        sa.Column('end_time', sa.DateTime(timezone=True), nullable=True),
        sa.Column('duration', sa.Interval(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text("datetime('now')") if op.get_bind().dialect.name == 'sqlite' else sa.text('now()'), nullable=True),
        
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('run_id')
    )
    
    # Create indexes for runtime_statistics
    op.create_index('idx_runtime_statistics_run_id', 'runtime_statistics', ['run_id'])
    op.create_index('idx_runtime_statistics_start_time', 'runtime_statistics', ['start_time'])
    
    # Set default values for boolean columns
    op.execute("UPDATE tweet_cache SET is_thread = false WHERE is_thread IS NULL")
    op.execute("UPDATE tweet_cache SET urls_expanded = false WHERE urls_expanded IS NULL")
    op.execute("UPDATE tweet_cache SET media_processed = false WHERE media_processed IS NULL")
    op.execute("UPDATE tweet_cache SET cache_complete = false WHERE cache_complete IS NULL")
    op.execute("UPDATE tweet_cache SET categories_processed = false WHERE categories_processed IS NULL")
    op.execute("UPDATE tweet_cache SET kb_item_created = false WHERE kb_item_created IS NULL")
    op.execute("UPDATE tweet_cache SET force_reprocess_pipeline = false WHERE force_reprocess_pipeline IS NULL")
    op.execute("UPDATE tweet_cache SET force_recache = false WHERE force_recache IS NULL")
    op.execute("UPDATE tweet_cache SET source = 'unknown' WHERE source IS NULL")
    op.execute("UPDATE tweet_cache SET recategorization_attempts = 0 WHERE recategorization_attempts IS NULL")
    op.execute("UPDATE tweet_cache SET cache_succeeded_this_run = false WHERE cache_succeeded_this_run IS NULL")
    op.execute("UPDATE tweet_cache SET media_succeeded_this_run = false WHERE media_succeeded_this_run IS NULL")
    op.execute("UPDATE tweet_cache SET llm_succeeded_this_run = false WHERE llm_succeeded_this_run IS NULL")
    op.execute("UPDATE tweet_cache SET kbitem_succeeded_this_run = false WHERE kbitem_succeeded_this_run IS NULL")
    op.execute("UPDATE tweet_cache SET db_synced = false WHERE db_synced IS NULL")
    
    op.execute("UPDATE tweet_processing_queue SET status = 'unprocessed' WHERE status IS NULL")
    op.execute("UPDATE tweet_processing_queue SET priority = 0 WHERE priority IS NULL")
    op.execute("UPDATE tweet_processing_queue SET retry_count = 0 WHERE retry_count IS NULL")
    
    op.execute("UPDATE category_hierarchy SET sort_order = 0 WHERE sort_order IS NULL")
    op.execute("UPDATE category_hierarchy SET is_active = true WHERE is_active IS NULL")
    op.execute("UPDATE category_hierarchy SET item_count = 0 WHERE item_count IS NULL")
    
    op.execute("UPDATE processing_statistics SET total_items_processed = 0 WHERE total_items_processed IS NULL")
    op.execute("UPDATE processing_statistics SET total_duration_seconds = 0 WHERE total_duration_seconds IS NULL")
    op.execute("UPDATE processing_statistics SET avg_time_per_item_seconds = 0 WHERE avg_time_per_item_seconds IS NULL")
    
    op.execute("UPDATE runtime_statistics SET processed_count = 0 WHERE processed_count IS NULL")
    op.execute("UPDATE runtime_statistics SET success_count = 0 WHERE success_count IS NULL")
    op.execute("UPDATE runtime_statistics SET error_count = 0 WHERE error_count IS NULL")
    op.execute("UPDATE runtime_statistics SET skipped_count = 0 WHERE skipped_count IS NULL")
    op.execute("UPDATE runtime_statistics SET media_processed = 0 WHERE media_processed IS NULL")
    op.execute("UPDATE runtime_statistics SET cache_hits = 0 WHERE cache_hits IS NULL")
    op.execute("UPDATE runtime_statistics SET cache_misses = 0 WHERE cache_misses IS NULL")
    op.execute("UPDATE runtime_statistics SET network_errors = 0 WHERE network_errors IS NULL")
    op.execute("UPDATE runtime_statistics SET retry_count = 0 WHERE retry_count IS NULL")


def downgrade():
    # Drop all new tables in reverse order
    op.drop_table('runtime_statistics')
    op.drop_table('processing_statistics')
    op.drop_table('category_hierarchy')
    op.drop_table('tweet_processing_queue')
    op.drop_table('tweet_cache')