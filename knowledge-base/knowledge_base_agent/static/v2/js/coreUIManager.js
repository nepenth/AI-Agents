/**
 * Core UI Manager
 * Consolidates ChatManager, KnowledgeBaseManager, and SynthesisManager
 * Provides unified interface for main content areas
 */
class CoreUIManager extends BaseManager {
    constructor(options = {}) {
        super({
            enableLogging: true,
            autoInit: false, // Manual initialization for better control
            ...options
        });

        // UI state management
        this.activeView = 'chat'; // chat, kb, synthesis
        this.viewHistory = ['chat'];
        this.maxHistoryLength = 10;

        // Component-specific state
        this.chatState = {
            currentSessionId: null,
            availableModels: [],
            sessions: [],
            isLoading: false
        };

        this.kbState = {
            currentCategory: null,
            currentItem: null,
            searchQuery: '',
            viewMode: 'tree', // tree, grid, list
            data: null
        };

        this.synthesisState = {
            currentDocument: null,
            documents: [],
            isLoading: false
        };
    }

    /**
     * Initialize DOM elements for all UI components
     */
    async initializeElements() {
        this.log('Initializing UI elements...');

        // Main content container
        this.elements.mainContent = document.getElementById('main-content');
        if (!this.elements.mainContent) {
            throw new Error('Main content container not found');
        }

        // Chat elements
        this.elements.chat = {
            container: document.getElementById('chat-content'),
            input: document.getElementById('v2-chat-input'),
            sendBtn: document.getElementById('v2-send-btn'),
            messagesContainer: document.getElementById('v2-messages'),
            sessionList: document.getElementById('v2-session-list'),
            modelSelector: document.getElementById('v2-model-selector'),
            newChatBtn: document.getElementById('v2-new-chat-btn'),
            sessionSearch: document.getElementById('v2-session-search'),
            archiveBtn: document.getElementById('v2-archive-btn'),
            deleteBtn: document.getElementById('v2-delete-btn'),
            exportBtn: document.getElementById('v2-export-btn')
        };

        // Knowledge Base elements
        this.elements.kb = {
            container: document.getElementById('kb-content'),
            tree: document.getElementById('kb-tree'),
            content: document.getElementById('kb-main-content'),
            filter: document.getElementById('kb-filter'),
            clearSearch: document.getElementById('kb-clear-search'),
            expandAll: document.getElementById('kb-expand-all'),
            collapseAll: document.getElementById('kb-collapse-all'),
            homeBtn: document.getElementById('kb-home-btn'),
            refreshBtn: document.getElementById('kb-refresh-btn'),
            exportBtn: document.getElementById('kb-export-btn'),
            itemsGridView: document.getElementById('kb-items-grid-view'),
            itemsListView: document.getElementById('kb-items-list-view'),
            itemsSort: document.getElementById('kb-items-sort')
        };

        // Synthesis elements
        this.elements.synthesis = {
            container: document.getElementById('synthesis-content'),
            documentList: document.getElementById('synthesis-document-list'),
            documentContent: document.getElementById('synthesis-document-content'),
            refreshBtn: document.getElementById('synthesis-refresh-btn'),
            exportBtn: document.getElementById('synthesis-export-btn')
        };

        // Navigation elements
        this.elements.navigation = {
            chatTab: document.querySelector('[data-view="chat"]'),
            kbTab: document.querySelector('[data-view="kb"]'),
            synthesisTab: document.querySelector('[data-view="synthesis"]')
        };

        this.log('UI elements initialized');
    }

    /**
     * Initialize component state
     */
    async initializeState() {
        await super.initializeState();
        
        // Set initial view based on URL or default
        const urlParams = new URLSearchParams(window.location.search);
        const initialView = urlParams.get('view') || 'chat';
        
        this.setState({
            activeView: initialView,
            chatState: { ...this.chatState },
            kbState: { ...this.kbState },
            synthesisState: { ...this.synthesisState }
        });

        this.log('State initialized with active view:', initialView);
    }

    /**
     * Setup event listeners for all UI components
     */
    async setupEventListeners() {
        this.log('Setting up event listeners...');

        // Use EventListenerService for comprehensive event handling
        this.eventService.setupStandardListeners(this, {
            // Navigation events
            buttons: [
                {
                    selector: this.elements.navigation.chatTab,
                    handler: () => this.switchView('chat'),
                    condition: () => this.elements.navigation.chatTab
                },
                {
                    selector: this.elements.navigation.kbTab,
                    handler: () => this.switchView('kb'),
                    condition: () => this.elements.navigation.kbTab
                },
                {
                    selector: this.elements.navigation.synthesisTab,
                    handler: () => this.switchView('synthesis'),
                    condition: () => this.elements.navigation.synthesisTab
                }
            ],

            // Chat-specific events
            inputs: [
                {
                    selector: this.elements.chat.input,
                    events: ['input'],
                    handler: () => this.handleChatInput(),
                    debounce: 100,
                    condition: () => this.elements.chat.input
                },
                {
                    selector: this.elements.chat.sessionSearch,
                    events: ['input'],
                    handler: (e) => this.filterChatSessions(e.target.value),
                    debounce: 200,
                    condition: () => this.elements.chat.sessionSearch
                },
                {
                    selector: this.elements.chat.modelSelector,
                    events: ['change'],
                    handler: () => this.updateChatModel(),
                    condition: () => this.elements.chat.modelSelector
                }
            ],

            // Knowledge Base events
            delegated: [
                {
                    container: this.elements.kb.tree,
                    selector: '*',
                    event: 'click',
                    handler: (e) => this.handleKBTreeClick(e),
                    condition: () => this.elements.kb.tree
                },
                {
                    selector: '.sample-prompt',
                    event: 'click',
                    handler: (e, target) => this.insertChatPrompt(target.dataset.prompt)
                },
                {
                    container: this.elements.chat.sessionList,
                    selector: '.session-item',
                    event: 'click',
                    handler: (e, target) => this.loadChatSession(target.dataset.sessionId),
                    condition: () => this.elements.chat.sessionList
                }
            ],

            // Keyboard shortcuts
            keyboard: [
                {
                    target: this.elements.chat.input,
                    key: 'Enter',
                    handler: () => this.handleChatSubmit(),
                    condition: (e) => !e.shiftKey && this.elements.chat.input
                },
                {
                    key: '1',
                    ctrlKey: true,
                    handler: () => this.switchView('chat')
                },
                {
                    key: '2',
                    ctrlKey: true,
                    handler: () => this.switchView('kb')
                },
                {
                    key: '3',
                    ctrlKey: true,
                    handler: () => this.switchView('synthesis')
                }
            ],

            // Custom events for inter-component communication
            customEvents: [
                {
                    event: 'view_change_requested',
                    handler: (e) => this.switchView(e.detail.view)
                },
                {
                    event: 'chat_session_updated',
                    handler: (e) => this.handleChatSessionUpdate(e.detail)
                },
                {
                    event: 'kb_item_selected',
                    handler: (e) => this.handleKBItemSelected(e.detail)
                }
            ]
        });

        this.log('Event listeners setup completed');
    }

    /**
     * Load initial data for all components
     */
    async loadInitialData() {
        this.log('Loading initial data...');

        try {
            // Load data based on active view
            switch (this.state.activeView) {
                case 'chat':
                    await this.loadChatData();
                    break;
                case 'kb':
                    await this.loadKBData();
                    break;
                case 'synthesis':
                    await this.loadSynthesisData();
                    break;
            }

            this.log('Initial data loaded successfully');
        } catch (error) {
            this.setError(error, 'loading initial data');
            throw error;
        }
    }

    /**
     * Switch between different views
     */
    async switchView(viewName) {
        if (this.state.activeView === viewName) return;

        this.log(`Switching view from ${this.state.activeView} to ${viewName}`);

        try {
            // Update view history
            this.viewHistory.push(viewName);
            if (this.viewHistory.length > this.maxHistoryLength) {
                this.viewHistory.shift();
            }

            // Hide current view
            this.hideCurrentView();

            // Update state
            this.setState({ activeView: viewName });

            // Show new view
            await this.showView(viewName);

            // Update URL without page reload
            const url = new URL(window.location);
            url.searchParams.set('view', viewName);
            window.history.pushState({ view: viewName }, '', url);

            // Dispatch view change event
            this.dispatchEvent('viewChanged', { 
                previousView: this.viewHistory[this.viewHistory.length - 2],
                currentView: viewName 
            });

            this.log(`View switched to ${viewName}`);

        } catch (error) {
            this.setError(error, `switching to ${viewName} view`);
            throw error;
        }
    }

    /**
     * Hide current view
     */
    hideCurrentView() {
        const containers = [
            this.elements.chat.container,
            this.elements.kb.container,
            this.elements.synthesis.container
        ];

        containers.forEach(container => {
            if (container) {
                container.style.display = 'none';
                container.classList.remove('active');
            }
        });

        // Update navigation tabs
        document.querySelectorAll('[data-view]').forEach(tab => {
            tab.classList.remove('active');
        });
    }

    /**
     * Show specific view
     */
    async showView(viewName) {
        let container;
        let tab;

        switch (viewName) {
            case 'chat':
                container = this.elements.chat.container;
                tab = this.elements.navigation.chatTab;
                await this.loadChatData();
                break;
            case 'kb':
                container = this.elements.kb.container;
                tab = this.elements.navigation.kbTab;
                await this.loadKBData();
                break;
            case 'synthesis':
                container = this.elements.synthesis.container;
                tab = this.elements.navigation.synthesisTab;
                await this.loadSynthesisData();
                break;
            default:
                throw new Error(`Unknown view: ${viewName}`);
        }

        if (container) {
            container.style.display = 'block';
            container.classList.add('active');
        }

        if (tab) {
            tab.classList.add('active');
        }
    }

    /**
     * Chat-specific methods
     */
    async loadChatData() {
        this.log('Loading chat data...');
        
        try {
            // Load available models
            const models = await this.apiCall('/api/chat/models', {
                action: 'load chat models',
                cache: true,
                cacheTTL: 300000 // 5 minutes
            });

            // Load chat sessions
            const sessions = await this.apiCall('/api/chat/sessions', {
                action: 'load chat sessions',
                cache: true,
                cacheTTL: 60000 // 1 minute
            });

            // Update chat state
            this.setState({
                chatState: {
                    ...this.state.chatState,
                    availableModels: models.data || [],
                    sessions: sessions.data || []
                }
            });

            this.updateChatUI();

        } catch (error) {
            this.logError('Failed to load chat data:', error);
            throw error;
        }
    }

    async handleChatSubmit() {
        const input = this.elements.chat.input;
        if (!input || !input.value.trim()) return;

        const message = input.value.trim();
        input.value = '';

        try {
            this.setLoading(true, 'Sending message...');

            const response = await this.apiCall('/api/chat/enhanced', {
                method: 'POST',
                body: {
                    message,
                    session_id: this.state.chatState.currentSessionId,
                    model: this.getSelectedModel()
                },
                action: 'send chat message'
            });

            this.handleChatResponse(response);

        } catch (error) {
            this.setError(error, 'sending chat message');
        }
    }

    /**
     * Knowledge Base specific methods
     */
    async loadKBData() {
        this.log('Loading knowledge base data...');
        
        try {
            const data = await this.apiCall('/api/kb/data', {
                action: 'load knowledge base data',
                cache: true,
                cacheTTL: 300000 // 5 minutes
            });

            this.setState({
                kbState: {
                    ...this.state.kbState,
                    data: data
                }
            });

            this.updateKBUI();

        } catch (error) {
            this.logError('Failed to load KB data:', error);
            throw error;
        }
    }

    /**
     * Synthesis specific methods
     */
    async loadSynthesisData() {
        this.log('Loading synthesis data...');
        
        try {
            const documents = await this.apiCall('/api/synthesis/documents', {
                action: 'load synthesis documents',
                cache: true,
                cacheTTL: 300000 // 5 minutes
            });

            this.setState({
                synthesisState: {
                    ...this.state.synthesisState,
                    documents: documents.data || []
                }
            });

            this.updateSynthesisUI();

        } catch (error) {
            this.logError('Failed to load synthesis data:', error);
            throw error;
        }
    }

    /**
     * UI update methods
     */
    updateChatUI() {
        // Update model selector
        if (this.elements.chat.modelSelector && this.state.chatState.availableModels.length > 0) {
            this.elements.chat.modelSelector.innerHTML = this.state.chatState.availableModels
                .map(model => `<option value="${model.name}">${model.display_name || model.name}</option>`)
                .join('');
        }

        // Update session list
        if (this.elements.chat.sessionList && this.state.chatState.sessions.length > 0) {
            this.elements.chat.sessionList.innerHTML = this.state.chatState.sessions
                .map(session => this.renderChatSession(session))
                .join('');
        }
    }

    updateKBUI() {
        if (!this.state.kbState.data) return;

        // Update knowledge base tree and content
        if (this.elements.kb.tree) {
            this.elements.kb.tree.innerHTML = this.renderKBTree(this.state.kbState.data);
        }
    }

    updateSynthesisUI() {
        if (!this.state.synthesisState.documents) return;

        // Update synthesis document list
        if (this.elements.synthesis.documentList) {
            this.elements.synthesis.documentList.innerHTML = this.state.synthesisState.documents
                .map(doc => this.renderSynthesisDocument(doc))
                .join('');
        }
    }

    /**
     * Utility methods
     */
    getSelectedModel() {
        return this.elements.chat.modelSelector?.value || 'llama3.2:latest';
    }

    renderChatSession(session) {
        return `
            <div class="session-item" data-session-id="${session.id}">
                <div class="session-title">${session.title || 'Untitled Session'}</div>
                <div class="session-meta">
                    <span class="session-date">${new Date(session.created_at).toLocaleDateString()}</span>
                    <span class="session-messages">${session.message_count || 0} messages</span>
                </div>
            </div>
        `;
    }

    renderKBTree(data) {
        // Simplified KB tree rendering - would be more complex in real implementation
        return Object.keys(data).map(category => `
            <div class="kb-category" data-category="${category}">
                <div class="kb-category-header">${category}</div>
                <div class="kb-category-items">
                    ${data[category].map(item => `
                        <div class="kb-item" data-item-id="${item.id}">${item.title}</div>
                    `).join('')}
                </div>
            </div>
        `).join('');
    }

    renderSynthesisDocument(doc) {
        return `
            <div class="synthesis-document" data-doc-id="${doc.id}">
                <div class="synthesis-title">${doc.title}</div>
                <div class="synthesis-meta">
                    <span class="synthesis-category">${doc.category}</span>
                    <span class="synthesis-items">${doc.item_count} items</span>
                </div>
            </div>
        `;
    }

    /**
     * Get current view
     */
    getCurrentView() {
        return this.state.activeView;
    }

    /**
     * Get view history
     */
    getViewHistory() {
        return [...this.viewHistory];
    }

    /**
     * Go back to previous view
     */
    goBack() {
        if (this.viewHistory.length > 1) {
            const previousView = this.viewHistory[this.viewHistory.length - 2];
            this.switchView(previousView);
        }
    }
}

// Make available globally
window.CoreUIManager = CoreUIManager;

// Export for module systems
if (typeof module !== 'undefined' && module.exports) {
    module.exports = CoreUIManager;
}