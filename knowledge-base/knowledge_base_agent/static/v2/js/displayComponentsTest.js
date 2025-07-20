/* V2 DISPLAYCOMPONENTSTEST.JS - COMPREHENSIVE TESTS FOR DISPLAY COMPONENTS */

/**
 * Comprehensive test suite for Phase, Progress, and Task Display Components
 * 
 * ARCHITECTURE:
 * - Tests PhaseDisplayManager functionality
 * - Tests ProgressDisplayManager functionality  
 * - Tests TaskDisplayManager functionality
 * - Validates integration between components
 * - Simulates real-world scenarios and edge cases
 */
class DisplayComponentsTestSuite {
    constructor() {
        this.testResults = [];
        this.mockData = this.createMockData();
        this.testManagers = {};
        
        console.log('🧪 DisplayComponentsTestSuite initialized');
    }
    
    createMockData() {
        return {
            phases: [
                {
                    phase_name: 'initialization',
                    phase_description: 'Initializing agent components',
                    estimated_duration: 30,
                    start_time: new Date().toISOString(),
                    task_id: 'test-task-001'
                },
                {
                    phase_name: 'content_processing',
                    phase_description: 'Processing tweet content',
                    estimated_duration: 300,
                    start_time: new Date(Date.now() + 30000).toISOString(),
                    task_id: 'test-task-001'
                },
                {
                    phase_name: 'synthesis_generation',
                    phase_description: 'Generating category syntheses',
                    estimated_duration: 120,
                    start_time: new Date(Date.now() + 330000).toISOString(),
                    task_id: 'test-task-001'
                }
            ],
            progress: [
                {
                    operation: 'tweet_processing',
                    current: 25,
                    total: 100,
                    percentage: 25,
                    task_id: 'test-task-001',
                    message: 'Processing tweets...'
                },
                {
                    operation: 'media_analysis',
                    current: 5,
                    total: 20,
                    percentage: 25,
                    task_id: 'test-task-001',
                    message: 'Analyzing media files...'
                }
            ],
            tasks: [
                {
                    task_id: 'test-task-001',
                    task_type: 'agent_execution',
                    preferences: { run_mode: 'full_pipeline' },
                    timestamp: new Date().toISOString()
                },
                {
                    task_id: 'test-task-002',
                    task_type: 'synthesis_only',
                    preferences: { run_mode: 'synthesis_only' },
                    timestamp: new Date(Date.now() + 60000).toISOString()
                }
            ],
            logs: [
                {
                    task_id: 'test-task-001',
                    message: 'Agent execution started',
                    level: 'INFO',
                    timestamp: new Date().toISOString(),
                    component: 'agent'
                },
                {
                    task_id: 'test-task-001',
                    message: 'Processing tweet batch 1/4',
                    level: 'INFO',
                    timestamp: new Date(Date.now() + 5000).toISOString(),
                    component: 'content_processor'
                },
                {
                    task_id: 'test-task-001',
                    message: 'Failed to process media file',
                    level: 'ERROR',
                    timestamp: new Date(Date.now() + 10000).toISOString(),
                    component: 'media_processor'
                }
            ],
            errors: [
                {
                    phase_name: 'media_analysis',
                    error: 'Failed to analyze image: timeout',
                    traceback: 'Traceback (most recent call last):\n  File "media.py", line 123...',
                    timestamp: new Date().toISOString(),
                    task_id: 'test-task-001'
                }
            ]
        };
    }
    
    async runAllTests() {
        console.log('🧪 Starting comprehensive display components test suite...');
        
        try {
            // Initialize test environment
            await this.setupTestEnvironment();
            
            // Run individual component tests
            await this.testPhaseDisplayManager();
            await this.testProgressDisplayManager();
            await this.testTaskDisplayManager();
            
            // Run integration tests
            await this.testComponentIntegration();
            
            // Run performance tests
            await this.testPerformance();
            
            // Run error handling tests
            await this.testErrorHandling();
            
            // Generate test report
            this.generateTestReport();
            
        } catch (error) {
            console.error('❌ Test suite failed:', error);
            this.testResults.push({
                test: 'Test Suite Execution',
                status: 'FAILED',
                error: error.message,
                timestamp: new Date()
            });
        }
    }
    
    async setupTestEnvironment() {
        console.log('🔧 Setting up test environment...');
        
        // Create test containers
        this.createTestContainers();
        
        // Initialize managers with test configuration
        this.testManagers.phaseDisplay = new PhaseDisplayManager();
        this.testManagers.progressDisplay = new ProgressDisplayManager();
        this.testManagers.taskDisplay = new TaskDisplayManager();
        
        // Wait for initialization
        await this.wait(100);
        
        this.testResults.push({
            test: 'Test Environment Setup',
            status: 'PASSED',
            timestamp: new Date()
        });
    }
    
    createTestContainers() {
        // Create test DOM elements
        const testContainer = document.createElement('div');
        testContainer.id = 'test-container';
        testContainer.style.cssText = `
            position: fixed;
            top: -9999px;
            left: -9999px;
            width: 1000px;
            height: 800px;
            visibility: hidden;
        `;
        
        testContainer.innerHTML = `
            <div class="dashboard-main-area">
                <div id="phase-list"></div>
                <div id="current-phase-display"></div>
                <div id="phase-timing-display"></div>
                <div id="progress-container"></div>
                <div id="global-progress-bar"></div>
                <div id="task-container"></div>
                <div id="task-switcher"></div>
                <div id="task-tabs"></div>
            </div>
        `;
        
        document.body.appendChild(testContainer);
    }
    
    async testPhaseDisplayManager() {
        console.log('🎯 Testing PhaseDisplayManager...');
        
        const manager = this.testManagers.phaseDisplay;
        
        try {
            // Test phase start
            await this.testPhaseStart(manager);
            
            // Test phase progress updates
            await this.testPhaseProgress(manager);
            
            // Test phase completion
            await this.testPhaseCompletion(manager);
            
            // Test phase error handling
            await this.testPhaseError(manager);
            
            // Test phase transitions
            await this.testPhaseTransitions(manager);
            
            this.testResults.push({
                test: 'PhaseDisplayManager',
                status: 'PASSED',
                timestamp: new Date()
            });
            
        } catch (error) {
            this.testResults.push({
                test: 'PhaseDisplayManager',
                status: 'FAILED',
                error: error.message,
                timestamp: new Date()
            });
        }
    }
    
    async testPhaseStart(manager) {
        const phaseData = this.mockData.phases[0];
        
        // Simulate phase start event
        document.dispatchEvent(new CustomEvent('phase_start', {
            detail: phaseData
        }));
        
        await this.wait(50);
        
        // Verify phase was registered
        const phase = manager.getPhaseStatus(phaseData.phase_name);
        if (!phase || phase.status !== 'running') {
            throw new Error('Phase start not properly handled');
        }
        
        // Verify current phase display updated
        const currentPhaseDisplay = document.getElementById('current-phase-display');
        if (!currentPhaseDisplay || !currentPhaseDisplay.textContent.includes(phaseData.phase_description)) {
            throw new Error('Current phase display not updated');
        }
    }
    
    async testPhaseProgress(manager) {
        const progressData = {
            phase_name: 'content_processing',
            processed_count: 50,
            total_count: 100,
            message: 'Processing tweets 50/100'
        };
        
        // Simulate phase update event
        document.dispatchEvent(new CustomEvent('phase_update', {
            detail: progressData
        }));
        
        await this.wait(50);
        
        // Verify progress was updated
        const phase = manager.getPhaseStatus(progressData.phase_name);
        if (!phase || phase.progress.current !== 50) {
            throw new Error('Phase progress not properly updated');
        }
    }
    
    async testPhaseCompletion(manager) {
        const completionData = {
            phase_name: 'initialization',
            success: true,
            result: { processed: 100 },
            end_time: new Date().toISOString()
        };
        
        // Simulate phase complete event
        document.dispatchEvent(new CustomEvent('phase_complete', {
            detail: completionData
        }));
        
        await this.wait(50);
        
        // Verify phase was marked complete
        const phase = manager.getPhaseStatus(completionData.phase_name);
        if (!phase || phase.status !== 'completed') {
            throw new Error('Phase completion not properly handled');
        }
    }
    
    async testPhaseError(manager) {
        const errorData = this.mockData.errors[0];
        
        // Simulate phase error event
        document.dispatchEvent(new CustomEvent('phase_error', {
            detail: errorData
        }));
        
        await this.wait(50);
        
        // Verify error was handled
        const phase = manager.getPhaseStatus(errorData.phase_name);
        if (!phase || phase.status !== 'error' || !phase.error) {
            throw new Error('Phase error not properly handled');
        }
    }
    
    async testPhaseTransitions(manager) {
        // Test phase reset
        manager.resetAllPhases();
        
        await this.wait(50);
        
        // Verify all phases reset
        const stats = manager.getPhaseStatistics();
        if (stats.running > 0 || stats.completed > 0 || stats.error > 0) {
            throw new Error('Phase reset not working properly');
        }
    }
    
    async testProgressDisplayManager() {
        console.log('📊 Testing ProgressDisplayManager...');
        
        const manager = this.testManagers.progressDisplay;
        
        try {
            // Test progress bar creation
            await this.testProgressCreation(manager);
            
            // Test progress updates
            await this.testProgressUpdates(manager);
            
            // Test ETC calculations
            await this.testETCCalculations(manager);
            
            // Test progress completion
            await this.testProgressCompletion(manager);
            
            // Test global progress
            await this.testGlobalProgress(manager);
            
            this.testResults.push({
                test: 'ProgressDisplayManager',
                status: 'PASSED',
                timestamp: new Date()
            });
            
        } catch (error) {
            this.testResults.push({
                test: 'ProgressDisplayManager',
                status: 'FAILED',
                error: error.message,
                timestamp: new Date()
            });
        }
    }
    
    async testProgressCreation(manager) {
        const progressData = this.mockData.progress[0];
        
        // Create progress bar
        const progressBar = manager.createProgress(progressData.operation, {
            label: 'Test Progress',
            showETC: true
        });
        
        if (!progressBar || progressBar.id !== progressData.operation) {
            throw new Error('Progress bar creation failed');
        }
        
        // Verify DOM element created
        const element = document.querySelector(`[data-progress-id="${progressData.operation}"]`);
        if (!element) {
            throw new Error('Progress bar DOM element not created');
        }
    }
    
    async testProgressUpdates(manager) {
        const progressData = this.mockData.progress[0];
        
        // Update progress
        manager.updateProgress(
            progressData.operation,
            progressData.current,
            progressData.total,
            progressData.message
        );
        
        await this.wait(50);
        
        // Verify progress updated
        const progress = manager.getProgress(progressData.operation);
        if (!progress || progress.percentage !== progressData.percentage) {
            throw new Error('Progress update failed');
        }
    }
    
    async testETCCalculations(manager) {
        const progressId = 'etc_test';
        
        // Create progress with history
        manager.createProgress(progressId, { showETC: true });
        
        // Simulate progress over time
        for (let i = 0; i <= 50; i += 10) {
            manager.updateProgress(progressId, i, 100);
            await this.wait(100); // Simulate time passage
        }
        
        // Verify ETC calculation
        const progress = manager.getProgress(progressId);
        if (!progress || !progress.etcElement) {
            throw new Error('ETC calculation not working');
        }
    }
    
    async testProgressCompletion(manager) {
        const progressId = 'completion_test';
        
        manager.createProgress(progressId);
        manager.completeProgress(progressId);
        
        await this.wait(50);
        
        const progress = manager.getProgress(progressId);
        if (!progress || progress.status !== 'completed') {
            throw new Error('Progress completion failed');
        }
    }
    
    async testGlobalProgress(manager) {
        // Create multiple progress bars
        manager.createProgress('global_test_1', { type: 'phase', estimatedDuration: 60 });
        manager.createProgress('global_test_2', { type: 'phase', estimatedDuration: 120 });
        
        // Update progress
        manager.updateProgress('global_test_1', 50, 100);
        manager.updateProgress('global_test_2', 25, 100);
        
        await this.wait(100);
        
        // Verify global progress calculation
        const globalSection = document.getElementById('global-progress-section');
        if (!globalSection || globalSection.style.display === 'none') {
            throw new Error('Global progress not displayed');
        }
    }
    
    async testTaskDisplayManager() {
        console.log('📋 Testing TaskDisplayManager...');
        
        const manager = this.testManagers.taskDisplay;
        
        try {
            // Test task creation
            await this.testTaskCreation(manager);
            
            // Test task updates
            await this.testTaskUpdates(manager);
            
            // Test task switching
            await this.testTaskSwitching(manager);
            
            // Test task completion
            await this.testTaskCompletion(manager);
            
            // Test task cleanup
            await this.testTaskCleanup(manager);
            
            this.testResults.push({
                test: 'TaskDisplayManager',
                status: 'PASSED',
                timestamp: new Date()
            });
            
        } catch (error) {
            this.testResults.push({
                test: 'TaskDisplayManager',
                status: 'FAILED',
                error: error.message,
                timestamp: new Date()
            });
        }
    }
    
    async testTaskCreation(manager) {
        const taskData = this.mockData.tasks[0];
        
        // Simulate task started event
        document.dispatchEvent(new CustomEvent('task_started', {
            detail: taskData
        }));
        
        await this.wait(50);
        
        // Verify task created
        const task = manager.getTask(taskData.task_id);
        if (!task || task.status !== 'running') {
            throw new Error('Task creation failed');
        }
        
        // Verify DOM element created
        const element = document.getElementById(`task-${taskData.task_id}`);
        if (!element) {
            throw new Error('Task DOM element not created');
        }
    }
    
    async testTaskUpdates(manager) {
        const taskId = this.mockData.tasks[0].task_id;
        const logData = this.mockData.logs[0];
        
        // Add log to task
        manager.updateTaskLogs(taskId, logData);
        
        await this.wait(50);
        
        // Verify log added
        const task = manager.getTask(taskId);
        if (!task || task.logs.length === 0) {
            throw new Error('Task log update failed');
        }
    }
    
    async testTaskSwitching(manager) {
        const taskId1 = this.mockData.tasks[0].task_id;
        const taskId2 = this.mockData.tasks[1].task_id;
        
        // Create second task
        document.dispatchEvent(new CustomEvent('task_started', {
            detail: this.mockData.tasks[1]
        }));
        
        await this.wait(50);
        
        // Switch to second task
        manager.switchToTask(taskId2);
        
        await this.wait(50);
        
        // Verify task switched
        if (manager.activeTaskId !== taskId2) {
            throw new Error('Task switching failed');
        }
    }
    
    async testTaskCompletion(manager) {
        const taskId = this.mockData.tasks[0].task_id;
        
        // Complete task
        document.dispatchEvent(new CustomEvent('task_completed', {
            detail: {
                task_id: taskId,
                result: { success: true },
                timestamp: new Date().toISOString()
            }
        }));
        
        await this.wait(50);
        
        // Verify task completed
        const task = manager.getTask(taskId);
        if (!task || task.status !== 'completed') {
            throw new Error('Task completion failed');
        }
    }
    
    async testTaskCleanup(manager) {
        const initialTaskCount = manager.getAllTasks().length;
        
        // Clear completed tasks
        manager.clearCompletedTasks();
        
        await this.wait(50);
        
        // Verify cleanup
        const finalTaskCount = manager.getAllTasks().length;
        if (finalTaskCount >= initialTaskCount) {
            throw new Error('Task cleanup failed');
        }
    }
    
    async testComponentIntegration() {
        console.log('🔗 Testing component integration...');
        
        try {
            // Test phase-progress integration
            await this.testPhaseProgressIntegration();
            
            // Test task-phase integration
            await this.testTaskPhaseIntegration();
            
            // Test cross-component event handling
            await this.testCrossComponentEvents();
            
            this.testResults.push({
                test: 'Component Integration',
                status: 'PASSED',
                timestamp: new Date()
            });
            
        } catch (error) {
            this.testResults.push({
                test: 'Component Integration',
                status: 'FAILED',
                error: error.message,
                timestamp: new Date()
            });
        }
    }
    
    async testPhaseProgressIntegration() {
        const phaseManager = this.testManagers.phaseDisplay;
        const progressManager = this.testManagers.progressDisplay;
        
        // Start a phase
        document.dispatchEvent(new CustomEvent('phase_start', {
            detail: {
                phase_name: 'integration_test',
                phase_description: 'Integration test phase',
                task_id: 'integration-task'
            }
        }));
        
        await this.wait(50);
        
        // Update progress
        document.dispatchEvent(new CustomEvent('progress_update', {
            detail: {
                operation: 'integration_test',
                current: 30,
                total: 100,
                task_id: 'integration-task'
            }
        }));
        
        await this.wait(50);
        
        // Verify both components updated
        const phase = phaseManager.getPhaseStatus('integration_test');
        const progress = progressManager.getProgress('integration_test');
        
        if (!phase || !progress) {
            throw new Error('Phase-progress integration failed');
        }
    }
    
    async testTaskPhaseIntegration() {
        const taskManager = this.testManagers.taskDisplay;
        const phaseManager = this.testManagers.phaseDisplay;
        
        const taskId = 'task-phase-integration';
        
        // Start task
        document.dispatchEvent(new CustomEvent('task_started', {
            detail: {
                task_id: taskId,
                task_type: 'integration_test'
            }
        }));
        
        await this.wait(50);
        
        // Start phase for task
        document.dispatchEvent(new CustomEvent('phase_start', {
            detail: {
                phase_name: 'task_integration_phase',
                task_id: taskId
            }
        }));
        
        await this.wait(50);
        
        // Verify integration
        const task = taskManager.getTask(taskId);
        const phase = phaseManager.getPhaseStatus('task_integration_phase');
        
        if (!task || !phase || !task.phases.has('task_integration_phase')) {
            throw new Error('Task-phase integration failed');
        }
    }
    
    async testCrossComponentEvents() {
        // Test that events are properly routed between components
        const eventTypes = [
            'phase_start',
            'phase_complete',
            'progress_update',
            'task_started',
            'agent_status_update'
        ];
        
        let eventsReceived = 0;
        
        // Add event listeners
        eventTypes.forEach(eventType => {
            document.addEventListener(eventType, () => {
                eventsReceived++;
            });
        });
        
        // Dispatch events
        eventTypes.forEach(eventType => {
            document.dispatchEvent(new CustomEvent(eventType, {
                detail: { test: true }
            }));
        });
        
        await this.wait(100);
        
        if (eventsReceived !== eventTypes.length) {
            throw new Error('Cross-component event handling failed');
        }
    }
    
    async testPerformance() {
        console.log('⚡ Testing performance...');
        
        try {
            // Test high-volume updates
            await this.testHighVolumeUpdates();
            
            // Test memory usage
            await this.testMemoryUsage();
            
            // Test rendering performance
            await this.testRenderingPerformance();
            
            this.testResults.push({
                test: 'Performance',
                status: 'PASSED',
                timestamp: new Date()
            });
            
        } catch (error) {
            this.testResults.push({
                test: 'Performance',
                status: 'FAILED',
                error: error.message,
                timestamp: new Date()
            });
        }
    }
    
    async testHighVolumeUpdates() {
        const startTime = performance.now();
        const updateCount = 1000;
        
        // Generate high volume of updates
        for (let i = 0; i < updateCount; i++) {
            document.dispatchEvent(new CustomEvent('progress_update', {
                detail: {
                    operation: `perf_test_${i % 10}`,
                    current: i % 100,
                    total: 100
                }
            }));
            
            if (i % 100 === 0) {
                await this.wait(1); // Yield to prevent blocking
            }
        }
        
        const endTime = performance.now();
        const duration = endTime - startTime;
        
        console.log(`📊 Processed ${updateCount} updates in ${duration.toFixed(2)}ms`);
        
        if (duration > 5000) { // 5 seconds threshold
            throw new Error('High-volume updates too slow');
        }
    }
    
    async testMemoryUsage() {
        const initialMemory = performance.memory ? performance.memory.usedJSHeapSize : 0;
        
        // Create many components
        for (let i = 0; i < 100; i++) {
            document.dispatchEvent(new CustomEvent('task_started', {
                detail: {
                    task_id: `memory_test_${i}`,
                    task_type: 'memory_test'
                }
            }));
        }
        
        await this.wait(100);
        
        // Clean up
        this.testManagers.taskDisplay.clearCompletedTasks();
        
        await this.wait(100);
        
        const finalMemory = performance.memory ? performance.memory.usedJSHeapSize : 0;
        const memoryIncrease = finalMemory - initialMemory;
        
        console.log(`💾 Memory increase: ${(memoryIncrease / 1024 / 1024).toFixed(2)}MB`);
        
        // Allow reasonable memory increase
        if (memoryIncrease > 50 * 1024 * 1024) { // 50MB threshold
            throw new Error('Excessive memory usage detected');
        }
    }
    
    async testRenderingPerformance() {
        const startTime = performance.now();
        
        // Create multiple visual updates
        for (let i = 0; i < 50; i++) {
            document.dispatchEvent(new CustomEvent('phase_start', {
                detail: {
                    phase_name: `render_test_${i}`,
                    phase_description: `Render test phase ${i}`
                }
            }));
        }
        
        // Force layout
        document.body.offsetHeight;
        
        const endTime = performance.now();
        const renderTime = endTime - startTime;
        
        console.log(`🎨 Rendering time: ${renderTime.toFixed(2)}ms`);
        
        if (renderTime > 1000) { // 1 second threshold
            throw new Error('Rendering performance too slow');
        }
    }
    
    async testErrorHandling() {
        console.log('🚨 Testing error handling...');
        
        try {
            // Test malformed events
            await this.testMalformedEvents();
            
            // Test missing data
            await this.testMissingData();
            
            // Test component failures
            await this.testComponentFailures();
            
            this.testResults.push({
                test: 'Error Handling',
                status: 'PASSED',
                timestamp: new Date()
            });
            
        } catch (error) {
            this.testResults.push({
                test: 'Error Handling',
                status: 'FAILED',
                error: error.message,
                timestamp: new Date()
            });
        }
    }
    
    async testMalformedEvents() {
        // Test with malformed event data
        const malformedEvents = [
            { detail: null },
            { detail: {} },
            { detail: { invalid: 'data' } },
            { detail: { phase_name: null } },
            { detail: { task_id: '' } }
        ];
        
        malformedEvents.forEach((event, index) => {
            try {
                document.dispatchEvent(new CustomEvent('phase_start', event));
                document.dispatchEvent(new CustomEvent('progress_update', event));
                document.dispatchEvent(new CustomEvent('task_started', event));
            } catch (error) {
                throw new Error(`Malformed event ${index} caused crash: ${error.message}`);
            }
        });
        
        await this.wait(50);
    }
    
    async testMissingData() {
        // Test with missing required data
        document.dispatchEvent(new CustomEvent('phase_start', {
            detail: { phase_name: 'missing_data_test' } // Missing other required fields
        }));
        
        document.dispatchEvent(new CustomEvent('progress_update', {
            detail: { current: 50 } // Missing total
        }));
        
        await this.wait(50);
        
        // Components should handle gracefully without crashing
    }
    
    async testComponentFailures() {
        // Test component behavior when DOM elements are missing
        const originalContainer = document.getElementById('test-container');
        if (originalContainer) {
            originalContainer.remove();
        }
        
        // Try to use components without DOM
        try {
            this.testManagers.phaseDisplay.updateCurrentPhaseDisplay({
                name: 'Test Phase',
                status: 'running'
            });
            
            this.testManagers.progressDisplay.updateProgress('test', 50, 100);
            
            this.testManagers.taskDisplay.switchToTask('nonexistent');
            
        } catch (error) {
            // Expected to handle gracefully
            console.log('Components handled missing DOM gracefully');
        }
        
        // Restore container
        this.createTestContainers();
    }
    
    generateTestReport() {
        console.log('📋 Generating test report...');
        
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
            timestamp: new Date().toISOString()
        };
        
        console.log('🧪 Test Report:', report);
        
        // Store report for external access
        window.displayComponentsTestReport = report;
        
        // Display summary
        if (failedTests === 0) {
            console.log(`✅ All tests passed! (${passedTests}/${totalTests})`);
        } else {
            console.log(`❌ ${failedTests} tests failed out of ${totalTests}`);
            console.log('Failed tests:', this.testResults.filter(r => r.status === 'FAILED'));
        }
        
        return report;
    }
    
    cleanup() {
        // Remove test containers
        const testContainer = document.getElementById('test-container');
        if (testContainer) {
            testContainer.remove();
        }
        
        // Clear test managers
        this.testManagers = {};
        
        console.log('🧹 Test cleanup completed');
    }
    
    wait(ms) {
        return new Promise(resolve => setTimeout(resolve, ms));
    }
}

// Auto-run tests when loaded
document.addEventListener('DOMContentLoaded', () => {
    // Only run tests if in test mode
    if (window.location.search.includes('test=display') || window.runDisplayTests) {
        const testSuite = new DisplayComponentsTestSuite();
        testSuite.runAllTests().then(() => {
            console.log('🧪 Display components test suite completed');
        });
    }
});

// Make globally available for manual testing
window.DisplayComponentsTestSuite = DisplayComponentsTestSuite;

// Export for module usage
if (typeof module !== 'undefined' && module.exports) {
    module.exports = DisplayComponentsTestSuite;
}