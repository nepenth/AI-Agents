#!/usr/bin/env python3
"""
Simple script to run the database migration for enhanced task management.
"""

import os
import sys
from pathlib import Path

# Add the project root to Python path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

# Set up environment
os.environ.setdefault('FLASK_APP', 'knowledge_base_agent.web')

try:
    from flask_migrate import upgrade
    from knowledge_base_agent.web import create_app
    
    print("🔄 Creating Flask app...")
    app, _, _, _ = create_app()
    
    with app.app_context():
        print("🔄 Running database migration...")
        upgrade()
        print("✅ Migration completed successfully!")
        
except Exception as e:
    print(f"❌ Migration failed: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)