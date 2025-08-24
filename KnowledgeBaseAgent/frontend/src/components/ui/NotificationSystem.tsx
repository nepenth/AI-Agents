import React from 'react';
import { X, CheckCircle, AlertTriangle, AlertCircle, Info, Zap } from 'lucide-react';
import { cn } from '@/utils/cn';
import { websocketService } from '@/services/websocket';

export interface Notification {
  id: string;
  type: 'success' | 'warning' | 'error' | 'info' | 'system';
  title: string;
  message: string;
  timestamp: Date;
  duration?: number; // Auto-dismiss after this many ms (0 = no auto-dismiss)
  actions?: Array<{
    label: string;
    action: () => void;
    variant?: 'primary' | 'secondary';
  }>;
}

interface NotificationSystemProps {
  className?: string;
  maxNotifications?: number;
  defaultDuration?: number;
}

export function NotificationSystem({ 
  className, 
  maxNotifications = 5,
  defaultDuration = 5000 
}: NotificationSystemProps) {
  const [notifications, setNotifications] = React.useState<Notification[]>([]);

  // Add notification
  const addNotification = React.useCallback((notification: Omit<Notification, 'id' | 'timestamp'>) => {
    const newNotification: Notification = {
      ...notification,
      id: `notification-${Date.now()}-${Math.random().toString(36).substr(2, 9)}`,
      timestamp: new Date(),
      duration: notification.duration ?? defaultDuration
    };

    setNotifications(prev => {
      const updated = [newNotification, ...prev];
      return updated.slice(0, maxNotifications);
    });

    // Auto-dismiss if duration is set
    if (newNotification.duration && newNotification.duration > 0) {
      setTimeout(() => {
        removeNotification(newNotification.id);
      }, newNotification.duration);
    }
  }, [defaultDuration, maxNotifications]);

  // Remove notification
  const removeNotification = React.useCallback((id: string) => {
    setNotifications(prev => prev.filter(n => n.id !== id));
  }, []);

  // Clear all notifications
  const clearAll = React.useCallback(() => {
    setNotifications([]);
  }, []);

  // Set up WebSocket listeners for real-time notifications
  React.useEffect(() => {
    const unsubscribeNotification = websocketService.subscribe('notification', (data: any) => {
      addNotification({
        type: data.level || 'info',
        title: data.title || 'System Notification',
        message: data.message,
        duration: data.duration
      });
    });

    const unsubscribeTaskProgress = websocketService.subscribe('task_progress', (data: any) => {
      if (data.status === 'completed') {
        addNotification({
          type: 'success',
          title: 'Task Completed',
          message: `${data.phase || 'Task'} completed successfully`,
          duration: 3000
        });
      } else if (data.status === 'failed') {
        addNotification({
          type: 'error',
          title: 'Task Failed',
          message: data.error || 'Task execution failed',
          duration: 0 // Don't auto-dismiss errors
        });
      }
    });

    const unsubscribeSystemStatus = websocketService.subscribe('system_status', (data: any) => {
      if (data.alert) {
        addNotification({
          type: data.alert.level || 'warning',
          title: 'System Alert',
          message: data.alert.message,
          duration: data.alert.critical ? 0 : 8000
        });
      }
    });

    const unsubscribeConnection = websocketService.subscribe('connection', (data: any) => {
      if (data.status === 'connected') {
        addNotification({
          type: 'success',
          title: 'Connected',
          message: 'Real-time updates are now active',
          duration: 2000
        });
      } else if (data.status === 'disconnected' && data.reconnectAttempts > 0) {
        addNotification({
          type: 'warning',
          title: 'Connection Lost',
          message: `Attempting to reconnect... (${data.reconnectAttempts}/5)`,
          duration: 3000
        });
      } else if (data.status === 'failed') {
        addNotification({
          type: 'error',
          title: 'Connection Failed',
          message: 'Unable to establish real-time connection',
          duration: 0,
          actions: [{
            label: 'Retry',
            action: () => websocketService.forceReconnect(),
            variant: 'primary'
          }]
        });
      }
    });

    return () => {
      unsubscribeNotification();
      unsubscribeTaskProgress();
      unsubscribeSystemStatus();
      unsubscribeConnection();
    };
  }, [addNotification]);

  const getNotificationIcon = (type: Notification['type']) => {
    switch (type) {
      case 'success':
        return CheckCircle;
      case 'warning':
        return AlertTriangle;
      case 'error':
        return AlertCircle;
      case 'system':
        return Zap;
      default:
        return Info;
    }
  };

  const getNotificationColors = (type: Notification['type']) => {
    switch (type) {
      case 'success':
        return {
          bg: 'bg-green-500/10 border-green-500/20',
          icon: 'text-green-500',
          title: 'text-green-400',
          text: 'text-green-300'
        };
      case 'warning':
        return {
          bg: 'bg-yellow-500/10 border-yellow-500/20',
          icon: 'text-yellow-500',
          title: 'text-yellow-400',
          text: 'text-yellow-300'
        };
      case 'error':
        return {
          bg: 'bg-red-500/10 border-red-500/20',
          icon: 'text-red-500',
          title: 'text-red-400',
          text: 'text-red-300'
        };
      case 'system':
        return {
          bg: 'bg-purple-500/10 border-purple-500/20',
          icon: 'text-purple-500',
          title: 'text-purple-400',
          text: 'text-purple-300'
        };
      default:
        return {
          bg: 'bg-blue-500/10 border-blue-500/20',
          icon: 'text-blue-500',
          title: 'text-blue-400',
          text: 'text-blue-300'
        };
    }
  };

  if (notifications.length === 0) {
    return null;
  }

  return (
    <div className={cn(
      'fixed top-4 right-4 z-50 space-y-2 max-w-sm w-full',
      className
    )}>
      {notifications.map((notification) => {
        const Icon = getNotificationIcon(notification.type);
        const colors = getNotificationColors(notification.type);

        return (
          <div
            key={notification.id}
            className={cn(
              'p-4 rounded-xl border backdrop-blur-md shadow-lg animate-in slide-in-from-right-full duration-300',
              colors.bg
            )}
          >
            <div className="flex items-start gap-3">
              <Icon className={cn('h-5 w-5 mt-0.5 flex-shrink-0', colors.icon)} />
              
              <div className="flex-1 min-w-0">
                <div className="flex items-start justify-between gap-2">
                  <h4 className={cn('font-semibold text-sm', colors.title)}>
                    {notification.title}
                  </h4>
                  <button
                    onClick={() => removeNotification(notification.id)}
                    className="text-muted-foreground hover:text-foreground transition-colors"
                  >
                    <X className="h-4 w-4" />
                  </button>
                </div>
                
                <p className={cn('text-sm mt-1', colors.text)}>
                  {notification.message}
                </p>
                
                <div className="flex items-center justify-between mt-2">
                  <span className="text-xs text-muted-foreground">
                    {notification.timestamp.toLocaleTimeString()}
                  </span>
                  
                  {notification.actions && notification.actions.length > 0 && (
                    <div className="flex gap-2">
                      {notification.actions.map((action, index) => (
                        <button
                          key={index}
                          onClick={() => {
                            action.action();
                            removeNotification(notification.id);
                          }}
                          className={cn(
                            'px-2 py-1 rounded text-xs font-medium transition-colors',
                            action.variant === 'primary'
                              ? 'bg-primary text-primary-foreground hover:bg-primary/90'
                              : 'bg-muted text-muted-foreground hover:bg-muted/80'
                          )}
                        >
                          {action.label}
                        </button>
                      ))}
                    </div>
                  )}
                </div>
              </div>
            </div>
          </div>
        );
      })}
      
      {notifications.length > 1 && (
        <div className="flex justify-end">
          <button
            onClick={clearAll}
            className="text-xs text-muted-foreground hover:text-foreground transition-colors px-2 py-1 rounded bg-black/20 backdrop-blur-sm"
          >
            Clear all
          </button>
        </div>
      )}
    </div>
  );
}

// Hook for programmatically adding notifications
export function useNotifications() {
  const addNotification = React.useCallback((notification: Omit<Notification, 'id' | 'timestamp'>) => {
    // This would typically dispatch to a global notification store
    // For now, we'll use a custom event
    window.dispatchEvent(new CustomEvent('add-notification', { detail: notification }));
  }, []);

  const showSuccess = React.useCallback((title: string, message: string, duration?: number) => {
    addNotification({ type: 'success', title, message, duration });
  }, [addNotification]);

  const showError = React.useCallback((title: string, message: string, duration?: number) => {
    addNotification({ type: 'error', title, message, duration: duration ?? 0 });
  }, [addNotification]);

  const showWarning = React.useCallback((title: string, message: string, duration?: number) => {
    addNotification({ type: 'warning', title, message, duration });
  }, [addNotification]);

  const showInfo = React.useCallback((title: string, message: string, duration?: number) => {
    addNotification({ type: 'info', title, message, duration });
  }, [addNotification]);

  return {
    addNotification,
    showSuccess,
    showError,
    showWarning,
    showInfo
  };
}