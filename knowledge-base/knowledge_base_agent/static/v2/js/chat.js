/* V2 CHAT.JS - MODERN AI CHAT INTERFACE */

class ChatManager {
    constructor(api) {
        this.api = api;
        this.currentSessionId = null;
        this.sessions = new Map();
        this.isTyping = false;
        this.messageCount = 0;
        
        // DOM elements - will be set after initialization
        this.elements = {};
        
        console.log('💬 ChatManager constructor called');
    }

    async initialize() {
        console.log('💬 ChatManager.initialize() called');
        
        try {
            // Load chat page content
            await this.loadPageContent();
            
            // Initialize DOM references
            this.initializeDOMReferences();
            
            // Set up all event listeners
            this.setupEventListeners();
            
            // Load available models
            await this.loadAvailableModels();
            
            // Load existing sessions
            await this.loadChatSessions();
            
            // Initialize with new session
            this.startNewSession();
            
            console.log('✅ ChatManager initialized successfully');
        } catch (error) {
            console.error('❌ ChatManager initialization failed:', error);
            this.showError('Failed to initialize chat interface');
        }
    }

    async loadPageContent() {
        const mainContent = document.getElementById('main-content');
        if (!mainContent) {
            throw new Error('Main content container not found');
        }

        const response = await fetch('/v2/page/chat');
        if (!response.ok) {
            throw new Error(`Failed to load chat content: ${response.status}`);
        }

        const html = await response.text();
        mainContent.innerHTML = html;
        console.log('💬 Chat content loaded');
    }

    initializeDOMReferences() {
        const elements = {
            // Chat UI elements
            chatHistory: 'v2-chat-history',
            chatInput: 'v2-chat-input',
            sendBtn: 'v2-send-btn',
            typingIndicator: 'v2-typing-indicator',
            charCount: 'v2-char-count',
            
            // Session management
            sessionList: 'v2-session-list',
            sessionSearch: 'v2-session-search',
            newChatBtn: 'v2-new-chat-btn',
            
            // Header elements
            chatTitle: 'v2-chat-title',
            chatModelDisplay: 'v2-chat-model-display',
            messageCount: 'v2-message-count',
            
            // Model selector
            modelSelector: 'v2-chat-model-selector',
            
            // Action buttons
            exportBtn: 'v2-export-chat-btn',
            archiveBtn: 'v2-archive-session-btn',
            deleteBtn: 'v2-delete-session-btn',
            
            // Modal
            sessionModal: 'v2-session-modal',
            sessionTitleInput: 'v2-session-title-input',
            sessionCreated: 'v2-session-created',
            sessionMessageCount: 'v2-session-message-count'
        };

        for (const [key, id] of Object.entries(elements)) {
            const element = document.getElementById(id);
            if (!element) {
                console.warn(`Element not found: ${id}`);
            }
            this.elements[key] = element;
        }

        // Verify essential elements
        const essential = ['chatHistory', 'chatInput', 'sendBtn', 'modelSelector'];
        for (const key of essential) {
            if (!this.elements[key]) {
                throw new Error(`Essential element not found: ${key}`);
            }
        }
    }

    setupEventListeners() {
        // Send button click
        this.elements.sendBtn = document.getElementById('v2-send-btn');
        if (this.elements.sendBtn) {
            this.elements.sendBtn.addEventListener('click', (e) => {
                e.preventDefault();
                this.handleChatSubmit();
            });
        }

        // Chat input handling
        this.elements.chatInput.addEventListener('input', () => {
            this.updateCharCount();
            this.updateSendButton();
        });

        this.elements.chatInput.addEventListener('keydown', (e) => {
            if (e.key === 'Enter' && !e.shiftKey) {
                e.preventDefault();
                this.handleChatSubmit();
            }
        });

        // Session management
        if (this.elements.newChatBtn) {
            this.elements.newChatBtn.addEventListener('click', () => {
                this.startNewSession();
            });
        }

        if (this.elements.sessionSearch) {
            this.elements.sessionSearch.addEventListener('input', (e) => {
                this.filterSessions(e.target.value);
            });
        }

        // Model selection
        if (this.elements.modelSelector) {
            this.elements.modelSelector.addEventListener('change', () => {
                this.updateModelDisplay();
            });
        }

        // Action buttons
        if (this.elements.archiveBtn) {
            this.elements.archiveBtn.addEventListener('click', () => {
                this.toggleSessionArchive();
            });
        }

        if (this.elements.deleteBtn) {
            this.elements.deleteBtn.addEventListener('click', () => {
                this.deleteSession();
            });
        }

        if (this.elements.exportBtn) {
            this.elements.exportBtn.addEventListener('click', () => {
                this.exportSession();
            });
        }

        // Sample prompts
        document.addEventListener('click', (e) => {
            if (e.target.closest('.sample-prompt')) {
                const prompt = e.target.closest('.sample-prompt').dataset.prompt;
                if (prompt) {
                    this.elements.chatInput.value = prompt;
                    this.updateCharCount();
                    this.updateSendButton();
                    this.elements.chatInput.focus();
                }
            }
        });

        // Session list clicks
        if (this.elements.sessionList) {
            this.elements.sessionList.addEventListener('click', (e) => {
                const sessionItem = e.target.closest('.session-item');
                if (sessionItem) {
                    const sessionId = sessionItem.dataset.sessionId;
                    this.loadSession(sessionId);
                }
            });
        }

        // Modal handling
        document.addEventListener('click', (e) => {
            if (e.target.dataset.action === 'close') {
                this.closeModal();
            }
        });
    }

    async loadAvailableModels() {
        try {
            const response = await fetch('/api/chat/models');
            if (!response.ok) throw new Error('Failed to fetch models');
            
            const models = await response.json();
            this.populateModelSelector(models);
        } catch (error) {
            console.error('Error loading models:', error);
            this.elements.modelSelector.innerHTML = '<option value="">Default Model</option>';
        }
    }

    populateModelSelector(models) {
        this.elements.modelSelector.innerHTML = '';
        
        if (models.length === 0) {
            this.elements.modelSelector.innerHTML = '<option value="">Default Model</option>';
            return;
        }

        models.forEach(model => {
            const option = document.createElement('option');
            option.value = model.id;
            option.textContent = model.name || model.id;
            this.elements.modelSelector.appendChild(option);
        });

        // Select first model by default
        if (models.length > 0) {
            this.elements.modelSelector.value = models[0].id;
            this.updateModelDisplay();
        }
    }

    async loadChatSessions() {
        try {
            const response = await fetch('/api/chat/sessions');
            if (!response.ok) throw new Error('Failed to fetch sessions');
            
            const sessions = await response.json();
            this.renderSessionList(sessions);
        } catch (error) {
            console.error('Error loading sessions:', error);
            this.elements.sessionList.innerHTML = '<div class="session-error">Failed to load sessions</div>';
        }
    }

    renderSessionList(sessions) {
        if (sessions.length === 0) {
            this.elements.sessionList.innerHTML = `
                <div class="no-sessions">
                    <i class="fas fa-comments"></i>
                    <p>No chat sessions yet</p>
                    <small>Start a new chat to begin</small>
                </div>
            `;
            return;
        }

        const sessionsHtml = sessions.map(session => `
            <div class="session-item ${session.session_id === this.currentSessionId ? 'active' : ''}" 
                 data-session-id="${session.session_id}">
                <div class="session-content">
                    <div class="session-title">${this.escapeHtml(session.title || 'Untitled Chat')}</div>
                    <div class="session-meta">
                        <span class="session-time">${this.formatTime(session.last_updated)}</span>
                        <span class="session-count">${session.message_count} messages</span>
                    </div>
                </div>
                <div class="session-actions">
                    <button class="session-action-btn" data-action="archive" title="Archive">
                        <i class="fas fa-archive"></i>
                    </button>
                </div>
            </div>
        `).join('');

        this.elements.sessionList.innerHTML = sessionsHtml;
    }

    async handleChatSubmit() {
        const query = this.elements.chatInput.value.trim();
        if (!query) return;

        // Check if model is selected
        if (!this.elements.modelSelector.value) {
            this.showError('Please select a model first');
            return;
        }

        // Add user message to UI
        this.addMessage('user', query);
        
        // Clear input and show typing
        this.elements.chatInput.value = '';
        this.updateCharCount();
        this.updateSendButton();
        this.showTyping(true);

        try {
            const response = await fetch('/api/chat/enhanced', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    message: query,
                    model: this.elements.modelSelector.value,
                    session_id: this.currentSessionId
                })
            });

            if (!response.ok) {
                throw new Error(`Server error: ${response.status}`);
            }

            const data = await response.json();
            
            // Update session ID if new session was created
            if (data.session_id && !this.currentSessionId) {
                this.currentSessionId = data.session_id;
                await this.loadChatSessions();
                this.updateSessionInfo();
            }
            
            // Add assistant response
            this.addMessage('assistant', data.response, {
                sources: data.sources,
                context_stats: data.context_stats,
                performance_metrics: data.performance_metrics
            });

        } catch (error) {
            console.error('Error during chat:', error);
            this.addMessage('assistant', `Sorry, an error occurred: ${error.message}`, { isError: true });
        } finally {
            this.showTyping(false);
            this.elements.chatInput.focus();
        }
    }

    addMessage(role, content, metadata = {}) {
        const messageContainer = this.elements.chatHistory;
        
        // Remove welcome message if present
        const welcomeMessage = messageContainer.querySelector('.welcome-message');
        if (welcomeMessage) {
            welcomeMessage.remove();
        }

        const messageEl = document.createElement('div');
        messageEl.className = `chat-message ${role}-message ${metadata.isError ? 'error-message' : ''}`;
        
        const avatarIcon = role === 'user' ? 'fa-user' : 'fa-robot';
        const authorName = role === 'user' ? 'You' : 'Assistant';
        
        messageEl.innerHTML = `
            <div class="message-avatar">
                <i class="fas ${avatarIcon}"></i>
            </div>
            <div class="message-content">
                <div class="message-header">
                    <span class="message-author">${authorName}</span>
                    <span class="message-time">${this.getCurrentTime()}</span>
                </div>
                <div class="message-text">
                    ${this.formatMessageContent(content)}
                </div>
                ${metadata.sources ? this.renderSources(metadata.sources) : ''}
                ${metadata.context_stats ? this.renderContextStats(metadata.context_stats) : ''}
            </div>
        `;

        messageContainer.appendChild(messageEl);
        
        // Update message count
        this.messageCount++;
        this.updateMessageCount();
        
        // Scroll to bottom
        this.scrollToBottom();
        
        // Make links clickable
        this.makeLinksClickable(messageEl);
    }

    formatMessageContent(content) {
        // Convert markdown-like formatting
        let formatted = this.escapeHtml(content);
        
        // Bold
        formatted = formatted.replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>');
        
        // Italic
        formatted = formatted.replace(/\*(.*?)\*/g, '<em>$1</em>');
        
        // Code blocks
        formatted = formatted.replace(/```([\s\S]*?)```/g, '<pre><code>$1</code></pre>');
        
        // Inline code
        formatted = formatted.replace(/`([^`]+)`/g, '<code>$1</code>');
        
        // Convert newlines to proper breaks
        formatted = formatted.replace(/\n/g, '<br>');
        
        // Convert URLs to links
        const urlRegex = /(https?:\/\/[^\s]+)/g;
        formatted = formatted.replace(urlRegex, '<a href="$1" target="_blank" rel="noopener noreferrer">$1</a>');
        
        return formatted;
    }

    makeLinksClickable(messageEl) {
        const links = messageEl.querySelectorAll('a[href]');
        links.forEach(link => {
            link.addEventListener('click', (e) => {
                // Handle internal links differently
                const href = link.getAttribute('href');
                if (href.startsWith('/')) {
                    e.preventDefault();
                    // Handle internal navigation
                    console.log('Internal link clicked:', href);
                }
            });
        });
    }

    renderSources(sources) {
        if (!sources || sources.length === 0) return '';
        
        const sourcesHtml = sources.map(source => `
            <div class="source-item">
                <span class="source-type">${source.doc_type_display || source.type}</span>
                <span class="source-title">${this.escapeHtml(source.title)}</span>
                ${source.score ? `<span class="source-score">${(source.score * 100).toFixed(1)}%</span>` : ''}
            </div>
        `).join('');

        return `
            <div class="message-sources">
                <div class="sources-header">
                    <i class="fas fa-link"></i>
                    <span>Sources</span>
                </div>
                <div class="sources-list">
                    ${sourcesHtml}
                </div>
            </div>
        `;
    }

    renderContextStats(stats) {
        if (!stats || Object.keys(stats).length === 0) return '';
        
        return `
            <div class="context-stats">
                <details>
                    <summary>
                        <i class="fas fa-chart-bar"></i>
                        Context Statistics
                    </summary>
                    <div class="stats-content">
                        ${Object.entries(stats).map(([key, value]) => 
                            `<div class="stat-item">
                                <span class="stat-label">${key}:</span>
                                <span class="stat-value">${value}</span>
                            </div>`
                        ).join('')}
                    </div>
                </details>
            </div>
        `;
    }

    showTyping(show) {
        this.isTyping = show;
        this.elements.typingIndicator.classList.toggle('hidden', !show);
        
        if (show) {
            this.scrollToBottom();
        }
    }

    updateCharCount() {
        const count = this.elements.chatInput.value.length;
        this.elements.charCount.textContent = count;
        
        if (count > 3600) {
            this.elements.charCount.classList.add('warning');
        } else {
            this.elements.charCount.classList.remove('warning');
        }
    }

    updateSendButton() {
        const hasText = this.elements.chatInput.value.trim().length > 0;
        const hasModel = this.elements.modelSelector.value.length > 0;
        const sendButton = this.elements.sendBtn || document.getElementById('v2-send-btn');
        
        if (sendButton) {
            sendButton.disabled = !hasText || !hasModel || this.isTyping;
        }
    }

    updateModelDisplay() {
        const selectedModel = this.elements.modelSelector.value;
        const modelText = this.elements.modelSelector.options[this.elements.modelSelector.selectedIndex]?.text || 'No model selected';
        this.elements.chatModelDisplay.textContent = modelText;
        this.updateSendButton();
    }

    updateMessageCount() {
        this.elements.messageCount.textContent = `${this.messageCount} messages`;
    }

    updateSessionInfo() {
        if (this.currentSessionId) {
            this.elements.chatTitle.textContent = 'Active Chat';
        } else {
            this.elements.chatTitle.textContent = 'New Chat';
        }
    }

    startNewSession() {
        this.currentSessionId = null;
        this.messageCount = 0;
        this.elements.chatHistory.innerHTML = `
            <div class="welcome-message">
                <div class="welcome-icon">
                    <i class="fas fa-robot"></i>
                </div>
                <h2>Welcome to Knowledge Base Chat</h2>
                <p>Ask me anything about your knowledge base. I can help you find information, explain concepts, and provide insights based on your documents.</p>
                <div class="sample-prompts">
                    <div class="prompt-category">
                        <h4>Try asking:</h4>
                        <div class="sample-prompt" data-prompt="What are the main categories in my knowledge base?">
                            "What are the main categories in my knowledge base?"
                        </div>
                        <div class="sample-prompt" data-prompt="Summarize the latest developments in [topic]">
                            "Summarize the latest developments in [topic]"
                        </div>
                        <div class="sample-prompt" data-prompt="Show me examples of [concept] from my documents">
                            "Show me examples of [concept] from my documents"
                        </div>
                    </div>
                </div>
            </div>
        `;
        this.updateSessionInfo();
        this.updateMessageCount();
        this.loadChatSessions(); // Refresh session list
    }

    async loadSession(sessionId) {
        if (sessionId === this.currentSessionId) return;

        try {
            const response = await fetch(`/api/chat/sessions/${sessionId}`);
            if (!response.ok) throw new Error('Failed to load session');
            
            const sessionData = await response.json();
            
            this.currentSessionId = sessionId;
            this.messageCount = sessionData.session.message_count;
            
            // Clear current messages
            this.elements.chatHistory.innerHTML = '';
            
            // Load session messages
            sessionData.messages.forEach(message => {
                const metadata = {};
                if (message.sources) metadata.sources = message.sources;
                if (message.context_stats) metadata.context_stats = message.context_stats;
                
                this.addMessage(message.role, message.content, metadata);
            });
            
            this.updateSessionInfo();
            this.updateMessageCount();
            this.loadChatSessions(); // Refresh to show active session
            
        } catch (error) {
            console.error('Error loading session:', error);
            this.showError('Failed to load chat session');
        }
    }

    scrollToBottom() {
        const container = this.elements.chatHistory.parentElement;
        setTimeout(() => {
            container.scrollTop = container.scrollHeight;
        }, 100);
    }

    showError(message) {
        // You could implement a toast notification here
        console.error(message);
        alert(message); // Temporary simple error display
    }

    escapeHtml(text) {
        const div = document.createElement('div');
        div.textContent = text;
        return div.innerHTML;
    }

    getCurrentTime() {
        return new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
    }

    formatTime(timestamp) {
        const date = new Date(timestamp);
        const now = new Date();
        const diffTime = Math.abs(now - date);
        const diffDays = Math.floor(diffTime / (1000 * 60 * 60 * 24));
        
        if (diffDays === 0) {
            return date.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
        } else if (diffDays === 1) {
            return 'Yesterday';
        } else if (diffDays < 7) {
            return `${diffDays} days ago`;
        } else {
            return date.toLocaleDateString();
        }
    }

    filterSessions(query) {
        const sessionItems = this.elements.sessionList.querySelectorAll('.session-item');
        sessionItems.forEach(item => {
            const title = item.querySelector('.session-title').textContent.toLowerCase();
            const visible = title.includes(query.toLowerCase());
            item.style.display = visible ? 'block' : 'none';
        });
    }

    async toggleSessionArchive() {
        if (!this.currentSessionId) return;
        
        try {
            const response = await fetch(`/api/chat/sessions/${this.currentSessionId}/archive`, {
                method: 'POST'
            });
            
            if (response.ok) {
                await this.loadChatSessions();
            }
        } catch (error) {
            console.error('Error archiving session:', error);
        }
    }

    async deleteSession() {
        if (!this.currentSessionId) return;
        
        if (!confirm('Are you sure you want to delete this chat session? This action cannot be undone.')) {
            return;
        }
        
        try {
            const response = await fetch(`/api/chat/sessions/${this.currentSessionId}`, {
                method: 'DELETE'
            });
            
            if (response.ok) {
                this.startNewSession();
                await this.loadChatSessions();
            }
        } catch (error) {
            console.error('Error deleting session:', error);
        }
    }

    exportSession() {
        if (!this.currentSessionId) return;
        
        // Simple export functionality
        const messages = Array.from(this.elements.chatHistory.querySelectorAll('.chat-message')).map(msg => {
            const role = msg.classList.contains('user-message') ? 'User' : 'Assistant';
            const content = msg.querySelector('.message-text').textContent;
            const time = msg.querySelector('.message-time').textContent;
            return `[${time}] ${role}: ${content}`;
        }).join('\n\n');
        
        const blob = new Blob([messages], { type: 'text/plain' });
        const url = URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        a.download = `chat-session-${this.currentSessionId}.txt`;
        a.click();
        URL.revokeObjectURL(url);
    }

    closeModal() {
        this.elements.sessionModal?.classList.add('hidden');
    }

    cleanup() {
        // Clear any timeouts or intervals if needed
        if (this.typingTimeout) {
            clearTimeout(this.typingTimeout);
        }
    }
}

// Make globally available for router usage
window.ChatManager = ChatManager; 