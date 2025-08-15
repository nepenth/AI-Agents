import React, { useState } from 'react';
import { Button } from '@/components/ui/Button';
import { useWebSocket } from '@/hooks/useWebSocket';
import { config } from '@/config';

export function WebSocketDebug() {
  const { connectionStatus, lastConnected, reconnectAttempts, reconnect, isConnected } = useWebSocket();
  const [testMessage, setTestMessage] = useState('');

  const handleTestConnection = () => {
    console.log('Testing WebSocket connection...');
    console.log('Config:', config);
    console.log('Connection Status:', connectionStatus);
    console.log('Is Connected:', isConnected);
    console.log('Last Connected:', lastConnected);
    console.log('Reconnect Attempts:', reconnectAttempts);
  };

  const handleSendTestMessage = () => {
    if (testMessage.trim()) {
      console.log('Sending test message:', testMessage);
      // You can implement send functionality here if needed
    }
  };

  return (
    <div className="p-4 border rounded-lg bg-gray-50 dark:bg-gray-800">
      <h3 className="text-lg font-semibold mb-4">WebSocket Debug</h3>
      
      <div className="space-y-2 mb-4">
        <div><strong>WebSocket URL:</strong> {config.wsUrl}</div>
        <div><strong>API URL:</strong> {config.apiUrl}</div>
        <div><strong>Status:</strong> <span className={`px-2 py-1 rounded text-sm ${
          connectionStatus === 'connected' ? 'bg-green-100 text-green-800' :
          connectionStatus === 'connecting' ? 'bg-yellow-100 text-yellow-800' :
          connectionStatus === 'error' ? 'bg-red-100 text-red-800' :
          'bg-gray-100 text-gray-800'
        }`}>{connectionStatus}</span></div>
        <div><strong>Is Connected:</strong> {isConnected ? 'Yes' : 'No'}</div>
        <div><strong>Last Connected:</strong> {lastConnected ? lastConnected.toLocaleString() : 'Never'}</div>
        <div><strong>Reconnect Attempts:</strong> {reconnectAttempts}</div>
      </div>

      <div className="space-x-2 mb-4">
        <Button onClick={handleTestConnection} variant="outline" size="sm">
          Log Debug Info
        </Button>
        <Button onClick={reconnect} variant="outline" size="sm">
          Force Reconnect
        </Button>
      </div>

      <div className="space-y-2">
        <input
          type="text"
          value={testMessage}
          onChange={(e) => setTestMessage(e.target.value)}
          placeholder="Test message"
          className="w-full px-3 py-2 border rounded"
        />
        <Button onClick={handleSendTestMessage} size="sm" disabled={!isConnected}>
          Send Test Message
        </Button>
      </div>
    </div>
  );
}