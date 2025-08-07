#!/usr/bin/env python3
"""
Simple script to run database cleanup and validation

This script provides an easy way to:
1. Validate the current state of the unified database
2. Run migration fixes to clean up data issues
3. Generate reports on data integrity

Usage:
    python scripts/run_db_cleanup.py --check     # Just check for issues
    python scripts/run_db_cleanup.py --fix       # Fix all issues found
    python scripts/run_db_cleanup.py --report    # Generate detailed report
"""

import sys
import argparse
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

def main():
    parser = argparse.ArgumentParser(description='Database cleanup and validation tool')
    parser.add_argument('--check', action='store_true', 
                       help='Check for data integrity issues (read-only)')
    parser.add_argument('--fix', action='store_true',
                       help='Fix all data integrity issues found')
    parser.add_argument('--report', action='store_true',
                       help='Generate detailed validation report')
    
    args = parser.parse_args()
    
    if not any([args.check, args.fix, args.report]):
        print("Please specify an action: --check, --fix, or --report")
        sys.exit(1)
    
    try:
        if args.check:
            print("🔍 Running database validation check...")
            from scripts.unified_db_validator import main as validator_main
            sys.argv = ['unified_db_validator.py', '--dry-run']
            validator_main()
            
        elif args.fix:
            print("🔧 Running database migration and fixes...")
            from scripts.migrate_unified_db import main as migrator_main
            sys.argv = ['migrate_unified_db.py', '--migrate']
            migrator_main()
            
        elif args.report:
            print("📊 Generating detailed validation report...")
            from scripts.migrate_unified_db import main as migrator_main
            sys.argv = ['migrate_unified_db.py', '--validate']
            migrator_main()
            
    except Exception as e:
        print(f"❌ Error running database cleanup: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()