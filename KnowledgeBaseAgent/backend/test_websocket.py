#!/usr/bin/env python3
"""
Simple WebSocket connection test.
"""

import asyncio
import websockets
import json

async def test_websocket():
    try:
        uri = 'ws://localhost:8000/api/v1/ws'
        print(f'Attempting to connect to {uri}')

        async with websockets.connect(uri) as websocket:
            print('WebSocket connection established!')

            # Send a test message
            test_message = {
                'type': 'heartbeat',
                'data': {'test': True},
                'timestamp': '2024-01-01T00:00:00Z'
            }
            await websocket.send(json.dumps(test_message))
            print('Test message sent')

            # Wait for response
            try:
                response = await asyncio.wait_for(websocket.recv(), timeout=5.0)
                print(f'Received response: {response}')
            except asyncio.TimeoutError:
                print('No response received within 5 seconds')

    except Exception as e:
        print(f'WebSocket connection failed: {e}')

if __name__ == "__main__":
    asyncio.run(test_websocket())