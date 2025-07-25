#!/usr/bin/env python3
"""
JSON to Database Migration Runner

This script provides a command-line interface for running the JSON to Database
migration with comprehensive logging, error handling, and reporting.
"""

import sys
import argparse
import logging
import os
from datetime import datetime
from pathlib import Path

# Add the project root to the Python path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

# Set up Flask environment
os.environ.setdefault('FLASK_APP', 'knowledge_base_agent.web')

# Import required modules
from knowledge_base_agent.config import Config
from knowledge_base_agent.json_to_db_migrator import JsonToDbMigrator, MigrationStatus
from knowledge_base_agent.web import create_app


def setup_logging(log_level: str = "INFO") -> None:
    """Set up logging configuration."""
    log_format = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    
    # Create logs directory if it doesn't exist
    logs_dir = project_root / "logs"
    logs_dir.mkdir(exist_ok=True)
    
    # Set up file and console logging
    logging.basicConfig(
        level=getattr(logging, log_level.upper()),
        format=log_format,
        handlers=[
            logging.FileHandler(logs_dir / f"migration_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log"),
            logging.StreamHandler(sys.stdout)
        ]
    )


def print_migration_report(report):
    """Print a formatted migration report."""
    print("\n" + "="*80)
    print("JSON TO DATABASE MIGRATION REPORT")
    print("="*80)
    print(f"Migration ID: {report.migration_id}")
    print(f"Status: {report.status.value}")
    print(f"Start Time: {report.start_time}")
    print(f"End Time: {report.end_time}")
    
    if report.end_time and report.start_time:
        duration = report.end_time - report.start_time
        print(f"Duration: {duration}")
    
    print(f"Total Items Migrated: {report.total_items_migrated}")
    print(f"Total Errors: {report.total_errors}")
    
    if report.backup_location:
        print(f"Backup Location: {report.backup_location}")
    
    print("\n" + "-"*80)
    print("MIGRATION STEPS")
    print("-"*80)
    
    for result in report.results:
        status_symbol = "✅" if result.status == MigrationStatus.COMPLETED else "❌"
        print(f"{status_symbol} {result.operation}")
        print(f"   Status: {result.status.value}")
        print(f"   Items Processed: {result.items_processed}")
        print(f"   Items Failed: {result.items_failed}")
        print(f"   Duration: {result.duration_seconds:.2f} seconds")
        
        if result.error_message:
            print(f"   Error: {result.error_message}")
        
        if result.warnings:
            print(f"   Warnings: {len(result.warnings)}")
            for warning in result.warnings[:3]:  # Show first 3 warnings
                print(f"     - {warning}")
            if len(result.warnings) > 3:
                print(f"     ... and {len(result.warnings) - 3} more warnings")
        print()
    
    if report.validation_results:
        print("-"*80)
        print("VALIDATION RESULTS")
        print("-"*80)
        
        for validation in report.validation_results:
            status_symbol = "✅" if validation.is_valid else "❌"
            print(f"{status_symbol} Data Validation")
            print(f"   Valid: {validation.is_valid}")
            print(f"   Total Items: {validation.total_items}")
            print(f"   Valid Items: {validation.valid_items}")
            print(f"   Invalid Items: {validation.invalid_items}")
            
            if validation.errors:
                print(f"   Errors: {len(validation.errors)}")
                for error in validation.errors[:3]:  # Show first 3 errors
                    print(f"     - {error}")
                if len(validation.errors) > 3:
                    print(f"     ... and {len(validation.errors) - 3} more errors")
            
            if validation.warnings:
                print(f"   Warnings: {len(validation.warnings)}")
                for warning in validation.warnings[:3]:  # Show first 3 warnings
                    print(f"     - {warning}")
                if len(validation.warnings) > 3:
                    print(f"     ... and {len(validation.warnings) - 3} more warnings")
            print()
    
    print("="*80)


def main():
    """Main migration runner function."""
    parser = argparse.ArgumentParser(
        description="Run JSON to Database migration for Knowledge Base Agent",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Run full migration with default settings
  python run_json_migration.py

  # Run migration with custom ID and debug logging
  python run_json_migration.py --migration-id my_migration --log-level DEBUG

  # Validate existing migration without running
  python run_json_migration.py --validate-only

  # Run with force flag to bypass confirmations
  python run_json_migration.py --force
        """
    )
    
    parser.add_argument(
        "--migration-id",
        type=str,
        help="Custom migration ID (defaults to timestamp-based ID)"
    )
    
    parser.add_argument(
        "--log-level",
        type=str,
        choices=["DEBUG", "INFO", "WARNING", "ERROR"],
        default="INFO",
        help="Logging level (default: INFO)"
    )
    
    parser.add_argument(
        "--validate-only",
        action="store_true",
        help="Only validate existing database data without running migration"
    )
    
    parser.add_argument(
        "--force",
        action="store_true",
        help="Skip confirmation prompts and proceed with migration"
    )
    
    parser.add_argument(
        "--rollback",
        type=str,
        metavar="BACKUP_PATH",
        help="Rollback migration using specified backup directory"
    )
    
    args = parser.parse_args()
    
    # Set up logging
    setup_logging(args.log_level)
    logger = logging.getLogger(__name__)
    
    try:
        # Create Flask app and get application context
        logger.info("Creating Flask application...")
        app, _, _, _ = create_app()
        
        with app.app_context():
            # Load configuration
            logger.info("Loading configuration...")
            config = Config()
            
            # Initialize migrator
            logger.info("Initializing migration engine...")
            migrator = JsonToDbMigrator(config)
        
            # Handle rollback
            if args.rollback:
                if not Path(args.rollback).exists():
                    print(f"❌ Backup directory not found: {args.rollback}")
                    return 1
                
                print(f"🔄 Rolling back migration from backup: {args.rollback}")
                
                if not args.force:
                    response = input("This will delete all database data and restore from backup. Continue? (y/N): ")
                    if response.lower() != 'y':
                        print("❌ Rollback cancelled by user")
                        return 0
                
                success = migrator.rollback_migration(args.rollback)
                if success:
                    print("✅ Migration rollback completed successfully")
                    return 0
                else:
                    print("❌ Migration rollback failed")
                    return 1
        
            # Handle validation only
            if args.validate_only:
                print("🔍 Validating existing database data...")
                validation_result = migrator.validate_migration()
                
                status_symbol = "✅" if validation_result.is_valid else "❌"
                print(f"{status_symbol} Validation completed")
                print(f"   Valid: {validation_result.is_valid}")
                print(f"   Total Items: {validation_result.total_items}")
                print(f"   Valid Items: {validation_result.valid_items}")
                print(f"   Invalid Items: {validation_result.invalid_items}")
                
                if validation_result.errors:
                    print(f"   Errors: {len(validation_result.errors)}")
                    for error in validation_result.errors:
                        print(f"     - {error}")
                
                if validation_result.warnings:
                    print(f"   Warnings: {len(validation_result.warnings)}")
                    for warning in validation_result.warnings:
                        print(f"     - {warning}")
                
                return 0 if validation_result.is_valid else 1
            
            # Check if JSON files exist
            data_dir = Path(config.project_root) / "data"
            json_files = [
                "tweet_cache.json",
                "categories.json",
                "processed_tweets.json",
                "unprocessed_tweets.json",
                "processing_stats.json",
                "latest_run_stats.json"
            ]
            
            existing_files = [f for f in json_files if (data_dir / f).exists()]
            
            if not existing_files:
                print("❌ No JSON files found to migrate. Migration not needed.")
                return 0
            
            print("📋 JSON files found for migration:")
            for filename in existing_files:
                file_path = data_dir / filename
                size_mb = file_path.stat().st_size / (1024 * 1024)
                print(f"   - {filename} ({size_mb:.1f} MB)")
            
            # Confirmation prompt
            if not args.force:
                print("\n⚠️  This will migrate JSON data to the database.")
                print("   A backup will be created before migration begins.")
                response = input("Continue with migration? (y/N): ")
                if response.lower() != 'y':
                    print("❌ Migration cancelled by user")
                    return 0
            
            # Run migration
            print("🚀 Starting JSON to Database migration...")
            logger.info("Starting migration process")
            
            report = migrator.migrate_all_data(args.migration_id)
        
            # Print detailed report
            print_migration_report(report)
            
            # Return appropriate exit code
            if report.status == MigrationStatus.COMPLETED:
                print("🎉 Migration completed successfully!")
                logger.info("Migration completed successfully")
                return 0
            else:
                print("💥 Migration failed!")
                logger.error("Migration failed")
                
                if report.backup_location:
                    print(f"\n🔄 To rollback this migration, run:")
                    print(f"   python run_json_migration.py --rollback {report.backup_location}")
                
                return 1
            
    except KeyboardInterrupt:
        print("\n❌ Migration interrupted by user")
        logger.warning("Migration interrupted by user")
        return 1
    except Exception as e:
        print(f"💥 Migration failed with error: {e}")
        logger.error(f"Migration failed with exception: {e}", exc_info=True)
        return 1


if __name__ == "__main__":
    exit_code = main()
    sys.exit(exit_code) 