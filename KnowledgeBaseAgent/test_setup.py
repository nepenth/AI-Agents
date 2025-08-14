#!/usr/bin/env python3
"""
Simple script to test the basic setup of the AI Agent Backend.
"""
import asyncio
import sys
import os

# Add backend to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'backend'))

async def test_basic_setup():
    """Test basic application setup."""
    print("🧪 Testing AI Agent Backend Setup...")
    
    try:
        # Test configuration loading
        print("📋 Testing configuration...")
        from app.config import get_settings
        
        # Set minimal required environment variables for testing
        os.environ.setdefault('DATABASE_URL', 'sqlite+aiosqlite:///:memory:')
        os.environ.setdefault('REDIS_URL', 'redis://localhost:6379')
        os.environ.setdefault('CELERY_BROKER_URL', 'redis://localhost:6379/0')
        os.environ.setdefault('CELERY_RESULT_BACKEND', 'redis://localhost:6379/0')
        os.environ.setdefault('SECRET_KEY', 'test-secret-key')
        
        settings = get_settings()
        print(f"✅ Configuration loaded successfully")
        print(f"   - App Name: {settings.APP_NAME}")
        print(f"   - Debug Mode: {settings.DEBUG}")
        print(f"   - Log Level: {settings.LOG_LEVEL}")
        
        # Test FastAPI app creation
        print("🚀 Testing FastAPI app creation...")
        from app.main import create_app
        
        # Mock the init_db function to avoid database dependency
        from unittest.mock import patch, AsyncMock
        with patch('app.main.init_db', new_callable=AsyncMock):
            app = create_app()
            print("✅ FastAPI app created successfully")
            print(f"   - Title: {app.title}")
            print(f"   - Version: {app.version}")
        
        # Test API endpoints are registered
        print("🔗 Testing API endpoints registration...")
        routes = [route.path for route in app.routes]
        expected_routes = [
            "/health",
            "/api/v1/agent",
            "/api/v1/content", 
            "/api/v1/chat",
            "/api/v1/knowledge",
            "/api/v1/system"
        ]
        
        for expected_route in expected_routes:
            if any(expected_route in route for route in routes):
                print(f"   ✅ {expected_route} routes registered")
            else:
                print(f"   ❌ {expected_route} routes missing")
        
        # Test Celery app creation
        print("⚙️  Testing Celery app creation...")
        from app.tasks.celery_app import celery_app
        print(f"✅ Celery app created successfully")
        print(f"   - App Name: {celery_app.main}")
        print(f"   - Broker: {celery_app.conf.broker_url}")
        
        print("\n🎉 Basic setup test completed successfully!")
        print("\n📝 Next steps:")
        print("   1. Run 'docker compose up -d' to start the development environment")
        print("   2. Visit http://localhost:8000/health to verify the API is running")
        print("   3. Visit http://localhost:8000/docs to see the API documentation")
        
        return True
        
    except Exception as e:
        print(f"❌ Setup test failed: {str(e)}")
        import traceback
        traceback.print_exc()
        return False


if __name__ == "__main__":
    success = asyncio.run(test_basic_setup())
    sys.exit(0 if success else 1)