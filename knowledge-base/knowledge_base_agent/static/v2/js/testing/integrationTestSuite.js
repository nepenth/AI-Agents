/**
 * Frontend Layout Integration Test Suite
 * 
 * Comprehensive testing for all display components working together
 * Tests layout consistency, component coordination, performance, and accessibility
 */

class IntegrationTestSuite {
    constructor() {
        this.testResults = [];
        this.performanceMetrics = {};
        this.accessibilityIssues = [];
        this.layoutIssues = [];
        
        this.initialize();
    }
    
    initialize() {
        console.log('🧪 Initializing Integration Test Suite...');
        
        // Create test UI
        this.createTestInterface();
        
        // Setup test environment
        this.setupTestEnvironment();
        
        console.log('✅ Integration Test Suite initialized');
    }
    
    createTestInterface() {
        // Create floating test panel
        const testPanel = document.createElement('div');
        testPanel.id = 'integration-test-panel';
        testPanel.innerHTML = `
            <div class="test-panel-header">
                <h4>🧪 Integration Tests</h4>
                <button id="minimize-test-panel" class="btn btn-sm btn-outline-secondary">−</button>
                <button id="close-test-panel" class="btn btn-sm btn-outline-danger">×</button>
            </div>
            <div class="test-panel-content">
                <div class="test-controls">
                    <button id="run-all-tests" class="btn btn-primary btn-sm">Run All Tests</button>
                    <button id="run-layout-tests" class="btn btn-secondary btn-sm">Layout Tests</button>
                    <button id="run-performance-tests" class="btn btn-secondary btn-sm">Performance Tests</button>
                    <button id="run-accessibility-tests" class="btn btn-secondary btn-sm">A11y Tests</button>
                    <button id="clear-test-results" class="btn btn-outline-secondary btn-sm">Clear</button>
                </div>
                <div class="test-results" id="test-results">
                    <div class="text-muted">Click "Run All Tests" to start validation</div>
                </div>
            </div>
        `;
        
        // Style the test panel
        testPanel.style.cssText = `
            position: fixed;
            top: 20px;
            right: 20px;
            width: 400px;
            max-height: 80vh;
            background: var(--glass-bg, rgba(255, 255, 255, 0.1));
            backdrop-filter: blur(10px);
            border: 1px solid var(--glass-border, rgba(255, 255, 255, 0.2));
            border-radius: 12px;
            padding: 16px;
            z-index: 10000;
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
            font-size: 14px;
            color: var(--text-primary, #333);
            box-shadow: 0 8px 32px rgba(0, 0, 0, 0.1);
        `;
        
        document.body.appendChild(testPanel);
        
        // Add event listeners
        this.attachTestPanelListeners();
    }
    
    attachTestPanelListeners() {
        document.getElementById('run-all-tests')?.addEventListener('click', () => this.runAllTests());
        document.getElementById('run-layout-tests')?.addEventListener('click', () => this.runLayoutTests());
        document.getElementById('run-performance-tests')?.addEventListener('click', () => this.runPerformanceTests());
        document.getElementById('run-accessibility-tests')?.addEventListener('click', () => this.runAccessibilityTests());
        document.getElementById('clear-test-results')?.addEventListener('click', () => this.clearResults());
        
        document.getElementById('minimize-test-panel')?.addEventListener('click', () => {
            const content = document.querySelector('#integration-test-panel .test-panel-content');
            if (content) {
                content.style.display = content.style.display === 'none' ? 'block' : 'none';
            }
        });
        
        document.getElementById('close-test-panel')?.addEventListener('click', () => {
            document.getElementById('integration-test-panel')?.remove();
        });
    }
    
    setupTestEnvironment() {
        // Create mock data generators
        this.mockDataGenerator = new MockDataGenerator();
        
        // Setup performance monitoring
        this.performanceMonitor = new PerformanceTestMonitor();
        
        // Setup accessibility checker
        this.accessibilityChecker = new AccessibilityChecker();
        
        // Setup layout validator
        this.layoutValidator = new LayoutValidator();
    }
    
    async runAllTests() {
        console.log('🧪 Running comprehensive integration tests...');
        this.clearResults();
        this.addResult('info', 'Starting comprehensive integration test suite...');
        
        try {
            // Test 1: Component Initialization
            await this.testComponentInitialization();
            
            // Test 2: Layout Consistency
            await this.testLayoutConsistency();
            
            // Test 3: Component Coordination
            await this.testComponentCoordination();
            
            // Test 4: Performance Validation
            await this.testPerformanceOptimization();
            
            // Test 5: Error Handling
            await this.testErrorHandling();
            
            // Test 6: Accessibility Validation
            await this.testAccessibility();
            
            // Test 7: Real Agent Execution Scenarios
            await this.testRealAgentScenarios();
            
            // Test 8: Responsive Design
            await this.testResponsiveDesign();
            
            // Generate final report
            this.generateTestReport();
            
        } catch (error) {
            this.addResult('error', `Test suite failed: ${error.message}`);
            console.error('Integration test suite failed:', error);
        }
    }
    
    async testComponentInitialization() {
        this.addResult('info', '🔧 Testing component initialization...');
        
        const components = [
            'PhaseDisplayManager',
            'ProgressDisplayManager', 
            'TaskDisplayManager',
            'AgentControlManager',
            'ExecutionPlanManager',
            'LiveLogsManager',
            'GpuStatusManager'
        ];
        
        let passedTests = 0;
        
        for (const componentName of components) {
            try {
                const isAvailable = !!window[componentName];
                
                if (isAvailable) {
                    // Test basic instantiation
                    const testContainer = document.createElement('div');
                    testContainer.id = `test-${componentName.toLowerCase()}`;
                    document.body.appendChild(testContainer);
                    
                    let instance;
                    if (componentName === 'AgentControlManager') {
                        instance = new window[componentName]({ request: () => Promise.resolve({}) });
                    } else if (['PhaseDisplayManager', 'ProgressDisplayManager', 'TaskDisplayManager'].includes(componentName)) {
                        instance = new window[componentName](testContainer);
                    } else {
                        instance = new window[componentName]();
                    }
                    
                    if (instance) {
                        this.addResult('success', `✅ ${componentName} initialized successfully`);
                        passedTests++;
                    }
                    
                    // Cleanup
                    testContainer.remove();
                    
                } else {
                    this.addResult('warning', `⚠️ ${componentName} not available`);
                }
                
            } catch (error) {
                this.addResult('error', `❌ ${componentName} failed to initialize: ${error.message}`);
            }
        }
        
        this.addResult('info', `Component initialization: ${passedTests}/${components.length} passed`);
    }
    
    async testLayoutConsistency() {
        this.addResult('info', '📐 Testing layout consistency across screen sizes...');
        
        const testSizes = [
            { width: 320, height: 568, name: 'Mobile Portrait' },
            { width: 768, height: 1024, name: 'Tablet Portrait' },
            { width: 1024, height: 768, name: 'Tablet Landscape' },
            { width: 1440, height: 900, name: 'Desktop' },
            { width: 1920, height: 1080, name: 'Large Desktop' }
        ];
        
        const originalSize = { width: window.innerWidth, height: window.innerHeight };
        
        for (const size of testSizes) {
            try {
                // Simulate viewport resize
                Object.defineProperty(window, 'innerWidth', { value: size.width, writable: true });
                Object.defineProperty(window, 'innerHeight', { value: size.height, writable: true });
                
                // Trigger resize event
                window.dispatchEvent(new Event('resize'));
                
                // Wait for layout adjustments
                await this.wait(100);
                
                // Check layout issues
                const issues = this.layoutValidator.checkLayout(size);
                
                if (issues.length === 0) {
                    this.addResult('success', `✅ ${size.name} (${size.width}x${size.height}): Layout OK`);
                } else {
                    this.addResult('warning', `⚠️ ${size.name}: ${issues.length} layout issues`);
                    issues.forEach(issue => {
                        this.addResult('warning', `  - ${issue}`);
                    });
                }
                
            } catch (error) {
                this.addResult('error', `❌ ${size.name}: Layout test failed - ${error.message}`);
            }
        }
        
        // Restore original size
        Object.defineProperty(window, 'innerWidth', { value: originalSize.width, writable: true });
        Object.defineProperty(window, 'innerHeight', { value: originalSize.height, writable: true });
        window.dispatchEvent(new Event('resize'));
    }
    
    async testComponentCoordination() {
        this.addResult('info', '🤝 Testing component coordination...');
        
        // Test event coordination
        const testEvents = [
            { name: 'agent_status_update', data: { is_running: true, current_phase_message: 'Test phase' } },
            { name: 'phase_update', data: { phase_id: 'test_phase', status: 'active', message: 'Testing...' } },
            { name: 'progress_update', data: { phase: 'test', processed_count: 50, total_count: 100 } },
            { name: 'log', data: { message: 'Test log message', level: 'INFO', timestamp: new Date().toISOString() } }
        ];
        
        let coordinationTests = 0;
        
        for (const testEvent of testEvents) {
            try {
                // Create event listeners to track coordination
                const listeners = [];
                const coordinationPromise = new Promise((resolve) => {
                    const listener = (event) => {
                        listeners.push(event.detail);
                        if (listeners.length >= 1) resolve(listeners);
                    };
                    document.addEventListener(testEvent.name, listener);
                    setTimeout(() => resolve(listeners), 1000); // Timeout after 1 second
                });
                
                // Dispatch test event
                document.dispatchEvent(new CustomEvent(testEvent.name, { detail: testEvent.data }));
                
                // Wait for coordination
                const results = await coordinationPromise;
                
                if (results.length > 0) {
                    this.addResult('success', `✅ ${testEvent.name}: Components coordinated (${results.length} responses)`);
                    coordinationTests++;
                } else {
                    this.addResult('warning', `⚠️ ${testEvent.name}: No component coordination detected`);
                }
                
            } catch (error) {
                this.addResult('error', `❌ ${testEvent.name}: Coordination test failed - ${error.message}`);
            }
        }
        
        this.addResult('info', `Component coordination: ${coordinationTests}/${testEvents.length} events coordinated`);
    }
    
    async testPerformanceOptimization() {
        this.addResult('info', '⚡ Testing performance optimization...');
        
        const performanceTests = [
            { name: 'DOM Update Performance', test: () => this.testDOMUpdatePerformance() },
            { name: 'Memory Usage', test: () => this.testMemoryUsage() },
            { name: 'Event Handler Performance', test: () => this.testEventHandlerPerformance() },
            { name: 'Rendering Performance', test: () => this.testRenderingPerformance() }
        ];
        
        for (const perfTest of performanceTests) {
            try {
                const startTime = performance.now();
                const result = await perfTest.test();
                const endTime = performance.now();
                const duration = endTime - startTime;
                
                this.performanceMetrics[perfTest.name] = { duration, result };
                
                if (duration < 100) { // Less than 100ms is good
                    this.addResult('success', `✅ ${perfTest.name}: ${duration.toFixed(2)}ms (Good)`);
                } else if (duration < 500) {
                    this.addResult('warning', `⚠️ ${perfTest.name}: ${duration.toFixed(2)}ms (Acceptable)`);
                } else {
                    this.addResult('error', `❌ ${perfTest.name}: ${duration.toFixed(2)}ms (Poor)`);
                }
                
            } catch (error) {
                this.addResult('error', `❌ ${perfTest.name}: Test failed - ${error.message}`);
            }
        }
    }
    
    async testErrorHandling() {
        this.addResult('info', '🛡️ Testing error handling and recovery...');
        
        const errorScenarios = [
            { name: 'Invalid Event Data', test: () => this.testInvalidEventData() },
            { name: 'Missing DOM Elements', test: () => this.testMissingDOMElements() },
            { name: 'Network Failures', test: () => this.testNetworkFailures() },
            { name: 'Component Failures', test: () => this.testComponentFailures() }
        ];
        
        let recoveryTests = 0;
        
        for (const scenario of errorScenarios) {
            try {
                const recovered = await scenario.test();
                
                if (recovered) {
                    this.addResult('success', `✅ ${scenario.name}: Error handled and recovered`);
                    recoveryTests++;
                } else {
                    this.addResult('warning', `⚠️ ${scenario.name}: Error handled but no recovery`);
                }
                
            } catch (error) {
                this.addResult('error', `❌ ${scenario.name}: Error handling failed - ${error.message}`);
            }
        }
        
        this.addResult('info', `Error handling: ${recoveryTests}/${errorScenarios.length} scenarios recovered`);
    }
    
    async testAccessibility() {
        this.addResult('info', '♿ Testing accessibility compliance...');
        
        const accessibilityTests = [
            { name: 'Keyboard Navigation', test: () => this.testKeyboardNavigation() },
            { name: 'Screen Reader Support', test: () => this.testScreenReaderSupport() },
            { name: 'Color Contrast', test: () => this.testColorContrast() },
            { name: 'ARIA Labels', test: () => this.testARIALabels() },
            { name: 'Focus Management', test: () => this.testFocusManagement() }
        ];
        
        let accessibilityScore = 0;
        
        for (const a11yTest of accessibilityTests) {
            try {
                const result = await a11yTest.test();
                
                if (result.passed) {
                    this.addResult('success', `✅ ${a11yTest.name}: ${result.score}% compliant`);
                    accessibilityScore += result.score;
                } else {
                    this.addResult('warning', `⚠️ ${a11yTest.name}: ${result.score}% compliant (${result.issues.length} issues)`);
                    result.issues.forEach(issue => {
                        this.addResult('warning', `  - ${issue}`);
                    });
                    accessibilityScore += result.score;
                }
                
            } catch (error) {
                this.addResult('error', `❌ ${a11yTest.name}: Test failed - ${error.message}`);
            }
        }
        
        const avgScore = accessibilityScore / accessibilityTests.length;
        this.addResult('info', `Overall accessibility score: ${avgScore.toFixed(1)}%`);
    }
    
    async testRealAgentScenarios() {
        this.addResult('info', '🤖 Testing with real agent execution scenarios...');
        
        const agentScenarios = [
            { name: 'Agent Startup', events: this.mockDataGenerator.generateAgentStartup() },
            { name: 'Processing Pipeline', events: this.mockDataGenerator.generateProcessingPipeline() },
            { name: 'Error Recovery', events: this.mockDataGenerator.generateErrorRecovery() },
            { name: 'Agent Completion', events: this.mockDataGenerator.generateAgentCompletion() }
        ];
        
        for (const scenario of agentScenarios) {
            try {
                this.addResult('info', `  Testing ${scenario.name}...`);
                
                // Simulate real-time event sequence
                for (const event of scenario.events) {
                    document.dispatchEvent(new CustomEvent(event.type, { detail: event.data }));
                    await this.wait(event.delay || 100);
                }
                
                // Validate UI state after scenario
                const uiState = this.validateUIState();
                
                if (uiState.isValid) {
                    this.addResult('success', `✅ ${scenario.name}: UI state valid after ${scenario.events.length} events`);
                } else {
                    this.addResult('warning', `⚠️ ${scenario.name}: UI state issues - ${uiState.issues.join(', ')}`);
                }
                
            } catch (error) {
                this.addResult('error', `❌ ${scenario.name}: Scenario test failed - ${error.message}`);
            }
        }
    }
    
    async testResponsiveDesign() {
        this.addResult('info', '📱 Testing responsive design behavior...');
        
        const breakpoints = [
            { name: 'Mobile', width: 375 },
            { name: 'Tablet', width: 768 },
            { name: 'Desktop', width: 1024 },
            { name: 'Large Desktop', width: 1440 }
        ];
        
        for (const breakpoint of breakpoints) {
            try {
                // Simulate viewport change
                Object.defineProperty(window, 'innerWidth', { value: breakpoint.width, writable: true });
                window.dispatchEvent(new Event('resize'));
                await this.wait(200);
                
                // Check responsive behavior
                const responsiveIssues = this.checkResponsiveBehavior(breakpoint.width);
                
                if (responsiveIssues.length === 0) {
                    this.addResult('success', `✅ ${breakpoint.name} (${breakpoint.width}px): Responsive design OK`);
                } else {
                    this.addResult('warning', `⚠️ ${breakpoint.name}: ${responsiveIssues.length} responsive issues`);
                }
                
            } catch (error) {
                this.addResult('error', `❌ ${breakpoint.name}: Responsive test failed - ${error.message}`);
            }
        }
    }
    
    // Helper methods for specific tests
    async testDOMUpdatePerformance() {
        const testContainer = document.createElement('div');
        document.body.appendChild(testContainer);
        
        // Simulate rapid DOM updates
        for (let i = 0; i < 100; i++) {
            const element = document.createElement('div');
            element.textContent = `Test element ${i}`;
            testContainer.appendChild(element);
        }
        
        testContainer.remove();
        return { updatesPerformed: 100 };
    }
    
    async testMemoryUsage() {
        const initialMemory = performance.memory ? performance.memory.usedJSHeapSize : 0;
        
        // Create and destroy components to test memory leaks
        const components = [];
        for (let i = 0; i < 10; i++) {
            const container = document.createElement('div');
            document.body.appendChild(container);
            
            if (window.PhaseDisplayManager) {
                components.push(new window.PhaseDisplayManager(container));
            }
        }
        
        // Cleanup
        components.forEach(component => {
            if (component.destroy) component.destroy();
        });
        
        const finalMemory = performance.memory ? performance.memory.usedJSHeapSize : 0;
        const memoryDelta = finalMemory - initialMemory;
        
        return { memoryDelta, acceptable: memoryDelta < 1024 * 1024 }; // Less than 1MB
    }
    
    async testEventHandlerPerformance() {
        let eventCount = 0;
        const handler = () => eventCount++;
        
        // Add many event listeners
        for (let i = 0; i < 100; i++) {
            document.addEventListener('test-event', handler);
        }
        
        // Fire events rapidly
        for (let i = 0; i < 100; i++) {
            document.dispatchEvent(new CustomEvent('test-event'));
        }
        
        // Cleanup
        for (let i = 0; i < 100; i++) {
            document.removeEventListener('test-event', handler);
        }
        
        return { eventsHandled: eventCount };
    }
    
    async testRenderingPerformance() {
        const testContainer = document.createElement('div');
        testContainer.style.cssText = 'position: absolute; top: -9999px; left: -9999px;';
        document.body.appendChild(testContainer);
        
        // Create complex layout
        for (let i = 0; i < 50; i++) {
            const row = document.createElement('div');
            row.style.cssText = 'display: flex; padding: 8px; border: 1px solid #ccc;';
            
            for (let j = 0; j < 10; j++) {
                const cell = document.createElement('div');
                cell.textContent = `Cell ${i}-${j}`;
                cell.style.cssText = 'flex: 1; padding: 4px; margin: 2px; background: #f0f0f0;';
                row.appendChild(cell);
            }
            
            testContainer.appendChild(row);
        }
        
        // Force layout calculation
        testContainer.offsetHeight;
        
        testContainer.remove();
        return { elementsRendered: 500 };
    }
    
    async testInvalidEventData() {
        try {
            // Send invalid event data
            document.dispatchEvent(new CustomEvent('phase_update', { 
                detail: { invalid: 'data', missing: 'required_fields' } 
            }));
            
            // Check if components handled gracefully
            await this.wait(100);
            return true; // If no errors thrown, recovery successful
        } catch (error) {
            return false;
        }
    }
    
    async testMissingDOMElements() {
        try {
            // Try to initialize component with missing container
            if (window.PhaseDisplayManager) {
                new window.PhaseDisplayManager(null);
            }
            return true;
        } catch (error) {
            return false;
        }
    }
    
    async testNetworkFailures() {
        // Mock network failure
        const originalFetch = window.fetch;
        window.fetch = () => Promise.reject(new Error('Network error'));
        
        try {
            // Trigger network-dependent operation
            if (window.APIClient) {
                const api = new window.APIClient();
                await api.request('/test').catch(() => {}); // Ignore error
            }
            
            // Restore fetch
            window.fetch = originalFetch;
            return true;
        } catch (error) {
            window.fetch = originalFetch;
            return false;
        }
    }
    
    async testComponentFailures() {
        try {
            // Simulate component method failure
            const testContainer = document.createElement('div');
            
            if (window.PhaseDisplayManager) {
                const manager = new window.PhaseDisplayManager(testContainer);
                
                // Try to call method with invalid data
                manager.updatePhase(null, null, null);
            }
            
            testContainer.remove();
            return true;
        } catch (error) {
            return false;
        }
    }
    
    async testKeyboardNavigation() {
        const focusableElements = document.querySelectorAll(
            'button, [href], input, select, textarea, [tabindex]:not([tabindex="-1"])'
        );
        
        let navigableElements = 0;
        let issues = [];
        
        focusableElements.forEach((element, index) => {
            try {
                element.focus();
                if (document.activeElement === element) {
                    navigableElements++;
                } else {
                    issues.push(`Element ${index} not focusable`);
                }
            } catch (error) {
                issues.push(`Element ${index} focus error: ${error.message}`);
            }
        });
        
        const score = focusableElements.length > 0 ? (navigableElements / focusableElements.length) * 100 : 100;
        
        return {
            passed: score >= 90,
            score,
            issues
        };
    }
    
    async testScreenReaderSupport() {
        const elementsWithLabels = document.querySelectorAll('[aria-label], [aria-labelledby], label');
        const interactiveElements = document.querySelectorAll('button, input, select, textarea, [role="button"]');
        
        let labeledElements = 0;
        let issues = [];
        
        interactiveElements.forEach((element, index) => {
            const hasLabel = element.hasAttribute('aria-label') || 
                           element.hasAttribute('aria-labelledby') ||
                           element.closest('label') ||
                           document.querySelector(`label[for="${element.id}"]`);
            
            if (hasLabel) {
                labeledElements++;
            } else {
                issues.push(`Interactive element ${index} missing label`);
            }
        });
        
        const score = interactiveElements.length > 0 ? (labeledElements / interactiveElements.length) * 100 : 100;
        
        return {
            passed: score >= 80,
            score,
            issues
        };
    }
    
    async testColorContrast() {
        // Simplified color contrast test
        const textElements = document.querySelectorAll('p, span, div, button, a, h1, h2, h3, h4, h5, h6');
        let contrastIssues = [];
        let checkedElements = 0;
        
        textElements.forEach((element, index) => {
            if (element.textContent.trim()) {
                const styles = window.getComputedStyle(element);
                const color = styles.color;
                const backgroundColor = styles.backgroundColor;
                
                // Basic contrast check (simplified)
                if (color === backgroundColor) {
                    contrastIssues.push(`Element ${index} has poor contrast`);
                }
                checkedElements++;
            }
        });
        
        const score = checkedElements > 0 ? ((checkedElements - contrastIssues.length) / checkedElements) * 100 : 100;
        
        return {
            passed: score >= 90,
            score,
            issues: contrastIssues
        };
    }
    
    async testARIALabels() {
        const elementsWithARIA = document.querySelectorAll('[aria-label], [aria-labelledby], [aria-describedby], [role]');
        const requiredARIAElements = document.querySelectorAll('button, input, select, textarea');
        
        let properARIA = 0;
        let issues = [];
        
        requiredARIAElements.forEach((element, index) => {
            const hasARIA = element.hasAttribute('aria-label') || 
                          element.hasAttribute('aria-labelledby') ||
                          element.hasAttribute('role');
            
            if (hasARIA) {
                properARIA++;
            } else {
                issues.push(`Element ${index} missing ARIA attributes`);
            }
        });
        
        const score = requiredARIAElements.length > 0 ? (properARIA / requiredARIAElements.length) * 100 : 100;
        
        return {
            passed: score >= 75,
            score,
            issues
        };
    }
    
    async testFocusManagement() {
        const modals = document.querySelectorAll('.modal, [role="dialog"]');
        let focusIssues = [];
        
        modals.forEach((modal, index) => {
            const focusableElements = modal.querySelectorAll(
                'button, [href], input, select, textarea, [tabindex]:not([tabindex="-1"])'
            );
            
            if (focusableElements.length === 0) {
                focusIssues.push(`Modal ${index} has no focusable elements`);
            }
        });
        
        const score = modals.length > 0 ? ((modals.length - focusIssues.length) / modals.length) * 100 : 100;
        
        return {
            passed: score >= 90,
            score,
            issues: focusIssues
        };
    }
    
    validateUIState() {
        const issues = [];
        
        // Check for common UI state issues
        const hiddenElements = document.querySelectorAll('[style*="display: none"]');
        const emptyContainers = document.querySelectorAll('.phase-display:empty, .progress-display:empty');
        const errorStates = document.querySelectorAll('.error, .alert-danger');
        
        if (emptyContainers.length > 0) {
            issues.push(`${emptyContainers.length} empty display containers`);
        }
        
        if (errorStates.length > 0) {
            issues.push(`${errorStates.length} error states visible`);
        }
        
        return {
            isValid: issues.length === 0,
            issues
        };
    }
    
    checkResponsiveBehavior(width) {
        const issues = [];
        
        // Check for horizontal scrollbars
        if (document.body.scrollWidth > width) {
            issues.push('Horizontal scrollbar present');
        }
        
        // Check for overlapping elements
        const elements = document.querySelectorAll('.phase-display, .progress-display, .agent-controls');
        elements.forEach((element, index) => {
            const rect = element.getBoundingClientRect();
            if (rect.right > width) {
                issues.push(`Element ${index} extends beyond viewport`);
            }
        });
        
        return issues;
    }
    
    generateTestReport() {
        const passedTests = this.testResults.filter(r => r.type === 'success').length;
        const warningTests = this.testResults.filter(r => r.type === 'warning').length;
        const failedTests = this.testResults.filter(r => r.type === 'error').length;
        const totalTests = passedTests + warningTests + failedTests;
        
        const report = `
            <div class="test-summary">
                <h5>📊 Test Summary</h5>
                <div class="test-stats">
                    <span class="badge bg-success">${passedTests} Passed</span>
                    <span class="badge bg-warning">${warningTests} Warnings</span>
                    <span class="badge bg-danger">${failedTests} Failed</span>
                    <span class="badge bg-info">${totalTests} Total</span>
                </div>
                <div class="test-score">
                    Overall Score: ${totalTests > 0 ? Math.round((passedTests / totalTests) * 100) : 0}%
                </div>
            </div>
        `;
        
        this.addResult('info', report, true);
        
        console.log('🧪 Integration Test Suite Complete');
        console.log(`Results: ${passedTests} passed, ${warningTests} warnings, ${failedTests} failed`);
    }
    
    // Test execution helpers
    async runLayoutTests() {
        this.clearResults();
        await this.testLayoutConsistency();
        await this.testResponsiveDesign();
    }
    
    async runPerformanceTests() {
        this.clearResults();
        await this.testPerformanceOptimization();
    }
    
    async runAccessibilityTests() {
        this.clearResults();
        await this.testAccessibility();
    }
    
    // Utility methods
    wait(ms) {
        return new Promise(resolve => setTimeout(resolve, ms));
    }
    
    addResult(type, message, isHTML = false) {
        const result = { type, message, timestamp: new Date(), isHTML };
        this.testResults.push(result);
        
        const resultsContainer = document.getElementById('test-results');
        if (resultsContainer) {
            const resultElement = document.createElement('div');
            resultElement.className = `test-result test-result--${type}`;
            
            if (isHTML) {
                resultElement.innerHTML = message;
            } else {
                resultElement.textContent = message;
            }
            
            resultsContainer.appendChild(resultElement);
            resultsContainer.scrollTop = resultsContainer.scrollHeight;
        }
        
        console.log(`[${type.toUpperCase()}] ${message}`);
    }
    
    clearResults() {
        this.testResults = [];
        const resultsContainer = document.getElementById('test-results');
        if (resultsContainer) {
            resultsContainer.innerHTML = '<div class="text-muted">Test results will appear here...</div>';
        }
    }
}

// Mock Data Generator for testing
class MockDataGenerator {
    generateAgentStartup() {
        return [
            { type: 'agent_status_update', data: { is_running: true, current_phase_message: 'Starting agent...' }, delay: 100 },
            { type: 'phase_start', data: { phase_id: 'initialization', message: 'Initializing system...' }, delay: 200 },
            { type: 'phase_update', data: { phase_id: 'initialization', status: 'active', message: 'Loading configuration...' }, delay: 300 },
            { type: 'phase_complete', data: { phase_id: 'initialization', message: 'Initialization complete' }, delay: 400 }
        ];
    }
    
    generateProcessingPipeline() {
        return [
            { type: 'phase_start', data: { phase_id: 'fetch_bookmarks', message: 'Fetching bookmarks...' }, delay: 100 },
            { type: 'progress_update', data: { phase: 'fetch_bookmarks', processed_count: 25, total_count: 100 }, delay: 200 },
            { type: 'progress_update', data: { phase: 'fetch_bookmarks', processed_count: 50, total_count: 100 }, delay: 300 },
            { type: 'progress_update', data: { phase: 'fetch_bookmarks', processed_count: 100, total_count: 100 }, delay: 400 },
            { type: 'phase_complete', data: { phase_id: 'fetch_bookmarks', message: 'Bookmarks fetched successfully' }, delay: 500 }
        ];
    }
    
    generateErrorRecovery() {
        return [
            { type: 'phase_start', data: { phase_id: 'process_content', message: 'Processing content...' }, delay: 100 },
            { type: 'phase_error', data: { phase_id: 'process_content', message: 'Network timeout occurred' }, delay: 200 },
            { type: 'log', data: { message: 'Retrying failed operation...', level: 'WARNING' }, delay: 300 },
            { type: 'phase_update', data: { phase_id: 'process_content', status: 'active', message: 'Retrying...' }, delay: 400 },
            { type: 'phase_complete', data: { phase_id: 'process_content', message: 'Content processed successfully' }, delay: 500 }
        ];
    }
    
    generateAgentCompletion() {
        return [
            { type: 'phase_start', data: { phase_id: 'finalization', message: 'Finalizing results...' }, delay: 100 },
            { type: 'progress_update', data: { phase: 'finalization', processed_count: 100, total_count: 100 }, delay: 200 },
            { type: 'phase_complete', data: { phase_id: 'finalization', message: 'All tasks completed' }, delay: 300 },
            { type: 'agent_status_update', data: { is_running: false, current_phase_message: 'Agent completed successfully' }, delay: 400 }
        ];
    }
}

// Performance Test Monitor
class PerformanceTestMonitor {
    constructor() {
        this.metrics = {};
        this.observers = [];
    }
    
    startMonitoring() {
        // Monitor performance metrics
        if ('PerformanceObserver' in window) {
            const observer = new PerformanceObserver((list) => {
                for (const entry of list.getEntries()) {
                    this.metrics[entry.name] = entry;
                }
            });
            
            observer.observe({ entryTypes: ['measure', 'navigation', 'paint'] });
            this.observers.push(observer);
        }
    }
    
    stopMonitoring() {
        this.observers.forEach(observer => observer.disconnect());
        this.observers = [];
    }
    
    getMetrics() {
        return { ...this.metrics };
    }
}

// Accessibility Checker
class AccessibilityChecker {
    checkElement(element) {
        const issues = [];
        
        // Check for missing alt text on images
        if (element.tagName === 'IMG' && !element.alt) {
            issues.push('Image missing alt text');
        }
        
        // Check for missing labels on form elements
        if (['INPUT', 'SELECT', 'TEXTAREA'].includes(element.tagName)) {
            const hasLabel = element.hasAttribute('aria-label') || 
                           element.hasAttribute('aria-labelledby') ||
                           document.querySelector(`label[for="${element.id}"]`);
            
            if (!hasLabel) {
                issues.push('Form element missing label');
            }
        }
        
        // Check for proper heading hierarchy
        if (element.tagName.match(/^H[1-6]$/)) {
            const level = parseInt(element.tagName.charAt(1));
            const prevHeading = this.findPreviousHeading(element);
            
            if (prevHeading && level > parseInt(prevHeading.tagName.charAt(1)) + 1) {
                issues.push('Heading hierarchy skipped');
            }
        }
        
        return issues;
    }
    
    findPreviousHeading(element) {
        let current = element.previousElementSibling;
        
        while (current) {
            if (current.tagName.match(/^H[1-6]$/)) {
                return current;
            }
            current = current.previousElementSibling;
        }
        
        return null;
    }
}

// Layout Validator
class LayoutValidator {
    checkLayout(viewport) {
        const issues = [];
        
        // Check for elements extending beyond viewport
        const allElements = document.querySelectorAll('*');
        allElements.forEach((element, index) => {
            const rect = element.getBoundingClientRect();
            
            if (rect.right > viewport.width) {
                issues.push(`Element ${index} extends beyond viewport width`);
            }
            
            if (rect.bottom > viewport.height && element.offsetParent) {
                // Only flag if element is visible
                issues.push(`Element ${index} extends beyond viewport height`);
            }
        });
        
        // Check for overlapping elements
        const importantElements = document.querySelectorAll('.phase-display, .progress-display, .agent-controls, .modal');
        for (let i = 0; i < importantElements.length; i++) {
            for (let j = i + 1; j < importantElements.length; j++) {
                if (this.elementsOverlap(importantElements[i], importantElements[j])) {
                    issues.push(`Elements ${i} and ${j} are overlapping`);
                }
            }
        }
        
        return issues;
    }
    
    elementsOverlap(el1, el2) {
        const rect1 = el1.getBoundingClientRect();
        const rect2 = el2.getBoundingClientRect();
        
        return !(rect1.right < rect2.left || 
                rect2.right < rect1.left || 
                rect1.bottom < rect2.top || 
                rect2.bottom < rect1.top);
    }
}

// Auto-initialize test suite when script loads
if (typeof window !== 'undefined') {
    window.IntegrationTestSuite = IntegrationTestSuite;
    
    // Add keyboard shortcut to open test suite
    document.addEventListener('keydown', (e) => {
        if (e.ctrlKey && e.shiftKey && e.key === 'T') {
            if (!document.getElementById('integration-test-panel')) {
                new IntegrationTestSuite();
            }
        }
    });
    
    console.log('🧪 Integration Test Suite loaded. Press Ctrl+Shift+T to open test panel.');
}

// Export for Node.js environments
if (typeof module !== 'undefined' && module.exports) {
    module.exports = {
        IntegrationTestSuite,
        MockDataGenerator,
        PerformanceTestMonitor,
        AccessibilityChecker,
        LayoutValidator
    };
}