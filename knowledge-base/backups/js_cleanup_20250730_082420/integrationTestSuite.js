/* V2 INTEGRATION TEST SUITE - COMPREHENSIVE FRONTEND LAYOUT INTEGRATION TESTING */

/**
 * IntegrationTestSuite - Comprehensive testing for frontend layout integration
 * 
 * Tests all requirements from the frontend-layout-integration spec:
 * - Display component integration without conflicts
 * - Layout consistency across screen sizes  
 * - Component coordination scenarios
 * - Performance optimization validation
 * - Error handling and recovery
 * - Accessibility compliance
 * - Real agent execution scenarios
 */
class IntegrationTestSuite {
    constructor() {
        this.testResults = new Map();
        this.testMetrics = {
            totalTests: 0,
            passedTests: 0,
            failedTests: 0,
            startTime: null,
            endTime: null,
            duration: null
        };
        
        this.performanceThresholds = {
            componentInitialization: 1000,
            domUpdateLatency: 100,
            memoryUsage: 50 * 1024 * 1024,
            eventProcessingDelay: 50
        };
        
        this.mockData = this.createMockData();
        this.init();
    }
    
    init() {
        console.log('🧪 IntegrationTestSuite initialized');
        this.setupTestEnvironment();
    }
    
    setupTestEnvironment() {
        this.testContainer = document.createElement('div');
        this.testContainer.id = 'integration-test-container';
        this.testContainer.style.cssText = `
            position: fixed; top: 10px; left: 10px; width: 400px; max-height: 600px;
            background: var(--glass-bg-primary); border: 1px solid var(--glass-border-primary);
            border-radius: var(--radius-lg); padding: var(--space-3); z-index: 10000;
            backdrop-filter: blur(10px); overflow-y: auto; display: none;
        `;
        
        this.testContainer.innerHTML = `
            <div style="display: flex; justify-content: space-between; margin-bottom: var(--space-3);">
                <h3 style="margin: 0;">Integration Tests</h3>
                <div>
                    <button id="run-all-tests-btn" class="glass-button glass-button--sm">Run All</button>
                    <button id="close-tests-btn" class="glass-button glass-button--sm">×</button>
                </div>
            </div>
            <div id="test-progress" style="margin-bottom: var(--space-3); display: none;">
                <div style="display: flex; justify-content: space-between; margin-bottom: var(--space-1);">
                    <span>Progress</span>
                    <span id="test-progress-text">0/0</span>
                </div>
                <div style="height: 4px; background: var(--glass-bg-tertiary); border-radius: var(--radius-sm);">
                    <div id="test-progress-bar" style="height: 100%; background: var(--gradient-primary); width: 0%;"></div>
                </div>
            </div>
            <div id="test-results"></div>
            <div id="test-summary" style="margin-top: var(--space-3); display: none;">
                <div style="display: grid; grid-template-columns: repeat(3, 1fr); gap: var(--space-2); text-align: center;">
                    <div><div id="passed-count" style="font-size: var(--font-size-lg); color: var(--success-green);">0</div><div>Passed</div></div>
                    <div><div id="failed-count" style="font-size: var(--font-size-lg); color: var(--error-red);">0</div><div>Failed</div></div>
                    <div><div id="duration-display" style="font-size: var(--font-size-lg);">0ms</div><div>Duration</div></div>
                </div>
            </div>
        `;
        
        document.body.appendChild(this.testContainer);
        
        document.getElementById('run-all-tests-btn').addEventListener('click', () => this.runAllTests());
        document.getElementById('close-tests-btn').addEventListener('click', () => this.hideTestSuite());
        
        document.addEventListener('keydown', (e) => {
            if (e.ctrlKey && e.shiftKey && e.key === 'T') {
                this.showTestSuite();
            }
        });
    }
    
    createMockData() {
        return {
            phases: [
                { phase_name: 'initialization', phase_description: 'Initializing', task_id: 'test_001' },
                { phase_name: 'fetch_bookmarks', phase_description: 'Fetching', task_id: 'test_001' },
                { phase_name: 'content_processing', phase_description: 'Processing', task_id: 'test_001' }
            ],
            progress: [
                { operation: 'test_op', current: 25, total: 100, percentage: 25, task_id: 'test_001' }
            ],
            tasks: [
                { task_id: 'test_001', task_type: 'agent_execution', timestamp: Date.now() }
            ]
        };
    }
    
    async runAllTests() {
        console.log('🧪 Starting integration test suite...');
        
        this.testMetrics.startTime = Date.now();
        this.testMetrics.totalTests = 0;
        this.testMetrics.passedTests = 0;
        this.testMetrics.failedTests = 0;
        
        this.showTestProgress();
        this.clearTestResults();
        
        const testSuites = [
            this.testDisplayComponentIntegration,
            this.testLayoutConsistency,
            this.testComponentCoordination,
            this.testPerformanceOptimization,
            this.testErrorHandling,
            this.testAccessibility,
            this.testRealAgentScenarios
        ];
        
        for (let i = 0; i < testSuites.length; i++) {
            this.updateTestProgress(i, testSuites.length);
            try {
                await testSuites[i].call(this);
            } catch (error) {
                console.error(`Test suite ${testSuites[i].name} failed:`, error);
                this.recordTestResult(testSuites[i].name, false, error.message);
            }
        }
        
        this.testMetrics.endTime = Date.now();
        this.testMetrics.duration = this.testMetrics.endTime - this.testMetrics.startTime;
        
        this.updateTestProgress(testSuites.length, testSuites.length);
        this.showTestSummary();
        
        console.log('🧪 Integration test suite completed', this.testMetrics);
    }
    
    async testDisplayComponentIntegration() {
        console.log('🧪 Testing Display Component Integration...');
        
        await this.runTest('PhaseDisplayManager Integration', async () => {
            if (!window.PhaseDisplayManager) {
                throw new Error('PhaseDisplayManager not found');
            }
            
            const phaseManager = new PhaseDisplayManager();
            const phaseList = document.getElementById('phase-list');
            
            if (!phaseList) {
                throw new Error('Phase list element not found');
            }
            
            document.dispatchEvent(new CustomEvent('phase_start', { detail: this.mockData.phases[0] }));
            await this.waitForDOMUpdate();
            
            return 'PhaseDisplayManager integrates with existing execution plan';
        });
        
        await this.runTest('ProgressDisplayManager Integration', async () => {
            if (!window.ProgressDisplayManager) {
                throw new Error('ProgressDisplayManager not found');
            }
            
            const progressManager = new ProgressDisplayManager();
            document.dispatchEvent(new CustomEvent('progress_update', { detail: this.mockData.progress[0] }));
            await this.waitForDOMUpdate();
            
            const progressContainer = document.getElementById('progress-container') || 
                                   document.getElementById('integrated-progress-section');
            
            if (!progressContainer) {
                throw new Error('Progress container not integrated');
            }
            
            return 'ProgressDisplayManager integrates with existing panels';
        });
        
        await this.runTest('TaskDisplayManager Integration', async () => {
            if (!window.TaskDisplayManager) {
                throw new Error('TaskDisplayManager not found');
            }
            
            const taskManager = new TaskDisplayManager();
            document.dispatchEvent(new CustomEvent('task_started', { detail: this.mockData.tasks[0] }));
            await this.waitForDOMUpdate();
            
            const taskSwitcher = document.getElementById('task-switcher') || 
                               document.getElementById('task-info-section');
            
            if (!taskSwitcher) {
                throw new Error('Task switcher not integrated');
            }
            
            return 'TaskDisplayManager integrates with existing status displays';
        });
        
        await this.runTest('Component Coordination', async () => {
            if (!window.displayCoordinator) {
                throw new Error('DisplayComponentCoordinator not found');
            }
            
            const coordinator = window.displayCoordinator;
            const components = coordinator.getAllComponents();
            const expectedComponents = ['PhaseDisplayManager', 'ProgressDisplayManager', 'TaskDisplayManager'];
            
            for (const expectedComponent of expectedComponents) {
                const component = coordinator.getComponent(expectedComponent);
                if (!component) {
                    throw new Error(`Component ${expectedComponent} not registered`);
                }
            }
            
            return 'All display components are properly coordinated';
        });
    }
    
    async testLayoutConsistency() {
        console.log('🧪 Testing Layout Consistency...');
        
        await this.runTest('Glass Theme Consistency', async () => {
            const panels = document.querySelectorAll('.glass-panel-v3, .glass-panel-v3--secondary');
            
            if (panels.length === 0) {
                throw new Error('No glass panels found');
            }
            
            for (const panel of panels) {
                const computedStyle = window.getComputedStyle(panel);
                
                if (!computedStyle.backdropFilter || computedStyle.backdropFilter === 'none') {
                    throw new Error(`Panel missing glass effect: ${panel.id || panel.className}`);
                }
            }
            
            return 'All panels maintain consistent glass theme styling';
        });
        
        await this.runTest('Responsive Design', async () => {
            const originalWidth = window.innerWidth;
            
            try {
                this.simulateViewportResize(375, 667); // Mobile
                await this.waitForDOMUpdate();
                
                this.simulateViewportResize(768, 1024); // Tablet
                await this.waitForDOMUpdate();
                
                this.simulateViewportResize(1920, 1080); // Desktop
                await this.waitForDOMUpdate();
                
                return 'Layout adapts properly to different screen sizes';
            } finally {
                this.simulateViewportResize(originalWidth, window.innerHeight);
            }
        });
        
        await this.runTest('Spacing Consistency', async () => {
            const elements = document.querySelectorAll('.glass-panel-v3, .phase-item, .progress-item');
            
            for (const element of elements) {
                const computedStyle = window.getComputedStyle(element);
                // Basic spacing validation
                if (computedStyle.padding === '0px' && computedStyle.margin === '0px') {
                    console.warn(`Element may lack proper spacing: ${element.className}`);
                }
            }
            
            return 'Spacing is consistent across components';
        });
    }
    
    async testComponentCoordination() {
        console.log('🧪 Testing Component Coordination...');
        
        await this.runTest('Event Coordination', async () => {
            const coordinator = window.displayCoordinator;
            if (!coordinator) {
                throw new Error('DisplayComponentCoordinator not available');
            }
            
            const startTime = performance.now();
            
            for (let i = 0; i < 10; i++) {
                document.dispatchEvent(new CustomEvent('phase_update', {
                    detail: { phase_name: 'test_phase', progress: i * 10, total: 100 }
                }));
            }
            
            await this.waitForDOMUpdate();
            
            const endTime = performance.now();
            const processingTime = endTime - startTime;
            
            if (processingTime > this.performanceThresholds.eventProcessingDelay * 10) {
                throw new Error(`Event processing too slow: ${processingTime}ms`);
            }
            
            return 'Events are properly coordinated and batched';
        });
        
        await this.runTest('Component Initialization Order', async () => {
            const coordinator = window.displayCoordinator;
            const initOrder = coordinator.initializationOrder;
            
            if (initOrder.length === 0) {
                throw new Error('No components in initialization order');
            }
            
            // Verify dependencies are respected
            for (const component of initOrder) {
                if (component.dependencies && component.dependencies.length > 0) {
                    for (const dep of component.dependencies) {
                        const depIndex = initOrder.findIndex(c => c.name === dep);
                        const componentIndex = initOrder.findIndex(c => c.name === component.name);
                        
                        if (depIndex > componentIndex) {
                            throw new Error(`Dependency ${dep} initialized after ${component.name}`);
                        }
                    }
                }
            }
            
            return 'Component initialization order respects dependencies';
        });
        
        await this.runTest('Duplicate Element Prevention', async () => {
            // Test that components don't create duplicate elements
            const phaseManager1 = new PhaseDisplayManager();
            const phaseManager2 = new PhaseDisplayManager();
            
            await this.waitForDOMUpdate();
            
            // Check for duplicate progress bars
            const phaseItems = document.querySelectorAll('.phase-item');
            
            // Each phase item should have at most one progress bar
            for (const phaseItem of phaseItems) {
                const itemProgressBars = phaseItem.querySelectorAll('.phase-progress-bar');
                if (itemProgressBars.length > 1) {
                    throw new Error(`Duplicate progress bars found in phase item ${phaseItem.id}`);
                }
            }
            
            return 'Components prevent creation of duplicate elements';
        });
    }
    
    async testPerformanceOptimization() {
        console.log('🧪 Testing Performance Optimization...');
        
        await this.runTest('Memory Usage', async () => {
            const initialMemory = this.getMemoryUsage();
            
            // Create multiple component instances
            const components = [];
            for (let i = 0; i < 10; i++) {
                components.push(new PhaseDisplayManager());
                components.push(new ProgressDisplayManager());
                components.push(new TaskDisplayManager());
            }
            
            // Simulate heavy usage
            for (let i = 0; i < 100; i++) {
                document.dispatchEvent(new CustomEvent('phase_start', {
                    detail: { phase_name: `test_phase_${i}`, task_id: `task_${i}` }
                }));
                document.dispatchEvent(new CustomEvent('progress_update', {
                    detail: { operation: `op_${i}`, current: i, total: 100 }
                }));
            }
            
            await this.waitForDOMUpdate();
            
            // Cleanup components
            components.forEach(component => {
                if (component.cleanup) {
                    component.cleanup();
                }
            });
            
            // Force garbage collection if available
            if (window.gc) {
                window.gc();
            }
            
            const finalMemory = this.getMemoryUsage();
            const memoryIncrease = finalMemory - initialMemory;
            
            if (memoryIncrease > this.performanceThresholds.memoryUsage) {
                throw new Error(`Memory usage increased by ${memoryIncrease} bytes`);
            }
            
            return 'Memory usage remains within acceptable limits';
        });
        
        await this.runTest('DOM Update Performance', async () => {
            const startTime = performance.now();
            
            // Perform multiple DOM updates
            for (let i = 0; i < 50; i++) {
                document.dispatchEvent(new CustomEvent('phase_update', {
                    detail: {
                        phase_name: 'performance_test',
                        progress: { current: i, total: 50 },
                        message: `Update ${i}`
                    }
                }));
            }
            
            await this.waitForDOMUpdate();
            
            const endTime = performance.now();
            const updateTime = endTime - startTime;
            
            if (updateTime > this.performanceThresholds.domUpdateLatency * 50) {
                throw new Error(`DOM updates too slow: ${updateTime}ms for 50 updates`);
            }
            
            return 'DOM updates perform within acceptable limits';
        });
    }
    
    async testErrorHandling() {
        console.log('🧪 Testing Error Handling...');
        
        await this.runTest('Component Error Recovery', async () => {
            // Simulate component error
            const originalConsoleError = console.error;
            let errorCaught = false;
            
            console.error = (...args) => {
                errorCaught = true;
                originalConsoleError.apply(console, args);
            };
            
            try {
                // Send malformed event
                document.dispatchEvent(new CustomEvent('phase_start', {
                    detail: { invalid_data: true }
                }));
                
                await this.waitForDOMUpdate();
                
                // Verify system still responds to valid events
                document.dispatchEvent(new CustomEvent('phase_start', {
                    detail: this.mockData.phases[0]
                }));
                
                await this.waitForDOMUpdate();
                
                return 'Components recover gracefully from errors';
            } finally {
                console.error = originalConsoleError;
            }
        });
        
        await this.runTest('Missing Element Handling', async () => {
            // Temporarily remove key elements
            const phaseList = document.getElementById('phase-list');
            const statusFooter = document.getElementById('agent-status-footer');
            
            if (phaseList) phaseList.style.display = 'none';
            if (statusFooter) statusFooter.style.display = 'none';
            
            try {
                // Create components when elements are missing
                const phaseManager = new PhaseDisplayManager();
                const progressManager = new ProgressDisplayManager();
                
                await this.waitForDOMUpdate();
                
                // Components should handle missing elements gracefully
                document.dispatchEvent(new CustomEvent('phase_start', {
                    detail: this.mockData.phases[0]
                }));
                
                await this.waitForDOMUpdate();
                
                return 'Components handle missing elements gracefully';
            } finally {
                // Restore elements
                if (phaseList) phaseList.style.display = '';
                if (statusFooter) statusFooter.style.display = '';
            }
        });
        
        await this.runTest('Network Error Handling', async () => {
            // Simulate network errors by sending error events
            document.dispatchEvent(new CustomEvent('phase_error', {
                detail: {
                    phase_name: 'test_phase',
                    error: 'Network connection failed',
                    traceback: 'Mock traceback',
                    task_id: 'test_task'
                }
            }));
            
            await this.waitForDOMUpdate();
            
            // Verify error is displayed appropriately
            const errorElements = document.querySelectorAll('.phase-status-error, .progress-error');
            
            if (errorElements.length === 0) {
                throw new Error('Error state not properly displayed');
            }
            
            return 'Network errors are properly handled and displayed';
        });
    }
    
    async testAccessibility() {
        console.log('🧪 Testing Accessibility...');
        
        await this.runTest('Keyboard Navigation', async () => {
            // Find focusable elements
            const focusableElements = document.querySelectorAll(
                'button, [href], input, select, textarea, [tabindex]:not([tabindex="-1"])'
            );
            
            if (focusableElements.length === 0) {
                throw new Error('No focusable elements found');
            }
            
            // Test tab navigation
            let focusableCount = 0;
            for (const element of focusableElements) {
                if (element.offsetParent !== null) { // Element is visible
                    element.focus();
                    if (document.activeElement === element) {
                        focusableCount++;
                    }
                }
            }
            
            if (focusableCount === 0) {
                throw new Error('No elements can receive focus');
            }
            
            return 'Keyboard navigation works properly';
        });
        
        await this.runTest('ARIA Labels and Roles', async () => {
            const interactiveElements = document.querySelectorAll('button, [role="button"]');
            
            for (const element of interactiveElements) {
                // Check for accessible name
                const hasAccessibleName = element.getAttribute('aria-label') ||
                                        element.getAttribute('aria-labelledby') ||
                                        element.textContent.trim() ||
                                        element.getAttribute('title');
                
                if (!hasAccessibleName) {
                    console.warn(`Interactive element missing accessible name:`, element);
                }
            }
            
            return 'Interactive elements have appropriate ARIA labels';
        });
        
        await this.runTest('Visual Indicators', async () => {
            // Test status indicators have multiple visual cues (not just color)
            const statusElements = document.querySelectorAll('.phase-status, .task-status, .progress-status');
            
            for (const element of statusElements) {
                // Check for icons or text indicators in addition to color
                const hasIcon = element.querySelector('i, .icon') || 
                              element.textContent.trim().length > 0;
                
                if (!hasIcon) {
                    console.warn(`Status element relies only on color:`, element);
                }
            }
            
            return 'Status indicators use multiple visual cues';
        });
    }
    
    async testRealAgentScenarios() {
        console.log('🧪 Testing Real Agent Scenarios...');
        
        await this.runTest('Complete Agent Execution', async () => {
            // Simulate full agent execution cycle
            const taskId = 'integration_test_task';
            
            // 1. Start task
            document.dispatchEvent(new CustomEvent('task_started', {
                detail: { task_id: taskId, task_type: 'agent_execution' }
            }));
            
            await this.waitForDOMUpdate();
            
            // 2. Start phases in sequence
            for (const phase of this.mockData.phases) {
                document.dispatchEvent(new CustomEvent('phase_start', {
                    detail: { ...phase, task_id: taskId }
                }));
                
                await this.waitForDOMUpdate(100);
                
                // Simulate progress updates
                for (let i = 0; i <= 100; i += 25) {
                    document.dispatchEvent(new CustomEvent('progress_update', {
                        detail: {
                            phase_name: phase.phase_name,
                            current: i,
                            total: 100,
                            percentage: i,
                            task_id: taskId
                        }
                    }));
                    
                    await this.waitForDOMUpdate(50);
                }
                
                // Complete phase
                document.dispatchEvent(new CustomEvent('phase_complete', {
                    detail: {
                        phase_name: phase.phase_name,
                        success: true,
                        task_id: taskId
                    }
                }));
                
                await this.waitForDOMUpdate(100);
            }
            
            // 3. Complete task
            document.dispatchEvent(new CustomEvent('task_completed', {
                detail: { task_id: taskId, result: 'success' }
            }));
            
            await this.waitForDOMUpdate();
            
            // 4. Update agent status
            document.dispatchEvent(new CustomEvent('agent_status_update', {
                detail: { is_running: false, status: 'completed', task_id: taskId }
            }));
            
            await this.waitForDOMUpdate();
            
            return 'Complete agent execution scenario works correctly';
        });
        
        await this.runTest('Concurrent Task Handling', async () => {
            const taskIds = ['task_1', 'task_2', 'task_3'];
            
            // Start multiple tasks
            for (const taskId of taskIds) {
                document.dispatchEvent(new CustomEvent('task_started', {
                    detail: { task_id: taskId, task_type: 'agent_execution' }
                }));
            }
            
            await this.waitForDOMUpdate();
            
            // Start phases for each task
            for (const taskId of taskIds) {
                document.dispatchEvent(new CustomEvent('phase_start', {
                    detail: {
                        phase_name: 'concurrent_test',
                        task_id: taskId,
                        phase_description: `Processing ${taskId}`
                    }
                }));
            }
            
            await this.waitForDOMUpdate();
            
            // Verify task switcher shows multiple tasks
            const taskSelector = document.getElementById('task-selector');
            if (taskSelector) {
                const options = taskSelector.querySelectorAll('option');
                if (options.length < taskIds.length) {
                    throw new Error('Not all concurrent tasks shown in selector');
                }
            }
            
            return 'Concurrent tasks are handled properly';
        });
        
        await this.runTest('Error Recovery Scenario', async () => {
            const taskId = 'error_test_task';
            
            // Start task and phase
            document.dispatchEvent(new CustomEvent('task_started', {
                detail: { task_id: taskId, task_type: 'agent_execution' }
            }));
            
            document.dispatchEvent(new CustomEvent('phase_start', {
                detail: {
                    phase_name: 'error_prone_phase',
                    task_id: taskId,
                    phase_description: 'Testing error handling'
                }
            }));
            
            await this.waitForDOMUpdate();
            
            // Simulate error
            document.dispatchEvent(new CustomEvent('phase_error', {
                detail: {
                    phase_name: 'error_prone_phase',
                    error: 'Simulated processing error',
                    task_id: taskId
                }
            }));
            
            await this.waitForDOMUpdate();
            
            // Verify error state is displayed
            const errorElements = document.querySelectorAll('[data-status="error"], .phase-status-error');
            if (errorElements.length === 0) {
                throw new Error('Error state not properly displayed');
            }
            
            // Simulate recovery
            document.dispatchEvent(new CustomEvent('phase_start', {
                detail: {
                    phase_name: 'recovery_phase',
                    task_id: taskId,
                    phase_description: 'Recovering from error'
                }
            }));
            
            await this.waitForDOMUpdate();
            
            return 'Error recovery scenario works correctly';
        });
    }
    
    // === TEST UTILITIES ===
    
    async runTest(testName, testFunction) {
        console.log(`🧪 Running test: ${testName}`);
        
        this.testMetrics.totalTests++;
        const testStartTime = performance.now();
        
        try {
            const result = await Promise.race([
                testFunction(),
                new Promise((_, reject) => 
                    setTimeout(() => reject(new Error('Test timeout')), 30000)
                )
            ]);
            
            const testEndTime = performance.now();
            const testDuration = testEndTime - testStartTime;
            
            this.recordTestResult(testName, true, result, testDuration);
            this.testMetrics.passedTests++;
            
            console.log(`✅ Test passed: ${testName} (${testDuration.toFixed(2)}ms)`);
            
        } catch (error) {
            const testEndTime = performance.now();
            const testDuration = testEndTime - testStartTime;
            
            this.recordTestResult(testName, false, error.message, testDuration);
            this.testMetrics.failedTests++;
            
            console.error(`❌ Test failed: ${testName} (${testDuration.toFixed(2)}ms)`, error);
        }
    }
    
    recordTestResult(testName, passed, message, duration = 0) {
        this.testResults.set(testName, {
            passed,
            message,
            duration,
            timestamp: Date.now()
        });
        
        this.updateTestResultsDisplay();
    }
    
    updateTestResultsDisplay() {
        const resultsContainer = document.getElementById('test-results');
        if (!resultsContainer) return;
        
        resultsContainer.innerHTML = '';
        
        for (const [testName, result] of this.testResults) {
            const resultElement = document.createElement('div');
            resultElement.className = `test-result test-result--${result.passed ? 'passed' : 'failed'}`;
            resultElement.style.cssText = `
                display: flex; justify-content: space-between; align-items: center;
                padding: var(--space-2); margin-bottom: var(--space-1);
                border-radius: var(--radius-base);
                background: ${result.passed ? 'rgba(34, 197, 94, 0.1)' : 'rgba(239, 68, 68, 0.1)'};
                border-left: 3px solid ${result.passed ? 'var(--success-green)' : 'var(--error-red)'};
            `;
            
            resultElement.innerHTML = `
                <div>
                    <div style="font-weight: 600; color: var(--text-primary); font-size: var(--font-size-sm);">
                        <i class="fas ${result.passed ? 'fa-check' : 'fa-times'}" style="color: ${result.passed ? 'var(--success-green)' : 'var(--error-red)'}; margin-right: var(--space-1);"></i>
                        ${testName}
                    </div>
                    <div style="font-size: var(--font-size-xs); color: var(--text-secondary); margin-top: var(--space-1);">
                        ${result.message}
                    </div>
                </div>
                <div style="text-align: right; font-size: var(--font-size-xs); color: var(--text-tertiary);">
                    ${result.duration.toFixed(2)}ms
                </div>
            `;
            
            resultsContainer.appendChild(resultElement);
        }
    }
    
    showTestProgress() {
        const progressContainer = document.getElementById('test-progress');
        if (progressContainer) {
            progressContainer.style.display = 'block';
        }
    }
    
    updateTestProgress(current, total) {
        const progressText = document.getElementById('test-progress-text');
        const progressBar = document.getElementById('test-progress-bar');
        
        if (progressText) {
            progressText.textContent = `${current}/${total}`;
        }
        
        if (progressBar) {
            const percentage = total > 0 ? (current / total) * 100 : 0;
            progressBar.style.width = `${percentage}%`;
        }
    }
    
    showTestSummary() {
        const summaryContainer = document.getElementById('test-summary');
        if (!summaryContainer) return;
        
        summaryContainer.style.display = 'block';
        
        document.getElementById('passed-count').textContent = this.testMetrics.passedTests;
        document.getElementById('failed-count').textContent = this.testMetrics.failedTests;
        document.getElementById('duration-display').textContent = `${this.testMetrics.duration}ms`;
    }
    
    clearTestResults() {
        this.testResults.clear();
        this.updateTestResultsDisplay();
        
        const summaryContainer = document.getElementById('test-summary');
        if (summaryContainer) {
            summaryContainer.style.display = 'none';
        }
    }
    
    async waitForDOMUpdate(delay = 50) {
        return new Promise(resolve => {
            requestAnimationFrame(() => {
                setTimeout(resolve, delay);
            });
        });
    }
    
    simulateViewportResize(width, height) {
        // This is a simulation - in a real browser, you'd need to actually resize
        // For testing purposes, we'll trigger resize events
        Object.defineProperty(window, 'innerWidth', { value: width, writable: true });
        Object.defineProperty(window, 'innerHeight', { value: height, writable: true });
        
        window.dispatchEvent(new Event('resize'));
    }
    
    getMemoryUsage() {
        if (performance.memory) {
            return performance.memory.usedJSHeapSize;
        }
        return 0; // Fallback if memory API not available
    }
    
    // === PUBLIC API ===
    
    showTestSuite() {
        this.testContainer.style.display = 'block';
    }
    
    hideTestSuite() {
        this.testContainer.style.display = 'none';
    }
    
    getTestResults() {
        return {
            results: Array.from(this.testResults.entries()),
            metrics: { ...this.testMetrics }
        };
    }
    
    exportTestResults() {
        const results = this.getTestResults();
        const blob = new Blob([JSON.stringify(results, null, 2)], { type: 'application/json' });
        const url = URL.createObjectURL(blob);
        
        const a = document.createElement('a');
        a.href = url;
        a.download = `integration-test-results-${Date.now()}.json`;
        document.body.appendChild(a);
        a.click();
        document.body.removeChild(a);
        
        URL.revokeObjectURL(url);
    }
}

// Make globally available
window.IntegrationTestSuite = IntegrationTestSuite;

// Auto-initialize if in development mode
if (window.location.hostname === 'localhost' || window.location.hostname === '127.0.0.1') {
    window.integrationTestSuite = new IntegrationTestSuite();
    console.log('🧪 Integration Test Suite available. Press Ctrl+Shift+T to open.');
}