import React, { useState, useEffect } from 'react'
import { X, AlertTriangle, AlertCircle, Info, CheckCircle, RefreshCw } from 'lucide-react'
import { GlassCard } from '@/components/ui/GlassCard'
import { Button } from '@/components/ui/Button'
import { Badge } from '@/components/ui/Badge'
import { errorService, ErrorReport, ErrorRecoveryAction } from '@/services/errorService'
import { cn } from '@/utils/cn'

interface ErrorNotificationProps {
  error: ErrorReport
  onDismiss: () => void
  onRecover?: (action: ErrorRecoveryAction) => void
  autoHide?: boolean
  hideDelay?: number
}

export function ErrorNotification({
  error,
  onDismiss,
  onRecover,
  autoHide = false,
  hideDelay = 5000
}: ErrorNotificationProps) {
  const [isVisible, setIsVisible] = useState(true)
  const [isRecovering, setIsRecovering] = useState(false)
  const [recoveryActions, setRecoveryActions] = useState<ErrorRecoveryAction[]>([])

  useEffect(() => {
    // Get recovery actions for this error
    const actions = errorService.getRecoveryActions(error)
    setRecoveryActions(actions)

    // Auto-hide for non-critical errors
    if (autoHide && error.severity !== 'critical') {
      const timer = setTimeout(() => {
        handleDismiss()
      }, hideDelay)

      return () => clearTimeout(timer)
    }
  }, [error, autoHide, hideDelay])

  const handleDismiss = () => {
    setIsVisible(false)
    setTimeout(onDismiss, 300) // Allow animation to complete
  }

  const handleRecoveryAction = async (action: ErrorRecoveryAction) => {
    setIsRecovering(true)
    
    try {
      await action.action()
      
      if (onRecover) {
        onRecover(action)
      }
      
      // Auto-dismiss after successful recovery
      if (action.type === 'retry' || action.type === 'reset') {
        handleDismiss()
      }
    } catch (recoveryError) {
      console.error('Recovery action failed:', recoveryError)
      // Show error but don't dismiss notification
    } finally {
      setIsRecovering(false)
    }
  }

  const getIcon = () => {
    switch (error.severity) {
      case 'critical':
        return <AlertTriangle className="h-5 w-5 text-red-500" />
      case 'high':
        return <AlertCircle className="h-5 w-5 text-orange-500" />
      case 'medium':
        return <Info className="h-5 w-5 text-blue-500" />
      case 'low':
        return <CheckCircle className="h-5 w-5 text-green-500" />
      default:
        return <Info className="h-5 w-5 text-gray-500" />
    }
  }

  const getSeverityColor = () => {
    switch (error.severity) {
      case 'critical':
        return 'border-l-red-500 bg-red-50/10'
      case 'high':
        return 'border-l-orange-500 bg-orange-50/10'
      case 'medium':
        return 'border-l-blue-500 bg-blue-50/10'
      case 'low':
        return 'border-l-green-500 bg-green-50/10'
      default:
        return 'border-l-gray-500 bg-gray-50/10'
    }
  }

  const getBadgeVariant = () => {
    switch (error.severity) {
      case 'critical':
      case 'high':
        return 'destructive'
      case 'medium':
        return 'outline'
      case 'low':
        return 'secondary'
      default:
        return 'outline'
    }
  }

  if (!isVisible) return null

  return (
    <div className={cn(
      'fixed top-4 right-4 z-50 max-w-md w-full transition-all duration-300',
      isVisible ? 'translate-x-0 opacity-100' : 'translate-x-full opacity-0'
    )}>
      <GlassCard className={cn(
        'p-4 border-l-4',
        getSeverityColor()
      )}>
        <div className="flex items-start justify-between mb-3">
          <div className="flex items-center gap-2">
            {getIcon()}
            <div>
              <div className="font-medium text-foreground">
                {error.type.replace('_', ' ').replace(/\b\w/g, l => l.toUpperCase())}
              </div>
              <Badge variant={getBadgeVariant() as any} className="text-xs">
                {error.severity.toUpperCase()}
              </Badge>
            </div>
          </div>
          
          <Button
            variant="ghost"
            size="sm"
            onClick={handleDismiss}
            className="h-6 w-6 p-0"
          >
            <X className="h-4 w-4" />
          </Button>
        </div>

        <div className="mb-3">
          <p className="text-sm text-foreground mb-1">
            {error.message}
          </p>
          
          {error.details.context && (
            <p className="text-xs text-muted-foreground">
              {error.details.context.component && `Component: ${error.details.context.component}`}
              {error.details.context.operation && ` • Operation: ${error.details.context.operation}`}
            </p>
          )}
        </div>

        {/* Recovery Actions */}
        {recoveryActions.length > 0 && (
          <div className="space-y-2">
            <div className="text-xs font-medium text-muted-foreground">
              Recovery Options:
            </div>
            
            <div className="flex flex-wrap gap-2">
              {recoveryActions.slice(0, 2).map((action) => (
                <Button
                  key={action.id}
                  size="sm"
                  variant="outline"
                  onClick={() => handleRecoveryAction(action)}
                  disabled={isRecovering}
                  className="text-xs"
                >
                  {isRecovering ? (
                    <RefreshCw className="h-3 w-3 animate-spin mr-1" />
                  ) : null}
                  {action.label}
                </Button>
              ))}
              
              {recoveryActions.length > 2 && (
                <Button
                  size="sm"
                  variant="ghost"
                  className="text-xs"
                  onClick={() => {
                    // Show all recovery actions in a modal or expanded view
                    console.log('Show all recovery actions:', recoveryActions)
                  }}
                >
                  +{recoveryActions.length - 2} more
                </Button>
              )}
            </div>
          </div>
        )}

        {/* Timestamp */}
        <div className="mt-3 pt-2 border-t border-border">
          <p className="text-xs text-muted-foreground">
            {new Date(error.timestamp).toLocaleTimeString()}
          </p>
        </div>
      </GlassCard>
    </div>
  )
}

// Error notification manager component
interface ErrorNotificationManagerProps {
  maxNotifications?: number
}

export function ErrorNotificationManager({ maxNotifications = 3 }: ErrorNotificationManagerProps) {
  const [notifications, setNotifications] = useState<ErrorReport[]>([])

  useEffect(() => {
    // Listen for new errors from the error service
    const checkForNewErrors = () => {
      const recentErrors = errorService.getRecentErrors(maxNotifications)
      const newErrors = recentErrors.filter(error => 
        !notifications.some(notification => notification.id === error.id)
      )
      
      if (newErrors.length > 0) {
        setNotifications(prev => [...newErrors, ...prev].slice(0, maxNotifications))
      }
    }

    // Check for new errors every second
    const interval = setInterval(checkForNewErrors, 1000)
    
    // Initial check
    checkForNewErrors()

    return () => clearInterval(interval)
  }, [notifications, maxNotifications])

  const handleDismiss = (errorId: string) => {
    setNotifications(prev => prev.filter(notification => notification.id !== errorId))
  }

  const handleRecover = (errorId: string, action: ErrorRecoveryAction) => {
    console.log(`Recovery action ${action.id} executed for error ${errorId}`)
    // Optionally remove the notification after successful recovery
    if (action.type === 'retry' || action.type === 'reset') {
      handleDismiss(errorId)
    }
  }

  return (
    <div className="fixed top-4 right-4 z-50 space-y-2">
      {notifications.map((error, index) => (
        <div
          key={error.id}
          style={{ transform: `translateY(${index * 10}px)` }}
        >
          <ErrorNotification
            error={error}
            onDismiss={() => handleDismiss(error.id)}
            onRecover={(action) => handleRecover(error.id, action)}
            autoHide={error.severity === 'low' || error.severity === 'medium'}
            hideDelay={error.severity === 'low' ? 3000 : 5000}
          />
        </div>
      ))}
    </div>
  )
}