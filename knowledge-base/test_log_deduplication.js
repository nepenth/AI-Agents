// Test script for log deduplication functionality
// Run this in browser console on the V2 interface

function testLogDeduplication() {
    console.log('🧪 Testing log deduplication...');
    
    // Get the LiveLogsManager instance
    const liveLogsManager = window.dashboardManager?.managers?.liveLogs;
    if (!liveLogsManager) {
        console.error('❌ LiveLogsManager not found');
        return;
    }
    
    // Test 1: Duplicate messages should be filtered
    console.log('Test 1: Duplicate message filtering');
    const duplicateLog = {
        message: 'StateManager initialization complete. Validation stats: {...}',
        level: 'INFO',
        timestamp: new Date().toISOString()
    };
    
    // Add the same log multiple times
    liveLogsManager.addLog(duplicateLog);
    liveLogsManager.addLog(duplicateLog);
    liveLogsManager.addLog(duplicateLog);
    
    console.log('✅ Added 3 duplicate logs - should only show 1');
    
    // Test 2: Different timestamps should create different IDs
    console.log('Test 2: Different timestamps');
    const log1 = {
        message: 'Test message',
        level: 'INFO',
        timestamp: '2024-01-01T10:00:00.000Z'
    };
    
    const log2 = {
        message: 'Test message',
        level: 'INFO',
        timestamp: '2024-01-01T10:00:01.000Z'
    };
    
    const id1 = liveLogsManager.createLogId(log1);
    const id2 = liveLogsManager.createLogId(log2);
    
    console.log('Log ID 1:', id1);
    console.log('Log ID 2:', id2);
    console.log('IDs different:', id1 !== id2 ? '✅' : '❌');
    
    // Test 3: Validation message throttling
    console.log('Test 3: Validation message throttling');
    const validationLog = {
        message: 'KB item phase validation complete. Fixed 0 issues.',
        level: 'INFO',
        timestamp: new Date().toISOString()
    };
    
    // Add multiple validation messages quickly
    for (let i = 0; i < 5; i++) {
        liveLogsManager.addLog({
            ...validationLog,
            timestamp: new Date(Date.now() + i * 100).toISOString()
        });
    }
    
    console.log('✅ Added 5 validation messages - should be throttled');
    
    // Test 4: Hash function consistency
    console.log('Test 4: Hash function consistency');
    const hash1 = liveLogsManager.simpleHash('Test message');
    const hash2 = liveLogsManager.simpleHash('Test message');
    const hash3 = liveLogsManager.simpleHash('Different message');
    
    console.log('Hash 1:', hash1);
    console.log('Hash 2:', hash2);
    console.log('Hash 3:', hash3);
    console.log('Same message hashes equal:', hash1 === hash2 ? '✅' : '❌');
    console.log('Different message hashes different:', hash1 !== hash3 ? '✅' : '❌');
    
    console.log('🧪 Log deduplication tests completed');
}

function testPhaseCompletion() {
    console.log('🧪 Testing phase completion...');
    
    // Get the ExecutionPlanManager instance
    const executionPlanManager = window.dashboardManager?.managers?.executionPlan;
    if (!executionPlanManager) {
        console.error('❌ ExecutionPlanManager not found');
        return;
    }
    
    // Test phase completion with counts
    console.log('Test 1: Phase completion with counts');
    executionPlanManager.updatePhase('tweet_caching', 'completed', 'Caching completed', {
        processed_count: 15,
        total_count: 20
    });
    
    console.log('✅ Updated tweet_caching phase with completion counts');
    
    // Test phase completion with no items needed
    console.log('Test 2: Phase completion with no items needed');
    executionPlanManager.updatePhase('media_analysis', 'completed', 'Media analysis completed', {
        processed_count: 0,
        total_count: 0
    });
    
    console.log('✅ Updated media_analysis phase with no items needed');
    
    // Test phase completion with skipped items
    console.log('Test 3: Phase completion with skipped items');
    executionPlanManager.updatePhase('llm_processing', 'completed', 'LLM processing completed', {
        skipped_count: 10
    });
    
    console.log('✅ Updated llm_processing phase with skipped items');
    
    console.log('🧪 Phase completion tests completed');
}

// Export functions for manual testing
window.testLogDeduplication = testLogDeduplication;
window.testPhaseCompletion = testPhaseCompletion;

console.log('🧪 Test functions loaded. Run testLogDeduplication() or testPhaseCompletion() to test.');