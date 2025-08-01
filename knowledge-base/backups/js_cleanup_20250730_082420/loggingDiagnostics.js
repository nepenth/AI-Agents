/* LOGGING DIAGNOSTICS AND MONITORING SYSTEM */

/**
 * Comprehensive diagnostics system for monitoring and debugging
 * the enhanced logging and event system
 */
class LoggingDiagnostics {
    constructor() {
        this.diagnostics = {
            eventCounts: new Map(),
            duplicateEvents: new Map(),
            eventSources: new Map(),
            eventTimings: new Map(),
            connectionStatus: {
                socketIO: false,
                polling: false,
                currentSource: 'unknown'
            },
            performance: {
                averageEventProcessingTime: 0,
                totalEventsProcessed: 0,
                eventsPerSecond: 0,
                memoryUsage: 0
            }
        };
        
        this.startTime = Date.now();
        this.lastEventTime = Date.now();
        this.eventBuffer = [];
        this.maxBufferSize = 100;
        
        this.init();
    }
    
    init() {
        console.log('🔍 LoggingDiagnostics initialized');
        
        // Monitor all event types
        this.setupEventMonitoring();
        
        // Start performance monitoring
        this.startPerformanceMonitoring();
        
        // Add diagnostic UI
        this.createDiagnosticUI();
    }
    
    setupEventMonitoring() {
        const eventTypes = [
            'log', 'live_log', 'agent_status_update', 'status_update',
            'phase_update', 'phase_start', 'phase_complete', 'phase_error',
            'progress_update', 'gpu_stats', 'logs_cleared', 'connection_changed'
        ];
        
        eventTypes.forEach(eventType => {
            document.addEventListener(eventType, (event) => {
                this.recordEvent(eventType, event.detail);
            });
        });
    }
    
    recordEvent(eventType, data) {
        const now = Date.now();
        const source = data._source || 'unknown';
        
        // Update event counts
        const currentCount = this.diagnostics.eventCounts.get(eventType) || 0;
        this.diagnostics.eventCounts.set(eventType, currentCount + 1);
        
        // Track event sources
        const sourceKey = `${eventType}:${source}`;
        const sourceCount = this.diagnostics.eventSources.get(sourceKey) || 0;
        this.diagnostics.eventSources.set(sourceKey, sourceCount + 1);
        
        // Track event timing
        this.diagnostics.eventTimings.set(eventType, now);
        
        // Add to event buffer for detailed analysis
        this.eventBuffer.push({
            type: eventType,
            source: source,
            timestamp: now,
            data: this.sanitizeEventData(data)
        });
        
        // Limit buffer size
        if (this.eventBuffer.length > this.maxBufferSize) {
            this.eventBuffer.shift();
        }
        
        // Update performance metrics
        this.updatePerformanceMetrics();
        
        // Check for potential duplicates
        this.checkForDuplicates(eventType, data, source);
        
        this.lastEventTime = now;
    }
    
    sanitizeEventData(data) {
        // Create a sanitized version of event data for logging
        const sanitized = {};
        
        if (data.message) {
            sanitized.message = data.message.substring(0, 100);
        }
        if (data.level) {
            sanitized.level = data.level;
        }
        if (data.phase_id) {
            sanitized.phase_id = data.phase_id;
        }
        if (data.status) {
            sanitized.status = data.status;
        }
        if (data.progress !== undefined) {
            sanitized.progress = data.progress;
        }
        
        return sanitized;
    }
    
    checkForDuplicates(eventType, data, source) {
        // Simple duplicate detection for diagnostics
        const eventKey = this.generateEventKey(eventType, data);
        const duplicateKey = `${eventType}:${eventKey}`;
        
        if (this.diagnostics.duplicateEvents.has(duplicateKey)) {
            const duplicateInfo = this.diagnostics.duplicateEvents.get(duplicateKey);
            duplicateInfo.count++;
            duplicateInfo.lastSeen = Date.now();
            duplicateInfo.sources.add(source);
            
            console.warn(`🔍 Potential duplicate detected: ${eventType} from ${source}`, {
                count: duplicateInfo.count,
                sources: Array.from(duplicateInfo.sources),
                data: this.sanitizeEventData(data)
            });
        } else {
            this.diagnostics.duplicateEvents.set(duplicateKey, {
                count: 1,
                firstSeen: Date.now(),
                lastSeen: Date.now(),
                sources: new Set([source])
            });
        }
    }
    
    generateEventKey(eventType, data) {
        // Generate a key for duplicate detection
        switch (eventType) {
            case 'log':
            case 'live_log':
                return `${data.level}:${(data.message || '').substring(0, 50)}`;
            case 'agent_status_update':
                return `${data.is_running}:${data.current_phase_message || ''}`;
            case 'phase_update':
                return `${data.phase_id}:${data.status}:${data.progress || 0}`;
            default:
                return JSON.stringify(data).substring(0, 100);
        }
    }
    
    updatePerformanceMetrics() {
        const now = Date.now();
        const totalTime = now - this.startTime;
        const totalEvents = this.diagnostics.performance.totalEventsProcessed + 1;
        
        this.diagnostics.performance.totalEventsProcessed = totalEvents;
        this.diagnostics.performance.eventsPerSecond = (totalEvents / (totalTime / 1000)).toFixed(2);
        
        // Update memory usage if available
        if (performance.memory) {
            this.diagnostics.performance.memoryUsage = Math.round(performance.memory.usedJSHeapSize / 1024 / 1024);
        }
    }
    
    startPerformanceMonitoring() {
        setInterval(() => {
            this.updateConnectionStatus();
            this.updateDiagnosticUI();
        }, 2000);
    }
    
    updateConnectionStatus() {
        // Check connection manager status if available
        if (window.uiManager && window.uiManager.connectionManager) {
            const status = window.uiManager.connectionManager.getStatus();
            this.diagnostics.connectionStatus = {
                socketIO: status.socketIOConnected,
                polling: status.pollingActive,
                currentSource: status.currentSource
            };
        }
    }
    
    createDiagnosticUI() {
        // Create a floating diagnostic panel
        const panel = document.createElement('div');
        panel.id = 'logging-diagnostics-panel';
        panel.style.cssText = `
            position: fixed;
            top: 10px;
            right: 10px;
            width: 300px;
            max-height: 400px;
            background: rgba(0, 0, 0, 0.9);
            color: white;
            padding: 10px;
            border-radius: 8px;
            font-family: monospace;
            font-size: 12px;
            z-index: 10000;
            overflow-y: auto;
            display: none;
            backdrop-filter: blur(10px);
        `;
        
        document.body.appendChild(panel);
        
        // Add toggle button
        const toggleBtn = document.createElement('button');
        toggleBtn.id = 'diagnostics-toggle';
        toggleBtn.textContent = '🔍';
        toggleBtn.title = 'Toggle Logging Diagnostics';
        toggleBtn.style.cssText = `
            position: fixed;
            top: 10px;
            right: 320px;
            width: 30px;
            height: 30px;
            background: rgba(0, 0, 0, 0.7);
            color: white;
            border: none;
            border-radius: 50%;
            cursor: pointer;
            z-index: 10001;
            font-size: 14px;
        `;
        
        toggleBtn.addEventListener('click', () => {
            const panel = document.getElementById('logging-diagnostics-panel');
            panel.style.display = panel.style.display === 'none' ? 'block' : 'none';
        });
        
        document.body.appendChild(toggleBtn);
    }
    
    updateDiagnosticUI() {
        const panel = document.getElementById('logging-diagnostics-panel');
        if (!panel || panel.style.display === 'none') return;
        
        const html = `
            <div style="border-bottom: 1px solid #333; margin-bottom: 10px; padding-bottom: 5px;">
                <strong>🔍 Logging Diagnostics</strong>
                <button onclick="window.loggingDiagnostics.clearStats()" style="float: right; font-size: 10px;">Clear</button>
            </div>
            
            <div style="margin-bottom: 10px;">
                <strong>Connection Status:</strong><br>
                SocketIO: ${this.diagnostics.connectionStatus.socketIO ? '✅' : '❌'}<br>
                Polling: ${this.diagnostics.connectionStatus.polling ? '✅' : '❌'}<br>
                Current: ${this.diagnostics.connectionStatus.currentSource}
            </div>
            
            <div style="margin-bottom: 10px;">
                <strong>Performance:</strong><br>
                Events/sec: ${this.diagnostics.performance.eventsPerSecond}<br>
                Total Events: ${this.diagnostics.performance.totalEventsProcessed}<br>
                Memory: ${this.diagnostics.performance.memoryUsage}MB
            </div>
            
            <div style="margin-bottom: 10px;">
                <strong>Event Counts:</strong><br>
                ${Array.from(this.diagnostics.eventCounts.entries())
                    .sort((a, b) => b[1] - a[1])
                    .slice(0, 5)
                    .map(([type, count]) => `${type}: ${count}`)
                    .join('<br>')}
            </div>
            
            <div style="margin-bottom: 10px;">
                <strong>Event Sources:</strong><br>
                ${Array.from(this.diagnostics.eventSources.entries())
                    .sort((a, b) => b[1] - a[1])
                    .slice(0, 5)
                    .map(([source, count]) => `${source}: ${count}`)
                    .join('<br>')}
            </div>
            
            <div style="margin-bottom: 10px;">
                <strong>Potential Duplicates:</strong><br>
                ${Array.from(this.diagnostics.duplicateEvents.entries())
                    .filter(([key, info]) => info.count > 1)
                    .slice(0, 3)
                    .map(([key, info]) => `${key.split(':')[0]}: ${info.count}x`)
                    .join('<br>') || 'None detected'}
            </div>
            
            <div>
                <strong>Recent Events:</strong><br>
                ${this.eventBuffer.slice(-3).map(event => 
                    `${event.type} (${event.source})`
                ).join('<br>')}
            </div>
        `;
        
        panel.innerHTML = html;
    }
    
    clearStats() {
        this.diagnostics.eventCounts.clear();
        this.diagnostics.duplicateEvents.clear();
        this.diagnostics.eventSources.clear();
        this.diagnostics.eventTimings.clear();
        this.eventBuffer = [];
        this.diagnostics.performance.totalEventsProcessed = 0;
        this.startTime = Date.now();
        console.log('🔍 Diagnostics stats cleared');
    }
    
    generateReport() {
        const report = {
            timestamp: new Date().toISOString(),
            uptime: Date.now() - this.startTime,
            diagnostics: {
                eventCounts: Object.fromEntries(this.diagnostics.eventCounts),
                eventSources: Object.fromEntries(this.diagnostics.eventSources),
                duplicateEvents: Object.fromEntries(
                    Array.from(this.diagnostics.duplicateEvents.entries())
                        .filter(([key, info]) => info.count > 1)
                        .map(([key, info]) => [key, { count: info.count, sources: Array.from(info.sources) }])
                ),
                connectionStatus: this.diagnostics.connectionStatus,
                performance: this.diagnostics.performance
            },
            recentEvents: this.eventBuffer.slice(-10)
        };
        
        console.log('🔍 Diagnostics Report:', report);
        return report;
    }
    
    exportReport() {
        const report = this.generateReport();
        const blob = new Blob([JSON.stringify(report, null, 2)], { type: 'application/json' });
        const url = URL.createObjectURL(blob);
        
        const a = document.createElement('a');
        a.href = url;
        a.download = `logging-diagnostics-${Date.now()}.json`;
        document.body.appendChild(a);
        a.click();
        document.body.removeChild(a);
        URL.revokeObjectURL(url);
        
        console.log('🔍 Diagnostics report exported');
    }
}

// Initialize diagnostics system
document.addEventListener('DOMContentLoaded', () => {
    // Only initialize if debugging is enabled
    const urlParams = new URLSearchParams(window.location.search);
    if (urlParams.get('debug') === 'true' || localStorage.getItem('loggingDebug') === 'true') {
        window.loggingDiagnostics = new LoggingDiagnostics();
        console.log('🔍 Logging diagnostics enabled - use ?debug=true or localStorage.setItem("loggingDebug", "true")');
    }
});

// Make available globally
window.LoggingDiagnostics = LoggingDiagnostics;