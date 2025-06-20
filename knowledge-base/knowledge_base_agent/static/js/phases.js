/**
 * Phase Management Module
 * Handles phase states, execution plan updates, and phase visualization
 */

class PhaseManager {
    constructor() {
        this.phaseStates = {
            initialization: 'normal',
            fetch_bookmarks: 'normal',
            content_processing_overall: 'normal',
            subphase_cp_cache: 'normal',
            subphase_cp_media: 'normal',
            subphase_cp_llm: 'normal',
            subphase_cp_kbitem: 'normal',
            subphase_cp_db: 'normal',
            synthesis_generation: 'normal',
            readme_generation: 'normal',
            git_sync: 'normal',
            cleanup: 'normal',
            embedding_generation: 'normal'
        };
        
        // Restore saved phase states from localStorage
        this.restorePhaseStates();

        this.subPhaseIds = [
            'subphase_cp_cache',
            'subphase_cp_media',
            'subphase_cp_llm',
            'subphase_cp_kbitem',
            'subphase_cp_db'
        ];

        this.phaseStateMapping = {
            initialization: {
                normal: { label: 'Will Run', class: 'status-will-run phase-always-run' },
            },
            fetch_bookmarks: {
                normal: { label: 'Will Run', class: 'status-will-run' },
                skip: { label: '(Skipped)', class: 'status-skipped phase-state-skip' },
                force: { label: 'Force Re-cache', class: 'status-will-run phase-state-force' }
            },
            content_processing_overall: {
                normal: { label: 'Will Run', class: 'status-will-run' },
                skip: { label: '(Skipped)', class: 'status-skipped phase-state-skip' },
                force: { label: 'Force Re-process', class: 'status-will-run phase-state-force' }
            },
            subphase_cp_cache: {
                normal: { label: 'Will Run', class: 'status-will-run' },
                skip: { label: '(Skipped)', class: 'status-skipped phase-state-skip' },
                force: { label: 'Force Re-cache', class: 'status-will-run phase-state-force' }
            },
            subphase_cp_media: {
                normal: { label: 'Will Run', class: 'status-will-run' },
                skip: { label: '(Skipped)', class: 'status-skipped phase-state-skip' },
                force: { label: 'Force Re-analyze', class: 'status-will-run phase-state-force' }
            },
            subphase_cp_llm: {
                normal: { label: 'Will Run', class: 'status-will-run' },
                skip: { label: '(Skipped)', class: 'status-skipped phase-state-skip' },
                force: { label: 'Force Re-process', class: 'status-will-run phase-state-force' }
            },
            subphase_cp_kbitem: {
                normal: { label: 'Will Run', class: 'status-will-run' },
                skip: { label: '(Skipped)', class: 'status-skipped phase-state-skip' },
                force: { label: 'Force Regenerate', class: 'status-will-run phase-state-force' }
            },
            subphase_cp_db: {
                normal: { label: 'Will Run', class: 'status-will-run' },
                skip: { label: '(Skipped)', class: 'status-skipped phase-state-skip' },
                force: { label: 'Force Sync', class: 'status-will-run phase-state-force' }
            },
            synthesis_generation: {
                normal: { label: 'Will Run', class: 'status-will-run' },
                skip: { label: '(Skipped)', class: 'status-skipped phase-state-skip' },
                force: { label: 'Force Regenerate', class: 'status-will-run phase-state-force' }
            },
            readme_generation: {
                normal: { label: 'Will Run', class: 'status-will-run' },
                skip: { label: '(Skipped)', class: 'status-skipped phase-state-skip' },
                force: { label: 'Force Regenerate', class: 'status-will-run phase-state-force' }
            },
            git_sync: {
                normal: { label: 'Will Run', class: 'status-will-run' },
                skip: { label: '(Skipped)', class: 'status-skipped phase-state-skip' },
                force: { label: 'Force Push', class: 'status-will-run phase-state-force' }
            },
            cleanup: {
                normal: { label: 'Will Run', class: 'status-will-run phase-always-run' },
            },
            embedding_generation: {
                normal: { label: 'Will Run', class: 'status-will-run' },
                skip: { label: '(Skipped)', class: 'status-skipped phase-state-skip' },
                force: { label: 'Force Regenerate', class: 'status-will-run phase-state-force' }
            }
        };

        // Initialize phase states
        Object.keys(this.phaseStateMapping).forEach(phase => {
            this.phaseStates[phase] = 'normal';
        });
        this.phaseStates['initialization'] = 'normal';
        this.phaseStates['cleanup'] = 'normal';

        this.restorePhaseStates();
        this.applyStateToUI();
        
        // Start periodic check for sub-phase completion
        this.startSubPhaseCompletionMonitor();
    }

    /**
     * Save current phase states to localStorage
     */
    savePhaseStates() {
        try {
            localStorage.setItem('phaseManagerStates', JSON.stringify(this.phaseStates));
        } catch (e) {
            console.warn('PhaseManager: Failed to save phase states to localStorage:', e);
        }
    }

    /**
     * Restore phase states from localStorage
     */
    restorePhaseStates() {
        try {
            const savedStates = localStorage.getItem('phaseManagerStates');
            if (savedStates) {
                const parsedStates = JSON.parse(savedStates);
                // Only restore valid phase IDs that exist in current setup
                Object.keys(parsedStates).forEach(phaseId => {
                    if (this.phaseStates.hasOwnProperty(phaseId)) {
                        this.phaseStates[phaseId] = parsedStates[phaseId];
                    }
                });
                console.log('PhaseManager: Restored phase states from localStorage:', this.phaseStates);
            }
        } catch (e) {
            console.warn('PhaseManager: Failed to restore phase states from localStorage:', e);
        }
    }

    /**
     * Apply saved phase states to UI elements
     */
    applyStateToUI() {
        Object.keys(this.phaseStates).forEach(phaseId => {
            const phaseElement = document.querySelector(`[data-phase-id="${phaseId}"]`);
            if (phaseElement) {
                const state = this.phaseStates[phaseId];
                phaseElement.setAttribute('data-phase-state', state);
                this.updatePhaseVisualState(phaseElement, phaseId, state);
            }
        });
    }

    /**
     * Toggle phase state (normal -> skip -> force -> normal)
     */
    togglePhaseState(phaseElement, agentIsRunning = false) {
        const phaseId = phaseElement.getAttribute('data-phase-id');

        if (phaseId === 'initialization' || phaseId === 'cleanup') {
            console.log(`PhaseManager: Phase ${phaseId} always runs and cannot be toggled.`);
            return;
        }

        if (agentIsRunning) {
            console.log('PhaseManager: Cannot change phase state while agent is running');
            return;
        }
        
        const currentState = this.phaseStates[phaseId] || 'normal';
        
        // Cycle through states
        let newState;
        switch (currentState) {
            case 'normal': newState = 'skip'; break;
            case 'skip': newState = 'force'; break;
            case 'force': newState = 'normal'; break;
            default: newState = 'normal';
        }
        
        this.phaseStates[phaseId] = newState;
        phaseElement.setAttribute('data-phase-state', newState);
        this.updatePhaseVisualState(phaseElement, phaseId, newState);
        this.savePhaseStates(); // Save state changes
        console.log(`PhaseManager: Phase ${phaseId} state changed to: ${newState}`);

        // Only handle parent-child relationships for content processing phases
        if (phaseId === 'content_processing_overall') {
            // When content_processing_overall is changed, update its sub-phases
            const subPhaseNewState = (newState === 'skip') ? 'skip' : 'normal';
            this.subPhaseIds.forEach(subId => {
                const subPhaseElement = document.querySelector(`[data-phase-id="${subId}"]`);
                if (subPhaseElement) {
                    this.phaseStates[subId] = subPhaseNewState;
                    subPhaseElement.setAttribute('data-phase-state', subPhaseNewState);
                    this.updatePhaseVisualState(subPhaseElement, subId, subPhaseNewState);
                    console.log(`PhaseManager: Sub-phase ${subId} state changed to: ${subPhaseNewState} due to parent content_processing_overall.`);
                }
            });
        }
        // If a sub-phase is changed and parent is 'skip', revert parent to 'normal'
        else if (this.subPhaseIds.includes(phaseId) && this.phaseStates.content_processing_overall === 'skip'){
            if (newState !== 'skip') { // if sub-phase is set to normal or force
                const parentPhaseElement = document.querySelector(`[data-phase-id="content_processing_overall"]`);
                if (parentPhaseElement) {
                    this.phaseStates.content_processing_overall = 'normal';
                    parentPhaseElement.setAttribute('data-phase-state', 'normal');
                    this.updatePhaseVisualState(parentPhaseElement, 'content_processing_overall', 'normal');
                    console.log(`PhaseManager: Parent phase content_processing_overall set to normal due to sub-phase ${phaseId} change.`);
                }
            }
        }
    }

    /**
     * Update visual state of a phase element
     */
    updatePhaseVisualState(phaseElement, phaseId, state) {
        const mapping = this.phaseStateMapping[phaseId];
        const stateConfig = (mapping && mapping[state]) ? mapping[state] :
                            ((phaseId === 'initialization' || phaseId === 'cleanup') && mapping && mapping.normal) ? mapping.normal : null;

        if (!stateConfig) {
            console.warn(`PhaseManager: No valid stateConfig found for phase ${phaseId} state ${state}. Defaulting visuals if possible.`);
            if (phaseElement) {
                // Remove all status and phase-state classes
                phaseElement.className = phaseElement.className.replace(/status-\w+|phase-state-\w+/g, '');
                phaseElement.classList.add('status-will-run');
                const statusElement = phaseElement.querySelector('.phase-status');
                if (statusElement) statusElement.textContent = 'Will Run';
            }
            return;
        }
        
        const statusElement = phaseElement.querySelector('.phase-status');
        
        // Remove existing status-* and phase-state-* classes while preserving others
        let baseClasses = [];
        phaseElement.classList.forEach(cls => {
            if (!cls.startsWith('status-') && !cls.startsWith('phase-state-')) {
                baseClasses.push(cls);
            }
        });
        phaseElement.className = baseClasses.join(' ');

        // Apply new classes from state config
        if (stateConfig.class) {
            stateConfig.class.split(' ').forEach(cls => {
                if (cls.trim()) phaseElement.classList.add(cls.trim());
            });
        }
        
        // Apply phase state class for CSS styling
        phaseElement.classList.add(`phase-state-${state}`);
        
        // Update status text
        if (statusElement) {
            statusElement.textContent = stateConfig.label;
        }
        
        console.log(`PhaseManager: Updated visual state for ${phaseId} to ${state}, classes: ${phaseElement.className}`);
    }

    /**
     * Update current phase details in footer with enhanced information
     */
    updateCurrentPhaseDetails(phaseId, message, processed_count = null, total_count = null, error_count = null, etcText = null) {
        const currentPhaseDetailsBox = document.getElementById('current-phase-details');
        if (!currentPhaseDetailsBox) return;
        
        // Get phase name from execution plan
        const phaseRow = document.querySelector(`[data-phase-id="${phaseId}"]`);
        let phaseName = phaseId;
        if (phaseRow) {
            const phaseNameCell = phaseRow.querySelector('.phase-name');
            if (phaseNameCell) {
                phaseName = phaseNameCell.textContent.trim();
            }
        }
        
        // Clean message of any HTML content for display in footer
        let cleanMessage = message.replace(/<[^>]*>/g, '');
        
        // Enhanced phase name mapping for better readability
        const phaseNameMap = {
            'user_input_parsing': 'Parsing User Preferences',
            'fetch_bookmarks': 'Fetching Bookmarks',
            'content_processing_overall': 'Content Processing',
            'subphase_cp_cache': 'Tweet Caching',
            'subphase_cp_media': 'Media Analysis',
            'subphase_cp_llm': 'LLM Processing',
            'subphase_cp_kbitem': 'KB Item Generation',
            'subphase_cp_db': 'Database Sync',
            'synthesis_generation': 'Synthesis Generation',
            'readme_generation': 'Root README Generation',
            'git_sync': 'Git Synchronization',
            'cleanup': 'Cleanup',
            'embedding_generation': 'Embedding Generation'
        };
        
        const displayName = phaseNameMap[phaseId] || phaseName;
        
        // Build enhanced status message with validation results
        let detailMessage = `📋 ${displayName}`;
        
        // Add status indicator
        if (cleanMessage.includes('Validating') || cleanMessage.includes('Found')) {
            detailMessage += ` - 🔍 ${cleanMessage}`;
        } else if (cleanMessage.includes('active') || cleanMessage.includes('Starting')) {
            detailMessage += ` - ⚡ ${cleanMessage}`;
        } else if (cleanMessage.includes('Completed') || cleanMessage.includes('✓')) {
            detailMessage += ` - ✅ ${cleanMessage}`;
        } else if (cleanMessage.includes('Skipped')) {
            detailMessage += ` - ⏭️ ${cleanMessage}`;
        } else if (cleanMessage.includes('Error') || cleanMessage.includes('✗')) {
            detailMessage += ` - ❌ ${cleanMessage}`;
        } else {
            detailMessage += ` - ${cleanMessage}`;
        }
        
        // Add detailed progress information if available
        if (processed_count !== null && total_count !== null && total_count > 0) {
            const percentage = Math.round((processed_count / total_count) * 100);
            if (!cleanMessage.includes(`${processed_count}/${total_count}`) && !cleanMessage.includes(`${percentage}%`)) {
                detailMessage += ` (Progress: ${processed_count}/${total_count} - ${percentage}%)`;
            }
        }
        
        // Add error count if there are errors
        if (error_count && error_count > 0) {
            detailMessage += ` ⚠️ [${error_count} errors]`;
        }
        
        // Add ETC if available
        if (etcText && etcText !== 'N/A') {
            detailMessage += ` - ⏱️ ETC: ${etcText}`;
        }
        
        // Enhanced messaging for specific phases
        if (phaseId === 'content_processing_overall' && cleanMessage.includes('No tweets to process')) {
            detailMessage = `📋 Content Processing - ✅ Validation Complete: All tweets already processed or no new tweets found`;
        }
        
        // README Generation specific messaging
        if (phaseId === 'readme_generation') {
            if (cleanMessage.includes('Generating README for') && total_count !== null) {
                detailMessage = `📋 README Generation - 📝 Creating root README.md catalog for ${total_count} existing KB items`;
            } else if (cleanMessage.includes('Found') && cleanMessage.includes('KB items')) {
                detailMessage = `📋 README Generation - 🔍 Found ${cleanMessage.match(/\d+/)?.[0] || '?'} existing KB items to catalog`;
            } else if (cleanMessage.includes('Validated') && cleanMessage.includes('KB items')) {
                detailMessage = `📋 README Generation - ✅ Validated ${cleanMessage.match(/\d+/)?.[0] || '?'} KB items for README catalog`;
            }
        }
        
        // Content Processing sub-phase specific messaging
        if (phaseId.startsWith('subphase_cp_')) {
            if (cleanMessage.includes('Found') && total_count !== null) {
                const needsProcessing = cleanMessage.match(/Found (\d+)/)?.[1] || processed_count || total_count;
                detailMessage = `📋 ${displayName} - 🔍 Validation: ${needsProcessing}/${total_count} tweets need processing`;
            } else if (cleanMessage.includes('Caching') || cleanMessage.includes('Processing') || cleanMessage.includes('Analyzing')) {
                detailMessage = `📋 ${displayName} - ⚡ Processing tweet ${processed_count || '?'}/${total_count || '?'}`;
            }
        }
        
        currentPhaseDetailsBox.textContent = detailMessage;
        
        // Also update the phase status in the execution plan
        this.updatePhaseExecutionStatus(phaseId, processed_count, total_count, error_count);
    }

    /**
     * Update phase status in the execution plan
     */
    updatePhaseExecutionStatus(phaseId, processed_count, total_count, error_count) {
        const phaseElement = document.querySelector(`[data-phase-id="${phaseId}"]`);
        if (!phaseElement) return;
        
        const statusElement = phaseElement.querySelector('.phase-status');
        if (!statusElement) return;
        
        // Update status text with progress information
        if (processed_count !== null && total_count !== null && total_count > 0) {
            const percentage = Math.round((processed_count / total_count) * 100);
            let statusText = `${processed_count}/${total_count}`;
            
            if (percentage === 100) {
                statusText = `Done (${total_count})`;  // Simplified text without emoji
                // Update the visual class to completed
                phaseElement.classList.remove('status-pending', 'status-active', 'status-skipped', 'status-error');
                phaseElement.classList.add('status-completed');
            } else {
                statusText += ` (${percentage}%)`;
                // Update the visual class to active
                phaseElement.classList.remove('status-pending', 'status-completed', 'status-skipped', 'status-error');
                phaseElement.classList.add('status-active');
            }
            
            if (error_count && error_count > 0) {
                statusText += ` ⚠️${error_count}`;
            }
            
            statusElement.textContent = statusText;
        } else if (processed_count === 0 && total_count === 0) {
            // Phase completed with no items to process
            statusElement.textContent = 'Done';  // Simplified text without emoji
            phaseElement.classList.remove('status-pending', 'status-active', 'status-skipped', 'status-error');
            phaseElement.classList.add('status-completed');
        }
    }

    /**
     * Update phase status in the execution plan with enhanced sub-phase handling
     */
    updatePhaseStatus(phaseId, status, message) {
        const phaseElement = document.querySelector(`[data-phase-id="${phaseId}"]`);
        if (!phaseElement) {
            console.warn(`PhaseManager: Phase element not found for ${phaseId}`);
            return;
        }

        const statusElement = phaseElement.querySelector('.phase-status');
        if (!statusElement) {
            console.warn(`PhaseManager: Status element not found for ${phaseId}`);
            return;
        }

        // Log all status changes for sub-phases
        if (this.subPhaseIds.includes(phaseId)) {
            console.log(`PhaseManager: Sub-phase ${phaseId} status update: ${status} - ${message}`);
        }

        // Remove existing status classes while preserving others
        let baseClasses = [];
        phaseElement.classList.forEach(cls => {
            if (!cls.startsWith('status-')) {
                baseClasses.push(cls);
            }
        });
        phaseElement.className = baseClasses.join(' ');

        // Apply the new status class based on status parameter
        switch (status) {
            case 'active':
            case 'in_progress':
                phaseElement.classList.add('status-active');
                statusElement.textContent = 'Running';  // Simplified text
                console.log(`PhaseManager: Set ${phaseId} to active`);
                // Update current phase details when a phase becomes active
                // This ensures the old phase status message is replaced
                this.updateCurrentPhaseDetails(phaseId, message || 'Phase started');
                break;
                
            case 'completed':
            case 'completed_with_errors': // Handle completion with errors
                phaseElement.classList.add('status-completed');
                statusElement.textContent = 'Done';  // Simplified "Done" text without emoji
                console.log(`PhaseManager: Set ${phaseId} to completed`);
                
                // Handle sub-phase completion for content processing
                if (this.subPhaseIds.includes(phaseId)) {
                    console.log(`PhaseManager: Triggering sub-phase completion check for ${phaseId}`);
                    this._handleSubPhaseCompletion(phaseId);
                }
                break;
                
            case 'skipped':
                phaseElement.classList.add('status-skipped');
                statusElement.textContent = 'Skipped';  // Simplified text
                console.log(`PhaseManager: Set ${phaseId} to skipped`);
                
                // Also handle sub-phase completion for skipped phases
                if (this.subPhaseIds.includes(phaseId)) {
                    console.log(`PhaseManager: Triggering sub-phase completion check for skipped ${phaseId}`);
                    this._handleSubPhaseCompletion(phaseId);
                }
                break;
                
            case 'error':
                phaseElement.classList.add('status-error');
                statusElement.textContent = 'Error';  // Simplified text
                console.log(`PhaseManager: Set ${phaseId} to error`);
                break;
                
            case 'interrupted':
                phaseElement.classList.add('status-interrupted');
                statusElement.textContent = 'Stopped';  // Simplified text
                console.log(`PhaseManager: Set ${phaseId} to interrupted`);
                break;
                
            case 'pending':
            default:
                phaseElement.classList.add('status-pending');
                statusElement.textContent = 'Pending';  // Simplified text
                console.log(`PhaseManager: Set ${phaseId} to pending/default`);
                break;
        }
    }

    /**
     * Handle sub-phase completion and update parent if necessary
     */
    _handleSubPhaseCompletion(subPhaseId) {
        console.log(`PhaseManager: Checking sub-phase completion for ${subPhaseId}`);
        
        // Check if all sub-phases are completed
        const subPhaseStatuses = {};
        const allSubPhasesCompleted = this.subPhaseIds.every(id => {
            const element = document.querySelector(`[data-phase-id="${id}"]`);
            const isCompleted = element && (
                element.classList.contains('status-completed') || 
                element.classList.contains('status-skipped')
            );
            subPhaseStatuses[id] = {
                exists: !!element,
                completed: element ? element.classList.contains('status-completed') : false,
                skipped: element ? element.classList.contains('status-skipped') : false,
                isCompleted: isCompleted
            };
            return isCompleted;
        });

        console.log(`PhaseManager: Sub-phase statuses:`, subPhaseStatuses);
        console.log(`PhaseManager: All sub-phases completed: ${allSubPhasesCompleted}`);

        // If all sub-phases are completed/skipped, mark parent as completed
        if (allSubPhasesCompleted) {
            const parentElement = document.querySelector('[data-phase-id="content_processing_overall"]');
            if (parentElement && !parentElement.classList.contains('status-completed')) {
                console.log('PhaseManager: All sub-phases completed, marking content_processing_overall as completed');
                this.updatePhaseStatus('content_processing_overall', 'completed', 'All sub-phases completed');
            } else if (parentElement && parentElement.classList.contains('status-completed')) {
                console.log('PhaseManager: Parent content_processing_overall already marked as completed');
            } else {
                console.warn('PhaseManager: Parent content_processing_overall element not found');
            }
        } else {
            console.log('PhaseManager: Not all sub-phases completed yet, parent remains unchanged');
        }
    }

    /**
     * Apply preset configuration
     */
    applyPreset(presetType) {
        console.log(`PhaseManager: Applying preset: ${presetType}`);
        
        // Reset all phases to normal state initially
        Object.keys(this.phaseStates).forEach(phaseId => {
            if (phaseId === 'initialization' || phaseId === 'cleanup') {
                this.phaseStates[phaseId] = 'normal';
            } else {
                this.phaseStates[phaseId] = 'normal';
            }
        });
        
        switch (presetType) {
            case 'full_run':
                // All phases (except always-run) remain in normal state
                break;
                
            case 'synthesis_only':
                Object.keys(this.phaseStates).forEach(phaseId => {
                    if (phaseId !== 'initialization' && phaseId !== 'cleanup' && phaseId !== 'synthesis_generation') {
                        this.phaseStates[phaseId] = 'skip';
                    }
                });
                this.phaseStates.synthesis_generation = 'normal';
                break;
                
            case 'embedding_only':
                Object.keys(this.phaseStates).forEach(phaseId => {
                    if (phaseId !== 'initialization' && phaseId !== 'cleanup' && phaseId !== 'embedding_generation') {
                        this.phaseStates[phaseId] = 'skip';
                    }
                });
                this.phaseStates.embedding_generation = 'normal';
                break;
                
            case 'force_reprocess':
                const forcePhases = ['subphase_cp_cache', 'subphase_cp_media', 'subphase_cp_llm', 'subphase_cp_kbitem', 'synthesis_generation'];
                forcePhases.forEach(phaseId => {
                    if (this.phaseStates[phaseId] !== undefined) {
                       this.phaseStates[phaseId] = 'force';
                    }
                });
                break;
                
            case 'clear_all':
                // All phases (except always-run) reset to normal above
                break;
                
            default:
                console.warn(`PhaseManager: Unknown preset type: ${presetType}`);
                return;
        }
        
        // Update visual states for all phases
        Object.keys(this.phaseStates).forEach(phaseId => {
            const phaseElement = document.querySelector(`[data-phase-id="${phaseId}"]`);
            if (phaseElement) {
                const stateToApply = this.phaseStates[phaseId];
                if (this.phaseStateMapping[phaseId] && this.phaseStateMapping[phaseId][stateToApply]) {
                    phaseElement.setAttribute('data-phase-state', stateToApply);
                    this.updatePhaseVisualState(phaseElement, phaseId, stateToApply);
                } else if (phaseId === 'initialization' || phaseId === 'cleanup') {
                    phaseElement.setAttribute('data-phase-state', 'normal');
                    this.updatePhaseVisualState(phaseElement, phaseId, 'normal');
                }
            }
        });
        
        // Save the updated states
        this.savePhaseStates();
    }

    /**
     * Get current phase states for server preferences
     */
    getServerPreferences() {
        const prefs = {};
        
        // Check if synthesis_only mode should be used
        const skipBookmarks = this.phaseStates.fetch_bookmarks === 'skip';
        const skipContent = this.phaseStates.content_processing_overall === 'skip';
        const skipReadme = this.phaseStates.readme_generation === 'skip';
        const skipGit = this.phaseStates.git_sync === 'skip';
        const skipSynthesis = this.phaseStates.synthesis_generation === 'skip';
        
        if (skipBookmarks && skipContent && skipReadme && skipGit && !skipSynthesis) {
            prefs.run_mode = 'synthesis_only';
        } else {
            prefs.run_mode = 'full_pipeline';
        }
        
        prefs.force_recache_tweets = this.phaseStates.subphase_cp_cache === 'force';
        prefs.force_reprocess_media = this.phaseStates.subphase_cp_media === 'force';
        prefs.force_reprocess_llm = this.phaseStates.subphase_cp_llm === 'force';
        prefs.force_reprocess_kb_item = this.phaseStates.subphase_cp_kbitem === 'force';
        prefs.skip_fetch_bookmarks = this.phaseStates.fetch_bookmarks === 'skip';
        prefs.skip_process_content = this.phaseStates.content_processing_overall === 'skip';
        prefs.skip_readme_generation = this.phaseStates.readme_generation === 'skip';
        prefs.skip_synthesis_generation = this.phaseStates.synthesis_generation === 'skip';
        prefs.skip_git_push = this.phaseStates.git_sync === 'skip';
        prefs.force_regenerate_synthesis = this.phaseStates.synthesis_generation === 'force';

        return prefs;
    }

    applyActiveRunPreferencesToUI(activePrefs) {
        if (!activePrefs || Object.keys(activePrefs).length === 0) {
            console.log('PhaseManager: No active run preferences from server to apply.');
            return;
        }
        console.log('PhaseManager: Applying active run preferences to UI from server:', activePrefs);

        const preferenceToPhaseMapping = {
            'fetch_bookmarks': { skipKey: 'skip_fetch_bookmarks' },
            'content_processing_overall': { skipKey: 'skip_process_content' },
            'subphase_cp_cache': { forceKey: 'force_recache_tweets', parentPhaseId: 'content_processing_overall' },
            'subphase_cp_media': { forceKey: 'force_reprocess_media', parentPhaseId: 'content_processing_overall' },
            'subphase_cp_llm': { forceKey: 'force_reprocess_llm', parentPhaseId: 'content_processing_overall' },
            'subphase_cp_kbitem': { forceKey: 'force_reprocess_kb_item', parentPhaseId: 'content_processing_overall' },
            'subphase_cp_db': { parentPhaseId: 'content_processing_overall' }, // No direct skip/force, depends on parent
            'synthesis_generation': { skipKey: 'skip_synthesis_generation', forceKey: 'force_regenerate_synthesis' },
            'readme_generation': { skipKey: 'skip_readme_generation' }, // Assuming force for readme is not a direct pref
            'git_sync': { skipKey: 'skip_git_push' }
        };

        const isContentProcessingSkipped = activePrefs.skip_process_content === true;

        Object.keys(this.phaseStates).forEach(phaseId => {
            const phaseElement = document.querySelector(`[data-phase-id="${phaseId}"]`);
            if (!phaseElement) {
                return;
            }

            const mappingConfig = preferenceToPhaseMapping[phaseId];
            let targetState = 'normal'; 

            if (phaseId === 'initialization' || phaseId === 'cleanup') {
                targetState = 'normal'; // These are always normal for config purposes
            } else if (mappingConfig) {
                if (mappingConfig.parentPhaseId === 'content_processing_overall' && isContentProcessingSkipped) {
                    targetState = 'skip';
                } else {
                    if (mappingConfig.skipKey && activePrefs[mappingConfig.skipKey] === true) {
                        targetState = 'skip';
                    }
                    if (targetState !== 'skip' && mappingConfig.forceKey && activePrefs[mappingConfig.forceKey] === true) {
                        targetState = 'force';
                    }
                }
            }

            // Apply the determined state
            if (this.phaseStates[phaseId] !== targetState) {
                console.log(`PhaseManager: Phase ${phaseId}: current UI state ${this.phaseStates[phaseId]}, server activePref suggests ${targetState}. Updating.`);
                this.phaseStates[phaseId] = targetState;
                phaseElement.setAttribute('data-phase-state', targetState);
                this.updatePhaseVisualState(phaseElement, phaseId, targetState); // Corrected call
            }
        });
        
        // After all individual states are set, ensure parent phase visual is consistent
        // This is especially for content_processing_overall if its subphases were individually forced
        // but the parent itself was not set to skip.
        const parentOverallElement = document.querySelector('[data-phase-id="content_processing_overall"]');
        if (parentOverallElement && !isContentProcessingSkipped) {
            let allSubphasesSkipped = true;
            let anySubphaseForced = false;
            this.subPhaseIds.forEach(subId => {
                if (this.phaseStates[subId] !== 'skip') allSubphasesSkipped = false;
                if (this.phaseStates[subId] === 'force') anySubphaseForced = true;
            });

            // If all subphases ended up skipped (e.g. individually by some logic not covered) 
            // and parent is not 'skip' by direct pref, it makes sense to ensure it's normal or reflects force.
            // The main 'content_processing_overall' skip is handled by `isContentProcessingSkipped`.
            // If any sub-phase is 'force', the parent 'content_processing_overall' could also reflect a 'force' state if desired,
            // or remain 'normal' if it's just a container.
            // For now, if it wasn't skipped by preference, and any sub-phase is forced, 
            // we ensure the parent is at least 'normal' or 'force' if that preference existed directly for it.
            let overallTargetState = activePrefs.skip_process_content ? 'skip' : (activePrefs.force_reprocess_content ? 'force' : 'normal');
            if (this.phaseStates.content_processing_overall !== overallTargetState) {
                 this.phaseStates.content_processing_overall = overallTargetState;
                 parentOverallElement.setAttribute('data-phase-state', overallTargetState);
                 this.updatePhaseVisualState(parentOverallElement, 'content_processing_overall', overallTargetState);
            }
        }

        console.log('PhaseManager: Finished applying active run preferences to UI. New phaseStates:', JSON.parse(JSON.stringify(this.phaseStates)));
    }

    /**
     * Update ETC display in logs footer
     */
    updateETCDisplay(etcData) {
        const phaseEtcElement = document.getElementById('phaseEtcLogsFooter');
        if (!phaseEtcElement) return;
        
        // Show/hide ETC display based on agent status
        const agentIsRunning = window.agentIsRunning || false;
        
        if (!agentIsRunning || !etcData || (!etcData.estimated_remaining_minutes && !etcData.estimated_completion_timestamp)) {
            phaseEtcElement.style.display = 'none';
            return;
        }
        
        // Format the ETC message
        const remainingMinutes = etcData.estimated_remaining_minutes;
        let etcMessage = '';
        
        if (remainingMinutes !== undefined && remainingMinutes !== null) {
            if (remainingMinutes <= 0) {
                etcMessage = 'Phase ETC: Completing...';
            } else if (remainingMinutes < 0.1) {
                // Handle very small estimates that might be due to bad historical data
                if (etcData.phase_id === 'synthesis_generation' && etcData.total_count > 0) {
                    // Provide reasonable fallback for synthesis generation (assume 60s per synthesis)
                    const remainingItems = etcData.total_count - (etcData.processed_count || 0);
                    const fallbackMinutes = remainingItems * 1.0; // 1 minute per synthesis as fallback
                    etcMessage = `Phase ETC: ~${Math.round(fallbackMinutes)} min (estimated)`;
                } else {
                    etcMessage = 'Phase ETC: < 1 min';
                }
            } else if (remainingMinutes < 1) {
                etcMessage = 'Phase ETC: < 1 min';
            } else if (remainingMinutes < 60) {
                etcMessage = `Phase ETC: ${Math.round(remainingMinutes)} min`;
            } else {
                const hours = Math.floor(remainingMinutes / 60);
                const mins = Math.round(remainingMinutes % 60);
                etcMessage = `Phase ETC: ${hours}h ${mins}m`;
            }
            
            // Add phase-specific information if available
            if (etcData.phase_id && etcData.total_count && etcData.processed_count !== null) {
                const progress = etcData.processed_count / etcData.total_count * 100;
                etcMessage += ` (${Math.round(progress)}%)`;
            }
        } else if (etcData.estimated_completion_timestamp) {
            // Calculate remaining time from timestamp
            const now = Date.now() / 1000; // Convert to seconds
            const remainingSeconds = etcData.estimated_completion_timestamp - now;
            if (remainingSeconds > 0) {
                const remainingMins = remainingSeconds / 60;
                if (remainingMins < 0.1) {
                    // Same fallback logic for timestamp-based estimates
                    if (etcData.phase_id === 'synthesis_generation' && etcData.total_count > 0) {
                        const remainingItems = etcData.total_count - (etcData.processed_count || 0);
                        const fallbackMinutes = remainingItems * 1.0;
                        etcMessage = `Phase ETC: ~${Math.round(fallbackMinutes)} min (estimated)`;
                    } else {
                        etcMessage = 'Phase ETC: < 1 min';
                    }
                } else if (remainingMins < 1) {
                    etcMessage = 'Phase ETC: < 1 min';
                } else if (remainingMins < 60) {
                    etcMessage = `Phase ETC: ${Math.round(remainingMins)} min`;
                } else {
                    const hours = Math.floor(remainingMins / 60);
                    const mins = Math.round(remainingMins % 60);
                    etcMessage = `Phase ETC: ${hours}h ${mins}m`;
                }
            } else {
                etcMessage = 'Phase ETC: Completing...';
            }
        }
        
        // Add current processing speed info if available and reasonable
        if (etcData.current_avg_time_per_item && etcData.current_avg_time_per_item > 0.1) {
            const avgTime = etcData.current_avg_time_per_item;
            if (avgTime < 60) {
                etcMessage += ` (${avgTime.toFixed(1)}s/item)`;
            } else {
                etcMessage += ` (${(avgTime/60).toFixed(1)}min/item)`;
            }
        }
        
        phaseEtcElement.textContent = etcMessage;
        phaseEtcElement.style.display = 'inline';
        
        console.log(`ETC updated: ${etcMessage}`, etcData);
    }

    /**
     * Handle phase update with ETC information
     */
    handlePhaseUpdateWithETC(data) {
        console.log('handlePhaseUpdateWithETC called with data:', data);
        
        // Standard phase update
        if (data.processed_count !== null && data.processed_count !== undefined) {
            this.updateCurrentPhaseDetails(
                data.phase_id, 
                data.message || '', 
                data.processed_count, 
                data.total_count, 
                data.error_count
            );
            
            this.updatePhaseStatus(data.phase_id, data.status, data.message);
            this.updatePhaseExecutionStatus(data.phase_id, data.processed_count, data.total_count, data.error_count);
        } else {
            this.updatePhaseStatus(data.phase_id, data.status, data.message);
        }
        
        // Update ETC display if we have ETC data
        if (data.estimated_remaining_minutes !== undefined || data.estimated_completion_timestamp) {
            console.log('ETC data found, updating display:', {
                estimated_remaining_minutes: data.estimated_remaining_minutes,
                estimated_completion_timestamp: data.estimated_completion_timestamp,
                progress: data.processed_count && data.total_count ? (data.processed_count / data.total_count * 100) : null
            });
            
            this.updateETCDisplay({
                phase_id: data.phase_id,
                estimated_remaining_minutes: data.estimated_remaining_minutes,
                estimated_completion_timestamp: data.estimated_completion_timestamp,
                total_count: data.total_count,
                processed_count: data.processed_count,
                current_avg_time_per_item: data.current_avg_time_per_item,
                progress_percentage: data.progress_percentage
            });
        } else {
            console.log('No ETC data in phase update:', {
                has_estimated_remaining_minutes: 'estimated_remaining_minutes' in data,
                has_estimated_completion_timestamp: 'estimated_completion_timestamp' in data,
                estimated_remaining_minutes_value: data.estimated_remaining_minutes,
                estimated_completion_timestamp_value: data.estimated_completion_timestamp
            });
        }
    }

    /**
     * Hide ETC display when agent stops
     */
    hideETCDisplay() {
        const phaseEtcElement = document.getElementById('phaseEtcLogsFooter');
        if (phaseEtcElement) {
            phaseEtcElement.style.display = 'none';
        }
    }

    /**
     * Start periodic monitoring of sub-phase completion
     */
    startSubPhaseCompletionMonitor() {
        // Check every 2 seconds for sub-phase completion
        setInterval(() => {
            this.checkAndUpdateSubPhaseCompletion();
        }, 2000);
    }

    /**
     * Check sub-phase completion and update parent if needed
     */
    checkAndUpdateSubPhaseCompletion() {
        // Only check if there are sub-phase elements on the page
        const hasSubPhases = this.subPhaseIds.some(id => 
            document.querySelector(`[data-phase-id="${id}"]`) !== null
        );
        
        if (hasSubPhases) {
            this._handleSubPhaseCompletion('periodic_check');
        }
    }
}

// Export singleton instance
window.phaseManager = new PhaseManager(); 