"use strict";

// --- Theme / Dark Mode ---
const getStoredTheme = () => localStorage.getItem('theme');
const setStoredTheme = theme => localStorage.setItem('theme', theme);

const getPreferredTheme = () => {
    const storedTheme = getStoredTheme();
    if (storedTheme) {
        return storedTheme;
    }
    // Use browser preference if available, default to light
    return window.matchMedia('(prefers-color-scheme: dark)').matches ? 'dark' : 'light';
};

const setTheme = theme => {
    if (theme === 'auto') {
        document.documentElement.setAttribute('data-bs-theme', (window.matchMedia('(prefers-color-scheme: dark)').matches ? 'dark' : 'light'));
    } else {
        document.documentElement.setAttribute('data-bs-theme', theme);
    }
};

// Set initial theme
setTheme(getPreferredTheme());

// --- UI State Persistence (Merged from app.js) ---
const uiStateKey = 'knowledgeAgentUIState';

// Function to load state from server/localStorage
async function loadUIState() {
    // NOTE: Server endpoint /api/ui-state needs to exist if we want server-side persistence.
    // For now, focusing on localStorage fallback.
    /* // Optional: Server-side loading (requires backend endpoint)
    try {
        const response = await fetch('/api/ui-state'); // Assumes endpoint exists
        if (response.ok) {
            const serverState = await response.json();
            localStorage.setItem(uiStateKey, JSON.stringify(serverState)); // Update local cache
            applyUIState(serverState);
            console.log("Loaded UI state from server:", serverState);
            return;
        } else {
             console.warn("Failed to load UI state from server:", response.status);
        }
    } catch (err) {
        console.error("Error fetching UI state from server:", err);
    }
    */
    // Fallback to localStorage
    const localState = JSON.parse(localStorage.getItem(uiStateKey) || '{}');
    applyUIState(localState);
    console.log("Loaded UI state from localStorage:", localState);
}

// Function to apply loaded state to UI elements
function applyUIState(state) {
    // Apply state to known preference checkboxes
    if (forceRecacheCheckbox) {
        forceRecacheCheckbox.checked = state.force_recache === true;
    }
    if (skipFetchCheckbox) {
        skipFetchCheckbox.checked = state.skip_fetch === true;
    }
    if (skipGitCheckbox) {
        skipGitCheckbox.checked = state.skip_git === true;
    }
    if (forceReinterpretCheckbox) {
        forceReinterpretCheckbox.checked = state.force_reinterpret === true;
    }
    if (forceRecategorizeCheckbox) {
        forceRecategorizeCheckbox.checked = state.force_recategorize === true;
    }
    if (forceRegenerateCheckbox) {
        forceRegenerateCheckbox.checked = state.force_regenerate === true;
    }

    // Apply state to Run Mode radio buttons
    const runMode = state.run_mode || 'Full'; // Default to 'Full'
    const runModeRadio = document.querySelector(`input[name="runMode"][value="${runMode}"]`);
    if (runModeRadio) {
        runModeRadio.checked = true;
    }
    // Add other elements if needed
}

// Function to save a single key-value pair
async function saveUIStateKey(key, value) {
    // 1. Update local storage immediately
    const currentState = JSON.parse(localStorage.getItem(uiStateKey) || '{}');
    currentState[key] = value;
    localStorage.setItem(uiStateKey, JSON.stringify(currentState));
    console.log(`Saved UI state key ${key}=${value} to localStorage.`);

    // 2. Send update to server (optional, requires backend endpoint)
    /* // Optional: Server-side saving
    try {
         await fetch(`/api/ui-state/${key}`, { // Assumes endpoint exists
             method: 'PUT',
             headers: { 'Content-Type': 'application/json' },
             body: JSON.stringify({ value: value })
         });
         console.log(`Saved UI state key ${key} to server.`);
    } catch (err) {
         console.error(`Error saving UI state key ${key} to server:`, err);
         // Optionally revert local state or show error
    }
    */
}

// --- End UI State Persistence ---

window.addEventListener('DOMContentLoaded', () => {
    // Activate the button corresponding to the current theme
    document.querySelectorAll('[data-bs-theme-value]')
        .forEach(toggle => {
            toggle.addEventListener('click', () => {
                const theme = toggle.getAttribute('data-bs-theme-value');
                setStoredTheme(theme);
                setTheme(theme);
                // Update active state on buttons
                 document.querySelectorAll('[data-bs-theme-value].active')
                    .forEach(btn => btn.classList.remove('active'));
                 toggle.classList.add('active');
            });
             // Set initial active state
             if (toggle.getAttribute('data-bs-theme-value') === getPreferredTheme()) {
                 toggle.classList.add('active');
             }
        });

     // Watch for OS theme changes if theme is 'auto'
     window.matchMedia('(prefers-color-scheme: dark)').addEventListener('change', () => {
         const storedTheme = getStoredTheme();
         if (storedTheme !== 'light' && storedTheme !== 'dark') {
             setTheme(getPreferredTheme());
         }
     });

    // --- Socket.IO ---
    // Connect to the default namespace for agent status
    const agentSocket = io('/agent'); // Use the '/agent' namespace
    const logSocket = io('/logs'); // Use the '/logs' namespace for logs

    const statusBadge = document.getElementById('agent-status');
    const statusMessage = document.getElementById('status-message');
    const startButton = document.getElementById('start-agent-btn');
    const stopButton = document.getElementById('stop-agent-btn');
    // Get references to ALL checkboxes
    const forceRecacheCheckbox = document.getElementById('forceRecacheCheck');
    const skipFetchCheckbox = document.getElementById('skipFetchCheck');
    const skipGitCheckbox = document.getElementById('skipGitCheck');
    const forceReinterpretCheckbox = document.getElementById('forceReinterpretCheck');
    const forceRecategorizeCheckbox = document.getElementById('forceRecategorizeCheck');
    const forceRegenerateCheckbox = document.getElementById('forceRegenerateCheck');
    const liveLogContent = document.getElementById('live-log-content');
    // New progress elements
    const progressCountSpan = document.getElementById('progress-count'); // Items in current phase batch
    const progressTotalSpan = document.getElementById('progress-total');   // Total in current phase batch
    const currentPhaseSpan = document.getElementById('current-phase');
    const currentItemIdSpan = document.getElementById('current-item-id');
    const etaSpan = document.getElementById('eta');
    // Add new elements for overall progress if you add them to your HTML
    // const overallProgressSpan = document.getElementById('overall-progress'); // e.g., "Overall: 15/100 items"
    // const phaseProgressSpan = document.getElementById('phase-progress');     // e.g., "Phase: 3/5"

    let logConnectionAttemptMade = false;
    let logConnectionErrorDisplayed = false;
    const initialLogMessage = 'Attempting to connect to agent logs...';

    const updateStatus = (status, message = '') => {
        if (statusBadge) {
            statusBadge.textContent = status;
            statusBadge.className = 'badge'; // Reset classes
            switch (status.toLowerCase()) {
                case 'running':
                    statusBadge.classList.add('bg-primary');
                    if(startButton) startButton.disabled = true;
                    if(stopButton) stopButton.disabled = false;
                    break;
                case 'stopping':
                    statusBadge.classList.add('bg-warning', 'text-dark');
                    if(startButton) startButton.disabled = true;
                    if(stopButton) stopButton.disabled = true; // Disable while stopping
                    break;
                case 'idle':
                    statusBadge.classList.add('bg-secondary');
                     if(startButton) startButton.disabled = false;
                     if(stopButton) stopButton.disabled = true;
                    break;
                case 'failed':
                    statusBadge.classList.add('bg-danger');
                    if(startButton) startButton.disabled = false;
                    if(stopButton) stopButton.disabled = true;
                    break;
                default:
                    statusBadge.classList.add('bg-info', 'text-dark');
            }
        }
        if (statusMessage) {
            statusMessage.textContent = message || `Agent is ${status}.`;
        }
    };

    const appendLog = (message, isSystemMessage = false) => {
        if (liveLogContent) {
            // If it's the very first message and it's the initial placeholder, replace it.
            // Or if it's a system message (connect/disconnect) that should clear old errors.
            if (liveLogContent.textContent === initialLogMessage && (isSystemMessage || !logConnectionErrorDisplayed)) {
                liveLogContent.textContent = ''; // Clear "Attempting to connect..."
            } else if (isSystemMessage && (logConnectionErrorDisplayed || liveLogContent.textContent.includes('--- Log connection error') || liveLogContent.textContent.includes('--- Log connection lost'))) {
                // If it's a system message like "connected" and errors were present, clear the whole log area first
                liveLogContent.textContent = '';
            }
            liveLogContent.textContent += message + '\n';
            const logOutputDiv = liveLogContent.closest('.log-output');
            if (logOutputDiv) {
                logOutputDiv.scrollTop = logOutputDiv.scrollHeight;
            }
        }
    };
    
    // Set initial message
    if (liveLogContent) {
        liveLogContent.textContent = initialLogMessage;
    }

    // Agent Socket Handlers
    agentSocket.on('connect', () => {
        console.log('Agent socket connected');
        agentSocket.emit('get_status'); // Request initial status on connect
    });

    agentSocket.on('disconnect', () => {
        console.log('Agent socket disconnected');
        updateStatus('Offline', 'Connection lost to agent server.');
    });

    agentSocket.on('status_update', (data) => {
        console.log('Status update received:', data);
        updateStatus(data.status, data.message);
         // Reset progress on idle/failed/finished
         if (['idle', 'failed'].includes(data.status.toLowerCase())) {
            if(progressCountSpan) progressCountSpan.textContent = '0';
            if(progressTotalSpan) progressTotalSpan.textContent = '0';
            if(currentPhaseSpan) currentPhaseSpan.textContent = 'Idle';
            if(currentItemIdSpan) currentItemIdSpan.textContent = '';
            if(etaSpan) etaSpan.textContent = '--:--:--';
        }
    });

    agentSocket.on('progress_update', (data) => {
        console.debug('Progress update:', data);
        if(progressCountSpan) progressCountSpan.textContent = data.processed_count || '0'; // Processed in current batch
        if(progressTotalSpan) progressTotalSpan.textContent = data.total_items || '0';     // Total in current batch
        
        let phaseText = data.current_phase || 'N/A';
        if (data.total_phases && data.current_phase_num) {
            phaseText += ` (${data.current_phase_num}/${data.total_phases})`;
        }
        if(currentPhaseSpan) currentPhaseSpan.textContent = phaseText;

        if(currentItemIdSpan) currentItemIdSpan.textContent = data.current_item_id ? `(Item: ${data.current_item_id})` : '';
        if(etaSpan) etaSpan.textContent = data.eta || '--:--:--';

        // Example for new overall progress display elements (if you add them to HTML)
        // if(overallProgressSpan && data.overall_total_items > 0) {
        //     overallProgressSpan.textContent = `Overall: ${data.overall_items_processed}/${data.overall_total_items} items`;
        // } else if (overallProgressSpan) {
        //     overallProgressSpan.textContent = "";
        // }
        // if(phaseProgressSpan && data.total_phases > 0) {
        //     phaseProgressSpan.textContent = `Phase: ${data.current_phase_num}/${data.total_phases}`;
        // } else if (phaseProgressSpan) {
        //      phaseProgressSpan.textContent = "";
        // }
    });

    agentSocket.on('connect_error', (err) => {
        console.error('Agent socket connection error:', err);
        updateStatus('Error', 'Could not connect to agent socket.');
    });

    // Log Socket Handlers
    logSocket.on('connect', () => {
        console.log('Log socket connected');
        // System message, will clear previous errors or initial message
        appendLog('--- Log connection established ---', true); 
        logConnectionAttemptMade = true;
        logConnectionErrorDisplayed = false; 
    });

    logSocket.on('disconnect', (reason) => {
        console.log('Log socket disconnected:', reason);
        // System message
        if (!logConnectionErrorDisplayed) { 
            appendLog(`--- Log connection lost: ${reason} ---`, true);
        }
        logConnectionErrorDisplayed = true; 
    });

    logSocket.on('connect_error', (err) => {
        console.error('Log connection error:', err);
        logConnectionAttemptMade = true;

        if (!logConnectionErrorDisplayed) { 
            let errorMessage = '--- Log connection error';
            if (err && err.message) {
                errorMessage += `: ${err.message}`;
            } else if (err && err.type && err.description && err.description.message) {
                errorMessage += `: ${err.type} - ${err.description.message}`;
            } else if (err && err.type) {
                errorMessage += `: ${err.type}`;
            }
            errorMessage += '. Will attempt to reconnect. ---';
            // System message
            appendLog(errorMessage, true); 
            logConnectionErrorDisplayed = true;
        }
    });

    logSocket.on('new_log', (data) => {
        // If an error message was on screen, this new log implies re-connection.
        // The appendLog function with isSystemMessage=true would have cleared it on 'connect'.
        // If 'connect' didn't fire but logs start appearing, we might still have an old error message.
        if (logConnectionErrorDisplayed || liveLogContent.textContent.includes('--- Log connection error') || liveLogContent.textContent.includes('--- Log connection lost')) {
            // Clear out old error/disconnect messages
            liveLogContent.textContent = ''; 
            appendLog('--- Log connection re-established (new data received) ---', true);
        }
        logConnectionErrorDisplayed = false; 
        appendLog(data.log_line); // Not a system message
    });

    // Button Listeners
    if (startButton) {
        startButton.addEventListener('click', () => {
            console.log('Start button clicked');
            
            // Get selected run mode
            let selectedRunMode = 'Full'; // Default
            const runModeRadios = document.querySelectorAll('input[name="runMode"]');
            for (const radio of runModeRadios) {
                if (radio.checked) {
                    selectedRunMode = radio.value;
                    break;
                }
            }

            const runPreferences = {
                // Run mode
                run_only_phase: selectedRunMode, // "Full" or "PhaseName"
                // Skip flags
                skip_fetch: skipFetchCheckbox ? skipFetchCheckbox.checked : false,
                skip_git: skipGitCheckbox ? skipGitCheckbox.checked : false,
                // Force flags
                force_recache: forceRecacheCheckbox ? forceRecacheCheckbox.checked : false,
                force_reinterpret: forceReinterpretCheckbox ? forceReinterpretCheckbox.checked : false,
                force_recategorize: forceRecategorizeCheckbox ? forceRecategorizeCheckbox.checked : false,
                force_regenerate: forceRegenerateCheckbox ? forceRegenerateCheckbox.checked : false,
            };
            console.log('Sending run preferences:', runPreferences); // Log preferences being sent
            agentSocket.emit('start_agent', runPreferences);
            updateStatus('Starting', 'Agent start requested...');
            startButton.disabled = true; // Disable immediately
        });
    }

    if (stopButton) {
        stopButton.addEventListener('click', () => {
            console.log('Stop button clicked');
            agentSocket.emit('stop_agent');
            updateStatus('Stopping', 'Agent stop requested...');
            stopButton.disabled = true; // Disable immediately
        });
    }

    // Add listeners for preference checkboxes to save state
    if (skipFetchCheckbox) {
        skipFetchCheckbox.addEventListener('change', (event) => {
            saveUIStateKey('skip_fetch', event.target.checked);
        });
    }
    if (skipGitCheckbox) {
        skipGitCheckbox.addEventListener('change', (event) => {
            saveUIStateKey('skip_git', event.target.checked);
        });
    }
    if (forceRecacheCheckbox) {
        forceRecacheCheckbox.addEventListener('change', (event) => {
            saveUIStateKey('force_recache', event.target.checked);
        });
    }
    if (forceReinterpretCheckbox) {
        forceReinterpretCheckbox.addEventListener('change', (event) => {
            saveUIStateKey('force_reinterpret', event.target.checked);
        });
    }
    if (forceRecategorizeCheckbox) {
        forceRecategorizeCheckbox.addEventListener('change', (event) => {
            saveUIStateKey('force_recategorize', event.target.checked);
        });
    }
    if (forceRegenerateCheckbox) {
        forceRegenerateCheckbox.addEventListener('change', (event) => {
            saveUIStateKey('force_regenerate', event.target.checked);
        });
    }

    // Add listeners for Run Mode radio buttons to save state
    document.querySelectorAll('input[name="runMode"]').forEach(radio => {
        radio.addEventListener('change', (event) => {
            if (event.target.checked) {
                saveUIStateKey('run_mode', event.target.value);
            }
        });
    });

    // --- KB Tree (Placeholder Logic) ---
    // In a real implementation, fetch data via API or receive it from Flask template
    // and build the tree structure (e.g., using Bootstrap Collapse)
    console.log("KB Tree population would happen here.");

    // --- Initial Load ---
    loadUIState(); // Load saved UI prefs on page load

});
