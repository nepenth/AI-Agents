/**
 * environment.js
 * Handles environment variable management functionality
 */

class EnvironmentManager {
    constructor() {
        this.envData = null;
        this.filteredVars = [];
        this.pendingChanges = {};
        this.init();
    }

    init() {
        console.log('EnvironmentManager init called');
        this.bindEvents();
        this.loadEnvironmentVariables();
        console.log('EnvironmentManager initialization complete');
    }

    bindEvents() {
        // Save changes button
        const saveBtn = document.getElementById('save-env-btn');
        if (saveBtn) {
            saveBtn.addEventListener('click', () => this.saveChanges());
        }

        // Add variable button
        const addBtn = document.getElementById('add-env-var-btn');
        if (addBtn) {
            addBtn.addEventListener('click', () => this.addEnvironmentVariable());
        }

        // Update variable button
        const updateBtn = document.getElementById('update-env-var-btn');
        if (updateBtn) {
            updateBtn.addEventListener('click', () => this.updateEnvironmentVariable());
        }

        // Search and filter
        const searchInput = document.getElementById('search-env-vars');
        if (searchInput) {
            searchInput.addEventListener('input', () => this.filterVariables());
        }

        const filterSelect = document.getElementById('filter-env-vars');
        if (filterSelect) {
            filterSelect.addEventListener('change', () => this.filterVariables());
        }

        // Password toggle
        const togglePassword = document.getElementById('toggle-password');
        if (togglePassword) {
            togglePassword.addEventListener('click', () => this.togglePasswordVisibility());
        }
    }

    async loadEnvironmentVariables() {
        try {
            console.log('Loading environment variables...');
            const response = await fetch('/api/environment-variables');
            if (!response.ok) {
                throw new Error(`HTTP error! status: ${response.status}`);
            }
            
            this.envData = await response.json();
            console.log('Environment data loaded:', this.envData);
            
            this.updateStatusCards();
            this.renderVariablesTable();
            this.showValidationResults();
        } catch (error) {
            console.error('Error loading environment variables:', error);
            this.showErrorMessage('Failed to load environment variables: ' + error.message);
        }
    }

    updateStatusCards() {
        if (!this.envData) return;

        document.getElementById('used-count').textContent = this.envData.used_env_vars.length;
        document.getElementById('unused-count').textContent = this.envData.unused_env_vars.length;
        document.getElementById('missing-count').textContent = this.envData.missing_env_vars.length;
        document.getElementById('total-count').textContent = Object.keys(this.envData.env_variables).length;
    }

    renderVariablesTable() {
        if (!this.envData) return;

        const tbody = document.getElementById('env-vars-tbody');
        tbody.innerHTML = '';

        // Combine all variables for display
        const allVars = {};
        
        // Add existing env variables
        Object.entries(this.envData.env_variables).forEach(([key, value]) => {
            allVars[key] = {
                value: value,
                exists: true,
                used: this.envData.used_env_vars.includes(key),
                configInfo: this.getConfigInfoForVar(key)
            };
        });

        // Add missing required variables
        this.envData.missing_env_vars.forEach(varName => {
            allVars[varName] = {
                value: '',
                exists: false,
                used: true,
                configInfo: this.getConfigInfoForVar(varName)
            };
        });

        this.filteredVars = Object.entries(allVars);
        this.filterVariables();
    }

    getConfigInfoForVar(varName) {
        if (!this.envData.config_fields) return null;
        
        for (const [fieldName, fieldInfo] of Object.entries(this.envData.config_fields)) {
            if (fieldInfo.alias === varName) {
                return fieldInfo;
            }
        }
        return null;
    }

    filterVariables() {
        const searchTerm = document.getElementById('search-env-vars').value.toLowerCase();
        const filterType = document.getElementById('filter-env-vars').value;

        let filtered = this.filteredVars.filter(([varName, varInfo]) => {
            const matchesSearch = varName.toLowerCase().includes(searchTerm) || 
                                (varInfo.configInfo?.description || '').toLowerCase().includes(searchTerm);
            
            let matchesFilter = true;
            switch (filterType) {
                case 'used':
                    matchesFilter = varInfo.used;
                    break;
                case 'unused':
                    matchesFilter = !varInfo.used && varInfo.exists;
                    break;
                case 'missing':
                    matchesFilter = !varInfo.exists;
                    break;
                case 'required':
                    matchesFilter = varInfo.configInfo?.required || false;
                    break;
                case 'optional':
                    matchesFilter = !(varInfo.configInfo?.required || false);
                    break;
                default:
                    matchesFilter = true;
            }

            return matchesSearch && matchesFilter;
        });

        this.displayFilteredVariables(filtered);
    }

    displayFilteredVariables(filtered) {
        const tbody = document.getElementById('env-vars-tbody');
        tbody.innerHTML = '';

        filtered.forEach(([varName, varInfo]) => {
            const row = this.createVariableRow(varName, varInfo);
            tbody.appendChild(row);
        });
    }

    createVariableRow(varName, varInfo) {
        const row = document.createElement('tr');
        
        // Determine status and styling
        let statusBadge, statusClass;
        if (!varInfo.exists) {
            statusBadge = '<span class="badge bg-danger">Missing</span>';
            statusClass = 'table-danger';
        } else if (!varInfo.used) {
            statusBadge = '<span class="badge bg-warning">Unused</span>';
            statusClass = 'table-warning';
        } else if (varInfo.configInfo?.required) {
            statusBadge = '<span class="badge bg-success">Required</span>';
            statusClass = '';
        } else {
            statusBadge = '<span class="badge bg-info">Optional</span>';
            statusClass = '';
        }

        // Mask sensitive values
        const isSensitive = this.isSensitiveVar(varName);
        const displayValue = isSensitive && varInfo.value ? 
            '••••••••' : (varInfo.value || '<em>Not set</em>');

        row.className = statusClass;
        const deleteButton = !varInfo.configInfo?.required ? 
            `<button class="btn btn-sm btn-danger" onclick="environmentManager.deleteVariable('${varName}')">
                <i class="bi bi-trash"></i>
            </button>` : '';
            
        row.innerHTML = `
            <td><strong>${varName}</strong></td>
            <td class="env-value" data-var-name="${varName}">${displayValue}</td>
            <td class="text-muted">${varInfo.configInfo?.description || 'No description available'}</td>
            <td>${statusBadge}</td>
            <td><code>${varInfo.configInfo?.type || 'string'}</code></td>
            <td>
                <button class="btn btn-sm btn-primary me-1" onclick="environmentManager.editVariable('${varName}')">
                    <i class="bi bi-pencil"></i>
                </button>
                ${deleteButton}
            </td>
        `;

        return row;
    }

    isSensitiveVar(varName) {
        const sensitivePatterns = ['PASSWORD', 'TOKEN', 'SECRET', 'KEY', 'PRIVATE'];
        return sensitivePatterns.some(pattern => varName.toUpperCase().includes(pattern));
    }

    editVariable(varName) {
        const varInfo = this.getVariableInfo(varName);
        if (!varInfo) return;

        document.getElementById('edit-env-name').value = varName;
        document.getElementById('edit-env-value').value = varInfo.value || '';
        document.getElementById('edit-env-description').value = varInfo.configInfo?.description || '';

        const modal = new bootstrap.Modal(document.getElementById('editEnvVarModal'));
        modal.show();
    }

    getVariableInfo(varName) {
        if (this.envData.env_variables[varName] !== undefined) {
            return {
                value: this.envData.env_variables[varName],
                exists: true,
                configInfo: this.getConfigInfoForVar(varName)
            };
        }
        
        if (this.envData.missing_env_vars.includes(varName)) {
            return {
                value: '',
                exists: false,
                configInfo: this.getConfigInfoForVar(varName)
            };
        }
        
        return null;
    }

    async updateEnvironmentVariable() {
        const varName = document.getElementById('edit-env-name').value;
        const varValue = document.getElementById('edit-env-value').value;

        if (!varName || varValue === '') {
            this.showErrorMessage('Variable name and value are required');
            return;
        }

        // Store pending change
        this.pendingChanges[varName] = varValue;
        
        // Update the display
        this.envData.env_variables[varName] = varValue;
        this.renderVariablesTable();

        // Close modal
        const modal = bootstrap.Modal.getInstance(document.getElementById('editEnvVarModal'));
        modal.hide();

        this.showSuccessMessage(`Variable ${varName} updated (pending save)`);
    }

    async addEnvironmentVariable() {
        const varName = document.getElementById('new-env-name').value.trim().toUpperCase();
        const varValue = document.getElementById('new-env-value').value;

        if (!varName || !varValue) {
            this.showErrorMessage('Variable name and value are required');
            return;
        }

        if (this.envData.env_variables[varName] !== undefined) {
            this.showErrorMessage('Variable already exists');
            return;
        }

        // Store pending change
        this.pendingChanges[varName] = varValue;
        
        // Update the display
        this.envData.env_variables[varName] = varValue;
        this.renderVariablesTable();

        // Clear form and close modal
        document.getElementById('add-env-var-form').reset();
        const modal = bootstrap.Modal.getInstance(document.getElementById('addEnvVarModal'));
        modal.hide();

        this.showSuccessMessage(`Variable ${varName} added (pending save)`);
    }

    async deleteVariable(varName) {
        if (!confirm(`Are you sure you want to delete the environment variable "${varName}"?`)) {
            return;
        }

        try {
            const response = await fetch(`/api/environment-variables/${varName}`, {
                method: 'DELETE'
            });

            if (!response.ok) {
                throw new Error(`HTTP error! status: ${response.status}`);
            }

            const result = await response.json();
            if (result.success) {
                this.showSuccessMessage(result.message);
                this.loadEnvironmentVariables(); // Reload data
            } else {
                this.showErrorMessage(result.error || 'Failed to delete variable');
            }
        } catch (error) {
            console.error('Error deleting variable:', error);
            this.showErrorMessage('Failed to delete variable: ' + error.message);
        }
    }

    async saveChanges() {
        if (Object.keys(this.pendingChanges).length === 0) {
            this.showInfoMessage('No changes to save');
            return;
        }

        try {
            const response = await fetch('/api/environment-variables', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify({
                    env_variables: this.pendingChanges
                })
            });

            if (!response.ok) {
                throw new Error(`HTTP error! status: ${response.status}`);
            }

            const result = await response.json();
            if (result.success) {
                this.showSuccessMessage('Environment variables saved successfully');
                this.pendingChanges = {};
                this.loadEnvironmentVariables(); // Reload to get fresh data
            } else {
                this.showErrorMessage(result.error || 'Failed to save changes');
            }
        } catch (error) {
            console.error('Error saving changes:', error);
            this.showErrorMessage('Failed to save changes: ' + error.message);
        }
    }

    togglePasswordVisibility() {
        const input = document.getElementById('edit-env-value');
        const icon = document.querySelector('#toggle-password i');
        
        if (input.type === 'password') {
            input.type = 'text';
            icon.className = 'bi bi-eye-slash';
        } else {
            input.type = 'password';
            icon.className = 'bi bi-eye';
        }
    }

    showValidationResults() {
        if (!this.envData) return;

        const validationCard = document.getElementById('validation-card');
        const validationResults = document.getElementById('validation-results');

        let hasIssues = this.envData.unused_env_vars.length > 0 || this.envData.missing_env_vars.length > 0;

        if (hasIssues) {
            validationCard.style.display = 'block';
            
            let html = '';
            
            if (this.envData.missing_env_vars.length > 0) {
                const missingVarsList = this.envData.missing_env_vars.map(varName => `<li><code>${varName}</code></li>`).join('');
                html += `
                    <div class="alert alert-danger">
                        <h6><i class="bi bi-x-circle me-2"></i>Missing Required Variables:</h6>
                        <ul class="mb-0">
                            ${missingVarsList}
                        </ul>
                    </div>
                `;
            }
            
            if (this.envData.unused_env_vars.length > 0) {
                const unusedVarsList = this.envData.unused_env_vars.map(varName => `<li><code>${varName}</code></li>`).join('');
                html += `
                    <div class="alert alert-warning">
                        <h6><i class="bi bi-exclamation-triangle me-2"></i>Unused Variables:</h6>
                        <ul class="mb-0">
                            ${unusedVarsList}
                        </ul>
                    </div>
                `;
            }
            
            validationResults.innerHTML = html;
        } else {
            validationCard.style.display = 'none';
        }
    }

    showSuccessMessage(message) {
        this.showToast(message, 'success');
    }

    showErrorMessage(message) {
        this.showToast(message, 'danger');
    }

    showInfoMessage(message) {
        this.showToast(message, 'info');
    }

    showToast(message, type) {
        // Create toast element
        const toastId = 'toast-' + Date.now();
        const toastHtml = `
            <div id="${toastId}" class="toast align-items-center text-white bg-${type} border-0" role="alert">
                <div class="d-flex">
                    <div class="toast-body">${message}</div>
                    <button type="button" class="btn-close btn-close-white me-2 m-auto" data-bs-dismiss="toast"></button>
                </div>
            </div>
        `;
        
        // Add to toast container (create if doesn't exist)
        let toastContainer = document.getElementById('toast-container');
        if (!toastContainer) {
            toastContainer = document.createElement('div');
            toastContainer.id = 'toast-container';
            toastContainer.className = 'toast-container position-fixed bottom-0 end-0 p-3';
            document.body.appendChild(toastContainer);
        }
        
        toastContainer.insertAdjacentHTML('beforeend', toastHtml);
        
        // Show toast
        const toastElement = document.getElementById(toastId);
        const toast = new bootstrap.Toast(toastElement, {delay: 5000});
        toast.show();
        
        // Remove from DOM after hide
        toastElement.addEventListener('hidden.bs.toast', () => {
            toastElement.remove();
        });
    }
}

// Initialize the environment manager when the DOM is loaded
document.addEventListener('DOMContentLoaded', () => {
    console.log('DOMContentLoaded - initializing EnvironmentManager');
    
    // Check if we're on the environment page
    if (document.querySelector('.environment-manager')) {
        console.log('Environment page detected, creating EnvironmentManager');
        window.environmentManager = new EnvironmentManager();
    } else {
        console.log('Not on environment page, skipping EnvironmentManager initialization');
    }
}); 