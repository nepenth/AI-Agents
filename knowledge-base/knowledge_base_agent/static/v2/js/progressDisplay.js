/* V2 PROGRESSDISPLAY.JS - PROGRESS BARS AND ETC CALCULATIONS */

/**
 * ProgressDisplayManager - Comprehensive progress tracking and display
 * 
 * ARCHITECTURE:
 * - Manages multiple progress bars for different operations
 * - Calculates accurate ETC based on historical performance data
 * - Provides visual feedback for long-running operations
 * - Integrates with PhaseDisplayManager for coordinated updates
 */
class ProgressDisplayManager {
    constructor() {
        this.progressBars = new Map();
        this.progressHistory = new Map();
        this.etcCalculations = new Map();
        
        // Configuration
        this.updateInterval = 1000; // 1 second
        this.historyRetention = 100; // Keep last 100 progress updates per operation
        this.etcSmoothingFactor = 0.3; // Exponential smoothing factor
        
        // UI Elements
        this.progressContainer = document.getElementById('progress-container');
        this.globalProgressBar = document.getElementById('global-progress-bar');
        
        this.init();
    }
    
    init() {
        this.setupEventListeners();
        this.createProgressContainer();
        this.startProgressUpdates();
        
        // Register with component coordinator
        if (window.displayCoordinator) {
            window.displayCoordinator.registerComponent('ProgressDisplayManager', this, {
                priority: 70,
                dependencies: ['PhaseDisplayManager']
            });
        }
        
        console.log('📊 ProgressDisplayManager initialized');
    }
    
    setupEventListeners() {
        // Use centralized EventListenerService
        EventListenerService.setupStandardListeners(this, {
            customEvents: [
                {
                    event: 'progress_update',
                    handler: (e) => this.handleProgressUpdate(e.detail)
                },
                {
                    event: 'phase_start',
                    handler: (e) => this.handlePhaseStart(e.detail)
                },
                {
                    event: 'phase_complete',
                    handler: (e) => this.handlePhaseComplete(e.detail)
                },
                {
                    event: 'phase_error',
                    handler: (e) => this.handlePhaseError(e.detail)
                },
                {
                    event: 'agent_status_update',
                    handler: (e) => this.handleAgentStatusUpdate(e.detail)
                }
            ]
        });
    }
    
    createProgressContainer() {
        // Try to use existing progress containers first
        this.progressContainer = document.getElementById('progress-container');
        this.globalProgressBar = document.getElementById('global-progress-bar');
        this.globalProgressSection = document.getElementById('global-progress-section');
        
        // If no existing containers, integrate with existing panels
        if (!this.progressContainer) {
            this.integrateWithExistingPanels();
        }
        
        // If still no container, create minimal overlay
        if (!this.progressContainer) {
            this.createMinimalProgressOverlay();
        }
    }
    
    integrateWithExistingPanels() {
        // Try to integrate with agent status footer
        const statusFooter = document.getElementById('agent-status-footer');
        if (statusFooter) {
            // Add progress section to status footer
            const progressSection = document.createElement('div');
            progressSection.id = 'integrated-progress-section';
            progressSection.className = 'integrated-progress';
            progressSection.style.display = 'none';
            progressSection.innerHTML = `
                <div class="progress-header" style="margin-top: var(--space-3); margin-bottom: var(--space-2);">
                    <span style="font-size: var(--font-size-xs); color: var(--text-tertiary);">Overall Progress</span>
                    <span id="global-progress-text" style="font-size: var(--font-size-xs); color: var(--text-secondary);">0%</span>
                </div>
                <div id="global-progress-bar" class="progress-bar-container" style="height: 4px; background: var(--glass-bg-tertiary); border-radius: var(--radius-sm); overflow: hidden;">
                    <div class="progress-bar-fill" style="height: 100%; background: var(--gradient-primary); width: 0%; transition: width var(--duration-normal) var(--ease-smooth);"></div>
                </div>
                <div id="progress-container" class="progress-container" style="margin-top: var(--space-2);">
                    <!-- Individual progress bars will be added here -->
                </div>
            `;
            
            statusFooter.appendChild(progressSection);
            
            this.progressContainer = document.getElementById('progress-container');
            this.globalProgressBar = document.getElementById('global-progress-bar');
            this.globalProgressSection = progressSection;
            
            console.log('📊 ProgressDisplayManager integrated with status footer');
            return;
        }
        
        // Try to integrate with phase list
        const phaseList = document.getElementById('phase-list');
        if (phaseList && phaseList.parentNode) {
            // Add progress overlay to phase list container
            const progressOverlay = document.createElement('div');
            progressOverlay.id = 'phase-progress-overlay';
            progressOverlay.className = 'progress-overlay';
            progressOverlay.style.cssText = `
                position: absolute;
                bottom: 0;
                left: 0;
                right: 0;
                background: var(--glass-bg-secondary);
                border-top: 1px solid var(--glass-border-secondary);
                padding: var(--space-2);
                display: none;
            `;
            progressOverlay.innerHTML = `
                <div id="global-progress-bar" class="progress-bar-container" style="height: 3px; background: var(--glass-bg-tertiary); border-radius: var(--radius-sm); overflow: hidden;">
                    <div class="progress-bar-fill" style="height: 100%; background: var(--gradient-primary); width: 0%; transition: width var(--duration-normal) var(--ease-smooth);"></div>
                </div>
                <div id="progress-container" class="progress-container" style="margin-top: var(--space-1);">
                    <!-- Individual progress bars will be added here -->
                </div>
            `;
            
            // Make phase list container relative
            phaseList.parentNode.style.position = 'relative';
            phaseList.parentNode.appendChild(progressOverlay);
            
            this.progressContainer = document.getElementById('progress-container');
            this.globalProgressBar = document.getElementById('global-progress-bar');
            this.globalProgressSection = progressOverlay;
            
            console.log('📊 ProgressDisplayManager integrated with phase list');
            return;
        }
    }
    
    createMinimalProgressOverlay() {
        // Create minimal progress overlay as fallback
        const overlay = document.createElement('div');
        overlay.id = 'progress-overlay';
        overlay.className = 'progress-overlay-minimal';
        overlay.style.cssText = `
            position: fixed;
            top: 60px;
            right: 20px;
            width: 300px;
            background: var(--glass-bg-primary);
            border: 1px solid var(--glass-border-primary);
            border-radius: var(--radius-lg);
            padding: var(--space-3);
            z-index: 1000;
            display: none;
            backdrop-filter: blur(10px);
        `;
        overlay.innerHTML = `
            <div class="progress-header" style="display: flex; justify-content: space-between; align-items: center; margin-bottom: var(--space-2);">
                <span style="font-size: var(--font-size-sm); font-weight: 600;">Progress</span>
                <button id="progress-close-btn" style="background: none; border: none; color: var(--text-tertiary); cursor: pointer;">
                    <i class="fas fa-times"></i>
                </button>
            </div>
            <div id="global-progress-bar" class="progress-bar-container" style="height: 4px; background: var(--glass-bg-tertiary); border-radius: var(--radius-sm); overflow: hidden; margin-bottom: var(--space-2);">
                <div class="progress-bar-fill" style="height: 100%; background: var(--gradient-primary); width: 0%; transition: width var(--duration-normal) var(--ease-smooth);"></div>
            </div>
            <div id="progress-container" class="progress-container">
                <!-- Individual progress bars will be added here -->
            </div>
        `;
        
        document.body.appendChild(overlay);
        
        // Add close button functionality
        const closeBtn = overlay.querySelector('#progress-close-btn');
        closeBtn.addEventListener('click', () => {
            overlay.style.display = 'none';
        });
        
        this.progressContainer = document.getElementById('progress-container');
        this.globalProgressBar = document.getElementById('global-progress-bar');
        this.globalProgressSection = overlay;
        
        console.log('📊 ProgressDisplayManager created minimal overlay');
    }
    
    handleProgressUpdate(data) {
        const { 
            operation, 
            current, 
            total, 
            percentage, 
            task_id, 
            phase_name,
            message,
            timestamp 
        } = data;
        
        const progressId = operation || phase_name || task_id || 'default';
        
        console.log(`📊 Progress update: ${progressId}`, data);
        
        // Create or update progress bar
        this.updateProgressBar(progressId, {
            current: current || 0,
            total: total || 100,
            percentage: percentage || (total > 0 ? (current / total) * 100 : 0),
            message: message || `Processing ${progressId}`,
            timestamp: new Date(timestamp || Date.now())
        });
        
        // Update global progress
        this.updateGlobalProgress();
    }
    
    handlePhaseStart(data) {
        const { phase_name, phase_description, estimated_duration } = data;
        
        // Create progress bar for the phase
        this.createProgressBar(phase_name, {
            label: phase_description || this.formatLabel(phase_name),
            estimatedDuration: estimated_duration,
            type: 'phase'
        });
    }
    
    handlePhaseComplete(data) {
        const { phase_name } = data;
        
        // Mark progress bar as complete
        this.completeProgressBar(phase_name);
        
        // Update global progress
        this.updateGlobalProgress();
    }
    
    handlePhaseError(data) {
        const { phase_name, error } = data;
        
        // Mark progress bar as error
        this.errorProgressBar(phase_name, error);
        
        // Update global progress
        this.updateGlobalProgress();
    }
    
    handleAgentStatusUpdate(data) {
        const { is_running, status } = data;
        
        if (!is_running && (status === 'completed' || status === 'idle' || status === 'error')) {
            // Agent finished - hide global progress after delay
            setTimeout(() => {
                this.hideGlobalProgress();
                this.clearAllProgressBars();
            }, 3000);
        } else if (is_running) {
            // Agent started - show global progress
            this.showGlobalProgress();
        }
    }
    
    createProgressBar(progressId, options = {}) {
        if (this.progressBars.has(progressId)) {
            return this.progressBars.get(progressId);
        }
        
        const {
            label = this.formatLabel(progressId),
            estimatedDuration = null,
            type = 'operation',
            showETC = true
        } = options;
        
        const progressBar = {
            id: progressId,
            label: label,
            type: type,
            current: 0,
            total: 100,
            percentage: 0,
            message: '',
            startTime: new Date(),
            estimatedDuration: estimatedDuration,
            showETC: showETC,
            status: 'active',
            element: null,
            etcElement: null,
            history: []
        };
        
        // Create DOM element
        const element = document.createElement('div');
        element.className = `progress-item progress-${type}`;
        element.innerHTML = `
            <div class="progress-header">
                <div class="progress-label">
                    <span class="progress-title">${label}</span>
                    <span class="progress-percentage">0%</span>
                </div>
                <div class="progress-controls">
                    ${showETC ? '<span class="progress-etc">--</span>' : ''}
                    <button class="progress-hide-btn" title="Hide this progress bar">
                        <i class="fas fa-times"></i>
                    </button>
                </div>
            </div>
            <div class="progress-bar-container">
                <div class="progress-bar-fill" style="width: 0%"></div>
            </div>
            <div class="progress-message">Initializing...</div>
        `;
        
        // Add event listeners
        const hideBtn = element.querySelector('.progress-hide-btn');
        hideBtn.addEventListener('click', () => {
            this.hideProgressBar(progressId);
        });
        
        // Store references
        progressBar.element = element;
        progressBar.etcElement = element.querySelector('.progress-etc');
        
        // Add to container
        this.progressContainer.appendChild(element);
        
        // Store progress bar
        this.progressBars.set(progressId, progressBar);
        this.progressHistory.set(progressId, []);
        
        console.log(`📊 Created progress bar: ${progressId}`);
        
        return progressBar;
    }
    
    updateProgressBar(progressId, data) {
        let progressBar = this.progressBars.get(progressId);
        
        if (!progressBar) {
            progressBar = this.createProgressBar(progressId);
        }
        
        const { current, total, percentage, message, timestamp } = data;
        
        // Update progress data
        progressBar.current = current;
        progressBar.total = total;
        progressBar.percentage = percentage;
        progressBar.message = message || progressBar.message;
        
        // Add to history for ETC calculation
        const historyEntry = {
            timestamp: timestamp || new Date(),
            current: current,
            total: total,
            percentage: percentage
        };
        
        const history = this.progressHistory.get(progressId);
        history.push(historyEntry);
        
        // Limit history size
        if (history.length > this.historyRetention) {
            history.shift();
        }
        
        // Update DOM
        this.updateProgressBarDOM(progressBar);
        
        // Calculate and update ETC
        if (progressBar.showETC) {
            this.updateETC(progressBar);
        }
    }
    
    updateProgressBarDOM(progressBar) {
        if (!progressBar.element) return;
        
        // Optimize DOM update using performance optimizer
        if (window.performanceOptimizer) {
            window.performanceOptimizer.optimizeDOMUpdate(() => {
                this.performProgressBarDOMUpdate(progressBar);
            }, `progress-${progressBar.id}`, 'normal');
        } else {
            this.performProgressBarDOMUpdate(progressBar);
        }
    }
    
    performProgressBarDOMUpdate(progressBar) {
        const percentageElement = progressBar.element.querySelector('.progress-percentage');
        const fillElement = progressBar.element.querySelector('.progress-bar-fill');
        const messageElement = progressBar.element.querySelector('.progress-message');
        
        if (percentageElement) {
            percentageElement.textContent = `${Math.round(progressBar.percentage)}%`;
        }
        
        if (fillElement) {
            fillElement.style.width = `${Math.min(100, Math.max(0, progressBar.percentage))}%`;
            
            // Add visual feedback based on progress
            fillElement.className = 'progress-bar-fill';
            if (progressBar.percentage >= 100) {
                fillElement.classList.add('progress-complete');
            } else if (progressBar.percentage >= 75) {
                fillElement.classList.add('progress-high');
            } else if (progressBar.percentage >= 25) {
                fillElement.classList.add('progress-medium');
            } else {
                fillElement.classList.add('progress-low');
            }
        }
        
        if (messageElement) {
            messageElement.textContent = progressBar.message;
        }
        
        // Update status class
        progressBar.element.className = `progress-item progress-${progressBar.type} progress-status-${progressBar.status}`;
    }
    
    updateETC(progressBar) {
        if (!progressBar.etcElement || progressBar.percentage <= 0) return;
        
        const history = this.progressHistory.get(progressBar.id);
        if (!history || history.length < 2) {
            // Not enough data for ETC calculation
            if (progressBar.estimatedDuration) {
                const elapsed = new Date() - progressBar.startTime;
                const remaining = progressBar.estimatedDuration * 1000 - elapsed;
                if (remaining > 0) {
                    progressBar.etcElement.textContent = this.formatDuration(remaining);
                }
            }
            return;
        }
        
        // Calculate ETC based on recent progress
        const recentHistory = history.slice(-10); // Use last 10 data points
        const firstPoint = recentHistory[0];
        const lastPoint = recentHistory[recentHistory.length - 1];
        
        const timeDiff = lastPoint.timestamp - firstPoint.timestamp;
        const progressDiff = lastPoint.percentage - firstPoint.percentage;
        
        if (timeDiff > 0 && progressDiff > 0) {
            const remainingProgress = 100 - lastPoint.percentage;
            const progressRate = progressDiff / timeDiff; // percentage per millisecond
            const etcMs = remainingProgress / progressRate;
            
            // Apply exponential smoothing
            const currentETC = this.etcCalculations.get(progressBar.id) || etcMs;
            const smoothedETC = (this.etcSmoothingFactor * etcMs) + ((1 - this.etcSmoothingFactor) * currentETC);
            
            this.etcCalculations.set(progressBar.id, smoothedETC);
            
            if (smoothedETC > 0 && smoothedETC < 24 * 60 * 60 * 1000) { // Less than 24 hours
                progressBar.etcElement.textContent = this.formatDuration(smoothedETC);
            } else {
                progressBar.etcElement.textContent = '--';
            }
        }
    }
    
    completeProgressBar(progressId) {
        const progressBar = this.progressBars.get(progressId);
        if (!progressBar) return;
        
        progressBar.status = 'completed';
        progressBar.percentage = 100;
        progressBar.current = progressBar.total;
        progressBar.message = 'Completed';
        
        this.updateProgressBarDOM(progressBar);
        
        // Hide after delay
        setTimeout(() => {
            this.hideProgressBar(progressId);
        }, 5000);
    }
    
    errorProgressBar(progressId, error) {
        const progressBar = this.progressBars.get(progressId);
        if (!progressBar) return;
        
        progressBar.status = 'error';
        progressBar.message = `Error: ${error}`;
        
        this.updateProgressBarDOM(progressBar);
        
        // Add error styling
        if (progressBar.element) {
            progressBar.element.classList.add('progress-error');
        }
    }
    
    hideProgressBar(progressId) {
        const progressBar = this.progressBars.get(progressId);
        if (!progressBar || !progressBar.element) return;
        
        // Animate out
        progressBar.element.style.opacity = '0';
        progressBar.element.style.transform = 'translateX(-100%)';
        
        setTimeout(() => {
            if (progressBar.element && progressBar.element.parentNode) {
                progressBar.element.parentNode.removeChild(progressBar.element);
            }
            this.progressBars.delete(progressId);
            this.progressHistory.delete(progressId);
            this.etcCalculations.delete(progressId);
        }, 300);
    }
    
    updateGlobalProgress() {
        if (!this.globalProgressBar) return;
        
        const activeProgressBars = Array.from(this.progressBars.values())
            .filter(pb => pb.status === 'active' && pb.type === 'phase');
        
        if (activeProgressBars.length === 0) {
            this.hideGlobalProgress();
            return;
        }
        
        // Calculate overall progress
        let totalWeight = 0;
        let weightedProgress = 0;
        
        activeProgressBars.forEach(pb => {
            const weight = pb.estimatedDuration || 60; // Default weight
            totalWeight += weight;
            weightedProgress += (pb.percentage / 100) * weight;
        });
        
        const overallPercentage = totalWeight > 0 ? (weightedProgress / totalWeight) * 100 : 0;
        
        // Update global progress bar
        const fillElement = this.globalProgressBar.querySelector('.progress-bar-fill');
        const textElement = document.getElementById('global-progress-text');
        const detailsElement = document.getElementById('global-progress-details');
        
        if (fillElement) {
            fillElement.style.width = `${Math.min(100, Math.max(0, overallPercentage))}%`;
        }
        
        if (textElement) {
            textElement.textContent = `${Math.round(overallPercentage)}%`;
        }
        
        if (detailsElement) {
            const activePhases = activeProgressBars.map(pb => pb.label).join(', ');
            detailsElement.textContent = `Active: ${activePhases}`;
        }
        
        this.showGlobalProgress();
    }
    
    showGlobalProgress() {
        if (this.globalProgressSection) {
            this.globalProgressSection.style.display = 'block';
        }
    }
    
    hideGlobalProgress() {
        if (this.globalProgressSection) {
            this.globalProgressSection.style.display = 'none';
        }
    }
    
    clearAllProgressBars() {
        this.progressBars.forEach((progressBar, progressId) => {
            this.hideProgressBar(progressId);
        });
    }
    
    startProgressUpdates() {
        // Start periodic updates for ETC calculations
        setInterval(() => {
            this.progressBars.forEach(progressBar => {
                if (progressBar.status === 'active' && progressBar.showETC) {
                    this.updateETC(progressBar);
                }
            });
        }, this.updateInterval);
    }
    
    formatLabel(progressId) {
        return progressId.split('_')
            .map(word => word.charAt(0).toUpperCase() + word.slice(1))
            .join(' ');
    }
    
    formatDuration(milliseconds) {
        // Use centralized DurationFormatter service
        return DurationFormatter.format(milliseconds);
    }
    
    // === PUBLIC API ===
    
    createProgress(progressId, options = {}) {
        return this.createProgressBar(progressId, options);
    }
    
    updateProgress(progressId, current, total, message = null) {
        const percentage = total > 0 ? (current / total) * 100 : 0;
        this.updateProgressBar(progressId, {
            current,
            total,
            percentage,
            message,
            timestamp: new Date()
        });
    }
    
    setProgressMessage(progressId, message) {
        const progressBar = this.progressBars.get(progressId);
        if (progressBar) {
            progressBar.message = message;
            this.updateProgressBarDOM(progressBar);
        }
    }
    
    completeProgress(progressId) {
        this.completeProgressBar(progressId);
    }
    
    errorProgress(progressId, error) {
        this.errorProgressBar(progressId, error);
    }
    
    hideProgress(progressId) {
        this.hideProgressBar(progressId);
    }
    
    getProgress(progressId) {
        const progressBar = this.progressBars.get(progressId);
        return progressBar ? { ...progressBar } : null;
    }
    
    getAllProgress() {
        return Array.from(this.progressBars.values());
    }
    
    getProgressStatistics() {
        const stats = {
            total: this.progressBars.size,
            active: 0,
            completed: 0,
            error: 0,
            averageProgress: 0
        };
        
        let totalProgress = 0;
        
        this.progressBars.forEach(pb => {
            stats[pb.status] = (stats[pb.status] || 0) + 1;
            totalProgress += pb.percentage;
        });
        
        if (this.progressBars.size > 0) {
            stats.averageProgress = totalProgress / this.progressBars.size;
        }
        
        return stats;
    }
}

// Make globally available
window.ProgressDisplayManager = ProgressDisplayManager;