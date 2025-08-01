/* V2 COMPONENTCOORDINATOR.JS - DISPLAY COMPONENT COORDINATION SYSTEM */

/**
 * DisplayComponentCoordinator - Central coordination system for display components
 * 
 * ARCHITECTURE:
 * - Manages component registration and lifecycle
 * - Coordinates events between components to prevent conflicts
 * - Provides centralized state management for UI components
 * - Handles component initialization order and dependencies
 * - Implements event batching and throttling for performance
 */
class DisplayComponentCoordinator {
    constructor() {
        this.components = new Map();
        this.eventQueue = [];
        this.isProcessing = false;
        this.eventBatch = [];
        this.batchTimeout = null;
        this.batchDelay = 50; // 50ms batching delay
        
        // Component states
        this.componentStates = new Map();
        this.componentDependencies = new Map();
        this.initializationOrder = [];
        
        // Event coordination
        this.eventCoordination = {
            'phase_start': ['PhaseDisplayManager', 'ProgressDisplayManager'],
            'phase_complete': ['PhaseDisplayManager', 'ProgressDisplayManager'],
            'phase_error': ['PhaseDisplayManager', 'ProgressDisplayManager'],
            'progress_update': ['ProgressDisplayManager', 'PhaseDisplayManager'],
            'log': ['LiveLogsManager', 'TaskDisplayManager'],
            'agent_status_update': ['PhaseDisplayManager', 'TaskDisplayManager', 'ProgressDisplayManager'],
            'task_started': ['TaskDisplayManager'],
            'task_completed': ['TaskDisplayManager'],
            'task_error': ['TaskDisplayManager']
        };
        
        this.init();
    }
    
    init() {
        this.setupEventListeners();
        this.startEventProcessing();
        console.log('🎛️ DisplayComponentCoordinator initialized');
    }
    
    setupEventListeners() {
        // Use centralized EventListenerService
        const customEvents = [
            {
                event: 'component_registered',
                handler: (e) => this.handleComponentRegistered(e.detail)
            },
            {
                event: 'component_destroyed',
                handler: (e) => this.handleComponentDestroyed(e.detail)
            }
        ];

        // Add coordinated events dynamically
        Object.keys(this.eventCoordination).forEach(eventType => {
            customEvents.push({
                event: eventType,
                handler: (e) => this.coordinateEvent(eventType, e.detail)
            });
        });

        EventListenerService.setupStandardListeners(this, {
            customEvents: customEvents
        });
    }
    
    // === COMPONENT REGISTRATION ===
    
    registerComponent(name, component, options = {}) {
        if (this.components.has(name)) {
            console.warn(`⚠️ Component ${name} already registered, replacing...`);
        }
        
        const componentInfo = {
            name: name,
            instance: component,
            dependencies: options.dependencies || [],
            priority: options.priority || 50,
            initialized: false,
            lastUpdate: null,
            eventHandlers: new Set(),
            ...options
        };
        
        this.components.set(name, componentInfo);
        this.componentStates.set(name, 'registered');
        
        // Set up dependencies
        if (componentInfo.dependencies.length > 0) {
            this.componentDependencies.set(name, componentInfo.dependencies);
        }
        
        // Add to initialization order based on priority
        this.updateInitializationOrder();
        
        console.log(`📋 Registered component: ${name}`, componentInfo);
        
        // Emit registration event
        this.emitEvent('component_registered', { name, component: componentInfo });
        
        return componentInfo;
    }
    
    unregisterComponent(name) {
        const component = this.components.get(name);
        if (!component) return false;
        
        // Cleanup component
        if (component.instance && typeof component.instance.cleanup === 'function') {
            component.instance.cleanup();
        }
        
        this.components.delete(name);
        this.componentStates.delete(name);
        this.componentDependencies.delete(name);
        
        // Update initialization order
        this.updateInitializationOrder();
        
        console.log(`🗑️ Unregistered component: ${name}`);
        
        // Emit destruction event
        this.emitEvent('component_destroyed', { name });
        
        return true;
    }
    
    updateInitializationOrder() {
        // Sort components by priority and dependencies
        const components = Array.from(this.components.values());
        
        // Topological sort considering dependencies
        this.initializationOrder = this.topologicalSort(components);
    }
    
    topologicalSort(components) {
        const sorted = [];
        const visited = new Set();
        const visiting = new Set();
        
        const visit = (component) => {
            if (visiting.has(component.name)) {
                console.warn(`⚠️ Circular dependency detected for component: ${component.name}`);
                return;
            }
            
            if (visited.has(component.name)) {
                return;
            }
            
            visiting.add(component.name);
            
            // Visit dependencies first
            const dependencies = this.componentDependencies.get(component.name) || [];
            dependencies.forEach(depName => {
                const depComponent = this.components.get(depName);
                if (depComponent) {
                    visit(depComponent);
                }
            });
            
            visiting.delete(component.name);
            visited.add(component.name);
            sorted.push(component);
        };
        
        // Sort by priority first, then apply topological sort
        const prioritySorted = components.sort((a, b) => b.priority - a.priority);
        prioritySorted.forEach(visit);
        
        return sorted;
    }
    
    // === EVENT COORDINATION ===
    
    coordinateEvent(eventType, eventData) {
        const targetComponents = this.eventCoordination[eventType];
        if (!targetComponents) return;
        
        // Add to event batch
        this.eventBatch.push({
            type: eventType,
            data: eventData,
            targets: targetComponents,
            timestamp: Date.now()
        });
        
        // Schedule batch processing
        this.scheduleBatchProcessing();
    }
    
    scheduleBatchProcessing() {
        if (this.batchTimeout) {
            clearTimeout(this.batchTimeout);
        }
        
        this.batchTimeout = setTimeout(() => {
            this.processBatch();
        }, this.batchDelay);
    }
    
    processBatch() {
        if (this.eventBatch.length === 0) return;
        
        const batch = [...this.eventBatch];
        this.eventBatch = [];
        
        // Performance optimization: measure batch processing time
        const startTime = performance.now();
        
        // Group events by type and target
        const groupedEvents = this.groupEventsByTarget(batch);
        
        // Process events in coordination order
        this.processGroupedEvents(groupedEvents);
        
        // Record performance metrics
        const processingTime = performance.now() - startTime;
        if (window.performanceMonitor) {
            window.performanceMonitor.recordLatency('component_batch_processing', processingTime);
        }
        
        // Emit performance event for monitoring
        this.emitEvent('component_batch_processed', {
            batchSize: batch.length,
            processingTime: processingTime,
            eventTypes: [...new Set(batch.map(e => e.type))]
        });
    }
    
    groupEventsByTarget(events) {
        const grouped = new Map();
        
        events.forEach(event => {
            event.targets.forEach(target => {
                if (!grouped.has(target)) {
                    grouped.set(target, []);
                }
                grouped.get(target).push(event);
            });
        });
        
        return grouped;
    }
    
    processGroupedEvents(groupedEvents) {
        // Process events in component initialization order
        this.initializationOrder.forEach(componentInfo => {
            const events = groupedEvents.get(componentInfo.name);
            if (!events || events.length === 0) return;
            
            this.processComponentEvents(componentInfo, events);
        });
    }
    
    processComponentEvents(componentInfo, events) {
        if (!componentInfo.instance) return;
        
        // Deduplicate events of the same type
        const deduplicatedEvents = this.deduplicateEvents(events);
        
        // Process each event
        deduplicatedEvents.forEach(event => {
            this.processComponentEvent(componentInfo, event);
        });
        
        // Update component state
        componentInfo.lastUpdate = Date.now();
    }
    
    deduplicateEvents(events) {
        const eventMap = new Map();
        
        events.forEach(event => {
            const key = `${event.type}_${JSON.stringify(event.data)}`;
            if (!eventMap.has(key) || eventMap.get(key).timestamp < event.timestamp) {
                eventMap.set(key, event);
            }
        });
        
        return Array.from(eventMap.values());
    }
    
    processComponentEvent(componentInfo, event) {
        try {
            // Emit coordinated event to component
            this.emitEventToComponent(componentInfo, event);
            
            // Track event handling
            componentInfo.eventHandlers.add(event.type);
            
        } catch (error) {
            console.error(`❌ Error processing event ${event.type} for component ${componentInfo.name}:`, error);
        }
    }
    
    emitEventToComponent(componentInfo, event) {
        // Create a coordinated event that includes coordination metadata
        const coordinatedEvent = new CustomEvent(`coordinated_${event.type}`, {
            detail: {
                ...event.data,
                _coordination: {
                    originalType: event.type,
                    targetComponent: componentInfo.name,
                    timestamp: event.timestamp,
                    batchId: this.generateBatchId()
                }
            }
        });
        
        // Emit to the component's element or document
        const target = componentInfo.instance.element || document;
        target.dispatchEvent(coordinatedEvent);
    }
    
    // === COMPONENT STATE MANAGEMENT ===
    
    getComponentState(name) {
        return this.componentStates.get(name) || 'unknown';
    }
    
    setComponentState(name, state) {
        const oldState = this.componentStates.get(name);
        this.componentStates.set(name, state);
        
        console.log(`🔄 Component ${name} state: ${oldState} → ${state}`);
        
        // Emit state change event
        this.emitEvent('component_state_changed', {
            name,
            oldState,
            newState: state
        });
    }
    
    initializeComponents() {
        console.log('🚀 Initializing components in coordination order...');
        
        this.initializationOrder.forEach(componentInfo => {
            this.initializeComponent(componentInfo);
        });
    }
    
    initializeComponent(componentInfo) {
        if (componentInfo.initialized) return;
        
        // Check dependencies
        const dependencies = this.componentDependencies.get(componentInfo.name) || [];
        const unmetDependencies = dependencies.filter(dep => {
            const depComponent = this.components.get(dep);
            return !depComponent || !depComponent.initialized;
        });
        
        if (unmetDependencies.length > 0) {
            console.warn(`⚠️ Component ${componentInfo.name} has unmet dependencies: ${unmetDependencies.join(', ')}`);
            return;
        }
        
        try {
            // Initialize component if it has an init method
            if (componentInfo.instance && typeof componentInfo.instance.init === 'function') {
                componentInfo.instance.init();
            }
            
            componentInfo.initialized = true;
            this.setComponentState(componentInfo.name, 'initialized');
            
            console.log(`✅ Initialized component: ${componentInfo.name}`);
            
        } catch (error) {
            console.error(`❌ Failed to initialize component ${componentInfo.name}:`, error);
            this.setComponentState(componentInfo.name, 'error');
        }
    }
    
    // === EVENT PROCESSING ===
    
    startEventProcessing() {
        // Start periodic event queue processing
        setInterval(() => {
            this.processEventQueue();
        }, 100); // Process every 100ms
    }
    
    processEventQueue() {
        if (this.isProcessing || this.eventQueue.length === 0) return;
        
        this.isProcessing = true;
        
        try {
            while (this.eventQueue.length > 0) {
                const event = this.eventQueue.shift();
                this.processQueuedEvent(event);
            }
        } catch (error) {
            console.error('❌ Error processing event queue:', error);
        } finally {
            this.isProcessing = false;
        }
    }
    
    processQueuedEvent(event) {
        // Process individual queued event
        const { type, data, timestamp } = event;
        
        // Check if event is still relevant (not too old)
        const age = Date.now() - timestamp;
        if (age > 5000) { // 5 seconds
            console.warn(`⚠️ Dropping old event: ${type} (${age}ms old)`);
            return;
        }
        
        // Emit the event
        this.emitEvent(type, data);
    }
    
    // === UTILITY METHODS ===
    
    emitEvent(type, data) {
        const event = new CustomEvent(type, { detail: data });
        document.dispatchEvent(event);
    }
    
    generateBatchId() {
        return `batch_${Date.now()}_${Math.random().toString(36).substr(2, 9)}`;
    }
    
    handleComponentRegistered(data) {
        console.log(`📋 Component registered: ${data.name}`);
    }
    
    handleComponentDestroyed(data) {
        console.log(`🗑️ Component destroyed: ${data.name}`);
    }
    
    // === PUBLIC API ===
    
    getComponent(name) {
        return this.components.get(name);
    }
    
    getAllComponents() {
        return Array.from(this.components.values());
    }
    
    getComponentStatistics() {
        const stats = {
            total: this.components.size,
            initialized: 0,
            error: 0,
            byState: {}
        };
        
        this.componentStates.forEach((state, name) => {
            stats.byState[state] = (stats.byState[state] || 0) + 1;
            
            if (state === 'initialized') stats.initialized++;
            if (state === 'error') stats.error++;
        });
        
        return stats;
    }
    
    getEventStatistics() {
        return {
            queueLength: this.eventQueue.length,
            batchLength: this.eventBatch.length,
            isProcessing: this.isProcessing,
            coordinatedEvents: Object.keys(this.eventCoordination).length
        };
    }
    
    // === DEBUGGING AND MONITORING ===
    
    enableDebugMode() {
        this.debugMode = true;
        console.log('🐛 DisplayComponentCoordinator debug mode enabled');
        
        // Add debug event listeners
        Object.keys(this.eventCoordination).forEach(eventType => {
            document.addEventListener(eventType, (event) => {
                console.log(`🎯 Event: ${eventType}`, event.detail);
            });
        });
    }
    
    disableDebugMode() {
        this.debugMode = false;
        console.log('🐛 DisplayComponentCoordinator debug mode disabled');
    }
    
    logComponentStatus() {
        console.log('📊 Component Status Report:');
        console.table(Array.from(this.components.entries()).map(([name, info]) => ({
            name,
            state: this.componentStates.get(name),
            initialized: info.initialized,
            priority: info.priority,
            dependencies: info.dependencies.join(', ') || 'none',
            lastUpdate: info.lastUpdate ? new Date(info.lastUpdate).toLocaleTimeString() : 'never'
        })));
    }
    
    // === CLEANUP ===
    
    destroy() {
        // Cleanup all components
        this.components.forEach((componentInfo, name) => {
            this.unregisterComponent(name);
        });
        
        // Clear timers
        if (this.batchTimeout) {
            clearTimeout(this.batchTimeout);
        }
        
        // Clear data structures
        this.components.clear();
        this.componentStates.clear();
        this.componentDependencies.clear();
        this.eventQueue = [];
        this.eventBatch = [];
        
        console.log('🧹 DisplayComponentCoordinator destroyed');
    }
}

// Make globally available
window.DisplayComponentCoordinator = DisplayComponentCoordinator;

// Auto-initialize global coordinator
if (!window.displayCoordinator) {
    window.displayCoordinator = new DisplayComponentCoordinator();
}