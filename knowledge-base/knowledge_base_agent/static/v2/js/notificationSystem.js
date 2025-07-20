/* V2 NOTIFICATIONSYSTEM.JS - USER NOTIFICATION SYSTEM FOR COMMUNICATION FAILURES */

/**
 * NotificationSystem - Comprehensive user notification system
 * 
 * ARCHITECTURE:
 * - Provides toast notifications for real-time feedback
 * - Manages notification queue and priorities
 * - Handles persistent notifications for critical issues
 * - Integrates with error recovery mechanisms
 */
class NotificationSystem {
    constructor(config = {}) {
        this.config = {
            maxNotifications: config.maxNotifications || 5,
            defaultDuration: config.defaultDuration || 5000,
            persistentDuration: config.persistentDuration || 0, // 0 = never auto-hide
            animationDuration: config.animationDuration || 300,
            position: config.position || 'top-right',
            ...config
        };
        
        this.notifications = new Map();
        this.notificationQueue = [];
        this.container = null;
        this.nextId = 1;
        
        // Notification types and their configurations
        this.notificationTypes = {
            success: {
                icon: 'fas fa-check-circle',
                className: 'notification-success',
                duration: 4000
            },
            info: {
                icon: 'fas fa-info-circle',
                className: 'notification-info',
                duration: 5000
            },
            warning: {
                icon: 'fas fa-exclamation-triangle',
                className: 'notification-warning',
                duration: 7000
            },
            error: {
                icon: 'fas fa-exclamation-circle',
                className: 'notification-error',
                duration: 10000
            },
            critical: {
                icon: 'fas fa-times-circle',
                className: 'notification-critical',
                duration: 0 // Persistent
            },
            connection: {
                icon: 'fas fa-wifi',
                className: 'notification-connection',
                duration: 0 // Persistent until resolved
            }
        };
        
        this.init();
    }
    
    init() {
        this.createContainer();
        this.setupStyles();
        console.log('🔔 NotificationSystem initialized');
    }
    
    createContainer() {
        this.container = document.createElement('div');
        this.container.id = 'notification-container';
        this.container.className = `notification-container notification-${this.config.position}`;
        
        document.body.appendChild(this.container);
    }
    
    setupStyles() {
        if (document.getElementById('notification-styles')) return;
        
        const style = document.createElement('style');
        style.id = 'notification-styles';
        style.textContent = `
            .notification-container {
                position: fixed;
                z-index: 10000;
                pointer-events: none;
                max-width: 400px;
                width: 100%;
            }
            
            .notification-top-right {
                top: var(--space-4);
                right: var(--space-4);
            }
            
            .notification-top-left {
                top: var(--space-4);
                left: var(--space-4);
            }
            
            .notification-bottom-right {
                bottom: var(--space-4);
                right: var(--space-4);
            }
            
            .notification-bottom-left {
                bottom: var(--space-4);
                left: var(--space-4);
            }
            
            .notification {
                display: flex;
                align-items: flex-start;
                gap: var(--space-3);
                padding: var(--space-4);
                margin-bottom: var(--space-2);
                background: var(--glass-bg-primary);
                border: 1px solid var(--glass-border-primary);
                border-radius: var(--radius-lg);
                backdrop-filter: blur(20px);
                box-shadow: 0 8px 32px rgba(0, 0, 0, 0.2);
                pointer-events: auto;
                transform: translateX(100%);
                opacity: 0;
                transition: all var(--duration-normal) var(--ease-smooth);
                max-width: 100%;
                word-wrap: break-word;
            }
            
            .notification.show {
                transform: translateX(0);
                opacity: 1;
            }
            
            .notification.hide {
                transform: translateX(100%);
                opacity: 0;
                margin-bottom: 0;
                padding-top: 0;
                padding-bottom: 0;
                max-height: 0;
                overflow: hidden;
            }
            
            .notification-success {
                border-left: 4px solid var(--success-green);
            }
            
            .notification-info {
                border-left: 4px solid var(--primary-blue);
            }
            
            .notification-warning {
                border-left: 4px solid var(--warning-yellow);
            }
            
            .notification-error {
                border-left: 4px solid var(--error-red);
            }
            
            .notification-critical {
                border-left: 4px solid var(--error-red);
                background: rgba(var(--error-red-rgb), 0.1);
                animation: pulse 2s infinite;
            }
            
            .notification-connection {
                border-left: 4px solid var(--warning-yellow);
                background: rgba(var(--warning-yellow-rgb), 0.1);
            }
            
            .notification-icon {
                flex-shrink: 0;
                font-size: var(--font-size-lg);
                margin-top: var(--space-1);
            }
            
            .notification-success .notification-icon {
                color: var(--success-green);
            }
            
            .notification-info .notification-icon {
                color: var(--primary-blue);
            }
            
            .notification-warning .notification-icon {
                color: var(--warning-yellow);
            }
            
            .notification-error .notification-icon,
            .notification-critical .notification-icon {
                color: var(--error-red);
            }
            
            .notification-connection .notification-icon {
                color: var(--warning-yellow);
            }
            
            .notification-content {
                flex: 1;
                min-width: 0;
            }
            
            .notification-title {
                font-weight: 600;
                font-size: var(--font-size-base);
                color: var(--text-primary);
                margin-bottom: var(--space-1);
                line-height: 1.4;
            }
            
            .notification-message {
                font-size: var(--font-size-sm);
                color: var(--text-secondary);
                line-height: 1.4;
                margin-bottom: var(--space-2);
            }
            
            .notification-actions {
                display: flex;
                gap: var(--space-2);
                margin-top: var(--space-2);
            }
            
            .notification-action {
                padding: var(--space-1) var(--space-2);
                background: var(--glass-bg-secondary);
                border: 1px solid var(--glass-border-secondary);
                border-radius: var(--radius-base);
                font-size: var(--font-size-xs);
                cursor: pointer;
                transition: all var(--duration-fast) var(--ease-smooth);
                color: var(--text-primary);
            }
            
            .notification-action:hover {
                background: var(--glass-bg-tertiary);
                border-color: var(--glass-border-primary);
            }
            
            .notification-close {
                flex-shrink: 0;
                background: none;
                border: none;
                color: var(--text-tertiary);
                cursor: pointer;
                padding: var(--space-1);
                border-radius: var(--radius-sm);
                transition: all var(--duration-fast) var(--ease-smooth);
                margin-top: var(--space-1);
            }
            
            .notification-close:hover {
                color: var(--text-secondary);
                background: var(--glass-bg-tertiary);
            }
            
            .notification-progress {
                height: 2px;
                background: var(--glass-bg-tertiary);
                border-radius: var(--radius-sm);
                overflow: hidden;
                margin-top: var(--space-2);
            }
            
            .notification-progress-bar {
                height: 100%;
                background: var(--primary-blue);
                transition: width linear;
                border-radius: var(--radius-sm);
            }
            
            @keyframes pulse {
                0%, 100% { opacity: 1; }
                50% { opacity: 0.7; }
            }
            
            @media (max-width: 768px) {
                .notification-container {
                    left: var(--space-2);
                    right: var(--space-2);
                    max-width: none;
                }
                
                .notification {
                    padding: var(--space-3);
                }
                
                .notification-title {
                    font-size: var(--font-size-sm);
                }
                
                .notification-message {
                    font-size: var(--font-size-xs);
                }
            }
        `;
        
        document.head.appendChild(style);
    }
    
    show(type, title, message, options = {}) {
        const id = this.nextId++;
        const typeConfig = this.notificationTypes[type] || this.notificationTypes.info;
        
        const notification = {
            id,
            type,
            title,
            message,
            timestamp: new Date(),
            duration: options.duration !== undefined ? options.duration : typeConfig.duration,
            persistent: options.persistent || typeConfig.duration === 0,
            actions: options.actions || [],
            onAction: options.onAction,
            onClose: options.onClose,
            priority: options.priority || this.getTypePriority(type)
        };
        
        // Check if we should replace existing notification of same type
        if (options.replace && type === 'connection') {
            this.removeByType(type);
        }
        
        // Add to queue if container is full
        if (this.notifications.size >= this.config.maxNotifications) {
            this.notificationQueue.push(notification);
            return id;
        }
        
        this.notifications.set(id, notification);
        this.renderNotification(notification);
        
        // Auto-hide if not persistent
        if (!notification.persistent && notification.duration > 0) {
            setTimeout(() => {
                this.hide(id);
            }, notification.duration);
        }
        
        return id;
    }
    
    renderNotification(notification) {
        const typeConfig = this.notificationTypes[notification.type];
        
        const element = document.createElement('div');
        element.className = `notification ${typeConfig.className}`;
        element.dataset.id = notification.id;
        
        element.innerHTML = `
            <div class="notification-icon">
                <i class="${typeConfig.icon}"></i>
            </div>
            <div class="notification-content">
                <div class="notification-title">${this.escapeHtml(notification.title)}</div>
                <div class="notification-message">${this.escapeHtml(notification.message)}</div>
                ${notification.actions.length > 0 ? this.renderActions(notification.actions) : ''}
                ${!notification.persistent && notification.duration > 0 ? this.renderProgress(notification.duration) : ''}
            </div>
            <button class="notification-close" title="Close">
                <i class="fas fa-times"></i>
            </button>
        `;
        
        // Add event listeners
        const closeBtn = element.querySelector('.notification-close');
        closeBtn.addEventListener('click', () => {
            this.hide(notification.id);
        });
        
        // Add action listeners
        const actionButtons = element.querySelectorAll('.notification-action');
        actionButtons.forEach((button, index) => {
            button.addEventListener('click', () => {
                if (notification.onAction) {
                    notification.onAction(notification.actions[index], notification);
                }
                
                // Auto-close unless action specifies otherwise
                if (!notification.actions[index].keepOpen) {
                    this.hide(notification.id);
                }
            });
        });
        
        // Add to container
        this.container.appendChild(element);
        
        // Trigger show animation
        requestAnimationFrame(() => {
            element.classList.add('show');
        });
        
        // Start progress bar if applicable
        if (!notification.persistent && notification.duration > 0) {
            this.startProgressBar(element, notification.duration);
        }
    }
    
    renderActions(actions) {
        return `
            <div class="notification-actions">
                ${actions.map(action => `
                    <button class="notification-action" data-action="${action.id}">
                        ${action.icon ? `<i class="${action.icon}"></i> ` : ''}${this.escapeHtml(action.label)}
                    </button>
                `).join('')}
            </div>
        `;
    }
    
    renderProgress(duration) {
        return `
            <div class="notification-progress">
                <div class="notification-progress-bar"></div>
            </div>
        `;
    }
    
    startProgressBar(element, duration) {
        const progressBar = element.querySelector('.notification-progress-bar');
        if (!progressBar) return;
        
        progressBar.style.transition = `width ${duration}ms linear`;
        progressBar.style.width = '0%';
        
        // Start progress
        requestAnimationFrame(() => {
            progressBar.style.width = '100%';
        });
    }
    
    hide(id) {
        const notification = this.notifications.get(id);
        if (!notification) return;
        
        const element = this.container.querySelector(`[data-id="${id}"]`);
        if (!element) return;
        
        // Trigger hide animation
        element.classList.add('hide');
        
        // Remove after animation
        setTimeout(() => {
            if (element.parentNode) {
                element.parentNode.removeChild(element);
            }
            
            this.notifications.delete(id);
            
            // Call onClose callback
            if (notification.onClose) {
                notification.onClose(notification);
            }
            
            // Process queue
            this.processQueue();
            
        }, this.config.animationDuration);
    }
    
    hideAll() {
        const ids = Array.from(this.notifications.keys());
        ids.forEach(id => this.hide(id));
    }
    
    removeByType(type) {
        const toRemove = [];
        this.notifications.forEach((notification, id) => {
            if (notification.type === type) {
                toRemove.push(id);
            }
        });
        
        toRemove.forEach(id => this.hide(id));
    }
    
    processQueue() {
        if (this.notificationQueue.length === 0) return;
        if (this.notifications.size >= this.config.maxNotifications) return;
        
        // Sort queue by priority
        this.notificationQueue.sort((a, b) => b.priority - a.priority);
        
        const notification = this.notificationQueue.shift();
        this.notifications.set(notification.id, notification);
        this.renderNotification(notification);
        
        // Auto-hide if not persistent
        if (!notification.persistent && notification.duration > 0) {
            setTimeout(() => {
                this.hide(notification.id);
            }, notification.duration);
        }
    }
    
    getTypePriority(type) {
        const priorities = {
            critical: 100,
            error: 80,
            connection: 70,
            warning: 60,
            info: 40,
            success: 20
        };
        
        return priorities[type] || 50;
    }
    
    escapeHtml(text) {
        const div = document.createElement('div');
        div.textContent = text;
        return div.innerHTML;
    }
    
    // Convenience methods for different notification types
    success(title, message, options = {}) {
        return this.show('success', title, message, options);
    }
    
    info(title, message, options = {}) {
        return this.show('info', title, message, options);
    }
    
    warning(title, message, options = {}) {
        return this.show('warning', title, message, options);
    }
    
    error(title, message, options = {}) {
        return this.show('error', title, message, options);
    }
    
    critical(title, message, options = {}) {
        return this.show('critical', title, message, { persistent: true, ...options });
    }
    
    connection(title, message, options = {}) {
        return this.show('connection', title, message, { 
            persistent: true, 
            replace: true,
            ...options 
        });
    }
    
    // Communication-specific notifications
    connectionLost(reason) {
        return this.connection(
            'Connection Lost',
            `Lost connection to server: ${reason}. Attempting to reconnect...`,
            {
                actions: [
                    {
                        id: 'retry',
                        label: 'Retry Now',
                        icon: 'fas fa-redo'
                    },
                    {
                        id: 'details',
                        label: 'Details',
                        icon: 'fas fa-info-circle',
                        keepOpen: true
                    }
                ],
                onAction: (action) => {
                    if (action.id === 'retry') {
                        this.retryConnection();
                    } else if (action.id === 'details') {
                        this.showConnectionDetails();
                    }
                }
            }
        );
    }
    
    connectionRestored() {
        this.removeByType('connection');
        return this.success(
            'Connection Restored',
            'Successfully reconnected to server. All features are now available.'
        );
    }
    
    pollingModeEnabled() {
        return this.warning(
            'Polling Mode Active',
            'Using polling for updates due to connection issues. Some features may be delayed.',
            {
                actions: [
                    {
                        id: 'retry_socket',
                        label: 'Retry Connection',
                        icon: 'fas fa-wifi'
                    }
                ],
                onAction: () => {
                    this.retryConnection();
                }
            }
        );
    }
    
    redisConnectionFailed() {
        return this.error(
            'Database Connection Failed',
            'Unable to connect to Redis database. Some features may not work properly.',
            {
                actions: [
                    {
                        id: 'retry_redis',
                        label: 'Retry',
                        icon: 'fas fa-database'
                    }
                ],
                onAction: () => {
                    this.retryRedisConnection();
                }
            }
        );
    }
    
    taskExecutionError(taskId, error) {
        return this.error(
            'Task Execution Failed',
            `Task ${taskId} failed: ${error}`,
            {
                actions: [
                    {
                        id: 'view_logs',
                        label: 'View Logs',
                        icon: 'fas fa-file-alt'
                    },
                    {
                        id: 'retry_task',
                        label: 'Retry Task',
                        icon: 'fas fa-redo'
                    }
                ],
                onAction: (action) => {
                    if (action.id === 'view_logs') {
                        this.showTaskLogs(taskId);
                    } else if (action.id === 'retry_task') {
                        this.retryTask(taskId);
                    }
                }
            }
        );
    }
    
    // Action handlers (to be implemented by integrating components)
    retryConnection() {
        console.log('🔄 Retrying connection...');
        if (window.uiManager && window.uiManager.socketManager) {
            window.uiManager.socketManager.forceReconnect();
        }
    }
    
    showConnectionDetails() {
        console.log('📊 Showing connection details...');
        // Implementation would show a detailed connection status modal
    }
    
    retryRedisConnection() {
        console.log('🔄 Retrying Redis connection...');
        // Implementation would retry Redis connection
    }
    
    showTaskLogs(taskId) {
        console.log(`📋 Showing logs for task ${taskId}...`);
        // Implementation would navigate to task logs
    }
    
    retryTask(taskId) {
        console.log(`🔄 Retrying task ${taskId}...`);
        // Implementation would retry the failed task
    }
    
    // Get notification statistics
    getStatistics() {
        const stats = {
            total: this.notifications.size,
            queued: this.notificationQueue.length,
            byType: {}
        };
        
        this.notifications.forEach(notification => {
            stats.byType[notification.type] = (stats.byType[notification.type] || 0) + 1;
        });
        
        return stats;
    }
    
    // Cleanup
    destroy() {
        this.hideAll();
        
        if (this.container && this.container.parentNode) {
            this.container.parentNode.removeChild(this.container);
        }
        
        const styles = document.getElementById('notification-styles');
        if (styles && styles.parentNode) {
            styles.parentNode.removeChild(styles);
        }
        
        console.log('🔔 NotificationSystem destroyed');
    }
}

// Make globally available
window.NotificationSystem = NotificationSystem;