# Frontend Architecture Guide

## 🏗️ **Overview**

The Knowledge Base Agent frontend has been transformed into a modern, consolidated architecture following service-oriented design principles. This guide provides comprehensive documentation for developers and AI agents working with the system.

## 🎯 **Architectural Principles**

### **1. Service-Oriented Architecture**
The frontend is built around 4 core utility services that provide comprehensive functionality:
- **DurationFormatter**: Centralized time formatting and display
- **CleanupService**: Resource management and memory safety
- **EventListenerService**: Modern event handling with delegation and optimization
- **EnhancedAPIService**: Enterprise-grade API communication with retry logic and caching

### **2. Consolidated Manager Pattern**
Complex functionality is organized into 5 consolidated managers:
- **CoreUIManager**: Main UI interactions (chat, knowledge base, synthesis)
- **UnifiedDisplayManager**: All display components (phases, progress, tasks)
- **UnifiedConnectionManager**: Connection management (SocketIO, API, health checks)
- **AgentSystemManager**: Agent operations (control, state, execution)
- **BaseManager**: Foundation class providing common functionality

### **3. Template Method Pattern**
All managers follow a consistent initialization pattern defined in BaseManager:
```javascript
async init() {
    await this.validateDependencies();
    await this.initializeElements();
    await this.initializeState();
    await this.setupEventListeners();
    await this.loadInitialData();
    await this.finalizeInitialization();
}
```

### **4. Automatic Service Integration**
All managers automatically integrate with core services through BaseManager:
```javascript
constructor(options = {}) {
    this.durationFormatter = window.DurationFormatter;
    this.cleanupService = window.CleanupService;
    this.eventService = window.EventListenerService;
    this.apiService = window.apiService;
}
```

## 🔧 **Core Services**

### **DurationFormatter Service**
**Purpose**: Centralized time formatting with advanced features
**Location**: `knowledge_base_agent/static/v2/js/durationFormatter.js`

**Key Methods**:
```javascript
// Format milliseconds to human-readable time
DurationFormatter.format(milliseconds, options)

// Format seconds input
DurationFormatter.formatSeconds(seconds, options)

// Format minutes with sub-minute precision
DurationFormatter.formatMinutes(minutes, options)

// Format ETC with prefix
DurationFormatter.formatETC(milliseconds, options)

// Format elapsed time
DurationFormatter.formatElapsed(milliseconds, options)
```

**Usage Example**:
```javascript
const formatted = DurationFormatter.format(125000); // "2m 5s"
const etc = DurationFormatter.formatETC(30000); // "ETC: 30s"
```

### **CleanupService**
**Purpose**: Comprehensive resource cleanup with component-specific intelligence
**Location**: `knowledge_base_agent/static/v2/js/cleanupService.js`

**Key Methods**:
```javascript
// Comprehensive component cleanup
CleanupService.cleanup(component, options)

// Add tracked event listener
CleanupService.addEventListenerWithCleanup(component, element, event, handler)

// Add tracked timeout
CleanupService.setTimeoutWithCleanup(component, callback, delay)

// Add tracked interval
CleanupService.setIntervalWithCleanup(component, callback, delay)
```

**Usage Example**:
```javascript
cleanup() {
    CleanupService.cleanup(this); // Automatic comprehensive cleanup
}
```

### **EventListenerService**
**Purpose**: Modern event handling with delegation, debouncing, and throttling
**Location**: `knowledge_base_agent/static/v2/js/eventListenerService.js`

**Key Methods**:
```javascript
// Setup standard event listeners
EventListenerService.setupStandardListeners(component, config)

// Cleanup component events
EventListenerService.cleanup(component)
```

**Usage Example**:
```javascript
EventListenerService.setupStandardListeners(this, {
    buttons: [
        { selector: '#btn', handler: this.handleClick, debounce: 300 }
    ],
    inputs: [
        { selector: '#input', handler: this.handleInput, debounce: 150 }
    ],
    keyboard: [
        { key: 'Enter', handler: this.handleSubmit }
    ]
});
```

### **EnhancedAPIService**
**Purpose**: Enterprise-grade API communication with comprehensive features
**Location**: `knowledge_base_agent/static/v2/js/enhancedAPIService.js`

**Key Methods**:
```javascript
// Main request method
apiService.request(endpoint, options)

// Convenience methods
apiService.get(endpoint, options)
apiService.post(endpoint, data, options)
apiService.put(endpoint, data, options)
apiService.delete(endpoint, options)
```

**Usage Example**:
```javascript
const data = await apiService.get('/api/data', {
    cache: true,
    cacheTTL: 300000,
    errorMessage: 'Failed to load data',
    showLoading: true
});
```

## 🏢 **Consolidated Managers**

### **BaseManager**
**Purpose**: Foundation class providing common functionality for all managers
**Location**: `knowledge_base_agent/static/v2/js/baseManager.js`

**Key Features**:
- Template method pattern for consistent initialization
- Automatic service integration
- Standardized state management
- Comprehensive error handling and logging
- Event dispatching and listening capabilities
- Component lifecycle management

**Usage Example**:
```javascript
class CustomManager extends BaseManager {
    async initializeElements() {
        this.elements.button = document.getElementById('my-button');
    }
    
    async setupEventListeners() {
        this.eventService.setupStandardListeners(this, {
            buttons: [{ selector: this.elements.button, handler: this.handleClick }]
        });
    }
    
    handleClick() {
        this.log('Button clicked');
    }
}
```

### **CoreUIManager**
**Purpose**: Unified interface for main content areas (chat, knowledge base, synthesis)
**Location**: `knowledge_base_agent/static/v2/js/coreUIManager.js`

**Key Features**:
- View-based architecture with seamless switching
- Keyboard shortcuts (Ctrl+1/2/3 for view switching)
- Unified event handling across all UI components
- Coordinated data loading and caching
- History management with back navigation

**Usage Example**:
```javascript
const coreUI = await CoreUIManager.create();
await coreUI.switchView('chat'); // Switch to chat view
const currentView = coreUI.getCurrentView(); // Get current view
```

### **UnifiedDisplayManager**
**Purpose**: Coordinated display management for phases, progress, and tasks
**Location**: `knowledge_base_agent/static/v2/js/unifiedDisplayManager.js`

**Key Features**:
- Queue-based update system for performance
- Throttled updates to prevent UI overwhelming
- Automatic cleanup of old phases/tasks
- Multiple display modes (integrated, separate, minimal)
- Comprehensive event handling for all display types

**Usage Example**:
```javascript
const displayManager = await UnifiedDisplayManager.create();
const currentPhase = displayManager.getCurrentPhase();
const activeTask = displayManager.getActiveTask();
```

### **UnifiedConnectionManager**
**Purpose**: Single source of truth for all connection states and strategies
**Location**: `knowledge_base_agent/static/v2/js/unifiedConnectionManager.js`

**Key Features**:
- Multi-layered connection strategy (SocketIO → Polling → Health checks)
- Automatic fallback mechanisms
- Connection state indicators and UI updates
- Performance metrics and downtime tracking
- Event delegation for application events

**Usage Example**:
```javascript
const connectionManager = await UnifiedConnectionManager.create();
const isConnected = connectionManager.isConnected();
const status = connectionManager.getConnectionStatus();
```

### **AgentSystemManager**
**Purpose**: Unified interface for agent operations and monitoring
**Location**: `knowledge_base_agent/static/v2/js/agentSystemManager.js`

**Key Features**:
- Unified agent control interface
- Task lifecycle management
- Preference collection and management
- Real-time status updates
- Historical task tracking

**Usage Example**:
```javascript
const agentSystem = await AgentSystemManager.create();
await agentSystem.startAgent(); // Start agent with current preferences
const isRunning = agentSystem.isAgentRunning();
```

## 🔄 **Component Lifecycle**

### **Initialization Flow**
1. **Dependency Validation**: Ensure required services are available
2. **Element Initialization**: Find and cache DOM elements
3. **State Initialization**: Set up initial component state
4. **Event Listener Setup**: Configure event handling using EventListenerService
5. **Data Loading**: Load initial data using EnhancedAPIService
6. **Finalization**: Complete initialization and mark as ready

### **State Management**
All managers use consistent state management:
```javascript
// Update state with automatic change notification
this.setState({ loading: true, data: newData });

// Handle state changes
onStateChange(newState, previousState) {
    // React to state changes
    this.updateUI();
}
```

### **Cleanup Process**
Automatic cleanup through CleanupService:
```javascript
cleanup() {
    CleanupService.cleanup(this); // Handles all resource cleanup
}
```

## 🎨 **UI Patterns**

### **Glass Morphism Design System**
The UI uses a glass morphism design with:
- Dark background with translucent glass panels
- Backdrop blur effects and subtle borders
- Blue-purple gradient accents with customizable themes
- Responsive design with mobile-first approach

### **Component Structure**
```html
<div class="glass-panel-v3 glass-panel-v3--primary">
    <div class="panel-header">
        <h3 class="panel-title">Component Title</h3>
        <div class="panel-controls">
            <button class="glass-button glass-button--small">
                <i class="fas fa-refresh"></i>
            </button>
        </div>
    </div>
    <div class="panel-content">
        <!-- Component content -->
    </div>
</div>
```

### **Event Handling Patterns**
```javascript
// Use EventListenerService for all event handling
this.eventService.setupStandardListeners(this, {
    buttons: [
        {
            selector: '.action-button',
            handler: this.handleAction,
            debounce: 300,
            preventDefault: true
        }
    ],
    inputs: [
        {
            selector: '.search-input',
            handler: this.handleSearch,
            debounce: 200,
            events: ['input']
        }
    ],
    delegated: [
        {
            container: '.item-list',
            selector: '.item',
            event: 'click',
            handler: this.handleItemClick
        }
    ]
});
```

## 🔌 **Integration Patterns**

### **Service Integration**
All components automatically have access to core services:
```javascript
// Duration formatting
const formatted = this.durationFormatter.format(duration);

// API calls with error handling
const data = await this.apiCall('/api/endpoint', {
    errorMessage: 'Failed to load data'
});

// Event handling
this.eventService.setupStandardListeners(this, config);

// Cleanup
this.cleanupService.cleanup(this);
```

### **Manager Communication**
Managers communicate through custom events:
```javascript
// Dispatch event
this.dispatchEvent('dataUpdated', { data: newData });

// Listen for events
this.addEventListener('dataUpdated', (e) => {
    this.handleDataUpdate(e.detail.data);
});
```

### **State Synchronization**
Managers can share state through the global event system:
```javascript
// Manager A dispatches state change
this.dispatchEvent('stateChanged', { newState: this.state });

// Manager B listens and updates
this.addEventListener('stateChanged', (e) => {
    this.syncWithExternalState(e.detail.newState);
});
```

## 📊 **Performance Considerations**

### **Memory Management**
- Automatic resource cleanup through CleanupService
- Event listener tracking and removal
- Timer management with automatic cleanup
- Component lifecycle management

### **Event Optimization**
- Debouncing for user inputs (150-300ms)
- Throttling for high-frequency events (100ms)
- Event delegation for dynamic content
- Conditional event setup

### **API Optimization**
- Request caching with TTL management
- Request deduplication
- Intelligent retry logic with exponential backoff
- Loading state management

### **Rendering Optimization**
- Queue-based updates in UnifiedDisplayManager
- Throttled rendering to prevent overwhelming
- Virtual scrolling for large lists
- Efficient DOM manipulation

## 🧪 **Testing Strategy**

### **Unit Testing**
Test individual managers in isolation:
```javascript
describe('CoreUIManager', () => {
    let manager;
    
    beforeEach(async () => {
        manager = await CoreUIManager.create({ autoInit: false });
        await manager.init();
    });
    
    afterEach(() => {
        manager.cleanup();
    });
    
    it('should switch views correctly', async () => {
        await manager.switchView('chat');
        expect(manager.getCurrentView()).toBe('chat');
    });
});
```

### **Integration Testing**
Test manager interactions:
```javascript
describe('Manager Integration', () => {
    it('should coordinate between display and connection managers', async () => {
        const displayManager = await UnifiedDisplayManager.create();
        const connectionManager = await UnifiedConnectionManager.create();
        
        // Test coordination
        connectionManager.dispatchConnectionEvent('status_changed');
        // Verify display manager responds appropriately
    });
});
```

### **End-to-End Testing**
Test complete user workflows:
```javascript
describe('User Workflows', () => {
    it('should handle complete agent execution workflow', async () => {
        // Start agent
        // Monitor progress
        // Verify completion
    });
});
```

## 🔧 **Development Guidelines**

### **Creating New Components**
1. Extend BaseManager for consistent behavior
2. Use EventListenerService for all event handling
3. Integrate with core services through BaseManager
4. Follow template method pattern for initialization
5. Implement proper cleanup

### **Best Practices**
- Always use core services instead of manual implementations
- Follow consistent naming conventions
- Implement comprehensive error handling
- Use declarative configuration over imperative code
- Ensure proper resource cleanup

### **Code Quality Standards**
- Use modern JavaScript patterns (async/await, destructuring, etc.)
- Follow consistent code formatting
- Include comprehensive logging
- Implement proper error boundaries
- Write testable code with clear interfaces

This architecture provides a solid foundation for maintainable, scalable, and performant frontend development while ensuring consistency and best practices across all components.