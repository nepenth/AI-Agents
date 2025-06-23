// knowledge_base_agent/static/js/chat.js

// Centralized chat state and functions
const chatSystem = {
    currentSessionId: null,
    chatSessions: [],
    
    // --- Session Management ---
    async createNewSession() {
        try {
            const response = await fetch('/api/chat/sessions', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ title: 'New Chat' })
            });
            
            if (response.ok) {
                const sessionData = await response.json();
                this.currentSessionId = sessionData.session_id;
                localStorage.setItem('currentChatSession', this.currentSessionId);
                await this.loadChatSessions(); // Use 'this'
                return sessionData;
            }
        } catch (error) {
            console.error('Error creating new session:', error);
        }
        return null;
    },
    
    async loadChatSessions() {
        try {
            const response = await fetch('/api/chat/sessions');
            if (response.ok) {
                this.chatSessions = await response.json();
                this.updateSessionSelector();
            }
        } catch (error) {
            console.error('Error loading chat sessions:', error);
        }
    },
    
    async loadChatSession(sessionId) {
        try {
            const response = await fetch(`/api/chat/sessions/${sessionId}`);
            if (response.ok) {
                const sessionData = await response.json();
                this.currentSessionId = sessionId;
                localStorage.setItem('currentChatSession', this.currentSessionId);
                
                const chatHistory = document.getElementById('chat-history-page');
                if (chatHistory) {
                    chatHistory.innerHTML = '';
                    sessionData.messages.forEach(message => {
                        this.appendMessage(chatHistory, message.role, message.content, 
                                    message.sources || [], message.context_stats || {}, 
                                    message.performance_metrics || {});
                    });
                }
                
                return sessionData;
            }
        } catch (error) {
            console.error('Error loading chat session:', error);
        }
        return null;
    },
    
    async archiveSession(sessionId) {
        try {
            const response = await fetch(`/api/chat/sessions/${sessionId}/archive`, {
                method: 'POST'
            });
            
            if (response.ok) {
                await this.loadChatSessions();
                this.showToast('Session archived successfully', 'success');
            }
        } catch (error) {
            console.error('Error archiving session:', error);
            this.showToast('Failed to archive session', 'error');
        }
    },
    
    async deleteSession(sessionId) {
        if (!confirm('Are you sure you want to delete this chat session? This action cannot be undone.')) {
            return;
        }
        
        try {
            const response = await fetch(`/api/chat/sessions/${sessionId}`, {
                method: 'DELETE'
            });
            
            if (response.ok) {
                if (this.currentSessionId === sessionId) {
                    this.currentSessionId = null;
                    localStorage.removeItem('currentChatSession');
                    this.clearChatHistory('chat-history-page');
                }
                await this.loadChatSessions();
                this.showToast('Session deleted successfully', 'success');
            }
        } catch (error) {
            console.error('Error deleting session:', error);
            this.showToast('Failed to delete session', 'error');
        }
    },
    
    updateSessionSelector() {
        const selector = document.getElementById('chat-session-selector');
        if (!selector) return;
        
        selector.innerHTML = '<option value="">New Chat</option>';
        
        const activeSessions = this.chatSessions.filter(s => !s.is_archived);
        const archivedSessions = this.chatSessions.filter(s => s.is_archived);
        
        if (activeSessions.length > 0) {
            const activeGroup = document.createElement('optgroup');
            activeGroup.label = 'Active Chats';
            activeSessions.forEach(session => {
                const option = document.createElement('option');
                option.value = session.session_id;
                option.textContent = session.title || `Chat ${session.id}`;
                if (session.session_id === this.currentSessionId) {
                    option.selected = true;
                }
                activeGroup.appendChild(option);
            });
            selector.appendChild(activeGroup);
        }
        
        if (archivedSessions.length > 0) {
            const archivedGroup = document.createElement('optgroup');
            archivedGroup.label = 'Archived Chats';
            archivedSessions.forEach(session => {
                const option = document.createElement('option');
                option.value = session.session_id;
                option.textContent = `[Archived] ${session.title || `Chat ${session.id}`}`;
                archivedGroup.appendChild(option);
            });
            selector.appendChild(archivedGroup);
        }
    },

    async fetchAndPopulateModels() {
        try {
            const response = await fetch('/api/chat/models');
            if (!response.ok) {
                throw new Error('Failed to fetch chat models');
            }
            const models = await response.json();
            
            const widgetSelector = document.getElementById('chat-model-selector-widget');
            const pageSelector = document.getElementById('chat-model-selector-page');

            if (widgetSelector) this.populateSelector(widgetSelector, models);
            if (pageSelector) this.populateSelector(pageSelector, models);

        } catch (error) {
            console.error('Error fetching chat models:', error);
        }
    },

    populateSelector(selector, models) {
        selector.innerHTML = '';
        models.forEach(model => {
            const option = document.createElement('option');
            option.value = model.id;
            option.textContent = model.name;
            selector.appendChild(option);
        });
    },

    async handleChatSubmit(inputId, historyId, typingIndicatorId, selectorId) {
        const chatInput = document.getElementById(inputId);
        const query = chatInput.value.trim();
        if (!query) return;

        const chatHistory = document.getElementById(historyId);
        const typingIndicator = document.getElementById(typingIndicatorId);
        const modelSelector = document.getElementById(selectorId);

        this.appendMessage(chatHistory, 'user', query);
        chatInput.value = '';
        chatInput.disabled = true;
        if (typingIndicator) typingIndicator.style.display = 'block';

        const selectedModel = modelSelector ? modelSelector.value : null;

        try {
            const response = await fetch('/api/chat', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ 
                    message: query, 
                    model: selectedModel,
                    session_id: this.currentSessionId
                })
            });

            if (!response.ok) {
                const errorData = await response.json();
                throw new Error(errorData.error || `HTTP ${response.status}: ${response.statusText}`);
            }

            const data = await response.json();
            
            if (data.session_id && !this.currentSessionId) {
                this.currentSessionId = data.session_id;
                localStorage.setItem('currentChatSession', this.currentSessionId);
                await this.loadChatSessions();
            }
            
            if (data.query_type) {
                console.log(`Query classified as: ${data.query_type}`);
            }
            
            this.appendMessage(chatHistory, 'assistant', data.response, data.sources, data.context_stats, data.performance_metrics);

        } catch (error) {
            console.error('Error during chat:', error);
            this.appendMessage(chatHistory, 'assistant', `Sorry, an error occurred: ${error.message}`);
        } finally {
            if (typingIndicator) typingIndicator.style.display = 'none';
            chatInput.disabled = false;
            chatInput.focus();
        }
    },

    appendMessage(history, role, text, sources = [], contextStats = {}, performanceMetrics = {}) {
        if (!history) return;
        
        const messageDiv = document.createElement('div');
        messageDiv.className = `chat-message ${role}-message`;
        
        const p = document.createElement('p');
        p.innerHTML = text.replace(/\n/g, '<br>');
        messageDiv.appendChild(p);

        if (role === 'assistant' && performanceMetrics && Object.keys(performanceMetrics).length > 0) {
            const metricsDiv = document.createElement('div');
            metricsDiv.className = 'chat-performance-metrics';
            
            const metricsToggle = document.createElement('button');
            metricsToggle.className = 'btn btn-outline-info btn-sm metrics-toggle';
            metricsToggle.innerHTML = '<i class="bi bi-speedometer2"></i> Performance Details';
            metricsToggle.style.fontSize = '0.75rem';
            metricsToggle.style.padding = '4px 8px';
            metricsToggle.style.marginTop = '8px';
            metricsToggle.style.marginBottom = '4px';
            
            const metricsContent = document.createElement('div');
            metricsContent.className = 'metrics-content';
            metricsContent.style.display = 'none';
            metricsContent.style.marginTop = '8px';
            metricsContent.style.padding = '12px';
            metricsContent.style.backgroundColor = '#f8f9fa';
            metricsContent.style.borderRadius = '6px';
            metricsContent.style.fontSize = '0.85rem';
            metricsContent.style.border = '1px solid #dee2e6';
            metricsContent.style.fontFamily = 'monospace';
            
            const responseTime = performanceMetrics.response_time_ms ? `${performanceMetrics.response_time_ms}ms` : 'N/A';
            const responseTimeSeconds = performanceMetrics.response_time_seconds ? `${performanceMetrics.response_time_seconds}s` : 'N/A';
            const tokensPerSecond = performanceMetrics.tokens_per_second ? `${performanceMetrics.tokens_per_second} tokens/sec` : 'N/A';
            const inputTokens = performanceMetrics.estimated_input_tokens || 'N/A';
            const outputTokens = performanceMetrics.estimated_output_tokens || 'N/A';
            const totalTokens = performanceMetrics.estimated_total_tokens || 'N/A';
            const model = performanceMetrics.model || 'N/A';
            const contextLength = performanceMetrics.context_length || contextStats?.total_sources || 0;
            
            const metricsHTML = `
                <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 12px;">
                    <div>
                        <div style="font-weight: bold; color: #495057; margin-bottom: 8px;">⏱️ Timing</div>
                        <div>Response Time: <span style="color: #007bff; font-weight: 500;">${responseTime} (${responseTimeSeconds})</span></div>
                        <div>Generation Speed: <span style="color: #28a745; font-weight: 500;">${tokensPerSecond}</span></div>
                    </div>
                    <div>
                        <div style="font-weight: bold; color: #495057; margin-bottom: 8px;">📊 Tokens</div>
                        <div>Input: <span style="color: #6c757d;">${inputTokens}</span></div>
                        <div>Output: <span style="color: #6c757d;">${outputTokens}</span></div>
                        <div>Total: <span style="color: #17a2b8; font-weight: 500;">${totalTokens}</span></div>
                    </div>
                </div>
                <hr style="margin: 12px 0; border-color: #dee2e6;">
                <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 12px;">
                    <div>
                        <div style="font-weight: bold; color: #495057; margin-bottom: 8px;">🤖 Model</div>
                        <div style="color: #6f42c1; font-weight: 500;">${model}</div>
                    </div>
                    <div>
                        <div style="font-weight: bold; color: #495057; margin-bottom: 8px;">📚 Context</div>
                        <div><span style="color: #fd7e14; font-weight: 500;">${contextLength}</span> sources used</div>
                    </div>
                </div>
            `;
            
            metricsContent.innerHTML = metricsHTML;
            
            metricsToggle.addEventListener('click', () => {
                const isVisible = metricsContent.style.display !== 'none';
                metricsContent.style.display = isVisible ? 'none' : 'block';
                metricsToggle.innerHTML = isVisible ? '<i class="bi bi-speedometer2"></i> Performance Details' : '<i class="bi bi-speedometer2-fill"></i> Hide Details';
                metricsToggle.className = isVisible ? 'btn btn-outline-info btn-sm metrics-toggle' : 'btn btn-info btn-sm metrics-toggle';
            });
            
            metricsDiv.appendChild(metricsToggle);
            metricsDiv.appendChild(metricsContent);
            messageDiv.appendChild(metricsDiv);
        }

        if (sources && sources.length > 0) {
            const sourcesDiv = document.createElement('div');
            sourcesDiv.className = 'chat-sources';
            
            if (contextStats && Object.keys(contextStats).length > 0) {
                const statsDiv = document.createElement('div');
                statsDiv.className = 'chat-context-stats';
                statsDiv.innerHTML = `
                    <strong>📊 Context Summary:</strong> 
                    ${contextStats.total_sources || 0} sources 
                    (${contextStats.synthesis_docs || 0} syntheses, 
                    ${contextStats.kb_items || 0} items) 
                    across ${contextStats.categories_covered || 0} categories
                `;
                sourcesDiv.appendChild(statsDiv);
            }
            
            sourcesDiv.innerHTML += '<strong>🔗 Sources:</strong>';
            const sourcesList = document.createElement('div');
            sourcesList.className = 'sources-list';
            
            sources.forEach((source, index) => {
                const sourceItem = document.createElement('div');
                sourceItem.className = 'source-item';
                
                const sourceLink = document.createElement('a');
                sourceLink.href = source.url || '#';
                sourceLink.className = 'source-link';
                sourceLink.textContent = source.title || 'Unknown Source';
                
                sourceLink.onclick = (e) => {
                    if (source.url && source.url !== '#') {
                        window.location.href = source.url;
                    } else {
                        e.preventDefault();
                        console.log('Source clicked but no URL available:', source);
                    }
                };
                
                const metadata = document.createElement('div');
                metadata.className = 'source-metadata';
                
                let metadataContent = '';
                
                if (source.doc_type_display) {
                    metadataContent += `<span class="doc-type">${source.doc_type_display}</span>`;
                }
                
                if (source.category || source.subcategory) {
                    const categoryPath = [source.category, source.subcategory].filter(Boolean).join('/');
                    metadataContent += `<span class="category">${categoryPath}</span>`;
                }
                
                if (source.score !== undefined && source.score !== null) {
                    const scorePercent = (source.score * 100).toFixed(1);
                    const scoreClass = source.score > 0.8 ? 'high-score' : source.score > 0.6 ? 'med-score' : 'low-score';
                    metadataContent += `<span class="score ${scoreClass}">${scorePercent}% relevant</span>`;
                }
                
                metadata.innerHTML = metadataContent;
                
                sourceItem.appendChild(sourceLink);
                sourceItem.appendChild(metadata);
                sourcesList.appendChild(sourceItem);
            });
            
            sourcesDiv.appendChild(sourcesList);
            messageDiv.appendChild(sourcesDiv);
        }
        
        history.appendChild(messageDiv);
        history.scrollTop = history.scrollHeight;
    },

    clearChatHistory(historyId) {
        const history = document.getElementById(historyId);
        if (!history) return;
        
        const messages = history.querySelectorAll('.chat-message');
        messages.forEach(message => {
            if (message.classList.contains('assistant-message') && message.querySelector('p')?.textContent.includes('Hello! How can I help you')) {
                return;
            }
            message.remove();
        });
        
        console.log('Chat history cleared');
    },

    setupClearChatButton(context) {
        const suffix = context === 'widget' ? '-widget' : '-page';
        const clearButtonId = `clear-chat${suffix}`;
        const historyId = `chat-history${suffix}`;
        
        const clearButton = document.getElementById(clearButtonId);
        if (clearButton) {
            const newButton = clearButton.cloneNode(true);
            clearButton.parentNode.replaceChild(newButton, clearButton);
            
            newButton.addEventListener('click', () => {
                if (confirm('Are you sure you want to clear the chat history?')) {
                    this.clearChatHistory(historyId);
                    this.currentSessionId = null;
                    localStorage.removeItem('currentChatSession');
                }
            });
        }
    },

    setupSessionControls() {
        const sessionSelector = document.getElementById('chat-session-selector');
        if (sessionSelector) {
            sessionSelector.addEventListener('change', async (e) => {
                const selectedSessionId = e.target.value;
                if (selectedSessionId) {
                    await this.loadChatSession(selectedSessionId);
                } else {
                    this.currentSessionId = null;
                    localStorage.removeItem('currentChatSession');
                    this.clearChatHistory('chat-history-page');
                }
            });
        }
        
        const newChatButton = document.getElementById('new-chat-btn');
        if (newChatButton) {
            newChatButton.addEventListener('click', async () => {
                this.currentSessionId = null;
                localStorage.removeItem('currentChatSession');
                this.clearChatHistory('chat-history-page');
                this.updateSessionSelector();
            });
        }
        
        const archiveButton = document.getElementById('archive-session-btn');
        if (archiveButton) {
            archiveButton.addEventListener('click', () => {
                if (this.currentSessionId) this.archiveSession(this.currentSessionId);
            });
        }
        
        const deleteButton = document.getElementById('delete-session-btn');
        if (deleteButton) {
            deleteButton.addEventListener('click', () => {
                if (this.currentSessionId) this.deleteSession(this.currentSessionId);
            });
        }
    },
    
    showToast(message, type = 'info') {
        const toastContainer = document.getElementById('toast-container') || this.createToastContainer();
        const toast = document.createElement('div');
        toast.className = `toast align-items-center text-white bg-${type} border-0`;
        toast.setAttribute('role', 'alert');
        toast.innerHTML = `<div class="d-flex"><div class="toast-body">${message}</div><button type="button" class="btn-close btn-close-white me-2 m-auto" data-bs-dismiss="toast"></button></div>`;
        toastContainer.appendChild(toast);
        const bsToast = new bootstrap.Toast(toast);
        bsToast.show();
        toast.addEventListener('hidden.bs.toast', () => toast.remove());
    },

    createToastContainer() {
        const container = document.createElement('div');
        container.id = 'toast-container';
        container.className = 'toast-container position-fixed top-0 end-0 p-3';
        container.style.zIndex = '1100';
        document.body.appendChild(container);
        return container;
    },

    initializeChat(context) {
        console.log(`Initializing chat for context: ${context}`);
        
        const suffix = context === 'widget' ? '-widget' : '-page';
        const formId = `chat-form${suffix}`;
        const inputId = `chat-input${suffix}`;
        const historyId = `chat-history${suffix}`;
        const typingIndicatorId = `chat-typing-indicator${suffix}`;
        const selectorId = `chat-model-selector${suffix}`;

        const form = document.getElementById(formId);
        if (form) {
            const newForm = form.cloneNode(true);
            form.parentNode.replaceChild(newForm, form);
            
            const newInput = newForm.querySelector('textarea');
            if (!newInput) return;
            
            newForm.addEventListener('submit', (event) => {
                event.preventDefault();
                this.handleChatSubmit(inputId, historyId, typingIndicatorId, selectorId);
            });

            newInput.addEventListener('keydown', (event) => {
                if (event.key === 'Enter' && !event.shiftKey) {
                    event.preventDefault();
                    newForm.dispatchEvent(new Event('submit'));
                }
            });
            
            this.setupClearChatButton(context);
            console.log(`Chat initialized successfully for ${context}`);
        }
    },

    initializeWidget() {
        this.initializeChat('widget');
        const savedSessionId = localStorage.getItem('currentChatSession');
        if (savedSessionId) {
            this.currentSessionId = savedSessionId;
        }
        this.fetchAndPopulateModels();
    },

    initializePage() {
        console.log('Chat page detected, initializing...');
        this.initializeChat('page');
        this.setupSessionControls();
        this.fetchAndPopulateModels();
        
        if (this.currentSessionId) {
            this.loadChatSession(this.currentSessionId);
        } else {
            this.loadChatSessions();
        }

        // Attach listeners for GPU panel on chat page
        const gpuPanelHeader = document.getElementById('gpu-panel-header');
        const gpuPanelBody = document.getElementById('gpu-panel-body');
        const gpuToggleIcon = document.getElementById('gpu-panel-toggle-icon');
        const refreshGpuBtn = document.getElementById('refresh-gpu-chat');

        if (gpuPanelHeader) {
            gpuPanelHeader.addEventListener('click', () => {
                const isCollapsed = gpuPanelBody.style.display === 'none';
                gpuPanelBody.style.display = isCollapsed ? 'block' : 'none';
                gpuToggleIcon.className = isCollapsed ? 'bi bi-chevron-up' : 'bi bi-chevron-down';
                if (isCollapsed && window.agentManager && window.agentManager.refreshGPUStats) {
                    window.agentManager.refreshGPUStats('gpuStatsContainerChat');
                }
            });
        }
        
        if (refreshGpuBtn) {
            refreshGpuBtn.addEventListener('click', (e) => {
                e.stopPropagation(); // Prevent the header click event from firing
                if (window.agentManager && window.agentManager.refreshGPUStats) {
                    window.agentManager.refreshGPUStats('gpuStatsContainerChat');
                }
            });
        }
    }
};

// --- Global Functions ---
function toggleChat() {
    const chatWidget = document.querySelector('#chat-widget');
    const chatBody = document.querySelector('#chat-widget .chat-widget-body');
    if (!chatWidget) return;
    
    chatWidget.classList.toggle('chat-widget-open');
    const isOpen = chatWidget.classList.contains('chat-widget-open');
    if (chatBody) chatBody.style.display = isOpen ? 'flex' : 'none';
}

// Expose functions to global scope
window.toggleChat = toggleChat;
window.initializeChatSystem = () => chatSystem.initializeWidget();
window.initializeChatPage = () => chatSystem.initializePage(); 