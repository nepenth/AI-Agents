/**
 * Modern Chat Manager - Grok-Inspired AI Chat Interface
 *
 * Features:
 * - Grok-like modern design with intelligent space utilization
 * - Persistent chat state with database storage
 * - Active chat always maintained and restored on page load
 * - Historical chat archive system
 * - Model selection from configured chat models
 * - Knowledge base integration with embeddings
 * - Real-time typing indicators and performance metrics
 * - Responsive design optimized for all screen sizes
 * - Apple-quality UX with smooth animations
 */
class ModernChatManager extends BaseManager {
    constructor(options = {}) {
        super({
            enableLogging: true,
            autoInit: false,
            componentName: 'ModernChatManager',
            ...options
        });
        // Chat state management
        this.currentSessionId = null;
        this.activeSession = null;
        this.sessions = new Map();
        this.archivedSessions = new Map();
        this.availableModels = [];
        this.selectedModel = null;
        this.isTyping = false;
        this.messageQueue = [];
        // UI state
        this.sidebarCollapsed = false;
        this.currentView = 'active'; // 'active' or 'history'
        this.searchQuery = '';
        // Performance tracking
        this.performanceMetrics = {
            lastResponseTime: null,
            averageResponseTime: null,
            totalMessages: 0,
            totalTokens: 0,
            sessionsCreated: 0
        };
        // Auto-save and state persistence
        this.autoSaveTimer = null;
        this.autoSaveInterval = 15000; // 15 seconds for better UX
        this.stateRestored = false;
        // Responsive design breakpoints
        this.breakpoints = {
            mobile: 768,
            tablet: 1024,
            desktop: 1200
        };
        // Message rendering optimization
        this.messageRenderer = new MessageRenderer(this);
        this.virtualScroll = null;
        // Duration formatter
        this.durationFormatter = {
            format: (ms) => {
                if (ms === null || ms === 0) return '--';
                if (ms < 1000) return `${ms} ms`;
                return `${(ms / 1000).toFixed(2)} s`;
            }
        };
    }
    async initializeElements() {
        // Main chat container
        this.elements.container = document.getElementById('main-content');
        if (!this.elements.container) {
            throw new Error('Main content container not found');
        }
        // Create the modern chat interface
        await this.createModernChatInterface();
        // Cache all interactive elements
        this.cacheElements();
        // Setup responsive design
        this.setupResponsiveDesign();
        // Initialize virtual scrolling for performance
        this.initializeVirtualScroll();
    }
    cacheElements() {
        // Sidebar elements
        this.elements.sidebar = document.getElementById('chat-sidebar');
        this.elements.sidebarToggle = document.getElementById('sidebar-toggle');
        this.elements.newChatBtn = document.getElementById('new-chat-btn');
        this.elements.viewToggle = document.getElementById('view-toggle');
        this.elements.sessionSearch = document.getElementById('session-search');
        this.elements.searchClear = document.getElementById('search-clear');
        this.elements.sessionsList = document.getElementById('sessions-list');
        this.elements.sessionsTitle = document.getElementById('sessions-title');
        this.elements.sessionsCount = document.getElementById('sessions-count');
        this.elements.modelSelector = document.getElementById('model-selector');
        // Main chat elements
        this.elements.chatHeader = document.getElementById('chat-header');
        this.elements.sessionTitle = document.getElementById('session-title');
        this.elements.sessionMeta = document.getElementById('session-meta');
        this.elements.messageCount = document.getElementById('message-count');
        this.elements.sessionTime = document.getElementById('session-time');
        this.elements.modelDisplay = document.getElementById('model-display');
        this.elements.chatMessages = document.getElementById('chat-messages');
        this.elements.typingIndicator = document.getElementById('typing-indicator');
        this.elements.chatInput = document.getElementById('chat-input');
        this.elements.sendBtn = document.getElementById('send-btn');
        this.elements.attachBtn = document.getElementById('attach-btn');
        this.elements.voiceBtn = document.getElementById('voice-btn');
        this.elements.inputActions = document.getElementById('input-actions');
        // Performance and status elements
        this.elements.performancePanel = document.getElementById('performance-panel');
        this.elements.performanceToggle = document.getElementById('performance-toggle');
        this.elements.performanceClose = document.getElementById('performance-close');
        this.elements.connectionStatus = document.getElementById('connection-status');
        // Header actions
        this.elements.archiveSessionBtn = document.getElementById('archive-session-btn');
        this.elements.exportSessionBtn = document.getElementById('export-session-btn');
        // Validate critical elements
        const requiredElements = ['sessionsList', 'chatMessages', 'chatInput', 'sendBtn'];
        for (const elementName of requiredElements) {
            if (!this.elements[elementName]) {
                throw new Error(`Required element ${elementName} not found`);
            }
        }
    }
    async setupEventListeners() {
        EventListenerService.setupStandardListeners(this, {
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
                },
                {
                    selector: this.elements.sidebarToggle,
                    handler: this.handleSidebarToggle,
                    debounce: 200
                },
                {
                    selector: this.elements.viewToggle,
                    handler: this.handleViewToggle,
                    debounce: 300
                },
                {
                    selector: this.elements.searchClear,
                    handler: this.handleSearchClear,
                    debounce: 0
                },
                {
                    selector: this.elements.performanceToggle,
                    handler: this.handlePerformanceToggle,
                    debounce: 200
                },
                {
                    selector: this.elements.performanceClose,
                    handler: this.handlePerformanceToggle,
                    debounce: 200
                },
                {
                    selector: this.elements.archiveSessionBtn,
                    handler: this.handleArchiveCurrentSession,
                    debounce: 300
                },
                {
                    selector: this.elements.exportSessionBtn,
                    handler: this.handleExportSession,
                    debounce: 300
                },
                {
                    selector: this.elements.attachBtn,
                    handler: this.handleAttachFile,
                    debounce: 300
                },
                {
                    selector: this.elements.voiceBtn,
                    handler: this.handleVoiceInput,
                    debounce: 300
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
                    events: ['input', 'paste'],
                    handler: this.handleInputChange,
                    debounce: 100
                }
            ],
            keyboard: [
                {
                    key: 'Enter',
                    handler: this.handleEnterKey,
                    condition: (e) => e.target === this.elements.chatInput && !e.shiftKey
                },
                {
                    key: 'Enter',
                    shiftKey: true,
                    handler: this.handleShiftEnter,
                    condition: (e) => e.target === this.elements.chatInput
                },
                {
                    key: 'Escape',
                    handler: this.handleEscapeKey
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
                    selector: '.restore-btn',
                    event: 'click',
                    handler: this.handleRestoreSession
                },
                {
                    container: this.elements.sessionsList,
                    selector: '.delete-btn',
                    event: 'click',
                    handler: this.handleDeleteSession
                },
                {
                    container: this.elements.sessionsList,
                    selector: '.empty-action-btn',
                    event: 'click',
                    handler: this.handleNewChat
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
                    selector: '.message-action',
                    event: 'click',
                    handler: this.handleMessageAction
                },
                {
                    container: this.elements.chatMessages,
                    selector: '.suggestion-card',
                    event: 'click',
                    handler: this.handleSuggestionClick
                },
                {
                    container: this.elements.chatMessages,
                    selector: '.performance-toggle',
                    event: 'click',
                    handler: this.handlePerformanceDetailsToggle
                },
                {
                    container: this.elements.chatMessages,
                    selector: '.sources-toggle',
                    event: 'click',
                    handler: this.handleSourcesToggle
                }
            ],
            customEvents: [
                {
                    target: window,
                    event: 'resize',
                    handler: this.handleWindowResize,
                    throttle: 100
                },
                {
                    event: 'chat_session_updated',
                    handler: (e) => this.handleSessionUpdate(e.detail)
                },
                {
                    event: 'model_changed',
                    handler: (e) => this.handleModelUpdate(e.detail)
                }
            ]
        });
    }
    async loadInitialData() {
        try {
            this.setState({ loading: true });
            // Load available models from config
            await this.loadAvailableModels();
            // Restore active session state
            await this.restoreActiveSession();
            // Load session history
            await this.loadSessionHistory();
            // Setup auto-save
            this.setupAutoSave();
            this.setState({
                initialized: true,
                loading: false
            });
            this.log('Modern chat manager initialized successfully');
        } catch (error) {
            this.setError(error, 'loading initial chat data');
        }
    }
    async createModernChatInterface() {
        this.elements.container.innerHTML = `
            <div class="modern-chat-layout" id="modern-chat-layout">
                <!-- Collapsible Sidebar -->
                <aside class="chat-sidebar glass-panel-v3--secondary" id="chat-sidebar">
                    <div class="sidebar-header">
                        <div class="sidebar-brand">
                            <i class="fas fa-comments"></i>
                            <span class="brand-text">Chat</span>
                        </div>
                        <div class="sidebar-controls">
                            <button id="view-toggle" class="view-toggle-btn" title="Toggle View">
                                <i class="fas fa-history"></i>
                            </button>
                            <button id="new-chat-btn" class="new-chat-btn" title="New Chat">
                                <i class="fas fa-plus"></i>
                            </button>
                        </div>
                    </div>
                  
                    <div class="sidebar-search">
                        <div class="search-container">
                            <i class="fas fa-search search-icon"></i>
                            <input
                                type="text"
                                id="session-search"
                                placeholder="Search conversations..."
                                class="search-input"
                            >
                            <button class="search-clear" id="search-clear" style="display: none;">
                                <i class="fas fa-times"></i>
                            </button>
                        </div>
                    </div>
                  
                    <div class="sessions-container">
                        <div class="sessions-header">
                            <span class="sessions-title" id="sessions-title">Active Chats</span>
                            <span class="sessions-count" id="sessions-count">0</span>
                        </div>
                        <div id="sessions-list" class="sessions-list">
                            <div class="loading-sessions">
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
                            <select id="model-selector" class="model-select">
                                <option value="">Loading models...</option>
                            </select>
                        </div>
                        <div class="connection-status" id="connection-status">
                            <div class="status-indicator online"></div>
                            <span class="status-text">Connected</span>
                        </div>
                    </div>
                </aside>
                <!-- Main Chat Area -->
                <main class="chat-main">
                    <!-- Mobile Header -->
                    <header class="chat-header mobile-only" id="chat-header-mobile">
                        <button id="sidebar-toggle" class="sidebar-toggle-btn">
                            <i class="fas fa-bars"></i>
                        </button>
                        <div class="header-title">
                            <span id="mobile-session-title">New Chat</span>
                        </div>
                        <div class="header-actions">
                            <button class="header-action-btn" id="mobile-menu-btn">
                                <i class="fas fa-ellipsis-v"></i>
                            </button>
                        </div>
                    </header>
                    <!-- Desktop Chat Header -->
                    <header class="chat-header desktop-only" id="chat-header">
                        <div class="session-info">
                            <h1 id="session-title" class="session-title">New Conversation</h1>
                            <div class="session-metadata" id="session-meta">
                                <span id="message-count" class="message-count">0 messages</span>
                                <span class="separator">•</span>
                                <span id="session-time" class="session-time">--</span>
                                <span class="separator">•</span>
                                <span id="model-display" class="model-display">--</span>
                            </div>
                        </div>
                        <div class="header-actions">
                            <button id="performance-toggle" class="header-action-btn" title="Performance Metrics">
                                <i class="fas fa-chart-line"></i>
                            </button>
                            <button id="archive-session-btn" class="header-action-btn" title="Archive Session">
                                <i class="fas fa-archive"></i>
                            </button>
                            <button id="export-session-btn" class="header-action-btn" title="Export Session">
                                <i class="fas fa-download"></i>
                            </button>
                        </div>
                    </header>
                    <!-- Chat Messages Area -->
                    <div class="chat-messages-container">
                        <div id="chat-messages" class="chat-messages">
                            ${this.createWelcomeMessage()}
                        </div>
                      
                        <!-- Typing Indicator -->
                        <div id="typing-indicator" class="typing-indicator hidden">
                            <div class="typing-avatar">
                                <div class="avatar-icon">
                                    <i class="fas fa-robot"></i>
                                </div>
                            </div>
                            <div class="typing-content">
                                <div class="typing-text">AI is thinking...</div>
                                <div class="typing-animation">
                                    <span></span>
                                    <span></span>
                                    <span></span>
                                </div>
                            </div>
                        </div>
                    </div>
                    <!-- Chat Input Area -->
                    <div class="chat-input-container">
                        <div class="input-wrapper">
                            <div class="input-field">
                                <textarea
                                    id="chat-input"
                                    class="chat-input"
                                    placeholder="Message..."
                                    rows="1"
                                    maxlength="4000"
                                    spellcheck="true"
                                ></textarea>
                              
                                <div class="input-actions" id="input-actions">
                                    <button id="attach-btn" class="input-action-btn" title="Attach File">
                                        <i class="fas fa-paperclip"></i>
                                    </button>
                                    <button id="voice-btn" class="input-action-btn" title="Voice Input">
                                        <i class="fas fa-microphone"></i>
                                    </button>
                                    <button id="send-btn" class="send-btn" disabled title="Send Message">
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
            <div id="performance-panel" class="performance-panel glass-panel-v3 hidden">
                <div class="panel-header">
                    <h3>Performance Metrics</h3>
                    <button class="panel-close-btn" id="performance-close">
                        <i class="fas fa-times"></i>
                    </button>
                </div>
                <div class="metrics-content">
                    <div class="metrics-grid">
                        <div class="metric-card">
                            <div class="metric-label">Last Response</div>
                            <div class="metric-value" id="last-response-time">--</div>
                        </div>
                        <div class="metric-card">
                            <div class="metric-label">Average Response</div>
                            <div class="metric-value" id="avg-response-time">--</div>
                        </div>
                        <div class="metric-card">
                            <div class="metric-label">Total Messages</div>
                            <div class="metric-value" id="total-messages">--</div>
                        </div>
                        <div class="metric-card">
                            <div class="metric-label">Tokens Used</div>
                            <div class="metric-value" id="total-tokens">--</div>
                        </div>
                    </div>
                </div>
            </div>
        `;
    }
    createWelcomeMessage() {
        return `
            <div class="welcome-message">
                <div class="welcome-header">
                    <div class="welcome-avatar">
                        <i class="fas fa-robot"></i>
                    </div>
                    <h2 class="welcome-title">Welcome to Knowledge Base Chat</h2>
                    <p class="welcome-description">
                        I'm your AI assistant with access to your knowledge base. I can help you find information,
                        analyze documents, and provide insights based on your content.
                    </p>
                </div>
              
                <div class="welcome-suggestions">
                    <h4 class="suggestions-title">Try asking me:</h4>
                    <div class="suggestions-grid">
                        <button class="suggestion-card" data-prompt="What are the main categories in my knowledge base?">
                            <div class="suggestion-icon">
                                <i class="fas fa-folder-open"></i>
                            </div>
                            <div class="suggestion-content">
                                <span class="suggestion-title">Explore Categories</span>
                                <span class="suggestion-desc">Browse your content organization</span>
                            </div>
                        </button>
                      
                        <button class="suggestion-card" data-prompt="Summarize the latest developments in AI and machine learning">
                            <div class="suggestion-icon">
                                <i class="fas fa-chart-line"></i>
                            </div>
                            <div class="suggestion-content">
                                <span class="suggestion-title">Summarize Topics</span>
                                <span class="suggestion-desc">Get insights on specific subjects</span>
                            </div>
                        </button>
                      
                        <button class="suggestion-card" data-prompt="Find examples and tutorials from my documents">
                            <div class="suggestion-icon">
                                <i class="fas fa-search"></i>
                            </div>
                            <div class="suggestion-content">
                                <span class="suggestion-title">Find Examples</span>
                                <span class="suggestion-desc">Locate specific content types</span>
                            </div>
                        </button>
                      
                        <button class="suggestion-card" data-prompt="What insights can you provide about my content patterns?">
                            <div class="suggestion-icon">
                                <i class="fas fa-lightbulb"></i>
                            </div>
                            <div class="suggestion-content">
                                <span class="suggestion-title">Get Insights</span>
                                <span class="suggestion-desc">Discover content patterns</span>
                            </div>
                        </button>
                    </div>
                </div>
            </div>
        `;
    }
    async loadAvailableModels() {
        try {
            this.log('Loading available models from API...');
            const models = await this.apiCall('/api/chat/models/available', {
                errorMessage: 'Failed to load available models'
            });

            this.availableModels = models && models.length > 0 ? models : [{
                id: 'default',
                name: 'Default Model'
            }];
            this.updateModelSelector();

            if (!this.selectedModel && this.availableModels.length > 0) {
                this.selectedModel = this.availableModels[0].id;
                if (this.elements.modelSelector) {
                    this.elements.modelSelector.value = this.selectedModel;
                }
            }
            this.log(`Loaded ${this.availableModels.length} available models, selected: ${this.selectedModel}`);
        } catch (error) {
            this.setError(error, 'loading available models');
            this.availableModels = [{
                id: 'default',
                name: 'Default Model (fallback)'
            }];
            this.selectedModel = this.availableModels[0].id;
            this.updateModelSelector();
        }
    }
    updateModelSelector() {
        if (!this.elements.modelSelector) return;
       
        // Clear the loading state and populate with actual models
        const options = this.availableModels.map(model =>
            `<option value="${model.id}" title="${model.description || ''}">${model.name}</option>`
        ).join('');
        this.elements.modelSelector.innerHTML = options;
       
        // Update model display
        if (this.elements.modelDisplay && this.selectedModel) {
            const selectedModel = this.availableModels.find(m => m.id === this.selectedModel);
            this.elements.modelDisplay.textContent = selectedModel ? selectedModel.name : this.selectedModel;
        }
       
        console.log('Model selector updated with', this.availableModels.length, 'models');
    }
    async restoreActiveSession() {
        try {
            this.log('Attempting to restore active session from API...');
            const sessionData = await this.apiCall('/api/chat/sessions/active', {
                errorMessage: 'Failed to restore active session',
                // A 404 is expected if no active session exists, so we handle it gracefully
                handle404: true
            });

            if (sessionData && sessionData.session_id) {
                this.log(`Restored active session ${sessionData.session_id}`);
                this.activeSession = sessionData;
                this.currentSessionId = sessionData.session_id;
                await this.loadSessionMessages(this.activeSession);
                this.updateSessionInfo();
            } else {
                this.log('No active session found, creating a new one.');
                await this.createNewSession();
            }
        } catch (error) {
            this.setError(error, 'restoring active session');
            // Fallback to creating a new session on any error
            await this.createNewSession();
        }
    }
    async loadSessionHistory() {
        try {
            this.log('Loading session history from API...');
            const sessions = await this.apiCall('/api/chat/sessions', {
                errorMessage: 'Failed to load chat sessions'
            });

            this.sessions.clear();
            this.archivedSessions.clear();

            sessions.forEach(session => {
                if (session.is_archived) {
                    this.archivedSessions.set(session.session_id, session);
                } else {
                    this.sessions.set(session.session_id, session);
                }
            });

            this.updateSessionsList();
            this.updateSessionsCount();
            this.log(`Loaded ${this.sessions.size} active and ${this.archivedSessions.size} archived sessions.`);
        } catch (error) {
            this.setError(error, 'loading session history');
            this.updateSessionsList(); // Show empty state
        }
    }
    async createNewSession() {
        try {
            this.log('Creating new session via API...');
            const newSession = await this.apiCall('/api/chat/sessions', {
                method: 'POST',
                body: {
                    title: 'New Conversation'
                },
                errorMessage: 'Failed to create new session'
            });

            this.currentSessionId = newSession.session_id;
            this.activeSession = { ...newSession,
                messages: []
            }; // Start with an empty message array
            this.sessions.set(newSession.session_id, this.activeSession);

            this.clearChatMessages();
            this.showWelcomeMessage();
            this.updateSessionInfo();
            this.updateSessionsList();
            this.updateSessionsCount();

            this.performanceMetrics.sessionsCreated++;
            this.log(`New chat session created: ${newSession.session_id}`);
        } catch (error) {
            this.setError(error, 'creating new chat session');
        }
    }
    updateSessionsList(filteredSessions = null) {
        if (!this.elements.sessionsList) return;
       
        const currentSessions = this.currentView === 'active' ?
            Array.from(this.sessions.values()) :
            Array.from(this.archivedSessions.values());
        const sessionsToShow = filteredSessions || currentSessions;
       
        if (sessionsToShow.length === 0) {
            this.elements.sessionsList.innerHTML = this.createEmptyState();
            return;
        }
       
        const sessionsHTML = sessionsToShow.map(session =>
            this.createSessionItem(session)
        ).join('');
        this.elements.sessionsList.innerHTML = sessionsHTML;
    }
    createEmptyState() {
        const isActive = this.currentView === 'active';
        return `
            <div class="empty-state">
                <div class="empty-icon">
                    <i class="fas fa-${isActive ? 'comments' : 'archive'}"></i>
                </div>
                <div class="empty-title">
                    ${isActive ? 'No active conversations' : 'No archived conversations'}
                </div>
                <div class="empty-description">
                    ${isActive ? 'Start a new chat to begin' : 'Archived chats will appear here'}
                </div>
                ${isActive ? '<button class="empty-action-btn">Start New Chat</button>' : ''}
            </div>
        `;
    }
    createSessionItem(session) {
        const isActive = session.session_id === this.currentSessionId;
        const isArchived = session.is_archived;
        const lastMessage = this.getLastMessagePreview(session);
        const timeAgo = this.formatSessionTime(session.last_updated || session.created_at);
        return `
            <div class="session-item ${isActive ? 'active' : ''} ${isArchived ? 'archived' : ''}"
                 data-session-id="${session.session_id}"
                 data-archived="${isArchived}">
                <div class="session-content">
                    <div class="session-header">
                        <div class="session-title">${session.title || 'New Conversation'}</div>
                        <div class="session-time">${timeAgo}</div>
                    </div>
                    <div class="session-preview">${lastMessage}</div>
                    <div class="session-metadata">
                        <span class="message-count">
                            <i class="fas fa-comment"></i>
                            ${session.message_count || 0}
                        </span>
                        <span class="model-used">
                            <i class="fas fa-brain"></i>
                            ${this.getModelName(session.model)}
                        </span>
                    </div>
                </div>
                <div class="session-actions">
                    ${isArchived ?
                `<button class="session-action-btn restore-btn" title="Restore">
                            <i class="fas fa-undo"></i>
                        </button>` :
                `<button class="session-action-btn archive-btn" title="Archive">
                            <i class="fas fa-archive"></i>
                        </button>`
            }
                    <button class="session-action-btn delete-btn" title="Delete">
                        <i class="fas fa-trash"></i>
                    </button>
                </div>
            </div>
        `;
    }
    getLastMessagePreview(session) {
        if (!session.messages || session.messages.length === 0) {
            return 'No messages yet';
        }
        const lastMessage = session.messages[session.messages.length - 1];
        const content = lastMessage.content || '';
        const maxLength = 80;
        if (content.length > maxLength) {
            return content.substring(0, maxLength) + '...';
        }
        return content;
    }
    updateSessionsCount() {
        if (this.elements.sessionsCount) {
            const count = this.currentView === 'active' ?
                this.sessions.size :
                this.archivedSessions.size;
            this.elements.sessionsCount.textContent = count.toString();
        }
       
        // Update sessions title
        if (this.elements.sessionsTitle) {
            this.elements.sessionsTitle.textContent =
                this.currentView === 'active' ? 'Active Chats' : 'Chat History';
        }
    }
    updateSessionInfo(session = null, readOnly = false) {
        const currentSession = session || this.activeSession;
        if (!currentSession) return;
       
        // Update session title
        if (this.elements.sessionTitle) {
            this.elements.sessionTitle.textContent = currentSession.title || 'New Conversation';
        }
       
        // Update mobile title
        const mobileTitle = document.getElementById('mobile-session-title');
        if (mobileTitle) {
            mobileTitle.textContent = currentSession.title || 'New Chat';
        }
       
        // Update metadata
        if (this.elements.sessionMeta) {
            const messageCount = currentSession.message_count || 0;
            const timeAgo = this.formatSessionTime(currentSession.last_updated || currentSession.created_at);
            const modelName = this.getModelName(currentSession.model || this.selectedModel);
            this.elements.sessionMeta.innerHTML = `
                <span class="message-count">${messageCount} messages</span>
                <span class="separator">•</span>
                <span class="session-time">${timeAgo}</span>
                <span class="separator">•</span>
                <span class="model-display">${modelName}</span>
                ${readOnly ? '<span class="separator">•</span><span class="read-only-badge">Read Only</span>' : ''}
            `;
        }
        // Update message count
        if (this.elements.messageCount) {
            this.elements.messageCount.textContent = `${currentSession.message_count || 0} messages`;
        }
    }
    formatSessionTime(timestamp) {
        const date = new Date(timestamp);
        const now = new Date();
        const diffMs = now - date;
        const diffMinutes = diffMs / (1000 * 60);
        const diffHours = diffMs / (1000 * 60 * 60);
        const diffDays = diffMs / (1000 * 60 * 60 * 24);
       
        if (diffMinutes < 1) {
            return 'Just now';
        } else if (diffMinutes < 60) {
            return `${Math.floor(diffMinutes)}m ago`;
        } else if (diffHours < 24) {
            return `${Math.floor(diffHours)}h ago`;
        } else if (diffDays < 7) {
            return `${Math.floor(diffDays)}d ago`;
        } else {
            return date.toLocaleDateString();
        }
    }
    getModelName(modelId) {
        const model = this.availableModels.find(m => m.id === modelId);
        return model ? model.name : modelId;
    }
    clearChatMessages() {
        if (this.elements.chatMessages) {
            this.elements.chatMessages.innerHTML = '';
        }
    }
    showWelcomeMessage() {
        if (this.elements.chatMessages) {
            this.elements.chatMessages.innerHTML = this.createWelcomeMessage();
        }
    }
    handleNewChat = async () => {
        try {
            // Archive current active session if it exists and has messages
            if (this.activeSession && this.activeSession.message_count > 0) {
                await this.archiveCurrentSession();
            }
            // Create new session
            await this.createNewSession();
        } catch (error) {
            this.setError(error, 'creating new chat session');
        }
    }
    handleModelChange = () => {
        this.selectedModel = this.elements.modelSelector.value;
        this.updateModelDisplay();
        this.dispatchEvent('model_changed', { model: this.selectedModel });
        this.log('Model changed to:', this.selectedModel);
    }
    updateModelDisplay() {
        if (this.elements.modelDisplay && this.selectedModel) {
            const selectedModel = this.availableModels.find(m => m.id === this.selectedModel);
            this.elements.modelDisplay.textContent = selectedModel ? selectedModel.name : this.selectedModel;
        }
    }
    setupAutoSave() {
        this.autoSaveTimer = setInterval(() => {
            this.saveSessionState();
        }, this.autoSaveInterval);
    }
    setupResponsiveDesign() {
        this.updateLayout();
        // Handle window resize
        this.handleWindowResize = EventListenerService.getInstance().throttle('window-resize', () => {
            this.updateLayout();
        }, 100);
    }
    initializeVirtualScroll() {
        if (this.virtualScroll) return;
        this.virtualScroll = new VirtualScrollManager(this.elements.chatMessages, {
            itemHeight: 80, // Approximate message height
            buffer: 10, // Number of items to render outside viewport
            onRender: null
        });
    }
    async archiveCurrentSession() {
        if (!this.activeSession) return;
        try {
            await this.apiCall(`/api/chat/sessions/${this.activeSession.session_id}/archive`, {
                method: 'POST',
                errorMessage: 'Failed to archive session'
            });
            // Move to archived sessions
            this.archivedSessions.set(this.activeSession.session_id, {
                ...this.activeSession,
                is_archived: true
            });
            this.sessions.delete(this.activeSession.session_id);
            this.activeSession = null;
            this.currentSessionId = null;
            this.updateSessionsList();
            this.updateSessionsCount();
        } catch (error) {
            this.logError('Failed to archive session:', error);
        }
    }
    handleSessionSelect = async (e) => {
        const sessionItem = e.target.closest('.session-item');
        if (!sessionItem) return;
        const sessionId = sessionItem.dataset.sessionId;
        const isArchived = sessionItem.dataset.archived === 'true';
        if (isArchived) {
            // For archived sessions, just show them (read-only)
            await this.viewArchivedSession(sessionId);
        } else {
            // For active sessions, switch to them
            await this.switchToSession(sessionId);
        }
    }
    async switchToSession(sessionId) {
        try {
            const session = await this.apiCall(`/api/chat/sessions/${sessionId}`, {
                errorMessage: 'Failed to load chat session'
            });
            // Set as active session
            await this.apiCall(`/api/chat/sessions/${sessionId}/activate`, {
                method: 'POST',
                errorMessage: 'Failed to activate session'
            });
            this.currentSessionId = sessionId;
            this.activeSession = session;
            this.sessions.set(sessionId, session);
            await this.loadSessionMessages(session);
            this.updateSessionInfo();
            this.updateSessionsList();
            this.log('Switched to session:', sessionId);
        } catch (error) {
            this.setError(error, 'switching to chat session');
        }
    }
    async viewArchivedSession(sessionId) {
        try {
            const session = await this.apiCall(`/api/chat/sessions/${sessionId}`, {
                errorMessage: 'Failed to load archived session'
            });
            await this.loadSessionMessages(session, true); // Read-only mode
            this.updateSessionInfo(session, true);
        } catch (error) {
            this.setError(error, 'viewing archived session');
        }
    }
    async loadSessionMessages(session, readOnly = false) {
        if (!session.messages || session.messages.length === 0) {
            this.showWelcomeMessage();
            return;
        }
        // Use virtual scrolling for large message lists
        if (session.messages.length > 100) {
            if (!this.virtualScroll) {
                this.initializeVirtualScroll();
            }
            this.virtualScroll.onRender = (item) => this.messageRenderer.createMessageHTML(item, readOnly);
            this.virtualScroll.updateMessages(session.messages);
        } else {
            this.renderMessagesStandard(session.messages, readOnly);
        }
        this.scrollToBottom();
    }
    renderMessagesStandard(messages, readOnly = false) {
        const messagesHTML = messages.map(message =>
            this.messageRenderer.createMessageHTML(message, readOnly)
        ).join('');
        this.elements.chatMessages.innerHTML = messagesHTML;
    }
    renderMessagesVirtual(messages, readOnly = false) {
        // Implement virtual scrolling for performance
        if (this.virtualScroll) {
            this.virtualScroll.updateMessages(messages, readOnly);
        }
    }
    handleSendMessage = async () => {
        const message = this.elements.chatInput.value.trim();
        if (!message || this.isTyping) return;
        // Ensure we have an active session
        if (!this.currentSessionId) {
            await this.createNewSession();
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
            this.updateSendButtonState();
            this.showTypingIndicator();
            this.isTyping = true;
            const startTime = Date.now();
            // Send message to API with knowledge base integration
            const response = await this.apiCall('/api/chat/enhanced', {
                method: 'POST',
                body: {
                    message: message,
                    session_id: this.currentSessionId,
                    model: this.selectedModel,
                    use_knowledge_base: true,
                    include_embeddings: true
                },
                errorMessage: 'Failed to send message',
                timeout: 120000 // 2 minute timeout for knowledge base queries
            });
            const responseTime = Date.now() - startTime;
            // Add assistant response to UI
            this.addMessageToUI({
                role: 'assistant',
                content: response.response,
                created_at: new Date().toISOString(),
                sources: response.sources || [],
                context_stats: response.context_stats || {},
                performance_metrics: {
                    response_time: responseTime,
                    tokens_used: response.context_stats?.total_tokens || 0,
                    sources_count: response.sources?.length || 0,
                    embedding_matches: response.context_stats?.embedding_matches || 0
                }
            });
            // Update performance metrics
            this.updatePerformanceMetrics(responseTime, response.context_stats?.total_tokens || 0);
            // Update session info
            this.updateSessionInfo();
            // Auto-save session state
            this.saveSessionState();
        } catch (error) {
            this.setError(error, 'sending chat message');
            this.addErrorMessageToUI('Sorry, I encountered an error processing your message. Please try again.');
        } finally {
            this.hideTypingIndicator();
            this.isTyping = false;
        }
    }
    addMessageToUI(message) {
        const messageHTML = this.messageRenderer.createMessageHTML(message);
        // Remove welcome message if present
        const welcomeMessage = this.elements.chatMessages.querySelector('.welcome-message');
        if (welcomeMessage) {
            welcomeMessage.remove();
        }
        this.elements.chatMessages.insertAdjacentHTML('beforeend', messageHTML);
        this.scrollToBottom();
        // Update session message count
        if (this.activeSession) {
            this.activeSession.message_count = (this.activeSession.message_count || 0) + 1;
            this.updateSessionInfo();
        }
    }
    addErrorMessageToUI(errorMessage) {
        const errorHTML = `
            <div class="message error-message">
                <div class="message-avatar">
                    <div class="avatar-icon error">
                        <i class="fas fa-exclamation-triangle"></i>
                    </div>
                </div>
                <div class="message-content">
                    <div class="message-header">
                        <span class="message-sender">System</span>
                        <span class="message-timestamp">${new Date().toLocaleTimeString()}</span>
                    </div>
                    <div class="message-text error-text">${errorMessage}</div>
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
    handleInputChange = () => {
        this.updateCharCount();
        this.updateSendButtonState();
        this.autoResizeInput();
    }
    updateCharCount() {
        const charCountEl = document.getElementById('char-count');
        if (charCountEl && this.elements.chatInput) {
            const count = this.elements.chatInput.value.length;
            charCountEl.textContent = `${count}/4000`;
            // Add warning class if approaching limit
            if (count > 3500) {
                charCountEl.classList.add('warning');
            } else {
                charCountEl.classList.remove('warning');
            }
        }
    }
    updateSendButtonState() {
        if (this.elements.sendBtn && this.elements.chatInput) {
            const hasText = this.elements.chatInput.value.trim().length > 0;
            this.elements.sendBtn.disabled = !hasText || this.isTyping;
            if (hasText && !this.isTyping) {
                this.elements.sendBtn.classList.add('ready');
            } else {
                this.elements.sendBtn.classList.remove('ready');
            }
        }
    }
    autoResizeInput() {
        if (this.elements.chatInput) {
            this.elements.chatInput.style.height = 'auto';
            const scrollHeight = this.elements.chatInput.scrollHeight;
            const maxHeight = 120; // Max 5 lines approximately
            this.elements.chatInput.style.height = Math.min(scrollHeight, maxHeight) + 'px';
        }
    }
    handleEnterKey = (e) => {
        e.preventDefault();
        this.handleSendMessage();
    }
    handleShiftEnter = (e) => {
        // Allow new line with Shift+Enter
        // Default behavior is fine, just prevent the regular Enter handler
    }
    handleEscapeKey = () => {
        // Clear input or close panels
        if (this.elements.chatInput.value.trim()) {
            this.elements.chatInput.value = '';
            this.updateCharCount();
            this.updateSendButtonState();
        } else {
            // Close any open panels
            this.closeAllPanels();
        }
    }
    handleSidebarToggle = () => {
        this.sidebarCollapsed = !this.sidebarCollapsed;
        if (this.elements.sidebar) {
            this.elements.sidebar.classList.toggle('collapsed', this.sidebarCollapsed);
        }
        // Update layout
        this.updateLayout();
    }
    handleViewToggle = () => {
        this.currentView = this.currentView === 'active' ? 'history' : 'active';
        // Update view toggle button
        if (this.elements.viewToggle) {
            const icon = this.elements.viewToggle.querySelector('i');
            if (icon) {
                icon.className = this.currentView === 'active' ? 'fas fa-history' : 'fas fa-comments';
            }
            this.elements.viewToggle.title = this.currentView === 'active' ? 'View History' : 'View Active';
        }
        this.updateSessionsList();
        this.updateSessionsCount();
    }
    handleSessionSearch = (e) => {
        this.searchQuery = e.target.value.toLowerCase();
        // Show/hide clear button
        const clearBtn = this.elements.searchClear;
        if (clearBtn) {
            clearBtn.style.display = this.searchQuery ? 'block' : 'none';
        }
        this.filterSessions();
    }
    handleSearchClear = () => {
        this.elements.sessionSearch.value = '';
        this.searchQuery = '';
        this.elements.searchClear.style.display = 'none';
        this.filterSessions();
    }
    filterSessions() {
        if (!this.searchQuery) {
            this.updateSessionsList();
            return;
        }
        const currentSessions = this.currentView === 'active' ?
            Array.from(this.sessions.values()) :
            Array.from(this.archivedSessions.values());
        const filteredSessions = currentSessions.filter(session => {
            const titleMatch = (session.title || '').toLowerCase().includes(this.searchQuery);
            const messageMatch = session.messages && session.messages.some(msg =>
                msg.content.toLowerCase().includes(this.searchQuery)
            );
            return titleMatch || messageMatch;
        });
        this.updateSessionsList(filteredSessions);
    }
    handleArchiveSession = async (e) => {
        e.stopPropagation();
        const sessionItem = e.target.closest('.session-item');
        if (!sessionItem) return;
        const sessionId = sessionItem.dataset.sessionId;
        await this.archiveSession(sessionId);
    }
    async archiveSession(sessionId) {
        try {
            await this.apiCall(`/api/chat/sessions/${sessionId}/archive`, {
                method: 'POST',
                errorMessage: 'Failed to archive session'
            });
            // Move session to archived
            const session = this.sessions.get(sessionId);
            if (session) {
                session.is_archived = true;
                this.archivedSessions.set(sessionId, session);
                this.sessions.delete(sessionId);
                // If this was the active session, create a new one
                if (sessionId === this.currentSessionId) {
                    await this.createNewSession();
                }
                this.updateSessionsList();
                this.updateSessionsCount();
            }
        } catch (error) {
            this.setError(error, 'archiving session');
        }
    }
    handleRestoreSession = async (e) => {
        e.stopPropagation();
        const sessionItem = e.target.closest('.session-item');
        if (!sessionItem) return;
        const sessionId = sessionItem.dataset.sessionId;
        await this.restoreSession(sessionId);
    }
    async restoreSession(sessionId) {
        try {
            await this.apiCall(`/api/chat/sessions/${sessionId}/restore`, {
                method: 'POST',
                errorMessage: 'Failed to restore session'
            });
            // Move session back to active
            const session = this.archivedSessions.get(sessionId);
            if (session) {
                session.is_archived = false;
                this.sessions.set(sessionId, session);
                this.archivedSessions.delete(sessionId);
                this.updateSessionsList();
                this.updateSessionsCount();
            }
        } catch (error) {
            this.setError(error, 'restoring session');
        }
    }
    handleDeleteSession = async (e) => {
        e.stopPropagation();
        const sessionItem = e.target.closest('.session-item');
        if (!sessionItem) return;
        const sessionId = sessionItem.dataset.sessionId;
        // Confirm deletion
        if (!confirm('Are you sure you want to delete this conversation? This action cannot be undone.')) {
            return;
        }
        await this.deleteSession(sessionId);
    }
    async deleteSession(sessionId) {
        try {
            await this.apiCall(`/api/chat/sessions/${sessionId}`, {
                method: 'DELETE',
                errorMessage: 'Failed to delete session'
            });
            // Remove from both maps
            this.sessions.delete(sessionId);
            this.archivedSessions.delete(sessionId);
            // If this was the active session, create a new one
            if (sessionId === this.currentSessionId) {
                await this.createNewSession();
            }
            this.updateSessionsList();
            this.updateSessionsCount();
        } catch (error) {
            this.setError(error, 'deleting session');
        }
    }
    updateLayout() {
        const width = window.innerWidth;
        const layout = document.getElementById('modern-chat-layout');
        if (!layout) return;
        // Remove existing responsive classes
        layout.classList.remove('mobile', 'tablet', 'desktop');
        // Add appropriate class
        if (width < this.breakpoints.mobile) {
            layout.classList.add('mobile');
            this.sidebarCollapsed = true;
        } else if (width < this.breakpoints.tablet) {
            layout.classList.add('tablet');
        } else {
            layout.classList.add('desktop');
            this.sidebarCollapsed = false;
        }
        // Update sidebar state
        if (this.elements.sidebar) {
            this.elements.sidebar.classList.toggle('collapsed', this.sidebarCollapsed);
        }
    }
    handleWindowResize = () => {
        this.updateLayout();
        if (this.virtualScroll) {
            this.virtualScroll.updateContainerHeight();
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
            const totalResponses = this.performanceMetrics.totalMessages;
            this.performanceMetrics.averageResponseTime =
                ((this.performanceMetrics.averageResponseTime * (totalResponses - 1)) + responseTime) / totalResponses;
        }
        // Update performance panel if visible
        this.updatePerformancePanel();
    }
    updatePerformancePanel() {
        const panel = this.elements.performancePanel;
        if (!panel || panel.classList.contains('hidden')) return;
        const elements = {
            lastResponse: document.getElementById('last-response-time'),
            avgResponse: document.getElementById('avg-response-time'),
            totalMessages: document.getElementById('total-messages'),
            totalTokens: document.getElementById('total-tokens')
        };
        if (elements.lastResponse) {
            elements.lastResponse.textContent = this.durationFormatter.format(
                this.performanceMetrics.lastResponseTime || 0
            );
        }
        if (elements.avgResponse) {
            elements.avgResponse.textContent = this.durationFormatter.format(
                this.performanceMetrics.averageResponseTime || 0
            );
        }
        if (elements.totalMessages) {
            elements.totalMessages.textContent = this.performanceMetrics.totalMessages.toString();
        }
        if (elements.totalTokens) {
            elements.totalTokens.textContent = this.performanceMetrics.totalTokens.toString();
        }
    }
    async saveSessionState() {
        if (!this.activeSession) return;
        try {
            await this.apiCall(`/api/chat/sessions/${this.activeSession.session_id}/state`, {
                method: 'POST',
                body: {
                    ui_state: {
                        selectedModel: this.selectedModel,
                        sidebarCollapsed: this.sidebarCollapsed,
                        currentView: this.currentView
                    }
                },
                errorMessage: 'Failed to save session state'
            });
        } catch (error) {
            this.logError('Failed to save session state:', error);
        }
    }
    closeAllPanels() {
        const panels = document.querySelectorAll('.performance-panel, .settings-panel');
        panels.forEach(panel => panel.classList.add('hidden'));
    }
    cleanup() {
        // Clear auto-save timer
        if (this.autoSaveTimer) {
            clearInterval(this.autoSaveTimer);
        }
        // Cleanup virtual scroll
        if (this.virtualScroll) {
            this.virtualScroll.destroy();
        }
        // Use CleanupService for comprehensive cleanup
        this.cleanupService.cleanup(this);
    }
    handlePerformanceToggle = () => {
        this.elements.performancePanel.classList.toggle('hidden');
        if (!this.elements.performancePanel.classList.contains('hidden')) {
            this.updatePerformancePanel();
        }
    }
    handleArchiveCurrentSession = () => {
        if (this.currentSessionId) {
            this.archiveSession(this.currentSessionId);
        }
    }
    handleExportSession = async () => {
        if (!this.activeSession) return;
        try {
            const blob = new Blob([JSON.stringify(this.activeSession, null, 2)], { type: 'application/json' });
            const url = URL.createObjectURL(blob);
            const a = document.createElement('a');
            a.href = url;
            a.download = `chat_session_${this.currentSessionId}.json`;
            a.click();
            URL.revokeObjectURL(url);
        } catch (error) {
            this.setError(error, 'exporting session');
        }
    }
    handleAttachFile = () => {
        // TODO: Implement file attachment
        alert('File attachment not implemented yet');
    }
    handleVoiceInput = () => {
        // TODO: Implement voice input
        alert('Voice input not implemented yet');
    }
    handleMessageAction = (e) => {
        const button = e.target.closest('.message-action');
        if (!button) return;
        const action = button.dataset.action;
        const messageEl = button.closest('.message');
        if (action === 'copy') {
            const text = messageEl.querySelector('.message-text').textContent;
            navigator.clipboard.writeText(text).then(() => {
                this.log('Message copied');
            });
        } else if (action === 'regenerate') {
            // TODO: regenerate response
            alert('Regenerate not implemented');
        } else if (action === 'details') {
            // TODO: show details
            alert('Details not implemented');
        }
    }
    handleKnowledgeBaseLink = (e) => {
        e.preventDefault();
        const kbItem = e.target.dataset.kbItem;
        // TODO: open knowledge base item
        alert(`Open KB: ${kbItem}`);
    }
    handleSynthesisLink = (e) => {
        e.preventDefault();
        const synthesis = e.target.dataset.synthesis;
        // TODO: open synthesis document
        alert(`Open Synthesis: ${synthesis}`);
    }
    handleSuggestionClick = (e) => {
        const card = e.target.closest('.suggestion-card');
        if (card && card.dataset.prompt) {
            this.elements.chatInput.value = card.dataset.prompt;
            this.handleInputChange();
            this.handleSendMessage();
        }
    }
    handlePerformanceDetailsToggle = (e) => {
        e.preventDefault();
        const details = e.target.closest('.message-performance').querySelector('.performance-details');
        if (details) {
            details.classList.toggle('hidden');
        }
    }
    handleSourcesToggle = (e) => {
        e.preventDefault();
        const content = e.target.closest('.message-sources').querySelector('.sources-content');
        if (content) {
            content.classList.toggle('hidden');
            const icon = e.target.querySelector('i');
            if (icon) {
                icon.classList.toggle('fa-chevron-down');
                icon.classList.toggle('fa-chevron-up');
            }
        }
    }
    handleSessionUpdate(detail) {
        // TODO: Implement if needed
    }
    handleModelUpdate(detail) {
        // TODO: Implement if needed
    }
}

/**
 * Message Renderer - Handles message display and formatting
 */
class MessageRenderer {
    constructor(chatManager) {
        this.chatManager = chatManager;
    }
    createMessageHTML(message, readOnly = false) {
        const isUser = message.role === 'user';
        const timestamp = new Date(message.created_at).toLocaleTimeString();
        let content = message.content;
        // Process links to knowledge base items and synthesis documents
        content = this.processContentLinks(content);
        // Add performance metrics for assistant messages
        let performanceHTML = '';
        let sourcesHTML = '';
        if (!isUser) {
            if (message.performance_metrics) {
                performanceHTML = this.createPerformanceMetricsHTML(message.performance_metrics);
            }
            if (message.sources && message.sources.length > 0) {
                sourcesHTML = this.createSourcesHTML(message.sources);
            }
        }
        return `
            <div class="message ${isUser ? 'user-message' : 'assistant-message'} ${readOnly ? 'read-only' : ''}">
                <div class="message-avatar">
                    <div class="avatar-icon ${isUser ? 'user' : 'assistant'}">
                        <i class="fas fa-${isUser ? 'user' : 'robot'}"></i>
                    </div>
                </div>
                <div class="message-content">
                    <div class="message-header">
                        <span class="message-sender">${isUser ? 'You' : 'AI Assistant'}</span>
                        <span class="message-timestamp">${timestamp}</span>
                    </div>
                    <div class="message-text">${content}</div>
                    ${sourcesHTML}
                    ${performanceHTML}
                    ${!readOnly ? this.createMessageActions(message) : ''}
                </div>
            </div>
        `;
    }
    processContentLinks(content) {
        // Convert knowledge base item references to clickable links
        content = content.replace(
            /\[KB:([^\]]+)\]/g,
            '<a href="#" class="kb-link" data-kb-item="$1" title="View in Knowledge Base">$1</a>'
        );
        // Convert synthesis document references to clickable links
        content = content.replace(
            /\[SYNTHESIS:([^\]]+)\]/g,
            '<a href="#" class="synthesis-link" data-synthesis="$1" title="View Synthesis Document">$1</a>'
        );
        // Convert URLs to clickable links
        content = content.replace(
            /(https?:\/\/[^\s]+)/g,
            '<a href="$1" target="_blank" rel="noopener noreferrer" class="external-link">$1</a>'
        );
        return content;
    }
    createPerformanceMetricsHTML(metrics) {
        return `
            <div class="message-performance">
                <button class="performance-toggle" title="View Performance Metrics">
                    <i class="fas fa-chart-bar"></i>
                    <span class="response-time">${this.chatManager.durationFormatter.format(metrics.response_time || 0)}</span>
                    ${metrics.sources_count ? `<span class="sources-count">${metrics.sources_count} sources</span>` : ''}
                </button>
                <div class="performance-details hidden">
                    <div class="metrics-grid">
                        <div class="metric">
                            <span class="label">Response Time:</span>
                            <span class="value">${this.chatManager.durationFormatter.format(metrics.response_time || 0)}</span>
                        </div>
                        <div class="metric">
                            <span class="label">Tokens Used:</span>
                            <span class="value">${metrics.tokens_used || 0}</span>
                        </div>
                        <div class="metric">
                            <span class="label">Sources Found:</span>
                            <span class="value">${metrics.sources_count || 0}</span>
                        </div>
                        ${metrics.embedding_matches ? `
                        <div class="metric">
                            <span class="label">Embedding Matches:</span>
                            <span class="value">${metrics.embedding_matches}</span>
                        </div>
                        ` : ''}
                    </div>
                </div>
            </div>
        `;
    }
    createSourcesHTML(sources) {
        if (!sources || sources.length === 0) return '';
        const sourcesHTML = sources.map(source => `
            <div class="source-item">
                <div class="source-header">
                    <span class="source-title">${source.title || 'Untitled'}</span>
                    <span class="source-type">${source.type || 'KB Item'}</span>
                </div>
                <div class="source-preview">${source.content ? source.content.substring(0, 150) + '...' : ''}</div>
                <div class="source-metadata">
                    <span class="source-category">${source.category || 'Uncategorized'}</span>
                    ${source.confidence ? `<span class="source-confidence">${Math.round(source.confidence * 100)}% match</span>` : ''}
                </div>
            </div>
        `).join('');
        return `
            <div class="message-sources">
                <div class="sources-header">
                    <i class="fas fa-book-open"></i>
                    <span class="sources-title">Sources (${sources.length})</span>
                    <button class="sources-toggle" title="Toggle Sources">
                        <i class="fas fa-chevron-down"></i>
                    </button>
                </div>
                <div class="sources-content hidden">
                    ${sourcesHTML}
                </div>
            </div>
        `;
    }
    createMessageActions(message) {
        const isUser = message.role === 'user';
        return `
            <div class="message-actions">
                <button class="message-action copy-btn" data-action="copy" title="Copy Message">
                    <i class="fas fa-copy"></i>
                </button>
                ${!isUser ? `
                <button class="message-action regenerate-btn" data-action="regenerate" title="Regenerate Response">
                    <i class="fas fa-redo"></i>
                </button>
                ` : ''}
                <button class="message-action details-btn" data-action="details" title="Message Details">
                    <i class="fas fa-info-circle"></i>
                </button>
            </div>
        `;
    }
}

/**
 * Virtual Scroll Manager - Handles large message lists efficiently
 */
class VirtualScrollManager {
    constructor(container, options = {}) {
        this.container = container;
        this.options = {
            itemHeight: 80,
            buffer: 10,
            ...options
        };
        this.onRender = options.onRender;
        this.items = [];
        this.visibleItems = [];
        this.scrollTop = 0;
        this.containerHeight = 0;
        this.init();
    }
    init() {
        this.container.addEventListener('scroll', this.handleScroll.bind(this));
        this.updateContainerHeight();
    }
    updateMessages(messages) {
        this.items = messages;
        this.render();
    }
    handleScroll() {
        this.scrollTop = this.container.scrollTop;
        this.render();
    }
    updateContainerHeight() {
        this.containerHeight = this.container.clientHeight;
        this.render();
    }
    render() {
        const startIndex = Math.max(0, Math.floor(this.scrollTop / this.options.itemHeight) - this.options.buffer);
        const endIndex = Math.min(
            this.items.length,
            startIndex + Math.ceil(this.containerHeight / this.options.itemHeight) + (this.options.buffer * 2)
        );
        this.visibleItems = this.items.slice(startIndex, endIndex);
        // Update container content
        this.updateDOM(startIndex, endIndex);
    }
    updateDOM(startIndex, endIndex) {
        if (!this.onRender) return;
        const startPadding = startIndex * this.options.itemHeight;
        const endPadding = (this.items.length - endIndex) * this.options.itemHeight;
        this.container.style.paddingTop = `${startPadding}px`;
        this.container.style.paddingBottom = `${endPadding}px`;
        const html = this.visibleItems.map(item => this.onRender(item)).join('');
        this.container.innerHTML = html;
    }
    destroy() {
        this.container.removeEventListener('scroll', this.handleScroll);
    }
}

// Export for use in other modules
window.ModernChatManager = ModernChatManager;
window.MessageRenderer = MessageRenderer;
window.VirtualScrollManager = VirtualScrollManager;
