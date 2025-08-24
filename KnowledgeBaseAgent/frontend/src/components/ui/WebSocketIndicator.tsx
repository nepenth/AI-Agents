import React from 'react';
import { Wifi, WifiOff, AlertTriangle } from 'lucide-react';
import { cn } from '@/utils/cn';
import { websocketService } from '@/services/websocket';

interface WebSocketIndicatorProps {
  className?: string;
  showText?: boolean;
  size?: 'sm' | 'md' | 'lg';
}

export function WebSocketIndicator({ 
  className, 
  showText = false, 
  size = 'md' 
}: WebSocketIndicatorProps) {
  const [connectionState, setConnectionState] = React.useState(websocketService.connectionState);
  const [lastConnected, setLastConnected] = React.useState(websocketService.lastConnectedTime);
  const [reconnectAttempts, setReconnectAttempts] = React.useState(websocketService.currentReconnectAttempts);

  React.useEffect(() => {
    const unsubscribe = websocketService.subscribe('connection', (data: any) => {
      setConnectionState(data.status);
      setLastConnected(data.lastConnected || websocketService.lastConnectedTime);
      setReconnectAttempts(data.reconnectAttempts || websocketService.currentReconnectAttempts);
    });

    // Update initial state
    setConnectionState(websocketService.connectionState);
    setLastConnected(websocketService.lastConnectedTime);
    setReconnectAttempts(websocketService.currentReconnectAttempts);

    return unsubscribe;
  }, []);

  const getStatusInfo = () => {
    switch (connectionState) {
      case 'connected':
        return {
          icon: Wifi,
          color: 'text-green-500',
          bgColor: 'bg-green-500/20',
          borderColor: 'border-green-500/30',
          text: 'Connected',
          description: 'Real-time updates active'
        };
      case 'connecting':
        return {
          icon: Wifi,
          color: 'text-yellow-500',
          bgColor: 'bg-yellow-500/20',
          borderColor: 'border-yellow-500/30',
          text: 'Connecting...',
          description: 'Establishing connection'
        };
      case 'disconnected':
        return {
          icon: WifiOff,
          color: 'text-red-500',
          bgColor: 'bg-red-500/20',
          borderColor: 'border-red-500/30',
          text: reconnectAttempts > 0 ? `Reconnecting (${reconnectAttempts})` : 'Disconnected',
          description: lastConnected 
            ? `Last connected: ${lastConnected.toLocaleTimeString()}`
            : 'No connection established'
        };
      case 'closing':
        return {
          icon: AlertTriangle,
          color: 'text-orange-500',
          bgColor: 'bg-orange-500/20',
          borderColor: 'border-orange-500/30',
          text: 'Closing...',
          description: 'Connection closing'
        };
      default:
        return {
          icon: WifiOff,
          color: 'text-gray-500',
          bgColor: 'bg-gray-500/20',
          borderColor: 'border-gray-500/30',
          text: 'Unknown',
          description: 'Connection status unknown'
        };
    }
  };

  const statusInfo = getStatusInfo();
  const Icon = statusInfo.icon;

  const iconSize = {
    sm: 'h-3 w-3',
    md: 'h-4 w-4',
    lg: 'h-5 w-5'
  }[size];

  const textSize = {
    sm: 'text-xs',
    md: 'text-sm',
    lg: 'text-base'
  }[size];

  const handleClick = () => {
    if (connectionState === 'disconnected') {
      websocketService.forceReconnect();
    }
  };

  if (showText) {
    return (
      <div 
        className={cn(
          'flex items-center gap-2 px-3 py-1 rounded-full border cursor-pointer transition-all duration-200 hover:opacity-80',
          statusInfo.bgColor,
          statusInfo.borderColor,
          textSize,
          className
        )}
        onClick={handleClick}
        title={statusInfo.description}
      >
        <Icon className={cn(iconSize, statusInfo.color)} />
        <span className={cn('font-medium', statusInfo.color)}>
          {statusInfo.text}
        </span>
      </div>
    );
  }

  return (
    <div
      className={cn(
        'flex items-center justify-center p-2 rounded-full border cursor-pointer transition-all duration-200 hover:opacity-80',
        statusInfo.bgColor,
        statusInfo.borderColor,
        className
      )}
      onClick={handleClick}
      title={`${statusInfo.text} - ${statusInfo.description}`}
    >
      <Icon className={cn(iconSize, statusInfo.color)} />
    </div>
  );
}

// Hook for getting WebSocket connection status
export function useWebSocketStatus() {
  const [connectionState, setConnectionState] = React.useState(websocketService.connectionState);
  const [lastConnected, setLastConnected] = React.useState(websocketService.lastConnectedTime);
  const [reconnectAttempts, setReconnectAttempts] = React.useState(websocketService.currentReconnectAttempts);

  React.useEffect(() => {
    const unsubscribe = websocketService.subscribe('connection', (data: any) => {
      setConnectionState(data.status);
      setLastConnected(data.lastConnected || websocketService.lastConnectedTime);
      setReconnectAttempts(data.reconnectAttempts || websocketService.currentReconnectAttempts);
    });

    // Update initial state
    setConnectionState(websocketService.connectionState);
    setLastConnected(websocketService.lastConnectedTime);
    setReconnectAttempts(websocketService.currentReconnectAttempts);

    return unsubscribe;
  }, []);

  return {
    connectionState,
    isConnected: connectionState === 'connected',
    isConnecting: connectionState === 'connecting',
    isDisconnected: connectionState === 'disconnected',
    lastConnected,
    reconnectAttempts,
    forceReconnect: () => websocketService.forceReconnect()
  };
}