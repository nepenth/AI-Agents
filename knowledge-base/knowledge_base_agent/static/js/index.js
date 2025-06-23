/**
 * Main Application - Core functionality and Socket.IO handling for the Agent Control Panel.
 * This script acts as a "specialist" for the main dashboard page.
 */

const socket = io();

// Centralized state management for the application
const appState = {
    agentIsRunning: false,
    currentPhaseId: null,
    activeRunPreferences: null,
    gpuStatsInterval: null,
    currentLogs: [], // Store current logs for restoration
    
    setAgentRunning(isRunning) {
        this.agentIsRunning = isRunning;
        // Keep a global copy for easier debugging from the console, if needed.
        window.agentIsRunning = isRunning;
        updateAgentStatusUI();
    },
    
    setCurrentPhase(phaseId) {
        this.currentPhaseId = phaseId;
    },
    
    setActivePreferences(preferences) {
        this.activeRunPreferences = preferences;
    }
};

// --- DOM and UI Utility Functions ---

/**
 * Gets a fresh reference to all dynamic DOM elements.
 * This is done as a function to ensure we always have the latest elements after page loads.
 */
function getDOMElements() {
    return {
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
}

/**
 * Adds a new message to the live logs UI.
 * @param {string} message - The log message content.
 * @param {string} [level='INFO'] - The log level (e.g., INFO, WARN, ERROR).
 */
function addLogMessage(message, level = 'INFO') {
    const DOM = getDOMElements();
    if (!DOM.liveLogsUl) return;
    
    const li = document.createElement('li');
    li.className = `list-group-item log-${level.toLowerCase()}`;
    const timestamp = new Date().toLocaleTimeString();
    li.innerHTML = `<span class="log-timestamp">[${timestamp}]</span> <span class="log-level">[${level}]</span> <span class="log-message">${message}</span>`;
    DOM.liveLogsUl.appendChild(li);
    DOM.liveLogsUl.scrollTop = DOM.liveLogsUl.scrollHeight;
    
    // Store in app state for restoration on navigation
    appState.currentLogs.push({message, level, timestamp});
    if (appState.currentLogs.length > 400) {
        appState.currentLogs.shift(); // Keep only recent logs
    }
    updateLogCount();
}

/**
 * Clears all messages from the live logs UI.
 */
function clearLogs() {
    const DOM = getDOMElements();
    if (DOM.liveLogsUl) {
        DOM.liveLogsUl.innerHTML = '';
        appState.currentLogs = []; // Clear stored logs
        // Let the server know to clear its own session logs if it maintains them
        socket.emit('clear_server_logs'); 
        updateLogCount();
        addLogMessage('On-screen logs cleared.', 'INFO');
    }
}

/**
 * Restores logs from the appState to the UI.
 * Used when navigating back to the control panel.
 */
function restoreLogsToUI() {
    const DOM = getDOMElements();
    if (!DOM.liveLogsUl) return;
    
    console.log(`Restoring ${appState.currentLogs.length} logs to UI`);
    DOM.liveLogsUl.innerHTML = ''; // Clear any existing logs
    
    appState.currentLogs.forEach(logEntry => {
        const li = document.createElement('li');
        li.className = `list-group-item log-${logEntry.level.toLowerCase()}`;
        li.innerHTML = `<span class="log-timestamp">[${logEntry.timestamp}]</span> <span class="log-level">[${logEntry.level}]</span> <span class="log-message">${logEntry.message}</span>`;
        DOM.liveLogsUl.appendChild(li);
    });
    
    DOM.liveLogsUl.scrollTop = DOM.liveLogsUl.scrollHeight;
    updateLogCount();
}

/**
 * Updates the log count display in the footer.
 */
function updateLogCount() {
    const DOM = getDOMElements();
    if (DOM.logCount && DOM.liveLogsUl) {
        const count = DOM.liveLogsUl.children.length;
        DOM.logCount.textContent = `${count} Log${count !== 1 ? 's' : ''}`;
    }
}

/**
 * Updates the run/stop buttons and status text based on the agent's running state.
 */
function updateAgentStatusUI() {
    const DOM = getDOMElements();
    const isRunning = appState.agentIsRunning;
    
    // Update Run/Stop buttons
    if (DOM.runAgentButton) DOM.runAgentButton.disabled = isRunning;
    if (DOM.stopAgentButton) DOM.stopAgentButton.disabled = !isRunning;
    
    // Update status display in the logs footer
    const statusFooter = document.getElementById('agentRunStatusLogsFooter');
    if (statusFooter) {
        statusFooter.textContent = isRunning ? 'Agent Status: Running' : 'Agent Status: Not Running';
        statusFooter.classList.remove('text-danger', 'text-success');
        statusFooter.classList.add(isRunning ? 'text-success' : 'text-danger');
    }
    
    // Show/hide ETC display based on agent status
    if (window.phaseManager) {
        if (isRunning) {
            // ETC will be shown when phase updates are received
            console.log('Agent started - ETC display will be shown with phase updates');
        } else {
            // Hide ETC display when agent stops
            window.phaseManager.hideETCDisplay();
            console.log('Agent stopped - ETC display hidden');
        }
    }
}


// --- Core Initialization for Agent Control Panel ---

/**
 * Main initializer for the Agent Control Panel. 
 * This is the entry point called by the navigation conductor.
 */
function initializeAgentControlPanel() {
    console.log("Initializing Agent Control Panel...");

    // Make sure we only run this on the correct page.
    if (!document.getElementById('runAgentButton')) {
        console.log("Agent Control Panel elements not found. Aborting initialization.");
        return;
    }

    // Connect event handlers for all interactive elements on the page.
    initializeEventHandlers();

    // Set up the phase manager for the execution plan display.
    initializePhaseManagerIntegration();
    
    // Set up the GPU stats display and monitoring.
    initializeGpuStats();

    // Restore any logs that were present before navigating away.
    restoreLogsToUI();

    // Update run/stop buttons based on the current agent state.
    updateAgentStatusUI();
    
    // Request the latest status from the server to ensure UI is in sync.
    requestCurrentStateFromServer();
    
    console.log("Agent Control Panel initialized successfully.");
}
window.initializeAgentControlPanel = initializeAgentControlPanel;


// --- Event Handler Management ---

/**
 * Binds all necessary event listeners for the control panel.
 */
function initializeEventHandlers() {
    console.log("Binding event handlers for Agent Control Panel.");
    
    // Main agent controls
    document.getElementById('runAgentButton').addEventListener('click', runAgent);
    document.getElementById('stopAgentButton').addEventListener('click', stopAgent);
    document.getElementById('clearLogsButton').addEventListener('click', clearLogs);
    
    // GPU stats refresh button
    document.getElementById('refresh-gpu-stats-btn').addEventListener('click', refreshGPUStats);

    // Use event delegation for preset buttons for efficiency
    const preferencesSection = document.querySelector('.preferences-section');
    if (preferencesSection) {
        preferencesSection.addEventListener('click', (event) => {
            const presetButton = event.target.closest('button[data-preset]');
            if (presetButton && window.phaseManager) {
                const presetType = presetButton.dataset.preset;
                window.phaseManager.applyPreset(presetType);
            }
        });
    }

    // Use event delegation for clickable phases
    const executionPlanPanel = document.querySelector('.execution-plan-panel');
    if (executionPlanPanel) {
        executionPlanPanel.addEventListener('click', (event) => {
            const phaseElement = event.target.closest('.clickable-phase');
            if (phaseElement && window.phaseManager) {
                // Pass the current running state to prevent changes during a run
                const isRunning = window.agentIsRunning || false;
                window.phaseManager.togglePhaseState(phaseElement, isRunning);
            }
        });
    }
}

// --- Agent Actions ---

function runAgent() {
    if (appState.agentIsRunning) {
        addLogMessage('Agent is already running.', 'WARN');
        return;
    }
    console.log("Attempting to run agent...");
    addLogMessage('Starting agent run...', 'INFO');
    appState.setAgentRunning(true);

    const runPreferences = window.phaseManager ? window.phaseManager.getServerPreferences() : {};
    appState.setActivePreferences(runPreferences);
    
    socket.emit('run_agent', runPreferences);
}

function stopAgent() {
    if (!appState.agentIsRunning) {
        addLogMessage('Agent is not currently running.', 'WARN');
        return;
    }
    console.log("Attempting to stop agent...");
    addLogMessage('Requesting to stop the agent...', 'INFO');
    socket.emit('stop_agent');
}


// --- Theme Management ---
// This is global and should remain accessible.
function toggleDarkMode() {
    const isChecked = document.getElementById('darkModeToggle').checked;
    const newTheme = isChecked ? 'dark' : 'light';
    document.documentElement.setAttribute('data-bs-theme', newTheme);
    
    // Save the preference
    try {
        const prefsRaw = localStorage.getItem('agentClientPreferences') || '{}';
        const prefs = JSON.parse(prefsRaw);
        prefs.darkMode = isChecked;
        localStorage.setItem('agentClientPreferences', JSON.stringify(prefs));
    } catch (e) {
        console.error("Could not save dark mode preference:", e);
    }
}
window.toggleDarkMode = toggleDarkMode;

function initializeTheme() {
    const darkModeToggle = document.getElementById('darkModeToggle');
    if (!darkModeToggle) return;

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
    if(darkModeToggle) {
        darkModeToggle.checked = (preferredTheme === 'dark');
    }
    console.log(`Theme initialized to: ${preferredTheme}`);
}

// --- Preferences Management ---
function saveClientPreferences() {
    if (!window.phaseManager) return;
    
    const phaseStates = window.phaseManager.phaseStates;
    const darkModeToggle = document.getElementById('darkModeToggle');
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
        darkMode: darkModeToggle?.checked || false
    };
    localStorage.setItem('agentClientPreferences', JSON.stringify(clientPrefs));
}


// --- Phase Management Integration ---
function initializePhaseManagerIntegration() {
    if (window.phaseManager) {
        console.log('index.js: Initializing phase manager integration');
        window.phaseManager.restorePhaseStates();
        window.phaseManager.applyStateToUI();
        // Add listener for phase changes to save preferences
        document.addEventListener('phaseStateChanged', saveClientPreferences);
    }
}

// --- Server State Sync ---
function requestCurrentStateFromServer() {
    console.log('Requesting current state from server...');
    // Request current status, logs, and git config
    socket.emit('request_initial_status_and_git_config');
    socket.emit('request_initial_logs');
}

// --- GPU Stats Management ---
function initializeGpuStats() {
    console.log("Initializing GPU stats monitoring...");
    startGPUStatsMonitoring();
    // The refresh button is handled in initializeEventHandlers
}

function updateGPUStats(data) {
    console.log('updateGPUStats called with data:', data);
    const gpuStatsContainer = document.getElementById('gpuStatsContainer');
    if (!gpuStatsContainer) {
        // This can happen if we navigate away before the call completes
        console.log('GPU stats container not found, skipping update.');
        return;
    }

    if (data.error) {
        gpuStatsContainer.innerHTML = `
            <div class="text-center text-danger">
                <i class="bi bi-exclamation-triangle"></i> ${data.error}
            </div>
        `;
        return;
    }

    if (!data.gpus || data.gpus.length === 0) {
        gpuStatsContainer.innerHTML = `
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
    
    gpuStatsContainer.innerHTML = html;
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
    return Math.min(100, Math.max(0, (frequency / 5000) * 100)); // Assume 5000MHz is a reasonable max
}

function refreshGPUStats() {
    console.log("refreshGPUStats called");
    const socketStatus = socket.connected ? 'connected' : 'disconnected';
    console.log(`Socket status: ${socketStatus}`);
    
    if (socket.connected) {
        addLogMessage('Requesting updated GPU stats...', 'DEBUG');
        console.log('Emitting request_gpu_stats via SocketIO');
        socket.emit('request_gpu_stats');
    } else {
        // Fallback to REST if socket is not connected
        console.log('Socket not connected, falling back to REST for GPU stats');
        fetchGPUStatsREST();
    }
}

async function fetchGPUStatsREST() {
    try {
        const response = await fetch('/api/gpu-stats');
        if (!response.ok) {
            throw new Error(`HTTP error! status: ${response.status}`);
        }
        const data = await response.json();
        updateGPUStats(data);
    } catch (error) {
        console.error('Error fetching GPU stats via REST:', error);
        updateGPUStats({ error: 'Could not fetch GPU stats.' });
    }
}

function startGPUStatsMonitoring() {
    // Clear any existing interval to prevent duplicates
    if (appState.gpuStatsInterval) {
        clearInterval(appState.gpuStatsInterval);
    }
    // Initial fetch
    refreshGPUStats();
    // Fetch every 30 seconds
    appState.gpuStatsInterval = setInterval(refreshGPUStats, 30000); 
    console.log(`GPU stats monitoring started with interval ID: ${appState.gpuStatsInterval}`);
}

function stopGPUStatsMonitoring() {
    if (appState.gpuStatsInterval) {
        clearInterval(appState.gpuStatsInterval);
        appState.gpuStatsInterval = null;
        console.log("GPU stats monitoring stopped.");
    }
}


// --- Chat Widget Management ---
function initializeChatWidget() {
    // This can be called globally as it's part of the main layout, not page-specific content.
    const chatWidget = document.getElementById('chat-widget');
    if (chatWidget && window.initializeChat) {
        console.log("Initializing chat for context: widget");
        window.initializeChat('widget');
    }
}


// --- Socket.IO Event Listeners ---

function initializeSocketListeners() {
    // Remove all existing listeners to prevent duplicates, crucial for SPA navigation
    socket.off();

    console.log("Initializing Socket.IO event listeners...");

    socket.on('connect', () => {
        console.log('SocketIO connected successfully');
        // When we first connect, or reconnect, make sure the UI is in sync.
        if (document.getElementById('runAgentButton')) {
            requestCurrentStateFromServer();
        }
        // Always request GPU stats on connection
        console.log('Requesting initial GPU stats on SocketIO connect');
        socket.emit('request_gpu_stats');
    });

    socket.on('disconnect', () => {
        addLogMessage('SocketIO disconnected from server.', 'ERROR');
    });

    socket.on('connect_error', (error) => {
        console.error('Socket.IO Connection Error:', error);
        addLogMessage(`SocketIO connection error: ${error.message}`, 'ERROR');
    });

    socket.on('log_message', (data) => {
        addLogMessage(data.message, data.level);
    });

    socket.on('agent_status_update', (data) => {
        console.log('Agent status update:', data);
        const newStatus = data.is_running;
        if (appState.agentIsRunning !== newStatus) {
            appState.setAgentRunning(newStatus);
        }
    });

    socket.on('initial_status_and_git_config', (data) => {
        console.log('Received initial_status_and_git_config:', data);
        appState.setAgentRunning(data.agent_is_running);
    });
    
    socket.on('initial_logs', (data) => {
        console.log('Received initial_logs:', data);
        const DOM = getDOMElements();
        if (!DOM.liveLogsUl) return;

        DOM.liveLogsUl.innerHTML = ''; // Clear current logs
        appState.currentLogs = []; // Clear state
        
        data.logs.forEach(log => {
            addLogMessage(log.message, log.level);
        });
        console.log(`Restoring ${data.logs.length} logs to UI`);
    });

    socket.on('agent_stopped', (data) => {
        addLogMessage(data.message, 'INFO');
        appState.setAgentRunning(false);
    });
    
    socket.on('agent_completed', (data) => {
        addLogMessage(data.message, 'SUCCESS');
        appState.setAgentRunning(false);
    });

    socket.on('agent_error', (data) => {
        addLogMessage(data.message, 'ERROR');
        appState.setAgentRunning(false);
    });

    socket.on('phase_update', (data) => {
        if (window.phaseManager) {
            window.phaseManager.handlePhaseUpdateWithETC(data);
        }
    });

    socket.on('gpu_stats_update', (data) => {
        updateGPUStats(data);
    });
}


// --- Global Application Initialization ---

/**
 * This function runs once when the main application script is loaded.
 * It sets up parts of the application that are persistent across all pages.
 */
function initializeGlobalApp() {
    console.log("Initializing global application components...");

    // Set up socket listeners immediately. They are fundamental.
    initializeSocketListeners();

    // Initialize the theme. The toggle is in the header, so it's always present.
    initializeTheme();
    
    // Initialize the chat widget. It's also always present.
    initializeChatWidget();

    // Initialize SPA navigation, which will handle loading page-specific content.
    if (window.initializeSPANavigation) {
        window.initializeSPANavigation();
    } else {
        console.error("SPA Navigation module not found!");
    }
    
    console.log("Global application components initialized.");
}

// Kick off the application.
document.addEventListener('DOMContentLoaded', initializeGlobalApp); 