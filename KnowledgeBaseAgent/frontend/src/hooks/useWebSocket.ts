import { useEffect, useCallback, useRef, useState } from 'react';
import { websocketService, WebSocketEventHandler } from '@/services/websocket';
import type { ConnectionStatus } from '@/components/ui/WebSocketIndicator';

export function useWebSocket() {
  const isConnectedRef = useRef(false);
  const [connectionStatus, setConnectionStatus] = useState<ConnectionStatus>('disconnected');
  const [lastConnected, setLastConnected] = useState<Date | null>(null);
  const [reconnectAttempts, setReconnectAttempts] = useState(0);



  useEffect(() => {
    let timeoutId: NodeJS.Timeout;

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
          setConnectionStatus('disconnected');
          isConnectedRef.current = false;
        }
      }
    };

    // Subscribe to connection events
    const unsubscribeConnection = websocketService.subscribe('connection', (data) => {
      if (data.status === 'connected') {
        setConnectionStatus('connected');
        setLastConnected(data.timestamp || new Date());
        setReconnectAttempts(0);
        isConnectedRef.current = true;
      } else if (data.status === 'disconnected') {
        setConnectionStatus('disconnected');
        setReconnectAttempts(data.reconnectAttempts || 0);
        isConnectedRef.current = false;
        if (data.lastConnected) {
          setLastConnected(new Date(data.lastConnected));
        }
      } else if (data.status === 'error') {
        setConnectionStatus('error');
        isConnectedRef.current = false;
      } else if (data.status === 'failed') {
        setConnectionStatus('error');
        isConnectedRef.current = false;
      }
    });

    // Delay initial connection attempt to allow app to fully load
    timeoutId = setTimeout(() => {
      connect();
    }, 1000);

    return () => {
      clearTimeout(timeoutId);
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