/**
 * Modern Schedule Manager
 * 
 * Features:
 * - Create and manage automated agent execution schedules
 * - View schedule history and execution logs
 * - Enable/disable schedules
 * - Run schedules manually
 * - Modern UI with glass morphism design
 */

class ModernScheduleManager extends BaseManager {
    constructor(options = {}) {
        super({
            enableLogging: true,
            autoInit: false,
            componentName: 'ModernScheduleManager',
            ...options
        });
        
        // Schedule state
        this.schedules = new Map();
        this.scheduleHistory = [];
        this.selectedSchedule = null;
    }
    
    async initializeElements() {
        this.elements.container = document.getElementById('main-content');
        if (!this.elements.container) {
            throw new Error('Main content container not found');
        }
        
        await this.createScheduleInterface();
        
        // Cache interactive elements
        this.elements.newScheduleBtn = document.getElementById('new-schedule-btn');
        this.elements.refreshBtn = document.getElementById('refresh-btn');
        this.elements.schedulesGrid = document.getElementById('schedules-grid');
        this.elements.historyTable = document.getElementById('history-table');
        this.elements.loadingState = document.getElementById('loading-state');
        this.elements.emptyState = document.getElementById('empty-state');
    }
    
    async setupEventListeners() {
        this.eventService.setupStandardListeners(this, {
            buttons: [
                {
                    selector: this.elements.newScheduleBtn,
                    handler: this.handleNewSchedule
                },
                {
                    selector: this.elements.refreshBtn,
                    handler: this.handleRefresh,
                    debounce: 1000
                }
            ],
            
            delegated: [
                {
                    container: this.elements.schedulesGrid,
                    selector: '.schedule-item',
                    event: 'click',
                    handler: this.handleScheduleClick
                },
                {
                    container: this.elements.schedulesGrid,
                    selector: '.schedule-action-btn',
                    event: 'click',
                    handler: this.handleScheduleAction
                }
            ]
        });
    }
    
    async loadInitialData() {
        try {
            this.showLoadingState();
            
            // Load schedules and history
            await Promise.all([
                this.loadSchedules(),
                this.loadScheduleHistory()
            ]);
            
            // Render the interface
            this.renderSchedules();
            this.renderHistory();
            
            this.setState({ 
                initialized: true,
                loading: false 
            });
            
        } catch (error) {
            this.setError(error, 'loading schedule data');
            this.showEmptyState('Failed to load schedule data');
        }
    }
    
    async createScheduleInterface() {
        this.elements.container.innerHTML = `
            <div class="modern-schedule-container glass-panel-v3 animate-glass-fade-in">
                <!-- Header -->
                <header class="schedule-header">
                    <div class="header-title">
                        <h1>
                            <i class="fas fa-calendar-alt"></i>
                            Schedule Management
                        </h1>
                        <p class="header-subtitle">Automate your agent execution</p>
                    </div>
                    
                    <div class="header-actions">
                        <button id="refresh-btn" class="glass-button glass-button--small" title="Refresh">
                            <i class="fas fa-sync-alt"></i>
                        </button>
                        <button id="new-schedule-btn" class="glass-button" title="New Schedule">
                            <i class="fas fa-plus"></i>
                            <span>New Schedule</span>
                        </button>
                    </div>
                </header>
                
                <!-- Content -->
                <div class="schedule-content">
                    <!-- Loading State -->
                    <div id="loading-state" class="loading-state">
                        <div class="loading-spinner"></div>
                        <span>Loading schedules...</span>
                    </div>
                    
                    <!-- Empty State -->
                    <div id="empty-state" class="empty-state hidden">
                        <i class="fas fa-calendar-alt"></i>
                        <h3>No schedules found</h3>
                        <p>Create your first automated schedule to get started</p>
                        <button class="glass-button create-first-btn">
                            <i class="fas fa-plus"></i>
                            Create First Schedule
                        </button>
                    </div>
                    
                    <!-- Schedules Section -->
                    <div class="schedules-section">
                        <div class="section-header">
                            <h2>Active Schedules</h2>
                            <div class="section-stats">
                                <span id="active-count" class="stat-badge">0 active</span>
                                <span id="total-count" class="stat-badge">0 total</span>
                            </div>
                        </div>
                        
                        <div id="schedules-grid" class="schedules-grid">
                            <!-- Schedules will be populated here -->
                        </div>
                    </div>
                    
                    <!-- History Section -->
                    <div class="history-section">
                        <div class="section-header">
                            <h2>Recent Executions</h2>
                            <button class="glass-button glass-button--small view-all-btn">
                                <span>View All</span>
                                <i class="fas fa-arrow-right"></i>
                            </button>
                        </div>
                        
                        <div class="history-table-container">
                            <table id="history-table" class="history-table">
                                <thead>
                                    <tr>
                                        <th>Schedule</th>
                                        <th>Execution Time</th>
                                        <th>Status</th>
                                        <th>Duration</th>
                                        <th>Items Processed</th>
                                    </tr>
                                </thead>
                                <tbody id="history-tbody">
                                    <!-- History will be populated here -->
                                </tbody>
                            </table>
                        </div>
                    </div>
                </div>
            </div>
            
            <!-- New Schedule Modal -->
            <div id="new-schedule-modal" class="schedule-modal hidden">
                <div class="modal-overlay"></div>
                <div class="modal-content">
                    <div class="modal-header">
                        <h3>Create New Schedule</h3>
                        <button class="modal-close-btn">
                            <i class="fas fa-times"></i>
                        </button>
                    </div>
                    <div class="modal-body">
                        <form id="schedule-form">
                            <div class="form-group">
                                <label for="schedule-name">Schedule Name</label>
                                <input type="text" id="schedule-name" class="glass-input" placeholder="Enter schedule name..." required>
                            </div>
                            
                            <div class="form-group">
                                <label for="schedule-frequency">Frequency</label>
                                <select id="schedule-frequency" class="glass-select" required>
                                    <option value="">Select frequency...</option>
                                    <option value="daily">Daily</option>
                                    <option value="weekly">Weekly</option>
                                    <option value="monthly">Monthly</option>
                                    <option value="custom">Custom (Cron)</option>
                                </select>
                            </div>
                            
                            <div class="form-group" id="time-group">
                                <label for="schedule-time">Time</label>
                                <input type="time" id="schedule-time" class="glass-input" required>
                            </div>
                            
                            <div class="form-group hidden" id="cron-group">
                                <label for="cron-expression">Cron Expression</label>
                                <input type="text" id="cron-expression" class="glass-input" placeholder="0 0 * * *">
                                <small class="form-help">Use standard cron format (minute hour day month weekday)</small>
                            </div>
                            
                            <div class="form-group">
                                <label for="pipeline-type">Pipeline Type</label>
                                <select id="pipeline-type" class="glass-select" required>
                                    <option value="">Select pipeline...</option>
                                    <option value="full">Full Processing</option>
                                    <option value="fetch_only">Fetch Bookmarks Only</option>
                                    <option value="process_only">Process Existing</option>
                                </select>
                            </div>
                            
                            <div class="form-group">
                                <label class="checkbox-label">
                                    <input type="checkbox" id="schedule-enabled" checked>
                                    <span class="checkmark"></span>
                                    Enable schedule immediately
                                </label>
                            </div>
                        </form>
                    </div>
                    <div class="modal-footer">
                        <button type="button" class="modal-btn secondary cancel-btn">Cancel</button>
                        <button type="submit" form="schedule-form" class="modal-btn primary">Create Schedule</button>
                    </div>
                </div>
            </div>
        `;
    }
    
    async loadSchedules() {
        try {
            const response = await this.apiCall('/schedules', {
                errorMessage: 'Failed to load schedules',
                cache: false
            });
            
            this.schedules.clear();
            
            if (response.schedules) {
                response.schedules.forEach(schedule => {
                    this.schedules.set(schedule.id, schedule);
                });
            }
            
            this.log(`Loaded ${this.schedules.size} schedules`);
            
        } catch (error) {
            this.logError('Failed to load schedules:', error);
            throw error;
        }
    }
    
    async loadScheduleHistory() {
        try {
            const response = await this.apiCall('/schedule-history', {
                errorMessage: 'Failed to load schedule history',
                cache: false
            });
            
            this.scheduleHistory = response.history || [];
            
            this.log(`Loaded ${this.scheduleHistory.length} history entries`);
            
        } catch (error) {
            this.logError('Failed to load schedule history:', error);
            // Don't throw - history is not critical
        }
    }
    
    renderSchedules() {
        if (!this.elements.schedulesGrid) return;
        
        const schedules = Array.from(this.schedules.values());
        
        if (schedules.length === 0) {
            this.showEmptyState();
            return;
        }
        
        this.hideLoadingState();
        this.hideEmptyState();
        
        const schedulesHTML = schedules.map(schedule => this.createScheduleHTML(schedule)).join('');
        this.elements.schedulesGrid.innerHTML = schedulesHTML;
        
        this.updateStats();
    }
    
    createScheduleHTML(schedule) {
        const isEnabled = schedule.enabled;
        const nextRun = schedule.next_run ? this.formatDate(schedule.next_run) : 'Not scheduled';
        const lastRun = schedule.last_run ? this.formatDate(schedule.last_run) : 'Never';
        const frequency = this.formatFrequency(schedule.frequency, schedule.time);
        
        return `
            <div class="schedule-item glass-panel-v3--interactive ${isEnabled ? 'enabled' : 'disabled'}" data-schedule-id="${schedule.id}">
                <div class="schedule-header">
                    <div class="schedule-status">
                        <div class="status-indicator ${isEnabled ? 'active' : 'inactive'}">
                            <i class="fas fa-${isEnabled ? 'play' : 'pause'}"></i>
                        </div>
                        <div class="schedule-info">
                            <h3 class="schedule-name">${schedule.name}</h3>
                            <p class="schedule-frequency">${frequency}</p>
                        </div>
                    </div>
                    
                    <div class="schedule-actions">
                        <button class="schedule-action-btn" data-action="toggle" title="${isEnabled ? 'Disable' : 'Enable'}">
                            <i class="fas fa-${isEnabled ? 'pause' : 'play'}"></i>
                        </button>
                        <button class="schedule-action-btn" data-action="run" title="Run Now">
                            <i class="fas fa-play-circle"></i>
                        </button>
                        <button class="schedule-action-btn" data-action="edit" title="Edit">
                            <i class="fas fa-edit"></i>
                        </button>
                        <button class="schedule-action-btn danger" data-action="delete" title="Delete">
                            <i class="fas fa-trash"></i>
                        </button>
                    </div>
                </div>
                
                <div class="schedule-details">
                    <div class="detail-item">
                        <span class="detail-label">Next Run:</span>
                        <span class="detail-value">${nextRun}</span>
                    </div>
                    <div class="detail-item">
                        <span class="detail-label">Last Run:</span>
                        <span class="detail-value">${lastRun}</span>
                    </div>
                    <div class="detail-item">
                        <span class="detail-label">Pipeline:</span>
                        <span class="detail-value">${schedule.pipeline_type || 'Full Processing'}</span>
                    </div>
                </div>
            </div>
        `;
    }
    
    formatFrequency(frequency, time) {
        switch (frequency) {
            case 'daily':
                return `Daily at ${time || '00:00'}`;
            case 'weekly':
                return `Weekly at ${time || '00:00'}`;
            case 'monthly':
                return `Monthly at ${time || '00:00'}`;
            case 'custom':
                return 'Custom schedule';
            default:
                return 'Manual only';
        }
    }
    
    renderHistory() {
        const tbody = document.getElementById('history-tbody');
        if (!tbody) return;
        
        if (this.scheduleHistory.length === 0) {
            tbody.innerHTML = `
                <tr>
                    <td colspan="5" class="no-history">
                        <i class="fas fa-info-circle"></i>
                        <span>No execution history available</span>
                    </td>
                </tr>
            `;
            return;
        }
        
        const historyHTML = this.scheduleHistory.slice(0, 10).map(entry => this.createHistoryRowHTML(entry)).join('');
        tbody.innerHTML = historyHTML;
    }
    
    createHistoryRowHTML(entry) {
        const schedule = this.schedules.get(entry.schedule_id);
        const scheduleName = schedule ? schedule.name : `Schedule ${entry.schedule_id}`;
        const executionTime = this.formatDateTime(entry.execution_time);
        const duration = entry.duration || '--';
        const processedItems = entry.processed_items || 0;
        
        const statusClass = entry.status === 'completed' ? 'success' : 
                           entry.status === 'failed' ? 'error' : 'warning';
        
        return `
            <tr class="history-row">
                <td class="schedule-name-cell">${scheduleName}</td>
                <td class="execution-time-cell">${executionTime}</td>
                <td class="status-cell">
                    <span class="status-badge ${statusClass}">${entry.status}</span>
                </td>
                <td class="duration-cell">${duration}</td>
                <td class="items-cell">${processedItems}</td>
            </tr>
        `;
    }
    
    formatDate(dateString) {
        if (!dateString) return 'Unknown';
        
        const date = new Date(dateString);
        const now = new Date();
        const diffMs = now - date;
        const diffDays = Math.floor(diffMs / (1000 * 60 * 60 * 24));
        
        if (diffDays === 0) {
            return 'Today';
        } else if (diffDays === 1) {
            return 'Tomorrow';
        } else if (diffDays < 7) {
            return `In ${diffDays} days`;
        } else {
            return date.toLocaleDateString();
        }
    }
    
    formatDateTime(dateString) {
        if (!dateString) return 'Unknown';
        
        const date = new Date(dateString);
        return date.toLocaleString();
    }
    
    updateStats() {
        const activeCount = Array.from(this.schedules.values()).filter(s => s.enabled).length;
        const totalCount = this.schedules.size;
        
        const activeCountEl = document.getElementById('active-count');
        const totalCountEl = document.getElementById('total-count');
        
        if (activeCountEl) activeCountEl.textContent = `${activeCount} active`;
        if (totalCountEl) totalCountEl.textContent = `${totalCount} total`;
    }
    
    showLoadingState() {
        if (this.elements.loadingState) {
            this.elements.loadingState.classList.remove('hidden');
        }
        const sectionsContainer = document.querySelector('.schedules-section');
        if (sectionsContainer) {
            sectionsContainer.style.display = 'none';
        }
        if (this.elements.emptyState) {
            this.elements.emptyState.classList.add('hidden');
        }
    }
    
    hideLoadingState() {
        if (this.elements.loadingState) {
            this.elements.loadingState.classList.add('hidden');
        }
        const sectionsContainer = document.querySelector('.schedules-section');
        if (sectionsContainer) {
            sectionsContainer.style.display = 'block';
        }
    }
    
    showEmptyState(message = null) {
        if (this.elements.emptyState) {
            this.elements.emptyState.classList.remove('hidden');
            if (message) {
                const messageEl = this.elements.emptyState.querySelector('p');
                if (messageEl) messageEl.textContent = message;
            }
        }
        const sectionsContainer = document.querySelector('.schedules-section');
        if (sectionsContainer) {
            sectionsContainer.style.display = 'none';
        }
        if (this.elements.loadingState) {
            this.elements.loadingState.classList.add('hidden');
        }
    }
    
    hideEmptyState() {
        if (this.elements.emptyState) {
            this.elements.emptyState.classList.add('hidden');
        }
    }
    
    // Event Handlers
    handleNewSchedule = () => {
        this.showNewScheduleModal();
    }
    
    handleRefresh = async () => {
        await this.loadInitialData();
    }
    
    handleScheduleClick = (e) => {
        const scheduleElement = e.target.closest('.schedule-item');
        if (!scheduleElement) return;
        
        const scheduleId = parseInt(scheduleElement.dataset.scheduleId);
        this.viewScheduleDetails(scheduleId);
    }
    
    handleScheduleAction = async (e) => {
        e.stopPropagation();
        
        const action = e.target.closest('.schedule-action-btn').dataset.action;
        const scheduleElement = e.target.closest('.schedule-item');
        const scheduleId = parseInt(scheduleElement.dataset.scheduleId);
        
        switch (action) {
            case 'toggle':
                await this.toggleSchedule(scheduleId);
                break;
            case 'run':
                await this.runSchedule(scheduleId);
                break;
            case 'edit':
                this.editSchedule(scheduleId);
                break;
            case 'delete':
                await this.deleteSchedule(scheduleId);
                break;
        }
    }
    
    showNewScheduleModal() {
        const modal = document.getElementById('new-schedule-modal');
        if (modal) {
            modal.classList.remove('hidden');
        }
    }
    
    async toggleSchedule(scheduleId) {
        try {
            await this.apiCall(`/schedules/${scheduleId}/toggle`, {
                method: 'POST',
                errorMessage: 'Failed to toggle schedule'
            });
            
            // Refresh the schedules
            await this.loadSchedules();
            this.renderSchedules();
            
            this.log(`Schedule ${scheduleId} toggled`);
            
        } catch (error) {
            this.setError(error, `toggling schedule ${scheduleId}`);
        }
    }
    
    async runSchedule(scheduleId) {
        try {
            await this.apiCall(`/schedules/${scheduleId}/run`, {
                method: 'POST',
                errorMessage: 'Failed to run schedule'
            });
            
            this.log(`Schedule ${scheduleId} started manually`);
            
            // Refresh history after a short delay
            setTimeout(async () => {
                await this.loadScheduleHistory();
                this.renderHistory();
            }, 2000);
            
        } catch (error) {
            this.setError(error, `running schedule ${scheduleId}`);
        }
    }
    
    editSchedule(scheduleId) {
        const schedule = this.schedules.get(scheduleId);
        if (!schedule) return;
        
        // This would open the edit modal with pre-filled data
        console.log('Editing schedule:', schedule);
    }
    
    async deleteSchedule(scheduleId) {
        const schedule = this.schedules.get(scheduleId);
        if (!schedule) return;
        
        if (!confirm(`Are you sure you want to delete the schedule "${schedule.name}"?`)) {
            return;
        }
        
        try {
            await this.apiCall(`/schedules/${scheduleId}`, {
                method: 'DELETE',
                errorMessage: 'Failed to delete schedule'
            });
            
            // Refresh the schedules
            await this.loadSchedules();
            this.renderSchedules();
            
            this.log(`Schedule ${scheduleId} deleted`);
            
        } catch (error) {
            this.setError(error, `deleting schedule ${scheduleId}`);
        }
    }
    
    viewScheduleDetails(scheduleId) {
        const schedule = this.schedules.get(scheduleId);
        if (!schedule) return;
        
        // This would show detailed schedule information
        console.log('Viewing schedule details:', schedule);
    }
    
    cleanup() {
        this.cleanupService.cleanup(this);
    }
}

// Export for use in other modules
window.ModernScheduleManager = ModernScheduleManager;