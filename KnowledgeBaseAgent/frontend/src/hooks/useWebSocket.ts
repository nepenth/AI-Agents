import { useEffect, useCallback, useRef, useState } from 'react';
import { websocketService, WebSocketEventHandler } from '@/services/websocket';
import type { ConnectionStatus } from '@/components/ui/WebSocketIndicator';

export function useWebSocket() {
  const isConnectedRef = useRef(false);
  const [connectionStatus, setConnectionStatus] = useState<ConnectionStatus>('disconnected');
  const [lastConnected, setLastConnected] = useState<Date | null>(null);
  const [reconnectAttempts, setReconnectAttempts] = useState(0);

  // Map websocket service state to component status
  const mapConnectionState = useCallback((state: string): ConnectionStatus => {
    switch (state) {
      case 'connecting':
        return 'connecting';
      case 'connected':
        return 'connected';
      case 'closing':
      case 'disconnected':
        return 'disconnected';
      default:
        return 'error';
    }
  }, []);

  useEffect(() => {
    const connect = async () => {
      if (!isConnectedRef.current) {
        try {
          setConnectionStatus('connecting');
          await websocketService.connect();
          isConnectedRef.current = true;
          setConnectionStatus('connected');
          setLastConnected(new Date());
          setReconnectAttempts(0);
        } catch (error) {
          console.error('Failed to connect to WebSocket:', error);
          setConnectionStatus('error');
        }
      }
    };

    // Subscribe to connection events
    const unsubscribeConnection = websocketService.subscribe('connection', (data) => {
      if (data.status === 'connected') {
        setConnectionStatus('connected');
        setLastConnected(data.timestamp || new Date());
        setReconnectAttempts(0);
      } else if (data.status === 'disconnected') {
        setConnectionStatus('disconnected');
        setReconnectAttempts(data.reconnectAttempts || 0);
        if (data.lastConnected) {
          setLastConnected(new Date(data.lastConnected));
        }
      } else if (data.status === 'error') {
        setConnectionStatus('error');
      }
    });

    connect();

    return () => {
      unsubscribeConnection();
      websocketService.disconnect();
      isConnectedRef.current = false;
    };
  }, []);

  const subscribe = useCallback((event: string, handler: WebSocketEventHandler) => {
    return websocketService.subscribe(event, handler);
  }, []);

  const send = useCallback((type: string, payload: any) => {
    websocketService.send(type, payload);
  }, []);

  const reconnect = useCallback(() => {
    websocketService.forceReconnect();
  }, []);

  return {
    subscribe,
    send,
    reconnect,
    isConnected: websocketService.isConnected,
    connectionState: websocketService.connectionState,
    connectionStatus,
    lastConnected,
    reconnectAttempts,
  };
}

export function useWebSocketEvent(
  event: string,
  handler: WebSocketEventHandler,
  dependencies: any[] = []
) {
  const { subscribe } = useWebSocket();

  useEffect(() => {
    const unsubscribe = subscribe(event, handler);
    return unsubscribe;
  }, [subscribe, event, ...dependencies]);
}