"""Add Twitter/X integration fields and sub-phase tracking

Revision ID: 003_twitter_x_integration
Revises: 002_pipeline_models
Create Date: 2024-01-01 15:00:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = '003_twitter_x_integration'
down_revision = '002_pipeline_models'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Add Twitter/X-specific fields to content_items
    op.add_column('content_items', sa.Column('tweet_id', sa.String(), nullable=True))
    op.add_column('content_items', sa.Column('author_username', sa.String(), nullable=True))
    op.add_column('content_items', sa.Column('author_id', sa.String(), nullable=True))
    op.add_column('content_items', sa.Column('tweet_url', sa.String(), nullable=True))
    
    # Add thread detection fields
    op.add_column('content_items', sa.Column('thread_id', sa.String(), nullable=True))
    op.add_column('content_items', sa.Column('is_thread_root', sa.Boolean(), nullable=False, server_default='false'))
    op.add_column('content_items', sa.Column('position_in_thread', sa.Integer(), nullable=True))
    op.add_column('content_items', sa.Column('thread_length', sa.Integer(), nullable=True))
    
    # Add engagement metrics
    op.add_column('content_items', sa.Column('like_count', sa.Integer(), nullable=True))
    op.add_column('content_items', sa.Column('retweet_count', sa.Integer(), nullable=True))
    op.add_column('content_items', sa.Column('reply_count', sa.Integer(), nullable=True))
    op.add_column('content_items', sa.Column('quote_count', sa.Integer(), nullable=True))
    
    # Add sub-phase processing states
    op.add_column('content_items', sa.Column('bookmark_cached', sa.Boolean(), nullable=False, server_default='false'))
    op.add_column('content_items', sa.Column('media_analyzed', sa.Boolean(), nullable=False, server_default='false'))
    op.add_column('content_items', sa.Column('content_understood', sa.Boolean(), nullable=False, server_default='false'))
    op.add_column('content_items', sa.Column('categorized', sa.Boolean(), nullable=False, server_default='false'))
    
    # Add AI analysis result fields
    op.add_column('content_items', sa.Column('media_analysis_results', sa.JSON(), nullable=True))
    op.add_column('content_items', sa.Column('collective_understanding', sa.Text(), nullable=True))
    op.add_column('content_items', sa.Column('category_intelligence_used', sa.JSON(), nullable=True))
    
    # Add additional metadata
    op.add_column('content_items', sa.Column('original_tweet_created_at', sa.DateTime(), nullable=True))
    
    # Add additional provenance fields
    op.add_column('content_items', sa.Column('understanding_model_used', sa.String(), nullable=True))
    op.add_column('content_items', sa.Column('categorization_model_used', sa.String(), nullable=True))
    
    # Create indexes for Twitter/X-specific fields
    op.create_index(op.f('ix_content_items_tweet_id'), 'content_items', ['tweet_id'], unique=False)
    op.create_index(op.f('ix_content_items_author_username'), 'content_items', ['author_username'], unique=False)
    op.create_index(op.f('ix_content_items_thread_id'), 'content_items', ['thread_id'], unique=False)
    
    # Create indexes for sub-phase states
    op.create_index(op.f('ix_content_items_bookmark_cached'), 'content_items', ['bookmark_cached'], unique=False)
    op.create_index(op.f('ix_content_items_media_analyzed'), 'content_items', ['media_analyzed'], unique=False)
    op.create_index(op.f('ix_content_items_content_understood'), 'content_items', ['content_understood'], unique=False)
    op.create_index(op.f('ix_content_items_categorized'), 'content_items', ['categorized'], unique=False)


def downgrade() -> None:
    # Drop indexes
    op.drop_index(op.f('ix_content_items_categorized'), table_name='content_items')
    op.drop_index(op.f('ix_content_items_content_understood'), table_name='content_items')
    op.drop_index(op.f('ix_content_items_media_analyzed'), table_name='content_items')
    op.drop_index(op.f('ix_content_items_bookmark_cached'), table_name='content_items')
    op.drop_index(op.f('ix_content_items_thread_id'), table_name='content_items')
    op.drop_index(op.f('ix_content_items_author_username'), table_name='content_items')
    op.drop_index(op.f('ix_content_items_tweet_id'), table_name='content_items')
    
    # Drop columns
    op.drop_column('content_items', 'categorization_model_used')
    op.drop_column('content_items', 'understanding_model_used')
    op.drop_column('content_items', 'original_tweet_created_at')
    op.drop_column('content_items', 'category_intelligence_used')
    op.drop_column('content_items', 'collective_understanding')
    op.drop_column('content_items', 'media_analysis_results')
    op.drop_column('content_items', 'categorized')
    op.drop_column('content_items', 'content_understood')
    op.drop_column('content_items', 'media_analyzed')
    op.drop_column('content_items', 'bookmark_cached')
    op.drop_column('content_items', 'quote_count')
    op.drop_column('content_items', 'reply_count')
    op.drop_column('content_items', 'retweet_count')
    op.drop_column('content_items', 'like_count')
    op.drop_column('content_items', 'thread_length')
    op.drop_column('content_items', 'position_in_thread')
    op.drop_column('content_items', 'is_thread_root')
    op.drop_column('content_items', 'thread_id')
    op.drop_column('content_items', 'tweet_url')
    op.drop_column('content_items', 'author_id')
    op.drop_column('content_items', 'author_username')
    op.drop_column('content_items', 'tweet_id')