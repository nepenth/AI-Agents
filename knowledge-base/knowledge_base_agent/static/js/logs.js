/**
 * logs.js - Handles the functionality for the log viewer page.
 * This module is implemented as a self-contained class to ensure proper encapsulation and
 * avoid conflicts in a Single Page Application (SPA) context.
 */

class LogViewer {
    /**
     * Initializes the LogViewer, finding DOM elements and binding events.
     */
    constructor() {
        // Find all necessary DOM elements once.
        this.logSelect = document.getElementById('log-file-select');
        this.logContentArea = document.getElementById('log-content-area');
        this.refreshLogListBtn = document.getElementById('refreshLogListBtn');
        this.deleteAllLogsBtn = document.getElementById('deleteAllLogsBtn');
        this.logContentHeader = document.getElementById('log-content-header');

        // If the primary element doesn't exist, we're not on the logs page.
        if (!this.logSelect) {
            return;
        }

        console.log("LogViewer class instantiated and initialized.");
        
        // Bind all event listeners cleanly.
        this.bindEvents();

        // Fetch the initial list of logs.
        this.fetchLogList();
    }

    /**
     * Attaches event listeners to the DOM elements.
     */
    bindEvents() {
        this.refreshLogListBtn.addEventListener('click', () => this.fetchLogList());
        this.deleteAllLogsBtn.addEventListener('click', () => this.deleteAllLogs());
        this.logSelect.addEventListener('change', () => this.handleSelectionChange());
    }

    /**
     * Handles the change event for the log file selector.
     */
    handleSelectionChange() {
        const selectedFile = this.logSelect.value;
        console.log('Log selection changed to:', selectedFile);
        if (selectedFile) {
            this.fetchLogContent(selectedFile);
        } else {
            this.logContentArea.textContent = 'Please select a log file.';
            this.logContentHeader.textContent = 'Log Content';
        }
    }

    /**
     * Fetches the list of available log files from the API and populates the dropdown.
     */
    async fetchLogList() {
        console.log("Fetching log list...");
        this.logSelect.innerHTML = '<option value="">Loading log files...</option>';
        this.logSelect.disabled = true;
        
        try {
            const response = await fetch('/api/logs');
            if (!response.ok) {
                const errorData = await response.json().catch(() => ({ error: `HTTP error! status: ${response.status}` }));
                throw new Error(errorData.error);
            }
            
            const logFiles = await response.json();
            
            // Clear existing options
            this.logSelect.innerHTML = '<option value="">Select a log file...</option>';
            
            if (Array.isArray(logFiles) && logFiles.length > 0) {
                logFiles.forEach(filename => {
                    const option = document.createElement('option');
                    option.value = filename;
                    option.textContent = filename;
                    this.logSelect.appendChild(option);
                });
                this.deleteAllLogsBtn.disabled = false;
                this.logContentArea.textContent = `Found ${logFiles.length} log file(s). Select one to view.`;
                console.log(`Successfully populated dropdown with ${logFiles.length} files.`);
            } else {
                this.logSelect.innerHTML = '<option value="">No log files found</option>';
                this.deleteAllLogsBtn.disabled = true;
                this.logContentArea.textContent = 'No log files available.';
                console.log('No log files found.');
            }
        } catch (error) {
            console.error("Error fetching log list:", error.message);
            this.logSelect.innerHTML = '<option value="">Error loading list</option>';
            this.logContentArea.textContent = `Error: ${error.message}`;
            this.deleteAllLogsBtn.disabled = true;
        } finally {
            this.logSelect.disabled = false;
        }
    }

    /**
     * Fetches and displays the content of a specific log file.
     * @param {string} filename - The name of the log file to fetch.
     */
    async fetchLogContent(filename) {
        if (!filename) return;

        this.logContentArea.textContent = `Loading content for ${filename}...`;
        this.logContentHeader.textContent = `Log Content: ${filename}`;
        
        try {
            const response = await fetch(`/api/logs/${encodeURIComponent(filename)}`);
            const textContent = await response.text();

            if (!response.ok) {
                // Try to parse error from JSON, otherwise use the text content.
                try {
                    const jsonError = JSON.parse(textContent);
                    throw new Error(jsonError.error || 'Unknown API error');
                } catch(e) {
                    throw new Error(textContent || `HTTP error! status: ${response.status}`);
                }
            }
            
            this.logContentArea.textContent = textContent;
        } catch (error) {
            console.error(`Error fetching log content for ${filename}:`, error);
            this.logContentArea.textContent = `Error loading ${filename}: ${error.message}`;
        }
    }
    
    /**
     * Handles the request to delete all log files after confirmation.
     */
    async deleteAllLogs() {
        if (!confirm('Are you sure you want to delete ALL log files? This cannot be undone.')) {
            return;
        }
        
        this.deleteAllLogsBtn.disabled = true;
        this.logContentArea.textContent = 'Deleting all log files...';
        
        try {
            const response = await fetch('/api/logs/delete-all', { method: 'POST' });
            const result = await response.json();
            
            if (!response.ok) {
                throw new Error(result.error || 'Failed to delete log files');
            }
            
            this.logContentArea.textContent = result.message || 'All logs deleted.';
            console.log(result.message);

        } catch (error) {
            console.error('Error deleting logs:', error);
            this.logContentArea.textContent = `Error: ${error.message}`;
        } finally {
            // Always refresh the list after attempting deletion.
            await this.fetchLogList();
        }
    }
}

/**
 * The single initialization function called by the SPA navigation conductor.
 * It creates a new instance of the LogViewer, ensuring a clean state on each page load.
 */
function initializeLogsPage() {
    console.log('Request to initialize logs page received.');
    // By creating a new instance, we ensure old event listeners are discarded
    // along with the old DOM elements, preventing memory leaks and conflicts.
    window.currentLogViewer = new LogViewer();
}

// Expose the initializer for the conductor to call.
window.initializeLogsPageNow = initializeLogsPage; 