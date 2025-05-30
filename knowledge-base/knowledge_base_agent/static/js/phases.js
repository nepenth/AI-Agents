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
            cleanup: 'normal'
        };

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
            }
        };
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
        
        console.log(`PhaseManager: Phase ${phaseId} state changed to: ${newState}`);
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
                phaseElement.className = phaseElement.className.replace(/status-\w+|phase-state-\w+/g, '');
                phaseElement.classList.add('status-will-run');
                const statusElement = phaseElement.querySelector('.phase-status');
                if (statusElement) statusElement.textContent = 'Will Run';
            }
            return;
        }
        
        const statusElement = phaseElement.querySelector('.phase-status');
        
        let baseClasses = [];
        phaseElement.classList.forEach(cls => {
            if (!cls.startsWith('status-') && !cls.startsWith('phase-state-')) {
                baseClasses.push(cls);
            }
        });
        phaseElement.className = baseClasses.join(' ');

        if (stateConfig.class) {
            stateConfig.class.split(' ').forEach(cls => {
                if (cls) phaseElement.classList.add(cls);
            });
        }
        
        if (statusElement) {
            statusElement.textContent = stateConfig.label;
        }
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
            'readme_generation': 'README Generation',
            'git_sync': 'Git Synchronization',
            'cleanup': 'Cleanup'
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
                statusText = `✓ ${total_count} items`;
            } else {
                statusText += ` (${percentage}%)`;
            }
            
            if (error_count && error_count > 0) {
                statusText += ` ⚠️${error_count}`;
            }
            
            statusElement.textContent = statusText;
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
}

// Export singleton instance
window.phaseManager = new PhaseManager(); 