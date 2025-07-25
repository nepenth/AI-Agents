#!/usr/bin/env python3
"""
Backup Management CLI Tool

Command-line interface for managing Knowledge Base Agent backups.
Provides comprehensive backup creation, validation, restoration, and cleanup operations.
"""

import argparse
import logging
import sys
import os
from pathlib import Path
from datetime import datetime
from typing import Optional, List

# Add the project root to Python path
sys.path.insert(0, str(Path(__file__).parent))

from knowledge_base_agent.config import Config
from knowledge_base_agent.backup_manager import BackupManager


def setup_logging(log_level: str):
    """Setup logging configuration."""
    level = getattr(logging, log_level.upper(), logging.INFO)
    logging.basicConfig(
        level=level,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=[
            logging.StreamHandler(),
            logging.FileHandler('backup_cli.log')
        ]
    )


def format_size(size_bytes: int) -> str:
    """Format byte size to human-readable string."""
    for unit in ['B', 'KB', 'MB', 'GB', 'TB']:
        if size_bytes < 1024.0:
            return f"{size_bytes:.1f} {unit}"
        size_bytes /= 1024.0
    return f"{size_bytes:.1f} PB"


def format_duration(seconds: float) -> str:
    """Format duration in seconds to human-readable string."""
    if seconds < 60:
        return f"{seconds:.1f}s"
    elif seconds < 3600:
        return f"{seconds/60:.1f}m"
    else:
        return f"{seconds/3600:.1f}h"


def print_backup_info(metadata, detailed: bool = False):
    """Print backup information in a formatted way."""
    print(f"📦 Backup ID: {metadata.backup_id}")
    print(f"   Type: {metadata.backup_type}")
    print(f"   Created: {metadata.created_at.strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"   Size: {format_size(metadata.size_bytes)}")
    print(f"   Description: {metadata.description}")
    print(f"   Components: {', '.join(metadata.components)}")
    print(f"   Validation Status: {metadata.validation_status}")
    print(f"   Restore Tested: {'✅ Yes' if metadata.restore_tested else '❌ No'}")
    print(f"   Retention Until: {metadata.retention_date.strftime('%Y-%m-%d %H:%M:%S')}")
    
    if detailed:
        print(f"   Checksum: {metadata.checksum}")
        print(f"   File Paths:")
        for component, path in metadata.file_paths.items():
            print(f"     {component}: {path}")
    print()


def cmd_create(args):
    """Create a new backup."""
    print(f"🔧 Creating {args.backup_type} backup...")
    
    try:
        config = Config()
        manager = BackupManager(config)
        
        components = args.components.split(',') if args.components else None
        
        start_time = datetime.now()
        backup_id = manager.create_backup(
            backup_type=args.backup_type,
            description=args.description or '',
            components=components
        )
        duration = datetime.now() - start_time
        
        print(f"✅ Backup created successfully!")
        print(f"   Backup ID: {backup_id}")
        print(f"   Duration: {format_duration(duration.total_seconds())}")
        
        # Show backup details
        metadata = manager.get_backup_info(backup_id)
        if metadata:
            print(f"   Size: {format_size(metadata.size_bytes)}")
            print(f"   Components: {', '.join(metadata.components)}")
        
    except Exception as e:
        print(f"❌ Backup creation failed: {e}")
        logging.error(f"Backup creation failed: {e}", exc_info=True)
        sys.exit(1)


def cmd_list(args):
    """List available backups."""
    try:
        config = Config()
        manager = BackupManager(config)
        
        backup_ids = manager.list_backups()
        
        if not backup_ids:
            print("📭 No backups found.")
            return
        
        print(f"📋 Found {len(backup_ids)} backup(s):")
        print()
        
        # Filter by type if specified
        if args.backup_type:
            filtered_ids = []
            for backup_id in backup_ids:
                metadata = manager.get_backup_info(backup_id)
                if metadata and metadata.backup_type == args.backup_type:
                    filtered_ids.append(backup_id)
            backup_ids = filtered_ids
            
            if not backup_ids:
                print(f"📭 No {args.backup_type} backups found.")
                return
        
        # Apply limit
        if args.limit:
            backup_ids = backup_ids[:args.limit]
        
        total_size = 0
        for backup_id in backup_ids:
            metadata = manager.get_backup_info(backup_id)
            if metadata:
                print_backup_info(metadata, args.detailed)
                total_size += metadata.size_bytes
        
        print(f"📊 Total size: {format_size(total_size)}")
        
    except Exception as e:
        print(f"❌ Failed to list backups: {e}")
        logging.error(f"Failed to list backups: {e}", exc_info=True)
        sys.exit(1)


def cmd_validate(args):
    """Validate a backup."""
    print(f"🔍 Validating backup: {args.backup_id}")
    
    try:
        config = Config()
        manager = BackupManager(config)
        
        start_time = datetime.now()
        result = manager.validate_backup(args.backup_id)
        duration = datetime.now() - start_time
        
        print(f"⏱️  Validation completed in {format_duration(duration.total_seconds())}")
        print()
        
        if result.is_valid:
            print("✅ Backup is valid!")
        else:
            print("❌ Backup validation failed!")
        
        print(f"   Checksum verified: {'✅' if result.checksum_verified else '❌'}")
        print(f"   Content verified: {'✅' if result.content_verified else '❌'}")
        print(f"   Restore tested: {'✅' if result.restore_tested else '⏭️  Skipped'}")
        
        if result.errors:
            print(f"\n🚨 Errors:")
            for error in result.errors:
                print(f"   • {error}")
        
        if result.warnings:
            print(f"\n⚠️  Warnings:")
            for warning in result.warnings:
                print(f"   • {warning}")
        
    except Exception as e:
        print(f"❌ Validation failed: {e}")
        logging.error(f"Validation failed: {e}", exc_info=True)
        sys.exit(1)


def cmd_restore(args):
    """Restore from a backup."""
    print(f"🔄 Restoring from backup: {args.backup_id}")
    
    # Confirmation for restore operations
    if not args.force:
        response = input("⚠️  This will overwrite existing data. Continue? (yes/no): ")
        if response.lower() != 'yes':
            print("🚫 Restore cancelled.")
            return
    
    try:
        config = Config()
        manager = BackupManager(config)
        
        components = args.components.split(',') if args.components else None
        
        start_time = datetime.now()
        result = manager.restore_backup(
            backup_id=args.backup_id,
            components=components,
            target_directory=args.target_directory,
            create_rollback=not args.no_rollback
        )
        duration = datetime.now() - start_time
        
        print(f"⏱️  Restore completed in {format_duration(duration.total_seconds())}")
        print()
        
        if result.success:
            print("✅ Restore completed successfully!")
            print(f"   Components restored: {', '.join(result.components_restored)}")
            if result.rollback_available:
                print("🔄 Rollback backup available for recovery")
        else:
            print("❌ Restore failed!")
        
        if result.errors:
            print(f"\n🚨 Errors:")
            for error in result.errors:
                print(f"   • {error}")
        
        if result.warnings:
            print(f"\n⚠️  Warnings:")
            for warning in result.warnings:
                print(f"   • {warning}")
        
    except Exception as e:
        print(f"❌ Restore failed: {e}")
        logging.error(f"Restore failed: {e}", exc_info=True)
        sys.exit(1)


def cmd_delete(args):
    """Delete a backup."""
    print(f"🗑️  Deleting backup: {args.backup_id}")
    
    try:
        config = Config()
        manager = BackupManager(config)
        
        # Check if backup exists
        metadata = manager.get_backup_info(args.backup_id)
        if not metadata:
            print(f"❌ Backup {args.backup_id} not found.")
            sys.exit(1)
        
        # Show backup info
        print_backup_info(metadata)
        
        # Confirmation
        if not args.force:
            response = input("⚠️  This will permanently delete the backup. Continue? (yes/no): ")
            if response.lower() != 'yes':
                print("🚫 Deletion cancelled.")
                return
        
        # Delete backup files and metadata
        backup_dir = manager.backup_base_dir / args.backup_id
        if backup_dir.exists():
            import shutil
            shutil.rmtree(backup_dir)
        
        metadata_file = manager.backup_base_dir / "metadata" / f"{args.backup_id}.json"
        if metadata_file.exists():
            metadata_file.unlink()
        
        print(f"✅ Backup {args.backup_id} deleted successfully.")
        
    except Exception as e:
        print(f"❌ Failed to delete backup: {e}")
        logging.error(f"Failed to delete backup: {e}", exc_info=True)
        sys.exit(1)


def cmd_cleanup(args):
    """Clean up expired backups."""
    print("🧹 Cleaning up expired backups...")
    
    try:
        config = Config()
        manager = BackupManager(config)
        
        # Show what would be deleted if dry run
        if args.dry_run:
            print("🔍 Dry run mode - showing what would be deleted:")
            
        start_time = datetime.now()
        if not args.dry_run:
            cleanup_stats = manager.cleanup_expired_backups()
        else:
            # Simulate cleanup for dry run
            from datetime import datetime
            current_time = datetime.now()
            backup_ids = manager.list_backups()
            
            cleanup_stats = {
                'total_checked': len(backup_ids),
                'expired_found': 0,
                'successfully_deleted': 0,
                'failed_deletions': 0,
                'space_freed_bytes': 0
            }
            
            for backup_id in backup_ids:
                metadata = manager.get_backup_info(backup_id)
                if metadata and current_time > metadata.retention_date:
                    cleanup_stats['expired_found'] += 1
                    print(f"   🗑️  Would delete: {backup_id} ({format_size(metadata.size_bytes)})")
        
        duration = datetime.now() - start_time
        
        print(f"⏱️  Cleanup completed in {format_duration(duration.total_seconds())}")
        print()
        print(f"📊 Cleanup Summary:")
        print(f"   Total backups checked: {cleanup_stats['total_checked']}")
        print(f"   Expired backups found: {cleanup_stats['expired_found']}")
        
        if not args.dry_run:
            print(f"   Successfully deleted: {cleanup_stats['successfully_deleted']}")
            print(f"   Failed deletions: {cleanup_stats['failed_deletions']}")
            print(f"   Space freed: {format_size(cleanup_stats['space_freed_bytes'])}")
        
    except Exception as e:
        print(f"❌ Cleanup failed: {e}")
        logging.error(f"Cleanup failed: {e}", exc_info=True)
        sys.exit(1)


def cmd_statistics(args):
    """Show backup statistics."""
    print("📊 Backup Statistics")
    print("=" * 50)
    
    try:
        config = Config()
        manager = BackupManager(config)
        
        stats = manager.get_backup_statistics()
        
        print(f"Total backups created: {stats['total_backups']}")
        print(f"Successful backups: {stats['successful_backups']}")
        print(f"Failed backups: {stats['failed_backups']}")
        print(f"Success rate: {(stats['successful_backups'] / max(stats['total_backups'], 1) * 100):.1f}%")
        print(f"Average backup time: {format_duration(stats['average_backup_time'])}")
        print(f"Total backup size: {format_size(stats['total_backup_size'])}")
        print()
        
        print(f"Backups on disk: {stats['total_backups_on_disk']}")
        print(f"Storage used: {format_size(stats['total_storage_bytes'])}")
        
        if stats['last_backup_time']:
            last_backup = datetime.fromisoformat(stats['last_backup_time'])
            print(f"Last backup: {last_backup.strftime('%Y-%m-%d %H:%M:%S')}")
        else:
            print("Last backup: Never")
        
        print()
        print("Backups by type:")
        for backup_type, count in stats.get('storage_by_type', {}).items():
            print(f"   {backup_type}: {count}")
        
    except Exception as e:
        print(f"❌ Failed to get statistics: {e}")
        logging.error(f"Failed to get statistics: {e}", exc_info=True)
        sys.exit(1)


def cmd_scheduler(args):
    """Control the backup scheduler."""
    try:
        config = Config()
        manager = BackupManager(config)
        
        if args.action == 'start':
            print("🚀 Starting backup scheduler...")
            manager.schedule_automated_backups()
            print("✅ Backup scheduler started successfully.")
            print("   Daily backups: 2:00 AM")
            print("   Weekly backups: Sunday 3:00 AM")
            print("   Cleanup: Daily 4:00 AM")
            
        elif args.action == 'status':
            print("📊 Backup Scheduler Status")
            print("=" * 30)
            
            status = {
                'backup_running': manager.backup_running,
                'last_backup_time': manager.last_backup_time.isoformat() if manager.last_backup_time else None,
                'backup_directory': str(manager.backup_base_dir),
            }
            
            print(f"Status: {'🟢 Running' if not manager.backup_running else '🔄 Backup in progress'}")
            if status['last_backup_time']:
                last_backup = datetime.fromisoformat(status['last_backup_time'])
                print(f"Last backup: {last_backup.strftime('%Y-%m-%d %H:%M:%S')}")
            else:
                print("Last backup: Never")
            print(f"Backup directory: {status['backup_directory']}")
            
            print("\nRetention policies:")
            for backup_type, policy in manager.retention_policies.items():
                print(f"   {backup_type}: {policy.days} days")
        
    except Exception as e:
        print(f"❌ Scheduler operation failed: {e}")
        logging.error(f"Scheduler operation failed: {e}", exc_info=True)
        sys.exit(1)


def main():
    """Main CLI entry point."""
    parser = argparse.ArgumentParser(
        description="Knowledge Base Agent Backup Management CLI",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s create --backup-type manual --description "Before upgrade"
  %(prog)s list --backup-type daily --limit 10
  %(prog)s validate manual_20231215_143022
  %(prog)s restore manual_20231215_143022 --components database,json_files
  %(prog)s cleanup --dry-run
  %(prog)s statistics
        """
    )
    
    parser.add_argument('--log-level', default='INFO', 
                       choices=['DEBUG', 'INFO', 'WARNING', 'ERROR'],
                       help='Set logging level')
    
    subparsers = parser.add_subparsers(dest='command', help='Available commands')
    
    # Create backup command
    create_parser = subparsers.add_parser('create', help='Create a new backup')
    create_parser.add_argument('--backup-type', default='manual',
                              choices=['manual', 'daily', 'weekly', 'monthly', 'pre_migration'],
                              help='Type of backup to create')
    create_parser.add_argument('--description', help='Backup description')
    create_parser.add_argument('--components', help='Comma-separated list of components to backup')
    create_parser.set_defaults(func=cmd_create)
    
    # List backups command
    list_parser = subparsers.add_parser('list', help='List available backups')
    list_parser.add_argument('--backup-type', help='Filter by backup type')
    list_parser.add_argument('--limit', type=int, help='Limit number of results')
    list_parser.add_argument('--detailed', action='store_true', help='Show detailed information')
    list_parser.set_defaults(func=cmd_list)
    
    # Validate backup command
    validate_parser = subparsers.add_parser('validate', help='Validate a backup')
    validate_parser.add_argument('backup_id', help='Backup ID to validate')
    validate_parser.set_defaults(func=cmd_validate)
    
    # Restore backup command
    restore_parser = subparsers.add_parser('restore', help='Restore from a backup')
    restore_parser.add_argument('backup_id', help='Backup ID to restore from')
    restore_parser.add_argument('--components', help='Comma-separated list of components to restore')
    restore_parser.add_argument('--target-directory', help='Custom target directory for restoration')
    restore_parser.add_argument('--no-rollback', action='store_true', help='Skip creating rollback backup')
    restore_parser.add_argument('--force', action='store_true', help='Skip confirmation prompt')
    restore_parser.set_defaults(func=cmd_restore)
    
    # Delete backup command
    delete_parser = subparsers.add_parser('delete', help='Delete a backup')
    delete_parser.add_argument('backup_id', help='Backup ID to delete')
    delete_parser.add_argument('--force', action='store_true', help='Skip confirmation prompt')
    delete_parser.set_defaults(func=cmd_delete)
    
    # Cleanup backups command
    cleanup_parser = subparsers.add_parser('cleanup', help='Clean up expired backups')
    cleanup_parser.add_argument('--dry-run', action='store_true', help='Show what would be deleted without actually deleting')
    cleanup_parser.set_defaults(func=cmd_cleanup)
    
    # Statistics command
    stats_parser = subparsers.add_parser('statistics', help='Show backup statistics')
    stats_parser.set_defaults(func=cmd_statistics)
    
    # Scheduler command
    scheduler_parser = subparsers.add_parser('scheduler', help='Control backup scheduler')
    scheduler_parser.add_argument('action', choices=['start', 'status'], help='Scheduler action')
    scheduler_parser.set_defaults(func=cmd_scheduler)
    
    args = parser.parse_args()
    
    if not args.command:
        parser.print_help()
        sys.exit(1)
    
    setup_logging(args.log_level)
    
    print("🔧 Knowledge Base Agent Backup CLI")
    print("=" * 50)
    
    try:
        args.func(args)
    except KeyboardInterrupt:
        print("\n🚫 Operation cancelled by user.")
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ Unexpected error: {e}")
        logging.error(f"Unexpected error: {e}", exc_info=True)
        sys.exit(1)


if __name__ == '__main__':
    main() 