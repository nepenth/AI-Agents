/**
 * Main Application - Core functionality and Socket.IO handling
 * Layout and Phase management moved to separate modules
 */

document.addEventListener('DOMContentLoaded', function () {
    const socket = io();

    // Cached DOM Elements - query once, use everywhere
    const DOM = {
        liveLogsUl: document.getElementById('liveLogsUl'),
        clearLogsButton: document.getElementById('clearLogsButton'),
        runAgentButton: document.getElementById('runAgentButton'),
        stopAgentButton: document.getElementById('stopAgentButton'),
        darkModeToggle: document.getElementById('darkModeToggle'),
        mainContentArea: document.getElementById('main-content-area'),
        logCount: document.getElementById('logCount'),
        agentRunStatusLogsFooter: document.getElementById('agentRunStatusLogsFooter'),
        gpuStatsContainer: document.getElementById('gpuStatsContainer'),
        chatWidget: document.getElementById('chat-widget')
    };

    // Centralized state management
    const appState = {
        agentIsRunning: false,
        currentPhaseId: null,
        activeRunPreferences: null,
        gpuStatsInterval: null,
        
        setAgentRunning(isRunning) {
            this.agentIsRunning = isRunning;
            window.agentIsRunning = isRunning; // Keep global in sync
            updateAgentStatusUI();
        },
        
        setCurrentPhase(phaseId) {
            this.currentPhaseId = phaseId;
        },
        
        setActivePreferences(preferences) {
            this.activeRunPreferences = preferences;
        }
    };

    // --- Theme Management ---
    function initializeTheme() {
        if (!DOM.darkModeToggle) return;

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
        DOM.darkModeToggle.checked = (preferredTheme === 'dark');

        DOM.darkModeToggle.addEventListener('change', function () {
            const newTheme = this.checked ? 'dark' : 'light';
            document.documentElement.setAttribute('data-bs-theme', newTheme);
            saveClientPreferences();
        });
        
        console.log(`Theme initialized to: ${preferredTheme}`);
    }

    // --- Log Management ---
    function addLogMessage(message, level = 'INFO') {
        if (!DOM.liveLogsUl) return;
        
        const li = document.createElement('li');
        li.className = `list-group-item log-${level.toLowerCase()}`;
        const timestamp = new Date().toLocaleTimeString();
        li.innerHTML = `<span class="log-timestamp">[${timestamp}]</span> <span class="log-level">[${level}]</span> <span class="log-message">${message}</span>`;
        DOM.liveLogsUl.appendChild(li);
        DOM.liveLogsUl.scrollTop = DOM.liveLogsUl.scrollHeight;
        
        updateLogCount();
    }

    function updateLogCount() {
        if (DOM.logCount && DOM.liveLogsUl) {
            const count = DOM.liveLogsUl.children.length;
            DOM.logCount.textContent = `${count} Log${count !== 1 ? 's' : ''}`;
        }
    }

    function clearLogs() {
        if (DOM.liveLogsUl) {
            DOM.liveLogsUl.innerHTML = '';
            socket.emit('clear_server_logs');
        }
    }

    // --- Agent Status Management ---
    function updateAgentStatusUI() {
        const isRunning = appState.agentIsRunning;
        
        // Update Run/Stop buttons
        if (DOM.runAgentButton) DOM.runAgentButton.disabled = isRunning;
        if (DOM.stopAgentButton) DOM.stopAgentButton.disabled = !isRunning;
        
        // Update status display
        if (DOM.agentRunStatusLogsFooter) {
            DOM.agentRunStatusLogsFooter.textContent = isRunning ? 'Agent Status: Running' : 'Agent Status: Not Running';
            DOM.agentRunStatusLogsFooter.classList.remove('text-danger', 'text-success');
            DOM.agentRunStatusLogsFooter.classList.add(isRunning ? 'text-success' : 'text-danger');
        }
    }

    // --- Preferences Management ---
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
            darkMode: DOM.darkModeToggle?.checked || false
        };
        localStorage.setItem('agentClientPreferences', JSON.stringify(clientPrefs));
    }

    // --- Phase Management Integration ---
    function initializePhaseManager() {
        if (window.phaseManager) {
            console.log('index.js: Initializing phase manager integration');
            window.phaseManager.restorePhaseStates();
            window.phaseManager.applyStateToUI();
        }
    }

    // --- GPU Stats Management ---
    function updateGPUStats(data) {
        console.log('updateGPUStats called with data:', data);
        if (!DOM.gpuStatsContainer) {
            console.error('gpuStatsContainer element not found');
            return;
        }

        if (data.error) {
            DOM.gpuStatsContainer.innerHTML = `
                <div class="text-center text-danger">
                    <i class="bi bi-exclamation-triangle"></i> ${data.error}
                </div>
            `;
            return;
        }

        if (!data.gpus || data.gpus.length === 0) {
            DOM.gpuStatsContainer.innerHTML = `
                <div class="text-center text-muted">
                    <i class="bi bi-info-circle"></i> No GPU data available
                </div>
            `;
            return;
        }

        // Create compact multi-GPU display
        let html = '';
        
        if (data.gpus.length === 1) {
            const gpu = data.gpus[0];
            html = createCompactGPUCard(gpu, 0, 'col-12');
        } else {
            html = '<div class="row g-3">';
            data.gpus.forEach((gpu, index) => {
                const colClass = data.gpus.length === 2 ? 'col-md-6' : 'col-md-4';
                html += createCompactGPUCard(gpu, index, colClass);
            });
            html += '</div>';
        }
        
        DOM.gpuStatsContainer.innerHTML = html;
    }

    function createCompactGPUCard(gpu, index, colClass) {
        const utilization = gpu.utilization_gpu || 0;
        const memoryUsed = gpu.memory_used || 0;
        const memoryTotal = gpu.memory_total || 1;
        const temperature = gpu.temperature_gpu_fahrenheit || ((gpu.temperature_gpu || 0) * 9/5 + 32);
        const temperatureCelsius = gpu.temperature_gpu || 0;
        const memoryPercent = (memoryUsed / memoryTotal) * 100;
        const graphicsFreq = gpu.clocks_graphics || 0;
        
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
                                <div class="progress-bar ${getUtilizationClass(utilization)}" 
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
                                <div class="progress-bar ${getMemoryClass(memoryPercent)}" 
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
                                <div class="progress-bar ${getTemperatureClass(temperatureCelsius)}" 
                                     style="width: ${getTemperatureBarWidth(temperatureCelsius)}%"></div>
                            </div>
                        </div>
                        
                        ${graphicsFreq > 0 ? `
                        <!-- GPU Frequency -->
                        <div class="mb-0">
                            <div class="d-flex justify-content-between align-items-center mb-1">
                                <span class="small fw-medium">GPU Frequency</span>
                                <span class="small fw-bold">${graphicsFreq} MHz</span>
                            </div>
                            <div class="progress" style="height: 6px;">
                                <div class="progress-bar ${getFrequencyClass(graphicsFreq)}" 
                                     style="width: ${getFrequencyBarWidth(graphicsFreq)}%"></div>
                            </div>
                        </div>
                        ` : ''}
                    </div>
                </div>
            </div>
        `;
    }

    // GPU Stats Helper Functions
    function getUtilizationClass(utilization) {
        if (utilization < 25) return 'bg-success';
        if (utilization < 50) return 'bg-warning';
        if (utilization < 80) return 'bg-orange';
        return 'bg-danger';
    }

    function getMemoryClass(memoryPercent) {
        if (memoryPercent < 50) return 'bg-success';
        if (memoryPercent < 70) return 'bg-warning';
        if (memoryPercent < 90) return 'bg-orange';
        return 'bg-danger';
    }

    function getTemperatureClass(temperature) {
        if (temperature < 40) return 'bg-info';
        if (temperature < 60) return 'bg-success';
        if (temperature < 75) return 'bg-warning';
        if (temperature < 85) return 'bg-orange';
        return 'bg-danger';
    }

    function getTemperatureBarWidth(temperature) {
        const maxTemp = 90;
        return Math.min((temperature / maxTemp) * 100, 100);
    }

    function getFrequencyClass(frequency) {
        if (frequency < 1000) return 'bg-success';
        if (frequency < 2000) return 'bg-warning';
        if (frequency < 3000) return 'bg-orange';
        return 'bg-danger';
    }

    function getFrequencyBarWidth(frequency) {
        const maxFreq = 3000;
        return Math.min((frequency / maxFreq) * 100, 100);
    }

    function refreshGPUStats() {
        console.log("refreshGPUStats called");
        console.log("Socket status:", socket ? (socket.connected ? 'connected' : 'disconnected') : 'undefined');
        
        if (!DOM.gpuStatsContainer) {
            console.log("GPU container not found");
            return;
        }
        
        if (socket && socket.connected) {
            console.log("Emitting request_gpu_stats via SocketIO");
            socket.emit('request_gpu_stats');
            
            // Fallback to REST if no response in 2 seconds
            setTimeout(() => {
                if (DOM.gpuStatsContainer && DOM.gpuStatsContainer.innerHTML.includes('Loading GPU statistics')) {
                    console.log("SocketIO didn't respond, falling back to REST API");
                    fetchGPUStatsREST();
                }
            }, 2000);
        } else {
            console.log("SocketIO not connected, using REST API fallback");
            fetchGPUStatsREST();
        }
    }

    async function fetchGPUStatsREST() {
        try {
            const response = await fetch('/api/gpu-stats');
            if (response.ok) {
                const data = await response.json();
                updateGPUStats(data);
            } else {
                const errorData = await response.json();
                updateGPUStats({error: errorData.error || 'Failed to fetch GPU stats'});
            }
        } catch (error) {
            console.error('Error fetching GPU stats via REST:', error);
            updateGPUStats({error: 'Network error fetching GPU stats'});
        }
    }

    function startGPUStatsMonitoring() {
        // Clear any existing interval
        if (appState.gpuStatsInterval) {
            clearInterval(appState.gpuStatsInterval);
        }
        
        // Set up periodic refresh every 10 seconds
        appState.gpuStatsInterval = setInterval(() => {
            if (DOM.gpuStatsContainer) {
                refreshGPUStats();
            }
        }, 10000);
    }

    // --- Event Handling ---
    function initializeEventHandlers() {
        if (!DOM.mainContentArea) return;

        // Use single delegated event handler for all clicks
        DOM.mainContentArea.addEventListener('click', (event) => {
            const target = event.target;

            if (target.matches('#runAgentButton')) {
                handleRunAgent();
            } else if (target.matches('#stopAgentButton')) {
                handleStopAgent();
            } else if (target.matches('#clearLogsButton')) {
                clearLogs();
            }
        });
    }

    function handleRunAgent() {
        console.log('Run Agent button clicked');
        if (window.phaseManager) {
            const preferences = window.phaseManager.getServerPreferences();
            console.log('Sending agent run request with preferences:', preferences);
            addLogMessage(`Requesting to run agent...`, 'INFO');
            socket.emit('run_agent', { preferences: preferences });
        } else {
            console.error('PhaseManager not found - using default preferences');
            addLogMessage('PhaseManager not found - using default preferences', 'WARNING');
            const defaultPrefs = {
                run_mode: 'full_pipeline',
                skip_fetch_bookmarks: false,
                skip_process_content: false,
                skip_synthesis_generation: false,
                skip_embedding_generation: false,
                skip_readme_generation: false,
                skip_git_push: false,
                force_recache_tweets: false,
                force_reprocess_media: false,
                force_reprocess_llm: false,
                force_reprocess_kb_item: false,
                force_regenerate_synthesis: false,
                force_regenerate_embeddings: false
            };
            socket.emit('run_agent', { preferences: defaultPrefs });
        }
    }

    function handleStopAgent() {
        addLogMessage('Requesting to stop agent.', 'WARN');
        socket.emit('stop_agent');
    }

    // --- Chat Widget Management ---
    function initializeChatWidget() {
        if (!DOM.chatWidget) return;

        const chatHeader = DOM.chatWidget.querySelector('.chat-widget-header');
        const chatBody = DOM.chatWidget.querySelector('.chat-widget-body');
        const toggleIcon = DOM.chatWidget.querySelector('.chat-toggle-icon');

        if (chatHeader) {
            chatHeader.addEventListener('click', () => {
                DOM.chatWidget.classList.toggle('chat-widget-open');
                const isOpen = DOM.chatWidget.classList.contains('chat-widget-open');
                chatBody.style.display = isOpen ? 'flex' : 'none';
                
                // Update toggle icon
                if (toggleIcon) {
                    toggleIcon.textContent = isOpen ? '-' : '+';
                }
                
                console.log(`Chat widget ${isOpen ? 'opened' : 'minimized'}`);
            });
        }

        if (window.initializeChat) {
            window.initializeChat();
        }
    }

    // --- Socket.IO Event Handlers ---
    socket.on('connect', () => {
        console.log('SocketIO connected successfully');
        addLogMessage('Connected to server via Socket.IO.', 'INFO');
        
        // Request GPU stats when connection is established
        setTimeout(() => {
            console.log('Requesting initial GPU stats on SocketIO connect');
            socket.emit('request_gpu_stats');
        }, 100);
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

        appState.setAgentRunning(data.agent_is_running || data.is_running);
        appState.setCurrentPhase(data.current_phase_id);
        appState.setActivePreferences(data.active_run_preferences || null);

        if (appState.agentIsRunning && appState.activeRunPreferences && window.phaseManager && typeof window.phaseManager.applyActiveRunPreferencesToUI === 'function') {
            console.log('Agent is running with preferences, applying to UI:', appState.activeRunPreferences);
            window.phaseManager.applyActiveRunPreferencesToUI(appState.activeRunPreferences);
        } else if (appState.agentIsRunning && appState.activeRunPreferences) {
            console.warn('phaseManager.applyActiveRunPreferencesToUI function not found. UI may not reflect active preferences.');
        }
    });

    socket.on('agent_status', function(data) {
        console.log("Agent status update:", data);
        appState.setAgentRunning(data.is_running);
        appState.setActivePreferences(data.active_run_preferences || null);
    });

    socket.on('phase_update', function(data) {
        console.log('Phase update received:', data);
        addLogMessage(`Phase update: ${data.phase_id} - ${data.status} - ${data.message}`, 'INFO');
        appState.setCurrentPhase(data.phase_id);
        
        // Use phase manager for updates (single point of truth)
        if (window.phaseManager) {
            // Update the bottom status message
            window.phaseManager.updateCurrentPhaseDetails(
                data.phase_id, 
                data.message || '', 
                data.processed_count, 
                data.total_count, 
                data.error_count
            );
            
            // Update the phase status in the execution plan
            window.phaseManager.updatePhaseStatus(
                data.phase_id,
                data.status,
                data.message
            );
            
            // If we have progress counts, also update progress display
            if (data.processed_count !== null && data.processed_count !== undefined) {
                window.phaseManager.updatePhaseExecutionStatus(
                    data.phase_id,
                    data.processed_count,
                    data.total_count,
                    data.error_count
                );
            }
        }
    });

    socket.on('agent_run_completed', function(data) {
        addLogMessage(`Agent run completed. Summary: ${data.summary_message}`, 'INFO');
        appState.setAgentRunning(data.is_running);
        appState.setCurrentPhase(null);
        appState.setActivePreferences(null);
    });

    socket.on('gpu_stats', function(data) {
        updateGPUStats(data);
    });

    socket.on('gpu_stats_update', function(data) {
        updateGPUStats(data);
    });

    // --- Dynamic Components Reinitialization (for SPA navigation) ---
    function reinitializeDynamicComponents() {
        console.log("Re-initializing dynamic components...");
        
        // Update DOM cache for new elements
        DOM.gpuStatsContainer = document.getElementById('gpuStatsContainer');
        
        // Refresh GPU stats if container exists
        if (DOM.gpuStatsContainer) {
            refreshGPUStats();
        }
        
        // Re-initialize chat widget
        initializeChatWidget();
        
        // Re-initialize logs page if we're on logs page
        if (document.getElementById('log-file-select')) {
            console.log('Logs page detected, initializing logs functionality');
            if (window.initializeLogsPage) {
                setTimeout(() => window.initializeLogsPage(), 100);
            }
        }
        
        // Re-initialize phase manager if available
        if (window.phaseManager) {
            window.phaseManager.restorePhaseStates();
            window.phaseManager.applyStateToUI();
        }
    }

    // --- Global Exports ---
    window.preferencesManager = { saveClientPreferences };
    window.reinitializeDynamicComponents = reinitializeDynamicComponents;
    window.refreshGPUStats = refreshGPUStats;

    // --- Application Initialization ---
    function initializeApplication() {
        console.log('Initializing main application...');
        
        // Initialize core systems
        initializeTheme();
        initializeEventHandlers();
        initializePhaseManager();
        initializeChatWidget();
        
        // Request initial status
        socket.emit('request_initial_status_and_git_config');
        
        // Start GPU monitoring with backup
        setTimeout(() => {
            if (DOM.gpuStatsContainer && DOM.gpuStatsContainer.innerHTML.includes('Loading GPU statistics')) {
                console.log('Backup GPU stats request');
                refreshGPUStats();
            }
        }, 2000);
        
        startGPUStatsMonitoring();
        
        // Initial log setup
        addLogMessage('Client JavaScript initialized.', 'INFO');
        setTimeout(updateLogCount, 100);
        
        console.log('Main application initialization complete');
    }

    // Start the application
    initializeApplication();
}); 