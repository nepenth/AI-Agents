/**
 * Centralized Event Listener Service
 * Eliminates duplicate setupEventListeners() methods across 15 files
 * Provides modern, efficient, and memory-safe event handling patterns
 * 
 * Design Principles:
 * - Event delegation for performance and dynamic content
 * - Automatic cleanup tracking for memory leak prevention
 * - Debouncing/throttling for performance optimization
 * - Type-safe event handling with validation
 * - Consistent error handling and logging
 */
class EventListenerService {
    constructor() {
        this.eventRegistry = new Map(); // Track all registered events
        this.delegatedEvents = new Map(); // Track delegated events
        this.debounceTimers = new Map(); // Track debounce timers
        this.throttleTimers = new Map(); // Track throttle timers
    }

    /**
     * Register standard event listeners for a component
     * @param {Object} component - Component instance
     * @param {Object} config - Event configuration
     */
    static setupStandardListeners(component, config = {}) {
        const service = EventListenerService.getInstance();
        return service.setupComponentListeners(component, config);
    }

    /**
     * Setup event listeners for a component with automatic cleanup tracking
     * @param {Object} component - Component instance
     * @param {Object} config - Event configuration
     */
    setupComponentListeners(component, config) {
        const componentName = component.constructor.name;
        console.log(`🎧 Setting up event listeners for ${componentName}`);

        // Initialize event tracking for component
        if (!component.eventListeners) {
            component.eventListeners = [];
        }

        // Process different event types
        this.setupButtonEvents(component, config.buttons || []);
        this.setupFormEvents(component, config.forms || []);
        this.setupInputEvents(component, config.inputs || []);
        this.setupCustomEvents(component, config.customEvents || []);
        this.setupKeyboardEvents(component, config.keyboard || []);
        this.setupModalEvents(component, config.modals || []);
        this.setupDelegatedEvents(component, config.delegated || []);

        // Setup component-specific events
        this.setupComponentSpecificEvents(component, config);

        console.log(`✅ Event listeners setup complete for ${componentName}`);
        return this;
    }

    /**
     * Setup button click events with automatic debouncing
     * @param {Object} component - Component instance
     * @param {Array} buttonConfigs - Button configurations
     */
    setupButtonEvents(component, buttonConfigs) {
        buttonConfigs.forEach(config => {
            const {
                selector,
                handler,
                debounce = 300,
                preventDefault = true,
                stopPropagation = false,
                condition = null
            } = config;

            const elements = this.getElements(selector);
            elements.forEach(element => {
                const wrappedHandler = (e) => {
                    if (preventDefault) e.preventDefault();
                    if (stopPropagation) e.stopPropagation();
                    
                    // Check condition if provided
                    if (condition && !condition(e, element)) return;

                    // Apply debouncing if specified
                    if (debounce > 0) {
                        this.debounce(`${component.constructor.name}-${selector}`, () => {
                            handler.call(component, e, element);
                        }, debounce);
                    } else {
                        handler.call(component, e, element);
                    }
                };

                this.addTrackedListener(component, element, 'click', wrappedHandler);
            });
        });
    }

    /**
     * Setup form events with validation and submission handling
     * @param {Object} component - Component instance
     * @param {Array} formConfigs - Form configurations
     */
    setupFormEvents(component, formConfigs) {
        formConfigs.forEach(config => {
            const {
                selector,
                onSubmit,
                onReset,
                validation = null,
                preventDefault = true
            } = config;

            const forms = this.getElements(selector);
            forms.forEach(form => {
                if (onSubmit) {
                    const submitHandler = async (e) => {
                        if (preventDefault) e.preventDefault();
                        
                        // Run validation if provided
                        if (validation && !validation(form)) {
                            return;
                        }

                        try {
                            await onSubmit.call(component, e, form);
                        } catch (error) {
                            console.error(`Form submission error in ${component.constructor.name}:`, error);
                        }
                    };

                    this.addTrackedListener(component, form, 'submit', submitHandler);
                }

                if (onReset) {
                    this.addTrackedListener(component, form, 'reset', (e) => {
                        onReset.call(component, e, form);
                    });
                }
            });
        });
    }

    /**
     * Setup input events with debouncing and validation
     * @param {Object} component - Component instance
     * @param {Array} inputConfigs - Input configurations
     */
    setupInputEvents(component, inputConfigs) {
        inputConfigs.forEach(config => {
            const {
                selector,
                events = ['input'],
                handler,
                debounce = 150,
                validation = null,
                transform = null
            } = config;

            const inputs = this.getElements(selector);
            inputs.forEach(input => {
                events.forEach(eventType => {
                    const wrappedHandler = (e) => {
                        let value = e.target.value;
                        
                        // Apply transformation if provided
                        if (transform) {
                            value = transform(value);
                            if (value !== e.target.value) {
                                e.target.value = value;
                            }
                        }

                        // Run validation if provided
                        if (validation && !validation(value, input)) {
                            return;
                        }

                        // Apply debouncing for input events
                        if (eventType === 'input' && debounce > 0) {
                            this.debounce(`${component.constructor.name}-${selector}-${eventType}`, () => {
                                handler.call(component, e, input, value);
                            }, debounce);
                        } else {
                            handler.call(component, e, input, value);
                        }
                    };

                    this.addTrackedListener(component, input, eventType, wrappedHandler);
                });
            });
        });
    }

    /**
     * Setup custom document/window events
     * @param {Object} component - Component instance
     * @param {Array} customConfigs - Custom event configurations
     */
    setupCustomEvents(component, customConfigs) {
        customConfigs.forEach(config => {
            const {
                target = document,
                event,
                handler,
                throttle = 0,
                condition = null
            } = config;

            const wrappedHandler = (e) => {
                // Check condition if provided
                if (condition && !condition(e)) return;

                // Apply throttling if specified
                if (throttle > 0) {
                    this.throttle(`${component.constructor.name}-${event}`, () => {
                        handler.call(component, e);
                    }, throttle);
                } else {
                    handler.call(component, e);
                }
            };

            this.addTrackedListener(component, target, event, wrappedHandler);
        });
    }

    /**
     * Setup keyboard event handlers with key combinations
     * @param {Object} component - Component instance
     * @param {Array} keyboardConfigs - Keyboard configurations
     */
    setupKeyboardEvents(component, keyboardConfigs) {
        keyboardConfigs.forEach(config => {
            const {
                target = document,
                key,
                ctrlKey = false,
                shiftKey = false,
                altKey = false,
                handler,
                preventDefault = true
            } = config;

            const keyHandler = (e) => {
                const keyMatch = Array.isArray(key) ? key.includes(e.key) : e.key === key;
                
                if (keyMatch && 
                    e.ctrlKey === ctrlKey && 
                    e.shiftKey === shiftKey && 
                    e.altKey === altKey) {
                    
                    if (preventDefault) e.preventDefault();
                    handler.call(component, e);
                }
            };

            this.addTrackedListener(component, target, 'keydown', keyHandler);
        });
    }

    /**
     * Setup modal event handlers
     * @param {Object} component - Component instance
     * @param {Array} modalConfigs - Modal configurations
     */
    setupModalEvents(component, modalConfigs) {
        modalConfigs.forEach(config => {
            const {
                triggerSelector,
                modalSelector,
                closeSelector,
                overlaySelector,
                onOpen,
                onClose,
                closeOnEscape = true,
                closeOnOverlay = true
            } = config;

            // Modal trigger
            if (triggerSelector && onOpen) {
                this.setupButtonEvents(component, [{
                    selector: triggerSelector,
                    handler: onOpen,
                    preventDefault: true,
                    stopPropagation: true
                }]);
            }

            // Close button
            if (closeSelector && onClose) {
                this.setupButtonEvents(component, [{
                    selector: closeSelector,
                    handler: onClose,
                    preventDefault: true,
                    stopPropagation: true
                }]);
            }

            // Overlay click
            if (overlaySelector && closeOnOverlay && onClose) {
                this.setupButtonEvents(component, [{
                    selector: overlaySelector,
                    handler: (e) => {
                        if (e.target === e.currentTarget) {
                            onClose.call(component, e);
                        }
                    }
                }]);
            }

            // Escape key
            if (closeOnEscape && onClose) {
                this.setupKeyboardEvents(component, [{
                    key: 'Escape',
                    handler: onClose
                }]);
            }
        });
    }

    /**
     * Setup delegated events for dynamic content
     * @param {Object} component - Component instance
     * @param {Array} delegatedConfigs - Delegated event configurations
     */
    setupDelegatedEvents(component, delegatedConfigs) {
        delegatedConfigs.forEach(config => {
            const {
                container = document,
                selector,
                event,
                handler,
                condition = null
            } = config;

            const delegatedHandler = (e) => {
                const target = e.target.closest(selector);
                if (!target) return;

                // Check condition if provided
                if (condition && !condition(e, target)) return;

                handler.call(component, e, target);
            };

            this.addTrackedListener(component, container, event, delegatedHandler);
        });
    }

    /**
     * Setup component-specific event patterns
     * @param {Object} component - Component instance
     * @param {Object} config - Configuration
     */
    setupComponentSpecificEvents(component, config) {
        const componentName = component.constructor.name;

        switch (componentName) {
            case 'SimplifiedLogsManager':
                this.setupLogsManagerEvents(component, config);
                break;
            case 'ChatManager':
                this.setupChatManagerEvents(component, config);
                break;
            case 'AgentControlsManager':
                this.setupAgentControlsEvents(component, config);
                break;
            case 'KnowledgeBaseManager':
                this.setupKBManagerEvents(component, config);
                break;
            case 'ThemeSettingsPanel':
                this.setupThemeSettingsEvents(component, config);
                break;
            case 'ProgressDisplayManager':
                this.setupProgressDisplayEvents(component, config);
                break;
            case 'TaskDisplayManager':
                this.setupTaskDisplayEvents(component, config);
                break;
            case 'GPUStatusManager':
                this.setupGPUStatusEvents(component, config);
                break;
            case 'PhaseDisplayManager':
                this.setupPhaseDisplayEvents(component, config);
                break;
            case 'ComponentCoordinator':
                this.setupComponentCoordinatorEvents(component, config);
                break;
            case 'EnhancedSocketIOManager':
                this.setupSocketIOManagerEvents(component, config);
                break;
            case 'HistoricalTasksManager':
                this.setupHistoricalTasksEvents(component, config);
                break;
            case 'UtilityHandlers':
                this.setupUtilityHandlersEvents(component, config);
                break;
            case 'ThemeManager':
                this.setupThemeManagerEvents(component, config);
                break;
            case 'StaticPagesManager':
                this.setupStaticPagesEvents(component, config);
                break;
        }
    }

    /**
     * Component-specific event setups
     */
    setupLogsManagerEvents(component, config) {
        // Auto-scroll management
        if (component.logsContainer) {
            this.addTrackedListener(component, component.logsContainer, 'scroll', 
                this.throttle('logs-scroll', () => {
                    const { scrollTop, scrollHeight, clientHeight } = component.logsContainer;
                    component.autoScroll = scrollTop + clientHeight >= scrollHeight - 10;
                }, 100)
            );

            this.addTrackedListener(component, component.logsContainer, 'dblclick', () => {
                component.autoScroll = !component.autoScroll;
                if (component.autoScroll) {
                    component.scrollToBottom();
                }
            });
        }

        // SocketIO events
        this.setupCustomEvents(component, [
            { event: 'socketio-ready', handler: () => component.initializeSocketIOListeners() },
            { event: 'socketio-failed', handler: () => component.startEmergencyPolling() }
        ]);

        // Keyboard shortcuts
        this.setupKeyboardEvents(component, [
            { key: 'l', ctrlKey: true, handler: () => component.clearLogs() }
        ]);
    }

    setupChatManagerEvents(component, config) {
        // Chat input with Enter key handling
        this.setupInputEvents(component, [
            {
                selector: '#v2-chat-input',
                events: ['input'],
                handler: () => {
                    component.updateCharCount();
                    component.updateSendButton();
                }
            }
        ]);

        this.setupKeyboardEvents(component, [
            {
                target: component.elements.chatInput,
                key: 'Enter',
                handler: (e) => {
                    if (!e.shiftKey) {
                        component.handleChatSubmit();
                    }
                }
            }
        ]);

        // Delegated events for dynamic content
        this.setupDelegatedEvents(component, [
            {
                selector: '.sample-prompt',
                event: 'click',
                handler: (e, target) => {
                    const prompt = target.dataset.prompt;
                    if (prompt) component.insertPrompt(prompt);
                }
            },
            {
                selector: '.session-item',
                event: 'click',
                handler: (e, target) => {
                    const sessionId = target.dataset.sessionId;
                    if (sessionId) component.loadSession(sessionId);
                }
            }
        ]);
    }

    setupAgentControlsEvents(component, config) {
        // Agent status updates
        this.setupCustomEvents(component, [
            { event: 'agent_status_update', handler: (e) => component.updateStatus(e.detail) },
            { event: 'agent_run_completed', handler: (e) => component.handleRunCompleted(e.detail) },
            { event: 'agent_error', handler: (e) => component.handleAgentError(e.detail) },
            { event: 'preferences-updated', handler: (e) => component.handlePreferencesUpdate(e.detail) }
        ]);
    }

    setupKBManagerEvents(component, config) {
        // Knowledge base specific events handled by standard listeners
        // No additional setup needed beyond what's configured in setupEventListeners
    }

    setupThemeSettingsEvents(component, config) {
        // Theme settings specific events handled by standard listeners
        // No additional setup needed beyond what's configured in setupEventListeners
    }

    setupProgressDisplayEvents(component, config) {
        // Progress display specific events handled by standard listeners
        // No additional setup needed beyond what's configured in setupEventListeners
    }

    setupTaskDisplayEvents(component, config) {
        // Task display specific events handled by standard listeners
        // No additional setup needed beyond what's configured in setupEventListeners
    }

    setupGPUStatusEvents(component, config) {
        // GPU status specific events handled by standard listeners
        // No additional setup needed beyond what's configured in setupEventListeners
    }

    setupPhaseDisplayEvents(component, config) {
        // Phase display specific events handled by standard listeners
        // No additional setup needed beyond what's configured in setupEventListeners
    }

    setupComponentCoordinatorEvents(component, config) {
        // Component coordinator specific events handled by standard listeners
        // No additional setup needed beyond what's configured in setupEventListeners
    }

    setupSocketIOManagerEvents(component, config) {
        // SocketIO manager specific events handled by standard listeners
        // No additional setup needed beyond what's configured in setupEventListeners
    }

    setupHistoricalTasksEvents(component, config) {
        // Historical tasks specific events handled by standard listeners
        // No additional setup needed beyond what's configured in setupEventListeners
    }

    setupUtilityHandlersEvents(component, config) {
        // Utility handlers specific events handled by standard listeners
        // No additional setup needed beyond what's configured in setupEventListeners
    }

    setupThemeManagerEvents(component, config) {
        // Theme manager specific events handled by standard listeners
        // No additional setup needed beyond what's configured in setupEventListeners
    }

    setupStaticPagesEvents(component, config) {
        // Static pages specific events handled by standard listeners
        // No additional setup needed beyond what's configured in setupEventListeners
    }

    /**
     * Utility methods
     */
    getElements(selector) {
        if (typeof selector === 'string') {
            return Array.from(document.querySelectorAll(selector));
        } else if (selector instanceof Element) {
            return [selector];
        } else if (selector instanceof NodeList || Array.isArray(selector)) {
            return Array.from(selector);
        }
        return [];
    }

    addTrackedListener(component, element, event, handler, options = {}) {
        element.addEventListener(event, handler, options);
        
        // Track for cleanup
        component.eventListeners.push({
            element,
            event,
            handler,
            options
        });
    }

    debounce(key, func, delay) {
        if (this.debounceTimers.has(key)) {
            clearTimeout(this.debounceTimers.get(key));
        }
        
        const timer = setTimeout(() => {
            func();
            this.debounceTimers.delete(key);
        }, delay);
        
        this.debounceTimers.set(key, timer);
    }

    throttle(key, func, delay) {
        if (this.throttleTimers.has(key)) {
            return;
        }
        
        func();
        
        const timer = setTimeout(() => {
            this.throttleTimers.delete(key);
        }, delay);
        
        this.throttleTimers.set(key, timer);
    }

    /**
     * Cleanup all tracked events for a component
     * @param {Object} component - Component instance
     */
    static cleanup(component) {
        const service = EventListenerService.getInstance();
        service.cleanupComponent(component);
    }

    cleanupComponent(component) {
        if (component.eventListeners) {
            component.eventListeners.forEach(({ element, event, handler, options }) => {
                element.removeEventListener(event, handler, options);
            });
            component.eventListeners = [];
        }

        // Clear component-specific timers
        const componentName = component.constructor.name;
        for (const [key, timer] of this.debounceTimers.entries()) {
            if (key.startsWith(componentName)) {
                clearTimeout(timer);
                this.debounceTimers.delete(key);
            }
        }
        
        for (const [key, timer] of this.throttleTimers.entries()) {
            if (key.startsWith(componentName)) {
                clearTimeout(timer);
                this.throttleTimers.delete(key);
            }
        }
    }

    /**
     * Singleton pattern
     */
    static getInstance() {
        if (!EventListenerService.instance) {
            EventListenerService.instance = new EventListenerService();
        }
        return EventListenerService.instance;
    }
}

// Make available globally
window.EventListenerService = EventListenerService;

// Export for module systems
if (typeof module !== 'undefined' && module.exports) {
    module.exports = EventListenerService;
}