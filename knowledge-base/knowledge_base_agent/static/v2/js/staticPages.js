/* V2 STATICPAGES.JS - LOGIC FOR SIMPLE CONTENT PAGES */

class StaticPagesManager {
    constructor(pageType, api) {
        this.pageType = pageType;
        this.api = api; // API client for REST operations
        this.container = document.getElementById('main-content');
        console.log(`📄 StaticPagesManager constructor called for page type: ${pageType}`);
    }

    async initialize() {
        console.log(`📄 StaticPagesManager.initialize() called for ${this.pageType}`);
        
        try {
            console.log(`📄 Loading ${this.pageType} page content...`);
            
            // Load the appropriate page content
            const mainContent = document.getElementById('main-content');
            if (mainContent) {
                const response = await fetch(`/v2/page/${this.pageType}`);
                if (response.ok) {
                    const html = await response.text();
                    mainContent.innerHTML = html;
                    console.log(`📄 ${this.pageType} content loaded`);
                    
                    // Re-initialize container reference after content load
                    this.container = document.getElementById('main-content');
                }
            }
            
            await this.init();
            console.log(`✅ StaticPagesManager initialized successfully for ${this.pageType}`);
        } catch (error) {
            console.error(`❌ StaticPagesManager initialization failed for ${this.pageType}:`, error);
        }
    }

    async init() {
        if (this.pageType === 'logs') {
            await this.initLogsPage();
        } else if (this.pageType === 'environment') {
            await this.initEnvironmentPage();
        } else if (this.pageType === 'schedule') {
            await this.initSchedulePage();
        }
    }

    async initLogsPage() {
        const selector = document.getElementById('v2-log-file-selector');
        const contentArea = document.getElementById('v2-log-content');
        
        try {
            const response = await fetch('/api/logs/files');
            const files = await response.json();
            files.forEach(file => {
                const option = document.createElement('option');
                option.value = file;
                option.textContent = file;
                selector.appendChild(option);
            });

            selector.addEventListener('change', async (e) => {
                const filename = e.target.value;
                if (!filename) return;
                const logResponse = await fetch(`/api/logs/files/${filename}`);
                const logContent = await logResponse.text();
                contentArea.textContent = logContent;
                if (window.Prism) Prism.highlightAllUnder(contentArea.parentElement);
            });
        } catch (error) {
            console.error('Failed to load log files:', error);
        }
    }

    async initEnvironmentPage() {
        try {
            const response = await fetch('/api/environment');
            if (!response.ok) throw new Error('Failed to fetch environment settings.');
            const settings = await response.json();
            
            const contentEl = this.container.querySelector('#environment-content');
            if (contentEl) {
                let html = '<ul>';
                for (const [key, value] of Object.entries(settings)) {
                    html += `<li><strong>${key}:</strong> <span>${value}</span></li>`;
                }
                html += '</ul>';
                contentEl.innerHTML = html;
            }
        } catch (error) {
            console.error('Failed to load environment settings:', error);
            const contentEl = this.container.querySelector('#environment-content');
            if (contentEl) contentEl.innerHTML = `<p class="error">${error.message}</p>`;
        }
    }

    async initSchedulePage() {
        const scheduleInput = document.getElementById('schedule-input');
        const saveButton = document.getElementById('save-schedule');
        const statusDiv = document.getElementById('schedule-status');

        if (!scheduleInput || !saveButton || !statusDiv) {
            console.error('Schedule page elements not found');
            return;
        }

        try {
            const response = await fetch('/api/v2/schedule');
            if (response.ok) {
                const data = await response.json();
                scheduleInput.value = data.schedule || '';
            } else {
                statusDiv.textContent = 'Error loading schedule.';
                statusDiv.className = 'status-error';
            }
        } catch (error) {
            console.error('Error fetching schedule:', error);
            statusDiv.textContent = 'Error loading schedule.';
            statusDiv.className = 'status-error';
        }

        saveButton.addEventListener('click', async () => {
            const newSchedule = scheduleInput.value;
            statusDiv.textContent = 'Saving...';
            statusDiv.className = 'status-saving';

            try {
                const response = await fetch('/api/v2/schedule', {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json',
                    },
                    body: JSON.stringify({ schedule: newSchedule }),
                });

                const data = await response.json();

                if (!response.ok) {
                    throw new Error(data.error || 'Failed to save schedule.');
                }

                if (statusDiv) {
                    statusDiv.textContent = 'Schedule updated successfully!';
                    statusDiv.className = 'status-success';
                }
            } catch (error) {
                if (statusDiv) {
                    statusDiv.textContent = `Error: ${error.message}`;
                    statusDiv.className = 'status-error';
                }
            }
        });
    }

    cleanup() {
        console.log(`🧹 Cleaning up StaticPagesManager for ${this.pageType}...`);
        // Clean up any event listeners or resources specific to each page type
        if (this.pageType === 'schedule') {
            const saveButton = document.getElementById('save-schedule');
            if (saveButton) {
                // Remove event listeners if needed
                saveButton.removeEventListener('click', this.saveScheduleHandler);
            }
        }
        // Add cleanup for other page types as needed
    }
}

// Make globally available for non-module usage
window.StaticPagesManager = StaticPagesManager; 