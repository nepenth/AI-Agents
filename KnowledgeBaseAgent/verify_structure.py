#!/usr/bin/env python3
"""
Simple script to verify the project structure is correctly set up.
"""
import os
import sys

def check_file_exists(filepath, description):
    """Check if a file exists and print status."""
    if os.path.exists(filepath):
        print(f"✅ {description}: {filepath}")
        return True
    else:
        print(f"❌ {description}: {filepath} (missing)")
        return False

def check_directory_exists(dirpath, description):
    """Check if a directory exists and print status."""
    if os.path.isdir(dirpath):
        print(f"✅ {description}: {dirpath}")
        return True
    else:
        print(f"❌ {description}: {dirpath} (missing)")
        return False

def main():
    """Verify the project structure."""
    print("🔍 Verifying AI Agent Backend Project Structure...")
    print()

    all_good = True

    # Check main project files
    print("📁 Main Project Files:")
    all_good &= check_file_exists("docker-compose.yml", "Docker Compose configuration")
    all_good &= check_file_exists("README.md", "Project README")
    all_good &= check_file_exists("init-db.sql", "Database initialization script")
    print()

    # Check backend structure
    print("🐍 Backend Structure:")
    all_good &= check_directory_exists("backend", "Backend directory")
    all_good &= check_file_exists("backend/Dockerfile", "Backend Dockerfile")
    all_good &= check_file_exists("backend/requirements.txt", "Python requirements")
    all_good &= check_file_exists("backend/.env.example", "Environment example")
    print()

    # Check app structure
    print("🚀 FastAPI App Structure:")
    all_good &= check_directory_exists("backend/app", "App directory")
    all_good &= check_file_exists("backend/app/main.py", "FastAPI main application")
    all_good &= check_file_exists("backend/app/config.py", "Configuration management")
    all_good &= check_file_exists("backend/app/database.py", "Database setup")
    all_good &= check_file_exists("backend/app/dependencies.py", "Dependency injection")
    all_good &= check_file_exists("backend/app/middleware.py", "Custom middleware")
    all_good &= check_file_exists("backend/app/logging_config.py", "Logging configuration")
    print()

    # Check API structure
    print("🔗 API Structure:")
    all_good &= check_directory_exists("backend/api", "API directory")
    all_good &= check_directory_exists("backend/api/v1", "API v1 directory")
    all_good &= check_file_exists("backend/api/v1/agent.py", "Agent endpoints")
    all_good &= check_file_exists("backend/api/v1/content.py", "Content endpoints")
    all_good &= check_file_exists("backend/api/v1/chat.py", "Chat endpoints")
    all_good &= check_file_exists("backend/api/v1/knowledge.py", "Knowledge endpoints")
    all_good &= check_file_exists("backend/api/v1/system.py", "System endpoints")
    print()

    # Check Celery structure
    print("⚙️  Celery Task Structure:")
    all_good &= check_directory_exists("backend/app/tasks", "Tasks directory")
    all_good &= check_file_exists("backend/app/tasks/celery_app.py", "Celery app configuration")
    all_good &= check_file_exists("backend/app/tasks/content_processing.py", "Content processing tasks")
    print()

    # Check Alembic structure
    print("🗄️  Database Migration Structure:")
    all_good &= check_file_exists("backend/alembic.ini", "Alembic configuration")
    all_good &= check_directory_exists("backend/alembic", "Alembic directory")
    all_good &= check_file_exists("backend/alembic/env.py", "Alembic environment")
    all_good &= check_file_exists("backend/alembic/script.py.mako", "Alembic script template")
    print()

    # Check test structure
    print("🧪 Test Structure:")
    all_good &= check_directory_exists("backend/tests", "Tests directory")
    all_good &= check_file_exists("backend/tests/conftest.py", "Pytest configuration")
    all_good &= check_file_exists("backend/tests/test_config.py", "Configuration tests")
    all_good &= check_file_exists("backend/tests/test_database.py", "Database tests")
    all_good &= check_file_exists("backend/tests/test_main.py", "Main app tests")
    print()

    # Summary
    if all_good:
        print("🎉 Project structure verification completed successfully!")
        print()
        print("📝 Next steps:")
        print("   1. Copy backend/.env.example to backend/.env and configure")
        print("   2. Run 'docker compose up -d' to start the development environment")
        print("   3. Visit http://localhost:8000/health to verify the API is running")
        print("   4. Visit http://localhost:8000/docs to see the API documentation")
        print("   5. Run 'cd backend && pytest' to run the test suite")
    else:
        print("❌ Some files or directories are missing. Please check the structure.")
        return False

    return True

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)