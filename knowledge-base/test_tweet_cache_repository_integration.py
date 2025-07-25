"""
Integration test for TweetCache Repository

Tests the TweetCacheRepository with actual database operations.
"""

import sys
sys.path.insert(0, '.')

from datetime import datetime, timezone
from knowledge_base_agent.web import app
from knowledge_base_agent.repositories import TweetCacheRepository
from knowledge_base_agent.models import db, TweetCache


def test_tweet_cache_repository_integration():
    """Test TweetCacheRepository with actual database operations."""
    
    with app.app_context():
        # Initialize repository
        repo = TweetCacheRepository()
        
        # Test data
        test_tweet_data = {
            'tweet_id': 'test_integration_123',
            'bookmarked_tweet_id': 'bookmark_integration_123',
            'is_thread': False,
            'source': 'twitter',
            'display_title': 'Integration Test Tweet',
            'full_text': 'This is an integration test tweet content for searching',
            'main_category': 'Technology',
            'sub_category': 'Testing',
            'cache_complete': True,
            'media_processed': False,
            'categories_processed': True,
            'kb_item_created': False
        }
        
        print("🧪 Starting TweetCache Repository Integration Tests")
        
        # Cleanup any existing test data first
        print("\n0. Cleaning up any existing test data...")
        try:
            test_tweet_ids = ['test_integration_123', 'bulk_test_1', 'bulk_test_2']
            for tweet_id in test_tweet_ids:
                repo.delete(tweet_id)
            print("✅ Cleanup completed")
        except Exception as e:
            print(f"⚠️ Cleanup warning (expected if no existing data): {e}")
        
        # Test 1: Create tweet
        print("\n1. Testing tweet creation...")
        try:
            created_tweet = repo.create(test_tweet_data)
            print(f"✅ Tweet created successfully: {created_tweet.tweet_id}")
            assert created_tweet.tweet_id == test_tweet_data['tweet_id']
            assert created_tweet.main_category == 'Technology'
        except Exception as e:
            print(f"❌ Tweet creation failed: {e}")
            return False
        
        # Test 2: Get tweet by ID
        print("\n2. Testing get by ID...")
        try:
            retrieved_tweet = repo.get_by_id('test_integration_123')
            print(f"✅ Tweet retrieved successfully: {retrieved_tweet.tweet_id}")
            assert retrieved_tweet is not None
            assert retrieved_tweet.display_title == 'Integration Test Tweet'
        except Exception as e:
            print(f"❌ Get by ID failed: {e}")
            return False
        
        # Test 3: Update tweet
        print("\n3. Testing tweet update...")
        try:
            update_data = {
                'media_processed': True,
                'kb_item_created': True,
                'display_title': 'Updated Integration Test Tweet'
            }
            updated_tweet = repo.update('test_integration_123', update_data)
            print(f"✅ Tweet updated successfully: {updated_tweet.display_title}")
            assert updated_tweet.media_processed == True
            assert updated_tweet.kb_item_created == True
            assert updated_tweet.display_title == 'Updated Integration Test Tweet'
        except Exception as e:
            print(f"❌ Tweet update failed: {e}")
            return False
        
        # Test 4: Get by processing status
        print("\n4. Testing get by processing status...")
        try:
            status_filters = {'cache_complete': True, 'media_processed': True}
            tweets = repo.get_by_processing_status(status_filters, limit=10)
            print(f"✅ Found {len(tweets)} tweets with specified processing status")
            assert len(tweets) >= 1  # Should find our test tweet
        except Exception as e:
            print(f"❌ Get by processing status failed: {e}")
            return False
        
        # Test 5: Get by category
        print("\n5. Testing get by category...")
        try:
            tweets = repo.get_by_category('Technology', 'Testing', limit=10)
            print(f"✅ Found {len(tweets)} tweets in Technology/Testing category")
            assert len(tweets) >= 1  # Should find our test tweet
        except Exception as e:
            print(f"❌ Get by category failed: {e}")
            return False
        
        # Test 6: Full-text search
        print("\n6. Testing full-text search...")
        try:
            tweets = repo.full_text_search('integration test', limit=10)
            print(f"✅ Full-text search found {len(tweets)} tweets")
            # Note: This might be 0 if full-text indexing isn't set up, which is OK
        except Exception as e:
            print(f"❌ Full-text search failed: {e}")
            return False
        
        # Test 7: Set reprocessing flag
        print("\n7. Testing reprocessing flag management...")
        try:
            success = repo.set_reprocessing_flag(
                'test_integration_123', 
                'force_reprocess_pipeline', 
                'integration_test'
            )
            print(f"✅ Reprocessing flag set successfully: {success}")
            assert success == True
            
            # Verify flag was set
            tweet = repo.get_by_id('test_integration_123')
            assert tweet.force_reprocess_pipeline == True
            assert tweet.reprocess_requested_by == 'integration_test'
        except Exception as e:
            print(f"❌ Set reprocessing flag failed: {e}")
            return False
        
        # Test 8: Get tweets needing reprocessing
        print("\n8. Testing get tweets needing reprocessing...")
        try:
            tweets = repo.get_tweets_needing_reprocessing('force_reprocess_pipeline')
            print(f"✅ Found {len(tweets)} tweets needing reprocessing")
            assert len(tweets) >= 1  # Should find our test tweet
        except Exception as e:
            print(f"❌ Get tweets needing reprocessing failed: {e}")
            return False
        
        # Test 9: Clear reprocessing flags
        print("\n9. Testing clear reprocessing flags...")
        try:
            success = repo.clear_reprocessing_flags('test_integration_123')
            print(f"✅ Reprocessing flags cleared successfully: {success}")
            assert success == True
            
            # Verify flags were cleared
            tweet = repo.get_by_id('test_integration_123')
            assert tweet.force_reprocess_pipeline == False
            assert tweet.reprocess_requested_by is None
        except Exception as e:
            print(f"❌ Clear reprocessing flags failed: {e}")
            return False
        
        # Test 10: Get processing statistics
        print("\n10. Testing processing statistics...")
        try:
            stats = repo.get_processing_statistics()
            print(f"✅ Processing statistics retrieved successfully")
            print(f"   Total tweets: {stats['total_tweets']}")
            print(f"   Completion rate: {stats['processing_completion']['completion_rate']:.1f}%")
            assert 'total_tweets' in stats
            assert 'processing_completion' in stats
            assert stats['total_tweets'] >= 1
        except Exception as e:
            print(f"❌ Get processing statistics failed: {e}")
            return False
        
        # Test 11: Bulk operations
        print("\n11. Testing bulk operations...")
        try:
            # Create additional test tweets for bulk operations
            bulk_data = [
                {
                    'tweet_id': 'bulk_test_1',
                    'bookmarked_tweet_id': 'bulk_bookmark_1',
                    'source': 'twitter',
                    'display_title': 'Bulk Test Tweet 1',
                    'cache_complete': False
                },
                {
                    'tweet_id': 'bulk_test_2',
                    'bookmarked_tweet_id': 'bulk_bookmark_2',
                    'source': 'twitter',
                    'display_title': 'Bulk Test Tweet 2',
                    'cache_complete': False
                }
            ]
            
            bulk_tweets = repo.bulk_create(bulk_data)
            print(f"✅ Bulk created {len(bulk_tweets)} tweets")
            assert len(bulk_tweets) == 2
            
            # Test bulk reprocessing flag setting
            tweet_ids = ['bulk_test_1', 'bulk_test_2']
            updated_count = repo.bulk_set_reprocessing_flags(
                tweet_ids, 'force_recache', 'bulk_test'
            )
            print(f"✅ Bulk set reprocessing flags for {updated_count} tweets")
            assert updated_count == 2
            
        except Exception as e:
            print(f"❌ Bulk operations failed: {e}")
            return False
        
        # Cleanup: Delete test tweets
        print("\n12. Cleaning up test data...")
        try:
            test_tweet_ids = ['test_integration_123', 'bulk_test_1', 'bulk_test_2']
            for tweet_id in test_tweet_ids:
                success = repo.delete(tweet_id)
                if success:
                    print(f"✅ Deleted test tweet: {tweet_id}")
                else:
                    print(f"⚠️ Test tweet not found for deletion: {tweet_id}")
        except Exception as e:
            print(f"❌ Cleanup failed: {e}")
            return False
        
        print("\n🎉 All TweetCache Repository integration tests passed!")
        return True


if __name__ == '__main__':
    success = test_tweet_cache_repository_integration()
    if success:
        print("\n✅ Integration test completed successfully!")
        exit(0)
    else:
        print("\n❌ Integration test failed!")
        exit(1)