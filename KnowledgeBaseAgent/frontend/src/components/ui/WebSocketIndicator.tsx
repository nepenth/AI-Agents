import React from 'react';
import { cn } from '../../utils/cn';

export type ConnectionStatus = 'connected' | 'connecting' | 'disconnected' | 'error';

export interface WebSocketIndicatorProps {
  status: ConnectionStatus;
  className?: string;
  showLabel?: boolean;
  size?: 'sm' | 'md' | 'lg';
  lastConnected?: Date;
  reconnectAttempts?: number;
  onReconnect?: () => void;
}

const statusConfig = {
  connected: {
    icon: '🟢',
    label: 'Connected',
    color: 'text-green-600',
    bgColor: 'bg-green-100',
    borderColor: 'border-green-200'
  },
  connecting: {
    icon: '🟡',
    label: 'Connecting...',
    color: 'text-yellow-600',
    bgColor: 'bg-yellow-100',
    borderColor: 'border-yellow-200'
  },
  disconnected: {
    icon: '🔴',
    label: 'Disconnected',
    color: 'text-red-600',
    bgColor: 'bg-red-100',
    borderColor: 'border-red-200'
  },
  error: {
    icon: '❌',
    label: 'Connection Error',
    color: 'text-red-600',
    bgColor: 'bg-red-100',
    borderColor: 'border-red-200'
  }
};\n\nexport const WebSocketIndicator: React.FC<WebSocketIndicatorProps> = ({\n  status,\n  className,\n  showLabel = true,\n  size = 'md',\n  lastConnected,\n  reconnectAttempts = 0,\n  onReconnect\n}) => {\n  const config = statusConfig[status];\n  \n  const sizeClasses = {\n    sm: 'px-2 py-1 text-xs',\n    md: 'px-3 py-1 text-sm',\n    lg: 'px-4 py-2 text-base'\n  };\n  \n  const formatLastConnected = (date: Date) => {\n    const now = new Date();\n    const diff = now.getTime() - date.getTime();\n    const minutes = Math.floor(diff / 60000);\n    const hours = Math.floor(minutes / 60);\n    \n    if (minutes < 1) return 'Just now';\n    if (minutes < 60) return `${minutes}m ago`;\n    if (hours < 24) return `${hours}h ago`;\n    return date.toLocaleDateString();\n  };\n  \n  return (\n    <div className={cn('inline-flex items-center gap-2', className)}>\n      <div\n        className={cn(\n          'inline-flex items-center gap-2 rounded-full border',\n          config.bgColor,\n          config.borderColor,\n          sizeClasses[size]\n        )}\n      >\n        <span \n          className={cn(\n            'inline-block',\n            {\n              'animate-pulse': status === 'connecting'\n            }\n          )}\n        >\n          {config.icon}\n        </span>\n        {showLabel && (\n          <span className={cn('font-medium', config.color)}>\n            {config.label}\n          </span>\n        )}\n      </div>\n      \n      {/* Additional status information */}\n      {(status === 'disconnected' || status === 'error') && (\n        <div className=\"flex items-center gap-2\">\n          {lastConnected && (\n            <span className=\"text-xs text-gray-500\">\n              Last: {formatLastConnected(lastConnected)}\n            </span>\n          )}\n          {reconnectAttempts > 0 && (\n            <span className=\"text-xs text-gray-500\">\n              Attempts: {reconnectAttempts}\n            </span>\n          )}\n          {onReconnect && (\n            <button\n              onClick={onReconnect}\n              className=\"text-xs text-blue-600 hover:text-blue-800 underline\"\n            >\n              Reconnect\n            </button>\n          )}\n        </div>\n      )}\n    </div>\n  );\n};\n\n// Utility component for simple status dot\nexport const ConnectionDot: React.FC<{ status: ConnectionStatus; className?: string }> = ({\n  status,\n  className\n}) => {\n  const config = statusConfig[status];\n  \n  return (\n    <div\n      className={cn(\n        'w-3 h-3 rounded-full border-2 border-white shadow-sm',\n        {\n          'bg-green-500': status === 'connected',\n          'bg-yellow-500 animate-pulse': status === 'connecting',\n          'bg-red-500': status === 'disconnected' || status === 'error'\n        },\n        className\n      )}\n      title={config.label}\n    />\n  );\n};