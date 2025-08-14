import { useEffect, useCallback, useRef } from 'react';
import { websocketService, WebSocketEventHandler } from '@/services/websocket';

export function useWebSocket() {
  const isConnectedRef = useRef(false);

  useEffect(() => {
    const connect = async () => {
      if (!isConnectedRef.current) {
        try {
          await websocketService.connect();
          isConnectedRef.current = true;
        } catch (error) {
          console.error('Failed to connect to WebSocket:', error);
        }
      }
    };

    connect();

    return () => {
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

  return {
    subscribe,
    send,
    isConnected: websocketService.isConnected,
    connectionState: websocketService.connectionState,
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