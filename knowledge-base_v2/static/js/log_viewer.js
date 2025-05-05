"use strict";

document.addEventListener('DOMContentLoaded', () => {
    const logFileSelect = document.getElementById('logFileSelect');
    const logContent = document.getElementById('log-content');
    const logOutputDiv = logContent.closest('.log-output'); // Get the container

    const fetchLogList = async () => {
        try {
            // Update URL to include blueprint prefix
            const response = await fetch('/logs/api/list');
            if (!response.ok) {
                throw new Error(`HTTP error! status: ${response.status}`);
            }
            const logFiles = await response.json();

            logFileSelect.innerHTML = '<option selected value="">-- Select a Log File --</option>'; // Clear loading message

            if (logFiles && logFiles.length > 0) {
                logFiles.forEach(file => {
                    const option = document.createElement('option');
                    option.value = file;
                    option.textContent = file;
                    logFileSelect.appendChild(option);
                });
            } else {
                 logFileSelect.innerHTML = '<option selected value="">No log files found</option>';
                 logContent.textContent = 'No log files available.';
            }
        } catch (error) {
            console.error('Error fetching log list:', error);
            logFileSelect.innerHTML = '<option selected value="">Error loading logs</option>';
            logContent.textContent = `Error loading log list: ${error.message}`;
        }
    };

    const fetchLogContent = async (filename) => {
        if (!filename) {
            logContent.textContent = 'Select a log file to view its contents.';
            return;
        }
        logContent.textContent = 'Loading log content...';
         try {
             // Update URL to include blueprint prefix
             const response = await fetch(`/logs/api/view/${encodeURIComponent(filename)}`);
             if (!response.ok) {
                 throw new Error(`HTTP error! status: ${response.status}`);
             }
             const content = await response.text();
             logContent.textContent = content;
             // Scroll to top after loading new content
             if(logOutputDiv) {
                 logOutputDiv.scrollTop = 0;
             }

         } catch (error) {
             console.error(`Error fetching log content for ${filename}:`, error);
             logContent.textContent = `Error loading log content: ${error.message}`;
         }
    };

    // Event Listener for select change
    logFileSelect.addEventListener('change', (event) => {
        fetchLogContent(event.target.value);
    });

    // Initial load
    fetchLogList();
});
