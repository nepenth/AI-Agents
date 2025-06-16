/**
 * logs.js - Handles logs page functionality
 */

// Make function globally accessible
window.initializeLogsPage = function initializeLogsPage() {
    console.log('Initializing logs page functionality');

    const logSelect = document.getElementById('log-file-select');
    const logContentArea = document.getElementById('log-content-area');
    const loadLogButton = document.getElementById('load-log-button');
    const refreshLogListBtn = document.getElementById('refreshLogListBtn');
    const deleteAllLogsBtn = document.getElementById('deleteAllLogsBtn');
    const logContentHeader = document.getElementById('log-content-header');

    // Only proceed if elements exist (we're on the logs page)
    if (!logSelect || !logContentArea || !loadLogButton) {
        console.log('Logs page elements not found:', { 
            logSelect: !!logSelect, 
            logContentArea: !!logContentArea, 
            loadLogButton: !!loadLogButton 
        });
        return;
    }

    console.log('Found all required logs page elements');

    async function fetchLogList() {
        console.log("Starting fetchLogList...");
        logSelect.innerHTML = '<option value="">Loading log files...</option>';
        logSelect.disabled = true;
        loadLogButton.disabled = true;
        
        try {
            console.log("Fetching log files from /api/logs...");
            const response = await fetch('/api/logs');
            console.log("Response status:", response.status);
            
            if (!response.ok) {
                const errorData = await response.json();
                const errorMessage = errorData.error || `HTTP error! status: ${response.status}`;
                throw new Error(errorMessage);
            }
            
            const logFiles = await response.json();
            console.log("Received log files:", logFiles);

            logSelect.innerHTML = '<option value="">Select a log file...</option>';
            if (logFiles && logFiles.length > 0) {
                logFiles.forEach(filename => {
                    const option = document.createElement('option');
                    option.value = filename;
                    option.textContent = filename;
                    logSelect.appendChild(option);
                });
                if (deleteAllLogsBtn) deleteAllLogsBtn.disabled = false;
                logContentArea.textContent = `Found ${logFiles.length} log file(s). Select one to view its content.`;
                console.log(`Successfully loaded ${logFiles.length} log files into dropdown`);
            } else {
                logSelect.innerHTML = '<option value="">No log files found</option>';
                if (deleteAllLogsBtn) deleteAllLogsBtn.disabled = true;
                logContentArea.textContent = 'No log files found. The agent hasn\'t created any logs yet.';
            }
        } catch (error) {
            console.error("Error fetching log list:", error);
            logSelect.innerHTML = '<option value="">Error loading list</option>';
            logContentArea.textContent = `Error loading log list: ${error.message}`;
            if (deleteAllLogsBtn) deleteAllLogsBtn.disabled = true;
        } finally {
            logSelect.disabled = false;
            loadLogButton.disabled = false;
        }
    }

    async function fetchLogContent(filename) {
        if (!filename) {
            logContentArea.textContent = 'Please select a log file.';
            if (logContentHeader) logContentHeader.textContent = 'Log Content';
            return;
        }
        logContentArea.textContent = `Loading ${filename}...`;
        if (logContentHeader) logContentHeader.textContent = `Log Content: ${filename}`;
        loadLogButton.disabled = true;
        
        try {
            const response = await fetch(`/api/logs/${encodeURIComponent(filename)}`);
            if (!response.ok) {
                const errorData = await response.text();
                try {
                    const jsonError = JSON.parse(errorData);
                    throw new Error(jsonError.error || `HTTP error! status: ${response.status}`);
                } catch (e) {
                    throw new Error(`HTTP error! status: ${response.status}`);
                }
            }
            const textContent = await response.text();
            logContentArea.textContent = textContent;
        } catch (error) {
            console.error(`Error fetching log content for ${filename}:`, error);
            logContentArea.textContent = `Error loading ${filename}: ${error.message}`;
        } finally {
             loadLogButton.disabled = false;
        }
    }
    
    async function deleteAllLogs() {
        if (!confirm('Are you sure you want to delete ALL log files? This cannot be undone.')) {
            return;
        }
        
        if (deleteAllLogsBtn) deleteAllLogsBtn.disabled = true;
        logContentArea.textContent = 'Deleting all log files...';
        
        try {
            const response = await fetch('/api/logs/delete-all', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                }
            });
            
            const result = await response.json();
            
            if (response.ok) {
                logContentArea.textContent = `${result.message || 'All log files have been deleted.'}\n\n${result.deleted_count || 0} files were deleted.`;
                logSelect.innerHTML = '<option value="">No log files available</option>';
                if (logContentHeader) logContentHeader.textContent = 'Log Content';
            } else {
                throw new Error(result.error || 'Failed to delete log files');
            }
        } catch (error) {
            console.error('Error deleting logs:', error);
            logContentArea.textContent = `Error deleting logs: ${error.message}`;
        } finally {
            await fetchLogList();
        }
    }

    // Clean event handling - remove existing listeners and add new ones
    if (loadLogButton) {
        loadLogButton.replaceWith(loadLogButton.cloneNode(true));
        const newLoadLogButton = document.getElementById('load-log-button');
        newLoadLogButton.addEventListener('click', () => {
            const selectedFile = logSelect.value;
            console.log('Load log button clicked, selected file:', selectedFile);
            fetchLogContent(selectedFile);
        });
    }

    if (refreshLogListBtn) {
        refreshLogListBtn.replaceWith(refreshLogListBtn.cloneNode(true));
        const newRefreshBtn = document.getElementById('refreshLogListBtn');
        newRefreshBtn.addEventListener('click', () => {
            console.log('Refresh button clicked');
            fetchLogList();
        });
    }

    if (deleteAllLogsBtn) {
        deleteAllLogsBtn.replaceWith(deleteAllLogsBtn.cloneNode(true));
        const newDeleteBtn = document.getElementById('deleteAllLogsBtn');
        newDeleteBtn.addEventListener('click', () => {
            console.log('Delete all logs button clicked');
            deleteAllLogs();
        });
    }

    if (logSelect) {
        logSelect.replaceWith(logSelect.cloneNode(true));
        const newLogSelect = document.getElementById('log-file-select');
        newLogSelect.addEventListener('change', () => {
            const selectedFile = newLogSelect.value;
            console.log('Log select changed, selected file:', selectedFile);
            if (selectedFile) {
                fetchLogContent(selectedFile);
            }
        });
    }

    // Initial load
    console.log('Calling initial fetchLogList...');
    fetchLogList();
}

// Auto-initialize when DOM is ready and logs page elements are present
document.addEventListener('DOMContentLoaded', function() {
    setTimeout(() => {
        if (document.getElementById('log-file-select')) {
            console.log('DOMContentLoaded: Initializing logs page');
            initializeLogsPage();
        }
    }, 100);
});

// Also export for manual calling
window.initializeLogsPageNow = function() {
    console.log('Manual logs page initialization called');
    initializeLogsPage();
}; 