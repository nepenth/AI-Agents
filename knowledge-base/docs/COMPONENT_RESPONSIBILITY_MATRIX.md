# Component Responsibility Matrix

## 🎯 **Overview**

This matrix defines clear boundaries and responsibilities for all components in the consolidated frontend architecture. It serves as the definitive guide for understanding what each component should and should not handle.

## 🔧 **Service Layer Responsibilities**

| Service | Primary Responsibility | Secondary Responsibilities | What It Does NOT Handle |
|---------|----------------------|---------------------------|------------------------|
| **DurationFormatter** | Time formatting and display | ETC calculations, elapsed time display, sub-minute precision | Date parsing, timezone conversion, calendar operations |
| **CleanupService** | Resource cleanup and memory management | Event listener removal, timer cleanup, manager cleanup | Business logic, data persistence, UI updates |
| **EventListenerService** | Event handling and user interaction | Debouncing, throttling, delegation, modal management | Data processing, API calls, state management |
| **EnhancedAPIService** | API communication and data fetching | Error handling, caching, retry logic, loading states | UI updates, business logic, data transformation |

## 🏢 **Manager Layer Responsibilities**

| Manager | Primary Responsibility | Components Managed | Key Interfaces | What It Does NOT Handle |
|---------|----------------------|-------------------|----------------|------------------------|
| **BaseManager** | Common functionality foundation | All other managers | `init()`, `cleanup()`, `setState()` | Specific business logic, UI rendering |
| **CoreUIManager** | Main UI interactions and navigation | Chat, Knowledge Base, Synthesis | `switchView()`, `getCurrentView()` | Display rendering, connection management |
| **UnifiedDisplayManager** | Display coordination and rendering | Progress, Phases, Tasks | `handlePhaseStart()`, `renderDisplay()` | User input, API communication |
| **UnifiedConnectionManager** | Connection state and communication | SocketIO, API, Health checks | `getConnectionStatus()`, `isConnected()` | UI rendering, business logic |
| **AgentSystemManager** | Agent operations and monitoring | Agent controls, Task state, Execution | `startAgent()`, `getAgentState()` | Display rendering, connection management |

## 📋 **Detailed Responsibility Breakdown**

### **Service Layer - Core Utilities**

#### **DurationFormatter Service**
**✅ Responsible For:**
- Converting milliseconds to human-readable format
- Formatting seconds and minutes input
- ETC (Estimated Time to Completion) calculations
- Elapsed time display
- Configurable formatting options (compact/verbose, show/hide seconds)
- Fallback handling for invalid durations

**❌ NOT Responsible For:**
- Date parsing or manipulation
- Timezone conversions
- Calendar operations
- Duration calculations (only formatting)
- Storing or persisting time data

**🔌 Interface:**
```javascript
DurationFormatter.format(milliseconds, options)
DurationFormatter.formatSeconds(seconds, options)
DurationFormatter.formatMinutes(minutes, options)
DurationFormatter.formatETC(milliseconds, options)
DurationFormatter.formatElapsed(milliseconds, options)
```

#### **CleanupService**
**✅ Responsible For:**
- Automatic timeout and interval cleanup
- Event listener removal (document, window, SocketIO)
- Manager and sub-component cleanup
- Component-specific cleanup logic
- Memory leak prevention
- Resource nullification

**❌ NOT Responsible For:**
- Business logic execution
- Data persistence or saving
- UI updates or rendering
- API calls or network operations
- State management

**🔌 Interface:**
```javascript
CleanupService.cleanup(component, options)
CleanupService.addEventListenerWithCleanup(component, element, event, handler)
CleanupService.setTimeoutWithCleanup(component, callback, delay)
CleanupService.setIntervalWithCleanup(component, callback, delay)
```

#### **EventListenerService**
**✅ Responsible For:**
- Declarative event listener setup
- Automatic debouncing and throttling
- Event delegation for dynamic content
- Modal and keyboard shortcut management
- Event listener tracking for cleanup
- Performance optimization (delegation, throttling)

**❌ NOT Responsible For:**
- Data processing or transformation
- API calls or network requests
- State management or persistence
- UI rendering or DOM manipulation
- Business logic execution

**🔌 Interface:**
```javascript
EventListenerService.setupStandardListeners(component, config)
EventListenerService.cleanup(component)
```

#### **EnhancedAPIService**
**✅ Responsible For:**
- HTTP request/response handling
- Error handling and user notifications
- Request caching and deduplication
- Retry logic with exponential backoff
- Loading state management
- Request/response interceptors

**❌ NOT Responsible For:**
- UI updates or DOM manipulation
- Business logic processing
- Data transformation (beyond basic parsing)
- Event handling or user interactions
- Component lifecycle management

**🔌 Interface:**
```javascript
apiService.request(endpoint, options)
apiService.get(endpoint, options)
apiService.post(endpoint, data, options)
apiService.put(endpoint, data, options)
apiService.delete(endpoint, options)
```

### **Manager Layer - Business Logic**

#### **BaseManager**
**✅ Responsible For:**
- Template method pattern implementation
- Automatic service integration
- Standardized state management
- Component lifecycle management
- Error handling and logging
- Event dispatching and listening

**❌ NOT Responsible For:**
- Specific business logic
- UI rendering or DOM manipulation
- Data persistence
- Network communication (delegates to services)

**🔌 Interface:**
```javascript
async init()
cleanup()
setState(updates, notify)
onStateChange(newState, previousState)
dispatchEvent(eventName, detail)
addEventListener(eventName, handler)
```

#### **CoreUIManager**
**✅ Responsible For:**
- View switching and navigation (chat, kb, synthesis)
- View history management
- URL state synchronization
- Coordinated data loading across views
- Keyboard shortcuts for navigation
- Cross-view event coordination

**❌ NOT Responsible For:**
- Individual view rendering (delegates to view-specific logic)
- Display component management (handled by UnifiedDisplayManager)
- Connection management (handled by UnifiedConnectionManager)
- Agent operations (handled by AgentSystemManager)

**🔌 Interface:**
```javascript
async switchView(viewName)
getCurrentView()
getViewHistory()
goBack()
```

**🔗 Dependencies:**
- EventListenerService (for navigation events)
- EnhancedAPIService (for data loading)
- DurationFormatter (for time display)

#### **UnifiedDisplayManager**
**✅ Responsible For:**
- Phase progress display and coordination
- Progress bar management and updates
- Task information display
- Real-time status updates
- Performance-optimized rendering
- Display mode management (integrated, separate, minimal)

**❌ NOT Responsible For:**
- User input handling (delegates to EventListenerService)
- API communication (delegates to EnhancedAPIService)
- Agent control operations (handled by AgentSystemManager)
- View navigation (handled by CoreUIManager)

**🔌 Interface:**
```javascript
handlePhaseStart(data)
handlePhaseUpdate(data)
handlePhaseComplete(data)
handleProgressUpdate(data)
handleTaskStarted(data)
getCurrentPhase()
getActiveTask()
```

**🔗 Dependencies:**
- DurationFormatter (for time display)
- EventListenerService (for display controls)
- EnhancedAPIService (for status updates)

#### **UnifiedConnectionManager**
**✅ Responsible For:**
- SocketIO connection management
- API health checking and monitoring
- Connection fallback strategies (polling)
- Connection state indicators
- Performance metrics and downtime tracking
- Application event delegation

**❌ NOT Responsible For:**
- UI rendering (delegates to display components)
- Business logic processing
- Data transformation
- User interaction handling
- Agent operations

**🔌 Interface:**
```javascript
getConnectionStatus()
isConnected()
isSocketIOConnected()
isAPIConnected()
registerEventHandler(eventName, handler)
reconnectAll()
```

**🔗 Dependencies:**
- EnhancedAPIService (for health checks)
- EventListenerService (for connection controls)

#### **AgentSystemManager**
**✅ Responsible For:**
- Agent execution control (start/stop)
- Task state management and monitoring
- Execution plan tracking
- Preference collection and management
- Agent history and statistics
- Task lifecycle management

**❌ NOT Responsible For:**
- Display rendering (delegates to UnifiedDisplayManager)
- Connection management (handled by UnifiedConnectionManager)
- UI navigation (handled by CoreUIManager)
- Low-level event handling (delegates to EventListenerService)

**🔌 Interface:**
```javascript
async startAgent()
async stopAgent()
getAgentState()
getTaskState()
getCurrentTask()
isAgentRunning()
```

**🔗 Dependencies:**
- EnhancedAPIService (for agent operations)
- EventListenerService (for control events)
- DurationFormatter (for time display)

## 🔄 **Inter-Component Communication**

### **Event-Based Communication**
Components communicate through custom events to maintain loose coupling:

```javascript
// Manager A dispatches event
this.dispatchEvent('dataUpdated', { data: newData });

// Manager B listens for event
this.addEventListener('dataUpdated', (e) => {
    this.handleDataUpdate(e.detail.data);
});
```

### **Service-Mediated Communication**
Components use services for shared functionality:

```javascript
// Both managers use the same API service
const data = await this.apiService.get('/api/data');

// Both managers use the same event service
this.eventService.setupStandardListeners(this, config);
```

## 🚫 **Anti-Patterns and Boundaries**

### **What Components Should NEVER Do**

#### **Services Should Never:**
- Directly manipulate DOM elements
- Handle business logic
- Manage component state
- Make decisions about UI flow
- Store application data

#### **Managers Should Never:**
- Implement utility functionality (use services)
- Directly manipulate other managers' DOM elements
- Bypass service interfaces for direct operations
- Handle low-level resource management (use CleanupService)
- Implement custom event handling (use EventListenerService)

### **Boundary Violations to Avoid**

```javascript
// ❌ BAD: Manager implementing utility functionality
class MyManager extends BaseManager {
    formatDuration(ms) {
        // Don't implement this - use DurationFormatter service
        return `${Math.floor(ms/1000)}s`;
    }
}

// ✅ GOOD: Manager using service
class MyManager extends BaseManager {
    formatDuration(ms) {
        return this.durationFormatter.format(ms);
    }
}
```

```javascript
// ❌ BAD: Direct DOM manipulation without service
element.addEventListener('click', handler);

// ✅ GOOD: Using EventListenerService
this.eventService.setupStandardListeners(this, {
    buttons: [{ selector: element, handler }]
});
```

## 📊 **Responsibility Matrix Summary**

| Layer | Components | Primary Focus | Key Principle |
|-------|------------|---------------|---------------|
| **Service** | 4 core services | Utility functionality | Single responsibility, no business logic |
| **Manager** | 5 consolidated managers | Business logic and coordination | Clear boundaries, service delegation |
| **Integration** | BaseManager + Event system | Communication and lifecycle | Loose coupling, event-driven |

## 🎯 **Decision Framework**

When adding new functionality, use this decision tree:

1. **Is it utility functionality?** → Add to appropriate service
2. **Is it business logic?** → Add to appropriate manager
3. **Does it cross manager boundaries?** → Use event-based communication
4. **Does it need new patterns?** → Extend BaseManager or create new service

## 🔍 **Validation Checklist**

Before implementing new functionality, verify:

- [ ] **Single Responsibility**: Component has one clear purpose
- [ ] **Service Usage**: Uses appropriate services instead of reimplementing
- [ ] **Boundary Respect**: Doesn't violate other components' responsibilities
- [ ] **Event Communication**: Uses events for inter-component communication
- [ ] **Cleanup Integration**: Properly integrates with CleanupService
- [ ] **Error Handling**: Uses consistent error handling patterns
- [ ] **Testing**: Can be tested in isolation

This responsibility matrix ensures clear architectural boundaries and prevents the responsibility drift that led to the original consolidation effort.