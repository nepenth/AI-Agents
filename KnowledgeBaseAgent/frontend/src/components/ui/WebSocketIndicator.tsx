import React from 'react'
import { Wifi, WifiOff, Loader2, AlertTriangle } from 'lucide-react'
import { cn } from '@/utils/cn'

export type ConnectionStatus = 'connected' | 'connecting' | 'disconnected' | 'error'

export interface WebSocketIndicatorProps {
  status?: ConnectionStatus
  className?: string
  showLabel?: boolean
  size?: 'sm' | 'md' | 'lg'
  lastConnected?: Date
  reconnectAttempts?: number
  onReconnect?: () => void
}

const statusConfig = {
  connected: {
    icon: <Wifi className="h-4 w-4" />,
    label: 'Connected',
    color: 'text-green-600',
    bgColor: 'bg-green-50',
    borderColor: 'border-green-200'
  },
  connecting: {
    icon: <Loader2 className="h-4 w-4 animate-spin" />,
    label: 'Connecting...',
    color: 'text-yellow-600',
    bgColor: 'bg-yellow-50',
    borderColor: 'border-yellow-200'
  },
  disconnected: {
    icon: <WifiOff className="h-4 w-4" />,
    label: 'Disconnected',
    color: 'text-red-600',
    bgColor: 'bg-red-50',
    borderColor: 'border-red-200'
  },
  error: {
    icon: <AlertTriangle className="h-4 w-4" />,
    label: 'Connection Error',
    color: 'text-red-600',
    bgColor: 'bg-red-50',
    borderColor: 'border-red-200'
  }
}

export const WebSocketIndicator: React.FC<WebSocketIndicatorProps> = ({
  status = 'disconnected', // Provide default value
  className,
  showLabel = true,
  size = 'md',
  lastConnected,
  reconnectAttempts = 0,
  onReconnect
}) => {
  // Ensure we have a valid config, fallback to disconnected if status is invalid
  const config = statusConfig[status] || statusConfig.disconnected
  
  const sizeClasses = {
    sm: 'px-2 py-1 text-xs',
    md: 'px-3 py-1 text-sm',
    lg: 'px-4 py-2 text-base'
  }
  
  const formatLastConnected = (date: Date) => {
    const now = new Date()
    const diff = now.getTime() - date.getTime()
    const minutes = Math.floor(diff / 60000)
    const hours = Math.floor(minutes / 60)
    
    if (minutes < 1) return 'Just now'
    if (minutes < 60) return `${minutes}m ago`
    if (hours < 24) return `${hours}h ago`
    return date.toLocaleDateString()
  }
  
  return (
    <div className={cn('inline-flex items-center gap-2', className)}>
      <div
        className={cn(
          'inline-flex items-center gap-2 rounded-full border',
          config.bgColor,
          config.borderColor,
          sizeClasses[size]
        )}
      >
        <span className={cn('inline-block', config.color)}>
          {config.icon}
        </span>
        {showLabel && (
          <span className={cn('font-medium', config.color)}>
            {config.label}
          </span>
        )}
      </div>
      
      {/* Additional status information */}
      {(status === 'disconnected' || status === 'error') && (
        <div className="flex items-center gap-2">
          {lastConnected && (
            <span className="text-xs text-muted-foreground">
              Last: {formatLastConnected(lastConnected)}
            </span>
          )}
          {reconnectAttempts > 0 && (
            <span className="text-xs text-muted-foreground">
              Attempts: {reconnectAttempts}
            </span>
          )}
          {onReconnect && (
            <button
              onClick={onReconnect}
              className="text-xs text-primary hover:text-primary/80 underline"
            >
              Reconnect
            </button>
          )}
        </div>
      )}
    </div>
  )
}

// Utility component for simple status dot
export const ConnectionDot: React.FC<{ status?: ConnectionStatus; className?: string }> = ({
  status = 'disconnected',
  className
}) => {
  const config = statusConfig[status] || statusConfig.disconnected
  
  return (
    <div
      className={cn(
        'w-3 h-3 rounded-full border-2 border-background shadow-sm',
        {
          'bg-green-500': status === 'connected',
          'bg-yellow-500 animate-pulse': status === 'connecting',
          'bg-red-500': status === 'disconnected' || status === 'error'
        },
        className
      )}
      title={config.label}
    />
  )
}