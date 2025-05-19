document.addEventListener('DOMContentLoaded', function () {
    const socket = io();

    // UI Elements
    const liveLogsUl = document.getElementById('liveLogsUl');
    const clearLogsButton = document.getElementById('clearLogsButton');
    const agentExecutionPlanUl = document.getElementById('agentExecutionPlan');
    const runAgentBtn = document.getElementById('runAgentButton');
    const stopAgentBtn = document.getElementById('stopAgentButton');
    
    const gpuUsageElement = document.getElementById('gpuUsage');
    const gpuMemoryElement = document.getElementById('gpuMemory');
    const gpuTemperatureElement = document.getElementById('gpuTemperature');
    const gpuLoadElement = document.getElementById('gpuLoad');

    const darkModeToggle = document.getElementById('darkModeToggle');
    const themeStylesheet = document.getElementById('theme-stylesheet');

    // Preference form controls
    const controlInputs = {
        skip_fetch_bookmarks: document.getElementById('skipFetchBookmarks'),
        skip_process_content: document.getElementById('skipProcessContent'),
        skip_readme_generation: document.getElementById('skipReadmeGeneration'),
        skip_git_push: document.getElementById('skipGitPush'),
        force_recache_tweets: document.getElementById('forceRecacheTweets'),
        force_reprocess_content: document.getElementById('forceReprocessContent')
    };

    // State variables
    let agentIsRunning = false;
    let currentPhaseId = null; // Stores the ID of the currently active main phase
    let activeRunPreferences = null; // Stores preferences of the current/last run

    // --- Theme Initialization (Dark Mode) ---
    function initializeTheme() {
        const darkModeToggleInput = document.getElementById('darkModeToggle'); // Renamed to avoid conflict
        if (!darkModeToggleInput) {
            console.warn("Dark mode toggle input not found.");
            return;
        }

        let preferredTheme = 'light'; // Default theme
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
            // Fallback to default 'light' theme already set
        }

        document.documentElement.setAttribute('data-bs-theme', preferredTheme);
        darkModeToggleInput.checked = (preferredTheme === 'dark');

        darkModeToggleInput.addEventListener('change', function () {
            const newTheme = this.checked ? 'dark' : 'light';
            document.documentElement.setAttribute('data-bs-theme', newTheme);
            // Save the preference using the existing saveClientPreferences function
            // which already reads the toggle's state.
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
        liveLogsUl.scrollTop = liveLogsUl.scrollHeight; // Auto-scroll
    }

    if (clearLogsButton) {
        clearLogsButton.addEventListener('click', () => {
            if (liveLogsUl) liveLogsUl.innerHTML = '';
            addLogMessage('Live logs cleared by user.', 'INFO');
        });
    }

    // --- Agent Run Button State & Status UI --- Changed name
    function updateAgentStatusUI() { 
        const isRunning = agentIsRunning || (activeRunPreferences && activeRunPreferences.is_running);
        const agentRunStatusSpan = document.getElementById('agentRunStatus');

        if (runAgentBtn) {
            runAgentBtn.disabled = isRunning;
            runAgentBtn.textContent = isRunning ? 'Agent Running...' : 'Run Agent';
            runAgentBtn.classList.toggle('btn-secondary', isRunning);
            runAgentBtn.classList.toggle('btn-primary', !isRunning);
        }
        if (stopAgentBtn) {
            stopAgentBtn.disabled = !isRunning;
            stopAgentBtn.classList.toggle('btn-danger', isRunning);
            stopAgentBtn.classList.toggle('btn-secondary', !isRunning);
        }
        if (agentRunStatusSpan) {
            agentRunStatusSpan.textContent = isRunning ? 'Running' : 'Not Running';
            agentRunStatusSpan.className = isRunning ? 'text-success fw-bold' : 'text-muted'; // Added styling
        }

        // Disable preference form controls if agent is running
        const formControlsToDisable = Object.values(controlInputs).filter(el => el);
        formControlsToDisable.forEach(control => {
            if (control) control.disabled = isRunning;
        });
    }

    // --- Agent Execution Plan UI Update ---
    function updatePhaseInExecutionPlan(phaseIdToUpdate, statusToSet, messageToSet, isSubStepUpdate = false, fullPlanStatuses = null) {
        const agentPhasesList = document.getElementById('agentPhasesList');
        if (!agentPhasesList) return;

        const applyStatusToElement = (el, status, message) => {
            if (!el) return;
            el.classList.remove('status-pending', 'status-will-run', 'status-active', 'status-completed', 'status-skipped', 'status-error', 'phase-hidden-by-mode');
            const statusSpan = el.querySelector('.phase-status');

            if (status) {
                el.classList.add(`status-${status}`);
            }
            if (message && statusSpan) {
                statusSpan.textContent = message;
            } else if (statusSpan && !message) {
                // Set default message based on status if no specific message provided
                switch (status) {
                    case 'pending': statusSpan.textContent = 'Pending'; break;
                    case 'will-run': statusSpan.textContent = 'Will run'; break;
                    case 'active': statusSpan.textContent = 'Running...'; break;
                    case 'completed': statusSpan.textContent = 'Completed'; break;
                    case 'skipped': statusSpan.textContent = 'Skipped'; break;
                    case 'error': statusSpan.textContent = 'Error'; break;
                    default: statusSpan.textContent = '';
                }
            }
        };

        if (fullPlanStatuses) {
            // Iterate and update all known plan items based on full server state
            for (const [phaseId, phaseInfo] of Object.entries(fullPlanStatuses)) {
                const phaseElement = agentPhasesList.querySelector(`[data-phase-id="${phaseId}"]`);
                if (phaseElement) {
                    applyStatusToElement(phaseElement, phaseInfo.status, phaseInfo.message);
                }
            }
        } else if (phaseIdToUpdate) {
            // Update a single specified phase
            const phaseElement = agentPhasesList.querySelector(`[data-phase-id="${phaseIdToUpdate}"]`);
            if (phaseElement) {
                applyStatusToElement(phaseElement, statusToSet, messageToSet);
            }
        }
        // Special handling for current phase details box
        const currentPhaseDetailsBox = document.getElementById('current-phase-details');
        if (currentPhaseDetailsBox) {
            if (agentIsRunning && currentPhaseId && messageToSet) {
                 let activePhaseName = '';
                 const activePhaseEl = agentPhasesList.querySelector(`[data-phase-id="${currentPhaseId}"] .phase-name`);
                 if(activePhaseEl) activePhaseName = activePhaseEl.textContent.trim() + ": ";
                 currentPhaseDetailsBox.textContent = activePhaseName + messageToSet;
            } else if (!agentIsRunning) {
                 currentPhaseDetailsBox.textContent = 'Agent Idle';
            }
        }
    }
    
    function updatePhaseProgress(phaseId, data) {
        // This function is now primarily for formatting the detailed progress message.
        // The actual class setting for status (active, completed, etc.) should be handled by
        // updatePhaseInExecutionPlan based on 'agent_phase_update' or 'initial_status_and_git_config' data.

        let progressMessage = data.status_message || ''; // Default to server-provided status message

        if (data.total_count > 0) {
            progressMessage = `(${data.processed_count}/${data.total_count}) ${progressMessage}`;
        }
        if (data.error_count > 0) {
            progressMessage += ` - ${data.error_count} errors`;
        }

        // The messageToSet for updatePhaseInExecutionPlan will use this formatted progressMessage
        // when an update comes for an active phase.
        // The statusToSet (e.g., 'active', 'completed') will come from the broader event data.
        // Example: socket.on('agent_phase_update', ... updatePhaseInExecutionPlan(data.phase_id, data.status, progressMessage) ...)
        return progressMessage; 
    }

    // --- Preferences Handling ---
    function getPreferencesForServer() {
        const prefs = {};
        prefs.run_mode = 'full_pipeline'; // Always full_pipeline now
        prefs.force_recache_tweets = controlInputs.force_recache_tweets ? controlInputs.force_recache_tweets.checked : false;
        prefs.force_reprocess_content = controlInputs.force_reprocess_content ? controlInputs.force_reprocess_content.checked : false;

        // These depend on run_mode - now they are direct controls
        prefs.skip_fetch_bookmarks = controlInputs.skip_fetch_bookmarks ? controlInputs.skip_fetch_bookmarks.checked : false;
        prefs.skip_process_content = controlInputs.skip_process_content ? controlInputs.skip_process_content.checked : false;
        prefs.skip_readme_generation = controlInputs.skip_readme_generation ? controlInputs.skip_readme_generation.checked : false;
        prefs.skip_git_push = controlInputs.skip_git_push ? controlInputs.skip_git_push.checked : false;

        return prefs;
    }

    function saveClientPreferences() {
        const clientPrefs = {
            skip_fetch_bookmarks: controlInputs.skip_fetch_bookmarks ? controlInputs.skip_fetch_bookmarks.checked : false,
            skip_process_content: controlInputs.skip_process_content ? controlInputs.skip_process_content.checked : false,
            skip_readme_generation: controlInputs.skip_readme_generation ? controlInputs.skip_readme_generation.checked : false,
            skip_git_push: controlInputs.skip_git_push ? controlInputs.skip_git_push.checked : false,
            force_recache_tweets: controlInputs.force_recache_tweets ? controlInputs.force_recache_tweets.checked : false,
            force_reprocess_content: controlInputs.force_reprocess_content ? controlInputs.force_reprocess_content.checked : false,
            darkMode: darkModeToggle ? darkModeToggle.checked : false
        };
        localStorage.setItem('agentClientPreferences', JSON.stringify(clientPrefs));
    }

    function loadClientPreferences(prefsToLoad = null) {
        const localPrefsRaw = localStorage.getItem('agentClientPreferences');
        let clientPrefs = prefsToLoad;

        if (!clientPrefs && localPrefsRaw) { 
            try {
                clientPrefs = JSON.parse(localPrefsRaw);
            } catch (e) {
                console.error("Error parsing client preferences from localStorage", e);
                clientPrefs = {}; 
            }
        } else if (!clientPrefs) {
            clientPrefs = {}; 
        }
        
        // Apply checkbox states from clientPrefs
        if (controlInputs.skip_fetch_bookmarks && clientPrefs.hasOwnProperty('skip_fetch_bookmarks')) controlInputs.skip_fetch_bookmarks.checked = clientPrefs.skip_fetch_bookmarks;
        else if (controlInputs.skip_fetch_bookmarks) controlInputs.skip_fetch_bookmarks.checked = false; // Default to not skipped

        if (controlInputs.skip_process_content && clientPrefs.hasOwnProperty('skip_process_content')) controlInputs.skip_process_content.checked = clientPrefs.skip_process_content;
        else if (controlInputs.skip_process_content) controlInputs.skip_process_content.checked = false;

        if (controlInputs.skip_readme_generation && clientPrefs.hasOwnProperty('skip_readme_generation')) controlInputs.skip_readme_generation.checked = clientPrefs.skip_readme_generation;
        else if (controlInputs.skip_readme_generation) controlInputs.skip_readme_generation.checked = false;

        if (controlInputs.skip_git_push && clientPrefs.hasOwnProperty('skip_git_push')) controlInputs.skip_git_push.checked = clientPrefs.skip_git_push;
        else if (controlInputs.skip_git_push) controlInputs.skip_git_push.checked = false;

        if (controlInputs.force_recache_tweets && clientPrefs.hasOwnProperty('force_recache_tweets')) controlInputs.force_recache_tweets.checked = clientPrefs.force_recache_tweets;
        else if (controlInputs.force_recache_tweets) controlInputs.force_recache_tweets.checked = false;

        if (controlInputs.force_reprocess_content && clientPrefs.hasOwnProperty('force_reprocess_content')) controlInputs.force_reprocess_content.checked = clientPrefs.force_reprocess_content;
        else if (controlInputs.force_reprocess_content) controlInputs.force_reprocess_content.checked = false;
            
        const currentPrefsForViz = getPreferencesForServer(); 
        updateExecutionPlanVisualization(currentPrefsForViz); 
    }
    
    function updateExecutionPlanVisualization(preferences) {
        console.log("Updating execution plan visualization (Restored Logic) with prefs:", preferences);
        const agentPhasesList = document.getElementById('agentPhasesList');
        if (!agentPhasesList) return;

        const phaseConfigs = {
            'initialization': { el: agentPhasesList.querySelector('[data-phase-id="initialization"]'), skipKey: null },
            'fetch_bookmarks': { el: agentPhasesList.querySelector('[data-phase-id="fetch_bookmarks"]'), skipKey: 'skip_fetch_bookmarks' },
            'content_processing_overall': { el: agentPhasesList.querySelector('[data-phase-id="content_processing_overall"]'), skipKey: 'skip_process_content' },
            'subphase_cp_cache': { el: agentPhasesList.querySelector('[data-phase-id="subphase_cp_cache"]'), parent: 'content_processing_overall' },
            'subphase_cp_media': { el: agentPhasesList.querySelector('[data-phase-id="subphase_cp_media"]'), parent: 'content_processing_overall' },
            'subphase_cp_llm': { el: agentPhasesList.querySelector('[data-phase-id="subphase_cp_llm"]'), parent: 'content_processing_overall' },
            'subphase_cp_kbitem': { el: agentPhasesList.querySelector('[data-phase-id="subphase_cp_kbitem"]'), parent: 'content_processing_overall' },
            'subphase_cp_db': { el: agentPhasesList.querySelector('[data-phase-id="subphase_cp_db"]'), parent: 'content_processing_overall' },
            'readme_generation': { el: agentPhasesList.querySelector('[data-phase-id="readme_generation"]'), skipKey: 'skip_readme_generation' },
            'git_sync': { el: agentPhasesList.querySelector('[data-phase-id="git_sync"]'), skipKey: 'skip_git_push' },
            'cleanup': { el: agentPhasesList.querySelector('[data-phase-id="cleanup"]'), skipKey: null }
        };

        for (const phaseId in phaseConfigs) {
            const config = phaseConfigs[phaseId];
            if (!config.el) {
                console.warn("Config element not found for phaseId:", phaseId);
                continue;
            }

            const statusSpan = config.el.querySelector('.phase-status');
            const optionalInfoSpan = config.el.querySelector('.optional-phase-info'); 
            
            config.el.classList.remove('status-pending', 'status-will-run', 'status-skipped', 'status-active', 'status-completed', 'status-error');
            
            if (statusSpan) statusSpan.textContent = '';
            if (optionalInfoSpan) optionalInfoSpan.textContent = ''; 

            let isSkippedByOwnCheckbox = config.skipKey && preferences[config.skipKey];
            let effectiveWillRun;
            let statusText = '';
            let statusClass = '';

            if (config.parent) { 
                const parentConfig = phaseConfigs[config.parent];
                if (!parentConfig || !parentConfig.el) {
                    console.warn("Parent config element not found for subphase:", phaseId);
                    continue;
                }
                // A sub-phase runs if its parent runs. Parent's skipKey determines its status.
                const parentIsSkipped = parentConfig.skipKey && preferences[parentConfig.skipKey];
                effectiveWillRun = !parentIsSkipped;
                if (parentIsSkipped) {
                    statusClass = 'status-skipped';
                    statusText = 'Skipped (parent)';
                } else {
                    statusClass = 'status-will-run';
                    statusText = 'Will run'; 
                }
            } else { // Main phases (and phases without a parent like initialization/cleanup)
                effectiveWillRun = !isSkippedByOwnCheckbox;
                if (isSkippedByOwnCheckbox) {
                    statusClass = 'status-skipped';
                    statusText = 'Skipped by selection';
                } else {
                    statusClass = 'status-will-run';
                    statusText = 'Will run';
                }
            }
            
            config.el.classList.add(statusClass);
            if (statusSpan) statusSpan.textContent = statusText;

            if (config.el.classList.contains('optional-phase') && optionalInfoSpan) {
                 if (statusClass === 'status-skipped'){
                    optionalInfoSpan.textContent = '(Skipped)';
                 } else if (statusClass === 'status-will-run') {
                    optionalInfoSpan.textContent = '(Will Run)'; 
                 }
            }
        }

        const contentProcessingSubphases = document.getElementById('content-processing-subphases');
        if (contentProcessingSubphases) {
            const overallProcessingConfig = phaseConfigs['content_processing_overall'];
            if (overallProcessingConfig && overallProcessingConfig.el) {
                const overallWillRun = overallProcessingConfig.el.classList.contains('status-will-run');
                contentProcessingSubphases.style.display = overallWillRun ? '' : 'none';
            } else {
                contentProcessingSubphases.style.display = 'none'; // Hide if parent config is missing
            }
        }
    }

    if (runAgentBtn) {
        runAgentBtn.addEventListener('click', () => {
            const preferences = getPreferencesForServer();
            addLogMessage(`Requesting to run agent with preferences: ${JSON.stringify(preferences)}`, 'INFO');
            socket.emit('run_agent', { preferences: preferences });
        });
    }

    if (stopAgentBtn) {
        stopAgentBtn.addEventListener('click', () => {
            addLogMessage('Requesting to stop agent.', 'WARN');
            socket.emit('stop_agent');
        });
    }

    // --- Socket.IO Event Handlers ---
    socket.on('connect', () => {
        addLogMessage('Connected to server via Socket.IO.', 'INFO');
        // Server will emit 'initial_status_and_git_config' automatically.
    });

    socket.on('disconnect', () => {
        addLogMessage('Disconnected from server.', 'WARN');
        // Optionally gray out controls or show a disconnected status
    });

    socket.on('log', function(data) {
        addLogMessage(data.message, data.level);
    });

    socket.on('initial_status_and_git_config', function(data) {
        addLogMessage('Received initial agent status and Git config.', 'DEBUG');
        console.log("Initial status and Git config data:", data);

        agentIsRunning = data.agent_is_running;
        currentPhaseId = data.current_phase_id;
        activeRunPreferences = data.active_run_preferences || null;

        // Load checkbox states. If agent is running, use its preferences, else use local storage.
        // updateAgentStatusUI will disable them if agentIsRunning.
        if (agentIsRunning && activeRunPreferences) {
            loadClientPreferences(activeRunPreferences);
        } else { // Else, use local storage or defaults
            loadClientPreferences(); 
        }
        updateAgentStatusUI(); // Updates buttons, status text, and disables/enables form controls

        // Determine how to render the execution plan:
        // Highest priority: If agent is running and server provides a live plan.
        if (agentIsRunning && data.plan_statuses && Object.keys(data.plan_statuses).length > 0) {
            console.log("Agent is running. Applying full plan from server:", data.plan_statuses);
            updatePhaseInExecutionPlan(null, null, null, false, data.plan_statuses);
        } else {
            // Fallback: Agent is NOT running, OR it is running but server didn't send a valid plan.
            // In these cases, visualize based on current checkbox selections (i.e., what a *new* run would look like).
            console.log("Agent not running or no valid plan_statuses from server for active run. Visualizing based on current control preferences.");
            const currentPrefsForViz = getPreferencesForServer(); // Gets values from checkboxes
            updateExecutionPlanVisualization(currentPrefsForViz);
        }

        // This part updates the "Current Phase Details" box with the specific step message.
        if (agentIsRunning && data.current_phase_id && data.current_step_in_current_phase_progress_message) {
             updatePhaseInExecutionPlan(
                data.current_phase_id,
                'active', // The phase itself should be marked 'active' in plan_statuses
                data.current_step_in_current_phase_progress_message, // This is the more detailed message for the box
                true // Indicates it's updating the details box / current sub-step message
            );
        }

        // Git config info
        const gitSshCommandEl = document.getElementById('gitSshCommand');
        const gitRemoteNameEl = document.getElementById('gitRemoteName');
        const gitBranchNameEl = document.getElementById('gitBranchName');
        if (gitSshCommandEl) gitSshCommandEl.textContent = data.git_ssh_command || 'Not set';
        if (gitRemoteNameEl) gitRemoteNameEl.textContent = data.git_remote_name || 'Not set';
        if (gitBranchNameEl) gitBranchNameEl.textContent = data.git_branch_name || 'Not set';

        // Log History - Process historical logs sent from the server 
        if (data.log_history && Array.isArray(data.log_history) && data.log_history.length > 0) {
            // Clear existing logs if we have historical ones to show
            if (liveLogsUl) liveLogsUl.innerHTML = '';
            
            // Add a header for historical logs
            addLogMessage('--- Begin historical logs from current run ---', 'INFO');
            
            // Add all the historical logs
            data.log_history.forEach(logEntry => {
                if (logEntry && logEntry.message) {
                    addLogMessage(logEntry.message, logEntry.level || 'INFO');
                }
            });
            
            // Add a separator after historical logs
            addLogMessage('--- End of historical logs ---', 'INFO');
            addLogMessage('Connected to server. New logs will appear below.', 'INFO');
        }
    });

    socket.on('agent_status', function(data) {
        console.log("Agent status update:", data);
        agentIsRunning = data.is_running;
        activeRunPreferences = data.active_run_preferences || null; // Store active run preferences

        updateAgentStatusUI(); // Changed from updateRunAgentButtonState
        // enableDisableInputsOnRunState(); // Removed, functionality integrated into updateAgentStatusUI

        if (agentIsRunning && activeRunPreferences) {
            console.log("Agent is running, attempting to restore execution plan state from activeRunPreferences.plan_statuses");
            // If agent is running, reconstruct the plan from server's idea of the current run.
            // The server should ideally send the full plan status.
            // The 'initial_status_and_git_config' event handles a more comprehensive initial setup.
            // This 'agent_status' might be more for simple running/not running updates.
            // Let's assume plan_statuses comes with initial_status or agent_phase_update.
            if (activeRunPreferences.plan_statuses) {
                 updatePhaseInExecutionPlan(null, null, null, false, activeRunPreferences.plan_statuses);
            } else {
                // If no plan_statuses, re-visualize based on loaded preferences (pre-run state)
                // This might be redundant if initial_status always provides plan_statuses
                 const prefsForViz = getPreferencesForServer();
                 updateExecutionPlanVisualization(prefsForViz);
            }
        } else if (!agentIsRunning) {
            // Agent stopped, reset currentPhaseId and clear details box
            currentPhaseId = null;
            const currentPhaseDetailsBox = document.getElementById('current-phase-details');
            if (currentPhaseDetailsBox) currentPhaseDetailsBox.textContent = 'Agent Idle';
            // Re-visualize based on current checkbox states for the next potential run
            const prefsForViz = getPreferencesForServer();
            updateExecutionPlanVisualization(prefsForViz);
        }
    });

    socket.on('agent_phase_update', function(data) {
        // Expected data: { phase_id, status, message, is_sub_step_update, 
        //                  processed_count, total_count, error_count, 
        //                  full_plan_statuses }
        console.log("Received agent_phase_update:", data);

        if (agentIsRunning && data.phase_id && !data.is_sub_step_update) {
            // Update currentPhaseId only for main phase changes (not sub-steps)
            // and only if the agent is actually running.
            currentPhaseId = data.phase_id; 
        } else if (agentIsRunning && data.phase_id && data.is_sub_step_update && !currentPhaseId) {
            // If we get a sub-step update but currentPhaseId is not set (e.g. page reload during sub-step)
            // try to infer it from the sub-step's phase_id if it implies a parent.
            // This is a heuristic. Better if server always anchors sub-steps to a known main phase.
            // For now, we'll rely on currentPhaseId being set by a main phase update.
        }


        // Create the payload for updatePhaseProgress formatter
        // data.message from server is the base status message for the item/event
        const progressDataForFormatter = {
            status_message: data.message, 
            processed_count: data.processed_count,
            total_count: data.total_count,
            error_count: data.error_count
        };
        
        // Generate the potentially detailed message string
        let detailedMessage = updatePhaseProgress(data.phase_id, progressDataForFormatter);

        // Pass this detailedMessage to updatePhaseInExecutionPlan.
        // data.status is the status for the list item (e.g., 'active', 'completed').
        // data.is_sub_step_update guides how updatePhaseInExecutionPlan behaves.
        // data.full_plan_statuses is used if it's a full plan refresh (typically not for sub-steps).
        
        if (data.is_sub_step_update) {
            // For sub-step updates, only update the specific phase.
            // The detailedMessage will be used by updatePhaseInExecutionPlan for the 
            // current-phase-details box and potentially the phase item's status span.
            updatePhaseInExecutionPlan(data.phase_id, data.status, detailedMessage, data.is_sub_step_update, null);
        } else {
            // For main phase updates or final summaries of sub-phases (where is_sub_step_update=false).
            // Here, data.full_plan_statuses might be relevant if the server sends it
            // to ensure the entire plan view is consistent with the server state.
            updatePhaseInExecutionPlan(data.phase_id, data.status, detailedMessage, data.is_sub_step_update, data.full_plan_statuses);
        }
    });
    
    socket.on('agent_run_completed', function(data) {
        addLogMessage(`Agent run completed. Summary: ${data.summary_message}`, 'INFO');
        agentIsRunning = data.is_running; 
        updateAgentStatusUI(); // Changed from updateRunAgentButtonState
        currentPhaseId = null; 
        activeRunPreferences = null; 

        if (data.plan_statuses) {
            updatePhaseInExecutionPlan(null, null, null, false, data.plan_statuses);
        }
        fetchKnowledgeBaseItems(); 
        loadClientPreferences(); // Reload local prefs and re-visualize for a new run
    });

    socket.on('progress_update', function(data) {
        // This event might be simplified or merged into 'agent_phase_update' if it always accompanies a phase status change.
        // For now, assume it provides detailed progress for the *currently active* phase.
        if (agentIsRunning && currentPhaseId && data.phase === currentPhaseId) {
            const detailedProgressMessage = updatePhaseProgress(currentPhaseId, data);
            updatePhaseInExecutionPlan(currentPhaseId, 'active', detailedProgressMessage, true);
        }
        
        // Overall progress bar (if you add one)
        // const overallProgressBar = document.getElementById('overallProgress');
        // const overallProgressText = document.getElementById('overallProgressText');
        // if (overallProgressBar && overallProgressText && data.total_count > 0) { ... }
    });

    socket.on('gpu_stats_update', function(data) {
        const gpuStatsContainer = document.getElementById('gpuStatsContainer');
        if (!gpuStatsContainer) return;

        if (data.error) {
            gpuStatsContainer.innerHTML = `
                <div class="alert alert-warning">
                    <i class="bi bi-exclamation-triangle me-2"></i>
                    ${data.error}
                </div>`;
            return;
        }

        if (!data.gpus || data.gpus.length === 0) {
            gpuStatsContainer.innerHTML = `
                <div class="alert alert-info">
                    <i class="bi bi-info-circle me-2"></i>
                    No GPU data available or monitoring disabled.
                </div>`;
            return;
        }

        let gpuCardsHTML = '';
        data.gpus.forEach((gpu, index) => {
            const utilization = gpu.utilization_gpu !== undefined ? parseFloat(gpu.utilization_gpu) : null;
            const memoryUsed = gpu.memory_used !== undefined ? parseFloat(gpu.memory_used) : null;
            const memoryTotal = gpu.memory_total !== undefined ? parseFloat(gpu.memory_total) : null;
            const memoryPercentage = (memoryUsed !== null && memoryTotal !== null && memoryTotal > 0) ? (memoryUsed / memoryTotal) * 100 : null;
            
            const tempC = gpu.temperature_gpu !== undefined ? parseFloat(gpu.temperature_gpu) : null;
            let tempClass = '';
            if (tempC !== null) {
                if (tempC >= 85) tempClass = 'text-danger fw-bold'; // Hot
                else if (tempC >= 70) tempClass = 'text-warning';    // Warm
                else tempClass = 'text-success';   // Cool
            }
            const tempDisplay = tempC ? `${tempC.toFixed(1)}°C` : 'N/A';

            const powerDraw = gpu.power_draw !== undefined && gpu.power_draw !== null ? `${gpu.power_draw.toFixed(1)}W` : 'N/A';
            const gfxClock = gpu.clocks_graphics !== undefined && gpu.clocks_graphics !== null ? `${gpu.clocks_graphics} MHz` : 'N/A';
            const memClock = gpu.clocks_memory !== undefined && gpu.clocks_memory !== null ? `${gpu.clocks_memory} MHz` : 'N/A';

            gpuCardsHTML += `
                <div class="col-md-${data.gpus.length > 2 ? '6' : (data.gpus.length === 2 ? '6' : '12')} col-lg-${data.gpus.length > 1 ? '6' : '12'} mb-3">
                    <div class="card h-100 gpu-card-item">
                        <div class="card-header">
                            <h6 class="card-title mb-0">
                                <i class="bi bi-gpu-card me-2"></i>
                                ${gpu.name || `GPU ${index}`}
                            </h6>
                        </div>
                        <div class="card-body">
                            <div class="mb-2">
                                <small class="text-muted d-block">GPU Utilization</small>
                                <div class="progress" style="height: 20px;" title="${utilization !== null ? utilization.toFixed(1) + '%' : 'N/A'}">
                                    <div class="progress-bar ${utilization >= 80 ? 'bg-danger' : (utilization >= 50 ? 'bg-warning' : 'bg-success')}" 
                                         role="progressbar" style="width: ${utilization !== null ? utilization : 0}%;" 
                                         aria-valuenow="${utilization !== null ? utilization : 0}" aria-valuemin="0" aria-valuemax="100">
                                         ${utilization !== null ? utilization.toFixed(1) + '%' : 'N/A'}
                                    </div>
                                </div>
                            </div>
                            <div class="mb-3">
                                <small class="text-muted d-block">Memory Usage (${memoryUsed !== null ? memoryUsed.toFixed(0) : 'N/A'}MB / ${memoryTotal !== null ? memoryTotal.toFixed(0) : 'N/A'}MB)</small>
                                <div class="progress" style="height: 20px;" title="${memoryPercentage !== null ? memoryPercentage.toFixed(1) + '%' : 'N/A'}">
                                    <div class="progress-bar ${memoryPercentage >= 85 ? 'bg-danger' : (memoryPercentage >= 60 ? 'bg-warning' : 'bg-info')}" 
                                         role="progressbar" style="width: ${memoryPercentage !== null ? memoryPercentage : 0}%;" 
                                         aria-valuenow="${memoryPercentage !== null ? memoryPercentage : 0}" aria-valuemin="0" aria-valuemax="100">
                                         ${memoryPercentage !== null ? memoryPercentage.toFixed(1) + '%' : ''}
                                    </div>
                                </div>
                            </div>
                            
                            <div class="row">
                                <div class="col-6 col-sm-4 mb-2">
                                    <small class="text-muted">Temperature</small>
                                    <div class="fw-bold ${tempClass}">${tempDisplay}</div>
                                </div>
                                <div class="col-6 col-sm-4 mb-2">
                                    <small class="text-muted">Power Draw</small>
                                    <div class="fw-bold">${powerDraw}</div>
                                </div>
                                 <div class="col-6 col-sm-4 mb-2">
                                    <small class="text-muted">Graphics Clock</small>
                                    <div class="fw-bold">${gfxClock}</div>
                                </div>
                                ${data.gpus.length === 1 ? `<div class="col-6 col-sm-4 mb-2">
                                    <small class="text-muted">Memory Clock</small>
                                    <div class="fw-bold">${memClock}</div>
                                </div>` : ''}
                            </div>
                             ${data.gpus.length > 1 && memClock !== 'N/A' ? `<div class="row"><div class="col-6 col-sm-4 mb-2">
                                    <small class="text-muted">Memory Clock</small>
                                    <div class="fw-bold">${memClock}</div>
                                </div></div>` : ''}
                        </div>
                    </div>
                </div>`;
        });

        gpuStatsContainer.innerHTML = `<div class="row">${gpuCardsHTML}</div>`;
    });

    // --- Knowledge Base Item Display ---
    const itemListUl = document.getElementById('itemList');
    const itemDetailDiv = document.getElementById('itemDetail');

    function fetchKnowledgeBaseItems() {
        if (!itemListUl) return;
        fetch('/api/kb_items')
            .then(response => response.json())
            .then(data => {
                itemListUl.innerHTML = ''; // Clear existing items
                if (data.length === 0) {
                    const li = document.createElement('li');
                    li.className = 'list-group-item';
                    li.textContent = 'No knowledge base items found.';
                    itemListUl.appendChild(li);
                    return;
                }
                data.forEach(item => {
                    const li = document.createElement('li');
                    li.className = 'list-group-item list-group-item-action';
                    li.textContent = item.item_name || 'Untitled Item';
                    li.dataset.itemId = item.id;
                    li.addEventListener('click', () => fetchItemDetail(item.id));
                    itemListUl.appendChild(li);
                });
            })
            .catch(error => {
                console.error('Error fetching knowledge base items:', error);
                if (itemListUl) itemListUl.innerHTML = '<li class="list-group-item text-danger">Error loading items.</li>';
            });
    }

    function fetchItemDetail(itemId) {
        if (!itemDetailDiv) return;
        fetch(`/api/kb_items/${itemId}`)
            .then(response => response.json())
            .then(item => {
                itemDetailDiv.innerHTML = `
                    <h3>${item.item_name}</h3>
                    <p><small class="text-muted">Category: ${item.main_category_name} / ${item.sub_category_name}</small></p>
                    <p><small class="text-muted">Source: ${item.source} | Created: ${new Date(item.created_at_tweet || item.created_at).toLocaleString()}</small></p>
                    <a href="${item.tweet_url}" target="_blank">View Original Tweet</a>
                    <hr>
                    <h5>Content:</h5>
                    <div class="markdown-content"></div>
                    <hr>
                    <h5>Media:</h5>
                    <div id="media-gallery-${itemId}" class="row"></div>
                `;
                // Render Markdown content
                if (item.content_markdown) {
                    itemDetailDiv.querySelector('.markdown-content').innerHTML = marked.parse(item.content_markdown);
                } else {
                     itemDetailDiv.querySelector('.markdown-content').innerHTML = '<p><em>No Markdown content available.</em></p>';
                }

                // Display media
                const mediaGallery = itemDetailDiv.querySelector(`#media-gallery-${itemId}`);
                if (item.kb_media_paths_resolved && item.kb_media_paths_resolved.length > 0) {
                    item.kb_media_paths_resolved.forEach(media => {
                        const col = document.createElement('div');
                        col.className = 'col-md-4 mb-3';
                        if (media.type.startsWith('image/')) {
                            col.innerHTML = `<img src="${media.url}" class="img-fluid rounded" alt="${media.alt_text || 'Knowledge Base Media'}">`;
                        } else if (media.type.startsWith('video/')) {
                            col.innerHTML = `<video controls src="${media.url}" class="img-fluid rounded"><p>Your browser does not support the video tag.</p></video>`;
                        } else {
                            col.innerHTML = `<a href="${media.url}" target="_blank">View Media File (${media.name})</a>`;
                        }
                        mediaGallery.appendChild(col);
                    });
                } else {
                    mediaGallery.innerHTML = '<p><em>No media items associated with this entry.</em></p>';
                }


                // Highlight selected item in the list
                if (itemListUl) {
                    Array.from(itemListUl.children).forEach(li => {
                        li.classList.remove('active');
                        if (li.dataset.itemId == itemId) {
                            li.classList.add('active');
                        }
                    });
                }
            })
            .catch(error => {
                console.error('Error fetching item detail:', error);
                if (itemDetailDiv) itemDetailDiv.innerHTML = '<p class="text-danger">Error loading item details.</p>';
            });
    }
    
    // Initializations
    initializeTheme(); // Initialize theme settings
    socket.emit('request_initial_status_and_git_config'); // Request initial state explicitly
    fetchKnowledgeBaseItems(); // Load KB items on page load

    addLogMessage('Client JavaScript initialized.', 'INFO');
}); 