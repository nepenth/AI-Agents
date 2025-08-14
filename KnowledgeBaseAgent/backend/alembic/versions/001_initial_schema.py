"""Create initial database schema with all models

Revision ID: 001_initial_schema
Revises: 
Create Date: 2025-08-13 14:30:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = "001_initial_schema"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Create content_items table
    op.create_table("content_items",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("source_type", sa.String(), nullable=False),
        sa.Column("source_id", sa.String(), nullable=False),
        sa.Column("title", sa.String(), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("raw_data", postgresql.JSON(astext_type=sa.Text()), nullable=True),
        sa.Column("processing_state", sa.String(), nullable=False),
        sa.Column("processed_at", sa.DateTime(), nullable=True),
        sa.Column("main_category", sa.String(), nullable=True),
        sa.Column("sub_category", sa.String(), nullable=True),
        sa.Column("tags", postgresql.JSON(astext_type=sa.Text()), nullable=False),
        sa.Column("media_files", postgresql.JSON(astext_type=sa.Text()), nullable=False),
        sa.Column("generated_files", postgresql.JSON(astext_type=sa.Text()), nullable=False),
        sa.Column("word_count", sa.Integer(), nullable=True),
        sa.Column("language", sa.String(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint("id")
    )
    op.create_index(op.f("ix_content_items_source_type"), "content_items", ["source_type"], unique=False)
    op.create_index(op.f("ix_content_items_processing_state"), "content_items", ["processing_state"], unique=False)
    op.create_index(op.f("ix_content_items_main_category"), "content_items", ["main_category"], unique=False)
    op.create_index(op.f("ix_content_items_sub_category"), "content_items", ["sub_category"], unique=False)
    op.create_index(op.f("ix_content_items_created_at"), "content_items", ["created_at"], unique=False)

    # Create knowledge_items table
    op.create_table("knowledge_items",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("content_item_id", sa.String(), nullable=False),
        sa.Column("display_title", sa.String(), nullable=False),
        sa.Column("summary", sa.Text(), nullable=True),
        sa.Column("enhanced_content", sa.Text(), nullable=False),
        sa.Column("key_points", postgresql.JSON(astext_type=sa.Text()), nullable=False),
        sa.Column("entities", postgresql.JSON(astext_type=sa.Text()), nullable=False),
        sa.Column("sentiment_score", sa.Float(), nullable=True),
        sa.Column("markdown_path", sa.String(), nullable=True),
        sa.Column("media_paths", postgresql.JSON(astext_type=sa.Text()), nullable=False),
        sa.Column("quality_score", sa.Float(), nullable=True),
        sa.Column("completeness_score", sa.Float(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["content_item_id"], ["content_items.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("content_item_id")
    )
    op.create_index(op.f("ix_knowledge_items_content_item_id"), "knowledge_items", ["content_item_id"], unique=False)
    op.create_index(op.f("ix_knowledge_items_display_title"), "knowledge_items", ["display_title"], unique=False)
    op.create_index(op.f("ix_knowledge_items_created_at"), "knowledge_items", ["created_at"], unique=False)

    # Create embeddings table (without vector column for now)
    op.create_table("embeddings",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("knowledge_item_id", sa.String(), nullable=False),
        sa.Column("model", sa.String(), nullable=False),
        sa.Column("chunk_index", sa.Integer(), nullable=False),
        sa.Column("chunk_text", sa.Text(), nullable=False),
        sa.Column("embedding_dimension", sa.Integer(), nullable=False),
        sa.Column("token_count", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["knowledge_item_id"], ["knowledge_items.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id")
    )
    op.create_index(op.f("ix_embeddings_knowledge_item_id"), "embeddings", ["knowledge_item_id"], unique=False)
    op.create_index(op.f("ix_embeddings_model"), "embeddings", ["model"], unique=False)
    op.create_index(op.f("ix_embeddings_created_at"), "embeddings", ["created_at"], unique=False)

    # Create synthesis_documents table
    op.create_table("synthesis_documents",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("main_category", sa.String(), nullable=False),
        sa.Column("sub_category", sa.String(), nullable=False),
        sa.Column("title", sa.String(), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("executive_summary", sa.Text(), nullable=True),
        sa.Column("item_count", sa.Integer(), nullable=False),
        sa.Column("word_count", sa.Integer(), nullable=True),
        sa.Column("source_item_ids", postgresql.JSON(astext_type=sa.Text()), nullable=False),
        sa.Column("content_hash", sa.String(), nullable=True),
        sa.Column("is_stale", sa.Boolean(), nullable=False),
        sa.Column("generation_model", sa.String(), nullable=True),
        sa.Column("generation_parameters", postgresql.JSON(astext_type=sa.Text()), nullable=True),
        sa.Column("generation_duration", sa.Float(), nullable=True),
        sa.Column("coherence_score", sa.Float(), nullable=True),
        sa.Column("completeness_score", sa.Float(), nullable=True),
        sa.Column("markdown_path", sa.String(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.Column("last_generated_at", sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("main_category", "sub_category", name="uq_synthesis_category")
    )
    op.create_index(op.f("ix_synthesis_documents_main_category"), "synthesis_documents", ["main_category"], unique=False)
    op.create_index(op.f("ix_synthesis_documents_sub_category"), "synthesis_documents", ["sub_category"], unique=False)
    op.create_index(op.f("ix_synthesis_documents_is_stale"), "synthesis_documents", ["is_stale"], unique=False)
    op.create_index(op.f("ix_synthesis_documents_created_at"), "synthesis_documents", ["created_at"], unique=False)

    # Create tasks table
    op.create_table("tasks",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("task_type", sa.String(), nullable=False),
        sa.Column("task_name", sa.String(), nullable=True),
        sa.Column("status", sa.String(), nullable=False),
        sa.Column("config", postgresql.JSON(astext_type=sa.Text()), nullable=True),
        sa.Column("current_phase", sa.String(), nullable=True),
        sa.Column("progress_percentage", sa.Integer(), nullable=False),
        sa.Column("progress_message", sa.String(), nullable=True),
        sa.Column("worker_id", sa.String(), nullable=True),
        sa.Column("queue_name", sa.String(), nullable=True),
        sa.Column("result_data", postgresql.JSON(astext_type=sa.Text()), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("error_traceback", sa.Text(), nullable=True),
        sa.Column("execution_time", sa.Float(), nullable=True),
        sa.Column("memory_usage", sa.Integer(), nullable=True),
        sa.Column("retry_count", sa.Integer(), nullable=False),
        sa.Column("max_retries", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("started_at", sa.DateTime(), nullable=True),
        sa.Column("completed_at", sa.DateTime(), nullable=True),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint("id")
    )
    op.create_index(op.f("ix_tasks_task_type"), "tasks", ["task_type"], unique=False)
    op.create_index(op.f("ix_tasks_status"), "tasks", ["status"], unique=False)
    op.create_index(op.f("ix_tasks_created_at"), "tasks", ["created_at"], unique=False)

    # Create chat_sessions table
    op.create_table("chat_sessions",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("title", sa.String(), nullable=True),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("message_count", sa.Integer(), nullable=False),
        sa.Column("total_tokens", sa.Integer(), nullable=False),
        sa.Column("is_archived", sa.Boolean(), nullable=False),
        sa.Column("is_pinned", sa.Boolean(), nullable=False),
        sa.Column("model_name", sa.String(), nullable=True),
        sa.Column("system_prompt", sa.Text(), nullable=True),
        sa.Column("temperature", sa.Float(), nullable=True),
        sa.Column("max_tokens", sa.Integer(), nullable=True),
        sa.Column("context_window", sa.Integer(), nullable=False),
        sa.Column("auto_summarize", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("last_updated", sa.DateTime(), nullable=False),
        sa.Column("last_message_at", sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint("id")
    )
    op.create_index(op.f("ix_chat_sessions_is_archived"), "chat_sessions", ["is_archived"], unique=False)
    op.create_index(op.f("ix_chat_sessions_created_at"), "chat_sessions", ["created_at"], unique=False)
    op.create_index(op.f("ix_chat_sessions_last_updated"), "chat_sessions", ["last_updated"], unique=False)

    # Create chat_messages table
    op.create_table("chat_messages",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("session_id", sa.String(), nullable=False),
        sa.Column("role", sa.String(), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("token_count", sa.Integer(), nullable=True),
        sa.Column("word_count", sa.Integer(), nullable=True),
        sa.Column("model_used", sa.String(), nullable=True),
        sa.Column("generation_time", sa.Float(), nullable=True),
        sa.Column("temperature_used", sa.Float(), nullable=True),
        sa.Column("sources", postgresql.JSON(astext_type=sa.Text()), nullable=False),
        sa.Column("context_stats", postgresql.JSON(astext_type=sa.Text()), nullable=True),
        sa.Column("is_edited", sa.Boolean(), nullable=False),
        sa.Column("is_regenerated", sa.Boolean(), nullable=False),
        sa.Column("parent_message_id", sa.String(), nullable=True),
        sa.Column("relevance_score", sa.Float(), nullable=True),
        sa.Column("helpfulness_score", sa.Float(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["session_id"], ["chat_sessions.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id")
    )
    op.create_index(op.f("ix_chat_messages_session_id"), "chat_messages", ["session_id"], unique=False)
    op.create_index(op.f("ix_chat_messages_role"), "chat_messages", ["role"], unique=False)
    op.create_index(op.f("ix_chat_messages_created_at"), "chat_messages", ["created_at"], unique=False)


def downgrade() -> None:
    # Drop tables in reverse order to handle foreign key constraints
    op.drop_table("chat_messages")
    op.drop_table("chat_sessions")
    op.drop_table("tasks")
    op.drop_table("synthesis_documents")
    op.drop_table("embeddings")
    op.drop_table("knowledge_items")
    op.drop_table("content_items")
