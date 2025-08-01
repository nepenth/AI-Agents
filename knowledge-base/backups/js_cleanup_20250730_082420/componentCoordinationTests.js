/* V2 COMPONENTCOORDINATIONTESTS.JS - COMPONENT COORDINATION SYSTEM TESTS */

/**
 * Comprehensive test suite for DisplayComponentCoordinator
 * 
 * ARCHITECTURE:
 * - Tests component registration and management
 * - Tests event coordination between components
 * - Tests component initialization order and dependencies
 * - Tests component cleanup coordination
 * - Validates duplicate DOM element prevention
 * - Tests component state management
 */
class ComponentCoordinationTestSuite {
    constructor() {
        this.testResults = [];
        this.originalCoordinator = window.displayCoordinator;
        this.testCoordinator = null;
        this.mockComponents = new Map();
        
        console.log('🧪 ComponentCoordinationTestSuite initialized');
    }
    
    async runAllTests() {
        console.log('🧪 Starting component coordination test suite...');
        
        try {
            // Setup test environment
            await this.setupTestEnvironment();
            
            // Run core functionality tests
            await this.testComponentRegistration();
            await this.testEventCoordination();
            await this.testInitializationOrder();
            await this.testComponentCleanup();
            await this.testDuplicatePrevention();
            await this.testStateManagement();
            
            // Run integration tests
            await this.testRealComponentIntegration();
            
            // Run performance tests
            await this.testCoordinationPerformance();
            
            // Run error handling tests
            await this.testErrorHandling();
            
            // Generate test report
            this.generateTestReport();
            
        } catch (error) {
            console.error('❌ Component coordination test suite failed:', error);
            this.testResults.push({
                test: 'Test Suite Execution',
                status: 'FAILED',
                error: error.message,
                timestamp: new Date()
            });
        } finally {
            // Cleanup test environment
            await this.cleanupTestEnvironment();
        }
    }
    
    async setupTestEnvironment() {
        console.log('🔧 Setting up component coordination test environment...');
        
        // Create isolated test coordinator
        this.testCoordinator = new DisplayComponentCoordinator();
        
        // Create mock components
        this.createMockComponents();
        
        // Create test DOM elements
        this.createTestDOM();
        
        this.testResults.push({
            test: 'Test Environment Setup',
            status: 'PASSED',
            timestamp: new Date()
        });
    }
    
    createMockComponents() {
        // Mock PhaseDisplayManager
        this.mockComponents.set('MockPhaseDisplay', {
            name: 'MockPhaseDisplay',
            initialized: false,
            events: [],
            element: null,
            init: function() {
                this.initialized = true;
                console.log('MockPhaseDisplay initialized');
            },
            cleanup: function() {
                this.initialized = false;
                this.events = [];
                console.log('MockPhaseDisplay cleaned up');
            },
            handleEvent: function(event) {
                this.events.push(event);
            }
        });
        
        // Mock ProgressDisplayManager
        this.mockComponents.set('MockProgressDisplay', {
            name: 'MockProgressDisplay',
            initialized: false,
            events: [],
            element: null,
            dependencies: ['MockPhaseDisplay'],
            init: function() {
                this.initialized = true;
                console.log('MockProgressDisplay initialized');
            },
            cleanup: function() {
                this.initialized = false;
                this.events = [];
                console.log('MockProgressDisplay cleaned up');
            },
            handleEvent: function(event) {
                this.events.push(event);
            }
        });
        
        // Mock TaskDisplayManager
        this.mockComponents.set('MockTaskDisplay', {
            name: 'MockTaskDisplay',
            initialized: false,
            events: [],
            element: null,
            init: function() {
                this.initialized = true;
                console.log('MockTaskDisplay initialized');
            },
            cleanup: function() {
                this.initialized = false;
                this.events = [];
                console.log('MockTaskDisplay cleaned up');
            },
            handleEvent: function(event) {
                this.events.push(event);
            }
        });
    }
    
    createTestDOM() {
        const testContainer = document.createElement('div');
        testContainer.id = 'coordination-test-container';
        testContainer.style.cssText = `
            position: fixed;
            top: -9999px;
            left: -9999px;
            width: 1000px;
            height: 800px;
            visibility: hidden;
        `;
        
        testContainer.innerHTML = `
            <div id="test-phase-list"></div>
            <div id="test-progress-container"></div>
            <div id="test-task-container"></div>
            <div id="test-notification-area"></div>
        `;
        
        document.body.appendChild(testContainer);
    }
    
    async testComponentRegistration() {
        console.log('📋 Testing component registration...');
        
        try {
            const mockComponent = this.mockComponents.get('MockPhaseDisplay');
            
            // Test basic registration
            const componentInfo = this.testCoordinator.registerComponent('MockPhaseDisplay', mockComponent, {
                priority: 80,
                dependencies: []
            });
            
            if (!componentInfo || componentInfo.name !== 'MockPhaseDisplay') {
                throw new Error('Component registration failed');
            }
            
            // Test component retrieval
            const retrievedComponent = this.testCoordinator.getComponent('MockPhaseDisplay');
            if (!retrievedComponent || retrievedComponent.name !== 'MockPhaseDisplay') {
                throw new Error('Component retrieval failed');
            }
            
            // Test duplicate registration (should replace)
            const duplicateInfo = this.testCoordinator.registerComponent('MockPhaseDisplay', mockComponent, {
                priority: 90
            });
            
            if (duplicateInfo.priority !== 90) {
                throw new Error('Duplicate registration replacement failed');
            }
            
            // Test component state tracking
            const state = this.testCoordinator.getComponentState('MockPhaseDisplay');
            if (state !== 'registered') {
                throw new Error('Component state tracking failed');
            }
            
            this.testResults.push({
                test: 'Component Registration',
                status: 'PASSED',
                timestamp: new Date()
            });
            
        } catch (error) {
            this.testResults.push({
                test: 'Component Registration',
                status: 'FAILED',
                error: error.message,
                timestamp: new Date()
            });
        }
    }
    
    async testEventCoordination() {
        console.log('🎯 Testing event coordination...');
        
        try {
            // Register multiple components
            const phaseComponent = this.mockComponents.get('MockPhaseDisplay');
            const progressComponent = this.mockComponents.get('MockProgressDisplay');
            
            this.testCoordinator.registerComponent('MockPhaseDisplay', phaseComponent);
            this.testCoordinator.registerComponent('MockProgressDisplay', progressComponent);
            
            // Set up event listeners to track coordinated events
            let coordinatedEventsReceived = 0;
            
            document.addEventListener('coordinated_phase_start', (event) => {
                coordinatedEventsReceived++;
                phaseComponent.handleEvent(event);
            });
            
            document.addEventListener('coordinated_progress_update', (event) => {
                coordinatedEventsReceived++;
                progressComponent.handleEvent(event);
            });
            
            // Dispatch events that should be coordinated
            document.dispatchEvent(new CustomEvent('phase_start', {
                detail: {
                    phase_name: 'test_phase',
                    phase_description: 'Test phase for coordination'
                }
            }));
            
            document.dispatchEvent(new CustomEvent('progress_update', {
                detail: {
                    operation: 'test_operation',
                    current: 50,
                    total: 100
                }
            }));
            
            // Wait for event processing
            await this.wait(200);
            
            // Verify events were coordinated
            if (coordinatedEventsReceived === 0) {
                throw new Error('No coordinated events received');
            }
            
            // Test event batching
            const batchStartTime = Date.now();
            
            // Send multiple events rapidly
            for (let i = 0; i < 10; i++) {
                document.dispatchEvent(new CustomEvent('progress_update', {
                    detail: {
                        operation: `batch_test_${i}`,
                        current: i * 10,
                        total: 100
                    }
                }));
            }
            
            await this.wait(100);
            
            // Verify batching occurred (events should be processed efficiently)
            const batchEndTime = Date.now();
            const batchDuration = batchEndTime - batchStartTime;
            
            if (batchDuration > 500) { // Should process quickly due to batching
                throw new Error('Event batching not working efficiently');
            }
            
            this.testResults.push({
                test: 'Event Coordination',
                status: 'PASSED',
                timestamp: new Date()
            });
            
        } catch (error) {
            this.testResults.push({
                test: 'Event Coordination',
                status: 'FAILED',
                error: error.message,
                timestamp: new Date()
            });
        }
    }
    
    async testInitializationOrder() {
        console.log('🚀 Testing component initialization order...');
        
        try {
            // Register components with dependencies
            const phaseComponent = this.mockComponents.get('MockPhaseDisplay');
            const progressComponent = this.mockComponents.get('MockProgressDisplay');
            const taskComponent = this.mockComponents.get('MockTaskDisplay');
            
            // Register in reverse priority order to test sorting
            this.testCoordinator.registerComponent('MockTaskDisplay', taskComponent, {
                priority: 60,
                dependencies: []
            });
            
            this.testCoordinator.registerComponent('MockProgressDisplay', progressComponent, {
                priority: 70,
                dependencies: ['MockPhaseDisplay'] // Depends on phase display
            });
            
            this.testCoordinator.registerComponent('MockPhaseDisplay', phaseComponent, {
                priority: 80,
                dependencies: []
            });
            
            // Initialize components
            this.testCoordinator.initializeComponents();
            
            await this.wait(100);
            
            // Verify initialization order
            if (!phaseComponent.initialized) {
                throw new Error('PhaseDisplay component not initialized');
            }
            
            if (!progressComponent.initialized) {
                throw new Error('ProgressDisplay component not initialized (dependency issue)');
            }
            
            if (!taskComponent.initialized) {
                throw new Error('TaskDisplay component not initialized');
            }
            
            // Test dependency handling
            const newComponent = {
                name: 'MockDependentComponent',
                initialized: false,
                init: function() { this.initialized = true; }
            };
            
            this.testCoordinator.registerComponent('MockDependentComponent', newComponent, {
                dependencies: ['NonExistentComponent'] // Should handle gracefully
            });
            
            this.testCoordinator.initializeComponents();
            
            await this.wait(50);
            
            // Component with unmet dependencies should not initialize
            if (newComponent.initialized) {
                throw new Error('Component with unmet dependencies was initialized');
            }
            
            this.testResults.push({
                test: 'Initialization Order',
                status: 'PASSED',
                timestamp: new Date()
            });
            
        } catch (error) {
            this.testResults.push({
                test: 'Initialization Order',
                status: 'FAILED',
                error: error.message,
                timestamp: new Date()
            });
        }
    }
    
    async testComponentCleanup() {
        console.log('🧹 Testing component cleanup...');
        
        try {
            const mockComponent = this.mockComponents.get('MockPhaseDisplay');
            
            // Register and initialize component
            this.testCoordinator.registerComponent('MockPhaseDisplay', mockComponent);
            this.testCoordinator.initializeComponents();
            
            await this.wait(50);
            
            if (!mockComponent.initialized) {
                throw new Error('Component not initialized for cleanup test');
            }
            
            // Test individual component cleanup
            const unregistered = this.testCoordinator.unregisterComponent('MockPhaseDisplay');
            
            if (!unregistered) {
                throw new Error('Component unregistration failed');
            }
            
            if (mockComponent.initialized) {
                throw new Error('Component cleanup method not called');
            }
            
            // Test coordinator destruction
            const testCoordinator2 = new DisplayComponentCoordinator();
            const mockComponent2 = { ...mockComponent, initialized: false };
            
            testCoordinator2.registerComponent('TestComponent', mockComponent2);
            testCoordinator2.initializeComponents();
            
            await this.wait(50);
            
            testCoordinator2.destroy();
            
            // Verify all components cleaned up
            const stats = testCoordinator2.getComponentStatistics();
            if (stats.total > 0) {
                throw new Error('Coordinator destruction did not clean up all components');
            }
            
            this.testResults.push({
                test: 'Component Cleanup',
                status: 'PASSED',
                timestamp: new Date()
            });
            
        } catch (error) {
            this.testResults.push({
                test: 'Component Cleanup',
                status: 'FAILED',
                error: error.message,
                timestamp: new Date()
            });
        }
    }
    
    async testDuplicatePrevention() {
        console.log('🚫 Testing duplicate DOM element prevention...');
        
        try {
            // Create mock components that create DOM elements
            const component1 = {
                name: 'DOMComponent1',
                element: null,
                init: function() {
                    // Check if element already exists
                    let existing = document.getElementById('shared-element');
                    if (existing) {
                        this.element = existing;
                        console.log('DOMComponent1: Using existing element');
                    } else {
                        this.element = document.createElement('div');
                        this.element.id = 'shared-element';
                        this.element.textContent = 'Created by Component1';
                        document.getElementById('coordination-test-container').appendChild(this.element);
                        console.log('DOMComponent1: Created new element');
                    }
                },
                cleanup: function() {
                    // Don't remove shared elements, just disconnect
                    this.element = null;
                }
            };
            
            const component2 = {
                name: 'DOMComponent2',
                element: null,
                init: function() {
                    // Check if element already exists
                    let existing = document.getElementById('shared-element');
                    if (existing) {
                        this.element = existing;
                        console.log('DOMComponent2: Using existing element');
                    } else {
                        this.element = document.createElement('div');
                        this.element.id = 'shared-element';
                        this.element.textContent = 'Created by Component2';
                        document.getElementById('coordination-test-container').appendChild(this.element);
                        console.log('DOMComponent2: Created new element');
                    }
                },
                cleanup: function() {
                    this.element = null;
                }
            };
            
            // Register components
            this.testCoordinator.registerComponent('DOMComponent1', component1, { priority: 80 });
            this.testCoordinator.registerComponent('DOMComponent2', component2, { priority: 70 });
            
            // Initialize components
            this.testCoordinator.initializeComponents();
            
            await this.wait(100);
            
            // Verify only one element exists
            const elements = document.querySelectorAll('#shared-element');
            if (elements.length !== 1) {
                throw new Error(`Expected 1 shared element, found ${elements.length}`);
            }
            
            // Verify both components reference the same element
            if (component1.element !== component2.element) {
                throw new Error('Components do not share the same DOM element');
            }
            
            // Verify the element was created by the higher priority component
            if (elements[0].textContent !== 'Created by Component1') {
                throw new Error('Element not created by correct component');
            }
            
            this.testResults.push({
                test: 'Duplicate Prevention',
                status: 'PASSED',
                timestamp: new Date()
            });
            
        } catch (error) {
            this.testResults.push({
                test: 'Duplicate Prevention',
                status: 'FAILED',
                error: error.message,
                timestamp: new Date()
            });
        }
    }
    
    async testStateManagement() {
        console.log('📊 Testing component state management...');
        
        try {
            const mockComponent = this.mockComponents.get('MockPhaseDisplay');
            
            // Register component
            this.testCoordinator.registerComponent('MockPhaseDisplay', mockComponent);
            
            // Test initial state
            let state = this.testCoordinator.getComponentState('MockPhaseDisplay');
            if (state !== 'registered') {
                throw new Error('Initial state incorrect');
            }
            
            // Initialize component
            this.testCoordinator.initializeComponents();
            await this.wait(50);
            
            // Test initialized state
            state = this.testCoordinator.getComponentState('MockPhaseDisplay');
            if (state !== 'initialized') {
                throw new Error('Initialized state not set');
            }
            
            // Test state change events
            let stateChangeReceived = false;
            document.addEventListener('component_state_changed', (event) => {
                if (event.detail.name === 'MockPhaseDisplay') {
                    stateChangeReceived = true;
                }
            });
            
            // Manually set state to test event emission
            this.testCoordinator.setComponentState('MockPhaseDisplay', 'error');
            
            await this.wait(50);
            
            if (!stateChangeReceived) {
                throw new Error('State change event not emitted');
            }
            
            // Test statistics
            const stats = this.testCoordinator.getComponentStatistics();
            if (stats.total !== 1 || stats.error !== 1) {
                throw new Error('Component statistics incorrect');
            }
            
            this.testResults.push({
                test: 'State Management',
                status: 'PASSED',
                timestamp: new Date()
            });
            
        } catch (error) {
            this.testResults.push({
                test: 'State Management',
                status: 'FAILED',
                error: error.message,
                timestamp: new Date()
            });
        }
    }
    
    async testRealComponentIntegration() {
        console.log('🔗 Testing real component integration...');
        
        try {
            // Test with actual display components if available
            if (window.PhaseDisplayManager && window.ProgressDisplayManager) {
                const realCoordinator = new DisplayComponentCoordinator();
                
                // Create real components
                const phaseManager = new window.PhaseDisplayManager();
                const progressManager = new window.ProgressDisplayManager();
                
                // Register with coordinator
                realCoordinator.registerComponent('PhaseDisplayManager', phaseManager, {
                    priority: 80,
                    dependencies: []
                });
                
                realCoordinator.registerComponent('ProgressDisplayManager', progressManager, {
                    priority: 70,
                    dependencies: ['PhaseDisplayManager']
                });
                
                // Initialize
                realCoordinator.initializeComponents();
                
                await this.wait(100);
                
                // Test coordinated event
                document.dispatchEvent(new CustomEvent('phase_start', {
                    detail: {
                        phase_name: 'integration_test',
                        phase_description: 'Real component integration test'
                    }
                }));
                
                await this.wait(100);
                
                // Verify components received events
                const stats = realCoordinator.getComponentStatistics();
                if (stats.initialized < 2) {
                    throw new Error('Real components not properly initialized');
                }
                
                // Cleanup
                realCoordinator.destroy();
            }
            
            this.testResults.push({
                test: 'Real Component Integration',
                status: 'PASSED',
                timestamp: new Date()
            });
            
        } catch (error) {
            this.testResults.push({
                test: 'Real Component Integration',
                status: 'FAILED',
                error: error.message,
                timestamp: new Date()
            });
        }
    }
    
    async testCoordinationPerformance() {
        console.log('⚡ Testing coordination performance...');
        
        try {
            const startTime = performance.now();
            
            // Register many components
            for (let i = 0; i < 50; i++) {
                const mockComponent = {
                    name: `PerfTestComponent${i}`,
                    initialized: false,
                    events: [],
                    init: function() { this.initialized = true; },
                    cleanup: function() { this.initialized = false; }
                };
                
                this.testCoordinator.registerComponent(`PerfTestComponent${i}`, mockComponent, {
                    priority: Math.random() * 100,
                    dependencies: i > 0 ? [`PerfTestComponent${i-1}`] : []
                });
            }
            
            // Initialize all components
            this.testCoordinator.initializeComponents();
            
            await this.wait(100);
            
            // Send many coordinated events
            for (let i = 0; i < 100; i++) {
                document.dispatchEvent(new CustomEvent('phase_start', {
                    detail: {
                        phase_name: `perf_test_${i}`,
                        phase_description: `Performance test phase ${i}`
                    }
                }));
            }
            
            await this.wait(200);
            
            const endTime = performance.now();
            const duration = endTime - startTime;
            
            console.log(`⚡ Coordination performance test completed in ${duration.toFixed(2)}ms`);
            
            // Verify all components initialized
            const stats = this.testCoordinator.getComponentStatistics();
            if (stats.initialized !== 50) {
                throw new Error(`Expected 50 initialized components, got ${stats.initialized}`);
            }
            
            // Performance threshold
            if (duration > 2000) { // 2 seconds
                throw new Error('Coordination performance too slow');
            }
            
            this.testResults.push({
                test: 'Coordination Performance',
                status: 'PASSED',
                duration: duration,
                timestamp: new Date()
            });
            
        } catch (error) {
            this.testResults.push({
                test: 'Coordination Performance',
                status: 'FAILED',
                error: error.message,
                timestamp: new Date()
            });
        }
    }
    
    async testErrorHandling() {
        console.log('🚨 Testing error handling...');
        
        try {
            // Test component with failing init
            const failingComponent = {
                name: 'FailingComponent',
                init: function() {
                    throw new Error('Intentional init failure');
                },
                cleanup: function() {}
            };
            
            this.testCoordinator.registerComponent('FailingComponent', failingComponent);
            
            // Should not crash the coordinator
            this.testCoordinator.initializeComponents();
            
            await this.wait(50);
            
            // Component should be in error state
            const state = this.testCoordinator.getComponentState('FailingComponent');
            if (state !== 'error') {
                throw new Error('Failing component not marked as error');
            }
            
            // Test invalid component registration
            try {
                this.testCoordinator.registerComponent(null, null);
                // Should handle gracefully
            } catch (error) {
                // Expected to handle gracefully, not crash
            }
            
            // Test event coordination with missing components
            document.dispatchEvent(new CustomEvent('phase_start', {
                detail: null // Invalid data
            }));
            
            await this.wait(50);
            
            // Should not crash
            
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
    
    generateTestReport() {
        console.log('📊 Generating component coordination test report...');
        
        const totalTests = this.testResults.length;
        const passedTests = this.testResults.filter(r => r.status === 'PASSED').length;
        const failedTests = this.testResults.filter(r => r.status === 'FAILED').length;
        
        console.log(`
🧪 Component Coordination Test Results:`);
        console.log(`   Total Tests: ${totalTests}`);
        console.log(`   Passed: ${passedTests}`);
        console.log(`   Failed: ${failedTests}`);
        console.log(`   Success Rate: ${((passedTests / totalTests) * 100).toFixed(1)}%`);
        
        if (failedTests > 0) {
            console.log(`
❌ Failed Tests:`);
            this.testResults.filter(r => r.status === 'FAILED').forEach(result => {
                console.log(`   - ${result.test}: ${result.error}`);
            });
        }
        
        console.log(`
✅ Passed Tests:`);
        this.testResults.filter(r => r.status === 'PASSED').forEach(result => {
            const duration = result.duration ? ` (${result.duration.toFixed(2)}ms)` : '';
            console.log(`   - ${result.test}${duration}`);
        });
        
        // Create visual test report
        this.createVisualTestReport();
    }
    
    createVisualTestReport() {
        const reportContainer = document.createElement('div');
        reportContainer.id = 'coordination-test-report';
        reportContainer.style.cssText = `
            position: fixed;
            top: 20px;
            right: 20px;
            width: 400px;
            max-height: 600px;
            background: var(--glass-bg-primary, rgba(255, 255, 255, 0.1));
            border: 1px solid var(--glass-border-primary, rgba(255, 255, 255, 0.2));
            border-radius: 12px;
            padding: 20px;
            z-index: 10000;
            backdrop-filter: blur(10px);
            overflow-y: auto;
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
            color: var(--text-primary, #333);
        `;
        
        const totalTests = this.testResults.length;
        const passedTests = this.testResults.filter(r => r.status === 'PASSED').length;
        const failedTests = this.testResults.filter(r => r.status === 'FAILED').length;
        const successRate = ((passedTests / totalTests) * 100).toFixed(1);
        
        reportContainer.innerHTML = `
            <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 16px;">
                <h3 style="margin: 0; color: var(--text-primary, #333);">Component Coordination Tests</h3>
                <button id="close-test-report" style="background: none; border: none; font-size: 18px; cursor: pointer; color: var(--text-tertiary, #666);">×</button>
            </div>
            
            <div style="margin-bottom: 20px;">
                <div style="display: flex; justify-content: space-between; margin-bottom: 8px;">
                    <span>Success Rate</span>
                    <span style="font-weight: 600; color: ${successRate >= 90 ? '#10b981' : successRate >= 70 ? '#f59e0b' : '#ef4444'};">${successRate}%</span>
                </div>
                <div style="background: rgba(0,0,0,0.1); height: 8px; border-radius: 4px; overflow: hidden;">
                    <div style="background: ${successRate >= 90 ? '#10b981' : successRate >= 70 ? '#f59e0b' : '#ef4444'}; height: 100%; width: ${successRate}%; transition: width 0.3s ease;"></div>
                </div>
            </div>
            
            <div style="display: grid; grid-template-columns: 1fr 1fr 1fr; gap: 12px; margin-bottom: 20px; text-align: center;">
                <div style="padding: 12px; background: rgba(16, 185, 129, 0.1); border-radius: 8px;">
                    <div style="font-size: 24px; font-weight: 600; color: #10b981;">${passedTests}</div>
                    <div style="font-size: 12px; color: var(--text-secondary, #666);">Passed</div>
                </div>
                <div style="padding: 12px; background: rgba(239, 68, 68, 0.1); border-radius: 8px;">
                    <div style="font-size: 24px; font-weight: 600; color: #ef4444;">${failedTests}</div>
                    <div style="font-size: 12px; color: var(--text-secondary, #666);">Failed</div>
                </div>
                <div style="padding: 12px; background: rgba(107, 114, 128, 0.1); border-radius: 8px;">
                    <div style="font-size: 24px; font-weight: 600; color: #6b7280;">${totalTests}</div>
                    <div style="font-size: 12px; color: var(--text-secondary, #666);">Total</div>
                </div>
            </div>
            
            <div style="max-height: 300px; overflow-y: auto;">
                ${this.testResults.map(result => `
                    <div style="display: flex; align-items: center; padding: 8px 0; border-bottom: 1px solid rgba(255,255,255,0.1);">
                        <div style="width: 20px; height: 20px; border-radius: 50%; background: ${result.status === 'PASSED' ? '#10b981' : '#ef4444'}; display: flex; align-items: center; justify-content: center; margin-right: 12px;">
                            <span style="color: white; font-size: 12px;">${result.status === 'PASSED' ? '✓' : '✗'}</span>
                        </div>
                        <div style="flex: 1;">
                            <div style="font-weight: 500; color: var(--text-primary, #333);">${result.test}</div>
                            ${result.error ? `<div style="font-size: 12px; color: #ef4444; margin-top: 2px;">${result.error}</div>` : ''}
                            ${result.duration ? `<div style="font-size: 12px; color: var(--text-tertiary, #666); margin-top: 2px;">${result.duration.toFixed(2)}ms</div>` : ''}
                        </div>
                    </div>
                `).join('')}
            </div>
        `;
        
        document.body.appendChild(reportContainer);
        
        // Add close functionality
        document.getElementById('close-test-report').addEventListener('click', () => {
            reportContainer.remove();
        });
        
        // Auto-remove after 30 seconds
        setTimeout(() => {
            if (document.body.contains(reportContainer)) {
                reportContainer.remove();
            }
        }, 30000);
    }
    
    async cleanupTestEnvironment() {
        console.log('🧹 Cleaning up component coordination test environment...');
        
        // Cleanup test coordinator
        if (this.testCoordinator) {
            this.testCoordinator.destroy();
            this.testCoordinator = null;
        }
        
        // Remove test DOM
        const testContainer = document.getElementById('coordination-test-container');
        if (testContainer) {
            testContainer.remove();
        }
        
        // Clear mock components
        this.mockComponents.clear();
        
        // Restore original coordinator if needed
        if (this.originalCoordinator) {
            window.displayCoordinator = this.originalCoordinator;
        }
    }
    
    // Utility method for waiting
    wait(ms) {
        return new Promise(resolve => setTimeout(resolve, ms));
    }
}

// Make globally available for testing
window.ComponentCoordinationTestSuite = ComponentCoordinationTestSuite;

// Auto-run tests if in test mode
if (window.location.search.includes('test=coordination') || window.location.hash.includes('test-coordination')) {
    document.addEventListener('DOMContentLoaded', async () => {
        console.log('🧪 Auto-running component coordination tests...');
        const testSuite = new ComponentCoordinationTestSuite();
        await testSuite.runAllTests();
    });
}