document.addEventListener('DOMContentLoaded', function () {
    const socket = io();

    // UI Elements
    const liveLogsUl = document.getElementById('liveLogsUl');
    const clearLogsButton = document.getElementById('clearLogsButton');
    const agentExecutionPlanUl = document.getElementById('agentExecutionPlan');
    const runAgentButton = document.getElementById('runAgentButton');
    const stopAgentButton = document.getElementById('stopAgentButton');
    
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
        force_reprocess_media: document.getElementById('forceReprocessMedia'),
        force_reprocess_llm: document.getElementById('forceReprocessLLM'),
        force_reprocess_kb_item: document.getElementById('forceReprocessKBItem')
    };

    // State variables
    let agentIsRunning = false;
    let currentPhaseId = null; // Stores the ID of the currently active main phase
    let activeRunPreferences = null; // Stores preferences of the current/last run
    let currentPhaseExpectedEndTime = null; // Timestamp when the current phase is expected to end (for ETC)
    let phaseEtcInterval = null; // Interval timer for updating ETC display

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
        
        // Update Run/Stop buttons
        runAgentButton.disabled = isRunning;
        stopAgentButton.disabled = !isRunning;
        
        // Update agent run status display IN THE LOGS FOOTER
        const agentRunStatusLogsFooter = document.getElementById('agentRunStatusLogsFooter');
        if (agentRunStatusLogsFooter) {
            agentRunStatusLogsFooter.textContent = isRunning ? 'Agent Status: Running' : 'Agent Status: Not Running';
            agentRunStatusLogsFooter.classList.remove('text-danger', 'text-success');
            agentRunStatusLogsFooter.classList.add(isRunning ? 'text-success' : 'text-danger');
        }
        
        // Show/hide ETC in LOGS FOOTER based on agent running state
        const phaseEtcLogsFooter = document.getElementById('phaseEtcLogsFooter');
        if (phaseEtcLogsFooter) {
            phaseEtcLogsFooter.style.display = isRunning && currentPhaseExpectedEndTime ? 'inline' : 'none';
        }

        // Disable preference form controls if agent is running
        const formControlsToDisable = Object.values(controlInputs).filter(el => el);
        formControlsToDisable.forEach(control => {
            if (control) control.disabled = isRunning;
        });
    }

    // --- Agent Execution Plan UI Update ---
    function updatePhaseInExecutionPlan(phaseIdToUpdate, statusToSet, messageToSet, isSubStepUpdate = false, fullPlanStatuses = null) {
        const executionPlanContainer = document.getElementById('executionPlanContainer');
        if (!executionPlanContainer) return;

        const applyStatusToElement = (el, status, message) => {
            if (!el) return;
            el.classList.remove('status-pending', 'status-will-run', 'status-active', 'status-completed', 'status-skipped', 'status-error', 'phase-hidden-by-mode', 'status-interrupted');
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
                    case 'interrupted': statusSpan.textContent = 'Interrupted'; break;
                    default: statusSpan.textContent = '';
                }
            }
        };

        if (fullPlanStatuses) {
            // Iterate and update all known plan items based on full server state
            for (const [phaseId, phaseInfo] of Object.entries(fullPlanStatuses)) {
                const phaseElement = executionPlanContainer.querySelector(`[data-phase-id="${phaseId}"]`);
                if (phaseElement) {
                    applyStatusToElement(phaseElement, phaseInfo.status, phaseInfo.message);
                }
            }
        } else if (phaseIdToUpdate) {
            // Update a single specified phase
            const phaseElement = executionPlanContainer.querySelector(`[data-phase-id="${phaseIdToUpdate}"]`);
            if (phaseElement) {
                applyStatusToElement(phaseElement, statusToSet, messageToSet);
            }
        }
        // Special handling for current phase details box
        const currentPhaseDetailsBox = document.getElementById('current-phase-details');
        if (currentPhaseDetailsBox) {
            if (agentIsRunning && currentPhaseId && messageToSet && messageToSet !== 'Running...') { // Avoid generic "Running..."
                 let activePhaseName = '';
                 const activePhaseEl = executionPlanContainer.querySelector(`[data-phase-id="${currentPhaseId}"] .phase-name`);
                 if(activePhaseEl) activePhaseName = activePhaseEl.textContent.trim() + ": ";
                 currentPhaseDetailsBox.textContent = activePhaseName + messageToSet;
            } else if (agentIsRunning && !messageToSet && currentPhaseId) {
                // If running and there's a phase but no specific message, show phase name + Processing
                let activePhaseName = '';
                const activePhaseEl = executionPlanContainer.querySelector(`[data-phase-id="${currentPhaseId}"] .phase-name`);
                if(activePhaseEl) activePhaseName = activePhaseEl.textContent.trim();
                currentPhaseDetailsBox.textContent = activePhaseName ? `${activePhaseName}: Processing...` : 'Agent Processing...';
            } else if (!agentIsRunning) {
                 currentPhaseDetailsBox.textContent = 'Agent Idle';
            }
        }

        // Call a new function to adjust heights after updating the execution plan
        setTimeout(adjustPanelHeights, 50);
    }

    // New function to ensure panel heights are matched appropriately
    function adjustPanelHeights() {
        // Get the execution plan and live logs containers using the new layout classes
        const executionPlanPanel = document.querySelector('.execution-plan-panel .card');
        const liveLogsPanel = document.querySelector('.live-logs-panel .card');
        
        if (!executionPlanPanel || !liveLogsPanel) return;
        
        // Let the execution plan determine its natural height first
        executionPlanPanel.style.height = 'auto';
        
        // Get the natural height of the execution plan after it has rendered
        const executionPlanHeight = executionPlanPanel.offsetHeight;
        
        // Make sure the live logs panel matches this height (but can scroll internally)
        liveLogsPanel.style.height = `${executionPlanHeight}px`;
        
        // Make sure log container fills the available space
        const logContainer = document.getElementById('liveLogsUl');
        if (logContainer) {
            // Calculate the height available for the logs container
            const logsPanelBody = document.querySelector('.live-logs-panel .card-body');
            const logsHeaderHeight = document.querySelector('.live-logs-panel .card-header')?.offsetHeight || 0;
            const logsFooterHeight = document.querySelector('.live-logs-panel .card-footer')?.offsetHeight || 0;
            
            if (logsPanelBody) {
                // Subtract header/footer heights from available space
                const availableHeight = executionPlanHeight - logsHeaderHeight - logsFooterHeight - 30; // 30px for padding
                logContainer.style.height = `${availableHeight}px`;
                logContainer.style.maxHeight = `${availableHeight}px`;
                logContainer.style.overflowY = 'auto';
            }
        }
        
        // Make sure panels are visible
        const mainPanelsContainer = document.querySelector('.dashboard-main-panels');
        if (mainPanelsContainer) {
            mainPanelsContainer.style.display = 'flex';
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
        
        // Granular force flags for different phases
        prefs.force_reprocess_media = controlInputs.force_reprocess_media ? controlInputs.force_reprocess_media.checked : false;
        prefs.force_reprocess_llm = controlInputs.force_reprocess_llm ? controlInputs.force_reprocess_llm.checked : false;
        prefs.force_reprocess_kb_item = controlInputs.force_reprocess_kb_item ? controlInputs.force_reprocess_kb_item.checked : false;

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
            force_reprocess_media: controlInputs.force_reprocess_media ? controlInputs.force_reprocess_media.checked : false,
            force_reprocess_llm: controlInputs.force_reprocess_llm ? controlInputs.force_reprocess_llm.checked : false,
            force_reprocess_kb_item: controlInputs.force_reprocess_kb_item ? controlInputs.force_reprocess_kb_item.checked : false,
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

        // New granular force reprocessing options
        if (controlInputs.force_reprocess_media && clientPrefs.hasOwnProperty('force_reprocess_media')) 
            controlInputs.force_reprocess_media.checked = clientPrefs.force_reprocess_media;
        else if (controlInputs.force_reprocess_media) 
            controlInputs.force_reprocess_media.checked = false;
            
        if (controlInputs.force_reprocess_llm && clientPrefs.hasOwnProperty('force_reprocess_llm')) 
            controlInputs.force_reprocess_llm.checked = clientPrefs.force_reprocess_llm;
        else if (controlInputs.force_reprocess_llm) 
            controlInputs.force_reprocess_llm.checked = false;
            
        if (controlInputs.force_reprocess_kb_item && clientPrefs.hasOwnProperty('force_reprocess_kb_item')) 
            controlInputs.force_reprocess_kb_item.checked = clientPrefs.force_reprocess_kb_item;
        else if (controlInputs.force_reprocess_kb_item) 
            controlInputs.force_reprocess_kb_item.checked = false;
            
        const currentPrefsForViz = getPreferencesForServer(); 
        updateExecutionPlanVisualization(currentPrefsForViz); 
    }
    
    function updateExecutionPlanVisualization(preferences) {
        console.log("Updating execution plan visualization (Restored Logic) with prefs:", preferences);
        const executionPlanContainer = document.getElementById('executionPlanContainer');
        if (!executionPlanContainer) return;

        const phaseConfigs = {
            'initialization': { el: executionPlanContainer.querySelector('[data-phase-id="initialization"]'), skipKey: null },
            'fetch_bookmarks': { el: executionPlanContainer.querySelector('[data-phase-id="fetch_bookmarks"]'), skipKey: 'skip_fetch_bookmarks' },
            'content_processing_overall': { el: executionPlanContainer.querySelector('[data-phase-id="content_processing_overall"]'), skipKey: 'skip_process_content' },
            'subphase_cp_cache': { el: executionPlanContainer.querySelector('[data-phase-id="subphase_cp_cache"]'), parent: 'content_processing_overall' },
            'subphase_cp_media': { el: executionPlanContainer.querySelector('[data-phase-id="subphase_cp_media"]'), parent: 'content_processing_overall' },
            'subphase_cp_llm': { el: executionPlanContainer.querySelector('[data-phase-id="subphase_cp_llm"]'), parent: 'content_processing_overall' },
            'subphase_cp_kbitem': { el: executionPlanContainer.querySelector('[data-phase-id="subphase_cp_kbitem"]'), parent: 'content_processing_overall' },
            'subphase_cp_db': { el: executionPlanContainer.querySelector('[data-phase-id="subphase_cp_db"]'), parent: 'content_processing_overall' },
            'readme_generation': { el: executionPlanContainer.querySelector('[data-phase-id="readme_generation"]'), skipKey: 'skip_readme_generation' },
            'git_sync': { el: executionPlanContainer.querySelector('[data-phase-id="git_sync"]'), skipKey: 'skip_git_push' },
            'cleanup': { el: executionPlanContainer.querySelector('[data-phase-id="cleanup"]'), skipKey: null }
        };

        for (const phaseId in phaseConfigs) {
            const config = phaseConfigs[phaseId];
            if (!config.el) {
                console.warn("Config element not found for phaseId:", phaseId);
                continue;
            }

            const statusSpan = config.el.querySelector('.phase-status');
            const optionalInfoSpan = config.el.querySelector('.optional-phase-info'); 
            
            config.el.classList.remove('status-pending', 'status-will-run', 'status-skipped', 'status-active', 'status-completed', 'status-error', 'status-interrupted');
            
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
                
                const parentIsSkipped = parentConfig.skipKey && preferences[parentConfig.skipKey];

                // If the parent "Content Processing Overall" is skipped, all sub-phases are skipped.
                if (parentIsSkipped) {
                    statusClass = 'status-skipped';
                    statusText = 'Skipped (parent)';
                } else {
                    // Default for sub-phases if parent is not skipped: they will run.
                    // Specific force flags might change their nature (e.g. re-running) but they are part of the active pipeline.
                    statusClass = 'status-will-run';
                    statusText = 'Will run';

                    // Indicate if a sub-phase is explicitly forced
                    if (phaseId === 'subphase_cp_cache' && preferences.force_recache_tweets) {
                        statusText = 'Will run (forced)';
                    } else if (phaseId === 'subphase_cp_media' && preferences.force_reprocess_media) {
                        statusText = 'Will run (forced)';
                    } else if (phaseId === 'subphase_cp_llm' && preferences.force_reprocess_llm) {
                        statusText = 'Will run (forced)';
                    } else if (phaseId === 'subphase_cp_kbitem' && preferences.force_reprocess_kb_item) {
                        statusText = 'Will run (forced)';
                    }
                    // DB sync runs if KB item runs, no separate force flag needed for visualization here.
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
                    // Don't add duplicate "(Will Run)" text, as it's already shown in the status span
                    // optionalInfoSpan.textContent = '(Will Run)'; 
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

    if (runAgentButton) {
        runAgentButton.addEventListener('click', () => {
            const preferences = getPreferencesForServer();
            addLogMessage(`Requesting to run agent with preferences: ${JSON.stringify(preferences)}`, 'INFO');
            socket.emit('run_agent', { preferences: preferences });
        });
    }

    if (stopAgentButton) {
        stopAgentButton.addEventListener('click', () => {
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

        // Restore time estimation if provided and agent is running
        if (agentIsRunning && data.phase_estimated_completion_times && currentPhaseId) {
            const phaseEtc = data.phase_estimated_completion_times[currentPhaseId];
            if (phaseEtc && phaseEtc > 0) {
                currentPhaseExpectedEndTime = phaseEtc * 1000; // Convert to milliseconds
                console.log(`Restored time estimation for phase ${currentPhaseId}: ${new Date(currentPhaseExpectedEndTime)}`);
                startEtcUpdateInterval();
                updatePhaseEtcDisplay();
            }
        }
        
        // Set time estimate if provided and agent is running (legacy support)
        if (agentIsRunning && data.time_estimate) {
            const timeEstimateSpans = document.querySelectorAll('#timeEstimatePlan, #timeEstimateLogs');
            timeEstimateSpans.forEach(span => {
                if (span) {
                    span.textContent = data.time_estimate;
                    span.style.display = 'inline';
                }
            });
        }
        
        // Update full execution plan based on initial status
        if (data.full_plan_statuses) {
            updatePhaseInExecutionPlan(null, null, null, false, data.full_plan_statuses);
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
            if (data.plan_statuses) {
                 updatePhaseInExecutionPlan(null, null, null, false, data.plan_statuses);
            } else if (activeRunPreferences.plan_statuses) {
                 updatePhaseInExecutionPlan(null, null, null, false, activeRunPreferences.plan_statuses);
            } else {
                // If no plan_statuses, re-visualize based on loaded preferences (pre-run state)
                 const prefsForViz = getPreferencesForServer();
                 updateExecutionPlanVisualization(prefsForViz);
            }
            
            // Update the current phase details box if we have phase info
            if (data.current_phase_id && data.current_step_in_current_phase_progress_message) {
                currentPhaseId = data.current_phase_id;
                const currentPhaseDetailsBox = document.getElementById('current-phase-details');
                if (currentPhaseDetailsBox) {
                    let activePhaseName = '';
                    const activePhaseEl = document.querySelector(`[data-phase-id="${currentPhaseId}"] .phase-name`);
                    if (activePhaseEl) activePhaseName = activePhaseEl.textContent.trim() + ": ";
                    currentPhaseDetailsBox.textContent = activePhaseName + data.current_step_in_current_phase_progress_message;
                }
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

        // Adjust panel heights after initialization
        setTimeout(adjustPanelHeights, 100);
    });

    socket.on('agent_phase_update', function(data) {
        addLogMessage(`Phase update: ${data.phase_id} - ${data.status} - ${data.message}`, 'INFO');
        console.log("Agent Phase Update:", data);
        currentPhaseId = data.phase_id; // Update current phase ID
        
        let formattedProgressMessage = data.message || '';
        if (data.status === 'active') {
             formattedProgressMessage = data.message || 'Processing...'; // Default for active phase in list
            
            // Use estimated_completion_timestamp directly from backend if available
            if (data.estimated_completion_timestamp && data.estimated_completion_timestamp > 0) {
                currentPhaseExpectedEndTime = data.estimated_completion_timestamp * 1000; // Convert to milliseconds
                console.log(`Phase ${data.phase_id} started. Expected end: ${new Date(currentPhaseExpectedEndTime)}`);
                startEtcUpdateInterval(); // Start ETC timer
                updatePhaseEtcDisplay(); // Initial display
            } else if (data.initial_estimated_duration_seconds !== undefined && data.initial_estimated_duration_seconds > 0) {
                // Fallback to calculating from initial_estimated_duration_seconds if timestamp not available
                const phaseStartTime = Date.now();
                currentPhaseExpectedEndTime = phaseStartTime + (data.initial_estimated_duration_seconds * 1000);
                console.log(`Phase ${data.phase_id} started. Initial Estimated Duration: ${data.initial_estimated_duration_seconds}s. Expected end: ${new Date(currentPhaseExpectedEndTime)}`);
                startEtcUpdateInterval(); // Start ETC timer
                updatePhaseEtcDisplay(); // Initial display
            } else {
                currentPhaseExpectedEndTime = null; // No estimate available
                stopEtcUpdateInterval();
                const phaseEtcLogsFooter = document.getElementById('phaseEtcLogsFooter');
                if(phaseEtcLogsFooter) {
                    phaseEtcLogsFooter.textContent = 'ETC: N/A';
                    phaseEtcLogsFooter.style.display = agentIsRunning ? 'inline' : 'none';
                }
            }
        } else if (data.status === 'completed' || data.status === 'skipped' || data.status === 'error') {
            // If the current phase just completed/skipped/errored, clear its ETC.
            if (data.phase_id === currentPhaseId) {
                currentPhaseExpectedEndTime = null;
                stopEtcUpdateInterval();
                 const phaseEtcLogsFooter = document.getElementById('phaseEtcLogsFooter');
                if(phaseEtcLogsFooter) phaseEtcLogsFooter.style.display = 'none';
            }
        }

        updatePhaseInExecutionPlan(data.phase_id, data.status, formattedProgressMessage, data.is_sub_step || false);
        updateAgentStatusUI(); // Update overall agent status display elements

        if (data.phase_id === 'git_sync' && data.git_config_error) {
            const gitPhaseElement = document.querySelector('[data-phase-id="git_sync"]');
            const optionalInfoSpan = gitPhaseElement ? gitPhaseElement.querySelector('.optional-phase-info') : null;
            if (optionalInfoSpan) {
                optionalInfoSpan.textContent = '(Error: Git not configured)';
                optionalInfoSpan.classList.add('text-danger');
            }
        }
    });

    // New listener for ongoing phase progress and ETC
    socket.on('agent_phase_progress', function(data) {
        // This event is now primarily for updating the (X/Y) counts in the current-phase-details box.
        // The main ETC countdown is handled by the interval timer.
        if (agentIsRunning && data.phase_id === currentPhaseId && data.total_count > 0) {
            const processed = data.processed_count;
            const total = data.total_count;
            
            const currentPhaseDetailsBox = document.getElementById('current-phase-details');
            if (currentPhaseDetailsBox) {
                let activePhaseName = '';
                const activePhaseEl = document.querySelector(`[data-phase-id="${currentPhaseId}"] .phase-name`);
                if(activePhaseEl) activePhaseName = activePhaseEl.textContent.trim();
                
                let baseMessage = data.status_message || 'Processing...'; // Message from backend if any
                
                // ETC string will be updated by the interval timer, so we don't include it here directly from this event
                // to avoid conflicts if historical ETC is used.
                currentPhaseDetailsBox.textContent = `${activePhaseName}: (${processed}/${total}) ${baseMessage}`;
            }
        } else if (data.phase_id === currentPhaseId && data.total_count === 0 && agentIsRunning) {
             const currentPhaseDetailsBox = document.getElementById('current-phase-details');
             if (currentPhaseDetailsBox) {
                let activePhaseName = '';
                const activePhaseEl = document.querySelector(`[data-phase-id="${currentPhaseId}"] .phase-name`);
                if(activePhaseEl) activePhaseName = activePhaseEl.textContent.trim();
                currentPhaseDetailsBox.textContent = `${activePhaseName}: ${data.status_message || 'Processing...'}`;
             }
        }
    });

    function formatRemainingTime(milliseconds) {
        if (milliseconds < 0) milliseconds = 0;
        const totalSeconds = Math.ceil(milliseconds / 1000);
        const hours = Math.floor(totalSeconds / 3600);
        const minutes = Math.floor((totalSeconds % 3600) / 60);
        const seconds = totalSeconds % 60;

        if (hours > 0) {
            return `${String(hours).padStart(2, '0')}h ${String(minutes).padStart(2, '0')}m`;
        } else if (minutes > 0) {
            return `${String(minutes).padStart(2, '0')}m ${String(seconds).padStart(2, '0')}s`;
        } else {
            return `${String(seconds).padStart(2, '0')}s`;
        }
    }

    function updatePhaseEtcDisplay() {
        const phaseEtcLogsFooter = document.getElementById('phaseEtcLogsFooter');
        if (!phaseEtcLogsFooter || !agentIsRunning) return;

        if (currentPhaseExpectedEndTime) {
            const remainingMs = currentPhaseExpectedEndTime - Date.now();
            if (remainingMs > 0) {
                phaseEtcLogsFooter.textContent = `ETC: ${formatRemainingTime(remainingMs)}`;
                phaseEtcLogsFooter.style.display = 'inline';
            } else {
                phaseEtcLogsFooter.textContent = 'ETC: Finishing...'; // Or some other message
                phaseEtcLogsFooter.style.display = 'inline';
                // Optionally stop interval if it goes significantly past expected end time
            }
        } else {
            // Fallback to real-time calculation if no historical estimate was provided
            // This part can reuse logic from the previous 'agent_phase_progress' if a simple real-time ETC is desired as fallback
            // For now, if no currentPhaseExpectedEndTime, it shows N/A via agent_phase_update logic.
            // phaseEtcLogsFooter.textContent = 'ETC: N/A (Live)';
            // phaseEtcLogsFooter.style.display = 'inline';
        }
    }

    function startEtcUpdateInterval() {
        stopEtcUpdateInterval(); // Clear existing interval if any
        if (currentPhaseExpectedEndTime) {
            phaseEtcInterval = setInterval(updatePhaseEtcDisplay, 1000); // Update every second
            updatePhaseEtcDisplay(); // Initial call
        }
    }

    function stopEtcUpdateInterval() {
        if (phaseEtcInterval) {
            clearInterval(phaseEtcInterval);
            phaseEtcInterval = null;
        }
    }

    socket.on('agent_run_completed', function(data) {
        addLogMessage(`Agent run completed. Summary: ${data.summary_message}`, 'INFO');
        agentIsRunning = data.is_running; 
        updateAgentStatusUI();
        currentPhaseId = null; 
        activeRunPreferences = null; 
        currentPhaseExpectedEndTime = null; // Clear expected end time
        stopEtcUpdateInterval(); // Stop ETC timer

        const phaseEtcLogsFooter = document.getElementById('phaseEtcLogsFooter');
        if (phaseEtcLogsFooter) {
            phaseEtcLogsFooter.style.display = 'none';
        }

        if (data.plan_statuses) {
            updatePhaseInExecutionPlan(null, null, null, false, data.plan_statuses);
        }
        fetchKnowledgeBaseItems(); 
        loadClientPreferences(); // Reload local prefs and re-visualize for a new run
        
        // Adjust panel heights after completion
        setTimeout(adjustPanelHeights, 50);
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
                            
                            <div class="row d-flex flex-nowrap">
                                <div class="col-3 mb-2">
                                    <small class="text-muted">Temperature</small>
                                    <div class="fw-bold ${tempClass}">${tempDisplay}</div>
                                </div>
                                <div class="col-3 mb-2">
                                    <small class="text-muted">Power Draw</small>
                                    <div class="fw-bold">${powerDraw}</div>
                                </div>
                                <div class="col-3 mb-2">
                                    <small class="text-muted">Graphics Clock</small>
                                    <div class="fw-bold">${gfxClock}</div>
                                </div>
                                <div class="col-3 mb-2">
                                    <small class="text-muted">Memory Clock</small>
                                    <div class="fw-bold">${memClock}</div>
                                </div>
                            </div>
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
    
    // Handle initialization of all UI components when the DOM loads
    function initializeUI() {
        // Other UI initialization...
        
        // When media option changes, update LLM and KB Item options to maintain pipeline coherence
        if (controlInputs.force_reprocess_media) {
            controlInputs.force_reprocess_media.addEventListener('change', function() {
                if (this.checked) {
                    // When enabling media processing, also enable all subsequent phases
                    if (controlInputs.force_reprocess_llm)
                        controlInputs.force_reprocess_llm.checked = true;
                    if (controlInputs.force_reprocess_kb_item)
                        controlInputs.force_reprocess_kb_item.checked = true;
                }
                
                updateExecutionPlanVisualization(getPreferencesForServer());
                saveClientPreferences();
            });
        }
        
        // When LLM option changes, update KB Item option to maintain pipeline coherence
        if (controlInputs.force_reprocess_llm) {
            controlInputs.force_reprocess_llm.addEventListener('change', function() {
                if (this.checked) {
                    // When enabling LLM processing, also enable KB item generation
                    if (controlInputs.force_reprocess_kb_item)
                        controlInputs.force_reprocess_kb_item.checked = true;
                } else if (!controlInputs.force_reprocess_media.checked) {
                    // Only allow unchecking if media option is not enabled
                    // Otherwise LLM should stay checked
                }
                
                updateExecutionPlanVisualization(getPreferencesForServer());
                saveClientPreferences();
            });
        }
        
        // When KB item option changes
        if (controlInputs.force_reprocess_kb_item) {
            controlInputs.force_reprocess_kb_item.addEventListener('change', function() {
                if (!this.checked) {
                    // If turning off KB item generation, ensure higher-level options are also off
                    if (controlInputs.force_reprocess_media.checked || controlInputs.force_reprocess_llm.checked) {
                        // KB items should stay checked if higher-level options are enabled
                        this.checked = true;
                    }
                }
                
                updateExecutionPlanVisualization(getPreferencesForServer());
                saveClientPreferences();
            });
        }
        
        // Restore preferences from localStorage
        restoreClientPreferences();
    }
    
    // Initializations
    initializeTheme(); // Initialize theme settings
    initializeUI(); // Initialize UI components and event handlers
    socket.emit('request_initial_status_and_git_config'); // Request initial state explicitly
    fetchKnowledgeBaseItems(); // Load KB items on page load
    
    // Call the adjustment function on page load, window resize, and whenever content changes
    adjustPanelHeights();
    window.addEventListener('resize', adjustPanelHeights);
    
    // Add additional trigger points for panel height adjustment
    const executionPlanObserver = new MutationObserver(adjustPanelHeights);
    const executionPlanContainer = document.getElementById('executionPlanContainer');
    if (executionPlanContainer) {
        executionPlanObserver.observe(executionPlanContainer, { childList: true, subtree: true });
    }

    addLogMessage('Client JavaScript initialized.', 'INFO');
}); 