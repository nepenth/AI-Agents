/**
 * Main Application - Core functionality and Socket.IO handling
 * Layout and Phase management moved to separate modules
 */

document.addEventListener('DOMContentLoaded', function () {
    const socket = io();

    // UI Elements
    const liveLogsUl = document.getElementById('liveLogsUl');
    const clearLogsButton = document.getElementById('clearLogsButton');
    const runAgentButton = document.getElementById('runAgentButton');
    const stopAgentButton = document.getElementById('stopAgentButton');
    const darkModeToggle = document.getElementById('darkModeToggle');

    // State variables
    let agentIsRunning = false;
    let currentPhaseId = null;
    let activeRunPreferences = null;

    // Make agentIsRunning available globally for phase manager
    window.agentIsRunning = agentIsRunning;

    function initializeDefaultPhaseVisuals() {
        if (window.phaseManager) {
            console.log('index.js: Initializing default phase visuals to "Will Run"');
            Object.keys(window.phaseManager.phaseStates).forEach(phaseId => {
                const phaseElement = document.querySelector(`[data-phase-id="${phaseId}"]`);
                if (phaseElement) {
                    // Set default state to normal, which maps to "Will Run"
                    window.phaseManager.phaseStates[phaseId] = 'normal'; 
                    phaseElement.setAttribute('data-phase-state', 'normal');
                    window.phaseManager.updatePhaseVisualState(phaseElement, phaseId, 'normal');
                }
            });
        }
    }

    // --- Theme Initialization (Dark Mode) ---
    function initializeTheme() {
        const darkModeToggleInput = document.getElementById('darkModeToggle');
        if (!darkModeToggleInput) return;

        let preferredTheme = 'light';
        try {
            const localPrefsRaw = localStorage.getItem('agentClientPreferences');
            if (localPrefsRaw) {
                const clientPrefs = JSON.parse(localPrefsRaw);
                if (clientPrefs.hasOwnProperty('darkMode')) {
                    preferredTheme = clientPrefs.darkMode ? 'dark' : 'light';
                }
            }
        } catch (e) {
            console.error("Error reading dark mode preference from localStorage", e);
        }

        document.documentElement.setAttribute('data-bs-theme', preferredTheme);
        darkModeToggleInput.checked = (preferredTheme === 'dark');

        darkModeToggleInput.addEventListener('change', function () {
            const newTheme = this.checked ? 'dark' : 'light';
            document.documentElement.setAttribute('data-bs-theme', newTheme);
            saveClientPreferences();
        });
        
        console.log(`Theme initialized to: ${preferredTheme}`);
    }

    // --- Log Handling ---
    function addLogMessage(message, level = 'INFO') {
        if (!liveLogsUl) return;
        
        const li = document.createElement('li');
        li.className = `list-group-item log-${level.toLowerCase()}`;
        const timestamp = new Date().toLocaleTimeString();
        li.innerHTML = `<span class="log-timestamp">[${timestamp}]</span> <span class="log-level">[${level}]</span> <span class="log-message">${message}</span>`;
        liveLogsUl.appendChild(li);
        liveLogsUl.scrollTop = liveLogsUl.scrollHeight;
        
        updateLogCount();
    }

    function updateLogCount() {
        const logCountElement = document.getElementById('logCount');
        if (logCountElement && liveLogsUl) {
            const count = liveLogsUl.children.length;
            logCountElement.textContent = `${count} Log${count !== 1 ? 's' : ''}`;
        }
    }

    if (clearLogsButton) {
        clearLogsButton.addEventListener('click', () => {
            if (liveLogsUl) {
                liveLogsUl.innerHTML = '';
                addLogMessage('Live logs cleared by user.', 'INFO');
            }
        });
    }

    // --- Agent Status UI ---
    function updateAgentStatusUI() {
        const isRunning = agentIsRunning || (activeRunPreferences && activeRunPreferences.is_running);
        
        // Update global state for phase manager
        window.agentIsRunning = isRunning;
        
        // Update Run/Stop buttons
        if (runAgentButton) runAgentButton.disabled = isRunning;
        if (stopAgentButton) stopAgentButton.disabled = !isRunning;
        
        // Update agent run status display in logs footer
        const agentRunStatusLogsFooter = document.getElementById('agentRunStatusLogsFooter');
        if (agentRunStatusLogsFooter) {
            agentRunStatusLogsFooter.textContent = isRunning ? 'Agent Status: Running' : 'Agent Status: Not Running';
            agentRunStatusLogsFooter.classList.remove('text-danger', 'text-success');
            agentRunStatusLogsFooter.classList.add(isRunning ? 'text-success' : 'text-danger');
        }
    }

    // --- Preferences Handling ---
    function saveClientPreferences() {
        if (!window.phaseManager) return;
        
        const phaseStates = window.phaseManager.phaseStates;
        const clientPrefs = {
            skip_fetch_bookmarks: phaseStates.fetch_bookmarks === 'skip',
            skip_process_content: phaseStates.content_processing_overall === 'skip',
            skip_readme_generation: phaseStates.readme_generation === 'skip',
            skip_synthesis_generation: phaseStates.synthesis_generation === 'skip',
            skip_git_push: phaseStates.git_sync === 'skip',
            force_recache_tweets: phaseStates.subphase_cp_cache === 'force',
            force_reprocess_media: phaseStates.subphase_cp_media === 'force',
            force_reprocess_llm: phaseStates.subphase_cp_llm === 'force',
            force_reprocess_kb_item: phaseStates.subphase_cp_kbitem === 'force',
            force_regenerate_synthesis: phaseStates.synthesis_generation === 'force',
            darkMode: document.getElementById('darkModeToggle')?.checked || false
        };
        localStorage.setItem('agentClientPreferences', JSON.stringify(clientPrefs));
    }

    // Make preferences available globally
    window.preferencesManager = { saveClientPreferences };

    // --- Socket.IO Event Handlers ---
    socket.on('connect', () => {
        console.log('SocketIO connected successfully');
        addLogMessage('Connected to server via Socket.IO.', 'INFO');
    });

    socket.on('disconnect', () => {
        addLogMessage('Disconnected from server.', 'WARN');
    });

    socket.on('log', function(data) {
        addLogMessage(data.message, data.level);
    });

    socket.on('initial_status_and_git_config', function(data) {
        console.log("Received initial_status_and_git_config:", data);
        addLogMessage('Received initial agent status and Git config.', 'DEBUG');

        agentIsRunning = data.agent_is_running || data.is_running;
        currentPhaseId = data.current_phase_id;
        activeRunPreferences = data.active_run_preferences || null;

        updateAgentStatusUI();
        
        // Ensure DOM structure is correct - NO MORE MOVING ELEMENTS AROUND
        // The current-phase-details should stay exactly where it is in HTML
    });

    socket.on('agent_status', function(data) {
        console.log("Agent status update:", data);
        agentIsRunning = data.is_running;
        activeRunPreferences = data.active_run_preferences || null;
        updateAgentStatusUI();
    });

    socket.on('agent_phase_update', function(data) {
        console.log('Phase update received:', data);
        addLogMessage(`Phase update: ${data.phase_id} - ${data.status} - ${data.message}`, 'INFO');
        currentPhaseId = data.phase_id;
        
        // Update visual status of the phase in execution plan
        updatePhaseVisualStatus(data.phase_id, data.status, data);
        
        // Use phase manager for detailed updates
        if (window.phaseManager) {
            window.phaseManager.updateCurrentPhaseDetails(
                data.phase_id, 
                data.message || '', 
                data.processed_count, 
                data.total_count, 
                data.error_count
            );
            // Also update the execution plan status directly
            window.phaseManager.updatePhaseExecutionStatus(
                data.phase_id,
                data.processed_count,
                data.total_count,
                data.error_count
            );
        }
    });

    // Enhanced phase visual status update function
    function updatePhaseVisualStatus(phaseId, status, data) {
        const phaseElement = document.querySelector(`[data-phase-id="${phaseId}"]`);
        if (!phaseElement) return;
        
        const statusElement = phaseElement.querySelector('.phase-status');
        if (!statusElement) return;
        
        // Remove existing status classes
        phaseElement.classList.remove('status-pending', 'status-active', 'status-completed', 'status-skipped', 'status-error');
        
        let statusText = '';
        let statusClass = '';
        
        switch (status) {
            case 'active':
            case 'in_progress':
                statusClass = 'status-active';
                if (data.processed_count !== null && data.total_count !== null) {
                    const percentage = Math.round((data.processed_count / data.total_count) * 100);
                    statusText = `${data.processed_count}/${data.total_count} (${percentage}%)`;
                } else {
                    statusText = '🔄 Running...';
                }
                break;
                
            case 'completed':
                statusClass = 'status-completed';
                if (data.total_count !== null && data.total_count > 0) {
                    statusText = `✅ Done (${data.total_count})`;
                } else {
                    // Completed with no items - show as Done, not Skipped
                    statusText = '✅ Done';
                }
                break;
                
            case 'skipped':
                statusClass = 'status-skipped';
                // Check if this was actually skipped by user choice or completed with no work
                if (data.message && (data.message.includes('already') || data.message.includes('no') || data.message.includes('All') || data.total_count === 0)) {
                    // This is "done" with no work, not actually skipped
                    statusClass = 'status-completed';
                    statusText = '✅ Done';
                } else {
                    // Actually skipped by user
                    statusText = '⏭️ Skipped';
                }
                break;
                
            case 'error':
                statusClass = 'status-error';
                statusText = '❌ Error';
                break;
                
            case 'pending':
            default:
                statusClass = 'status-pending';
                if (data.total_count !== null && data.total_count > 0) {
                    statusText = `Will Run (${data.total_count})`;
                } else {
                    statusText = 'Will Run';
                }
                break;
        }
        
        phaseElement.classList.add(statusClass);
        statusElement.textContent = statusText;
        
        // Add progress indication for active phases
        if (status === 'active' || status === 'in_progress') {
            phaseElement.style.background = 'linear-gradient(90deg, #e3f2fd 0%, #bbdefb 100%)';
        } else {
            phaseElement.style.background = '';
        }
    }

    socket.on('agent_run_completed', function(data) {
        addLogMessage(`Agent run completed. Summary: ${data.summary_message}`, 'INFO');
        agentIsRunning = data.is_running;
        updateAgentStatusUI();
        currentPhaseId = null;
        activeRunPreferences = null;
    });

    socket.on('gpu_stats_update', function(data) {
        updateGPUStats(data);
    });

    // Enhanced GPU Stats Update Function
    function updateGPUStats(data) {
        const container = document.getElementById('gpuStatsContainer');
        if (!container) return;

        if (data.error) {
            container.innerHTML = `
                <div class="text-center text-danger">
                    <i class="bi bi-exclamation-triangle"></i> ${data.error}
                </div>
            `;
            return;
        }

        if (!data.gpus || data.gpus.length === 0) {
            container.innerHTML = `
                <div class="text-center text-muted">
                    <i class="bi bi-info-circle"></i> No GPU data available
                </div>
            `;
            return;
        }

        // Create compact multi-GPU display
        let html = '';
        
        if (data.gpus.length === 1) {
            // Single GPU - use full width
            const gpu = data.gpus[0];
            html = createCompactGPUCard(gpu, 0, 'col-12');
        } else {
            // Multiple GPUs - side by side
            html = '<div class="row g-3">';
            data.gpus.forEach((gpu, index) => {
                const colClass = data.gpus.length === 2 ? 'col-md-6' : 'col-md-4';
                html += createCompactGPUCard(gpu, index, colClass);
            });
            html += '</div>';
        }
        
        container.innerHTML = html;
    }

    function createCompactGPUCard(gpu, index, colClass) {
        const utilization = gpu.utilization_gpu || 0;
        const memoryUsed = gpu.memory_used || 0;
        const memoryTotal = gpu.memory_total || 1;
        const temperature = gpu.temperature_gpu_fahrenheit || ((gpu.temperature_gpu || 0) * 9/5 + 32);
        const temperatureCelsius = gpu.temperature_gpu || 0;
        const memoryPercent = (memoryUsed / memoryTotal) * 100;
        const graphicsFreq = gpu.clocks_graphics || 0;
        const memoryFreq = gpu.clocks_memory || 0;
        
        return `
            <div class="${colClass}">
                <div class="card">
                    <div class="card-header py-2">
                        <h6 class="card-title mb-0 text-center">
                            <i class="bi bi-gpu-card me-2"></i>GPU ${index} - ${gpu.name || 'Unknown'}
                        </h6>
                    </div>
                    <div class="card-body py-2">
                        <!-- GPU Load -->
                        <div class="mb-2">
                            <div class="d-flex justify-content-between align-items-center mb-1">
                                <span class="small fw-medium">GPU Load</span>
                                <span class="small fw-bold">${utilization.toFixed(1)}%</span>
                            </div>
                            <div class="progress" style="height: 6px;">
                                <div class="progress-bar ${getUtilizationBootstrapClass(utilization)}" 
                                     style="width: ${utilization}%"></div>
                            </div>
                        </div>
                        
                        <!-- Memory -->
                        <div class="mb-2">
                            <div class="d-flex justify-content-between align-items-center mb-1">
                                <span class="small fw-medium">Memory</span>
                                <span class="small fw-bold">${(memoryUsed/1024).toFixed(1)}/${(memoryTotal/1024).toFixed(1)} GB</span>
                            </div>
                            <div class="progress" style="height: 6px;">
                                <div class="progress-bar ${getMemoryBootstrapClass(memoryPercent)}" 
                                     style="width: ${memoryPercent}%"></div>
                            </div>
                        </div>
                        
                        <!-- Temperature -->
                        <div class="mb-2">
                            <div class="d-flex justify-content-between align-items-center mb-1">
                                <span class="small fw-medium">Temperature</span>
                                <span class="small fw-bold">${temperature.toFixed(0)}°F</span>
                            </div>
                            <div class="progress" style="height: 6px;">
                                <div class="progress-bar ${getTemperatureBootstrapClass(temperatureCelsius)}" 
                                     style="width: ${getTemperatureBarWidth(temperatureCelsius)}%"></div>
                            </div>
                        </div>
                        
                        <!-- GPU Frequency -->
                        ${graphicsFreq > 0 ? `
                        <div class="mb-0">
                            <div class="d-flex justify-content-between align-items-center mb-1">
                                <span class="small fw-medium">GPU Frequency</span>
                                <span class="small fw-bold">${graphicsFreq} MHz</span>
                            </div>
                            <div class="progress" style="height: 6px;">
                                <div class="progress-bar ${getFrequencyBootstrapClass(graphicsFreq)}" 
                                     style="width: ${getFrequencyBarWidth(graphicsFreq)}%"></div>
                            </div>
                        </div>
                        ` : ''}
                    </div>
                </div>
            </div>
        `;
    }

    function getUtilizationBootstrapClass(utilization) {
        if (utilization < 25) return 'bg-success';
        if (utilization < 50) return 'bg-warning';
        if (utilization < 80) return 'bg-orange';
        return 'bg-danger';
    }

    function getMemoryBootstrapClass(memoryPercent) {
        if (memoryPercent < 50) return 'bg-success';
        if (memoryPercent < 70) return 'bg-warning';
        if (memoryPercent < 90) return 'bg-orange';
        return 'bg-danger';
    }

    function getTemperatureBootstrapClass(temperature) {
        // Tesla P40 temperature ranges
        if (temperature < 40) return 'bg-info';
        if (temperature < 60) return 'bg-success';
        if (temperature < 75) return 'bg-warning';
        if (temperature < 85) return 'bg-orange';
        return 'bg-danger';
    }

    function getTemperatureBarWidth(temperature) {
        // Tesla P40 max operating temp is around 89°C
        const maxTemp = 90;
        return Math.min((temperature / maxTemp) * 100, 100);
    }

    function getFrequencyBootstrapClass(frequency) {
        if (frequency < 1000) return 'bg-success';
        if (frequency < 2000) return 'bg-warning';
        if (frequency < 3000) return 'bg-orange';
        return 'bg-danger';
    }

    function getFrequencyBarWidth(frequency) {
        // Assuming a default max frequency of 3000 MHz
        const maxFreq = 3000;
        return Math.min((frequency / maxFreq) * 100, 100);
    }

    // --- UI Initialization ---
    function initializeUI() {
        console.log('Initializing main UI...');
        
        if (runAgentButton) {
            runAgentButton.addEventListener('click', () => {
                if (window.phaseManager) {
                    const preferences = window.phaseManager.getServerPreferences();
                    addLogMessage(`Requesting to run agent...`, 'INFO');
                    socket.emit('run_agent', { preferences: preferences });
                }
            });
        }

        if (stopAgentButton) {
            stopAgentButton.addEventListener('click', () => {
                addLogMessage('Requesting to stop agent.', 'WARN');
                socket.emit('stop_agent');
            });
        }
    }
    
    // Initialize everything
    initializeDefaultPhaseVisuals();
    initializeTheme();
    initializeUI();
    socket.emit('request_initial_status_and_git_config');
    
    // Initial log message
    addLogMessage('Client JavaScript initialized.', 'INFO');
    setTimeout(updateLogCount, 100);
    
    console.log('Main application initialization complete');
}); 