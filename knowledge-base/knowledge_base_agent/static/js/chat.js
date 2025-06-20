// knowledge_base_agent/static/js/chat.js

document.addEventListener('DOMContentLoaded', function() {
    console.log('Chat.js: Initializing chat functionality');
    
    // Chat session management
    let currentSessionId = null;
    let chatSessions = [];
    
    // --- Session Management ---
    async function createNewSession() {
        try {
            const response = await fetch('/api/chat/sessions', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ title: 'New Chat' })
            });
            
            if (response.ok) {
                const sessionData = await response.json();
                currentSessionId = sessionData.session_id;
                localStorage.setItem('currentChatSession', currentSessionId);
                loadChatSessions();
                return sessionData;
            }
        } catch (error) {
            console.error('Error creating new session:', error);
        }
        return null;
    }
    
    async function loadChatSessions() {
        try {
            const response = await fetch('/api/chat/sessions');
            if (response.ok) {
                chatSessions = await response.json();
                updateSessionSelector();
            }
        } catch (error) {
            console.error('Error loading chat sessions:', error);
        }
    }
    
    async function loadChatSession(sessionId) {
        try {
            const response = await fetch(`/api/chat/sessions/${sessionId}`);
            if (response.ok) {
                const sessionData = await response.json();
                currentSessionId = sessionId;
                localStorage.setItem('currentChatSession', currentSessionId);
                
                // Clear current chat history
                const chatHistory = document.getElementById('chat-history-page');
                if (chatHistory) {
                    chatHistory.innerHTML = '';
                    
                    // Load messages from session
                    sessionData.messages.forEach(message => {
                        appendMessage(chatHistory, message.role, message.content, 
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
    }
    
    async function archiveSession(sessionId) {
        try {
            const response = await fetch(`/api/chat/sessions/${sessionId}/archive`, {
                method: 'POST'
            });
            
            if (response.ok) {
                loadChatSessions();
                showToast('Session archived successfully', 'success');
            }
        } catch (error) {
            console.error('Error archiving session:', error);
            showToast('Failed to archive session', 'error');
        }
    }
    
    async function deleteSession(sessionId) {
        if (!confirm('Are you sure you want to delete this chat session? This action cannot be undone.')) {
            return;
        }
        
        try {
            const response = await fetch(`/api/chat/sessions/${sessionId}`, {
                method: 'DELETE'
            });
            
            if (response.ok) {
                if (currentSessionId === sessionId) {
                    currentSessionId = null;
                    localStorage.removeItem('currentChatSession');
                    clearChatHistory('chat-history-page');
                }
                loadChatSessions();
                showToast('Session deleted successfully', 'success');
            }
        } catch (error) {
            console.error('Error deleting session:', error);
            showToast('Failed to delete session', 'error');
        }
    }
    
    function updateSessionSelector() {
        const selector = document.getElementById('chat-session-selector');
        if (!selector) return;
        
        selector.innerHTML = '<option value="">New Chat</option>';
        
        // Group sessions by archived status
        const activeSessions = chatSessions.filter(s => !s.is_archived);
        const archivedSessions = chatSessions.filter(s => s.is_archived);
        
        if (activeSessions.length > 0) {
            const activeGroup = document.createElement('optgroup');
            activeGroup.label = 'Active Chats';
            activeSessions.forEach(session => {
                const option = document.createElement('option');
                option.value = session.session_id;
                option.textContent = session.title || `Chat ${session.id}`;
                if (session.session_id === currentSessionId) {
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
    }
    
    // --- Model Loading ---
    async function fetchAndPopulateModels() {
        try {
            const response = await fetch('/api/chat/models');
            if (!response.ok) {
                throw new Error('Failed to fetch chat models');
            }
            const models = await response.json();
            
            const widgetSelector = document.getElementById('chat-model-selector-widget');
            const pageSelector = document.getElementById('chat-model-selector-page');

            if (widgetSelector) {
                populateSelector(widgetSelector, models);
            }
            if (pageSelector) {
                populateSelector(pageSelector, models);
            }
        } catch (error) {
            console.error('Error fetching chat models:', error);
        }
    }

    function populateSelector(selector, models) {
        selector.innerHTML = '';
        models.forEach(model => {
            const option = document.createElement('option');
            option.value = model.id;
            option.textContent = model.name;
            selector.appendChild(option);
        });
    }

    // --- Core Chat Logic ---
    async function handleChatSubmit(inputId, historyId, typingIndicatorId, selectorId) {
        const chatInput = document.getElementById(inputId);
        const query = chatInput.value.trim();
        if (!query) return;

        const chatHistory = document.getElementById(historyId);
        const typingIndicator = document.getElementById(typingIndicatorId);
        const modelSelector = document.getElementById(selectorId);

        // Add user message to history
        appendMessage(chatHistory, 'user', query);
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
                    session_id: currentSessionId
                })
            });

            if (!response.ok) {
                const errorData = await response.json();
                throw new Error(errorData.error || `HTTP ${response.status}: ${response.statusText}`);
            }

            const data = await response.json();
            
            // Update current session ID if it was created
            if (data.session_id && !currentSessionId) {
                currentSessionId = data.session_id;
                localStorage.setItem('currentChatSession', currentSessionId);
                loadChatSessions();
            }
            
            // Display query type if available
            if (data.query_type) {
                console.log(`Query classified as: ${data.query_type}`);
            }
            
            appendMessage(chatHistory, 'assistant', data.response, data.sources, data.context_stats, data.performance_metrics);

        } catch (error) {
            console.error('Error during chat:', error);
            appendMessage(chatHistory, 'assistant', `Sorry, an error occurred: ${error.message}`);
        } finally {
            if (typingIndicator) typingIndicator.style.display = 'none';
            chatInput.disabled = false;
            chatInput.focus();
        }
    }

    function appendMessage(history, role, text, sources = [], contextStats = {}, performanceMetrics = {}) {
        if (!history) return;
        
        const messageDiv = document.createElement('div');
        messageDiv.className = `chat-message ${role}-message`;
        
        const p = document.createElement('p');
        p.innerHTML = text.replace(/\n/g, '<br>');
        messageDiv.appendChild(p);

        // Add performance metrics for assistant messages
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
            
            // Format performance metrics with better organization
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
            
            // Toggle functionality with enhanced UX
            metricsToggle.addEventListener('click', () => {
                const isVisible = metricsContent.style.display !== 'none';
                metricsContent.style.display = isVisible ? 'none' : 'block';
                metricsToggle.innerHTML = isVisible ? 
                    '<i class="bi bi-speedometer2"></i> Performance Details' : 
                    '<i class="bi bi-speedometer2-fill"></i> Hide Details';
                metricsToggle.className = isVisible ? 
                    'btn btn-outline-info btn-sm metrics-toggle' : 
                    'btn btn-info btn-sm metrics-toggle';
            });
            
            metricsDiv.appendChild(metricsToggle);
            metricsDiv.appendChild(metricsContent);
            messageDiv.appendChild(metricsDiv);
        }

        // Enhanced source display with rich metadata
        if (sources && sources.length > 0) {
            const sourcesDiv = document.createElement('div');
            sourcesDiv.className = 'chat-sources';
            
            // Add context stats if available
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
                
                // Create main source link
                const sourceLink = document.createElement('a');
                sourceLink.href = source.url || '#';
                sourceLink.className = 'source-link';
                sourceLink.textContent = source.title || 'Unknown Source';
                
                // Handle click for navigation
                sourceLink.onclick = (e) => {
                    if (source.url && source.url !== '#') {
                        // Navigate to the source page
                        window.location.href = source.url;
                    } else {
                        e.preventDefault();
                        console.log('Source clicked but no URL available:', source);
                    }
                };
                
                // Create metadata display
                const metadata = document.createElement('div');
                metadata.className = 'source-metadata';
                
                let metadataContent = '';
                
                // Document type with emoji
                if (source.doc_type_display) {
                    metadataContent += `<span class="doc-type">${source.doc_type_display}</span>`;
                }
                
                // Category information
                if (source.category || source.subcategory) {
                    const categoryPath = [source.category, source.subcategory].filter(Boolean).join('/');
                    metadataContent += `<span class="category">${categoryPath}</span>`;
                }
                
                // Relevance score
                if (source.score !== undefined && source.score !== null) {
                    const scorePercent = (source.score * 100).toFixed(1);
                    const scoreClass = source.score > 0.8 ? 'high-score' : source.score > 0.6 ? 'med-score' : 'low-score';
                    metadataContent += `<span class="score ${scoreClass}">${scorePercent}% relevant</span>`;
                }
                
                metadata.innerHTML = metadataContent;
                
                // Assemble source item
                sourceItem.appendChild(sourceLink);
                sourceItem.appendChild(metadata);
                sourcesList.appendChild(sourceItem);
            });
            
            sourcesDiv.appendChild(sourcesList);
            messageDiv.appendChild(sourcesDiv);
        }
        
        history.appendChild(messageDiv);
        history.scrollTop = history.scrollHeight;
    }

    // --- Clear Chat Functionality ---
    function clearChatHistory(historyId) {
        const history = document.getElementById(historyId);
        if (!history) return;
        
        // Remove all chat messages except any initial system message
        const messages = history.querySelectorAll('.chat-message');
        messages.forEach(message => {
            // Keep the initial assistant welcome message
            if (message.classList.contains('assistant-message') && 
                message.querySelector('p')?.textContent.includes('Hello! How can I help you')) {
                return;
            }
            message.remove();
        });
        
        console.log('Chat history cleared');
    }

    function setupClearChatButton(context) {
        const suffix = context === 'widget' ? '-widget' : '-page';
        const clearButtonId = `clear-chat${suffix}`;
        const historyId = `chat-history${suffix}`;
        
        const clearButton = document.getElementById(clearButtonId);
        if (clearButton) {
            // Remove any existing event listeners
            const newButton = clearButton.cloneNode(true);
            clearButton.parentNode.replaceChild(newButton, clearButton);
            
            newButton.addEventListener('click', () => {
                if (confirm('Are you sure you want to clear the chat history?')) {
                    clearChatHistory(historyId);
                    // Start a new session
                    currentSessionId = null;
                    localStorage.removeItem('currentChatSession');
                }
            });
        }
    }

    // --- Session Controls ---
    function setupSessionControls() {
        // Session selector
        const sessionSelector = document.getElementById('chat-session-selector');
        if (sessionSelector) {
            sessionSelector.addEventListener('change', async (e) => {
                const selectedSessionId = e.target.value;
                if (selectedSessionId) {
                    await loadChatSession(selectedSessionId);
                } else {
                    // New chat
                    currentSessionId = null;
                    localStorage.removeItem('currentChatSession');
                    clearChatHistory('chat-history-page');
                }
            });
        }
        
        // New chat button
        const newChatButton = document.getElementById('new-chat-btn');
        if (newChatButton) {
            newChatButton.addEventListener('click', async () => {
                currentSessionId = null;
                localStorage.removeItem('currentChatSession');
                clearChatHistory('chat-history-page');
                updateSessionSelector();
            });
        }
        
        // Archive session button
        const archiveButton = document.getElementById('archive-session-btn');
        if (archiveButton) {
            archiveButton.addEventListener('click', () => {
                if (currentSessionId) {
                    archiveSession(currentSessionId);
                }
            });
        }
        
        // Delete session button
        const deleteButton = document.getElementById('delete-session-btn');
        if (deleteButton) {
            deleteButton.addEventListener('click', () => {
                if (currentSessionId) {
                    deleteSession(currentSessionId);
                }
            });
        }
    }
    
    // --- Toast Notifications ---
    function showToast(message, type = 'info') {
        const toastContainer = document.getElementById('toast-container') || createToastContainer();
        
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

    function createToastContainer() {
        const container = document.createElement('div');
        container.id = 'toast-container';
        container.className = 'toast-container position-fixed top-0 end-0 p-3';
        container.style.zIndex = '1100';
        document.body.appendChild(container);
        return container;
    }

    // --- Chat Initialization ---
    function initializeChat(context) {
        console.log(`Initializing chat for context: ${context}`);
        
        const suffix = context === 'widget' ? '-widget' : '-page';
        const formId = `chat-form${suffix}`;
        const inputId = `chat-input${suffix}`;
        const historyId = `chat-history${suffix}`;
        const typingIndicatorId = `chat-typing-indicator${suffix}`;
        const selectorId = `chat-model-selector${suffix}`;

        const form = document.getElementById(formId);
        const input = document.getElementById(inputId);
        const history = document.getElementById(historyId);

        if (form && input && history) {
            console.log(`Found chat elements for ${context}`);
            
            // Remove existing event listeners by cloning the form
            const newForm = form.cloneNode(true);
            form.parentNode.replaceChild(newForm, form);
            
            // Get the new input element from the cloned form
            const newInput = newForm.querySelector('textarea');
            if (!newInput) {
                console.error(`Failed to find textarea in cloned form for ${context}`);
                return;
            }
            
            console.log(`Setting up event listeners for ${context}`);
            
            // Add submit handler
            newForm.addEventListener('submit', (event) => {
                event.preventDefault();
                console.log(`Form submitted for ${context}`);
                handleChatSubmit(inputId, historyId, typingIndicatorId, selectorId);
            });

            // Setup Enter/Shift+Enter handling on the new input
            newInput.addEventListener('keydown', function(event) {
                if (event.key === 'Enter') {
                    if (event.shiftKey) {
                        // Shift+Enter: Allow new line (default behavior)
                        console.log(`Shift+Enter pressed for ${context}`);
                        return;
                    } else {
                        // Enter without Shift: Submit form
                        console.log(`Enter pressed for ${context}, submitting form`);
                        event.preventDefault();
                        newForm.dispatchEvent(new Event('submit'));
                    }
                }
            });
            
            // Setup clear chat button
            setupClearChatButton(context);
            
            console.log(`Chat initialized successfully for ${context}`);
        } else {
            console.warn(`Chat elements not found for context: ${context}. Form: ${!!form}, Input: ${!!input}, History: ${!!history}`);
        }
    }

    // --- Initialize ---
    // Load session from localStorage on page load
    const savedSessionId = localStorage.getItem('currentChatSession');
    if (savedSessionId) {
        currentSessionId = savedSessionId;
    }
    
    // Load initial data
    loadChatSessions();
    setupSessionControls();
    
    // Widget Chat Initialization
    initializeChat('widget');
    
    // Dynamic Page Chat Initialization
    const observer = new MutationObserver((mutationsList) => {
        for (const mutation of mutationsList) {
            if (mutation.type === 'childList') {
                const chatPageContainer = document.querySelector('.chat-page-container');
                if (chatPageContainer && !chatPageContainer.dataset.initialized) {
                    chatPageContainer.dataset.initialized = 'true';
                    console.log('Chat page detected, initializing...');
                    initializeChat('page');
                    setupSessionControls();
                    
                    // Load session if we have one saved
                    if (currentSessionId) {
                        loadChatSession(currentSessionId);
                    }
                    
                    fetchAndPopulateModels(); // Refresh models for the page
                    observer.disconnect();
                    break;
                }
            }
        }
    });

    observer.observe(document.body, { childList: true, subtree: true });

    // Initial model load
    fetchAndPopulateModels();
});

// --- Global Functions ---
function toggleChat() {
    const chatWidget = document.querySelector('#chat-widget');
    const chatBody = document.querySelector('#chat-widget .chat-widget-body');
    const toggleIcon = document.querySelector('.chat-toggle-icon');
    
    if (!chatWidget || !toggleIcon) {
        console.error('Chat widget or toggle icon not found');
        return;
    }
    
    if (chatWidget.classList.contains('chat-widget-open')) {
        chatWidget.classList.remove('chat-widget-open');
        if (chatBody) chatBody.style.display = 'none';
        toggleIcon.textContent = '+';
        console.log('Chat widget minimized');
    } else {
        chatWidget.classList.add('chat-widget-open');
        if (chatBody) chatBody.style.display = 'flex';
        toggleIcon.textContent = '-';
        console.log('Chat widget opened');
    }
}

// Expose functions to global scope
window.toggleChat = toggleChat; 