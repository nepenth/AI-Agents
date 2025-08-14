"""CLI tool for data migration operations."""

import asyncio
import click
import json
from pathlib import Path
from typing import Optional

from app.services.migration_service import get_migration_service, MigrationConfig


@click.group()
def migration():
    """Data migration commands."""
    pass


@migration.command()
@click.option('--source', '-s', required=True, help='Source directory containing legacy data')
@click.option('--backup', '-b', required=True, help='Backup directory for reports and backups')
@click.option('--batch-size', default=100, help='Batch size for processing files')
@click.option('--no-validate', is_flag=True, help='Skip data validation')
@click.option('--no-backup', is_flag=True, help='Skip creating backups')
@click.option('--dry-run', is_flag=True, help='Perform dry run without actual migration')
@click.option('--incremental', is_flag=True, help='Perform incremental migration (skip already migrated files)')
@click.option('--max-file-size', default=50*1024*1024, help='Maximum file size to process (bytes)')
@click.option('--no-skip-large', is_flag=True, help='Do not skip large files')
@click.option('--parallel', is_flag=True, help='Use parallel processing')
@click.option('--max-workers', default=4, help='Maximum number of worker threads')
@click.option('--verbose', '-v', is_flag=True, help='Verbose output')
def migrate(
    source: str,
    backup: str,
    batch_size: int,
    no_validate: bool,
    no_backup: bool,
    dry_run: bool,
    incremental: bool,
    max_file_size: int,
    no_skip_large: bool,
    parallel: bool,
    max_workers: int,
    verbose: bool
):
    """Migrate legacy data to new unified model."""
    
    async def run_migration():
        migration_service = get_migration_service()
        
        config = MigrationConfig(
            source_directory=source,
            backup_directory=backup,
            batch_size=batch_size,
            validate_data=not no_validate,
            create_backups=not no_backup,
            preserve_timestamps=True,
            dry_run=dry_run,
            incremental=incremental,
            max_file_size=max_file_size,
            skip_large_files=not no_skip_large,
            parallel_processing=parallel,
            max_workers=max_workers
        )
        
        if verbose:
            click.echo(f"Migration configuration:")
            click.echo(f"  Source: {source}")
            click.echo(f"  Backup: {backup}")
            click.echo(f"  Batch size: {batch_size}")
            click.echo(f"  Validate: {not no_validate}")
            click.echo(f"  Create backups: {not no_backup}")
            click.echo(f"  Dry run: {dry_run}")
            click.echo(f"  Incremental: {incremental}")
            click.echo(f"  Max file size: {max_file_size:,} bytes")
            click.echo(f"  Skip large files: {not no_skip_large}")
            click.echo(f"  Parallel processing: {parallel}")
            click.echo(f"  Max workers: {max_workers}")
            click.echo()
        
        click.echo("Starting migration...")
        
        result = await migration_service.migrate_legacy_data(config)
        
        if result.success:
            click.echo(click.style("✓ Migration completed successfully!", fg='green'))
        else:
            click.echo(click.style("✗ Migration failed!", fg='red'))
        
        click.echo(f"Message: {result.message}")
        
        # Display statistics
        stats = result.stats
        click.echo("\nMigration Statistics:")
        click.echo(f"  Total files: {stats.total_files}")
        click.echo(f"  Processed: {stats.processed_files}")
        click.echo(f"  Successful: {stats.successful_migrations}")
        click.echo(f"  Failed: {stats.failed_migrations}")
        click.echo(f"  Skipped: {stats.skipped_files}")
        click.echo(f"  Validation errors: {stats.validation_errors}")
        
        if stats.start_time and stats.end_time:
            duration = stats.end_time - stats.start_time
            click.echo(f"  Duration: {duration}")
        
        # Display errors if any
        if result.errors:
            click.echo(f"\nErrors ({len(result.errors)}):")
            for error in result.errors[:10]:  # Show first 10 errors
                click.echo(f"  - {error}")
            
            if len(result.errors) > 10:
                click.echo(f"  ... and {len(result.errors) - 10} more errors")
        
        return result.success
    
    success = asyncio.run(run_migration())
    if not success:
        raise click.ClickException("Migration failed")


@migration.command()
@click.option('--source', '-s', required=True, help='Source directory to validate')
@click.option('--output', '-o', help='Output file for validation report')
@click.option('--verbose', '-v', is_flag=True, help='Verbose output')
def validate(source: str, output: Optional[str], verbose: bool):
    """Validate migration data without performing migration."""
    
    async def run_validation():
        migration_service = get_migration_service()
        
        config = MigrationConfig(
            source_directory=source,
            backup_directory="/tmp",  # Not used for validation
            validate_data=True,
            dry_run=True
        )
        
        click.echo("Validating migration data...")
        
        result = await migration_service.validate_migration(config)
        
        click.echo(f"\nValidation Results:")
        click.echo(f"  Total files: {result['total_files']}")
        click.echo(f"  Valid files: {result['valid_files']}")
        click.echo(f"  Invalid files: {result['invalid_files']}")
        
        if result['errors']:
            click.echo(f"\nErrors ({len(result['errors'])}):")
            for error in result['errors'][:20]:  # Show first 20 errors
                click.echo(f"  - {error}")
            
            if len(result['errors']) > 20:
                click.echo(f"  ... and {len(result['errors']) - 20} more errors")
        
        if result['warnings']:
            click.echo(f"\nWarnings ({len(result['warnings'])}):")
            for warning in result['warnings'][:10]:  # Show first 10 warnings
                click.echo(f"  - {warning}")
        
        # Save report if requested
        if output:
            output_path = Path(output)
            output_path.parent.mkdir(parents=True, exist_ok=True)
            
            with open(output_path, 'w') as f:
                json.dump(result, f, indent=2, default=str)
            
            click.echo(f"\nValidation report saved to: {output_path}")
        
        return result['invalid_files'] == 0
    
    success = asyncio.run(run_validation())
    if not success:
        click.echo(click.style("Validation found issues!", fg='yellow'))
    else:
        click.echo(click.style("✓ All files are valid!", fg='green'))


@migration.command()
@click.option('--rollback-file', '-r', required=True, help='Rollback information file')
@click.option('--confirm', is_flag=True, help='Confirm rollback operation')
def rollback(rollback_file: str, confirm: bool):
    """Rollback a migration using rollback information."""
    
    if not confirm:
        click.echo("This operation will rollback the migration and may result in data loss.")
        if not click.confirm("Are you sure you want to continue?"):
            click.echo("Rollback cancelled.")
            return
    
    async def run_rollback():
        try:
            # Load rollback information
            with open(rollback_file, 'r') as f:
                rollback_info = json.load(f)
            
            migration_service = get_migration_service()
            
            click.echo("Starting rollback...")
            
            success = await migration_service.rollback_migration(rollback_info)
            
            if success:
                click.echo(click.style("✓ Rollback completed successfully!", fg='green'))
            else:
                click.echo(click.style("✗ Rollback failed!", fg='red'))
            
            return success
            
        except FileNotFoundError:
            click.echo(click.style(f"✗ Rollback file not found: {rollback_file}", fg='red'))
            return False
        except json.JSONDecodeError:
            click.echo(click.style(f"✗ Invalid rollback file format: {rollback_file}", fg='red'))
            return False
    
    success = asyncio.run(run_rollback())
    if not success:
        raise click.ClickException("Rollback failed")


@migration.command()
@click.option('--source', '-s', required=True, help='Source directory to analyze')
@click.option('--output', '-o', help='Output file for analysis report')
def analyze(source: str, output: Optional[str]):
    """Analyze legacy data structure and content."""
    
    def analyze_directory(source_path: Path):
        """Analyze directory structure and files."""
        analysis = {
            'total_files': 0,
            'file_types': {},
            'directory_structure': {},
            'file_sizes': [],
            'largest_files': [],
            'sample_files': []
        }
        
        for file_path in source_path.rglob('*'):
            if file_path.is_file():
                analysis['total_files'] += 1
                
                # File type analysis
                suffix = file_path.suffix.lower()
                analysis['file_types'][suffix] = analysis['file_types'].get(suffix, 0) + 1
                
                # File size analysis
                try:
                    size = file_path.stat().st_size
                    analysis['file_sizes'].append(size)
                    
                    # Track largest files
                    analysis['largest_files'].append({
                        'path': str(file_path.relative_to(source_path)),
                        'size': size
                    })
                    
                except OSError:
                    pass
        
        # Sort largest files
        analysis['largest_files'].sort(key=lambda x: x['size'], reverse=True)
        analysis['largest_files'] = analysis['largest_files'][:10]
        
        # Calculate size statistics
        if analysis['file_sizes']:
            analysis['total_size'] = sum(analysis['file_sizes'])
            analysis['average_size'] = analysis['total_size'] / len(analysis['file_sizes'])
            analysis['median_size'] = sorted(analysis['file_sizes'])[len(analysis['file_sizes']) // 2]
        
        return analysis
    
    source_path = Path(source)
    if not source_path.exists():
        raise click.ClickException(f"Source directory does not exist: {source}")
    
    click.echo("Analyzing legacy data structure...")
    
    analysis = analyze_directory(source_path)
    
    click.echo(f"\nAnalysis Results:")
    click.echo(f"  Total files: {analysis['total_files']}")
    click.echo(f"  Total size: {analysis.get('total_size', 0):,} bytes")
    
    if analysis['file_types']:
        click.echo(f"\nFile types:")
        for file_type, count in sorted(analysis['file_types'].items(), key=lambda x: x[1], reverse=True):
            click.echo(f"  {file_type or '(no extension)'}: {count}")
    
    if analysis['largest_files']:
        click.echo(f"\nLargest files:")
        for file_info in analysis['largest_files'][:5]:
            click.echo(f"  {file_info['path']}: {file_info['size']:,} bytes")
    
    # Save analysis if requested
    if output:
        output_path = Path(output)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        
        with open(output_path, 'w') as f:
            json.dump(analysis, f, indent=2, default=str)
        
        click.echo(f"\nAnalysis report saved to: {output_path}")


@migration.command()
@click.option('--migration-id', '-m', help='Specific migration ID to check')
@click.option('--recent', '-r', default=10, help='Number of recent migrations to show')
def status(migration_id: Optional[str], recent: int):
    """Check migration status and history."""
    
    async def check_status():
        # This would integrate with the migration API to check status
        # For now, provide a placeholder implementation
        
        if migration_id:
            click.echo(f"Checking status for migration: {migration_id}")
            click.echo("Status: This would show the actual migration status")
        else:
            click.echo(f"Showing {recent} most recent migrations:")
            click.echo("Migration history would be displayed here")
    
    asyncio.run(check_status())


@migration.command()
@click.option('--source', '-s', required=True, help='Source directory to check for incremental changes')
@click.option('--verbose', '-v', is_flag=True, help='Verbose output')
def check_incremental(source: str, verbose: bool):
    """Check what files would be processed in an incremental migration."""
    
    async def check_files():
        migration_service = get_migration_service()
        
        source_path = Path(source)
        if not source_path.exists():
            raise click.ClickException(f"Source directory does not exist: {source}")
        
        click.echo("Checking for files that need incremental migration...")
        
        # Discover all files
        all_files = migration_service._discover_files(source_path)
        click.echo(f"Total files found: {len(all_files)}")
        
        # Filter for incremental migration
        try:
            incremental_files = await migration_service._filter_incremental_files(all_files)
            click.echo(f"Files needing migration: {len(incremental_files)}")
            
            if verbose and incremental_files:
                click.echo("\nFiles to be migrated:")
                for file_path in incremental_files[:20]:  # Show first 20
                    click.echo(f"  {file_path.relative_to(source_path)}")
                
                if len(incremental_files) > 20:
                    click.echo(f"  ... and {len(incremental_files) - 20} more files")
            
            if len(incremental_files) == 0:
                click.echo(click.style("✓ All files are already migrated!", fg='green'))
            else:
                click.echo(f"Run migration with --incremental to process {len(incremental_files)} files")
                
        except Exception as e:
            click.echo(click.style(f"Error checking incremental files: {e}", fg='red'))
    
    asyncio.run(check_files())


if __name__ == '__main__':
    migration()