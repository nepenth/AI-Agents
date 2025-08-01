/**
 * Test Suite for Enhanced SocketIO Manager
 * 
 * Comprehensive tests for the enhanced SocketIO client functionality
 * including event validation, reconnection, buffering, and error handling.
 */

class EnhancedSocketIOManagerTester {
    constructor() {
        this.testResults = [];
        this.mockSocket = null;
        this.manager = null;
    }
    
    async runAllTests() {
        console.log('🧪 Starting Enhanced SocketIO Manager Test Suite...');
        
        const tests = [
            this.testInitialization,
            this.testEventValidation,
            this.testEventHandling,
            this.testBatchEventHandling,
            this.testConnectionManagement,
            this.testReconnectionLogic,
            this.testEventBuffering,
            this.testHeartbeat,
            this.testStatusCallbacks,
            this.testErrorHandling
        ];
        
        for (const test of tests) {
            try {
                await test.call(this);
            } catch (error) {
                this.addTestResult(test.name, false, `Test threw error: ${error.message}`);
            }
        }
        
        this.displayResults();
        return this.getTestSummary();
    }
    
    setupMockSocket() {
        this.mockSocket = {
            id: 'mock-socket-id',
            connected: false,
            disconnected: true,
            on: jest.fn ? jest.fn() : function(event, handler) {
                this._handlers = this._handlers || {};
                this._handlers[event] = this._handlers[event] || [];
                this._handlers[event].push(handler);
            },
            emit: jest.fn ? jest.fn() : function(event, data) {
                console.log(`Mock emit: ${event}`, data);
            },
            disconnect: jest.fn ? jest.fn() : function() {
                this.connected = false;
                this.disconnected = true;
            },
            _trigger: function(event, data) {
                if (this._handlers && this._handlers[event]) {
                    this._handlers[event].forEach(handler => handler(data));
                }
            }
        };
        
        // Mock window.io
        window.io = () => this.mockSocket;
    }
    
    testInitialization() {
        console.log('🔍 Testing initialization...');
        
        this.setupMockSocket();
        
        try {
            this.manager = new EnhancedSocketIOManager({
                autoConnect: false,
                maxReconnectAttempts: 3
            });
            
            // Check initial state
            if (!this.manager.validator) {
                throw new Error('Validator not initialized');
            }
            
            if (this.manager.isConnected) {
                throw new Error('Should not be connected initially with autoConnect: false');
            }
            
            const status = this.manager.getStatus();
            if (!status || typeof status.isConnected !== 'boolean') {
                throw new Error('Invalid status object');
            }
            
            this.addTestResult('testInitialization', true, 'Manager initialized correctly');
            
        } catch (error) {
            this.addTestResult('testInitialization', false, error.message);
        }
    }
    
    testEventValidation() {
        console.log('🔍 Testing event validation...');
        
        try {
            const validator = new SocketEventValidator();
            
            // Test valid log event
            const validLog = {
                message: 'Test log message',
                level: 'INFO'
            };
            
            const logResult = validator.validateEvent('log', validLog);
            if (!logResult.isValid) {
                throw new Error(`Valid log event failed validation: ${logResult.error}`);
            }
            
            // Test invalid phase event
            const invalidPhase = {
                phase_id: 'test_phase',
                status: 'invalid_status'
            };
            
            const phaseResult = validator.validateEvent('phase_update', invalidPhase);
            if (phaseResult.isValid) {
                throw new Error('Invalid phase event should fail validation');
            }
            
            // Test progress event with percentage calculation
            const progressEvent = {
                processed_count: 7,
                total_count: 10
            };
            
            const progressResult = validator.validateEvent('progress_update', progressEvent);
            if (!progressResult.isValid) {
                throw new Error(`Valid progress event failed validation: ${progressResult.error}`);
            }
            
            if (progressResult.sanitizedData.percentage !== 70) {
                throw new Error(`Incorrect percentage calculation: ${progressResult.sanitizedData.percentage}`);
            }
            
            this.addTestResult('testEventValidation', true, 'Event validation working correctly');
            
        } catch (error) {
            this.addTestResult('testEventValidation', false, error.message);
        }
    }
    
    testEventHandling() {
        console.log('🔍 Testing event handling...');
        
        try {
            if (!this.manager) {
                throw new Error('Manager not initialized');
            }
            
            let receivedEvent = null;
            let receivedData = null;
            
            // Register event handler
            const unsubscribe = this.manager.on('test_event', (data, eventName) => {
                receivedEvent = eventName;
                receivedData = data;
            });
            
            // Simulate incoming event
            this.manager.handleIncomingEvent('test_event', { test: 'data' });
            
            if (receivedEvent !== 'test_event') {
                throw new Error(`Expected 'test_event', got '${receivedEvent}'`);
            }
            
            if (!receivedData || receivedData.test !== 'data') {
                throw new Error('Event data not received correctly');
            }
            
            // Test unsubscribe
            unsubscribe();
            receivedEvent = null;
            
            this.manager.handleIncomingEvent('test_event', { test: 'data2' });
            
            if (receivedEvent !== null) {
                throw new Error('Event handler not unsubscribed correctly');
            }
            
            this.addTestResult('testEventHandling', true, 'Event handling working correctly');
            
        } catch (error) {
            this.addTestResult('testEventHandling', false, error.message);
        }
    }
    
    testBatchEventHandling() {
        console.log('🔍 Testing batch event handling...');
        
        try {
            if (!this.manager) {
                throw new Error('Manager not initialized');
            }
            
            const receivedEvents = [];
            
            // Register event handler
            this.manager.on('log', (data) => {
                receivedEvents.push(data);
            });
            
            // Simulate batch event
            const batchData = {
                events: [
                    { message: 'Log 1', level: 'INFO' },
                    { message: 'Log 2', level: 'WARNING' },
                    { message: 'Log 3', level: 'ERROR' }
                ],
                count: 3
            };
            
            this.manager.handleBatchEvent('log', batchData);
            
            if (receivedEvents.length !== 3) {
                throw new Error(`Expected 3 events, got ${receivedEvents.length}`);
            }
            
            if (receivedEvents[0].message !== 'Log 1') {
                throw new Error('First batch event not processed correctly');
            }
            
            this.addTestResult('testBatchEventHandling', true, 'Batch event handling working correctly');
            
        } catch (error) {
            this.addTestResult('testBatchEventHandling', false, error.message);
        }
    }
    
    testConnectionManagement() {
        console.log('🔍 Testing connection management...');
        
        try {
            if (!this.manager) {
                throw new Error('Manager not initialized');
            }
            
            // Test initial state
            if (this.manager.isConnected) {
                throw new Error('Should not be connected initially');
            }
            
            // Simulate connection
            this.manager.isConnected = false;
            this.manager.handleConnect();
            
            if (!this.manager.isConnected) {
                throw new Error('Should be connected after handleConnect');
            }
            
            if (this.manager.isConnecting) {
                throw new Error('Should not be connecting after successful connection');
            }
            
            // Simulate disconnection
            this.manager.handleDisconnect('transport close');
            
            if (this.manager.isConnected) {
                throw new Error('Should not be connected after disconnect');
            }
            
            this.addTestResult('testConnectionManagement', true, 'Connection management working correctly');
            
        } catch (error) {
            this.addTestResult('testConnectionManagement', false, error.message);
        }
    }
    
    testReconnectionLogic() {
        console.log('🔍 Testing reconnection logic...');
        
        try {
            if (!this.manager) {
                throw new Error('Manager not initialized');
            }
            
            // Reset connection attempts
            this.manager.connectionAttempts = 0;
            
            // Test reconnection scheduling
            this.manager.scheduleReconnection();
            
            if (!this.manager.reconnectTimer) {
                throw new Error('Reconnection timer not set');
            }
            
            // Test max attempts
            this.manager.connectionAttempts = this.manager.options.maxReconnectAttempts;
            
            // Clear existing timer
            if (this.manager.reconnectTimer) {
                clearTimeout(this.manager.reconnectTimer);
                this.manager.reconnectTimer = null;
            }
            
            this.manager.scheduleReconnection();
            
            if (this.manager.reconnectTimer) {
                throw new Error('Should not schedule reconnection after max attempts');
            }
            
            this.addTestResult('testReconnectionLogic', true, 'Reconnection logic working correctly');
            
        } catch (error) {
            this.addTestResult('testReconnectionLogic', false, error.message);
        }
    }
    
    testEventBuffering() {
        console.log('🔍 Testing event buffering...');
        
        try {
            if (!this.manager) {
                throw new Error('Manager not initialized');
            }
            
            // Ensure not connected
            this.manager.isConnected = false;
            
            // Buffer some events
            this.manager.bufferEvent('test_event', { data: 1 });
            this.manager.bufferEvent('test_event', { data: 2 });
            
            if (this.manager.eventBuffer.length !== 2) {
                throw new Error(`Expected 2 buffered events, got ${this.manager.eventBuffer.length}`);
            }
            
            // Test buffer processing
            const receivedEvents = [];
            this.manager.on('test_event', (data) => {
                receivedEvents.push(data);
            });
            
            this.manager.processBufferedEvents();
            
            if (receivedEvents.length !== 2) {
                throw new Error(`Expected 2 processed events, got ${receivedEvents.length}`);
            }
            
            if (this.manager.eventBuffer.length !== 0) {
                throw new Error('Event buffer should be empty after processing');
            }
            
            this.addTestResult('testEventBuffering', true, 'Event buffering working correctly');
            
        } catch (error) {
            this.addTestResult('testEventBuffering', false, error.message);
        }
    }
    
    testHeartbeat() {
        console.log('🔍 Testing heartbeat functionality...');
        
        try {
            if (!this.manager) {
                throw new Error('Manager not initialized');
            }
            
            // Test heartbeat start
            this.manager.startHeartbeat();
            
            if (!this.manager.heartbeatTimer) {
                throw new Error('Heartbeat timer not started');
            }
            
            // Test heartbeat stop
            this.manager.stopHeartbeat();
            
            if (this.manager.heartbeatTimer) {
                throw new Error('Heartbeat timer not stopped');
            }
            
            // Test heartbeat handling
            this.manager.handleHeartbeat();
            // Should not throw error
            
            this.addTestResult('testHeartbeat', true, 'Heartbeat functionality working correctly');
            
        } catch (error) {
            this.addTestResult('testHeartbeat', false, error.message);
        }
    }
    
    testStatusCallbacks() {
        console.log('🔍 Testing status callbacks...');
        
        try {
            if (!this.manager) {
                throw new Error('Manager not initialized');
            }
            
            let receivedStatus = null;
            
            // Register status callback
            const unsubscribe = this.manager.onStatusChange((status) => {
                receivedStatus = status;
            });
            
            // Trigger status change
            this.manager.notifyStatusChange('connected', 'Test connection');
            
            if (!receivedStatus) {
                throw new Error('Status callback not called');
            }
            
            if (receivedStatus.status !== 'connected') {
                throw new Error(`Expected 'connected', got '${receivedStatus.status}'`);
            }
            
            if (receivedStatus.message !== 'Test connection') {
                throw new Error(`Expected 'Test connection', got '${receivedStatus.message}'`);
            }
            
            // Test unsubscribe
            unsubscribe();
            receivedStatus = null;
            
            this.manager.notifyStatusChange('disconnected', 'Test disconnect');
            
            if (receivedStatus !== null) {
                throw new Error('Status callback not unsubscribed correctly');
            }
            
            this.addTestResult('testStatusCallbacks', true, 'Status callbacks working correctly');
            
        } catch (error) {
            this.addTestResult('testStatusCallbacks', false, error.message);
        }
    }
    
    testErrorHandling() {
        console.log('🔍 Testing error handling...');
        
        try {
            if (!this.manager) {
                throw new Error('Manager not initialized');
            }
            
            // Test connection error handling
            const testError = new Error('Test connection error');
            this.manager.handleConnectionError(testError);
            
            if (this.manager.isConnecting) {
                throw new Error('Should not be connecting after error');
            }
            
            if (this.manager.eventStats.errors === 0) {
                throw new Error('Error count not incremented');
            }
            
            // Test invalid event handling
            const initialErrors = this.manager.eventStats.errors;
            
            // This should increment error count due to validation failure
            this.manager.handleIncomingEvent('phase_update', {
                phase_id: 'test',
                status: 'invalid_status'
            });
            
            if (this.manager.eventStats.errors <= initialErrors) {
                throw new Error('Error count not incremented for invalid event');
            }
            
            this.addTestResult('testErrorHandling', true, 'Error handling working correctly');
            
        } catch (error) {
            this.addTestResult('testErrorHandling', false, error.message);
        }
    }
    
    addTestResult(testName, passed, message) {
        this.testResults.push({
            test: testName,
            passed,
            message,
            timestamp: new Date().toISOString()
        });
        
        const status = passed ? '✅' : '❌';
        console.log(`${status} ${testName}: ${message}`);
    }
    
    displayResults() {
        console.log('\
📊 Test Results Summary:');
        console.log('=' .repeat(50));
        
        const passed = this.testResults.filter(r => r.passed).length;
        const total = this.testResults.length;
        
        console.log(`Total Tests: ${total}`);
        console.log(`Passed: ${passed}`);
        console.log(`Failed: ${total - passed}`);
        console.log(`Success Rate: ${((passed / total) * 100).toFixed(1)}%`);
        
        console.log('\
📋 Detailed Results:');
        this.testResults.forEach(result => {
            const status = result.passed ? '✅' : '❌';
            console.log(`${status} ${result.test}: ${result.message}`);
        });
        
        if (passed === total) {
            console.log('\
🎉 All tests passed! Enhanced SocketIO Manager is working correctly.');
        } else {
            console.log(`\
⚠️ ${total - passed} test(s) failed. Please review the implementation.`);
        }
    }
    
    getTestSummary() {
        const passed = this.testResults.filter(r => r.passed).length;
        const total = this.testResults.length;
        
        return {
            total,
            passed,
            failed: total - passed,
            successRate: (passed / total) * 100,
            allPassed: passed === total,
            results: this.testResults
        };
    }
}

// Auto-run tests if this script is loaded directly
if (typeof window !== 'undefined' && window.EnhancedSocketIOManager) {
    // Wait for DOM to be ready
    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', () => {
            const tester = new EnhancedSocketIOManagerTester();
            tester.runAllTests();
        });
    } else {
        const tester = new EnhancedSocketIOManagerTester();
        tester.runAllTests();
    }
}

// Export for use in other modules
if (typeof module !== 'undefined' && module.exports) {
    module.exports = EnhancedSocketIOManagerTester;
} else {
    window.EnhancedSocketIOManagerTester = EnhancedSocketIOManagerTester;
}"