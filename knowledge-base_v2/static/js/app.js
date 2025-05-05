document.addEventListener('DOMContentLoaded', () => {
    // --- SocketIO Connections ---
    const agentSocket = io('/agent'); // Connect to agent namespace
    const logSocket = io('/logs');   // Connect to logs namespace

    // --- DOM Elements (Get references to buttons, status divs, log area, checkboxes) ---
    const statusDiv = document.getElementById('agent-status');
    const statusMsgDiv = document.getElementById('agent-status-message');
    const startButton = document.getElementById('start-agent-btn');
    const stopButton = document.getElementById('stop-agent-btn');
    const logArea = document.getElementById('log-area');
    const forceRecacheCheckbox = document.getElementById('force-recache');
    // ... other preference checkboxes ...

    let agentState = 'unknown'; // Track current state

    // --- UI State Persistence ---
    const uiStateKey = 'knowledgeAgentUIState';

    // Function to load state from server/localStorage
    async function loadUIState() {
        try {
            // 1. Try loading from server first
            const response = await fetch('/api/ui-state');
            if (response.ok) {
                const serverState = await response.json();
                localStorage.setItem(uiStateKey, JSON.stringify(serverState)); // Update local cache
                applyUIState(serverState);
                console.log("Loaded UI state from server:", serverState);
                return;
            } else {
                 console.error("Failed to load UI state from server:", response.status);
            }
        } catch (err) {
            console.error("Error fetching UI state from server:", err);
        }
        // 2. Fallback to localStorage if server fails
        const localState = JSON.parse(localStorage.getItem(uiStateKey) || '{}');
        applyUIState(localState);
        console.log("Loaded UI state from localStorage:", localState);
    }

    // Function to apply loaded state to UI elements
    function applyUIState(state) {
        if (forceRecacheCheckbox) {
            forceRecacheCheckbox.checked = state.force_recache === true;
        }
        // ... apply other states ...
    }

    // Function to save a single key-value pair
    async function saveUIStateKey(key, value) {
        // 1. Update local storage immediately
        const currentState = JSON.parse(localStorage.getItem(uiStateKey) || '{}');
        currentState[key] = value;
        localStorage.setItem(uiStateKey, JSON.stringify(currentState));

        // 2. Send update to server (fire and forget, or handle errors)
        try {
             await fetch(`/api/ui-state/${key}`, {
                 method: 'PUT',
                 headers: { 'Content-Type': 'application/json' },
                 body: JSON.stringify({ value: value })
             });
             console.log(`Saved UI state key ${key} to server.`);
        } catch (err) {
             console.error(`Error saving UI state key ${key} to server:`, err);
             // Optionally revert local state or show error
        }
    }

    // --- SocketIO Event Handlers ---
    agentSocket.on('connect', () => {
        console.log('Connected to /agent namespace');
        agentSocket.emit('get_status'); // Request status on connect/reconnect
    });

    agentSocket.on('disconnect', () => {
        console.log('Disconnected from /agent namespace');
        updateStatusDisplay('disconnected', 'Connection lost...');
    });

    agentSocket.on('status_update', (data) => {
        console.log('Status update received:', data);
        agentState = data.status || 'unknown';
        updateStatusDisplay(agentState, data.message || '');
    });

    logSocket.on('connect', () => {
        console.log('Connected to /logs namespace');
        // Optionally fetch recent logs on connect?
        // fetchRecentLogs();
    });

     logSocket.on('log_message', (data) => {
         // console.log('Log message:', data);
         appendLogMessage(data.level, data.message);
     });


    // --- UI Update Functions ---
    function updateStatusDisplay(status, message) {
        if (!statusDiv || !statusMsgDiv) return;
        statusDiv.textContent = `Status: ${status}`;
        statusDiv.className = `status status-${status}`; // Use CSS classes for styling
        statusMsgDiv.textContent = message || '';

        // Enable/disable buttons based on state
        if (startButton) startButton.disabled = (status === 'running' || status === 'stopping');
        if (stopButton) stopButton.disabled = (status !== 'running');
    }

    function appendLogMessage(level, message) {
        if (!logArea) return;
        const logEntry = document.createElement('div');
        logEntry.classList.add('log-entry', `log-${level.toLowerCase()}`);
        // Basic HTML escaping (replace with a proper library if needed)
        const escapedMessage = message.replace(/</g, "&lt;").replace(/>/g, "&gt;");
        logEntry.innerHTML = `[${level}] ${escapedMessage}`; // Use innerHTML carefully
        logArea.appendChild(logEntry);
        // Auto-scroll to bottom
        logArea.scrollTop = logArea.scrollHeight;
    }

     // --- Button/Control Event Listeners ---
     if (startButton) {
         startButton.addEventListener('click', () => {
             console.log('Start button clicked');
             // Gather preferences from UI
             const preferences = {
                 force_recache: forceRecacheCheckbox ? forceRecacheCheckbox.checked : false,
                 // ... get other preferences ...
             };
             agentSocket.emit('start_agent', { preferences: preferences });
         });
     }

     if (stopButton) {
         stopButton.addEventListener('click', () => {
             console.log('Stop button clicked');
             agentSocket.emit('stop_agent');
         });
     }

     // Add listeners for preference checkboxes to save state
     if (forceRecacheCheckbox) {
          forceRecacheCheckbox.addEventListener('change', (event) => {
              saveUIStateKey('force_recache', event.target.checked);
          });
     }
     // ... listeners for other checkboxes ...


    // --- Initial Load ---
    loadUIState(); // Load saved UI prefs on page load

}); // End DOMContentLoaded
