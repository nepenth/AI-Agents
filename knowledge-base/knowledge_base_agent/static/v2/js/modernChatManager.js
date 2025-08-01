/**
 * Modern Chat Manager - Clean, Best-in-Class AI Chat Interface
 * 
 * Features:
 * - Model selection from predefined chat models
 * - Persistent chat history with session management
 * - Active chat maintenance across devices
 * - Archive functionality for completed conversations
 * - Modern prompting system integration
 * - Clickable links to knowledge base items and synthesis documents
 * - LLM speed metrics and performance indicators
 * - Glass morphism design with responsive layout
 */

class ModernChatManager extends BaseManager {
    constructor(options = {}) {
        super({
            enableLogging: true,
            autoInit: false,
            componentName: 'ModernChatManager',
            ...options
        });
        
        // Chat state
        this.currentSessionId = null;
        this.sessions = new Map();
        this.availableModels = [];
        this.selectedModel = null;
        this.isTyping = false;
        this.messageQueue = [];
        
        // Performance tracking
        this.performanceMetrics = {
            lastResponseTime: null,
            averageResponseTime: null,
            totalMessages: 0,
            totalTokens: 0
        };
        
        // Auto-save timer
        this.autoSaveTimer = null;
        this.autoSaveInterval = 30000; // 30 seconds
    }
    
    async initializeElements() {
        // Main chat container
        this.elements.container = document.getElementById('main-content');
        if (!this.elements.container) {
            throw new Error('Main content container not found');
        }
        
        // Create the chat interface
        await this.createChatInterface();
        
        // Cache all interactive elements
        this.elements.sessionsList = document.getElementById('chat-sessions-list');
        this.elements.newChatBtn = document.getElementById('new-chat-btn');
        this.elements.sessionSearch = document.getElementById('session-search');
        this.elements.modelSelector = document.getElementById('model-selector');
        this.elements.chatMessages = document.getElementById('chat-messages');
        this.elements.chatInput = document.getElementById('chat-input');
        this.elements.sendBtn = document.getElementById('send-btn');
        this.elements.typingIndicator = document.getElementById('typing-indicator');
        this.elements.sessionTitle = document.getElementById('session-title');
        this.elements.messageCount = document.getElementById('message-count');
        this.elements.performancePanel = document.getElementById('performance-panel');
        
        // Validate required elements
        const requiredElements = ['sessionsList', 'chatMessages', 'chatInput', 'sendBtn'];
        for (const elementName of requiredElements) {
            if (!this.elements[elementName]) {
                throw new Error(`Required element ${elementName} not found`);
            }
        }
    }
    
    async setupEventListeners() {
        this.eventService.setupStandardListeners(this, {
            buttons: [
                {
                    selector: this.elements.newChatBtn,
                    handler: this.handleNewChat,
                    debounce: 300
                },
                {
                    selector: this.elements.sendBtn,
                    handler: this.handleSendMessage,
                    debounce: 500,
                    condition: () => !this.isTyping && this.elements.chatInput.value.trim()
                }
            ],
            
            inputs: [
                {
                    selector: this.elements.sessionSearch,
                    events: ['input'],
                    handler: this.handleSessionSearch,
                    debounce: 200
                },
                {
                    selector: this.elements.modelSelector,
                    events: ['change'],
                    handler: this.handleModelChange
                },
                {
                    selector: this.elements.chatInput,
                    events: ['input'],
                    handler: this.handleInputChange,
                    debounce: 100
                }
            ],
            
            keyboard: [
                {
                    key: 'Enter',
                    handler: this.handleEnterKey,
                    condition: (e) => e.target === this.elements.chatInput
                },
                {
                    key: 'Enter',
                    ctrlKey: true,
                    handler: this.handleSendMessage,
                    condition: (e) => e.target === this.elements.chatInput
                }
            ],
            
            delegated: [
                {
                    container: this.elements.sessionsList,
                    selector: '.session-item',
                    event: 'click',
                    handler: this.handleSessionSelect
                },
                {
                    container: this.elements.sessionsList,
                    selector: '.archive-btn',
                    event: 'click',
                    handler: this.handleArchiveSession
                },
                {
                    container: this.elements.sessionsList,
                    selector: '.delete-btn',
                    event: 'click',
                    handler: this.handleDeleteSession
                },
                {
                    container: this.elements.chatMessages,
                    selector: '.kb-link',
                    event: 'click',
                    handler: this.handleKnowledgeBaseLink
                },
                {
                    container: this.elements.chatMessages,
                    selector: '.synthesis-link',
                    event: 'click',
                    handler: this.handleSynthesisLink
                },
                {
                    container: this.elements.chatMessages,
                    selector: '.performance-toggle',
                    event: 'click',
                    handler: this.handlePerformanceToggle
                }
            ]
        });
    }
    
    async loadInitialData() {
        try {
            // Load available models
            await this.loadAvailableModels();
            
            // Load existing chat sessions
            await this.loadChatSessions();
            
            // Restore active session or create new one
            await this.restoreOrCreateSession();
            
            this.setState({ 
                initialized: true,
                loading: false 
            });
            
        } catch (error) {
            this.setError(error, 'loading initial chat data');
        }
    }
    
    async createChatInterface() {
        this.elements.container.innerHTML = `
            <div class="modern-chat-container glass-panel-v3 animate-glass-fade-in">
                <!-- Chat Sessions Sidebar -->
                <aside class="chat-sidebar glass-panel-v3--secondary">
                    <div class="sidebar-header">
                        <div class="sidebar-title">
                            <i class="fas fa-comments"></i>
                            <span>Conversations</span>
                        </div>
                        <button id="new-chat-btn" class="glass-button glass-button--small" title="New Chat">
                            <i class="fas fa-plus"></i>
                        </button>
                    </div>
                    
                    <div class="sidebar-search">
                        <div class="search-container">
                            <i class="fas fa-search"></i>
                            <input 
                                type="text" 
                                id="session-search" 
                                placeholder="Search conversations..."
                                class="glass-input"
                            >
                        </div>
                    </div>
                    
                    <div class="sessions-container">
                        <div id="chat-sessions-list" class="sessions-list">
                            <div class="loading-state">
                                <div class="loading-spinner"></div>
                                <span>Loading conversations...</span>
                            </div>
                        </div>
                    </div>
                    
                    <div class="sidebar-footer">
                        <div class="model-selection">
                            <label class="model-label">
                                <i class="fas fa-brain"></i>
                                <span>AI Model</span>
                            </label>
                            <select id="model-selector" class="glass-select">
                                <option value="">Loading models...</option>
                            </select>
                        </div>
                    </div>
                </aside>

                <!-- Main Chat Area -->
                <main class="chat-main">
                    <!-- Chat Header -->
                    <header class="chat-header">
                        <div class="session-info">
                            <h1 id="session-title" class="session-title">New Conversation</h1>
                            <div class="session-metadata">
                                <span id="message-count" class="message-count">0 messages</span>
                                <span class="separator">•</span>
                                <span id="session-time" class="session-time">--</span>
                                <button id="performance-panel" class="performance-toggle glass-button glass-button--small" title="Performance Metrics">
                                    <i class="fas fa-chart-line"></i>
                                </button>
                            </div>
                        </div>
                        <div class="header-actions">
                            <button id="archive-session-btn" class="glass-button glass-button--small" title="Archive Session">
                                <i class="fas fa-archive"></i>
                            </button>
                            <button id="export-session-btn" class="glass-button glass-button--small" title="Export Session">
                                <i class="fas fa-download"></i>
                            </button>
                        </div>
                    </header>

                    <!-- Chat Messages -->
                    <div class="chat-messages-container">
                        <div id="chat-messages" class="chat-messages">
                            ${this.createWelcomeMessage()}
                        </div>
                        
                        <div id="typing-indicator" class="typing-indicator hidden">
                            <div class="typing-avatar">
                                <i class="fas fa-robot"></i>
                            </div>
                            <div class="typing-content">
                                <div class="typing-text">AI is thinking...</div>
                                <div class="typing-dots">
                                    <span></span>
                                    <span></span>
                                    <span></span>
                                </div>
                            </div>
                        </div>
                    </div>

                    <!-- Chat Input -->
                    <div class="chat-input-area">
                        <div class="input-container">
                            <div class="input-wrapper">
                                <textarea 
                                    id="chat-input" 
                                    class="chat-input glass-input"
                                    placeholder="Ask me anything about your knowledge base..." 
                                    rows="1"
                                    maxlength="4000"
                                ></textarea>
                                
                                <div class="input-actions">
                                    <button id="send-btn" class="send-btn glass-button" disabled title="Send Message">
                                        <i class="fas fa-paper-plane"></i>
                                    </button>
                                </div>
                            </div>
                            
                            <div class="input-footer">
                                <div class="input-info">
                                    <span id="char-count" class="char-count">0/4000</span>
                                    <span class="input-tip">Press Enter to send, Shift+Enter for new line</span>
                                </div>
                            </div>
                        </div>
                    </div>
                </main>
            </div>
            
            <!-- Performance Metrics Panel -->
            <div id="performance-metrics-panel" class="performance-panel glass-panel-v3 hidden">
                <div class="panel-header">
                    <h3>Performance Metrics</h3>
                    <button class="close-btn">
                        <i class="fas fa-times"></i>
                    </button>
                </div>
                <div class="metrics-grid">
                    <div class="metric-item">
                        <div class="metric-label">Last Response</div>
                        <div class="metric-value" id="last-response-time">--</div>
                    </div>
                    <div class="metric-item">
                        <div class="metric-label">Average Response</div>
                        <div class="metric-value" id="avg-response-time">--</div>
                    </div>
                    <div class="metric-item">
                        <div class="metric-label">Total Messages</div>
                        <div class="metric-value" id="total-messages">--</div>
                    </div>
                    <div class="metric-item">
                        <div class="metric-label">Tokens Used</div>
                        <div class="metric-value" id="total-tokens">--</div>
                    </div>
                </div>
            </div>
        `;
    }
    
    createWelcomeMessage() {
        return `
            <div class="welcome-message">
                <div class="welcome-avatar">
                    <i class="fas fa-robot"></i>
                </div>
                <div class="welcome-content">
                    <h2>Welcome to Knowledge Base Chat</h2>
                    <p>I'm your AI assistant with access to your knowledge base. I can help you find information, analyze documents, and provide insights based on your content.</p>
                    
                    <div class="welcome-suggestions">
                        <h4>Try asking me:</h4>
                        <div class="suggestion-grid">
                            <button class="suggestion-btn" data-prompt="What are the main categories in my knowledge base?">
                                <i class="fas fa-folder"></i>
                                <span>Explore Categories</span>
                            </button>
                            <button class="suggestion-btn" data-prompt="Summarize recent developments in AI">
                                <i class="fas fa-chart-line"></i>
                                <span>Summarize Topics</span>
                            </button>
                            <button class="suggestion-btn" data-prompt="Find examples of machine learning concepts">
                                <i class="fas fa-search"></i>
                                <span>Find Examples</span>
                            </button>
                            <button class="suggestion-btn" data-prompt="What insights can you provide about my content?">
                                <i class="fas fa-lightbulb"></i>
                                <span>Get Insights</span>
                            </button>
                        </div>
                    </div>
                </div>
            </div>
        `;
    }
    
    async loadAvailableModels() {
        try {
            // CRITICAL FIX: Use the correct API endpoint and handle different response formats
            const response = await this.apiCall('/api/chat/models', {
                errorMessage: 'Failed to load chat models',
                cache: true,
                cacheTTL: 300000 // 5 minutes
            });
            
            // Handle different response formats
            let models = [];
            if (response && Array.isArray(response)) {
                models = response;
            } else if (response && response.models && Array.isArray(response.models)) {
                models = response.models;
            } else if (response && response.data && Array.isArray(response.data)) {
                models = response.data;
            }
            
            if (models.length > 0) {
                this.availableModels = models;
            } else {
                // Fallback to common Ollama models if API doesn't return any
                this.availableModels = [
                    { id: 'llama3.2:latest', name: 'Llama 3.2' },
                    { id: 'llama3.1:latest', name: 'Llama 3.1' },
                    { id: 'mistral:latest', name: 'Mistral' },
                    { id: 'codellama:latest', name: 'Code Llama' }
                ];
            }
            
            this.updateModelSelector();
            
            // Select first model if none selected
            if (!this.selectedModel && this.availableModels.length > 0) {
                this.selectedModel = this.availableModels[0].id;
                if (this.elements.modelSelector) {
                    this.elements.modelSelector.value = this.selectedModel;
                }
            }
            
            this.log(`Loaded ${this.availableModels.length} available models`);
            
        } catch (error) {
            this.logError('Failed to load available models:', error);
            // Fallback to common Ollama models
            this.availableModels = [
                { id: 'llama3.2:latest', name: 'Llama 3.2' },
                { id: 'llama3.1:latest', name: 'Llama 3.1' },
                { id: 'mistral:latest', name: 'Mistral' }
            ];
            this.selectedModel = 'llama3.2:latest';
            this.updateModelSelector();
        }
    }
    
    updateModelSelector() {
        if (!this.elements.modelSelector) return;
        
        const options = this.availableModels.map(model => 
            `<option value="${model.id}">${model.name}</option>`
        ).join('');
        
        this.elements.modelSelector.innerHTML = options;
    }
    
    async loadChatSessions() {
        try {
            const sessions = await this.apiCall('/api/chat/sessions', {
                errorMessage: 'Failed to load chat sessions',
                cache: false
            });
            
            this.sessions.clear();
            sessions.forEach(session => {
                this.sessions.set(session.session_id, session);
            });
            
            this.updateSessionsList();
            
        } catch (error) {
            this.logError('Failed to load chat sessions:', error);
            this.updateSessionsList([]); // Show empty state
        }
    }
    
    updateSessionsList(filteredSessions = null) {
        if (!this.elements.sessionsList) return;
        
        const sessionsToShow = filteredSessions || Array.from(this.sessions.values());
        
        if (sessionsToShow.length === 0) {
            this.elements.sessionsList.innerHTML = `
                <div class="empty-state">
                    <i class="fas fa-comments"></i>
                    <span>No conversations yet</span>
                    <p>Start a new chat to begin</p>
                </div>
            `;
            return;
        }
        
        const sessionsHTML = sessionsToShow.map(session => this.createSessionItem(session)).join('');
        this.elements.sessionsList.innerHTML = sessionsHTML;
    }
    
    createSessionItem(session) {
        const isActive = session.session_id === this.currentSessionId;
        const lastMessage = session.messages && session.messages.length > 0 
            ? session.messages[session.messages.length - 1].content.substring(0, 100) + '...'
            : 'No messages yet';
        
        return `
            <div class="session-item ${isActive ? 'active' : ''}" data-session-id="${session.session_id}">
                <div class="session-content">
                    <div class="session-title">${session.title || 'New Conversation'}</div>
                    <div class="session-preview">${lastMessage}</div>
                    <div class="session-metadata">
                        <span class="session-time">${this.formatSessionTime(session.created_at)}</span>
                        <span class="message-count">${session.message_count || 0} messages</span>
                    </div>
                </div>
                <div class="session-actions">
                    <button class="archive-btn glass-button glass-button--small" title="Archive">
                        <i class="fas fa-archive"></i>
                    </button>
                    <button class="delete-btn glass-button glass-button--small danger" title="Delete">
                        <i class="fas fa-trash"></i>
                    </button>
                </div>
            </div>
        `;
    }
    
    formatSessionTime(timestamp) {
        const date = new Date(timestamp);
        const now = new Date();
        const diffMs = now - date;
        const diffHours = diffMs / (1000 * 60 * 60);
        const diffDays = diffMs / (1000 * 60 * 60 * 24);
        
        if (diffHours < 1) {
            return 'Just now';
        } else if (diffHours < 24) {
            return `${Math.floor(diffHours)}h ago`;
        } else if (diffDays < 7) {
            return `${Math.floor(diffDays)}d ago`;
        } else {
            return date.toLocaleDateString();
        }
    }
    
    // Event Handlers
    handleNewChat = async () => {
        try {
            const session = await this.apiCall('/api/chat/sessions', {
                method: 'POST',
                body: {
                    title: 'New Conversation',
                    model: this.selectedModel
                },
                errorMessage: 'Failed to create new chat session'
            });
            
            this.sessions.set(session.session_id, session);
            this.currentSessionId = session.session_id;
            
            this.updateSessionsList();
            this.clearChatMessages();
            this.showWelcomeMessage();
            this.updateSessionInfo();
            
            this.log('New chat session created:', session.session_id);
            
        } catch (error) {
            this.setError(error, 'creating new chat session');
        }
    }
    
    handleSessionSelect = async (e) => {
        const sessionItem = e.target.closest('.session-item');
        if (!sessionItem) return;
        
        const sessionId = sessionItem.dataset.sessionId;
        await this.switchToSession(sessionId);
    }
    
    async switchToSession(sessionId) {
        try {
            const session = await this.apiCall(`/api/chat/sessions/${sessionId}`, {
                errorMessage: 'Failed to load chat session'
            });
            
            this.currentSessionId = sessionId;
            this.sessions.set(sessionId, session);
            
            this.loadSessionMessages(session);
            this.updateSessionsList();
            this.updateSessionInfo();
            
            this.log('Switched to session:', sessionId);
            
        } catch (error) {
            this.setError(error, 'switching to chat session');
        }
    }
    
    loadSessionMessages(session) {
        if (!session.messages || session.messages.length === 0) {
            this.showWelcomeMessage();
            return;
        }
        
        const messagesHTML = session.messages.map(message => this.createMessageHTML(message)).join('');
        this.elements.chatMessages.innerHTML = messagesHTML;
        this.scrollToBottom();
    }
    
    createMessageHTML(message) {
        const isUser = message.role === 'user';
        const timestamp = new Date(message.created_at).toLocaleTimeString();
        
        let content = message.content;
        
        // Process links to knowledge base items and synthesis documents
        content = this.processContentLinks(content);
        
        // Add performance metrics for assistant messages
        let performanceHTML = '';
        if (!isUser && message.performance_metrics) {
            performanceHTML = this.createPerformanceMetricsHTML(message.performance_metrics);
        }
        
        return `
            <div class="message ${isUser ? 'user-message' : 'assistant-message'}">
                <div class="message-avatar">
                    <i class="fas fa-${isUser ? 'user' : 'robot'}"></i>
                </div>
                <div class="message-content">
                    <div class="message-header">
                        <span class="message-sender">${isUser ? 'You' : 'AI Assistant'}</span>
                        <span class="message-timestamp">${timestamp}</span>
                    </div>
                    <div class="message-text">${content}</div>
                    ${performanceHTML}
                </div>
            </div>
        `;
    }
    
    processContentLinks(content) {
        // Convert knowledge base item references to clickable links
        content = content.replace(
            /\[KB:([^\]]+)\]/g,
            '<a href="#" class="kb-link" data-kb-item="$1">$1</a>'
        );
        
        // Convert synthesis document references to clickable links
        content = content.replace(
            /\[SYNTHESIS:([^\]]+)\]/g,
            '<a href="#" class="synthesis-link" data-synthesis="$1">$1</a>'
        );
        
        return content;
    }
    
    createPerformanceMetricsHTML(metrics) {
        return `
            <div class="message-performance">
                <button class="performance-toggle" title="View Performance Metrics">
                    <i class="fas fa-chart-bar"></i>
                    <span>${this.durationFormatter.format(metrics.response_time || 0)}</span>
                </button>
                <div class="performance-details hidden">
                    <div class="metric">
                        <span class="label">Response Time:</span>
                        <span class="value">${this.durationFormatter.format(metrics.response_time || 0)}</span>
                    </div>
                    <div class="metric">
                        <span class="label">Tokens:</span>
                        <span class="value">${metrics.tokens_used || 0}</span>
                    </div>
                    <div class="metric">
                        <span class="label">Sources:</span>
                        <span class="value">${metrics.sources_count || 0}</span>
                    </div>
                </div>
            </div>
        `;
    }
    
    handleSendMessage = async () => {
        const message = this.elements.chatInput.value.trim();
        if (!message || this.isTyping) return;
        
        if (!this.currentSessionId) {
            await this.handleNewChat();
        }
        
        if (!this.selectedModel) {
            this.showError('Please select an AI model first');
            return;
        }
        
        try {
            // Add user message to UI immediately
            this.addMessageToUI({
                role: 'user',
                content: message,
                created_at: new Date().toISOString()
            });
            
            // Clear input and show typing indicator
            this.elements.chatInput.value = '';
            this.updateCharCount();
            this.showTypingIndicator();
            this.isTyping = true;
            
            const startTime = Date.now();
            
            // Send message to API
            const response = await this.apiCall('/api/chat/enhanced', {
                method: 'POST',
                body: {
                    message: message,
                    session_id: this.currentSessionId,
                    model: this.selectedModel
                },
                errorMessage: 'Failed to send message',
                timeout: 60000 // 1 minute timeout
            });
            
            const responseTime = Date.now() - startTime;
            
            // Add assistant response to UI
            this.addMessageToUI({
                role: 'assistant',
                content: response.response,
                created_at: new Date().toISOString(),
                performance_metrics: {
                    response_time: responseTime,
                    tokens_used: response.context_stats?.total_tokens || 0,
                    sources_count: response.sources?.length || 0
                }
            });
            
            // Update performance metrics
            this.updatePerformanceMetrics(responseTime, response.context_stats?.total_tokens || 0);
            
            // Update session info
            this.updateSessionInfo();
            
        } catch (error) {
            this.setError(error, 'sending chat message');
            this.addErrorMessageToUI('Sorry, I encountered an error processing your message. Please try again.');
        } finally {
            this.hideTypingIndicator();
            this.isTyping = false;
        }
    }
    
    addMessageToUI(message) {
        const messageHTML = this.createMessageHTML(message);
        
        // Remove welcome message if present
        const welcomeMessage = this.elements.chatMessages.querySelector('.welcome-message');
        if (welcomeMessage) {
            welcomeMessage.remove();
        }
        
        this.elements.chatMessages.insertAdjacentHTML('beforeend', messageHTML);
        this.scrollToBottom();
    }
    
    addErrorMessageToUI(errorMessage) {
        const errorHTML = `
            <div class="message assistant-message error-message">
                <div class="message-avatar">
                    <i class="fas fa-exclamation-triangle"></i>
                </div>
                <div class="message-content">
                    <div class="message-header">
                        <span class="message-sender">System</span>
                        <span class="message-timestamp">${new Date().toLocaleTimeString()}</span>
                    </div>
                    <div class="message-text">${errorMessage}</div>
                </div>
            </div>
        `;
        
        this.elements.chatMessages.insertAdjacentHTML('beforeend', errorHTML);
        this.scrollToBottom();
    }
    
    showTypingIndicator() {
        if (this.elements.typingIndicator) {
            this.elements.typingIndicator.classList.remove('hidden');
            this.scrollToBottom();
        }
    }
    
    hideTypingIndicator() {
        if (this.elements.typingIndicator) {
            this.elements.typingIndicator.classList.add('hidden');
        }
    }
    
    scrollToBottom() {
        if (this.elements.chatMessages) {
            this.elements.chatMessages.scrollTop = this.elements.chatMessages.scrollHeight;
        }
    }
    
    showWelcomeMessage() {
        this.elements.chatMessages.innerHTML = this.createWelcomeMessage();
    }
    
    clearChatMessages() {
        this.elements.chatMessages.innerHTML = '';
    }
    
    updateSessionInfo() {
        if (this.currentSessionId && this.sessions.has(this.currentSessionId)) {
            const session = this.sessions.get(this.currentSessionId);
            
            if (this.elements.sessionTitle) {
                this.elements.sessionTitle.textContent = session.title || 'New Conversation';
            }
            
            if (this.elements.messageCount) {
                this.elements.messageCount.textContent = `${session.message_count || 0} messages`;
            }
            
            if (this.elements.sessionTime) {
                this.elements.sessionTime.textContent = this.formatSessionTime(session.created_at);
            }
        }
    }
    
    updatePerformanceMetrics(responseTime, tokens) {
        this.performanceMetrics.totalMessages++;
        this.performanceMetrics.totalTokens += tokens;
        this.performanceMetrics.lastResponseTime = responseTime;
        
        // Calculate average response time
        if (this.performanceMetrics.averageResponseTime === null) {
            this.performanceMetrics.averageResponseTime = responseTime;
        } else {
            this.performanceMetrics.averageResponseTime = 
                (this.performanceMetrics.averageResponseTime + responseTime) / 2;
        }
        
        // Update performance panel if visible
        this.updatePerformancePanel();
    }
    
    updatePerformancePanel() {
        const panel = document.getElementById('performance-metrics-panel');
        if (!panel || panel.classList.contains('hidden')) return;
        
        const lastResponseEl = document.getElementById('last-response-time');
        const avgResponseEl = document.getElementById('avg-response-time');
        const totalMessagesEl = document.getElementById('total-messages');
        const totalTokensEl = document.getElementById('total-tokens');
        
        if (lastResponseEl) {
            lastResponseEl.textContent = this.durationFormatter.format(this.performanceMetrics.lastResponseTime || 0);
        }
        
        if (avgResponseEl) {
            avgResponseEl.textContent = this.durationFormatter.format(this.performanceMetrics.averageResponseTime || 0);
        }
        
        if (totalMessagesEl) {
            totalMessagesEl.textContent = this.performanceMetrics.totalMessages.toString();
        }
        
        if (totalTokensEl) {
            totalTokensEl.textContent = this.performanceMetrics.totalTokens.toString();
        }
    }
    
    // Additional event handlers
    handleInputChange = () => {
        this.updateCharCount();
        this.updateSendButtonState();
    }
    
    updateCharCount() {
        const charCountEl = document.getElementById('char-count');
        if (charCountEl && this.elements.chatInput) {
            const count = this.elements.chatInput.value.length;
            charCountEl.textContent = `${count}/4000`;
        }
    }
    
    updateSendButtonState() {
        if (this.elements.sendBtn && this.elements.chatInput) {
            const hasText = this.elements.chatInput.value.trim().length > 0;
            this.elements.sendBtn.disabled = !hasText || this.isTyping;
        }
    }
    
    handleEnterKey = (e) => {
        if (e.shiftKey) {
            // Allow new line with Shift+Enter
            return;
        }
        
        e.preventDefault();
        this.handleSendMessage();
    }
    
    handleModelChange = () => {
        this.selectedModel = this.elements.modelSelector.value;
        this.log('Model changed to:', this.selectedModel);
    }
    
    handleSessionSearch = (e) => {
        const query = e.target.value.toLowerCase();
        const allSessions = Array.from(this.sessions.values());
        
        if (!query) {
            this.updateSessionsList();
            return;
        }
        
        const filteredSessions = allSessions.filter(session => 
            (session.title || '').toLowerCase().includes(query) ||
            (session.messages && session.messages.some(msg => 
                msg.content.toLowerCase().includes(query)
            ))
        );
        
        this.updateSessionsList(filteredSessions);
    }
    
    handleKnowledgeBaseLink = async (e) => {
        e.preventDefault();
        const kbItem = e.target.dataset.kbItem;
        
        // Navigate to knowledge base page with the specific item
        window.location.hash = `#knowledge-base?item=${encodeURIComponent(kbItem)}`;
    }
    
    handleSynthesisLink = async (e) => {
        e.preventDefault();
        const synthesis = e.target.dataset.synthesis;
        
        // Navigate to synthesis page with the specific document
        window.location.hash = `#synthesis?doc=${encodeURIComponent(synthesis)}`;
    }
    
    handlePerformanceToggle = (e) => {
        const panel = document.getElementById('performance-metrics-panel');
        if (panel) {
            panel.classList.toggle('hidden');
            this.updatePerformancePanel();
        }
    }
    
    async restoreOrCreateSession() {
        // Try to restore the last active session
        const sessions = Array.from(this.sessions.values());
        const activeSession = sessions.find(s => !s.is_archived) || sessions[0];
        
        if (activeSession) {
            await this.switchToSession(activeSession.session_id);
        } else {
            await this.handleNewChat();
        }
    }
    
    cleanup() {
        // Clear auto-save timer
        if (this.autoSaveTimer) {
            clearInterval(this.autoSaveTimer);
        }
        
        // Use CleanupService for comprehensive cleanup
        this.cleanupService.cleanup(this);
    }
}

// Export for use in other modules
window.ModernChatManager = ModernChatManager;