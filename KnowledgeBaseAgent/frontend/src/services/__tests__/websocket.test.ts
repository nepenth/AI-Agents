import { WebSocketService } from '../websocket';

// Mock WebSocket
class MockWebSocket {
  static CONNECTING = 0;
  static OPEN = 1;
  static CLOSING = 2;
  static CLOSED = 3;

  readyState = MockWebSocket.CONNECTING;
  url: string;
  onopen: ((event: Event) => void) | null = null;
  onclose: ((event: CloseEvent) => void) | null = null;
  onmessage: ((event: MessageEvent) => void) | null = null;
  onerror: ((event: Event) => void) | null = null;

  constructor(url: string) {
    this.url = url;
    // Simulate connection after a short delay
    setTimeout(() => {
      this.readyState = MockWebSocket.OPEN;
      this.onopen?.(new Event('open'));
    }, 10);
  }

  send(data: string) {
    if (this.readyState !== MockWebSocket.OPEN) {
      throw new Error('WebSocket is not open');
    }
    // Mock sending data
  }

  close(code?: number, reason?: string) {
    this.readyState = MockWebSocket.CLOSED;
    const closeEvent = new CloseEvent('close', { code, reason, wasClean: true });
    this.onclose?.(closeEvent);
  }

  // Helper method to simulate receiving a message
  simulateMessage(data: any) {
    if (this.readyState === MockWebSocket.OPEN) {
      const messageEvent = new MessageEvent('message', { 
        data: JSON.stringify(data) 
      });
      this.onmessage?.(messageEvent);
    }
  }

  // Helper method to simulate connection error
  simulateError() {
    this.onerror?.(new Event('error'));
  }
}

// Replace global WebSocket with mock
(global as any).WebSocket = MockWebSocket;

describe('WebSocketService', () => {
  let service: WebSocketService;
  let mockWebSocket: MockWebSocket;

  beforeEach(() => {
    service = new WebSocketService('ws://localhost:8000/ws');
    jest.clearAllMocks();
  });

  afterEach(() => {
    service.disconnect();
  });

  describe('connection management', () => {
    it('should connect successfully', async () => {
      const connectionPromise = service.connect();
      
      // Wait for connection to complete
      await connectionPromise;
      
      expect(service.isConnected).toBe(true);
      expect(service.connectionState).toBe('connected');
    });

    it('should handle connection errors', async () => {
      const originalWebSocket = (global as any).WebSocket;
      
      // Mock WebSocket constructor to throw error
      (global as any).WebSocket = jest.fn(() => {
        throw new Error('Connection failed');
      });

      await expect(service.connect()).rejects.toThrow('Connection failed');
      
      // Restore original WebSocket
      (global as any).WebSocket = originalWebSocket;
    });

    it('should disconnect cleanly', async () => {
      await service.connect();
      expect(service.isConnected).toBe(true);
      
      service.disconnect();
      expect(service.isConnected).toBe(false);
    });

    it('should track last connected time', async () => {
      const beforeConnect = new Date();
      await service.connect();
      const afterConnect = new Date();
      
      const lastConnected = service.lastConnectedTime;
      expect(lastConnected).toBeInstanceOf(Date);
      expect(lastConnected!.getTime()).toBeGreaterThanOrEqual(beforeConnect.getTime());
      expect(lastConnected!.getTime()).toBeLessThanOrEqual(afterConnect.getTime());
    });
  });

  describe('message handling', () => {
    beforeEach(async () => {
      await service.connect();
      mockWebSocket = (service as any).ws;
    });

    it('should send messages when connected', () => {
      const sendSpy = jest.spyOn(mockWebSocket, 'send');
      
      const result = service.send('test_message', { data: 'test' });
      
      expect(result).toBe(true);
      expect(sendSpy).toHaveBeenCalledWith(
        JSON.stringify({
          type: 'test_message',
          payload: { data: 'test' },
          timestamp: expect.any(String)
        })
      );
    });

    it('should queue messages when disconnected', () => {
      service.disconnect();
      
      const result = service.send('test_message', { data: 'test' });
      
      expect(result).toBe(false);
      expect(service.currentReconnectAttempts).toBe(0);
    });

    it('should process queued messages on reconnection', async () => {
      // Disconnect and queue a message
      service.disconnect();
      service.send('queued_message', { data: 'queued' });
      
      // Reconnect
      await service.connect();
      mockWebSocket = (service as any).ws;
      const sendSpy = jest.spyOn(mockWebSocket, 'send');
      
      // Trigger message queue processing
      (service as any).processMessageQueue();
      
      expect(sendSpy).toHaveBeenCalledWith(
        JSON.stringify({
          type: 'queued_message',
          payload: { data: 'queued' },
          timestamp: expect.any(String)
        })
      );
    });

    it('should handle incoming messages', async () => {
      const handler = jest.fn();
      service.subscribe('test_event', handler);
      
      // Simulate receiving a message
      mockWebSocket.simulateMessage({
        type: 'test_event',
        payload: { message: 'hello' },
        timestamp: new Date().toISOString()
      });
      
      expect(handler).toHaveBeenCalledWith({ message: 'hello' });
    });

    it('should handle malformed messages gracefully', () => {
      const consoleSpy = jest.spyOn(console, 'error').mockImplementation();
      
      // Simulate receiving malformed message
      const messageEvent = new MessageEvent('message', { 
        data: 'invalid json' 
      });
      mockWebSocket.onmessage?.(messageEvent);
      
      expect(consoleSpy).toHaveBeenCalledWith(
        'Failed to parse WebSocket message:',
        expect.any(Error)
      );
      
      consoleSpy.mockRestore();
    });
  });

  describe('event subscription', () => {
    beforeEach(async () => {
      await service.connect();
    });

    it('should subscribe and unsubscribe from events', () => {
      const handler = jest.fn();
      
      const unsubscribe = service.subscribe('test_event', handler);
      expect(typeof unsubscribe).toBe('function');
      
      // Test that handler is called
      (service as any).emit('test_event', { data: 'test' });
      expect(handler).toHaveBeenCalledWith({ data: 'test' });
      
      // Test unsubscribe
      unsubscribe();
      (service as any).emit('test_event', { data: 'test2' });
      expect(handler).toHaveBeenCalledTimes(1); // Should not be called again
    });

    it('should handle multiple subscribers for the same event', () => {
      const handler1 = jest.fn();
      const handler2 = jest.fn();
      
      service.subscribe('test_event', handler1);
      service.subscribe('test_event', handler2);
      
      (service as any).emit('test_event', { data: 'test' });
      
      expect(handler1).toHaveBeenCalledWith({ data: 'test' });
      expect(handler2).toHaveBeenCalledWith({ data: 'test' });
    });

    it('should handle errors in event handlers gracefully', () => {
      const consoleSpy = jest.spyOn(console, 'error').mockImplementation();
      const errorHandler = jest.fn(() => {
        throw new Error('Handler error');
      });
      const normalHandler = jest.fn();
      
      service.subscribe('test_event', errorHandler);
      service.subscribe('test_event', normalHandler);
      
      (service as any).emit('test_event', { data: 'test' });
      
      expect(errorHandler).toHaveBeenCalled();
      expect(normalHandler).toHaveBeenCalled(); // Should still be called
      expect(consoleSpy).toHaveBeenCalledWith(
        'Error in WebSocket handler for test_event:',
        expect.any(Error)
      );
      
      consoleSpy.mockRestore();
    });
  });

  describe('reconnection logic', () => {
    it('should attempt reconnection on unexpected disconnect', async () => {
      await service.connect();
      mockWebSocket = (service as any).ws;
      
      const connectSpy = jest.spyOn(service, 'connect');
      
      // Simulate unexpected disconnect
      const closeEvent = new CloseEvent('close', { 
        code: 1006, 
        reason: 'Connection lost', 
        wasClean: false 
      });
      mockWebSocket.onclose?.(closeEvent);
      
      // Wait for reconnection attempt
      await new Promise(resolve => setTimeout(resolve, 100));
      
      expect(connectSpy).toHaveBeenCalled();
    });

    it('should not reconnect on clean disconnect', async () => {
      await service.connect();
      mockWebSocket = (service as any).ws;
      
      const connectSpy = jest.spyOn(service, 'connect');
      
      // Simulate clean disconnect
      service.disconnect();
      
      // Wait to ensure no reconnection attempt
      await new Promise(resolve => setTimeout(resolve, 100));
      
      expect(connectSpy).toHaveBeenCalledTimes(1); // Only the initial connect
    });

    it('should implement exponential backoff for reconnection', async () => {
      jest.useFakeTimers();
      
      await service.connect();
      mockWebSocket = (service as any).ws;
      
      // Simulate multiple failed reconnections
      for (let i = 0; i < 3; i++) {
        const closeEvent = new CloseEvent('close', { 
          code: 1006, 
          wasClean: false 
        });
        mockWebSocket.onclose?.(closeEvent);
        
        // Fast-forward time
        jest.advanceTimersByTime(1000 * Math.pow(2, i));
      }
      
      expect(service.currentReconnectAttempts).toBe(3);
      
      jest.useRealTimers();
    });

    it('should force reconnect when requested', async () => {
      await service.connect();
      
      const connectSpy = jest.spyOn(service, 'connect');
      
      service.forceReconnect();
      
      expect(service.currentReconnectAttempts).toBe(0);
      expect(connectSpy).toHaveBeenCalled();
    });
  });

  describe('heartbeat functionality', () => {
    beforeEach(async () => {
      await service.connect();
      mockWebSocket = (service as any).ws;
    });

    it('should send heartbeat messages', () => {
      jest.useFakeTimers();
      
      const sendSpy = jest.spyOn(mockWebSocket, 'send');
      
      // Fast-forward to trigger heartbeat
      jest.advanceTimersByTime(30000);
      
      expect(sendSpy).toHaveBeenCalledWith(
        JSON.stringify({
          type: 'ping',
          payload: { timestamp: expect.any(String) },
          timestamp: expect.any(String)
        })
      );
      
      jest.useRealTimers();
    });

    it('should stop heartbeat on disconnect', () => {
      const clearIntervalSpy = jest.spyOn(global, 'clearInterval');
      
      service.disconnect();
      
      expect(clearIntervalSpy).toHaveBeenCalled();
    });
  });
});