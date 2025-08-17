import { WebSocketMessage } from '@/types';
import { config } from '@/config';

export type WebSocketEventHandler = (data: any) => void;

export class WebSocketService {
  private ws: WebSocket | null = null;
  private url: string;
  private reconnectAttempts = 0;
  private maxReconnectAttempts = 5;
  private reconnectDelay = 1000;
  private eventHandlers = new Map<string, WebSocketEventHandler[]>();
  private isConnecting = false;
  private shouldReconnect = true;
  private lastConnected: Date | null = null;
  private messageQueue: WebSocketMessage[] = [];
  private heartbeatInterval: NodeJS.Timeout | null = null;
  private heartbeatIntervalMs = 30000; // 30 seconds

  constructor(url?: string) {
    this.url = url || config.wsUrl;

    // Log configuration for debugging
    console.log('WebSocket service initialized with URL:', this.url);
    console.log('Current location:', window.location.href);
    console.log('Config:', config);
  }

  async connect(): Promise<void> {
    if (this.isConnecting || (this.ws && this.ws.readyState === WebSocket.OPEN)) {
      return;
    }

    this.isConnecting = true;
    this.shouldReconnect = true;

    console.log(`Attempting WebSocket connection to: ${this.url}`);

    return new Promise((resolve, reject) => {
      try {
        this.ws = new WebSocket(this.url);

        this.ws.onopen = () => {
          console.log('WebSocket connected successfully');
          this.isConnecting = false;
          this.reconnectAttempts = 0;
          this.lastConnected = new Date();
          
          // Process queued messages
          this.processMessageQueue();
          
          // Start heartbeat
          this.startHeartbeat();
          
          this.emit('connection', { status: 'connected', timestamp: this.lastConnected });
          resolve();
        };

        this.ws.onmessage = (event) => {
          try {
            const message: WebSocketMessage = JSON.parse(event.data);
            console.log('WebSocket message received:', message.type);
            this.handleMessage(message);
          } catch (error) {
            console.error('Failed to parse WebSocket message:', error);
          }
        };

        this.ws.onclose = (event) => {
          console.log(`WebSocket disconnected: code=${event.code}, reason=${event.reason}, wasClean=${event.wasClean}`);
          this.isConnecting = false;
          this.stopHeartbeat();
          this.emit('connection', { 
            status: 'disconnected', 
            code: event.code, 
            reason: event.reason,
            lastConnected: this.lastConnected,
            reconnectAttempts: this.reconnectAttempts
          });
          
          if (this.shouldReconnect && !event.wasClean) {
            this.handleReconnect();
          }
        };

        this.ws.onerror = (error) => {
          console.error('WebSocket error:', error);
          this.isConnecting = false;
          this.emit('connection', { status: 'error', error });
          reject(error);
        };
      } catch (error) {
        console.error('Failed to create WebSocket:', error);
        this.isConnecting = false;
        reject(error);
      }
    });
  }

  disconnect(): void {
    this.shouldReconnect = false;
    if (this.ws) {
      this.ws.close(1000, 'Client disconnect');
      this.ws = null;
    }
  }

  send(type: string, payload: any): boolean {
    return this.sendWithQueue(type, payload);
  }

  subscribe(event: string, handler: WebSocketEventHandler): () => void {
    if (!this.eventHandlers.has(event)) {
      this.eventHandlers.set(event, []);
    }
    this.eventHandlers.get(event)!.push(handler);

    // Return unsubscribe function
    return () => {
      const handlers = this.eventHandlers.get(event);
      if (handlers) {
        const index = handlers.indexOf(handler);
        if (index > -1) {
          handlers.splice(index, 1);
        }
      }
    };
  }

  private handleMessage(message: WebSocketMessage): void {
    const handlers = this.eventHandlers.get(message.type) || [];
    handlers.forEach(handler => {
      try {
        handler(message.payload);
      } catch (error) {
        console.error(`Error in WebSocket handler for ${message.type}:`, error);
      }
    });
  }

  private emit(event: string, data: any): void {
    const handlers = this.eventHandlers.get(event) || [];
    handlers.forEach(handler => {
      try {
        handler(data);
      } catch (error) {
        console.error(`Error in WebSocket handler for ${event}:`, error);
      }
    });
  }

  private handleReconnect(): void {
    if (this.reconnectAttempts >= this.maxReconnectAttempts) {
      console.error('Max reconnection attempts reached');
      this.emit('connection', { status: 'failed', reason: 'Max reconnection attempts reached' });
      return;
    }

    const delay = this.reconnectDelay * Math.pow(2, this.reconnectAttempts);
    this.reconnectAttempts++;

    console.log(`Attempting to reconnect in ${delay}ms (attempt ${this.reconnectAttempts})`);
    
    setTimeout(() => {
      if (this.shouldReconnect) {
        this.connect().catch(error => {
          console.error('Reconnection failed:', error);
          this.emit('connection', { 
            status: 'disconnected', 
            reconnectAttempts: this.reconnectAttempts,
            lastConnected: this.lastConnected
          });
        });
      }
    }, delay);
  }

  get isConnected(): boolean {
    return this.ws?.readyState === WebSocket.OPEN;
  }

  get connectionState(): string {
    if (!this.ws) return 'disconnected';
    
    switch (this.ws.readyState) {
      case WebSocket.CONNECTING:
        return 'connecting';
      case WebSocket.OPEN:
        return 'connected';
      case WebSocket.CLOSING:
        return 'closing';
      case WebSocket.CLOSED:
        return 'disconnected';
      default:
        return 'unknown';
    }
  }

  get lastConnectedTime(): Date | null {
    return this.lastConnected;
  }

  get currentReconnectAttempts(): number {
    return this.reconnectAttempts;
  }

  private processMessageQueue(): void {
    if (this.ws && this.ws.readyState === WebSocket.OPEN && this.messageQueue.length > 0) {
      const messages = [...this.messageQueue];
      this.messageQueue = [];
      
      messages.forEach(message => {
        this.ws!.send(JSON.stringify(message));
      });
      
      console.log(`Processed ${messages.length} queued messages`);
    }
  }

  private startHeartbeat(): void {
    this.stopHeartbeat();
    
    this.heartbeatInterval = setInterval(() => {
      if (this.ws && this.ws.readyState === WebSocket.OPEN) {
        this.send('ping', { timestamp: new Date().toISOString() });
      }
    }, this.heartbeatIntervalMs);
  }

  private stopHeartbeat(): void {
    if (this.heartbeatInterval) {
      clearInterval(this.heartbeatInterval);
      this.heartbeatInterval = null;
    }
  }

  // Enhanced send method with queuing
  sendWithQueue(type: string, payload: any): boolean {
    const message: WebSocketMessage = {
      type,
      payload,
      timestamp: new Date().toISOString(),
    };

    if (this.ws && this.ws.readyState === WebSocket.OPEN) {
      try {
        this.ws.send(JSON.stringify(message));
        return true;
      } catch (error) {
        console.error('Failed to send WebSocket message:', error);
        this.messageQueue.push(message);
        return false;
      }
    } else {
      // Queue message for when connection is restored
      this.messageQueue.push(message);
      console.warn('WebSocket not connected, message queued');
      return false;
    }
  }

  // Force reconnect method
  forceReconnect(): void {
    this.reconnectAttempts = 0;
    if (this.ws) {
      this.ws.close();
    }
    this.connect().catch(error => {
      console.error('Force reconnect failed:', error);
    });
  }

  // Test connection with different URLs
  async testConnection(): Promise<{ url: string; success: boolean; error?: string }[]> {
    const wsProtocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
    const currentHost = `${window.location.hostname}:${window.location.port}`;

    const testUrls = [
      this.url,
      `${wsProtocol}//${currentHost}/ws`, // Vite proxy
      'ws://localhost:8000/api/v1/ws', // Direct backend
      `ws://${window.location.hostname}:8000/api/v1/ws`, // Backend with current host
      'ws://127.0.0.1:8000/api/v1/ws' // Backend with 127.0.0.1
    ];

    const results = [];

    for (const testUrl of testUrls) {
      try {
        console.log(`Testing WebSocket connection to: ${testUrl}`);

        const testResult = await new Promise<{ success: boolean; error?: string }>((resolve) => {
          const testWs = new WebSocket(testUrl);

          const timeout = setTimeout(() => {
            testWs.close();
            resolve({ success: false, error: 'Connection timeout' });
          }, 5000);

          testWs.onopen = () => {
            clearTimeout(timeout);
            testWs.close();
            resolve({ success: true });
          };

          testWs.onerror = (error) => {
            clearTimeout(timeout);
            resolve({ success: false, error: 'Connection failed' });
          };
        });

        results.push({ url: testUrl, ...testResult });

        if (testResult.success) {
          console.log(`✅ WebSocket connection successful to: ${testUrl}`);
          // Update the URL if this one works and it's different
          if (testUrl !== this.url) {
            console.log(`Updating WebSocket URL from ${this.url} to ${testUrl}`);
            this.url = testUrl;
          }
          break;
        } else {
          console.log(`❌ WebSocket connection failed to: ${testUrl} - ${testResult.error}`);
        }
      } catch (error) {
        console.log(`❌ WebSocket test error for ${testUrl}:`, error);
        results.push({ url: testUrl, success: false, error: String(error) });
      }
    }

    return results;
  }
}

// Create singleton instance
export const websocketService = new WebSocketService();