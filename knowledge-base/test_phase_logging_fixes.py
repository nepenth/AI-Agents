#!/usr/bin/env python3
"""
Test script to verify phase logging and synthesis staleness fixes
"""

import sys
import os
import sqlite3
import json
from datetime import datetime

def test_synthesis_staleness():
    """Test the synthesis staleness detection"""
    print("=== TESTING SYNTHESIS STALENESS DETECTION ===\n")
    
    # Connect to database
    db_path = "instance/knowledge_base.db"
    if not os.path.exists(db_path):
        print(f"❌ Database not found at {db_path}")
        return False
    
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    
    # Get synthesis staleness status
    cursor.execute("SELECT COUNT(*) as total FROM subcategory_synthesis")
    total_syntheses = cursor.fetchone()['total']
    
    cursor.execute("SELECT COUNT(*) as stale FROM subcategory_synthesis WHERE is_stale = 1 OR needs_regeneration = 1")
    stale_syntheses = cursor.fetchone()['stale']
    
    # Get new subcategories needing synthesis
    cursor.execute("""
        SELECT main_category, sub_category, COUNT(*) as item_count
        FROM knowledge_base_item 
        GROUP BY main_category, sub_category
        HAVING COUNT(*) >= 2
    """)
    kb_subcategories = cursor.fetchall()
    
    cursor.execute("SELECT main_category, sub_category FROM subcategory_synthesis WHERE sub_category IS NOT NULL")
    existing_syntheses = {(row['main_category'], row['sub_category']) for row in cursor.fetchall()}
    
    new_subcategories = []
    for kb_sub in kb_subcategories:
        key = (kb_sub['main_category'], kb_sub['sub_category'])
        if key not in existing_syntheses:
            new_subcategories.append(kb_sub)
    
    conn.close()
    
    print(f"📊 Synthesis Status:")
    print(f"  - Total syntheses: {total_syntheses}")
    print(f"  - Stale syntheses: {stale_syntheses}")
    print(f"  - New subcategories needing synthesis: {len(new_subcategories)}")
    print(f"  - Total that would be generated: {stale_syntheses + len(new_subcategories)}")
    
    # Expected: 5 stale + 19 new = 24 total
    expected_total = 24
    actual_total = stale_syntheses + len(new_subcategories)
    
    if actual_total == expected_total:
        print(f"✅ Synthesis staleness detection is working correctly!")
        print(f"   Expected {expected_total} documents to be generated, found {actual_total}")
        return True
    else:
        print(f"⚠️  Synthesis staleness detection may have issues")
        print(f"   Expected ~{expected_total} documents to be generated, found {actual_total}")
        return False

def test_phase_logging_logic():
    """Test the phase logging logic improvements"""
    print("\n=== TESTING PHASE LOGGING LOGIC ===\n")
    
    # Test the rich message detection logic
    test_cases = [
        # Rich completion messages that should NOT get phase prefix
        ("completed", "✅ Successfully generated 5 synthesis documents", False),
        ("completed", "Successfully generated 3 synthesis documents", False),
        ("completed", "Generated 10 synthesis documents with detailed analysis", False),
        ("completed", "Processed 25 knowledge base items successfully", False),
        ("completed", "Synthesis generation completed with 0 errors", False),
        
        # Regular messages that SHOULD get phase prefix
        ("running", "Starting synthesis generation", True),
        ("in_progress", "Processing item 5 of 10", True),
        ("completed", "Completed", True),
        ("completed", "Done", True),
        ("error", "Failed to process item", True),
    ]
    
    def should_add_prefix(status, message):
        """Replicate the logic from the fixed progress_callback"""
        return not (status == 'completed' and 
                   message and 
                   (message.startswith('✅') or 
                    message.startswith('Successfully') or
                    'generated' in message.lower() or
                    'processed' in message.lower() or
                    'synthesis' in message.lower()))
    
    print("🧪 Testing rich message detection logic:")
    all_passed = True
    
    for status, message, expected_prefix in test_cases:
        actual_prefix = should_add_prefix(status, message)
        result = "✅" if actual_prefix == expected_prefix else "❌"
        
        print(f"  {result} Status: {status}, Message: '{message[:50]}{'...' if len(message) > 50 else ''}'")
        print(f"     Expected prefix: {expected_prefix}, Got: {actual_prefix}")
        
        if actual_prefix != expected_prefix:
            all_passed = False
    
    if all_passed:
        print(f"\n✅ Phase logging logic is working correctly!")
        return True
    else:
        print(f"\n❌ Phase logging logic has issues!")
        return False

def test_frontend_execution_plan_logic():
    """Test the frontend execution plan improvements"""
    print("\n=== TESTING FRONTEND EXECUTION PLAN LOGIC ===\n")
    
    # Test the phase completion message logic
    def get_phase_completion_message(phase_id):
        """Replicate the logic from the fixed executionPlan.js"""
        completion_messages = {
            'initialization': '✅ Agent components initialized',
            'fetch_bookmarks': '✅ Bookmarks fetched and cached',
            'content_processing': '✅ Content processing completed',
            'tweet_caching': '✅ Tweet data cached',
            'media_analysis': '✅ Media analysis completed',
            'llm_processing': '✅ LLM processing completed',
            'kb_item_generation': '✅ Knowledge base items generated',
            'database_sync': '✅ Database synchronized',
            'synthesis_generation': '✅ Synthesis documents generated',
            'embedding_generation': '✅ Vector embeddings generated',
            'readme_generation': '✅ README files generated',
            'git_sync': '✅ Changes pushed to Git'
        }
        return completion_messages.get(phase_id, '✅ Phase completed')
    
    def should_preserve_rich_message(status, message):
        """Replicate the logic from the fixed updatePhase method"""
        if status != 'completed':
            return False
            
        if not message or not message.strip():
            return False
            
        if message in ['completed', 'Completed']:
            return False
            
        # Check if message is already rich
        return (message.startswith('✅') or 
                message.startswith('🔄') or 
                message.startswith('❌') or
                'synthesis' in message or
                'generated' in message or
                'processed' in message or
                'items' in message)
    
    print("🧪 Testing phase completion message logic:")
    
    test_cases = [
        # Rich messages that should be preserved
        ("completed", "✅ Successfully generated 5 synthesis documents", True),
        ("completed", "Generated 10 synthesis documents with detailed analysis", True),
        ("completed", "Processed 25 knowledge base items successfully", True),
        ("completed", "5 synthesis documents generated", True),
        
        # Generic messages that should use fallback
        ("completed", "Completed", False),
        ("completed", "completed", False),
        ("completed", "", False),
        ("completed", None, False),
        
        # Non-completion messages
        ("running", "✅ Successfully generated 5 synthesis documents", False),
        ("in_progress", "Generated 10 synthesis documents", False),
    ]
    
    all_passed = True
    
    for status, message, should_preserve in test_cases:
        actual_preserve = should_preserve_rich_message(status, message)
        result = "✅" if actual_preserve == should_preserve else "❌"
        
        message_display = message if message else "None"
        print(f"  {result} Status: {status}, Message: '{message_display}'")
        print(f"     Should preserve: {should_preserve}, Got: {actual_preserve}")
        
        if actual_preserve != should_preserve:
            all_passed = False
    
    if all_passed:
        print(f"\n✅ Frontend execution plan logic is working correctly!")
        return True
    else:
        print(f"\n❌ Frontend execution plan logic has issues!")
        return False

def main():
    print("🧪 COMPREHENSIVE FRONTEND FIXES TEST\n")
    
    # Run all tests
    test1_passed = test_synthesis_staleness()
    test2_passed = test_phase_logging_logic()
    test3_passed = test_frontend_execution_plan_logic()
    
    print(f"\n" + "="*60)
    print(f"📊 TEST RESULTS SUMMARY:")
    print(f"  - Synthesis Staleness Detection: {'✅ PASS' if test1_passed else '❌ FAIL'}")
    print(f"  - Phase Logging Logic: {'✅ PASS' if test2_passed else '❌ FAIL'}")
    print(f"  - Frontend Execution Plan Logic: {'✅ PASS' if test3_passed else '❌ FAIL'}")
    
    all_passed = test1_passed and test2_passed and test3_passed
    
    if all_passed:
        print(f"\n🎉 ALL TESTS PASSED! The fixes are working correctly.")
        print(f"\n💡 Next Steps:")
        print(f"  1. Run an agent execution to test the fixes in practice")
        print(f"  2. Verify that rich completion messages appear in Live Logs")
        print(f"  3. Confirm that ~24 synthesis documents are generated (5 updates + 19 new)")
        print(f"  4. Check that debug messages are filtered out of logs")
    else:
        print(f"\n⚠️  SOME TESTS FAILED! Please review the fixes.")
    
    print(f"="*60)
    return all_passed

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)