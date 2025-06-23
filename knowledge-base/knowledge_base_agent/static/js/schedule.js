/**
 * schedule.js
 * Handles schedule management functionality including creating, editing, deleting and viewing schedules
 */

class ScheduleManager {
    constructor() {
        console.log('ScheduleManager constructor called');
        this.schedules = [];
        this.history = [];
        this.init();
    }

    init() {
        console.log('ScheduleManager init called');
        this.bindEvents();
        this.loadSchedules();
        this.loadHistory();
        this.updateFrequencyOptions();
        console.log('ScheduleManager initialization complete');
    }

    bindEvents() {
        // Form submission handlers
        const saveBtn = document.getElementById('save-schedule-btn');
        const updateBtn = document.getElementById('update-schedule-btn');
        
        if (saveBtn) {
            saveBtn.addEventListener('click', () => {
                console.log('Save schedule button clicked!');
                this.saveSchedule();
            });
        } else {
            console.error('Save schedule button not found!');
        }
        
        if (updateBtn) {
            updateBtn.addEventListener('click', () => this.updateSchedule());
        }
        
        // Frequency change handler for add form
        const frequencySelect = document.getElementById('schedule-frequency');
        if (frequencySelect) {
            frequencySelect.addEventListener('change', (e) => this.updateFrequencyOptions(e.target.value));
        }
        
        // Frequency change handler for edit form
        const editFrequencySelect = document.getElementById('edit-schedule-frequency');
        if (editFrequencySelect) {
            editFrequencySelect.addEventListener('change', (e) => this.updateEditFormFrequencyOptions(e.target.value));
        }
        
        // Pipeline configuration change handler for add form
        const pipelineSelect = document.getElementById('schedule-pipeline');
        if (pipelineSelect) {
            pipelineSelect.addEventListener('change', (e) => this.updatePipelineOptions(e.target.value));
        }
        
        // Pipeline configuration change handler for edit form
        const editPipelineSelect = document.getElementById('edit-schedule-pipeline');
        if (editPipelineSelect) {
            editPipelineSelect.addEventListener('change', (e) => this.updateEditFormPipelineOptions(e.target.value));
        }
        
        // Form reset on modal hide
        const addModal = document.getElementById('addScheduleModal');
        if (addModal) {
            addModal.addEventListener('hidden.bs.modal', () => this.resetForm());
        }
        
        const editModal = document.getElementById('editScheduleModal');
        if (editModal) {
            editModal.addEventListener('hidden.bs.modal', () => this.resetEditForm());
        }
        
        // Refresh schedules every 30 seconds
        setInterval(() => this.loadSchedules(), 30000);
    }

    updateFrequencyOptions(frequency = null) {
        if (!frequency) frequency = document.getElementById('schedule-frequency').value;
        
        const timeConfig = document.getElementById('time-config');
        const dayOfWeekConfig = document.getElementById('day-of-week-config');
        const dayOfMonthConfig = document.getElementById('day-of-month-config');
        const cronConfig = document.getElementById('cron-config');
        
        // Hide all configs first
        dayOfWeekConfig.style.display = 'none';
        dayOfMonthConfig.style.display = 'none';
        cronConfig.style.display = 'none';
        timeConfig.style.display = 'block';
        
        switch (frequency) {
            case 'weekly':
                dayOfWeekConfig.style.display = 'block';
                break;
            case 'monthly':
                dayOfMonthConfig.style.display = 'block';
                break;
            case 'custom':
                timeConfig.style.display = 'none';
                cronConfig.style.display = 'block';
                break;
            case 'manual':
                timeConfig.style.display = 'none';
                break;
        }
    }

    updatePipelineOptions(pipeline = null) {
        if (!pipeline) pipeline = document.getElementById('schedule-pipeline').value;
        
        const customConfig = document.getElementById('custom-pipeline-config');
        
        if (pipeline === 'custom') {
            customConfig.style.display = 'block';
        } else {
            customConfig.style.display = 'none';
            // Set predefined configurations
            this.setPipelineDefaults(pipeline);
        }
    }

    setPipelineDefaults(pipeline) {
        const checkboxes = document.querySelectorAll('#custom-pipeline-config input[type="checkbox"]');
        checkboxes.forEach(checkbox => checkbox.checked = false);
        
        switch (pipeline) {
            case 'fetch-only':
                document.getElementById('skip-process-content').checked = true;
                break;
            case 'process-only':
                document.getElementById('skip-fetch-bookmarks').checked = true;
                break;
            // 'full' and other cases use default (all unchecked)
        }
    }

    async loadSchedules() {
        try {
            const response = await fetch('/api/schedules');
            if (response.ok) {
                this.schedules = await response.json();
                this.renderSchedules();
            } else {
                console.error('Failed to load schedules');
                this.showNoSchedulesMessage();
            }
        } catch (error) {
            console.error('Error loading schedules:', error);
            this.showNoSchedulesMessage();
        }
    }

    async loadHistory() {
        try {
            const response = await fetch('/api/schedule-history');
            if (response.ok) {
                this.history = await response.json();
                this.renderHistory();
            } else {
                console.error('Failed to load schedule history');
            }
        } catch (error) {
            console.error('Error loading schedule history:', error);
        }
    }

    renderSchedules() {
        const container = document.getElementById('active-schedules');
        const noSchedulesMessage = document.getElementById('no-schedules-message');
        
        if (this.schedules.length === 0) {
            this.showNoSchedulesMessage();
            return;
        }
        
        noSchedulesMessage.style.display = 'none';
        container.innerHTML = '';
        
        this.schedules.forEach(schedule => {
            const card = this.createScheduleCard(schedule);
            container.appendChild(card);
        });
    }

    createScheduleCard(schedule) {
        const card = document.createElement('div');
        card.className = 'col-md-6 col-lg-4 mb-3';
        
        const statusClass = schedule.enabled ? 'text-success' : 'text-muted';
        const statusIcon = schedule.enabled ? 'bi-play-circle-fill' : 'bi-pause-circle-fill';
        const nextRun = schedule.next_run ? new Date(schedule.next_run).toLocaleString() : 'N/A';
        
        card.innerHTML = `
            <div class="card h-100">
                <div class="card-header d-flex justify-content-between align-items-center">
                    <h6 class="mb-0">${schedule.name}</h6>
                    <span class="${statusClass}">
                        <i class="bi ${statusIcon}"></i>
                    </span>
                </div>
                <div class="card-body">
                    <p class="card-text small text-muted mb-2">${schedule.description || 'No description'}</p>
                    <div class="d-flex justify-content-between small">
                        <div>
                            <strong>Frequency:</strong><br>
                            ${this.formatFrequency(schedule)}
                        </div>
                        <div>
                            <strong>Next Run:</strong><br>
                            ${nextRun}
                        </div>
                    </div>
                    <div class="mt-2 small">
                        <strong>Pipeline:</strong> ${schedule.pipeline_type}
                    </div>
                </div>
                <div class="card-footer">
                    <div class="btn-group btn-group-sm w-100" role="group">
                        <button type="button" class="btn btn-outline-primary" onclick="scheduleManager.editSchedule(${schedule.id})">
                            <i class="bi bi-pencil"></i> Edit
                        </button>
                        <button type="button" class="btn btn-outline-${schedule.enabled ? 'warning' : 'success'}" 
                                onclick="scheduleManager.toggleSchedule(${schedule.id})">
                            <i class="bi bi-${schedule.enabled ? 'pause' : 'play'}"></i> ${schedule.enabled ? 'Pause' : 'Resume'}
                        </button>
                        <button type="button" class="btn btn-outline-info" onclick="scheduleManager.runScheduleNow(${schedule.id})">
                            <i class="bi bi-play-fill"></i> Run Now
                        </button>
                        <button type="button" class="btn btn-outline-danger" onclick="scheduleManager.deleteSchedule(${schedule.id})">
                            <i class="bi bi-trash"></i>
                        </button>
                    </div>
                </div>
            </div>
        `;
        
        return card;
    }

    formatFrequency(schedule) {
        switch (schedule.frequency) {
            case 'daily':
                return `Daily at ${schedule.time}`;
            case 'weekly':
                const days = ['Sunday', 'Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday'];
                return `Weekly on ${days[schedule.day_of_week]} at ${schedule.time}`;
            case 'monthly':
                return `Monthly on day ${schedule.day_of_month} at ${schedule.time}`;
            case 'custom':
                return `Custom: ${schedule.cron_expression}`;
            case 'manual':
                return 'Manual execution only';
            default:
                return schedule.frequency;
        }
    }

    renderHistory() {
        const tbody = document.getElementById('schedule-history-body');
        tbody.innerHTML = '';
        
        if (this.history.length === 0) {
            tbody.innerHTML = '<tr><td colspan="6" class="text-center text-muted py-3">No execution history found</td></tr>';
            return;
        }
        
        this.history.forEach(execution => {
            const row = document.createElement('tr');
            const statusClass = execution.status === 'completed' ? 'success' : 
                              execution.status === 'failed' ? 'danger' : 'warning';
            
            row.innerHTML = `
                <td>${execution.schedule_name}</td>
                <td>${new Date(execution.execution_time).toLocaleString()}</td>
                <td><span class="badge bg-${statusClass}">${execution.status}</span></td>
                <td>${execution.duration || 'N/A'}</td>
                <td>${execution.processed_items || 0}</td>
                <td>
                    <button class="btn btn-sm btn-outline-info" onclick="scheduleManager.viewExecutionDetails('${execution.id}')">
                        <i class="bi bi-eye"></i> Details
                    </button>
                </td>
            `;
            
            tbody.appendChild(row);
        });
    }

    showNoSchedulesMessage() {
        document.getElementById('active-schedules').innerHTML = '';
        document.getElementById('no-schedules-message').style.display = 'block';
    }

    async saveSchedule() {
        console.log('saveSchedule method called');
        
        // Validate form first
        const form = document.getElementById('schedule-form');
        if (!form.checkValidity()) {
            console.log('Form validation failed');
            form.reportValidity();
            return;
        }
        
        const formData = this.getFormData('schedule-form');
        console.log('Form data collected:', formData);
        
        // Basic validation
        if (!formData.name || !formData.frequency) {
            this.showErrorMessage('Please fill in all required fields');
            return;
        }
        
        try {
            console.log('Sending request to /api/schedules');
            const response = await fetch('/api/schedules', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify(formData)
            });
            
            console.log('Response received:', response.status);
            
            if (response.ok) {
                const result = await response.json();
                console.log('Schedule created successfully:', result);
                this.showSuccessMessage('Schedule created successfully!');
                bootstrap.Modal.getInstance(document.getElementById('addScheduleModal')).hide();
                this.loadSchedules();
            } else {
                const error = await response.json();
                console.error('Error response:', error);
                this.showErrorMessage(error.message || 'Failed to create schedule');
            }
        } catch (error) {
            console.error('Error saving schedule:', error);
            this.showErrorMessage('An error occurred while saving the schedule');
        }
    }

    async updateSchedule() {
        const formData = this.getFormData('edit-schedule-form');
        const scheduleId = document.getElementById('edit-schedule-id').value;
        
        try {
            const response = await fetch(`/api/schedules/${scheduleId}`, {
                method: 'PUT',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify(formData)
            });
            
            if (response.ok) {
                this.showSuccessMessage('Schedule updated successfully!');
                bootstrap.Modal.getInstance(document.getElementById('editScheduleModal')).hide();
                this.loadSchedules();
            } else {
                const error = await response.json();
                this.showErrorMessage(error.message || 'Failed to update schedule');
            }
        } catch (error) {
            console.error('Error updating schedule:', error);
            this.showErrorMessage('An error occurred while updating the schedule');
        }
    }

    async deleteSchedule(scheduleId) {
        if (!confirm('Are you sure you want to delete this schedule? This action cannot be undone.')) {
            return;
        }
        
        try {
            const response = await fetch(`/api/schedules/${scheduleId}`, {
                method: 'DELETE'
            });
            
            if (response.ok) {
                this.showSuccessMessage('Schedule deleted successfully!');
                this.loadSchedules();
            } else {
                const error = await response.json();
                this.showErrorMessage(error.message || 'Failed to delete schedule');
            }
        } catch (error) {
            console.error('Error deleting schedule:', error);
            this.showErrorMessage('An error occurred while deleting the schedule');
        }
    }

    async toggleSchedule(scheduleId) {
        try {
            const response = await fetch(`/api/schedules/${scheduleId}/toggle`, {
                method: 'POST'
            });
            
            if (response.ok) {
                this.loadSchedules();
            } else {
                const error = await response.json();
                this.showErrorMessage(error.message || 'Failed to toggle schedule');
            }
        } catch (error) {
            console.error('Error toggling schedule:', error);
            this.showErrorMessage('An error occurred while toggling the schedule');
        }
    }

    async runScheduleNow(scheduleId) {
        if (!confirm('Are you sure you want to run this schedule now?')) {
            return;
        }
        
        try {
            const response = await fetch(`/api/schedules/${scheduleId}/run`, {
                method: 'POST'
            });
            
            if (response.ok) {
                this.showSuccessMessage('Schedule execution started!');
                this.loadHistory();
            } else {
                const error = await response.json();
                this.showErrorMessage(error.message || 'Failed to run schedule');
            }
        } catch (error) {
            console.error('Error running schedule:', error);
            this.showErrorMessage('An error occurred while running the schedule');
        }
    }

    editSchedule(scheduleId) {
        // Find the schedule and populate the edit form
        const schedule = this.schedules.find(s => s.id === scheduleId);
        if (!schedule) {
            this.showErrorMessage('Schedule not found');
            return;
        }
        
        // Populate edit form fields
        document.getElementById('edit-schedule-id').value = schedule.id;
        document.getElementById('edit-schedule-name').value = schedule.name;
        document.getElementById('edit-schedule-frequency').value = schedule.frequency;
        document.getElementById('edit-schedule-time').value = schedule.time || '02:00';
        document.getElementById('edit-schedule-description').value = schedule.description || '';
        document.getElementById('edit-schedule-enabled').checked = schedule.enabled;
        
        // Set frequency-specific fields
        if (schedule.frequency === 'weekly' && schedule.day_of_week !== null) {
            document.getElementById('edit-schedule-day').value = schedule.day_of_week;
        }
        if (schedule.frequency === 'monthly' && schedule.day_of_month !== null) {
            document.getElementById('edit-schedule-date').value = schedule.day_of_month;
        }
        if (schedule.frequency === 'custom' && schedule.cron_expression) {
            document.getElementById('edit-schedule-cron').value = schedule.cron_expression;
        }
        
        // Set pipeline configuration
        document.getElementById('edit-schedule-pipeline').value = schedule.pipeline_type || 'full';
        
        // Set pipeline options
        document.getElementById('edit-skip-fetch-bookmarks').checked = schedule.skip_fetch_bookmarks || false;
        document.getElementById('edit-skip-process-content').checked = schedule.skip_process_content || false;
        document.getElementById('edit-force-recache').checked = schedule.force_recache_tweets || false;
        document.getElementById('edit-force-reprocess-media').checked = schedule.force_reprocess_media || false;
        document.getElementById('edit-force-reprocess-llm').checked = schedule.force_reprocess_llm || false;
        document.getElementById('edit-force-reprocess-kb').checked = schedule.force_reprocess_kb_item || false;
        
        // Update the edit form's dynamic fields
        this.updateEditFormFrequencyOptions(schedule.frequency);
        this.updateEditFormPipelineOptions(schedule.pipeline_type || 'full');
        
        // Show edit modal
        new bootstrap.Modal(document.getElementById('editScheduleModal')).show();
    }

    updateEditFormFrequencyOptions(frequency) {
        const timeConfig = document.getElementById('edit-time-config');
        const dayOfWeekConfig = document.getElementById('edit-day-of-week-config');
        const dayOfMonthConfig = document.getElementById('edit-day-of-month-config');
        const cronConfig = document.getElementById('edit-cron-config');
        
        // Hide all configs first
        dayOfWeekConfig.style.display = 'none';
        dayOfMonthConfig.style.display = 'none';
        cronConfig.style.display = 'none';
        timeConfig.style.display = 'block';
        
        switch (frequency) {
            case 'weekly':
                dayOfWeekConfig.style.display = 'block';
                break;
            case 'monthly':
                dayOfMonthConfig.style.display = 'block';
                break;
            case 'custom':
                timeConfig.style.display = 'none';
                cronConfig.style.display = 'block';
                break;
            case 'manual':
                timeConfig.style.display = 'none';
                break;
        }
    }

    updateEditFormPipelineOptions(pipeline) {
        const customConfig = document.getElementById('edit-custom-pipeline-config');
        
        if (pipeline === 'custom') {
            customConfig.style.display = 'block';
        } else {
            customConfig.style.display = 'none';
            // Set predefined configurations
            this.setEditFormPipelineDefaults(pipeline);
        }
    }

    setEditFormPipelineDefaults(pipeline) {
        const checkboxes = document.querySelectorAll('#edit-custom-pipeline-config input[type="checkbox"]');
        checkboxes.forEach(checkbox => checkbox.checked = false);
        
        switch (pipeline) {
            case 'fetch-only':
                document.getElementById('edit-skip-process-content').checked = true;
                break;
            case 'process-only':
                document.getElementById('edit-skip-fetch-bookmarks').checked = true;
                break;
            // 'full' and other cases use default (all unchecked)
        }
    }

    viewExecutionDetails(executionId) {
        // Implementation for viewing execution details
        console.log('View execution details for:', executionId);
    }

    getFormData(formId) {
        const form = document.getElementById(formId);
        const formData = new FormData(form);
        const data = {};
        
        // Convert FormData to object
        for (const [key, value] of formData.entries()) {
            if (data[key]) {
                // Handle multiple values (like checkboxes)
                if (Array.isArray(data[key])) {
                    data[key].push(value);
                } else {
                    data[key] = [data[key], value];
                }
            } else {
                data[key] = value;
            }
        }
        
        // Handle checkboxes that are unchecked (they won't appear in FormData)
        const checkboxes = form.querySelectorAll('input[type="checkbox"]');
        checkboxes.forEach(checkbox => {
            if (!checkbox.checked && !data.hasOwnProperty(checkbox.name)) {
                data[checkbox.name] = false;
            } else if (checkbox.checked) {
                data[checkbox.name] = true;
            }
        });
        
        // Map form field names to API expected names
        const mappedData = {
            name: data['name'],
            description: data['description'],
            frequency: data['frequency'],
            time: data['time'],
            day: data['day'],
            date: data['date'],
            cron: data['cron'],
            pipeline: data['pipeline'],
            enabled: data['enabled'] !== false, // Convert to boolean, default true
            skip_fetch_bookmarks: data['skip_fetch_bookmarks'] || false,
            skip_process_content: data['skip_process_content'] || false,
            force_recache_tweets: data['force_recache_tweets'] || false,
            force_reprocess_media: data['force_reprocess_media'] || false,
            force_reprocess_llm: data['force_reprocess_llm'] || false,
            force_reprocess_kb_item: data['force_reprocess_kb_item'] || false
        };
        
        return mappedData;
    }

    resetForm() {
        document.getElementById('schedule-form').reset();
        document.getElementById('schedule-frequency').value = '';
        this.updateFrequencyOptions();
        this.updatePipelineOptions();
    }

    resetEditForm() {
        document.getElementById('edit-schedule-form').reset();
        document.getElementById('edit-schedule-frequency').value = '';
        this.updateEditFormFrequencyOptions();
        this.updateEditFormPipelineOptions();
    }

    showSuccessMessage(message) {
        this.showToast(message, 'success');
    }

    showErrorMessage(message) {
        this.showToast(message, 'danger');
    }

    showToast(message, type = 'info') {
        // Create a toast notification
        const toastContainer = document.getElementById('toast-container') || this.createToastContainer();
        
        const toast = document.createElement('div');
        toast.className = `toast align-items-center text-white bg-${type} border-0`;
        toast.setAttribute('role', 'alert');
        toast.innerHTML = `
            <div class="d-flex">
                <div class="toast-body">${message}</div>
                <button type="button" class="btn-close btn-close-white me-2 m-auto" data-bs-dismiss="toast"></button>
            </div>
        `;
        
        toastContainer.appendChild(toast);
        
        const bsToast = new bootstrap.Toast(toast);
        bsToast.show();
        
        // Remove toast after it's hidden
        toast.addEventListener('hidden.bs.toast', () => {
            toast.remove();
        });
    }

    createToastContainer() {
        const container = document.createElement('div');
        container.id = 'toast-container';
        container.className = 'toast-container position-fixed top-0 end-0 p-3';
        container.style.zIndex = '1100';
        document.body.appendChild(container);
        return container;
    }
}

function initializeSchedulePage() {
    // Check if we are on the schedule page by looking for a unique element
    if (document.querySelector('.schedule-manager')) {
        console.log('Schedule page detected, creating ScheduleManager');
        // Instantiate the manager and attach it to the window
        // This ensures it only runs when the schedule page is loaded
        window.scheduleManager = new ScheduleManager();
    } else {
        // This case should not be hit if navigation.js is working correctly,
        // but it's good practice for defensive coding.
        console.log('Not on schedule page, skipping ScheduleManager initialization');
    }
}

window.initializeSchedulePage = initializeSchedulePage; 