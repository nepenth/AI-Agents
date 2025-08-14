#!/usr/bin/env python3
"""
Test script for AI services with proper initialization.
"""
import asyncio
import sys
import os

# Add the backend directory to Python path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app.services.ai_service import get_ai_service, initialize_ai_service
from app.services.model_router import get_model_router
from app.services.model_settings import ModelPhase
from app.services.xml_prompting_system import get_xml_prompting_system


async def test_ai_service():
    """Test AI service functionality."""
    print("🧪 Testing AI Service...")
    try:
        # Initialize AI service first
        ai_service = await initialize_ai_service()
        print("✅ AI service initialized successfully!")
        
        # Test backend status
        status = await ai_service.get_backend_status()
        print(f"✅ Backend status: {status['initialized']}")
        print(f"✅ Default backend: {status.get('default_backend', 'unknown')}")
        print(f"✅ Available backends: {list(status.get('backends', {}).keys())}")
        
        # Test health check
        is_healthy = await ai_service.health_check()
        print(f"✅ AI service healthy: {is_healthy}")
        
        # Test simple text generation (if healthy)
        if is_healthy:
            try:
                result = await ai_service.generate_text(
                    prompt="Hello, this is a test.",
                    model="qwen3:8b",  # Use a smaller model for testing
                    backend_name="ollama"
                )
                print(f"✅ Text generation works: {result[:100]}...")
            except Exception as e:
                print(f"⚠️  Text generation test: {e}")
        
        return ai_service
        
    except Exception as e:
        print(f"❌ AI service error: {e}")
        return None


async def test_model_router(ai_service):
    """Test model router functionality."""
    print("\n🧪 Testing Model Router...")
    try:
        router = get_model_router()
        print("✅ Model router initialized!")
        
        # Test each phase configuration
        phases = [ModelPhase.vision, ModelPhase.kb_generation, ModelPhase.synthesis, 
                 ModelPhase.chat, ModelPhase.embeddings]
        
        for phase in phases:
            try:
                backend, model, params = await router.resolve(phase)
                backend_name = getattr(backend, 'name', str(backend))
                print(f"✅ {phase.value}: {backend_name} - {model}")
            except Exception as e:
                print(f"⚠️  {phase.value}: {e}")
                
    except Exception as e:
        print(f"❌ Model router error: {e}")


def test_xml_prompting():
    """Test XML prompting system."""
    print("\n🧪 Testing XML Prompting System...")
    try:
        xml_system = get_xml_prompting_system()
        print("✅ XML prompting system initialized!")
        
        # Test prompt generation
        prompt = xml_system.create_media_analysis_prompt(
            media_url='https://example.com/test.jpg',
            media_type='image',
            tweet_context='This is a test tweet',
            author_username='testuser'
        )
        print("✅ XML prompt generated successfully!")
        print(f"✅ Prompt length: {len(prompt)} characters")
        print("✅ First 200 characters:")
        print(prompt[:200] + "...")
        
    except Exception as e:
        print(f"❌ XML prompting error: {e}")


async def main():
    """Main test function."""
    print("🚀 Starting AI Services Test Suite")
    print("=" * 50)
    
    # Test AI service
    ai_service = await test_ai_service()
    
    # Test model router (only if AI service is working)
    if ai_service:
        await test_model_router(ai_service)
    
    # Test XML prompting (doesn't depend on AI service)
    test_xml_prompting()
    
    print("\n" + "=" * 50)
    print("🏁 Test Suite Complete")
    
    # Cleanup
    if ai_service:
        try:
            await ai_service.cleanup()
            print("✅ AI service cleaned up")
        except Exception as e:
            print(f"⚠️  Cleanup warning: {e}")


if __name__ == "__main__":
    asyncio.run(main())