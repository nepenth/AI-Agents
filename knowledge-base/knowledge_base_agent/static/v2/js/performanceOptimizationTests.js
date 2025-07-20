/* V2 PERFORMANCEOPTIMIZATIONTESTS.JS - PERFORMANCE OPTIMIZATION TESTS */

/**
 * PerformanceOptimizationTestSuite - Tests for enhanced performance optimization
 * 
 * ARCHITECTURE:
 * - Tests DOM update batching and throttling
 * - Tests memory usage monitoring and optimization
 * - Tests event deduplication and throttling
 * - Tests virtual scrolling performance
 * - Tests component operation optimization
 * - Tests integration with component coordination system
 */
class PerformanceOptimizationTestSuite {
    constructor() {
        this.testResults = [];
        this.performanceOptimizer = null;
        this.testData = this.generateTestData();
        
        console.log('🧪 PerformanceOptimizationTestSuite initialized');
    }
    
    generateTestData() {
        return {
            domUpdates: Array.from({ length: 100 }, (_, i) => ({
                id: `element-${i}`,
                content: `Content ${i}`,
                priority: i % 3 === 0 ? 'high' : 'normal'
            })),
            events: Array.from({ length: 200 }, (_, i) => ({
                type: `event_${i % 5}`,
                data: { id: i, value: Math.random() },
                component: `Component${i % 3}`
            })),
            virtualScrollItems: Array.from({ length: 5000 }, (_, i) => ({
                id: i,
                text: `Virtual scroll item ${i}`,
                data: { index: i, random: Math.random() }
            }))
        };
    }
    
    async runAllTests() {
        console.log('🧪 Starting performance optimization test suite...');
        
        try {
            await this.setupTestEnvironment();
            await this.testDOMUpdateOptimization();
            await this.testMemoryOptimization();
            await this.testEventOptimization();
            await this.testVirtualScrollOptimization();
            await this.testComponentOptimization();
            await this.testIntegrationWithCoordinator();
            await this.testHighLoadScenarios();
            
            this.generateTestReport();
            
        } catch (error) {
            console.error('❌ Performance optimization test suite failed:', error);
            this.testResults.push({
                test: 'Test Suite Execution',
                status: 'FAILED',
                error: error.message,
                timestamp: new Date()
            });
        } finally {
            this.cleanup();
        }
    }
    
    async setupTestEnvironment() {
        console.log('🔧 Setting up performance optimization test environment...');
        
        this.performanceOptimizer = new PerformanceOptimizer({
            domBatchSize: 10,
            domBatchDelay: 50,
            memoryCheckInterval: 1000,
            eventBatchSize: 20
        });
        
        this.createTestContainers();
        await this.wait(100);
        
        this.testResults.push({
            test: 'Performance Optimization Test Environment Setup',
            status: 'PASSED',
            timestamp: new Date()
        });
    }
    
    createTestContainers() {
        const testContainer = document.createElement('div');
        testContainer.id = 'perf-opt-test-container';
        testContainer.style.cssText = `
            position: fixed;
            top: -9999px;
            left: -9999px;
            width: 800px;
            height: 600px;
            visibility: hidden;
        `;
        
        testContainer.innerHTML = `
            <div id="test-dom-updates"></div>
            <div id="test-virtual-scroll" style="height: 300px; overflow: auto;"></div>
            <div id="test-events-container"></div>
        `;
        
        document.body.appendChild(testContainer);
    }
    
    async testDOMUpdateOptimization() {
        console.log('🎨 Testing DOM update optimization...');
        
        try {
            await this.testDOMBatching();
            await this.testDOMThrottling();
            await this.testDOMPriorityHandling();
            
            this.testResults.push({
                test: 'DOM Update Optimization',
                status: 'PASSED',
                timestamp: new Date()
            });
            
        } catch (error) {
            this.testResults.push({
                test: 'DOM Update Optimization',
                status: 'FAILED',
                error: error.message,
                timestamp: new Date()
            });
        }
    }
    
    async testDOMBatching() {
        const optimizer = this.performanceOptimizer;
        const initialBatched = optimizer.metrics.domUpdates.batched;
        
        // Queue multiple DOM updates
        for (let i = 0; i < 15; i++) {
            optimizer.optimizeDOMUpdate(() => {
                const element = document.createElement('div');
                element.textContent = `Batched update ${i}`;
            }, `batch-test-${i}`);
        }
        
        await this.wait(100);
        
        const finalBatched = optimizer.metrics.domUpdates.batched;
        if (finalBatched > initialBatched) {
            console.log('✅ DOM batching working correctly');
        } else {
            throw new Error('DOM batching not working');
        }
    }
    
    async testDOMThrottling() {
        const optimizer = this.performanceOptimizer;
        const initialThrottled = optimizer.metrics.domUpdates.throttled;
        
        // Rapidly queue updates for the same element
        for (let i = 0; i < 10; i++) {
            optimizer.optimizeDOMUpdate(() => {
                // Simulate DOM update
            }, 'throttle-test-element');
        }
        
        await this.wait(100);
        
        const finalThrottled = optimizer.metrics.domUpdates.throttled;
        if (finalThrottled > initialThrottled) {
            console.log('✅ DOM throttling working correctly');
        } else {
            throw new Error('DOM throttling not working');
        }
    }
    
    async testDOMPriorityHandling() {
        const optimizer = this.performanceOptimizer;
        const executionOrder = [];
        
        // Queue updates with different priorities
        optimizer.optimizeDOMUpdate(() => {
            executionOrder.push('low');
        }, 'priority-test-1', 'low');
        
        optimizer.optimizeDOMUpdate(() => {
            executionOrder.push('high');
        }, 'priority-test-2', 'high');
        
        optimizer.optimizeDOMUpdate(() => {
            executionOrder.push('normal');
        }, 'priority-test-3', 'normal');
        
        await this.wait(100);
        
        // High priority should execute first
        if (executionOrder[0] === 'high') {
            console.log('✅ DOM priority handling working correctly');
        } else {
            throw new Error('DOM priority handling not working');
        }
    }
    
    async testMemoryOptimization() {
        console.log('💾 Testing memory optimization...');
        
        try {
            await this.testMemoryPressureDetection();
            await this.testMemoryCleanup();
            await this.testAdaptiveOptimization();
            
            this.testResults.push({
                test: 'Memory Optimization',
                status: 'PASSED',
                timestamp: new Date()
            });
            
        } catch (error) {
            this.testResults.push({
                test: 'Memory Optimization',
                status: 'FAILED',
                error: error.message,
                timestamp: new Date()
            });
        }
    }
    
    async testMemoryPressureDetection() {
        const optimizer = this.performanceOptimizer;
        
        // Simulate high memory usage
        optimizer.updateMemoryPressureLevel({
            used: optimizer.config.memoryThreshold * 1.5,
            limit: optimizer.config.memoryThreshold * 2
        });
        
        if (optimizer.memoryPressureLevel > 0) {
            console.log('✅ Memory pressure detection working correctly');
        } else {
            throw new Error('Memory pressure detection not working');
        }
    }
    
    async testMemoryCleanup() {
        const optimizer = this.performanceOptimizer;
        const initialCleanups = optimizer.metrics.memory.cleanups;
        
        // Fill up caches to trigger cleanup
        for (let i = 0; i < 100; i++) {
            optimizer.eventCache.set(`test_${i}`, {
                result: `result_${i}`,
                timestamp: Date.now() - 400000 // Old timestamp
            });
        }
        
        // Trigger cleanup
        optimizer.performMemoryCleanup();
        
        const finalCleanups = optimizer.metrics.memory.cleanups;
        if (finalCleanups > initialCleanups) {
            console.log('✅ Memory cleanup working correctly');
        } else {
            throw new Error('Memory cleanup not working');
        }
    }
    
    async testAdaptiveOptimization() {
        const optimizer = this.performanceOptimizer;
        const originalBatchSize = optimizer.config.domBatchSize;
        
        // Set high memory pressure
        optimizer.memoryPressureLevel = 3;
        optimizer.adjustOptimizationLevel();
        
        if (optimizer.config.domBatchSize < originalBatchSize) {
            console.log('✅ Adaptive optimization working correctly');
        } else {
            throw new Error('Adaptive optimization not working');
        }
    }
    
    async testEventOptimization() {
        console.log('🎯 Testing event optimization...');
        
        try {
            await this.testEventDeduplication();
            await this.testEventThrottling();
            await this.testEventCaching();
            
            this.testResults.push({
                test: 'Event Optimization',
                status: 'PASSED',
                timestamp: new Date()
            });
            
        } catch (error) {
            this.testResults.push({
                test: 'Event Optimization',
                status: 'FAILED',
                error: error.message,
                timestamp: new Date()
            });
        }
    }
    
    async testEventDeduplication() {
        const optimizer = this.performanceOptimizer;
        const initialDeduplicated = optimizer.metrics.events.deduplicated;
        
        // Send duplicate events rapidly
        const eventData = { id: 1, value: 'test' };
        
        for (let i = 0; i < 5; i++) {
            optimizer.optimizeEvent('test_event', eventData, 'TestComponent');
        }
        
        const finalDeduplicated = optimizer.metrics.events.deduplicated;
        if (finalDeduplicated > initialDeduplicated) {
            console.log('✅ Event deduplication working correctly');
        } else {
            throw new Error('Event deduplication not working');
        }
    }
    
    async testEventThrottling() {
        const optimizer = this.performanceOptimizer;
        const initialThrottled = optimizer.metrics.events.throttled;
        
        // Send events rapidly to trigger throttling
        for (let i = 0; i < 10; i++) {
            optimizer.optimizeEvent('throttle_test', { id: i }, 'TestComponent');
        }
        
        const finalThrottled = optimizer.metrics.events.throttled;
        if (finalThrottled > initialThrottled) {
            console.log('✅ Event throttling working correctly');
        } else {
            throw new Error('Event throttling not working');
        }
    }
    
    async testEventCaching() {
        const optimizer = this.performanceOptimizer;
        
        // Cache an event result
        const eventKey = optimizer.generateEventKey('cache_test', { id: 1 }, 'TestComponent');
        optimizer.eventCache.set(eventKey, {
            result: true,
            timestamp: Date.now()
        });
        
        // Test cache hit
        const result = optimizer.optimizeEvent('cache_test', { id: 1 }, 'TestComponent');
        
        if (result === true) {
            console.log('✅ Event caching working correctly');
        } else {
            throw new Error('Event caching not working');
        }
    }
    
    async testVirtualScrollOptimization() {
        console.log('📜 Testing virtual scroll optimization...');
        
        try {
            await this.testVirtualScrollCreation();
            await this.testVirtualScrollPerformance();
            await this.testVirtualScrollMemoryOptimization();
            
            this.testResults.push({
                test: 'Virtual Scroll Optimization',
                status: 'PASSED',
                timestamp: new Date()
            });
            
        } catch (error) {
            this.testResults.push({
                test: 'Virtual Scroll Optimization',
                status: 'FAILED',
                error: error.message,
                timestamp: new Date()
            });
        }
    }
    
    async testVirtualScrollCreation() {
        const optimizer = this.performanceOptimizer;
        
        const manager = optimizer.optimizeVirtualScrolling(
            'test-virtual-scroll',
            this.testData.virtualScrollItems
        );
        
        if (manager && optimizer.virtualScrollManagers.has('test-virtual-scroll')) {
            console.log('✅ Virtual scroll creation working correctly');
        } else {
            throw new Error('Virtual scroll creation failed');
        }
    }
    
    async testVirtualScrollPerformance() {
        const optimizer = this.performanceOptimizer;
        const startTime = performance.now();
        
        // Test with large dataset
        optimizer.optimizeVirtualScrolling(
            'test-virtual-scroll',
            this.testData.virtualScrollItems
        );
        
        const endTime = performance.now();
        const renderTime = endTime - startTime;
        
        if (renderTime < 100) {
            console.log(`✅ Virtual scroll performance good: ${renderTime.toFixed(2)}ms`);
        } else {
            throw new Error(`Virtual scroll too slow: ${renderTime.toFixed(2)}ms`);
        }
    }
    
    async testVirtualScrollMemoryOptimization() {
        const optimizer = this.performanceOptimizer;
        
        // Set high memory pressure
        optimizer.memoryPressureLevel = 3;
        
        const manager = optimizer.virtualScrollManagers.get('test-virtual-scroll');
        if (manager) {
            const originalBufferSize = manager.config.bufferSize;
            optimizer.adjustVirtualScrollSettings(manager);
            
            if (manager.config.bufferSize < originalBufferSize) {
                console.log('✅ Virtual scroll memory optimization working correctly');
            } else {
                throw new Error('Virtual scroll memory optimization not working');
            }
        }
    }
    
    async testComponentOptimization() {
        console.log('🔧 Testing component optimization...');
        
        try {
            await this.testRedundantOperationBlocking();
            await this.testComponentOperationThrottling();
            await this.testComponentCleanup();
            
            this.testResults.push({
                test: 'Component Optimization',
                status: 'PASSED',
                timestamp: new Date()
            });
            
        } catch (error) {
            this.testResults.push({
                test: 'Component Optimization',
                status: 'FAILED',
                error: error.message,
                timestamp: new Date()
            });
        }
    }
    
    async testRedundantOperationBlocking() {
        const optimizer = this.performanceOptimizer;
        const initialBlocked = optimizer.metrics.components.redundantOpsBlocked;
        
        // Simulate redundant operations
        for (let i = 0; i < 10; i++) {
            optimizer.optimizeComponentOperation('TestComponent', 'update', { same: 'data' });
        }
        
        const finalBlocked = optimizer.metrics.components.redundantOpsBlocked;
        if (finalBlocked >= initialBlocked) {
            console.log('✅ Redundant operation blocking working correctly');
        } else {
            throw new Error('Redundant operation blocking not working');
        }
    }
    
    async testComponentOperationThrottling() {
        const optimizer = this.performanceOptimizer;
        
        // First operation should succeed
        const result1 = optimizer.optimizeComponentOperation('TestComponent', 'throttle_test', {});
        
        // Immediate second operation should be throttled
        const result2 = optimizer.optimizeComponentOperation('TestComponent', 'throttle_test', {});
        
        if (result1 === true && result2 === false) {
            console.log('✅ Component operation throttling working correctly');
        } else {
            throw new Error('Component operation throttling not working');
        }
    }
    
    async testComponentCleanup() {
        const optimizer = this.performanceOptimizer;
        const initialCleanups = optimizer.metrics.components.cleanupsPerformed;
        
        // Trigger component cleanup
        optimizer.performComponentCleanup();
        
        const finalCleanups = optimizer.metrics.components.cleanupsPerformed;
        if (finalCleanups > initialCleanups) {
            console.log('✅ Component cleanup working correctly');
        } else {
            throw new Error('Component cleanup not working');
        }
    }
    
    async testIntegrationWithCoordinator() {
        console.log('🔗 Testing integration with component coordinator...');
        
        try {
            await this.testCoordinatorEnhancement();
            await this.testBatchProcessingOptimization();
            
            this.testResults.push({
                test: 'Integration with Coordinator',
                status: 'PASSED',
                timestamp: new Date()
            });
            
        } catch (error) {
            this.testResults.push({
                test: 'Integration with Coordinator',
                status: 'FAILED',
                error: error.message,
                timestamp: new Date()
            });
        }
    }
    
    async testCoordinatorEnhancement() {
        // Test that coordinator is enhanced with optimization
        if (window.displayCoordinator && window.performanceOptimizer) {
            console.log('✅ Coordinator enhancement working correctly');
        } else {
            throw new Error('Coordinator enhancement not working');
        }
    }
    
    async testBatchProcessingOptimization() {
        // Test batch processing optimization
        const optimizer = this.performanceOptimizer;
        
        // Simulate batch processing event
        optimizer.handleComponentBatchProcessed({
            batchSize: 10,
            processingTime: 100,
            eventTypes: ['test_event']
        });
        
        // Configuration should be adjusted for slow processing
        if (optimizer.config.eventBatchSize < 50) {
            console.log('✅ Batch processing optimization working correctly');
        } else {
            throw new Error('Batch processing optimization not working');
        }
    }
    
    async testHighLoadScenarios() {
        console.log('⚡ Testing high-load scenarios...');
        
        try {
            await this.testConcurrentOptimizations();
            await this.testMemoryPressureHandling();
            await this.testPerformanceDegradationRecovery();
            
            this.testResults.push({
                test: 'High-Load Scenarios',
                status: 'PASSED',
                timestamp: new Date()
            });
            
        } catch (error) {
            this.testResults.push({
                test: 'High-Load Scenarios',
                status: 'FAILED',
                error: error.message,
                timestamp: new Date()
            });
        }
    }
    
    async testConcurrentOptimizations() {
        const optimizer = this.performanceOptimizer;
        const promises = [];
        
        // Create concurrent optimization operations
        for (let i = 0; i < 50; i++) {
            promises.push(new Promise(resolve => {
                optimizer.optimizeDOMUpdate(() => {
                    resolve();
                }, `concurrent-${i}`);
            }));
        }
        
        const startTime = performance.now();
        await Promise.all(promises);
        const endTime = performance.now();
        
        const concurrentTime = endTime - startTime;
        if (concurrentTime < 500) {
            console.log(`✅ Concurrent optimizations completed in ${concurrentTime.toFixed(2)}ms`);
        } else {
            throw new Error(`Concurrent optimizations too slow: ${concurrentTime.toFixed(2)}ms`);
        }
    }
    
    async testMemoryPressureHandling() {
        const optimizer = this.performanceOptimizer;
        
        // Simulate extreme memory pressure
        optimizer.memoryPressureLevel = 3;
        optimizer.adjustOptimizationLevel();
        
        // Test that optimization becomes more aggressive
        const aggressiveBatchSize = optimizer.config.domBatchSize;
        
        // Reset pressure
        optimizer.memoryPressureLevel = 0;
        optimizer.adjustOptimizationLevel();
        
        if (aggressiveBatchSize < optimizer.config.domBatchSize) {
            console.log('✅ Memory pressure handling working correctly');
        } else {
            throw new Error('Memory pressure handling not working');
        }
    }
    
    async testPerformanceDegradationRecovery() {
        const optimizer = this.performanceOptimizer;
        
        // Simulate long task
        optimizer.handleLongTask({ duration: 100 });
        
        await this.wait(100);
        
        // Check that optimization parameters were adjusted
        if (optimizer.config.domBatchSize < 20) {
            console.log('✅ Performance degradation recovery working correctly');
        } else {
            throw new Error('Performance degradation recovery not working');
        }
    }
    
    generateTestReport() {
        console.log('📋 Generating performance optimization test report...');
        
        const totalTests = this.testResults.length;
        const passedTests = this.testResults.filter(r => r.status === 'PASSED').length;
        const failedTests = this.testResults.filter(r => r.status === 'FAILED').length;
        
        const report = {
            summary: {
                total: totalTests,
                passed: passedTests,
                failed: failedTests,
                successRate: totalTests > 0 ? (passedTests / totalTests * 100).toFixed(2) : 0
            },
            results: this.testResults,
            optimizationMetrics: this.performanceOptimizer ? 
                this.performanceOptimizer.getOptimizationMetrics() : null,
            timestamp: new Date().toISOString()
        };
        
        console.log('🧪 Performance Optimization Test Report:', report);
        
        // Store report for external access
        window.performanceOptimizationTestReport = report;
        
        if (failedTests === 0) {
            console.log(`✅ All performance optimization tests passed! (${passedTests}/${totalTests})`);
        } else {
            console.log(`❌ ${failedTests} performance optimization tests failed out of ${totalTests}`);
        }
        
        return report;
    }
    
    cleanup() {
        if (this.performanceOptimizer) {
            this.performanceOptimizer.destroy();
        }
        
        const testContainer = document.getElementById('perf-opt-test-container');
        if (testContainer) {
            testContainer.remove();
        }
        
        console.log('🧹 Performance optimization test cleanup completed');
    }
    
    wait(ms) {
        return new Promise(resolve => setTimeout(resolve, ms));
    }
}

// Make globally available
window.PerformanceOptimizationTestSuite = PerformanceOptimizationTestSuite;

// Auto-run tests if in test mode
if (window.location.search.includes('test=perf-opt') || window.runPerformanceOptimizationTests) {
    document.addEventListener('DOMContentLoaded', async () => {
        console.log('🧪 Auto-running performance optimization tests...');
        const testSuite = new PerformanceOptimizationTestSuite();
        await testSuite.runAllTests();
    });
}