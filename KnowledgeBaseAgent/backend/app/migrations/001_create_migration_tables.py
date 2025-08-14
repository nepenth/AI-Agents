"""Create migration tracking tables

Revision ID: 001_migration_tables
Revises: 
Create Date: 2024-01-01 12:00:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = '001_migration_tables'
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Create migration tracking tables."""
    
    # Create migration_runs table
    op.create_table(
        'migration_runs',
        sa.Column('id', sa.String(), nullable=False),
        sa.Column('migration_type', sa.String(50), nullable=False),
        sa.Column('source_directory', sa.String(500), nullable=False),
        sa.Column('backup_directory', sa.String(500), nullable=False),
        sa.Column('status', sa.String(20), nullable=False),
        sa.Column('config', sa.JSON(), nullable=False),
        sa.Column('stats', sa.JSON(), nullable=True),
        sa.Column('errors', sa.JSON(), nullable=True),
        sa.Column('rollback_info', sa.JSON(), nullable=True),
        sa.Column('started_by', sa.String(), nullable=True),
        sa.Column('started_at', sa.DateTime(), nullable=False),
        sa.Column('completed_at', sa.DateTime(), nullable=True),
        sa.Column('created_at', sa.DateTime(), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(), server_default=sa.text('now()'), nullable=False),
        sa.PrimaryKeyConstraint('id')
    )
    
    # Create indexes
    op.create_index('ix_migration_runs_status', 'migration_runs', ['status'])
    op.create_index('ix_migration_runs_started_at', 'migration_runs', ['started_at'])
    op.create_index('ix_migration_runs_migration_type', 'migration_runs', ['migration_type'])
    
    # Create migration_items table for tracking individual migrated items
    op.create_table(
        'migration_items',
        sa.Column('id', sa.String(), nullable=False),
        sa.Column('migration_run_id', sa.String(), nullable=False),
        sa.Column('item_type', sa.String(50), nullable=False),  # content, knowledge, synthesis
        sa.Column('item_id', sa.String(), nullable=False),
        sa.Column('source_file', sa.String(1000), nullable=True),
        sa.Column('legacy_id', sa.String(), nullable=True),
        sa.Column('status', sa.String(20), nullable=False),
        sa.Column('error_message', sa.Text(), nullable=True),
        sa.Column('metadata', sa.JSON(), nullable=True),
        sa.Column('created_at', sa.DateTime(), server_default=sa.text('now()'), nullable=False),
        sa.PrimaryKeyConstraint('id'),
        sa.ForeignKeyConstraint(['migration_run_id'], ['migration_runs.id'], ondelete='CASCADE')
    )
    
    # Create indexes for migration_items
    op.create_index('ix_migration_items_migration_run_id', 'migration_items', ['migration_run_id'])
    op.create_index('ix_migration_items_item_type', 'migration_items', ['item_type'])
    op.create_index('ix_migration_items_status', 'migration_items', ['status'])
    op.create_index('ix_migration_items_legacy_id', 'migration_items', ['legacy_id'])
    
    # Create data_integrity_checks table
    op.create_table(
        'data_integrity_checks',
        sa.Column('id', sa.String(), nullable=False),
        sa.Column('migration_run_id', sa.String(), nullable=False),
        sa.Column('check_type', sa.String(50), nullable=False),
        sa.Column('check_name', sa.String(100), nullable=False),
        sa.Column('status', sa.String(20), nullable=False),
        sa.Column('expected_count', sa.Integer(), nullable=True),
        sa.Column('actual_count', sa.Integer(), nullable=True),
        sa.Column('details', sa.JSON(), nullable=True),
        sa.Column('error_message', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(), server_default=sa.text('now()'), nullable=False),
        sa.PrimaryKeyConstraint('id'),
        sa.ForeignKeyConstraint(['migration_run_id'], ['migration_runs.id'], ondelete='CASCADE')
    )
    
    # Create indexes for data_integrity_checks
    op.create_index('ix_data_integrity_checks_migration_run_id', 'data_integrity_checks', ['migration_run_id'])
    op.create_index('ix_data_integrity_checks_check_type', 'data_integrity_checks', ['check_type'])
    op.create_index('ix_data_integrity_checks_status', 'data_integrity_checks', ['status'])


def downgrade() -> None:
    """Drop migration tracking tables."""
    
    # Drop tables in reverse order
    op.drop_table('data_integrity_checks')
    op.drop_table('migration_items')
    op.drop_table('migration_runs')