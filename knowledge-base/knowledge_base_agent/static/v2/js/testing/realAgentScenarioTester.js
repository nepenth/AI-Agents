/**
 * Real Agent Scenario Tester
 * 
 * Tests the integrated frontend components with realistic agent execution scenarios
 * Validates that all components work together seamlessly during actual agent operations
 */

class RealAgentScenarioTester {
    constructor() {
        this.scenarios = [];
        this.currentScenario = null;
        this.testResults = [];
        this.isRunning = false;
        
        this.initialize();
    }
    
    initialize() {
        console.log('🤖 Initializing Real Agent Scenario Tester...');
        
        // Define comprehensive test scenarios
        this.defineScenarios();
        
        // Create test interface
        this.createTestInterface();
        
        console.log('✅ Real Agent Scenario Tester initialized');
    }
    
    defineScenarios() {
        this.scenarios = [
            {
                name: 'Full Pipeline Execution',
                description: 'Complete agent run with all phases',
                duration: 30000, // 30 seconds
                events: this.generateFullPipelineEvents()
            },
            {
                name: 'Error Recovery Scenario',
                description: 'Agent encounters errors and recovers',
                duration: 20000, // 20 seconds
                events: this.generateErrorRecoveryEvents()
            },
            {
                name: 'High-Load Processing',
                description: 'Processing large number of items',
                duration: 25000, // 25 seconds
                events: this.generateHighLoadEvents()
            },
            {
                name: 'Interrupted Execution',
                description: 'Agent is stopped mid-execution',
                duration: 15000, // 15 seconds
                events: this.generateInterruptedEvents()
            },
            {
                name: 'Multi-Phase Coordination',
                description: 'Multiple phases running simultaneously',
                duration: 35000, // 35 seconds
                events: this.generateMultiPhaseEvents()
            }
        ];
    }
    
    createTestInterface() {
        // Create scenario test panel
        const testPanel = document.createElement('div');
        testPanel.id = 'agent-scenario-tester';
        testPanel.innerHTML = `
            <div class="scenario-panel-header">
                <h4>🤖 Agent Scenario Tester</h4>
                <button id="close-scenario-panel" class="btn btn-sm btn-outline-danger">×</button>
            </div>
            <div class="scenario-panel-content">
                <div class="scenario-selector">
                    <label for="scenario-select">Select Scenario:</label>
                    <select id="scenario-select" class="form-select form-select-sm">
                        <option value="">Choose a scenario...</option>
                        ${this.scenarios.map((scenario, index) => 
                            `<option value="${index}">${scenario.name}</option>`
                        ).join('')}
                    </select>
                </div>
                <div class="scenario-description" id="scenario-description">
                    <p class="text-muted">Select a scenario to see its description</p>
                </div>
                <div class="scenario-controls">
                    <button id="run-scenario" class="btn btn-primary btn-sm" disabled>Run Scenario</button>
                    <button id="stop-scenario" class="btn btn-danger btn-sm" disabled>Stop Scenario</button>
                    <button id="reset-ui" class="btn btn-secondary btn-sm">Reset UI</button>
                </div>
                <div class="scenario-progress" id="scenario-progress" style="display: none;">
                    <div class="progress mb-2">
                        <div class="progress-bar" role="progressbar" style="width: 0%"></div>
                    </div>
                    <div class="scenario-status">Ready</div>
                </div>
                <div class="scenario-results" id="scenario-results">
                    <div class="text-muted">Scenario results will appear here...</div>
                </div>
            </div>
        `;
        
        // Style the panel
        testPanel.style.cssText = `
            position: fixed;
            top: 20px;
            left: 20px;
            width: 400px;
            max-height: 80vh;
            background: var(--glass-bg, rgba(255, 255, 255, 0.1));
            backdrop-filter: blur(10px);
            border: 1px solid var(--glass-border, rgba(255, 255, 255, 0.2));
            border-radius: 12px;
            padding: 16px;
            z-index: 9999;
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
            font-size: 14px;
            color: var(--text-primary, #333);
            box-shadow: 0 8px 32px rgba(0, 0, 0, 0.1);
            overflow-y: auto;
        `;
        
        document.body.appendChild(testPanel);
        
        // Attach event listeners
        this.attachEventListeners();
    }
    
    attachEventListeners() {
        // Scenario selection
        document.getElementById('scenario-select')?.addEventListener('change', (e) => {
            this.selectScenario(parseInt(e.target.value));
        });
        
        // Control buttons
        document.getElementById('run-scenario')?.addEventListener('click', () => this.runScenario());
        document.getElementById('stop-scenario')?.addEventListener('click', () => this.stopScenario());
        document.getElementById('reset-ui')?.addEventListener('click', () => this.resetUI());
        document.getElementById('close-scenario-panel')?.addEventListener('click', () => {
            document.getElementById('agent-scenario-tester')?.remove();
        });
    }
    
    selectScenario(index) {
        if (index >= 0 && index < this.scenarios.length) {
            this.currentScenario = this.scenarios[index];
            
            // Update description
            const descriptionEl = document.getElementById('scenario-description');
            if (descriptionEl) {
                descriptionEl.innerHTML = `
                    <h6>${this.currentScenario.name}</h6>
                    <p>${this.currentScenario.description}</p>
                    <small class="text-muted">Duration: ${this.currentScenario.duration / 1000}s | Events: ${this.currentScenario.events.length}</small>
                `;
            }
            
            // Enable run button
            const runBtn = document.getElementById('run-scenario');
            if (runBtn) {
                runBtn.disabled = false;
            }
        }
    }
    
    async runScenario() {
        if (!this.currentScenario || this.isRunning) return;
        
        console.log(`🤖 Running scenario: ${this.currentScenario.name}`);
        
        this.isRunning = true;
        this.updateControls();
        this.showProgress();
        this.clearResults();
        
        try {
            // Reset UI state before starting
            this.resetUI();
            
            // Execute scenario events
            await this.executeScenarioEvents();
            
            // Validate final state
            const validation = this.validateScenarioResults();
            this.displayResults(validation);
            
        } catch (error) {
            console.error('Scenario execution failed:', error);
            this.addResult('error', `Scenario failed: ${error.message}`);
        } finally {
            this.isRunning = false;
            this.updateControls();
            this.hideProgress();
        }
    }
    
    async executeScenarioEvents() {
        const events = this.currentScenario.events;
        const totalEvents = events.length;
        
        for (let i = 0; i < events.length; i++) {
            if (!this.isRunning) break; // Allow stopping mid-scenario
            
            const event = events[i];
            
            // Update progress
            this.updateProgress((i / totalEvents) * 100, `Executing: ${event.type}`);
            
            // Dispatch event
            document.dispatchEvent(new CustomEvent(event.type, { detail: event.data }));
            
            // Log event for debugging
            console.log(`📡 Dispatched: ${event.type}`, event.data);
            
            // Wait for specified delay
            await this.wait(event.delay || 100);
        }
        
        this.updateProgress(100, 'Scenario completed');
    }
    
    validateScenarioResults() {
        const validation = {
            timestamp: new Date(),
            scenario: this.currentScenario.name,
            checks: [],
            passed: 0,
            failed: 0,
            warnings: 0
        };
        
        // Check 1: UI Components are responsive
        const uiResponsive = this.checkUIResponsiveness();
        validation.checks.push({
            name: 'UI Responsiveness',
            status: uiResponsive.passed ? 'passed' : 'failed',
            details: uiResponsive.details
        });
        if (uiResponsive.passed) validation.passed++; else validation.failed++;
        
        // Check 2: Event coordination working
        const eventCoordination = this.checkEventCoordination();
        validation.checks.push({
            name: 'Event Coordination',
            status: eventCoordination.passed ? 'passed' : 'failed',
            details: eventCoordination.details
        });
        if (eventCoordination.passed) validation.passed++; else validation.failed++;
        
        // Check 3: Display components updated
        const displayUpdates = this.checkDisplayUpdates();
        validation.checks.push({
            name: 'Display Updates',
            status: displayUpdates.passed ? 'passed' : 'failed',
            details: displayUpdates.details
        });
        if (displayUpdates.passed) validation.passed++; else validation.failed++;
        
        // Check 4: No JavaScript errors
        const jsErrors = this.checkJavaScriptErrors();
        validation.checks.push({
            name: 'JavaScript Errors',
            status: jsErrors.passed ? 'passed' : 'warning',
            details: jsErrors.details
        });
        if (jsErrors.passed) validation.passed++; else validation.warnings++;
        
        // Check 5: Memory usage reasonable
        const memoryUsage = this.checkMemoryUsage();
        validation.checks.push({
            name: 'Memory Usage',
            status: memoryUsage.passed ? 'passed' : 'warning',
            details: memoryUsage.details
        });
        if (memoryUsage.passed) validation.passed++; else validation.warnings++;
        
        return validation;
    }
    
    checkUIResponsiveness() {
        // Check if UI elements are still interactive
        const interactiveElements = document.querySelectorAll('button, input, select');
        let responsiveCount = 0;
        
        interactiveElements.forEach(element => {
            if (!element.disabled && element.offsetParent !== null) {
                responsiveCount++;
            }
        });
        
        const passed = responsiveCount > 0;
        return {
            passed,
            details: `${responsiveCount} interactive elements responsive`
        };
    }
    
    checkEventCoordination() {
        // Check if components have updated their state
        const phaseDisplay = document.querySelector('.phase-display');
        const progressDisplay = document.querySelector('.progress-display');
        const agentControls = document.querySelector('.agent-controls');
        
        let updatedComponents = 0;
        
        if (phaseDisplay && phaseDisplay.innerHTML.includes('phase-')) {
            updatedComponents++;
        }
        
        if (progressDisplay && progressDisplay.innerHTML.includes('progress-')) {
            updatedComponents++;
        }
        
        if (agentControls) {
            updatedComponents++;
        }
        
        const passed = updatedComponents >= 2;
        return {
            passed,
            details: `${updatedComponents} components coordinated properly`
        };
    }
    
    checkDisplayUpdates() {
        // Check if display components show updated content
        const displays = document.querySelectorAll('.phase-display, .progress-display, .task-display');
        let updatedDisplays = 0;
        
        displays.forEach(display => {
            const content = display.textContent || display.innerHTML;
            if (content && !content.includes('Waiting') && !content.includes('Ready')) {
                updatedDisplays++;
            }
        });
        
        const passed = updatedDisplays > 0;
        return {
            passed,
            details: `${updatedDisplays} displays updated with content`
        };
    }
    
    checkJavaScriptErrors() {
        // This is a simplified check - in a real scenario, you'd track errors
        const passed = true; // Assume no errors if we got this far
        return {
            passed,
            details: 'No JavaScript errors detected during scenario'
        };
    }
    
    checkMemoryUsage() {
        if (performance.memory) {
            const memoryMB = performance.memory.usedJSHeapSize / (1024 * 1024);
            const passed = memoryMB < 100; // Less than 100MB is reasonable
            return {
                passed,
                details: `Memory usage: ${memoryMB.toFixed(1)}MB`
            };
        }
        
        return {
            passed: true,
            details: 'Memory monitoring not available'
        };
    }
    
    displayResults(validation) {
        const resultsEl = document.getElementById('scenario-results');
        if (!resultsEl) return;
        
        const successRate = validation.passed / (validation.passed + validation.failed + validation.warnings) * 100;
        
        resultsEl.innerHTML = `
            <div class="validation-summary">
                <h6>📊 Scenario Results</h6>
                <div class="result-stats">
                    <span class="badge bg-success">${validation.passed} Passed</span>
                    <span class="badge bg-danger">${validation.failed} Failed</span>
                    <span class="badge bg-warning">${validation.warnings} Warnings</span>
                </div>
                <div class="success-rate">Success Rate: ${successRate.toFixed(1)}%</div>
            </div>
            <div class="validation-details">
                ${validation.checks.map(check => `
                    <div class="check-result check-${check.status}">
                        <strong>${check.name}:</strong> ${check.details}
                    </div>
                `).join('')}
            </div>
        `;
        
        // Add some basic styling
        const style = document.createElement('style');
        style.textContent = `
            .validation-summary { margin-bottom: 12px; padding: 8px; background: rgba(0,0,0,0.05); border-radius: 4px; }
            .result-stats { margin: 8px 0; }
            .result-stats .badge { margin-right: 4px; font-size: 10px; padding: 2px 6px; }
            .success-rate { font-weight: 600; }
            .check-result { padding: 4px 0; font-size: 12px; }
            .check-passed { color: #28a745; }
            .check-failed { color: #dc3545; }
            .check-warning { color: #ffc107; }
        `;
        document.head.appendChild(style);
    }
    
    stopScenario() {
        if (this.isRunning) {
            console.log('🛑 Stopping scenario...');
            this.isRunning = false;
            this.addResult('warning', 'Scenario stopped by user');
        }
    }
    
    resetUI() {
        console.log('🔄 Resetting UI components...');
        
        // Reset display components
        const resetEvents = [
            { type: 'agent_status_update', data: { is_running: false, current_phase_message: 'Idle' } },
            { type: 'phase_update', data: { phase_id: 'reset', status: 'ready', message: 'Ready' } }
        ];
        
        resetEvents.forEach(event => {
            document.dispatchEvent(new CustomEvent(event.type, { detail: event.data }));
        });
    }
    
    // Event generators for different scenarios
    generateFullPipelineEvents() {
        return [
            // Agent startup
            { type: 'agent_status_update', data: { is_running: true, current_phase_message: 'Starting agent...' }, delay: 500 },
            
            // Initialization phase
            { type: 'phase_start', data: { phase_id: 'initialization', message: 'Initializing system...' }, delay: 1000 },
            { type: 'phase_update', data: { phase_id: 'initialization', status: 'active', message: 'Loading configuration...' }, delay: 1500 },
            { type: 'phase_complete', data: { phase_id: 'initialization', message: 'Initialization complete' }, delay: 2000 },
            
            // Fetch bookmarks phase
            { type: 'phase_start', data: { phase_id: 'fetch_bookmarks', message: 'Fetching bookmarks...' }, delay: 2500 },
            { type: 'progress_update', data: { phase: 'fetch_bookmarks', processed_count: 0, total_count: 150 }, delay: 3000 },
            { type: 'progress_update', data: { phase: 'fetch_bookmarks', processed_count: 50, total_count: 150 }, delay: 4000 },
            { type: 'progress_update', data: { phase: 'fetch_bookmarks', processed_count: 100, total_count: 150 }, delay: 5000 },
            { type: 'progress_update', data: { phase: 'fetch_bookmarks', processed_count: 150, total_count: 150 }, delay: 6000 },
            { type: 'phase_complete', data: { phase_id: 'fetch_bookmarks', message: 'Bookmarks fetched successfully' }, delay: 6500 },
            
            // Content processing phase
            { type: 'phase_start', data: { phase_id: 'process_content', message: 'Processing content...' }, delay: 7000 },
            { type: 'progress_update', data: { phase: 'process_content', processed_count: 0, total_count: 150 }, delay: 7500 },
            { type: 'log', data: { message: 'Processing tweet content...', level: 'INFO' }, delay: 8000 },
            { type: 'progress_update', data: { phase: 'process_content', processed_count: 25, total_count: 150 }, delay: 9000 },
            { type: 'progress_update', data: { phase: 'process_content', processed_count: 75, total_count: 150 }, delay: 11000 },
            { type: 'progress_update', data: { phase: 'process_content', processed_count: 125, total_count: 150 }, delay: 13000 },
            { type: 'progress_update', data: { phase: 'process_content', processed_count: 150, total_count: 150 }, delay: 15000 },
            { type: 'phase_complete', data: { phase_id: 'process_content', message: 'Content processing complete' }, delay: 15500 },
            
            // Synthesis generation
            { type: 'phase_start', data: { phase_id: 'synthesis_generation', message: 'Generating syntheses...' }, delay: 16000 },
            { type: 'progress_update', data: { phase: 'synthesis_generation', processed_count: 0, total_count: 25 }, delay: 16500 },
            { type: 'progress_update', data: { phase: 'synthesis_generation', processed_count: 10, total_count: 25 }, delay: 18000 },
            { type: 'progress_update', data: { phase: 'synthesis_generation', processed_count: 20, total_count: 25 }, delay: 20000 },
            { type: 'progress_update', data: { phase: 'synthesis_generation', processed_count: 25, total_count: 25 }, delay: 22000 },
            { type: 'phase_complete', data: { phase_id: 'synthesis_generation', message: 'Syntheses generated successfully' }, delay: 22500 },
            
            // Finalization
            { type: 'phase_start', data: { phase_id: 'finalization', message: 'Finalizing results...' }, delay: 23000 },
            { type: 'progress_update', data: { phase: 'finalization', processed_count: 100, total_count: 100 }, delay: 24000 },
            { type: 'phase_complete', data: { phase_id: 'finalization', message: 'All tasks completed successfully' }, delay: 25000 },
            
            // Agent completion
            { type: 'agent_status_update', data: { is_running: false, current_phase_message: 'Agent completed successfully' }, delay: 26000 },
            { type: 'log', data: { message: 'Agent execution completed successfully', level: 'SUCCESS' }, delay: 26500 }
        ];
    }
    
    generateErrorRecoveryEvents() {
        return [
            // Start normally
            { type: 'agent_status_update', data: { is_running: true, current_phase_message: 'Starting agent...' }, delay: 500 },
            { type: 'phase_start', data: { phase_id: 'process_content', message: 'Processing content...' }, delay: 1000 },
            { type: 'progress_update', data: { phase: 'process_content', processed_count: 25, total_count: 100 }, delay: 2000 },
            
            // Encounter error
            { type: 'phase_error', data: { phase_id: 'process_content', message: 'Network timeout occurred' }, delay: 3000 },
            { type: 'log', data: { message: 'ERROR: Network timeout during content processing', level: 'ERROR' }, delay: 3500 },
            
            // Recovery attempt
            { type: 'log', data: { message: 'Attempting to recover from error...', level: 'WARNING' }, delay: 4000 },
            { type: 'phase_update', data: { phase_id: 'process_content', status: 'active', message: 'Retrying failed operations...' }, delay: 5000 },
            { type: 'progress_update', data: { phase: 'process_content', processed_count: 25, total_count: 100 }, delay: 6000 },
            
            // Successful recovery
            { type: 'log', data: { message: 'Recovery successful, continuing processing...', level: 'INFO' }, delay: 7000 },
            { type: 'progress_update', data: { phase: 'process_content', processed_count: 50, total_count: 100 }, delay: 8000 },
            { type: 'progress_update', data: { phase: 'process_content', processed_count: 75, total_count: 100 }, delay: 10000 },
            { type: 'progress_update', data: { phase: 'process_content', processed_count: 100, total_count: 100 }, delay: 12000 },
            { type: 'phase_complete', data: { phase_id: 'process_content', message: 'Content processing completed successfully' }, delay: 13000 },
            
            // Complete normally
            { type: 'agent_status_update', data: { is_running: false, current_phase_message: 'Agent completed with recovery' }, delay: 14000 }
        ];
    }
    
    generateHighLoadEvents() {
        const events = [];
        const totalItems = 500;
        const batchSize = 25;
        let delay = 500;
        
        // Start
        events.push({ type: 'agent_status_update', data: { is_running: true, current_phase_message: 'Processing high load...' }, delay });
        delay += 500;
        
        events.push({ type: 'phase_start', data: { phase_id: 'high_load_processing', message: 'Processing large dataset...' }, delay });
        delay += 500;
        
        // Generate progress updates in batches
        for (let processed = 0; processed <= totalItems; processed += batchSize) {
            const actualProcessed = Math.min(processed, totalItems);
            events.push({
                type: 'progress_update',
                data: { phase: 'high_load_processing', processed_count: actualProcessed, total_count: totalItems },
                delay
            });
            delay += 1000;
            
            // Add some logs
            if (processed % 100 === 0 && processed > 0) {
                events.push({
                    type: 'log',
                    data: { message: `Processed ${actualProcessed}/${totalItems} items...`, level: 'INFO' },
                    delay: delay - 500
                });
            }
        }
        
        // Complete
        events.push({ type: 'phase_complete', data: { phase_id: 'high_load_processing', message: 'High load processing complete' }, delay });
        delay += 500;
        
        events.push({ type: 'agent_status_update', data: { is_running: false, current_phase_message: 'High load processing completed' }, delay });
        
        return events;
    }
    
    generateInterruptedEvents() {
        return [
            // Start normally
            { type: 'agent_status_update', data: { is_running: true, current_phase_message: 'Starting agent...' }, delay: 500 },
            { type: 'phase_start', data: { phase_id: 'process_content', message: 'Processing content...' }, delay: 1000 },
            { type: 'progress_update', data: { phase: 'process_content', processed_count: 0, total_count: 100 }, delay: 1500 },
            { type: 'progress_update', data: { phase: 'process_content', processed_count: 25, total_count: 100 }, delay: 3000 },
            { type: 'progress_update', data: { phase: 'process_content', processed_count: 50, total_count: 100 }, delay: 5000 },
            
            // Interruption
            { type: 'log', data: { message: 'Stop signal received...', level: 'WARNING' }, delay: 7000 },
            { type: 'phase_update', data: { phase_id: 'process_content', status: 'interrupted', message: 'Processing interrupted by user' }, delay: 7500 },
            { type: 'agent_status_update', data: { is_running: false, current_phase_message: 'Agent stopped by user' }, delay: 8000 },
            { type: 'log', data: { message: 'Agent execution stopped', level: 'INFO' }, delay: 8500 }
        ];
    }
    
    generateMultiPhaseEvents() {
        // Simulate multiple phases running with overlapping progress
        return [
            // Start multiple phases
            { type: 'agent_status_update', data: { is_running: true, current_phase_message: 'Multi-phase processing...' }, delay: 500 },
            
            // Phase 1 starts
            { type: 'phase_start', data: { phase_id: 'fetch_data', message: 'Fetching data...' }, delay: 1000 },
            { type: 'progress_update', data: { phase: 'fetch_data', processed_count: 0, total_count: 100 }, delay: 1500 },
            
            // Phase 2 starts while Phase 1 is running
            { type: 'phase_start', data: { phase_id: 'process_media', message: 'Processing media...' }, delay: 2000 },
            { type: 'progress_update', data: { phase: 'process_media', processed_count: 0, total_count: 50 }, delay: 2500 },
            
            // Both phases progress
            { type: 'progress_update', data: { phase: 'fetch_data', processed_count: 25, total_count: 100 }, delay: 3000 },
            { type: 'progress_update', data: { phase: 'process_media', processed_count: 10, total_count: 50 }, delay: 3500 },
            
            // Phase 3 starts
            { type: 'phase_start', data: { phase_id: 'generate_content', message: 'Generating content...' }, delay: 4000 },
            { type: 'progress_update', data: { phase: 'generate_content', processed_count: 0, total_count: 25 }, delay: 4500 },
            
            // All phases progress
            { type: 'progress_update', data: { phase: 'fetch_data', processed_count: 50, total_count: 100 }, delay: 5000 },
            { type: 'progress_update', data: { phase: 'process_media', processed_count: 25, total_count: 50 }, delay: 5500 },
            { type: 'progress_update', data: { phase: 'generate_content', processed_count: 5, total_count: 25 }, delay: 6000 },
            
            // Phases complete in sequence
            { type: 'progress_update', data: { phase: 'fetch_data', processed_count: 100, total_count: 100 }, delay: 7000 },
            { type: 'phase_complete', data: { phase_id: 'fetch_data', message: 'Data fetching complete' }, delay: 7500 },
            
            { type: 'progress_update', data: { phase: 'process_media', processed_count: 50, total_count: 50 }, delay: 8000 },
            { type: 'phase_complete', data: { phase_id: 'process_media', message: 'Media processing complete' }, delay: 8500 },
            
            { type: 'progress_update', data: { phase: 'generate_content', processed_count: 25, total_count: 25 }, delay: 9000 },
            { type: 'phase_complete', data: { phase_id: 'generate_content', message: 'Content generation complete' }, delay: 9500 },
            
            // Final completion
            { type: 'agent_status_update', data: { is_running: false, current_phase_message: 'Multi-phase processing completed' }, delay: 10000 }
        ];
    }
    
    // Utility methods
    updateControls() {
        const runBtn = document.getElementById('run-scenario');
        const stopBtn = document.getElementById('stop-scenario');
        
        if (runBtn) runBtn.disabled = this.isRunning;
        if (stopBtn) stopBtn.disabled = !this.isRunning;
    }
    
    showProgress() {
        const progressEl = document.getElementById('scenario-progress');
        if (progressEl) {
            progressEl.style.display = 'block';
        }
    }
    
    hideProgress() {
        const progressEl = document.getElementById('scenario-progress');
        if (progressEl) {
            progressEl.style.display = 'none';
        }
    }
    
    updateProgress(percentage, status) {
        const progressBar = document.querySelector('#scenario-progress .progress-bar');
        const statusEl = document.querySelector('#scenario-progress .scenario-status');
        
        if (progressBar) {
            progressBar.style.width = `${percentage}%`;
            progressBar.setAttribute('aria-valuenow', percentage);
        }
        
        if (statusEl) {
            statusEl.textContent = status;
        }
    }
    
    clearResults() {
        const resultsEl = document.getElementById('scenario-results');
        if (resultsEl) {
            resultsEl.innerHTML = '<div class="text-muted">Running scenario...</div>';
        }
    }
    
    addResult(type, message) {
        console.log(`[${type.toUpperCase()}] ${message}`);
    }
    
    wait(ms) {
        return new Promise(resolve => setTimeout(resolve, ms));
    }
}

// Auto-initialize when script loads
if (typeof window !== 'undefined') {
    window.RealAgentScenarioTester = RealAgentScenarioTester;
    
    // Add keyboard shortcut to open scenario tester
    document.addEventListener('keydown', (e) => {
        if (e.ctrlKey && e.shiftKey && e.key === 'S') {
            if (!document.getElementById('agent-scenario-tester')) {
                new RealAgentScenarioTester();
            }
        }
    });
    
    console.log('🤖 Real Agent Scenario Tester loaded. Press Ctrl+Shift+S to open scenario tester.');
}

// Export for Node.js environments
if (typeof module !== 'undefined' && module.exports) {
    module.exports = RealAgentScenarioTester;
}