"""
Integration test for TweetProcessingQueue Repository

Tests the TweetProcessingQueueRepository with actual database operations.
"""

import sys
sys.path.insert(0, '.')

from datetime import datetime, timezone, timedelta
from knowledge_base_agent.web import app
from knowledge_base_agent.repositories import TweetProcessingQueueRepository, TweetCacheRepository
from knowledge_base_agent.models import db, TweetProcessingQueue, TweetCache


def test_processing_queue_repository_integration():
    """Test TweetProcessingQueueRepository with actual database operations."""
    
    with app.app_context():
        # Initialize repositories
        queue_repo = TweetProcessingQueueRepository()
        tweet_repo = TweetCacheRepository()
        
        print("🧪 Starting TweetProcessingQueue Repository Integration Tests")
        
        # Setup: Create a test tweet first (required for foreign key)
        print("\n0. Setting up test data...")
        try:
            # Cleanup any existing test data first
            test_tweet_ids = ['queue_test_tweet_1', 'queue_test_tweet_2', 'queue_test_tweet_3']
            for tweet_id in test_tweet_ids:
                queue_repo.delete(tweet_id)
                tweet_repo.delete(tweet_id)
            
            # Create test tweets
            test_tweets = [
                {
                    'tweet_id': 'queue_test_tweet_1',
                    'bookmarked_tweet_id': 'bookmark_queue_1',
                    'source': 'twitter',
                    'display_title': 'Queue Test Tweet 1'
                },
                {
                    'tweet_id': 'queue_test_tweet_2',
                    'bookmarked_tweet_id': 'bookmark_queue_2',
                    'source': 'twitter',
                    'display_title': 'Queue Test Tweet 2'
                },
                {
                    'tweet_id': 'queue_test_tweet_3',
                    'bookmarked_tweet_id': 'bookmark_queue_3',
                    'source': 'twitter',
                    'display_title': 'Queue Test Tweet 3'
                }
            ]
            
            for tweet_data in test_tweets:
                tweet_repo.create(tweet_data)
            
            print("✅ Test tweets created successfully")
        except Exception as e:
            print(f"❌ Setup failed: {e}")
            return False
        
        # Test 1: Create queue entry
        print("\n1. Testing queue entry creation...")
        try:
            queue_data = {
                'tweet_id': 'queue_test_tweet_1',
                'status': 'unprocessed',
                'processing_phase': 'cache',
                'priority': 1
            }
            created_entry = queue_repo.create(queue_data)
            print(f"✅ Queue entry created successfully: {created_entry.tweet_id}")
            assert created_entry.tweet_id == 'queue_test_tweet_1'
            assert created_entry.status == 'unprocessed'
            assert created_entry.processing_phase == 'cache'
            assert created_entry.priority == 1
        except Exception as e:
            print(f"❌ Queue entry creation failed: {e}")
            return False
        
        # Test 2: Get queue entry by tweet ID
        print("\n2. Testing get by tweet ID...")
        try:
            retrieved_entry = queue_repo.get_by_tweet_id('queue_test_tweet_1')
            print(f"✅ Queue entry retrieved successfully: {retrieved_entry.tweet_id}")
            assert retrieved_entry is not None
            assert retrieved_entry.status == 'unprocessed'
            assert retrieved_entry.processing_phase == 'cache'
        except Exception as e:
            print(f"❌ Get by tweet ID failed: {e}")
            return False
        
        # Test 3: Update status
        print("\n3. Testing status update...")
        try:
            updated_entry = queue_repo.update_status(
                'queue_test_tweet_1', 
                'processing', 
                'media',
                error_message=None,
                increment_retry=False
            )
            print(f"✅ Status updated successfully: {updated_entry.status} - {updated_entry.processing_phase}")
            assert updated_entry.status == 'processing'
            assert updated_entry.processing_phase == 'media'
        except Exception as e:
            print(f"❌ Status update failed: {e}")
            return False
        
        # Test 4: Create more queue entries for bulk operations
        print("\n4. Testing bulk queue entry creation...")
        try:
            bulk_queue_data = [
                {
                    'tweet_id': 'queue_test_tweet_2',
                    'status': 'unprocessed',
                    'processing_phase': 'cache',
                    'priority': 2
                },
                {
                    'tweet_id': 'queue_test_tweet_3',
                    'status': 'unprocessed',
                    'processing_phase': 'categorization',
                    'priority': 0
                }
            ]
            
            bulk_entries = queue_repo.bulk_create(bulk_queue_data)
            print(f"✅ Bulk created {len(bulk_entries)} queue entries")
            assert len(bulk_entries) == 2
        except Exception as e:
            print(f"❌ Bulk creation failed: {e}")
            return False
        
        # Test 5: Get next for processing (priority-based)
        print("\n5. Testing get next for processing...")
        try:
            next_entries = queue_repo.get_next_for_processing(limit=5)
            print(f"✅ Found {len(next_entries)} entries ready for processing")
            # Should find tweet_2 first (priority 2), then tweet_3 (priority 0)
            assert len(next_entries) >= 2
            # Verify priority ordering
            if len(next_entries) >= 2:
                assert next_entries[0].priority >= next_entries[1].priority
        except Exception as e:
            print(f"❌ Get next for processing failed: {e}")
            return False
        
        # Test 6: Mark as processing
        print("\n6. Testing mark as processing...")
        try:
            tweet_ids = ['queue_test_tweet_2', 'queue_test_tweet_3']
            updated_count = queue_repo.mark_as_processing(tweet_ids, 'media')
            print(f"✅ Marked {updated_count} entries as processing")
            assert updated_count == 2
        except Exception as e:
            print(f"❌ Mark as processing failed: {e}")
            return False
        
        # Test 7: Get by status
        print("\n7. Testing get by status...")
        try:
            processing_entries = queue_repo.get_by_status('processing', limit=10)
            print(f"✅ Found {len(processing_entries)} entries with 'processing' status")
            assert len(processing_entries) >= 3  # All our test entries should be processing now
        except Exception as e:
            print(f"❌ Get by status failed: {e}")
            return False
        
        # Test 8: Get by processing phase
        print("\n8. Testing get by processing phase...")
        try:
            media_entries = queue_repo.get_by_processing_phase('media', limit=10)
            print(f"✅ Found {len(media_entries)} entries in 'media' phase")
            assert len(media_entries) >= 3  # All should be in media phase now
        except Exception as e:
            print(f"❌ Get by processing phase failed: {e}")
            return False
        
        # Test 9: Bulk status update
        print("\n9. Testing bulk status update...")
        try:
            updates = [
                {'tweet_id': 'queue_test_tweet_1', 'status': 'failed', 'last_error': 'Test error 1'},
                {'tweet_id': 'queue_test_tweet_2', 'status': 'processed'},
                {'tweet_id': 'queue_test_tweet_3', 'status': 'failed', 'last_error': 'Test error 3'}
            ]
            
            updated_count = queue_repo.bulk_update_status(updates)
            print(f"✅ Bulk updated {updated_count} entries")
            assert updated_count == 3
        except Exception as e:
            print(f"❌ Bulk status update failed: {e}")
            return False
        
        # Test 10: Get failed entries for retry
        print("\n10. Testing get failed entries...")
        try:
            failed_entries = queue_repo.get_failed_entries(max_retries=3, limit=10)
            print(f"✅ Found {len(failed_entries)} failed entries that can be retried")
            assert len(failed_entries) >= 2  # tweet_1 and tweet_3 should be failed
        except Exception as e:
            print(f"❌ Get failed entries failed: {e}")
            return False
        
        # Test 11: Reset for retry
        print("\n11. Testing reset for retry...")
        try:
            success = queue_repo.reset_for_retry('queue_test_tweet_1')
            print(f"✅ Reset for retry successful: {success}")
            assert success == True
            
            # Verify it was reset
            entry = queue_repo.get_by_tweet_id('queue_test_tweet_1')
            assert entry.status == 'unprocessed'
            assert entry.last_error is None
        except Exception as e:
            print(f"❌ Reset for retry failed: {e}")
            return False
        
        # Test 12: Bulk set priority
        print("\n12. Testing bulk set priority...")
        try:
            tweet_ids = ['queue_test_tweet_1', 'queue_test_tweet_2', 'queue_test_tweet_3']
            updated_count = queue_repo.bulk_set_priority(tweet_ids, 5)
            print(f"✅ Bulk set priority for {updated_count} entries")
            assert updated_count == 3
        except Exception as e:
            print(f"❌ Bulk set priority failed: {e}")
            return False
        
        # Test 13: Get queue statistics
        print("\n13. Testing queue statistics...")
        try:
            stats = queue_repo.get_queue_statistics()
            print(f"✅ Queue statistics retrieved successfully")
            print(f"   Total entries: {stats['total_entries']}")
            print(f"   Status distribution: {stats['status_distribution']}")
            print(f"   Priority distribution: {stats['priority_distribution']}")
            assert 'total_entries' in stats
            assert 'status_distribution' in stats
            assert stats['total_entries'] >= 3
        except Exception as e:
            print(f"❌ Get queue statistics failed: {e}")
            return False
        
        # Test 14: Get processing performance
        print("\n14. Testing processing performance...")
        try:
            performance = queue_repo.get_processing_performance(hours=24)
            print(f"✅ Processing performance retrieved successfully")
            print(f"   Processed count: {performance['processed_count']}")
            print(f"   Failed count: {performance['failed_count']}")
            print(f"   Success rate: {performance['success_rate']:.1f}%")
            assert 'processed_count' in performance
            assert 'success_rate' in performance
        except Exception as e:
            print(f"❌ Get processing performance failed: {e}")
            return False
        
        # Cleanup: Delete test data
        print("\n15. Cleaning up test data...")
        try:
            for tweet_id in test_tweet_ids:
                queue_repo.delete(tweet_id)
                tweet_repo.delete(tweet_id)
            print("✅ Cleanup completed successfully")
        except Exception as e:
            print(f"❌ Cleanup failed: {e}")
            return False
        
        print("\n🎉 All TweetProcessingQueue Repository integration tests passed!")
        return True


if __name__ == '__main__':
    success = test_processing_queue_repository_integration()
    if success:
        print("\n✅ Integration test completed successfully!")
        exit(0)
    else:
        print("\n❌ Integration test failed!")
        exit(1)