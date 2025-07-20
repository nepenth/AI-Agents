# Knowledge Base Agent API Documentation

Comprehensive documentation for all API endpoints.

## Overview

- **Total Endpoints:** 66
- **Categories:** 14
- **API Versions:** v1, v2, web

## Table of Contents

- [Web UI](#web-ui)
- [Agent Management (V2)](#agent-management-v2)
- [Celery Management (V2)](#celery-management-v2)
- [Agent Management](#agent-management)
- [API](#api)
- [Chat & AI](#chat-&-ai)
- [Configuration](#configuration)
- [Knowledge Base](#knowledge-base)
- [Logging](#logging)
- [Environment](#environment)
- [System Utilities](#system-utilities)
- [Hardware Monitoring](#hardware-monitoring)
- [Scheduling](#scheduling)
- [Web UI (V2)](#web-ui-v2)

## Web UI

### GET /static/<path:filename>

**Summary:** No description available

**Description:** 

**Path Parameters:**

- `filename` (string, Required): Name of the file

**Responses:**

- **200**: Success - returns requested item
  ```json
  {
    "id": 1,
    "data": "..."
  }
  ```
- **404**: Item not found
  ```json
  {
    "error": "Item not found"
  }
  ```
- **400**: Bad request - invalid parameters
  ```json
  {
    "error": "Invalid request data"
  }
  ```
- **500**: Internal server error
  ```json
  {
    "error": "Internal server error"
  }
  ```

**Example (curl):**

```bash
curl -X GET \
  "http://localhost:5000/static/path/to/file"
```

**Common Error Scenarios:**

- Invalid ID format - returns 404

---

### GET /

**Summary:** No description available

**Description:** 

**Responses:**

- **200**: Success - returns list of items
  ```json
  {
    "items": [],
    "total": 0
  }
  ```
- **400**: Bad request - invalid parameters
  ```json
  {
    "error": "Invalid request data"
  }
  ```
- **500**: Internal server error
  ```json
  {
    "error": "Internal server error"
  }
  ```

**Example (curl):**

```bash
curl -X GET \
  "http://localhost:5000/"
```

---

## Agent Management (V2)

### POST /api/v2/agent/start

**Summary:** Sync wrapper that queues an agent run. Executes async logic via asyncio.run.

**Request Body:**

```json
{
  "type": "object",
  "properties": {
    "preferences": {
      "type": "object",
      "properties": {
        "run_mode": {
          "type": "string",
          "enum": [
            "full",
            "test",
            "minimal"
          ]
        },
        "skip_fetch_bookmarks": {
          "type": "boolean"
        },
        "skip_process_content": {
          "type": "boolean"
        },
        "force_recache_tweets": {
          "type": "boolean"
        }
      }
    }
  },
  "required": [
    "preferences"
  ]
}
```

**Responses:**

- **201**: Created successfully
  ```json
  {
    "success": true,
    "id": 1
  }
  ```
- **400**: Bad request - invalid parameters
  ```json
  {
    "error": "Invalid request data"
  }
  ```
- **500**: Internal server error
  ```json
  {
    "error": "Internal server error"
  }
  ```

**Example (curl):**

```bash
curl -X POST \
  "http://localhost:5000/api/v2/agent/start" \
  -H "Content-Type: application/json" \
  -d '{"preferences": {"run_mode": "full", "skip_fetch_bookmarks": true, "skip_process_content": true, "force_recache_tweets": true}}'
```

**Workflow Context:** Part of the agent execution workflow. Use this to start the Knowledge Base Agent with specific preferences.

**Common Error Scenarios:**

- Agent already running - returns 400
- Invalid preferences format - returns 400
- System resources unavailable - returns 503
- Missing required fields - returns 400
- Invalid JSON format - returns 400

---

### GET /api/v2/agent/status/<task_id>

**Summary:** Sync wrapper around async status-gathering logic.

**Path Parameters:**

- `task_id` (string, Required): Task identifier for tracking

**Responses:**

- **200**: Success - returns requested item
  ```json
  {
    "id": 1,
    "data": "..."
  }
  ```
- **404**: Item not found
  ```json
  {
    "error": "Item not found"
  }
  ```
- **400**: Bad request - invalid parameters
  ```json
  {
    "error": "Invalid request data"
  }
  ```
- **500**: Internal server error
  ```json
  {
    "error": "Internal server error"
  }
  ```

**Example (curl):**

```bash
curl -X GET \
  "http://localhost:5000/api/v2/agent/status/example"
```

**Workflow Context:** Monitor agent execution progress. Poll this endpoint to track task completion.

**Common Error Scenarios:**

- Invalid ID format - returns 404

---

### POST /api/v2/agent/stop

**Summary:** Stops a running agent task via Celery.

**Request Body:**

```json
{
  "type": "object"
}
```

**Responses:**

- **200**: Operation completed successfully
  ```json
  {
    "success": true,
    "message": "Operation completed"
  }
  ```
- **400**: Bad request - invalid parameters
  ```json
  {
    "error": "Invalid request data"
  }
  ```
- **500**: Internal server error
  ```json
  {
    "error": "Internal server error"
  }
  ```

**Example (curl):**

```bash
curl -X POST \
  "http://localhost:5000/api/v2/agent/stop" \
  -H "Content-Type: application/json" \
  -d '{}'
```

**Workflow Context:** Stop running agent tasks. Use when you need to cancel ongoing operations.

**Common Error Scenarios:**

- Missing required fields - returns 400
- Invalid JSON format - returns 400

---

## Celery Management (V2)

### POST /api/v2/celery/clear-queue

**Summary:** Clear all tasks from Celery queue.

**Request Body:**

```json
{
  "type": "object"
}
```

**Responses:**

- **200**: Operation completed successfully
  ```json
  {
    "success": true,
    "message": "Operation completed"
  }
  ```
- **400**: Bad request - invalid parameters
  ```json
  {
    "error": "Invalid request data"
  }
  ```
- **500**: Internal server error
  ```json
  {
    "error": "Internal server error"
  }
  ```

**Example (curl):**

```bash
curl -X POST \
  "http://localhost:5000/api/v2/celery/clear-queue" \
  -H "Content-Type: application/json" \
  -d '{}'
```

**Common Error Scenarios:**

- Missing required fields - returns 400
- Invalid JSON format - returns 400

---

### POST /api/v2/celery/purge-tasks

**Summary:** Purge all Celery tasks (active and queued).

**Request Body:**

```json
{
  "type": "object"
}
```

**Responses:**

- **200**: Operation completed successfully
  ```json
  {
    "success": true,
    "message": "Operation completed"
  }
  ```
- **400**: Bad request - invalid parameters
  ```json
  {
    "error": "Invalid request data"
  }
  ```
- **500**: Internal server error
  ```json
  {
    "error": "Internal server error"
  }
  ```

**Example (curl):**

```bash
curl -X POST \
  "http://localhost:5000/api/v2/celery/purge-tasks" \
  -H "Content-Type: application/json" \
  -d '{}'
```

**Common Error Scenarios:**

- Missing required fields - returns 400
- Invalid JSON format - returns 400

---

### POST /api/v2/celery/restart-workers

**Summary:** Restart Celery workers.

**Request Body:**

```json
{
  "type": "object"
}
```

**Responses:**

- **201**: Created successfully
  ```json
  {
    "success": true,
    "id": 1
  }
  ```
- **400**: Bad request - invalid parameters
  ```json
  {
    "error": "Invalid request data"
  }
  ```
- **500**: Internal server error
  ```json
  {
    "error": "Internal server error"
  }
  ```

**Example (curl):**

```bash
curl -X POST \
  "http://localhost:5000/api/v2/celery/restart-workers" \
  -H "Content-Type: application/json" \
  -d '{}'
```

**Common Error Scenarios:**

- Agent already running - returns 400
- Invalid preferences format - returns 400
- System resources unavailable - returns 503
- Missing required fields - returns 400
- Invalid JSON format - returns 400

---

### GET /api/v2/celery/status

**Summary:** Get Celery worker status.

**Responses:**

- **200**: Success - returns list of items
  ```json
  {
    "items": [],
    "total": 0
  }
  ```
- **400**: Bad request - invalid parameters
  ```json
  {
    "error": "Invalid request data"
  }
  ```
- **500**: Internal server error
  ```json
  {
    "error": "Internal server error"
  }
  ```

**Example (curl):**

```bash
curl -X GET \
  "http://localhost:5000/api/v2/celery/status"
```

---

## Agent Management

### GET /api/agent/status

**Summary:** Synchronous wrapper around get_task_status to avoid AsyncToSync errors

**Description:** when running Flask on gevent.  Executes the coroutine in its own event
loop with ``asyncio.run``.

**Responses:**

- **200**: Success - returns list of items
  ```json
  {
    "items": [],
    "total": 0
  }
  ```
- **400**: Bad request - invalid parameters
  ```json
  {
    "error": "Invalid request data"
  }
  ```
- **500**: Internal server error
  ```json
  {
    "error": "Internal server error"
  }
  ```

**Example (curl):**

```bash
curl -X GET \
  "http://localhost:5000/api/agent/status"
```

**Workflow Context:** Monitor agent execution progress. Poll this endpoint to track task completion.

---

### POST /api/agent/reset

**Summary:** Resets the agent's database state to idle.

**Request Body:**

```json
{
  "type": "object"
}
```

**Responses:**

- **200**: Operation completed successfully
  ```json
  {
    "success": true,
    "message": "Operation completed"
  }
  ```
- **400**: Bad request - invalid parameters
  ```json
  {
    "error": "Invalid request data"
  }
  ```
- **500**: Internal server error
  ```json
  {
    "error": "Internal server error"
  }
  ```

**Example (curl):**

```bash
curl -X POST \
  "http://localhost:5000/api/agent/reset" \
  -H "Content-Type: application/json" \
  -d '{}'
```

**Common Error Scenarios:**

- Missing required fields - returns 400
- Invalid JSON format - returns 400

---

## API

### GET /api/media/<path:path>

**Summary:** Serve media files from the knowledge base directory.

**Path Parameters:**

- `path` (string, Required): Path parameter

**Responses:**

- **200**: Success - returns requested item
  ```json
  {
    "id": 1,
    "data": "..."
  }
  ```
- **404**: Item not found
  ```json
  {
    "error": "Item not found"
  }
  ```
- **400**: Bad request - invalid parameters
  ```json
  {
    "error": "Invalid request data"
  }
  ```
- **500**: Internal server error
  ```json
  {
    "error": "Internal server error"
  }
  ```

**Example (curl):**

```bash
curl -X GET \
  "http://localhost:5000/api/media/path/to/file"
```

**Common Error Scenarios:**

- Invalid ID format - returns 404

---

### POST, GET /api/schedule

**Summary:** V1 LEGACY ENDPOINT: Simulates schedule handling for backward compatibility.

**Request Body:**

```json
{
  "type": "object"
}
```

**Responses:**

- **200**: Success - returns list of items
  ```json
  {
    "items": [],
    "total": 0
  }
  ```
- **200**: Operation completed successfully
  ```json
  {
    "success": true,
    "message": "Operation completed"
  }
  ```
- **400**: Bad request - invalid parameters
  ```json
  {
    "error": "Invalid request data"
  }
  ```
- **500**: Internal server error
  ```json
  {
    "error": "Internal server error"
  }
  ```

**Example (curl):**

```bash
curl -X POST \
  "http://localhost:5000/api/schedule" \
  -H "Content-Type: application/json" \
  -d '{}'
```

**Common Error Scenarios:**

- Missing required fields - returns 400
- Invalid JSON format - returns 400

---

### GET /api/hardware-detection

**Summary:** Get detected hardware information.

**Responses:**

- **200**: Success - returns list of items
  ```json
  {
    "items": [],
    "total": 0
  }
  ```
- **400**: Bad request - invalid parameters
  ```json
  {
    "error": "Invalid request data"
  }
  ```
- **500**: Internal server error
  ```json
  {
    "error": "Internal server error"
  }
  ```

**Example (curl):**

```bash
curl -X GET \
  "http://localhost:5000/api/hardware-detection"
```

---

### POST /api/ollama-optimization

**Summary:** Generate Ollama optimization settings based on hardware and profile.

**Request Body:**

```json
{
  "type": "object"
}
```

**Responses:**

- **200**: Operation completed successfully
  ```json
  {
    "success": true,
    "message": "Operation completed"
  }
  ```
- **400**: Bad request - invalid parameters
  ```json
  {
    "error": "Invalid request data"
  }
  ```
- **500**: Internal server error
  ```json
  {
    "error": "Internal server error"
  }
  ```

**Example (curl):**

```bash
curl -X POST \
  "http://localhost:5000/api/ollama-optimization" \
  -H "Content-Type: application/json" \
  -d '{}'
```

**Common Error Scenarios:**

- Missing required fields - returns 400
- Invalid JSON format - returns 400

---

### GET /api/syntheses

**Summary:** API endpoint to get all synthesis documents.

**Responses:**

- **200**: Success - returns list of items
  ```json
  {
    "items": [],
    "total": 0
  }
  ```
- **400**: Bad request - invalid parameters
  ```json
  {
    "error": "Invalid request data"
  }
  ```
- **500**: Internal server error
  ```json
  {
    "error": "Internal server error"
  }
  ```

**Example (curl):**

```bash
curl -X GET \
  "http://localhost:5000/api/syntheses"
```

---

### GET /api/schedule-history

**Summary:** Get schedule execution history.

**Responses:**

- **200**: Success - returns list of items
  ```json
  {
    "items": [],
    "total": 0
  }
  ```
- **400**: Bad request - invalid parameters
  ```json
  {
    "error": "Invalid request data"
  }
  ```
- **500**: Internal server error
  ```json
  {
    "error": "Internal server error"
  }
  ```

**Example (curl):**

```bash
curl -X GET \
  "http://localhost:5000/api/schedule-history"
```

---

### DELETE /api/schedule-runs/<int:run_id>

**Summary:** API endpoint to delete a schedule run from history.

**Path Parameters:**

- `run_id` (integer, Required): Schedule run identifier

**Responses:**

- **200**: Deleted successfully
  ```json
  {
    "success": true,
    "message": "Deleted"
  }
  ```
- **400**: Bad request - invalid parameters
  ```json
  {
    "error": "Invalid request data"
  }
  ```
- **500**: Internal server error
  ```json
  {
    "error": "Internal server error"
  }
  ```

**Example (curl):**

```bash
curl -X DELETE \
  "http://localhost:5000/api/schedule-runs/1"
```

**Common Error Scenarios:**

- Invalid ID format - returns 404

---

### GET /api/kb/all

**Summary:** Returns a JSON object with all KB items and syntheses for the TOC.

**Query Parameters:**

- `limit` (integer, Optional): Maximum number of results
- `offset` (integer, Optional): Number of results to skip

**Responses:**

- **200**: Success - returns list of items
  ```json
  {
    "items": [],
    "total": 0
  }
  ```
- **400**: Bad request - invalid parameters
  ```json
  {
    "error": "Invalid request data"
  }
  ```
- **500**: Internal server error
  ```json
  {
    "error": "Internal server error"
  }
  ```

**Example (curl):**

```bash
curl -X GET \
  "http://localhost:5000/api/kb/all"
```

---

### POST, GET /api/v2/schedule

**Summary:** V2 ENDPOINT: Handles getting and setting the agent execution schedule from the database.

**Request Body:**

```json
{
  "type": "object"
}
```

**Responses:**

- **200**: Success - returns list of items
  ```json
  {
    "items": [],
    "total": 0
  }
  ```
- **200**: Operation completed successfully
  ```json
  {
    "success": true,
    "message": "Operation completed"
  }
  ```
- **400**: Bad request - invalid parameters
  ```json
  {
    "error": "Invalid request data"
  }
  ```
- **500**: Internal server error
  ```json
  {
    "error": "Internal server error"
  }
  ```

**Example (curl):**

```bash
curl -X POST \
  "http://localhost:5000/api/v2/schedule" \
  -H "Content-Type: application/json" \
  -d '{}'
```

**Common Error Scenarios:**

- Missing required fields - returns 400
- Invalid JSON format - returns 400

---

### GET /api/items/<int:item_id>

**Summary:** API endpoint for getting KB item data in JSON format.

**Path Parameters:**

- `item_id` (integer, Required): Knowledge base item identifier

**Responses:**

- **200**: Success - returns requested item
  ```json
  {
    "id": 1,
    "data": "..."
  }
  ```
- **404**: Item not found
  ```json
  {
    "error": "Item not found"
  }
  ```
- **400**: Bad request - invalid parameters
  ```json
  {
    "error": "Invalid request data"
  }
  ```
- **500**: Internal server error
  ```json
  {
    "error": "Internal server error"
  }
  ```

**Example (curl):**

```bash
curl -X GET \
  "http://localhost:5000/api/items/1"
```

**Common Error Scenarios:**

- Invalid ID format - returns 404

---

### GET /api/system/info

**Summary:** Get comprehensive system information.

**Responses:**

- **200**: Success - returns list of items
  ```json
  {
    "items": [],
    "total": 0
  }
  ```
- **400**: Bad request - invalid parameters
  ```json
  {
    "error": "Invalid request data"
  }
  ```
- **500**: Internal server error
  ```json
  {
    "error": "Internal server error"
  }
  ```

**Example (curl):**

```bash
curl -X GET \
  "http://localhost:5000/api/system/info"
```

---

### POST /api/v2/logs/clear

**Summary:** V2 API: Clear all server-side logs.

**Request Body:**

```json
{
  "type": "object"
}
```

**Responses:**

- **200**: Operation completed successfully
  ```json
  {
    "success": true,
    "message": "Operation completed"
  }
  ```
- **400**: Bad request - invalid parameters
  ```json
  {
    "error": "Invalid request data"
  }
  ```
- **500**: Internal server error
  ```json
  {
    "error": "Internal server error"
  }
  ```

**Example (curl):**

```bash
curl -X POST \
  "http://localhost:5000/api/v2/logs/clear" \
  -H "Content-Type: application/json" \
  -d '{}'
```

**Common Error Scenarios:**

- Missing required fields - returns 400
- Invalid JSON format - returns 400

---

## Chat & AI

### GET /api/chat/models

**Summary:** Returns the list of available chat models from the config.

**Responses:**

- **200**: Success - returns list of items
  ```json
  {
    "items": [],
    "total": 0
  }
  ```
- **400**: Bad request - invalid parameters
  ```json
  {
    "error": "Invalid request data"
  }
  ```
- **500**: Internal server error
  ```json
  {
    "error": "Internal server error"
  }
  ```

**Example (curl):**

```bash
curl -X GET \
  "http://localhost:5000/api/chat/models"
```

**Workflow Context:** Interactive chat with the knowledge base. Send messages to get AI-powered responses.

---

### POST /api/chat

**Summary:** Handle chat interactions via API using the knowledge base agent.

**Request Body:**

```json
{
  "type": "object",
  "properties": {
    "message": {
      "type": "string"
    },
    "model": {
      "type": "string"
    },
    "session_id": {
      "type": "string"
    }
  },
  "required": [
    "message"
  ]
}
```

**Responses:**

- **200**: Operation completed successfully
  ```json
  {
    "success": true,
    "message": "Operation completed"
  }
  ```
- **400**: Bad request - invalid parameters
  ```json
  {
    "error": "Invalid request data"
  }
  ```
- **500**: Internal server error
  ```json
  {
    "error": "Internal server error"
  }
  ```

**Example (curl):**

```bash
curl -X POST \
  "http://localhost:5000/api/chat" \
  -H "Content-Type: application/json" \
  -d '{"message": "example_message", "model": "example_model", "session_id": "example_session_id"}'
```

**Workflow Context:** Interactive chat with the knowledge base. Send messages to get AI-powered responses.

**Common Error Scenarios:**

- Missing required fields - returns 400
- Invalid JSON format - returns 400

---

### POST /api/chat/enhanced

**Summary:** Enhanced chat API endpoint with technical expertise and rich source metadata.

**Request Body:**

```json
{
  "type": "object",
  "properties": {
    "message": {
      "type": "string"
    },
    "model": {
      "type": "string"
    },
    "session_id": {
      "type": "string"
    }
  },
  "required": [
    "message"
  ]
}
```

**Responses:**

- **200**: Operation completed successfully
  ```json
  {
    "success": true,
    "message": "Operation completed"
  }
  ```
- **400**: Bad request - invalid parameters
  ```json
  {
    "error": "Invalid request data"
  }
  ```
- **500**: Internal server error
  ```json
  {
    "error": "Internal server error"
  }
  ```

**Example (curl):**

```bash
curl -X POST \
  "http://localhost:5000/api/chat/enhanced" \
  -H "Content-Type: application/json" \
  -d '{"message": "example_message", "model": "example_model", "session_id": "example_session_id"}'
```

**Workflow Context:** Interactive chat with the knowledge base. Send messages to get AI-powered responses.

**Common Error Scenarios:**

- Missing required fields - returns 400
- Invalid JSON format - returns 400

---

### GET /api/chat/models/available

**Summary:** Get available chat models.

**Responses:**

- **200**: Success - returns list of items
  ```json
  {
    "items": [],
    "total": 0
  }
  ```
- **400**: Bad request - invalid parameters
  ```json
  {
    "error": "Invalid request data"
  }
  ```
- **500**: Internal server error
  ```json
  {
    "error": "Internal server error"
  }
  ```

**Example (curl):**

```bash
curl -X GET \
  "http://localhost:5000/api/chat/models/available"
```

**Workflow Context:** Interactive chat with the knowledge base. Send messages to get AI-powered responses.

---

### GET /api/chat/sessions

**Summary:** Get all chat sessions.

**Query Parameters:**

- `limit` (integer, Optional): Maximum number of results
- `offset` (integer, Optional): Number of results to skip

**Responses:**

- **200**: Success - returns list of items
  ```json
  {
    "items": [],
    "total": 0
  }
  ```
- **400**: Bad request - invalid parameters
  ```json
  {
    "error": "Invalid request data"
  }
  ```
- **500**: Internal server error
  ```json
  {
    "error": "Internal server error"
  }
  ```

**Example (curl):**

```bash
curl -X GET \
  "http://localhost:5000/api/chat/sessions"
```

**Workflow Context:** Interactive chat with the knowledge base. Send messages to get AI-powered responses.

---

### GET /api/chat/sessions/<session_id>

**Summary:** Get a specific chat session with messages.

**Path Parameters:**

- `session_id` (string, Required): Chat session identifier

**Query Parameters:**

- `limit` (integer, Optional): Maximum number of results
- `offset` (integer, Optional): Number of results to skip

**Responses:**

- **200**: Success - returns requested item
  ```json
  {
    "id": 1,
    "data": "..."
  }
  ```
- **404**: Item not found
  ```json
  {
    "error": "Item not found"
  }
  ```
- **400**: Bad request - invalid parameters
  ```json
  {
    "error": "Invalid request data"
  }
  ```
- **500**: Internal server error
  ```json
  {
    "error": "Internal server error"
  }
  ```

**Example (curl):**

```bash
curl -X GET \
  "http://localhost:5000/api/chat/sessions/example"
```

**Workflow Context:** Interactive chat with the knowledge base. Send messages to get AI-powered responses.

**Common Error Scenarios:**

- Invalid ID format - returns 404

---

### POST /api/chat/sessions

**Summary:** Create a new chat session.

**Request Body:**

```json
{
  "type": "object",
  "properties": {
    "message": {
      "type": "string"
    },
    "model": {
      "type": "string"
    },
    "session_id": {
      "type": "string"
    }
  },
  "required": [
    "message"
  ]
}
```

**Responses:**

- **200**: Operation completed successfully
  ```json
  {
    "success": true,
    "message": "Operation completed"
  }
  ```
- **400**: Bad request - invalid parameters
  ```json
  {
    "error": "Invalid request data"
  }
  ```
- **500**: Internal server error
  ```json
  {
    "error": "Internal server error"
  }
  ```

**Example (curl):**

```bash
curl -X POST \
  "http://localhost:5000/api/chat/sessions" \
  -H "Content-Type: application/json" \
  -d '{"message": "example_message", "model": "example_model", "session_id": "example_session_id"}'
```

**Workflow Context:** Interactive chat with the knowledge base. Send messages to get AI-powered responses.

**Common Error Scenarios:**

- Missing required fields - returns 400
- Invalid JSON format - returns 400

---

### POST /api/chat/sessions/<session_id>/archive

**Summary:** Archive/unarchive a chat session.

**Path Parameters:**

- `session_id` (string, Required): Chat session identifier

**Request Body:**

```json
{
  "type": "object",
  "properties": {
    "message": {
      "type": "string"
    },
    "model": {
      "type": "string"
    },
    "session_id": {
      "type": "string"
    }
  },
  "required": [
    "message"
  ]
}
```

**Responses:**

- **200**: Operation completed successfully
  ```json
  {
    "success": true,
    "message": "Operation completed"
  }
  ```
- **400**: Bad request - invalid parameters
  ```json
  {
    "error": "Invalid request data"
  }
  ```
- **500**: Internal server error
  ```json
  {
    "error": "Internal server error"
  }
  ```

**Example (curl):**

```bash
curl -X POST \
  "http://localhost:5000/api/chat/sessions/example/archive" \
  -H "Content-Type: application/json" \
  -d '{"message": "example_message", "model": "example_model", "session_id": "example_session_id"}'
```

**Workflow Context:** Interactive chat with the knowledge base. Send messages to get AI-powered responses.

**Common Error Scenarios:**

- Invalid ID format - returns 404
- Missing required fields - returns 400
- Invalid JSON format - returns 400

---

### DELETE /api/chat/sessions/<session_id>

**Summary:** Delete a chat session and all its messages.

**Path Parameters:**

- `session_id` (string, Required): Chat session identifier

**Responses:**

- **200**: Deleted successfully
  ```json
  {
    "success": true,
    "message": "Deleted"
  }
  ```
- **400**: Bad request - invalid parameters
  ```json
  {
    "error": "Invalid request data"
  }
  ```
- **500**: Internal server error
  ```json
  {
    "error": "Internal server error"
  }
  ```

**Example (curl):**

```bash
curl -X DELETE \
  "http://localhost:5000/api/chat/sessions/example"
```

**Workflow Context:** Interactive chat with the knowledge base. Send messages to get AI-powered responses.

**Common Error Scenarios:**

- Invalid ID format - returns 404

---

## Configuration

### GET /api/preferences

**Summary:** Get current user preferences.

**Responses:**

- **200**: Success - returns list of items
  ```json
  {
    "items": [],
    "total": 0
  }
  ```
- **400**: Bad request - invalid parameters
  ```json
  {
    "error": "Invalid request data"
  }
  ```
- **500**: Internal server error
  ```json
  {
    "error": "Internal server error"
  }
  ```

**Example (curl):**

```bash
curl -X GET \
  "http://localhost:5000/api/preferences"
```

**Workflow Context:** Configure agent behavior. Set processing preferences before starting agent tasks.

---

### POST /api/preferences

**Summary:** Save user preferences.

**Request Body:**

```json
{
  "type": "object",
  "properties": {
    "run_mode": {
      "type": "string"
    },
    "skip_fetch_bookmarks": {
      "type": "boolean"
    },
    "skip_process_content": {
      "type": "boolean"
    }
  }
}
```

**Responses:**

- **200**: Operation completed successfully
  ```json
  {
    "success": true,
    "message": "Operation completed"
  }
  ```
- **400**: Bad request - invalid parameters
  ```json
  {
    "error": "Invalid request data"
  }
  ```
- **500**: Internal server error
  ```json
  {
    "error": "Internal server error"
  }
  ```

**Example (curl):**

```bash
curl -X POST \
  "http://localhost:5000/api/preferences" \
  -H "Content-Type: application/json" \
  -d '{"run_mode": "example_run_mode", "skip_fetch_bookmarks": true, "skip_process_content": true}'
```

**Workflow Context:** Configure agent behavior. Set processing preferences before starting agent tasks.

**Common Error Scenarios:**

- Missing required fields - returns 400
- Invalid JSON format - returns 400

---

## Knowledge Base

### GET /api/synthesis

**Summary:** API endpoint to get all synthesis documents.

**Responses:**

- **200**: Success - returns list of items
  ```json
  {
    "items": [],
    "total": 0
  }
  ```
- **400**: Bad request - invalid parameters
  ```json
  {
    "error": "Invalid request data"
  }
  ```
- **500**: Internal server error
  ```json
  {
    "error": "Internal server error"
  }
  ```

**Example (curl):**

```bash
curl -X GET \
  "http://localhost:5000/api/synthesis"
```

---

### GET /api/synthesis/<int:synthesis_id>

**Summary:** API endpoint for getting synthesis data in JSON format.

**Path Parameters:**

- `synthesis_id` (integer, Required): Synthesis document identifier

**Responses:**

- **200**: Success - returns requested item
  ```json
  {
    "id": 1,
    "data": "..."
  }
  ```
- **404**: Item not found
  ```json
  {
    "error": "Item not found"
  }
  ```
- **400**: Bad request - invalid parameters
  ```json
  {
    "error": "Invalid request data"
  }
  ```
- **500**: Internal server error
  ```json
  {
    "error": "Internal server error"
  }
  ```

**Example (curl):**

```bash
curl -X GET \
  "http://localhost:5000/api/synthesis/1"
```

**Common Error Scenarios:**

- Invalid ID format - returns 404

---

## Logging

### GET /api/logs

**Summary:** API endpoint to list available log files.

**Responses:**

- **200**: Success - returns list of items
  ```json
  {
    "items": [],
    "total": 0
  }
  ```
- **400**: Bad request - invalid parameters
  ```json
  {
    "error": "Invalid request data"
  }
  ```
- **500**: Internal server error
  ```json
  {
    "error": "Internal server error"
  }
  ```

**Example (curl):**

```bash
curl -X GET \
  "http://localhost:5000/api/logs"
```

---

### GET /api/logs/<filename>

**Summary:** API endpoint to get the content of a specific log file.

**Path Parameters:**

- `filename` (string, Required): Name of the file

**Responses:**

- **200**: Success - returns requested item
  ```json
  {
    "id": 1,
    "data": "..."
  }
  ```
- **404**: Item not found
  ```json
  {
    "error": "Item not found"
  }
  ```
- **400**: Bad request - invalid parameters
  ```json
  {
    "error": "Invalid request data"
  }
  ```
- **500**: Internal server error
  ```json
  {
    "error": "Internal server error"
  }
  ```

**Example (curl):**

```bash
curl -X GET \
  "http://localhost:5000/api/logs/example"
```

**Common Error Scenarios:**

- Invalid ID format - returns 404

---

### POST /api/logs/delete-all

**Summary:** API endpoint to delete all log files.

**Request Body:**

```json
{
  "type": "object"
}
```

**Responses:**

- **200**: Operation completed successfully
  ```json
  {
    "success": true,
    "message": "Operation completed"
  }
  ```
- **400**: Bad request - invalid parameters
  ```json
  {
    "error": "Invalid request data"
  }
  ```
- **500**: Internal server error
  ```json
  {
    "error": "Internal server error"
  }
  ```

**Example (curl):**

```bash
curl -X POST \
  "http://localhost:5000/api/logs/delete-all" \
  -H "Content-Type: application/json" \
  -d '{}'
```

**Common Error Scenarios:**

- Missing required fields - returns 400
- Invalid JSON format - returns 400

---

### GET /api/logs/files

**Summary:** API endpoint to get a list of log files.

**Responses:**

- **200**: Success - returns list of items
  ```json
  {
    "items": [],
    "total": 0
  }
  ```
- **400**: Bad request - invalid parameters
  ```json
  {
    "error": "Invalid request data"
  }
  ```
- **500**: Internal server error
  ```json
  {
    "error": "Internal server error"
  }
  ```

**Example (curl):**

```bash
curl -X GET \
  "http://localhost:5000/api/logs/files"
```

---

### GET /api/logs/recent

**Summary:** Get recent log messages from Redis via TaskProgressManager.

**Responses:**

- **200**: Success - returns list of items
  ```json
  {
    "items": [],
    "total": 0
  }
  ```
- **400**: Bad request - invalid parameters
  ```json
  {
    "error": "Invalid request data"
  }
  ```
- **500**: Internal server error
  ```json
  {
    "error": "Internal server error"
  }
  ```

**Example (curl):**

```bash
curl -X GET \
  "http://localhost:5000/api/logs/recent"
```

---

### POST /api/logs/clear

**Summary:** REST API: Clear the in-memory log buffer.

**Request Body:**

```json
{
  "type": "object"
}
```

**Responses:**

- **200**: Operation completed successfully
  ```json
  {
    "success": true,
    "message": "Operation completed"
  }
  ```
- **400**: Bad request - invalid parameters
  ```json
  {
    "error": "Invalid request data"
  }
  ```
- **500**: Internal server error
  ```json
  {
    "error": "Internal server error"
  }
  ```

**Example (curl):**

```bash
curl -X POST \
  "http://localhost:5000/api/logs/clear" \
  -H "Content-Type: application/json" \
  -d '{}'
```

**Common Error Scenarios:**

- Missing required fields - returns 400
- Invalid JSON format - returns 400

---

## Environment

### GET /api/environment-variables

**Summary:** Get all environment variables with metadata.

**Responses:**

- **200**: Success - returns list of items
  ```json
  {
    "items": [],
    "total": 0
  }
  ```
- **400**: Bad request - invalid parameters
  ```json
  {
    "error": "Invalid request data"
  }
  ```
- **500**: Internal server error
  ```json
  {
    "error": "Internal server error"
  }
  ```

**Example (curl):**

```bash
curl -X GET \
  "http://localhost:5000/api/environment-variables"
```

---

### POST /api/environment-variables

**Summary:** Update environment variables.

**Request Body:**

```json
{
  "type": "object"
}
```

**Responses:**

- **200**: Operation completed successfully
  ```json
  {
    "success": true,
    "message": "Operation completed"
  }
  ```
- **400**: Bad request - invalid parameters
  ```json
  {
    "error": "Invalid request data"
  }
  ```
- **500**: Internal server error
  ```json
  {
    "error": "Internal server error"
  }
  ```

**Example (curl):**

```bash
curl -X POST \
  "http://localhost:5000/api/environment-variables" \
  -H "Content-Type: application/json" \
  -d '{}'
```

**Common Error Scenarios:**

- Missing required fields - returns 400
- Invalid JSON format - returns 400

---

### DELETE /api/environment-variables/<variable_name>

**Summary:** Delete an environment variable.

**Path Parameters:**

- `variable_name` (string, Required): Environment variable name

**Responses:**

- **200**: Deleted successfully
  ```json
  {
    "success": true,
    "message": "Deleted"
  }
  ```
- **400**: Bad request - invalid parameters
  ```json
  {
    "error": "Invalid request data"
  }
  ```
- **500**: Internal server error
  ```json
  {
    "error": "Internal server error"
  }
  ```

**Example (curl):**

```bash
curl -X DELETE \
  "http://localhost:5000/api/environment-variables/example"
```

**Common Error Scenarios:**

- Invalid ID format - returns 404

---

### GET /api/environment

**Summary:** Returns environment settings from the config.

**Responses:**

- **200**: Success - returns list of items
  ```json
  {
    "items": [],
    "total": 0
  }
  ```
- **400**: Bad request - invalid parameters
  ```json
  {
    "error": "Invalid request data"
  }
  ```
- **500**: Internal server error
  ```json
  {
    "error": "Internal server error"
  }
  ```

**Example (curl):**

```bash
curl -X GET \
  "http://localhost:5000/api/environment"
```

---

## System Utilities

### POST /api/utilities/celery/clear-queue

**Summary:** Clear all pending tasks from Celery queue.

**Request Body:**

```json
{
  "type": "object"
}
```

**Responses:**

- **200**: Operation completed successfully
  ```json
  {
    "success": true,
    "message": "Operation completed"
  }
  ```
- **400**: Bad request - invalid parameters
  ```json
  {
    "error": "Invalid request data"
  }
  ```
- **500**: Internal server error
  ```json
  {
    "error": "Internal server error"
  }
  ```

**Example (curl):**

```bash
curl -X POST \
  "http://localhost:5000/api/utilities/celery/clear-queue" \
  -H "Content-Type: application/json" \
  -d '{}'
```

**Common Error Scenarios:**

- Missing required fields - returns 400
- Invalid JSON format - returns 400

---

### POST /api/utilities/celery/purge-all

**Summary:** Purge all Celery tasks (pending, active, reserved).

**Request Body:**

```json
{
  "type": "object"
}
```

**Responses:**

- **200**: Operation completed successfully
  ```json
  {
    "success": true,
    "message": "Operation completed"
  }
  ```
- **400**: Bad request - invalid parameters
  ```json
  {
    "error": "Invalid request data"
  }
  ```
- **500**: Internal server error
  ```json
  {
    "error": "Internal server error"
  }
  ```

**Example (curl):**

```bash
curl -X POST \
  "http://localhost:5000/api/utilities/celery/purge-all" \
  -H "Content-Type: application/json" \
  -d '{}'
```

**Common Error Scenarios:**

- Missing required fields - returns 400
- Invalid JSON format - returns 400

---

### POST /api/utilities/celery/restart-workers

**Summary:** Restart Celery workers.

**Request Body:**

```json
{
  "type": "object"
}
```

**Responses:**

- **201**: Created successfully
  ```json
  {
    "success": true,
    "id": 1
  }
  ```
- **400**: Bad request - invalid parameters
  ```json
  {
    "error": "Invalid request data"
  }
  ```
- **500**: Internal server error
  ```json
  {
    "error": "Internal server error"
  }
  ```

**Example (curl):**

```bash
curl -X POST \
  "http://localhost:5000/api/utilities/celery/restart-workers" \
  -H "Content-Type: application/json" \
  -d '{}'
```

**Common Error Scenarios:**

- Agent already running - returns 400
- Invalid preferences format - returns 400
- System resources unavailable - returns 503
- Missing required fields - returns 400
- Invalid JSON format - returns 400

---

### GET /api/utilities/celery/status

**Summary:** Get Celery worker and task status.

**Responses:**

- **200**: Success - returns list of items
  ```json
  {
    "items": [],
    "total": 0
  }
  ```
- **400**: Bad request - invalid parameters
  ```json
  {
    "error": "Invalid request data"
  }
  ```
- **500**: Internal server error
  ```json
  {
    "error": "Internal server error"
  }
  ```

**Example (curl):**

```bash
curl -X GET \
  "http://localhost:5000/api/utilities/celery/status"
```

---

### POST /api/utilities/system/clear-redis

**Summary:** Clear Redis cache.

**Request Body:**

```json
{
  "type": "object"
}
```

**Responses:**

- **200**: Operation completed successfully
  ```json
  {
    "success": true,
    "message": "Operation completed"
  }
  ```
- **400**: Bad request - invalid parameters
  ```json
  {
    "error": "Invalid request data"
  }
  ```
- **500**: Internal server error
  ```json
  {
    "error": "Internal server error"
  }
  ```

**Example (curl):**

```bash
curl -X POST \
  "http://localhost:5000/api/utilities/system/clear-redis" \
  -H "Content-Type: application/json" \
  -d '{}'
```

**Common Error Scenarios:**

- Missing required fields - returns 400
- Invalid JSON format - returns 400

---

### POST /api/utilities/system/cleanup-temp

**Summary:** Cleanup temporary files.

**Request Body:**

```json
{
  "type": "object"
}
```

**Responses:**

- **200**: Operation completed successfully
  ```json
  {
    "success": true,
    "message": "Operation completed"
  }
  ```
- **400**: Bad request - invalid parameters
  ```json
  {
    "error": "Invalid request data"
  }
  ```
- **500**: Internal server error
  ```json
  {
    "error": "Internal server error"
  }
  ```

**Example (curl):**

```bash
curl -X POST \
  "http://localhost:5000/api/utilities/system/cleanup-temp" \
  -H "Content-Type: application/json" \
  -d '{}'
```

**Common Error Scenarios:**

- Missing required fields - returns 400
- Invalid JSON format - returns 400

---

### GET /api/utilities/system/health-check

**Summary:** Perform system health check.

**Responses:**

- **200**: Success - returns list of items
  ```json
  {
    "items": [],
    "total": 0
  }
  ```
- **400**: Bad request - invalid parameters
  ```json
  {
    "error": "Invalid request data"
  }
  ```
- **500**: Internal server error
  ```json
  {
    "error": "Internal server error"
  }
  ```

**Example (curl):**

```bash
curl -X GET \
  "http://localhost:5000/api/utilities/system/health-check"
```

---

### GET /api/utilities/debug/export-logs

**Summary:** Export all logs as a downloadable file.

**Responses:**

- **200**: Success - returns list of items
  ```json
  {
    "items": [],
    "total": 0
  }
  ```
- **400**: Bad request - invalid parameters
  ```json
  {
    "error": "Invalid request data"
  }
  ```
- **500**: Internal server error
  ```json
  {
    "error": "Internal server error"
  }
  ```

**Example (curl):**

```bash
curl -X GET \
  "http://localhost:5000/api/utilities/debug/export-logs"
```

---

### GET /api/utilities/debug/test-connections

**Summary:** Test all system connections.

**Responses:**

- **200**: Success - returns list of items
  ```json
  {
    "items": [],
    "total": 0
  }
  ```
- **400**: Bad request - invalid parameters
  ```json
  {
    "error": "Invalid request data"
  }
  ```
- **500**: Internal server error
  ```json
  {
    "error": "Internal server error"
  }
  ```

**Example (curl):**

```bash
curl -X GET \
  "http://localhost:5000/api/utilities/debug/test-connections"
```

---

### GET /api/utilities/debug/info

**Summary:** Get system debug information.

**Responses:**

- **200**: Success - returns list of items
  ```json
  {
    "items": [],
    "total": 0
  }
  ```
- **400**: Bad request - invalid parameters
  ```json
  {
    "error": "Invalid request data"
  }
  ```
- **500**: Internal server error
  ```json
  {
    "error": "Internal server error"
  }
  ```

**Example (curl):**

```bash
curl -X GET \
  "http://localhost:5000/api/utilities/debug/info"
```

---

## Hardware Monitoring

### GET /api/gpu-stats

**Summary:** REST API: Get GPU statistics.

**Responses:**

- **200**: Success - returns list of items
  ```json
  {
    "items": [],
    "total": 0
  }
  ```
- **400**: Bad request - invalid parameters
  ```json
  {
    "error": "Invalid request data"
  }
  ```
- **500**: Internal server error
  ```json
  {
    "error": "Internal server error"
  }
  ```

**Example (curl):**

```bash
curl -X GET \
  "http://localhost:5000/api/gpu-stats"
```

---

### GET /api/gpu-status

**Summary:** Check comprehensive GPU status including NVIDIA, CUDA, and Ollama.

**Responses:**

- **200**: Success - returns list of items
  ```json
  {
    "items": [],
    "total": 0
  }
  ```
- **400**: Bad request - invalid parameters
  ```json
  {
    "error": "Invalid request data"
  }
  ```
- **500**: Internal server error
  ```json
  {
    "error": "Internal server error"
  }
  ```

**Example (curl):**

```bash
curl -X GET \
  "http://localhost:5000/api/gpu-status"
```

**Common Error Scenarios:**

- Validation error: Request failed: HTTPConnectionPool(host='localhost', port=5000): Read timed out. (read timeout=10)

---

## Scheduling

### GET /api/schedules

**Summary:** Get all schedules.

**Query Parameters:**

- `limit` (integer, Optional): Maximum number of results
- `offset` (integer, Optional): Number of results to skip

**Responses:**

- **200**: Success - returns list of items
  ```json
  {
    "items": [],
    "total": 0
  }
  ```
- **400**: Bad request - invalid parameters
  ```json
  {
    "error": "Invalid request data"
  }
  ```
- **500**: Internal server error
  ```json
  {
    "error": "Internal server error"
  }
  ```

**Example (curl):**

```bash
curl -X GET \
  "http://localhost:5000/api/schedules"
```

**Workflow Context:** Manage automated agent execution. Create and manage recurring agent runs.

---

### POST /api/schedules

**Summary:** Create a new schedule.

**Request Body:**

```json
{
  "type": "object",
  "properties": {
    "name": {
      "type": "string"
    },
    "frequency": {
      "type": "string",
      "enum": [
        "manual",
        "daily",
        "weekly",
        "monthly"
      ]
    },
    "enabled": {
      "type": "boolean"
    }
  },
  "required": [
    "name",
    "frequency"
  ]
}
```

**Responses:**

- **200**: Operation completed successfully
  ```json
  {
    "success": true,
    "message": "Operation completed"
  }
  ```
- **400**: Bad request - invalid parameters
  ```json
  {
    "error": "Invalid request data"
  }
  ```
- **500**: Internal server error
  ```json
  {
    "error": "Internal server error"
  }
  ```

**Example (curl):**

```bash
curl -X POST \
  "http://localhost:5000/api/schedules" \
  -H "Content-Type: application/json" \
  -d '{"name": "example_name", "frequency": "manual", "enabled": true}'
```

**Workflow Context:** Manage automated agent execution. Create and manage recurring agent runs.

**Common Error Scenarios:**

- Missing required fields - returns 400
- Invalid JSON format - returns 400

---

### PUT /api/schedules/<int:schedule_id>

**Summary:** Update an existing schedule.

**Path Parameters:**

- `schedule_id` (integer, Required): Schedule identifier

**Request Body:**

```json
{
  "type": "object",
  "properties": {
    "name": {
      "type": "string"
    },
    "frequency": {
      "type": "string",
      "enum": [
        "manual",
        "daily",
        "weekly",
        "monthly"
      ]
    },
    "enabled": {
      "type": "boolean"
    }
  },
  "required": [
    "name",
    "frequency"
  ]
}
```

**Responses:**

- **200**: Updated successfully
  ```json
  {
    "success": true,
    "message": "Updated"
  }
  ```
- **400**: Bad request - invalid parameters
  ```json
  {
    "error": "Invalid request data"
  }
  ```
- **500**: Internal server error
  ```json
  {
    "error": "Internal server error"
  }
  ```

**Example (curl):**

```bash
curl -X PUT \
  "http://localhost:5000/api/schedules/1" \
  -H "Content-Type: application/json" \
  -d '{"name": "example_name", "frequency": "manual", "enabled": true}'
```

**Workflow Context:** Manage automated agent execution. Create and manage recurring agent runs.

**Common Error Scenarios:**

- Invalid ID format - returns 404
- Missing required fields - returns 400
- Invalid JSON format - returns 400

---

### DELETE /api/schedules/<int:schedule_id>

**Summary:** Delete a schedule.

**Path Parameters:**

- `schedule_id` (integer, Required): Schedule identifier

**Responses:**

- **200**: Deleted successfully
  ```json
  {
    "success": true,
    "message": "Deleted"
  }
  ```
- **400**: Bad request - invalid parameters
  ```json
  {
    "error": "Invalid request data"
  }
  ```
- **500**: Internal server error
  ```json
  {
    "error": "Internal server error"
  }
  ```

**Example (curl):**

```bash
curl -X DELETE \
  "http://localhost:5000/api/schedules/1"
```

**Workflow Context:** Manage automated agent execution. Create and manage recurring agent runs.

**Common Error Scenarios:**

- Invalid ID format - returns 404

---

### POST /api/schedules/<int:schedule_id>/toggle

**Summary:** Toggle schedule enabled/disabled status.

**Path Parameters:**

- `schedule_id` (integer, Required): Schedule identifier

**Request Body:**

```json
{
  "type": "object",
  "properties": {
    "name": {
      "type": "string"
    },
    "frequency": {
      "type": "string",
      "enum": [
        "manual",
        "daily",
        "weekly",
        "monthly"
      ]
    },
    "enabled": {
      "type": "boolean"
    }
  },
  "required": [
    "name",
    "frequency"
  ]
}
```

**Responses:**

- **200**: Operation completed successfully
  ```json
  {
    "success": true,
    "message": "Operation completed"
  }
  ```
- **400**: Bad request - invalid parameters
  ```json
  {
    "error": "Invalid request data"
  }
  ```
- **500**: Internal server error
  ```json
  {
    "error": "Internal server error"
  }
  ```

**Example (curl):**

```bash
curl -X POST \
  "http://localhost:5000/api/schedules/1/toggle" \
  -H "Content-Type: application/json" \
  -d '{"name": "example_name", "frequency": "manual", "enabled": true}'
```

**Workflow Context:** Manage automated agent execution. Create and manage recurring agent runs.

**Common Error Scenarios:**

- Invalid ID format - returns 404
- Missing required fields - returns 400
- Invalid JSON format - returns 400

---

### POST /api/schedules/<int:schedule_id>/run

**Summary:** Run a schedule immediately.

**Path Parameters:**

- `schedule_id` (integer, Required): Schedule identifier

**Request Body:**

```json
{
  "type": "object",
  "properties": {
    "name": {
      "type": "string"
    },
    "frequency": {
      "type": "string",
      "enum": [
        "manual",
        "daily",
        "weekly",
        "monthly"
      ]
    },
    "enabled": {
      "type": "boolean"
    }
  },
  "required": [
    "name",
    "frequency"
  ]
}
```

**Responses:**

- **200**: Operation completed successfully
  ```json
  {
    "success": true,
    "message": "Operation completed"
  }
  ```
- **400**: Bad request - invalid parameters
  ```json
  {
    "error": "Invalid request data"
  }
  ```
- **500**: Internal server error
  ```json
  {
    "error": "Internal server error"
  }
  ```

**Example (curl):**

```bash
curl -X POST \
  "http://localhost:5000/api/schedules/1/run" \
  -H "Content-Type: application/json" \
  -d '{"name": "example_name", "frequency": "manual", "enabled": true}'
```

**Workflow Context:** Manage automated agent execution. Create and manage recurring agent runs.

**Common Error Scenarios:**

- Invalid ID format - returns 404
- Missing required fields - returns 400
- Invalid JSON format - returns 400

---

## Web UI (V2)

### GET /v2/

**Summary:** No description available

**Description:** 

**Responses:**

- **200**: Success - returns list of items
  ```json
  {
    "items": [],
    "total": 0
  }
  ```
- **400**: Bad request - invalid parameters
  ```json
  {
    "error": "Invalid request data"
  }
  ```
- **500**: Internal server error
  ```json
  {
    "error": "Internal server error"
  }
  ```

**Example (curl):**

```bash
curl -X GET \
  "http://localhost:5000/v2/"
```

---

### GET /v2/page/<string:page_name>

**Summary:** Serves the HTML content for different pages of the V2 UI.

**Path Parameters:**

- `page_name` (string, Required): Page name for UI routing

**Responses:**

- **200**: Success - returns requested item
  ```json
  {
    "id": 1,
    "data": "..."
  }
  ```
- **404**: Item not found
  ```json
  {
    "error": "Item not found"
  }
  ```
- **400**: Bad request - invalid parameters
  ```json
  {
    "error": "Invalid request data"
  }
  ```
- **500**: Internal server error
  ```json
  {
    "error": "Internal server error"
  }
  ```

**Example (curl):**

```bash
curl -X GET \
  "http://localhost:5000/v2/page/example"
```

**Common Error Scenarios:**

- Invalid ID format - returns 404

---
