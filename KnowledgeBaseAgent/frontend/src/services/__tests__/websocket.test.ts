import { describe, it, expect, beforeEach, vi } from 'vitest';
import { WebSocketService } from '../websocket';

// Mock WebSocket
class MockWebSocket {
  static CONNECTING = 0;
  static OPEN = 1;
  static CLOSING = 2;
  static CLOSED = 3;

  readyState = MockWebSocket.CONNECTING;
  onopen: ((event: Event) => void) | null = null;
  onclose: ((event: CloseEvent) => void) | null = null;
  onmessage: ((event: MessageEvent) => void) | null = null;
  onerror: ((event: Event) => void) | null = null;

  constructor(public url: string) {
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
  }

  close(code?: number, reason?: string) {
    this.readyState = MockWebSocket.CLOSED;
    this.onclose?.(new CloseEvent('close', { code, reason, wasClean: true }));
  }
}

global.WebSocket = MockWebSocket as any;

describe('WebSocketService', () => {
  let wsService: WebSocketService;

  beforeEach(() => {
    wsService = new WebSocketService('/test-ws');
    vi.clearAllMocks();
  });

  it('should connect successfully', async () => {
    await wsService.connect();
    expect(wsService.isConnected).toBe(true);
    expect(wsService.connectionState).toBe('connected');
  });

  it('should handle connection events', async () => {
    const connectionHandler = vi.fn();
    wsService.subscribe('connection', connectionHandler);

    await wsService.connect();

    expect(connectionHandler).toHaveBeenCalledWith({ status: 'connected' });
  });

  it('should send messages when connected', async () => {
    await wsService.connect();
    
    const sendSpy = vi.spyOn(wsService['ws']!, 'send');
    
    wsService.send('test_event', { data: 'test' });
    
    expect(sendSpy).toHaveBeenCalledWith(
      JSON.stringify({
        type: 'test_event',
        payload: { data: 'test' },
        timestamp: expect.any(String),
      })
    );
  });

  it('should handle incoming messages', async () => {
    const messageHandler = vi.fn();
    wsService.subscribe('test_message', messageHandler);

    await wsService.connect();

    // Simulate incoming message
    const mockMessage = {
      type: 'test_message',
      payload: { data: 'received' },
      timestamp: new Date().toISOString(),
    };

    wsService['ws']!.onmessage?.(new MessageEvent('message', {
      data: JSON.stringify(mockMessage),
    }));

    expect(messageHandler).toHaveBeenCalledWith({ data: 'received' });
  });

  it('should unsubscribe from events', async () => {
    const messageHandler = vi.fn();
    const unsubscribe = wsService.subscribe('test_message', messageHandler);

    await wsService.connect();

    // Unsubscribe
    unsubscribe();

    // Send message - handler should not be called
    const mockMessage = {
      type: 'test_message',
      payload: { data: 'test' },
      timestamp: new Date().toISOString(),
    };

    wsService['ws']!.onmessage?.(new MessageEvent('message', {
      data: JSON.stringify(mockMessage),
    }));

    expect(messageHandler).not.toHaveBeenCalled();
  });

  it('should disconnect properly', async () => {
    await wsService.connect();
    expect(wsService.isConnected).toBe(true);

    wsService.disconnect();
    expect(wsService.connectionState).toBe('disconnected');
  });
});