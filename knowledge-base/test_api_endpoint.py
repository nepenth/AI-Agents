#!/usr/bin/env python3
"""
Test script to verify the Knowledge Base API endpoint works correctly
"""

import json
from knowledge_base_agent.web import create_app
from knowledge_base_agent.models import UnifiedTweet, db

def test_api_endpoint():
    """Test the knowledge base items API endpoint"""
    app, socketio, migrate, realtime_manager = create_app()
    
    with app.test_client() as client:
        with app.app_context():
            # Test the API endpoint
            response = client.get('/api/items')
            
            print(f"Status Code: {response.status_code}")
            
            if response.status_code == 200:
                data = response.get_json()
                print(f"Found {len(data)} items")
                
                # Show first few items
                for i, item in enumerate(data[:3]):
                    print(f"\nItem {i+1}:")
                    print(f"  Tweet ID: {item['tweet_id']}")
                    print(f"  Title: {item['title']}")
                    print(f"  Category: {item['main_category']} > {item['sub_category']}")
                    print(f"  Media files: {len(item.get('media_files', []))}")
                    print(f"  KB media paths: {len(item.get('kb_media_paths', []))}")
                
                return True
            else:
                print(f"Error: {response.get_data(as_text=True)}")
                return False

if __name__ == "__main__":
    success = test_api_endpoint()
    if success:
        print("\n✅ API endpoint test passed!")
    else:
        print("\n❌ API endpoint test failed!")