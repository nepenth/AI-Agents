/* V2 SCHEDULE.JS - Logic for Schedule administration */

class ScheduleManager {
    constructor(api) {
        this.api = api || (window.API ? new window.API() : new window.APIClient());
        this.tableBody = null;
        this.modal = null;
        this.form = null;
        this.addBtn = null;
        this.editingId = null;
        console.log('📅 ScheduleManager constructed');
    }

    async initialize() {
        console.log('📅 ScheduleManager.initialize()');
        const mainContent = document.getElementById('main-content');
        if (mainContent && !mainContent.querySelector('.schedule-page')) {
            const html = await (await fetch('/v2/page/schedule')).text();
            mainContent.innerHTML = html;
        }

        // capture elements
        this.tableBody = document.querySelector('#v2-schedule-table tbody');
        this.modal = document.getElementById('v2-schedule-modal');
        this.form = document.getElementById('v2-schedule-form');
        this.addBtn = document.getElementById('v2-add-schedule-btn');
        this.cancelBtn = document.getElementById('schedule-cancel-btn');

        if (!this.tableBody || !this.modal || !this.form || !this.addBtn) {
            console.error('Schedule page elements missing');
            return;
        }

        this.attachListeners();
        await this.refreshTable();
    }

    attachListeners() {
        // open modal for new schedule
        this.addBtn.addEventListener('click', () => {
            this.openModal();
        });

        // cancel
        this.cancelBtn.addEventListener('click', () => this.closeModal());

        // submit form
        this.form.addEventListener('submit', async (e) => {
            e.preventDefault();
            const formData = new FormData(this.form);
            const payload = Object.fromEntries(formData.entries());
            payload.enabled = !!payload.enabled;
            try {
                if (this.editingId) {
                    await this.api.request(`/schedules/${this.editingId}`, { method: 'PUT', body: payload });
                } else {
                    await this.api.request('/schedules', { method: 'POST', body: payload });
                }
                await this.refreshTable();
                this.closeModal();
            } catch (err) {
                console.error(err);
                alert(err.message);
            }
        });
    }

    async refreshTable() {
        this.tableBody.innerHTML = '<tr class="loading-state"><td colspan="5"><div class="loading-container"><div class="loading-spinner"></div><span>Loading schedules...</span></div></td></tr>';
        try {
            const schedules = await this.api.request('/schedules');
            
            // Update statistics
            this.updateStatistics(schedules);
            
            if (!Array.isArray(schedules) || schedules.length === 0) {
                this.tableBody.innerHTML = '<tr><td colspan="5" class="text-muted text-center">No schedules configured.</td></tr>';
                return;
            }
            
            let rows = '';
            // store for easy lookup
            this.scheduleMap = {};
            schedules.forEach(s => {
                this.scheduleMap[s.id] = s;
                const nextRun = s.next_run ? new Date(s.next_run).toLocaleString() : 'Not scheduled';
                const statusBadge = s.enabled ? 
                    '<span class="status-badge status-badge--success"><i class="fas fa-check-circle"></i> Enabled</span>' : 
                    '<span class="status-badge status-badge--secondary"><i class="fas fa-pause-circle"></i> Disabled</span>';
                
                rows += `
                    <tr data-schedule-id="${s.id}">
                        <td>
                            <div class="schedule-name">
                                <strong>${s.name}</strong>
                                ${s.description ? `<br><small class="text-muted">${s.description}</small>` : ''}
                            </div>
                        </td>
                        <td><span class="frequency-badge">${this.formatFrequency(s.frequency)}</span></td>
                        <td>${nextRun}</td>
                        <td>${statusBadge}</td>
                        <td>
                            <div class="action-buttons">
                                <button class="glass-button glass-button--small glass-button--ghost" onclick="scheduleManager.runNow(event)">
                                    <i class="fas fa-play"></i>
                                </button>
                                <button class="glass-button glass-button--small glass-button--ghost" onclick="scheduleManager.openEdit(event)">
                                    <i class="fas fa-edit"></i>
                                </button>
                                <button class="glass-button glass-button--small glass-button--ghost" onclick="scheduleManager.toggleEnabled(event)">
                                    <i class="fas ${s.enabled ? 'fa-pause' : 'fa-play'}"></i>
                                </button>
                                <button class="glass-button glass-button--small glass-button--danger" onclick="scheduleManager.deleteSchedule(event)">
                                    <i class="fas fa-trash"></i>
                                </button>
                            </div>
                        </td>
                    </tr>
                `;
            });
            this.tableBody.innerHTML = rows;
        } catch (err) {
            console.error(err);
            this.tableBody.innerHTML = `<tr><td colspan="5" class="text-danger">Error: ${err.message}</td></tr>`;
        }
    }

    updateStatistics(schedules) {
        const totalEl = document.getElementById('total-schedules');
        const activeEl = document.getElementById('active-schedules');
        const nextRunEl = document.getElementById('next-run');
        
        if (totalEl) {
            totalEl.textContent = schedules.length;
        }
        
        if (activeEl) {
            const activeCount = schedules.filter(s => s.enabled).length;
            activeEl.textContent = activeCount;
        }
        
        if (nextRunEl) {
            const nextRuns = schedules
                .filter(s => s.enabled && s.next_run)
                .map(s => new Date(s.next_run))
                .sort((a, b) => a - b);
            
            if (nextRuns.length > 0) {
                nextRunEl.textContent = nextRuns[0].toLocaleString();
            } else {
                nextRunEl.textContent = '--';
            }
        }
    }

    formatFrequency(frequency) {
        const frequencies = {
            'hourly': 'Every Hour',
            'daily': 'Daily',
            'weekly': 'Weekly',
            'monthly': 'Monthly',
            'cron': 'Custom'
        };
        return frequencies[frequency] || frequency;
    }

    getRowScheduleId(eventTarget) {
        return eventTarget.closest('tr').dataset.id;
    }

    async openEdit(event) {
        const id = this.getRowScheduleId(event.target);
        const schedule = this.scheduleMap ? this.scheduleMap[id] : null;
        if (schedule) {
            this.openModal(schedule);
        } else {
            alert('Schedule data not found. Try refreshing.');
        }
    }

    async deleteSchedule(event) {
        const id = this.getRowScheduleId(event.target);
        if (!confirm('Delete schedule?')) return;
        try {
            await this.api.request(`/schedules/${id}`, { method: 'DELETE' });
            await this.refreshTable();
        } catch (err) {
            console.error(err);
            alert(err.message);
        }
    }

    async runNow(event) {
        const id = this.getRowScheduleId(event.target);
        try {
            await this.api.request(`/schedules/${id}/run`, { method: 'POST' });
            alert('Schedule queued!');
        } catch (err) {
            console.error(err);
            alert(err.message);
        }
    }

    async toggleEnabled(event) {
        const id = this.getRowScheduleId(event.target);
        try {
            await this.api.request(`/schedules/${id}/toggle`, { method: 'POST' });
        } catch (err) {
            console.error(err);
            alert(err.message);
            // revert checkbox
            event.target.checked = !event.target.checked;
        }
    }

    openModal(schedule = null) {
        this.editingId = schedule ? schedule.id : null;
        // reset form
        this.form.reset();
        this.modal.style.display = 'flex';
        document.getElementById('schedule-modal-title').textContent = schedule ? 'Edit Schedule' : 'New Schedule';
        if (schedule) {
            // populate form fields
            this.form.name.value = schedule.name;
            this.form.description.value = schedule.description;
            this.form.frequency.value = schedule.frequency;
            this.form.enabled.checked = schedule.enabled;
        }
    }

    closeModal() {
        this.modal.style.display = 'none';
        this.editingId = null;
    }

    cleanup() {
        // remove event listeners if needed
        console.log('🧹 Cleaning ScheduleManager');
    }
}

window.ScheduleManager = ScheduleManager; 