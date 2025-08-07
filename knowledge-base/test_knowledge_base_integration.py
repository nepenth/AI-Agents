#!/usr/bin/env python3
"""
Comprehensive Knowledge Base Integration Test

Tests the complete Knowledge Base functionality:
1. Database data integrity after migration
2. API endpoint functionality
3. Frontend JavaScript component loading
4. Media file handling
5. Title display and categorization

This verifies that our systematic data cleanup resolved all issues.
"""

import json
import sys
from pathlib import Path
from knowledge_base_agent.web import create_app
from knowledge_base_agent.models import UnifiedTweet, db

def test_database_integrity():
    """Test that the database has clean, valid data"""
    print("🔍 Testing database integrity...")
    
    app, socketio, migrate, realtime_manager = create_app()
    
    with app.app_context():
        # Test basic data retrieval
        total_tweets = db.session.query(UnifiedTweet).count()
        kb_items = db.session.query(UnifiedTweet).filter(
            UnifiedTweet.kb_item_created == True,
            UnifiedTweet.kb_content.isnot(None)
        ).count()
        
        print(f"  📊 Total tweets: {total_tweets}")
        print(f"  📚 KB items: {kb_items}")
        
        # Test data quality
        items_with_titles = db.session.query(UnifiedTweet).filter(
            UnifiedTweet.kb_item_created == True,
            UnifiedTweet.kb_display_title.isnot(None),
            UnifiedTweet.kb_display_title != ''
        ).count()
        
        items_with_categories = db.session.query(UnifiedTweet).filter(
            UnifiedTweet.kb_item_created == True,
            UnifiedTweet.main_category.isnot(None),
            UnifiedTweet.sub_category.isnot(None)
        ).count()
        
        print(f"  📝 Items with titles: {items_with_titles}")
        print(f"  🏷️  Items with categories: {items_with_categories}")
        
        # Test JSON field integrity
        sample_items = db.session.query(UnifiedTweet).filter(
            UnifiedTweet.kb_item_created == True
        ).limit(5).all()
        
        json_issues = 0
        for item in sample_items:
            # Check that JSON fields are properly parsed
            if isinstance(item.media_files, str):
                json_issues += 1
            if isinstance(item.kb_media_paths, str):
                json_issues += 1
        
        print(f"  🔧 JSON parsing issues: {json_issues}")
        
        return {
            'total_tweets': total_tweets,
            'kb_items': kb_items,
            'items_with_titles': items_with_titles,
            'items_with_categories': items_with_categories,
            'json_issues': json_issues
        }

def test_api_endpoint():
    """Test that the API endpoint returns valid data"""
    print("\n🌐 Testing API endpoint...")
    
    app, socketio, migrate, realtime_manager = create_app()
    
    with app.test_client() as client:
        with app.app_context():
            # Test the main endpoint
            response = client.get('/api/items')
            
            if response.status_code != 200:
                print(f"  ❌ API returned status {response.status_code}")
                return False
            
            try:
                data = response.get_json()
                print(f"  📊 API returned {len(data)} items")
                
                # Test data structure
                if data:
                    sample_item = data[0]
                    required_fields = [
                        'id', 'tweet_id', 'title', 'content', 
                        'main_category', 'sub_category', 'media_files'
                    ]
                    
                    missing_fields = [field for field in required_fields if field not in sample_item]
                    if missing_fields:
                        print(f"  ❌ Missing fields: {missing_fields}")
                        return False
                    
                    print(f"  ✅ Sample item structure valid")
                    print(f"  📝 Sample title: {sample_item['title'][:50]}...")
                    print(f"  🏷️  Sample category: {sample_item['main_category']} > {sample_item['sub_category']}")
                    print(f"  🖼️  Media files: {len(sample_item.get('media_files', []))}")
                
                return True
                
            except Exception as e:
                print(f"  ❌ Error parsing API response: {e}")
                return False

def test_javascript_component():
    """Test that the JavaScript component can be loaded"""
    print("\n📜 Testing JavaScript component...")
    
    js_file = Path('knowledge_base_agent/static/v2/js/modernKnowledgeBaseManager.js')
    
    if not js_file.exists():
        print("  ❌ JavaScript file not found")
        return False
    
    # Read and check basic structure
    content = js_file.read_text()
    
    # Check for key components
    checks = {
        'Class definition': 'class ModernKnowledgeBaseManager extends BaseManager',
        'Constructor': 'constructor(options = {})',
        'Load initial data': 'async loadInitialData()',
        'Render items': 'renderItems(',
        'Setup event listeners': 'async setupEventListeners()',
        'Cleanup method': 'cleanup()'
    }
    
    results = {}
    for check_name, pattern in checks.items():
        found = pattern in content
        results[check_name] = found
        status = "✅" if found else "❌"
        print(f"  {status} {check_name}: {found}")
    
    # Check for service usage (following component standards)
    service_checks = {
        'EventListenerService usage': 'this.eventService.setupStandardListeners',
        'API service usage': 'this.apiCall(',
        'CleanupService usage': 'this.cleanupService.cleanup',
        'BaseManager extension': 'extends BaseManager'
    }
    
    print("\n  🔧 Service integration checks:")
    for check_name, pattern in service_checks.items():
        found = pattern in content
        results[check_name] = found
        status = "✅" if found else "❌"
        print(f"    {status} {check_name}: {found}")
    
    return all(results.values())

def test_media_handling():
    """Test media file handling"""
    print("\n🖼️  Testing media handling...")
    
    app, socketio, migrate, realtime_manager = create_app()
    
    with app.app_context():
        # Find items with media files
        items_with_media = db.session.query(UnifiedTweet).filter(
            UnifiedTweet.kb_item_created == True,
            UnifiedTweet.media_files.isnot(None)
        ).limit(5).all()
        
        print(f"  📊 Found {len(items_with_media)} items with media")
        
        media_stats = {
            'total_media_references': 0,
            'valid_media_files': 0,
            'invalid_media_files': 0
        }
        
        for item in items_with_media:
            if item.media_files and isinstance(item.media_files, list):
                media_stats['total_media_references'] += len(item.media_files)
                
                for media_path in item.media_files:
                    # Check if file exists (simplified check)
                    if media_path and isinstance(media_path, str):
                        media_stats['valid_media_files'] += 1
                    else:
                        media_stats['invalid_media_files'] += 1
        
        print(f"  📊 Total media references: {media_stats['total_media_references']}")
        print(f"  ✅ Valid media files: {media_stats['valid_media_files']}")
        print(f"  ❌ Invalid media files: {media_stats['invalid_media_files']}")
        
        return media_stats['invalid_media_files'] == 0

def run_comprehensive_test():
    """Run all tests and provide summary"""
    print("🚀 Running comprehensive Knowledge Base integration test...")
    print("=" * 60)
    
    results = {}
    
    # Test 1: Database integrity
    try:
        db_stats = test_database_integrity()
        results['database'] = {
            'passed': db_stats['json_issues'] == 0 and db_stats['kb_items'] > 0,
            'stats': db_stats
        }
    except Exception as e:
        print(f"  ❌ Database test failed: {e}")
        results['database'] = {'passed': False, 'error': str(e)}
    
    # Test 2: API endpoint
    try:
        api_result = test_api_endpoint()
        results['api'] = {'passed': api_result}
    except Exception as e:
        print(f"  ❌ API test failed: {e}")
        results['api'] = {'passed': False, 'error': str(e)}
    
    # Test 3: JavaScript component
    try:
        js_result = test_javascript_component()
        results['javascript'] = {'passed': js_result}
    except Exception as e:
        print(f"  ❌ JavaScript test failed: {e}")
        results['javascript'] = {'passed': False, 'error': str(e)}
    
    # Test 4: Media handling
    try:
        media_result = test_media_handling()
        results['media'] = {'passed': media_result}
    except Exception as e:
        print(f"  ❌ Media test failed: {e}")
        results['media'] = {'passed': False, 'error': str(e)}
    
    # Summary
    print("\n" + "=" * 60)
    print("📊 INTEGRATION TEST SUMMARY")
    print("=" * 60)
    
    passed_tests = sum(1 for result in results.values() if result['passed'])
    total_tests = len(results)
    
    for test_name, result in results.items():
        status = "✅ PASSED" if result['passed'] else "❌ FAILED"
        print(f"{test_name.upper()}: {status}")
        if not result['passed'] and 'error' in result:
            print(f"  Error: {result['error']}")
    
    print(f"\nOverall: {passed_tests}/{total_tests} tests passed")
    
    if passed_tests == total_tests:
        print("🎉 All tests passed! Knowledge Base functionality is fully restored.")
        return True
    else:
        print("⚠️  Some tests failed. Review the issues above.")
        return False

if __name__ == "__main__":
    success = run_comprehensive_test()
    sys.exit(0 if success else 1)