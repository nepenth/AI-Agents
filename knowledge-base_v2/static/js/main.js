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
    const progressCountSpan = document.getElementById('progress-count');
    const progressTotalSpan = document.getElementById('progress-total');
    const currentPhaseSpan = document.getElementById('current-phase');
    const currentItemIdSpan = document.getElementById('current-item-id');
    const etaSpan = document.getElementById('eta');

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

    const appendLog = (message) => {
         if (liveLogContent) {
             // Initial connection message clear
             if (liveLogContent.textContent === 'Connecting to agent logs...') {
                 liveLogContent.textContent = '';
             }
             liveLogContent.textContent += message + '\n';
             // Auto-scroll to bottom
             const logOutputDiv = liveLogContent.closest('.log-output');
             if(logOutputDiv) {
                 logOutputDiv.scrollTop = logOutputDiv.scrollHeight;
             }
         }
     };

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
        console.debug('Progress update:', data); // Debug level for potentially frequent messages
        if(progressCountSpan) progressCountSpan.textContent = data.processed_count || '0';
        if(progressTotalSpan) progressTotalSpan.textContent = data.total_items || '0';
        if(currentPhaseSpan) currentPhaseSpan.textContent = data.current_phase || 'N/A';
        if(currentItemIdSpan) currentItemIdSpan.textContent = data.current_item_id ? `(ID: ${data.current_item_id})` : '';
        if(etaSpan) etaSpan.textContent = data.eta || '--:--:--';
    });

    agentSocket.on('connect_error', (err) => {
        console.error('Agent socket connection error:', err);
        updateStatus('Error', 'Could not connect to agent socket.');
    });

    // Log Socket Handlers
     logSocket.on('connect', () => {
         console.log('Log socket connected');
         if(liveLogContent) liveLogContent.textContent = 'Connected to logs. Waiting for messages...\n';
     });

    logSocket.on('disconnect', () => {
         console.log('Log socket disconnected');
         appendLog('--- Log stream disconnected ---');
     });

    logSocket.on('log_message', (data) => {
         console.log('Log message:', data);
         appendLog(data.data); // Assuming data = { data: "log line" }
     });

    logSocket.on('connect_error', (err) => {
        console.error('Log socket connection error:', err);
        appendLog(`--- Log connection error: ${err.message} ---`);
    });


    // Button Listeners
    if (startButton) {
        startButton.addEventListener('click', () => {
            console.log('Start button clicked');
            // Collect preferences from all relevant checkboxes
            const runPreferences = {
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

    // --- KB Tree (Placeholder Logic) ---
    // In a real implementation, fetch data via API or receive it from Flask template
    // and build the tree structure (e.g., using Bootstrap Collapse)
    console.log("KB Tree population would happen here.");

});
