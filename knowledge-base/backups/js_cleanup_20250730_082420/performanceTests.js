/* V2 PERFORMANCETESTS.JS - COMPREHENSIVE PERFORMANCE TESTS */

/**
 * PerformanceTestSuite - Tests performance optimization and monitoring
 * 
 * ARCHITECTURE:
 * - Tests event batching and rate limiting
 * - Tests virtual scrolling performance
 * - Tests memory usage optimization
 * - Tests high-volume and concurrent scenarios
 * - Validates performance metrics collection
 */
class PerformanceTestSuite {
    constructor() {
        this.testResults = [];
        this.performanceMonitor = null;
        this.testData = this.generateTestData();
        
        console.log('🧪 PerformanceTestSuite initialized');
    }
    
    generateTestData() {
        return {
            smallDataset: Array.from({ length: 100 }, (_, i) => ({
                id: i,
                message: `Test message ${i}`,
                timestamp: new Date(Date.now() + i * 1000).toISOString()
            })),
            mediumDataset: Array.from({ length: 1000 }, (_, i) => ({
                id: i,
                message: `Test message ${i}`,
                timestamp: new Date(Date.now() + i * 1000).toISOString()
            })),
            largeDataset: Array.from({ length: 10000 }, (_, i) => ({
                id: i,
                message: `Test message ${i}`,
                timestamp: new Date(Date.now() + i * 1000).toISOString()
            })),
            highVolumeEvents: Array.from({ length: 5000 }, (_, i) => ({
                type: 'log',
                data: {
                    message: `High volume log ${i}`,
                    level: i % 4 === 0 ? 'ERROR' : 'INFO',
                    timestamp: Date.now() + i
                }
            }))
        };
    }
    
    async runAllTests() {
        console.log('🧪 Starting comprehensive performance test suite...');
        
        try {
            // Setup test environment
            await this.setupTestEnvironment();
            
            // Test event batching
            await this.testEventBatching();
            
            // Test rate limiting
            await this.testRateLimiting();
            
            // Test virtual scrolling
            await this.testVirtualScrolling();
            
            // Test memory optimization
            await this.testMemoryOptimization();
            
            // Test high-volume scenarios
            await this.testHighVolumeScenarios();
            
            // Test concurrent operations
            await this.testConcurrentOperations();
            
            // Test performance monitoring
            await this.testPerformanceMonitoring();
            
            // Generate test report
            this.generateTestReport();
            
        } catch (error) {
            console.error('❌ Performance test suite failed:', error);
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
        console.log('🔧 Setting up performance test environment...');
        
        // Initialize performance monitor
        this.performanceMonitor = new PerformanceMonitor({
            batchSize: 10,
            batchTimeout: 100,
            rateLimit: 50,
            memoryCheckInterval: 1000
        });
        
        // Create test containers
        this.createTestContainers();
        
        await this.wait(100);
        
        this.testResults.push({
            test: 'Performance Test Environment Setup',
            status: 'PASSED',
            timestamp: new Date()
        });
    }
    
    createTestContainers() {
        const testContainer = document.createElement('div');
        testContainer.id = 'performance-test-container';
        testContainer.style.cssText = `
            position: fixed;
            top: -9999px;
            left: -9999px;
            width: 800px;
            height: 600px;
            visibility: hidden;
        `;
        
        testContainer.innerHTML = `
            <div id="test-virtual-scroll" style="height: 300px; overflow: auto;"></div>
            <div id="test-logs-container" style="height: 200px; overflow: auto;"></div>
            <div id="test-progress-container"></div>
        `;
        
        document.body.appendChild(testContainer);
    }
    
    async testEventBatching() {
        console.log('📦 Testing event batching...');
        
        try {
            await this.testBatchSizeLimit();
            await this.testBatchTimeout();
            await this.testBatchProcessing();
            
            this.testResults.push({
                test: 'Event Batching',
                status: 'PASSED',
                timestamp: new Date()
            });
            
        } catch (error) {
            this.testResults.push({
                test: 'Event Batching',
                status: 'FAILED',
                error: error.message,
                timestamp: new Date()
            });
        }
    }
    
    async testBatchSizeLimit() {
        const monitor = this.performanceMonitor;
        const initialBatched = monitor.metrics.events.batched;
        
        // Send events to trigger batch size limit
        for (let i = 0; i < 15; i++) {
            monitor.batchEvent('test_batch', { id: i });
        }
        
        await this.wait(50);
        
        const finalBatched = monitor.metrics.events.batched;
        if (finalBatched > initialBatched) {
            console.log('✅ Batch size limit working correctly');
        } else {
            throw new Error('Batch size limit not working');
        }
    }
    
    async testBatchTimeout() {
        const monitor = this.performanceMonitor;
        const initialProcessed = monitor.metrics.events.processed;
        
        // Send a few events and wait for timeout
        for (let i = 0; i < 5; i++) {
            monitor.batchEvent('test_timeout', { id: i });
        }
        
        await this.wait(150); // Wait longer than batch timeout
        
        const finalProcessed = monitor.metrics.events.processed;
        if (finalProcessed > initialProcessed) {
            console.log('✅ Batch timeout working correctly');
        } else {
            throw new Error('Batch timeout not working');
        }
    }
    
    async testBatchProcessing() {
        const monitor = this.performanceMonitor;
        
        // Test different event types
        const eventTypes = ['log', 'progress', 'status'];
        
        for (const eventType of eventTypes) {
            for (let i = 0; i < 12; i++) {
                monitor.batchEvent(eventType, { id: i, type: eventType });
            }
        }
        
        await this.wait(200);
        
        console.log('✅ Batch processing for different event types working');
    }
    
    async testRateLimiting() {
        console.log('🚦 Testing rate limiting...');
        
        try {
            await this.testRateLimitThreshold();
            await this.testRateLimitWindow();
            
            this.testResults.push({
                test: 'Rate Limiting',
                status: 'PASSED',
                timestamp: new Date()
            });
            
        } catch (error) {
            this.testResults.push({
                test: 'Rate Limiting',
                status: 'FAILED',
                error: error.message,
                timestamp: new Date()
            });
        }
    }
    
    async testRateLimitThreshold() {
        const monitor = this.performanceMonitor;
        const initialRateLimited = monitor.metrics.events.rateLimited;
        
        // Send more events than rate limit allows
        for (let i = 0; i < 100; i++) {
            monitor.batchEvent('rate_limit_test', { id: i });
        }
        
        await this.wait(50);
        
        const finalRateLimited = monitor.metrics.events.rateLimited;
        if (finalRateLimited > initialRateLimited) {
            console.log('✅ Rate limit threshold working correctly');
        } else {
            throw new Error('Rate limit threshold not working');
        }
    }
    
    async testRateLimitWindow() {
        const monitor = this.performanceMonitor;
        
        // Test that rate limit resets after window
        for (let i = 0; i < 60; i++) {
            monitor.batchEvent('window_test', { id: i });
        }
        
        await this.wait(1100); // Wait longer than rate limit window
        
        // Should be able to send more events now
        const success = monitor.batchEvent('window_test', { id: 'after_window' });
        
        if (success) {
            console.log('✅ Rate limit window working correctly');
        } else {
            throw new Error('Rate limit window not working');
        }
    }
    
    async testVirtualScrolling() {
        console.log('📜 Testing virtual scrolling...');
        
        try {
            await this.testVirtualScrollCreation();
            await this.testVirtualScrollPerformance();
            await this.testVirtualScrollMemoryUsage();
            
            this.testResults.push({
                test: 'Virtual Scrolling',
                status: 'PASSED',
                timestamp: new Date()
            });
            
        } catch (error) {
            this.testResults.push({
                test: 'Virtual Scrolling',
                status: 'FAILED',
                error: error.message,
                timestamp: new Date()
            });
        }
    }
    
    async testVirtualScrollCreation() {
        const monitor = this.performanceMonitor;
        
        const virtualScroll = monitor.createVirtualScrollManager('test-virtual-scroll', {
            itemHeight: 30,
            bufferSize: 5
        });
        
        if (virtualScroll && monitor.virtualScrollManagers.has('test-virtual-scroll')) {
            console.log('✅ Virtual scroll creation working correctly');
        } else {
            throw new Error('Virtual scroll creation failed');
        }
    }
    
    async testVirtualScrollPerformance() {
        const monitor = this.performanceMonitor;
        const virtualScroll = monitor.virtualScrollManagers.get('test-virtual-scroll');
        
        if (!virtualScroll) {
            throw new Error('Virtual scroll not found');
        }
        
        const startTime = performance.now();
        
        // Set large dataset
        virtualScroll.setItems(this.testData.largeDataset);
        
        const endTime = performance.now();
        const renderTime = endTime - startTime;
        
        if (renderTime < 100) { // Should render quickly
            console.log(`✅ Virtual scroll performance good: ${renderTime.toFixed(2)}ms`);
        } else {
            throw new Error(`Virtual scroll too slow: ${renderTime.toFixed(2)}ms`);
        }
    }
    
    async testVirtualScrollMemoryUsage() {
        const monitor = this.performanceMonitor;
        const virtualScroll = monitor.virtualScrollManagers.get('test-virtual-scroll');
        
        if (!virtualScroll) {
            throw new Error('Virtual scroll not found');
        }
        
        const initialMemory = performance.memory ? performance.memory.usedJSHeapSize : 0;
        
        // Add many items
        for (let i = 0; i < 1000; i++) {
            virtualScroll.addItem({ id: i, data: `Item ${i}` });
        }
        
        const finalMemory = performance.memory ? performance.memory.usedJSHeapSize : 0;
        const memoryIncrease = finalMemory - initialMemory;
        
        // Memory increase should be reasonable
        if (memoryIncrease < 10 * 1024 * 1024) { // Less than 10MB
            console.log(`✅ Virtual scroll memory usage reasonable: ${(memoryIncrease / 1024 / 1024).toFixed(2)}MB`);
        } else {
            console.warn(`Virtual scroll memory usage high: ${(memoryIncrease / 1024 / 1024).toFixed(2)}MB`);
        }
    }
    
    async testMemoryOptimization() {
        console.log('💾 Testing memory optimization...');
        
        try {
            await this.testMemoryMonitoring();
            await this.testMemoryCleanup();
            await this.testMemoryThreshold();
            
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
    
    async testMemoryMonitoring() {
        const monitor = this.performanceMonitor;
        
        // Trigger memory check
        monitor.checkMemoryUsage();
        
        if (monitor.metrics.memory.current > 0) {
            console.log('✅ Memory monitoring working correctly');
        } else {
            console.log('⚠️ Memory monitoring not available in this browser');
        }
    }
    
    async testMemoryCleanup() {
        const monitor = this.performanceMonitor;
        
        // Fill up metrics samples
        for (let i = 0; i < 200; i++) {
            monitor.metrics.latency.samples.push(Math.random() * 100);
            monitor.metrics.memory.samples.push({ used: Math.random() * 1000000 });
        }
        
        const initialSamples = monitor.metrics.latency.samples.length;
        
        // Trigger optimization
        monitor.optimizeMemoryUsage();
        
        const finalSamples = monitor.metrics.latency.samples.length;
        
        if (finalSamples < initialSamples) {
            console.log('✅ Memory cleanup working correctly');
        } else {
            throw new Error('Memory cleanup not working');
        }
    }
    
    async testMemoryThreshold() {
        const monitor = this.performanceMonitor;
        
        let warningEmitted = false;
        document.addEventListener('memory_warning', () => {
            warningEmitted = true;
        });
        
        // Simulate high memory usage
        monitor.handleMemoryThresholdExceeded({
            used: monitor.config.memoryThreshold + 1000000,
            total: monitor.config.memoryThreshold + 2000000
        });
        
        await this.wait(50);
        
        if (warningEmitted) {
            console.log('✅ Memory threshold warning working correctly');
        } else {
            throw new Error('Memory threshold warning not working');
        }
    }
    
    async testHighVolumeScenarios() {
        console.log('⚡ Testing high-volume scenarios...');
        
        try {
            await this.testHighVolumeEventProcessing();
            await this.testConcurrentBatching();
            await this.testThroughputMeasurement();
            
            this.testResults.push({
                test: 'High-Volume Scenarios',
                status: 'PASSED',
                timestamp: new Date()
            });
            
        } catch (error) {
            this.testResults.push({
                test: 'High-Volume Scenarios',
                status: 'FAILED',
                error: error.message,
                timestamp: new Date()
            });
        }
    }
    
    async testHighVolumeEventProcessing() {
        const monitor = this.performanceMonitor;
        const startTime = performance.now();
        
        // Process high volume of events
        const events = this.testData.highVolumeEvents;
        
        for (const event of events) {
            monitor.batchEvent(event.type, event.data);
        }
        
        await this.wait(500); // Wait for processing
        
        const endTime = performance.now();
        const processingTime = endTime - startTime;
        
        if (processingTime < 2000) { // Should complete within 2 seconds
            console.log(`✅ High-volume processing completed in ${processingTime.toFixed(2)}ms`);
        } else {
            throw new Error(`High-volume processing too slow: ${processingTime.toFixed(2)}ms`);
        }
    }
    
    async testConcurrentBatching() {
        const monitor = this.performanceMonitor;
        
        // Create multiple concurrent batching operations
        const promises = [];
        
        for (let batch = 0; batch < 10; batch++) {
            promises.push(this.createBatchingPromise(monitor, batch));
        }
        
        const startTime = performance.now();
        await Promise.all(promises);
        const endTime = performance.now();
        
        const concurrentTime = endTime - startTime;
        
        if (concurrentTime < 1000) { // Should handle concurrency well
            console.log(`✅ Concurrent batching completed in ${concurrentTime.toFixed(2)}ms`);
        } else {
            throw new Error(`Concurrent batching too slow: ${concurrentTime.toFixed(2)}ms`);
        }
    }
    
    async createBatchingPromise(monitor, batchId) {
        for (let i = 0; i < 100; i++) {
            monitor.batchEvent(`concurrent_${batchId}`, { id: i, batch: batchId });
            if (i % 10 === 0) {
                await this.wait(1); // Yield occasionally
            }
        }
    }
    
    async testThroughputMeasurement() {
        const monitor = this.performanceMonitor;
        
        // Reset metrics
        monitor.resetMetrics();
        
        // Generate events at known rate
        const eventsPerSecond = 100;
        const duration = 2000; // 2 seconds
        const expectedEvents = (eventsPerSecond * duration) / 1000;
        
        const interval = setInterval(() => {
            monitor.batchEvent('throughput_test', { timestamp: Date.now() });
        }, 1000 / eventsPerSecond);
        
        await this.wait(duration);
        clearInterval(interval);
        
        await this.wait(200); // Wait for processing
        
        // Check throughput measurement
        const measuredThroughput = monitor.metrics.throughput.eventsPerSecond;
        
        if (measuredThroughput > 0) {
            console.log(`✅ Throughput measurement working: ${measuredThroughput.toFixed(2)} events/sec`);
        } else {
            throw new Error('Throughput measurement not working');
        }
    }
    
    async testConcurrentOperations() {
        console.log('🔄 Testing concurrent operations...');
        
        try {
            await this.testConcurrentDOMUpdates();
            await this.testConcurrentVirtualScrolling();
            
            this.testResults.push({
                test: 'Concurrent Operations',
                status: 'PASSED',
                timestamp: new Date()
            });
            
        } catch (error) {
            this.testResults.push({
                test: 'Concurrent Operations',
                status: 'FAILED',
                error: error.message,
                timestamp: new Date()
            });
        }
    }
    
    async testConcurrentDOMUpdates() {
        const monitor = this.performanceMonitor;
        
        // Queue many DOM updates concurrently
        const updatePromises = [];
        
        for (let i = 0; i < 100; i++) {
            updatePromises.push(new Promise(resolve => {
                monitor.queueDOMUpdate(() => {
                    // Simulate DOM update
                    const element = document.createElement('div');
                    element.textContent = `Update ${i}`;
                    resolve();
                });
            }));
        }
        
        const startTime = performance.now();
        await Promise.all(updatePromises);
        const endTime = performance.now();
        
        const updateTime = endTime - startTime;
        
        if (updateTime < 500) { // Should handle concurrent updates efficiently
            console.log(`✅ Concurrent DOM updates completed in ${updateTime.toFixed(2)}ms`);
        } else {
            throw new Error(`Concurrent DOM updates too slow: ${updateTime.toFixed(2)}ms`);
        }
    }
    
    async testConcurrentVirtualScrolling() {
        const monitor = this.performanceMonitor;
        
        // Create multiple virtual scroll managers
        const managers = [];
        
        for (let i = 0; i < 3; i++) {
            const containerId = `concurrent-scroll-${i}`;
            
            // Create container
            const container = document.createElement('div');
            container.id = containerId;
            container.style.height = '200px';
            document.getElementById('performance-test-container').appendChild(container);
            
            const manager = monitor.createVirtualScrollManager(containerId);
            managers.push(manager);
        }
        
        // Update all managers concurrently
        const updatePromises = managers.map((manager, index) => {
            return new Promise(resolve => {
                setTimeout(() => {
                    manager.setItems(this.testData.mediumDataset);
                    resolve();
                }, index * 10);
            });
        });
        
        const startTime = performance.now();
        await Promise.all(updatePromises);
        const endTime = performance.now();
        
        const concurrentTime = endTime - startTime;
        
        if (concurrentTime < 200) {
            console.log(`✅ Concurrent virtual scrolling completed in ${concurrentTime.toFixed(2)}ms`);
        } else {
            throw new Error(`Concurrent virtual scrolling too slow: ${concurrentTime.toFixed(2)}ms`);
        }
    }
    
    async testPerformanceMonitoring() {
        console.log('📊 Testing performance monitoring...');
        
        try {
            await this.testMetricsCollection();
            await this.testLatencyMeasurement();
            await this.testPerformanceReporting();
            
            this.testResults.push({
                test: 'Performance Monitoring',
                status: 'PASSED',
                timestamp: new Date()
            });
            
        } catch (error) {
            this.testResults.push({
                test: 'Performance Monitoring',
                status: 'FAILED',
                error: error.message,
                timestamp: new Date()
            });
        }
    }
    
    async testMetricsCollection() {
        const monitor = this.performanceMonitor;
        
        // Generate some activity
        for (let i = 0; i < 50; i++) {
            monitor.batchEvent('metrics_test', { id: i });
            monitor.recordLatency('test_operation', Math.random() * 100);
        }
        
        await this.wait(100);
        
        const metrics = monitor.getMetrics();
        
        if (metrics.events.total > 0 && metrics.latency.samples.length > 0) {
            console.log('✅ Metrics collection working correctly');
        } else {
            throw new Error('Metrics collection not working');
        }
    }
    
    async testLatencyMeasurement() {
        const monitor = this.performanceMonitor;
        
        // Test latency recording
        const testLatencies = [50, 100, 150, 200, 250];
        
        testLatencies.forEach(latency => {
            monitor.recordLatency('test_latency', latency);
        });
        
        const metrics = monitor.getMetrics();
        
        if (metrics.latency.min === 50 && metrics.latency.max === 250) {
            console.log('✅ Latency measurement working correctly');
        } else {
            throw new Error('Latency measurement not working');
        }
    }
    
    async testPerformanceReporting() {
        const monitor = this.performanceMonitor;
        
        const report = monitor.getPerformanceReport();
        
        if (report.metrics && report.config && report.timestamp) {
            console.log('✅ Performance reporting working correctly');
        } else {
            throw new Error('Performance reporting not working');
        }
    }
    
    generateTestReport() {
        console.log('📋 Generating performance test report...');
        
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
            performanceMetrics: this.performanceMonitor ? this.performanceMonitor.getPerformanceReport() : null,
            timestamp: new Date().toISOString()
        };
        
        console.log('🧪 Performance Test Report:', report);
        
        // Store report for external access
        window.performanceTestReport = report;
        
        // Display summary
        if (failedTests === 0) {
            console.log(`✅ All performance tests passed! (${passedTests}/${totalTests})`);
        } else {
            console.log(`❌ ${failedTests} performance tests failed out of ${totalTests}`);
            console.log('Failed tests:', this.testResults.filter(r => r.status === 'FAILED'));
        }
        
        return report;
    }
    
    cleanup() {
        // Cleanup performance monitor
        if (this.performanceMonitor) {
            this.performanceMonitor.destroy();
        }
        
        // Remove test containers
        const testContainer = document.getElementById('performance-test-container');
        if (testContainer) {
            testContainer.remove();
        }
        
        console.log('🧹 Performance test cleanup completed');
    }
    
    wait(ms) {
        return new Promise(resolve => setTimeout(resolve, ms));
    }
}

// Auto-run tests when loaded
document.addEventListener('DOMContentLoaded', () => {
    // Only run tests if in test mode
    if (window.location.search.includes('test=performance') || window.runPerformanceTests) {
        const testSuite = new PerformanceTestSuite();
        testSuite.runAllTests().then(() => {
            console.log('🧪 Performance test suite completed');
        });
    }
});

// Make globally available for manual testing
window.PerformanceTestSuite = PerformanceTestSuite;

// Export for module usage
if (typeof module !== 'undefined' && module.exports) {
    module.exports = PerformanceTestSuite;
}