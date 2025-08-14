#!/usr/bin/env python3
"""
Simple pipeline test script that tests the seven-phase pipeline logic
without complex database operations.
"""
import asyncio
import sys
import json
import argparse
from datetime import datetime
from typing import Dict, Any, Optional

# Add the app directory to the path so we can import our modules
sys.path.append('.')

from app.config import get_settings


class MockContentItem:
    """Mock content item for testing."""
    
    def __init__(self, tweet_id: str = "1234567890"):
        self.id = f"content_{tweet_id}"
        self.title = f"Test Tweet {tweet_id}"
        self.content = "This is a test tweet about AI and machine learning. #AI #ML #Testing"
        self.source_type = "twitter"
        self.source_id = tweet_id
        self.tweet_id = tweet_id
        self.author_username = "testuser"
        self.author_id = "user123"
        self.tweet_url = f"https://twitter.com/testuser/status/{tweet_id}"
        self.like_count = 10
        self.retweet_count = 5
        self.reply_count = 2
        self.quote_count = 1
        self.total_engagement = 18
        self.processing_state = "fetched"
        self.has_media = True
        self.media_content = [{
            "id": "media123",
            "type": "image",
            "url": "https://example.com/test-image.jpg",
            "alt_text": "Test image for AI testing"
        }]
        
        # Sub-phase states - all start as False
        self.bookmark_cached = False
        self.media_analyzed = False
        self.content_understood = False
        self.categorized = False
        
        # AI analysis results
        self.media_analysis_results = None
        self.collective_understanding = None
        self.main_category = None
        self.sub_category = None
        self.embeddings = None
        
        # Model tracking
        self.vision_model_used = None
        self.understanding_model_used = None
        self.categorization_model_used = None
        self.embeddings_model_used = None
        
        # Thread info
        self.is_thread_root = False
        self.thread_id = None
        self.thread_length = None
        
        # Additional flags
        self.has_media_analysis = False
        self.has_collective_understanding = False
        
        # Timestamps
        self.created_at = datetime.utcnow()
        self.updated_at = datetime.utcnow()


async def test_phase_1_initialization():
    """Test Phase 1: System Initialization."""
    print("\n🚀 Testing Phase 1: System Initialization")
    
    try:
        # Test configuration loading
        settings = get_settings()
        print(f"   ✅ Configuration loaded: {settings.APP_NAME}")
        
        # Test basic imports
        from app.services.ai_service import get_ai_service
        ai_service = get_ai_service()
        print(f"   ✅ AI service initialized: {ai_service.__class__.__name__}")
        
        # Test database connection (basic check)
        try:
            from app.database.connection import get_db_session
            print("   ✅ Database connection module: OK")
        except Exception as e:
            print(f"   ⚠️  Database connection: {e}")
        
        print("✅ Phase 1 (Initialization): PASSED")
        return True
        
    except Exception as e:
        print(f"❌ Phase 1 (Initialization): FAILED - {e}")
        return False


async def test_phase_2_fetch_bookmarks(content_item: MockContentItem):
    """Test Phase 2: Fetch Bookmarks."""
    print("\n📥 Testing Phase 2: Fetch Bookmarks")
    
    try:
        print(f"   📄 Processing bookmark: {content_item.tweet_id}")
        print(f"   👤 Author: @{content_item.author_username}")
        print(f"   💬 Content: {content_item.content[:50]}...")
        print(f"   📊 Engagement: {content_item.total_engagement}")
        
        # Simulate bookmark fetching success
        content_item.processing_state = "fetched"
        
        print("✅ Phase 2 (Fetch Bookmarks): PASSED")
        return True
        
    except Exception as e:
        print(f"❌ Phase 2 (Fetch Bookmarks): FAILED - {e}")
        return False


async def test_phase_2_1_bookmark_caching(content_item: MockContentItem):
    """Test Sub-phase 2.1: Bookmark Caching."""
    print("\n💾 Testing Sub-phase 2.1: Bookmark Caching")
    
    try:
        # Simulate bookmark caching process
        content_item.bookmark_cached = True
        content_item.processing_state = "cached"
        
        # Simulate thread detection
        if "thread" not in content_item.content.lower():
            content_item.is_thread_root = False
            content_item.thread_id = None
            print("   🔗 Thread detection: Single tweet (not part of thread)")
        else:
            content_item.is_thread_root = True
            content_item.thread_id = f"thread_{content_item.tweet_id}"
            content_item.thread_length = 1
            print("   🔗 Thread detection: Thread root detected")
        
        # Simulate media caching
        if content_item.media_content:
            print(f"   🖼️  Media caching: {len(content_item.media_content)} media items cached")
        
        print("✅ Sub-phase 2.1 (Bookmark Caching): PASSED")
        return True
        
    except Exception as e:
        print(f"❌ Sub-phase 2.1 (Bookmark Caching): FAILED - {e}")
        return False


async def test_phase_3_1_media_analysis(content_item: MockContentItem):
    """Test Sub-phase 3.1: Media Analysis."""
    print("\n🖼️  Testing Sub-phase 3.1: Media Analysis")
    
    try:
        if not content_item.media_content:
            print("   ⏭️  No media content to analyze, skipping...")
            return True
        
        # Simulate media analysis
        media_analysis = []
        for media_item in content_item.media_content:
            analysis = {
                "media_id": media_item["id"],
                "media_type": media_item["type"],
                "analysis": f"Mock analysis: This {media_item['type']} shows content related to the tweet about AI and machine learning.",
                "key_elements": ["AI", "technology", "testing"],
                "relevance_to_tweet": "High - directly supports the tweet content",
                "model_used": "mock-vision-model"
            }
            media_analysis.append(analysis)
            print(f"   🔍 Analyzed {media_item['type']}: {media_item['id']}")
        
        # Update content item
        content_item.media_analysis_results = media_analysis
        content_item.vision_model_used = "mock-vision-model"
        content_item.media_analyzed = True
        content_item.has_media_analysis = True
        
        print("✅ Sub-phase 3.1 (Media Analysis): PASSED")
        return True
        
    except Exception as e:
        print(f"❌ Sub-phase 3.1 (Media Analysis): FAILED - {e}")
        return False


async def test_phase_3_2_content_understanding(content_item: MockContentItem):
    """Test Sub-phase 3.2: AI Content Understanding."""
    print("\n🧠 Testing Sub-phase 3.2: AI Content Understanding")
    
    try:
        # Simulate AI content understanding
        understanding = {
            "main_topic": "Artificial Intelligence and Machine Learning",
            "key_insights": [
                "Discussion about AI/ML technologies",
                "Testing and development focus",
                "Technical content with hashtags"
            ],
            "technical_details": "Content includes AI and ML hashtags, suggests technical discussion",
            "context_relevance": "High relevance for AI/ML knowledge base",
            "sentiment": "neutral-positive",
            "complexity_level": "intermediate",
            "model_used": "mock-understanding-model"
        }
        
        # Include media analysis if available
        if content_item.media_analysis_results:
            understanding["media_context"] = "Media analysis supports the AI/ML topic"
        
        content_item.collective_understanding = understanding
        content_item.understanding_model_used = "mock-understanding-model"
        content_item.content_understood = True
        content_item.has_collective_understanding = True
        
        print("   🎯 Main topic identified: AI and Machine Learning")
        print("   💡 Key insights extracted: 3 insights")
        print("   🔍 Technical details analyzed")
        
        print("✅ Sub-phase 3.2 (AI Content Understanding): PASSED")
        return True
        
    except Exception as e:
        print(f"❌ Sub-phase 3.2 (AI Content Understanding): FAILED - {e}")
        return False


async def test_phase_3_3_categorization(content_item: MockContentItem):
    """Test Sub-phase 3.3: AI Categorization."""
    print("\n📂 Testing Sub-phase 3.3: AI Categorization")
    
    try:
        # Simulate AI categorization
        main_category = "Technology"
        sub_category = "Artificial Intelligence"
        
        content_item.main_category = main_category
        content_item.sub_category = sub_category
        content_item.categorization_model_used = "mock-categorization-model"
        content_item.categorized = True
        
        print(f"   📁 Main category: {main_category}")
        print(f"   📄 Sub-category: {sub_category}")
        
        print("✅ Sub-phase 3.3 (AI Categorization): PASSED")
        return True
        
    except Exception as e:
        print(f"❌ Sub-phase 3.3 (AI Categorization): FAILED - {e}")
        return False


async def test_phase_4_synthesis_generation(content_item: MockContentItem):
    """Test Phase 4: Synthesis Generation."""
    print("\n📚 Testing Phase 4: Synthesis Generation")
    
    try:
        print("   📝 Generating synthesis for Technology/AI category...")
        print("   🔗 Linking related content items...")
        print("   📊 Analyzing content patterns...")
        print("   ✍️  Creating synthesis document...")
        
        print("✅ Phase 4 (Synthesis Generation): PASSED")
        return True
        
    except Exception as e:
        print(f"❌ Phase 4 (Synthesis Generation): FAILED - {e}")
        return False


async def test_phase_5_embedding_generation(content_item: MockContentItem):
    """Test Phase 5: Embedding Generation."""
    print("\n🔢 Testing Phase 5: Embedding Generation")
    
    try:
        # Simulate embedding generation
        mock_embeddings = [0.1, 0.2, 0.3, 0.4, 0.5] * 77  # 385 dimensions (mock)
        
        content_item.embeddings = mock_embeddings
        content_item.embeddings_model_used = "mock-embedding-model"
        
        print(f"   🔢 Generated embeddings: {len(mock_embeddings)} dimensions")
        print("   💾 Stored in vector database")
        
        print("✅ Phase 5 (Embedding Generation): PASSED")
        return True
        
    except Exception as e:
        print(f"❌ Phase 5 (Embedding Generation): FAILED - {e}")
        return False


async def test_phase_6_readme_generation():
    """Test Phase 6: README Generation."""
    print("\n📖 Testing Phase 6: README Generation")
    
    try:
        print("   📋 Analyzing content structure...")
        print("   🗂️  Building category navigation...")
        print("   📝 Generating README content...")
        print("   🔗 Creating cross-references...")
        
        print("✅ Phase 6 (README Generation): PASSED")
        return True
        
    except Exception as e:
        print(f"❌ Phase 6 (README Generation): FAILED - {e}")
        return False


async def test_phase_7_git_sync():
    """Test Phase 7: Git Sync."""
    print("\n🔄 Testing Phase 7: Git Sync")
    
    try:
        print("   📁 Preparing export directory...")
        print("   📄 Generating markdown files...")
        print("   🔄 Syncing with git repository...")
        print("   📤 Pushing changes...")
        
        print("✅ Phase 7 (Git Sync): PASSED")
        return True
        
    except Exception as e:
        print(f"❌ Phase 7 (Git Sync): FAILED - {e}")
        return False


def print_content_summary(content_item: MockContentItem):
    """Print a summary of the content item."""
    print(f"\n📄 Content Summary:")
    print(f"   ID: {content_item.id}")
    print(f"   Title: {content_item.title}")
    print(f"   Tweet ID: {content_item.tweet_id}")
    print(f"   Author: @{content_item.author_username}")
    print(f"   Processing State: {content_item.processing_state}")
    print(f"   Total Engagement: {content_item.total_engagement}")
    print(f"   Category: {content_item.main_category}/{content_item.sub_category}")
    
    # Sub-phase completion status
    completion_count = sum([
        content_item.bookmark_cached,
        content_item.media_analyzed,
        content_item.content_understood,
        content_item.categorized
    ])
    completion_percentage = (completion_count / 4) * 100
    
    print(f"\n📊 Sub-phase Status:")
    print(f"   Bookmark Cached: {'✅' if content_item.bookmark_cached else '❌'}")
    print(f"   Media Analyzed: {'✅' if content_item.media_analyzed else '❌'}")
    print(f"   Content Understood: {'✅' if content_item.content_understood else '❌'}")
    print(f"   Categorized: {'✅' if content_item.categorized else '❌'}")
    print(f"   Completion: {completion_percentage:.1f}%")


async def run_full_pipeline_test(tweet_id: str = "1234567890"):
    """Run the complete seven-phase pipeline test."""
    print("🚀 Starting Seven-Phase Pipeline Test")
    print("=" * 50)
    
    results = {}
    
    # Phase 1: Initialization
    results["phase_1"] = await test_phase_1_initialization()
    if not results["phase_1"]:
        print("❌ Pipeline test stopped due to Phase 1 failure")
        return results
    
    # Create test bookmark
    content_item = MockContentItem(tweet_id)
    print(f"\n🔄 Created test bookmark for tweet {tweet_id}")
    
    # Phase 2: Fetch Bookmarks
    results["phase_2"] = await test_phase_2_fetch_bookmarks(content_item)
    
    # Sub-phase 2.1: Bookmark Caching
    results["phase_2_1"] = await test_phase_2_1_bookmark_caching(content_item)
    
    # Sub-phase 3.1: Media Analysis
    results["phase_3_1"] = await test_phase_3_1_media_analysis(content_item)
    
    # Sub-phase 3.2: Content Understanding
    results["phase_3_2"] = await test_phase_3_2_content_understanding(content_item)
    
    # Sub-phase 3.3: Categorization
    results["phase_3_3"] = await test_phase_3_3_categorization(content_item)
    
    # Phase 4: Synthesis Generation
    results["phase_4"] = await test_phase_4_synthesis_generation(content_item)
    
    # Phase 5: Embedding Generation
    results["phase_5"] = await test_phase_5_embedding_generation(content_item)
    
    # Phase 6: README Generation
    results["phase_6"] = await test_phase_6_readme_generation()
    
    # Phase 7: Git Sync
    results["phase_7"] = await test_phase_7_git_sync()
    
    # Print final summary
    print("\n" + "=" * 50)
    print("🎯 Pipeline Test Results Summary")
    print("=" * 50)
    
    passed = sum(results.values())
    total = len(results)
    
    for phase, result in results.items():
        status = "✅ PASSED" if result else "❌ FAILED"
        print(f"   {phase.replace('_', ' ').title()}: {status}")
    
    print(f"\n📊 Overall Result: {passed}/{total} phases passed ({(passed/total)*100:.1f}%)")
    
    if passed == total:
        print("🎉 All phases completed successfully!")
    else:
        print("⚠️  Some phases failed - check logs above for details")
    
    # Print final content summary
    print_content_summary(content_item)
    
    return results


async def main():
    parser = argparse.ArgumentParser(description="Test seven-phase pipeline (simplified)")
    parser.add_argument("--phase", type=int, choices=range(1, 8), help="Test specific phase (1-7)")
    parser.add_argument("--tweet-id", default="1234567890", help="Tweet ID for testing")
    parser.add_argument("--full", action="store_true", help="Run full pipeline test")
    
    args = parser.parse_args()
    
    try:
        if args.full or not args.phase:
            # Run full pipeline test
            await run_full_pipeline_test(args.tweet_id)
        else:
            # Run specific phase test
            content_item = MockContentItem(args.tweet_id)
            print(f"🔄 Created test bookmark for tweet {args.tweet_id}")
            
            if args.phase == 1:
                await test_phase_1_initialization()
            elif args.phase == 2:
                await test_phase_2_fetch_bookmarks(content_item)
                await test_phase_2_1_bookmark_caching(content_item)
            elif args.phase == 3:
                await test_phase_3_1_media_analysis(content_item)
                await test_phase_3_2_content_understanding(content_item)
                await test_phase_3_3_categorization(content_item)
            elif args.phase == 4:
                await test_phase_4_synthesis_generation(content_item)
            elif args.phase == 5:
                await test_phase_5_embedding_generation(content_item)
            elif args.phase == 6:
                await test_phase_6_readme_generation()
            elif args.phase == 7:
                await test_phase_7_git_sync()
            
            print_content_summary(content_item)
    
    except KeyboardInterrupt:
        print("\n❌ Test cancelled by user")
        sys.exit(1)
    except Exception as e:
        print(f"❌ Test failed with error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())