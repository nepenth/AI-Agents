# Knowledge Base Agent API Documentation

This document outlines the API endpoints and WebSocket events for the Knowledge Base Agent application.

## Table of Contents
1.  [Guiding Principles](#guiding-principles)
2.  [HTTP API Endpoints](#http-api-endpoints)
    -   [Page-Serving Routes](#page-serving-routes)
    -   [Data API Routes](#data-api-routes)
        -   [Chat Management](#chat-management)
        -   [Knowledge Base & Content](#knowledge-base-content)
        -   [Agent & Environment](#agent-environment)
        -   [Scheduling](#scheduling)
        -   [Logging](#logging)
        -   [System & Hardware](#system-hardware)
3.  [WebSocket (Socket.IO) Events](#websocket-socketio-events)
    -   [Client to Server](#client-to-server)
    -   [Server to Client](#server-to-client)

---

## 1. Guiding Principles

-   **REST-First Architecture**: REST APIs are the PRIMARY interface for all operations and state management
-   **SocketIO as Notification Layer**: SocketIO serves as a PURE NOTIFICATION LAYER for real-time updates and live streaming
-   **Shared Business Logic**: All operations use centralized business logic functions that both REST and SocketIO call
-   **Consistent Behavior**: Both REST and SocketIO endpoints produce identical results through shared functions
-   **Comprehensive Fallbacks**: Every SocketIO operation has a REST alternative for reliability
-   **Clean Separation**: HTML routes in `web.py` serve only HTML content. JSON APIs in `api/routes.py` serve only JSON data.
-   **External Integration Friendly**: All functionality accessible via standard REST APIs for automation and third-party tools

### Hybrid Architecture Benefits (2025-07-08)

The system now implements a mature hybrid approach:
- **🎯 REST APIs**: Primary interface for CRUD operations, state management, and external integrations
- **⚡ SocketIO**: Real-time notifications, live streaming, and immediate UI updates
- **🔄 Shared Logic**: Centralized business functions ensure consistent behavior across both interfaces
- **🛡️ Reliability**: REST fallbacks available when SocketIO connections fail
- **🧪 Testability**: All functionality testable through standard HTTP endpoints
- **🔌 Integration**: External tools can use REST APIs without SocketIO complexity

### Architecture Implementation

All major operations follow this pattern:
```python
def operation_name(params, socketio_emit=True):
    """Shared business logic for operation. Used by both REST and SocketIO."""
    # Perform actual business logic
    result = perform_operation(params)
    
    # Emit SocketIO notifications if requested
    if socketio_emit:
        socketio.emit('operation_result', result)
    
    return {'success': True/False, 'data': result, 'message': 'status'}

# REST endpoint (primary interface)
@bp.route('/api/operation', methods=['POST'])
def rest_operation():
    result = operation_name(request.json, socketio_emit=False)
    return jsonify(result)

# SocketIO handler (notification layer)
@socketio.on('operation_request')
def socketio_operation(data):
    operation_name(data, socketio_emit=True)  # Same logic + notifications
```

---

## 2. HTTP API Endpoints

### Page-Serving Routes
These routes deliver HTML content for both the V1 and V2 applications.

| Method | Path                          | Description                                                                                              |
| :----- | :---------------------------- | :------------------------------------------------------------------------------------------------------- |
| `GET`  | `/`                           | Serves the main V1 `index.html` page.                                                                    |
| `GET`  | `/v2/`                        | Serves the main `_layout.html` which bootstraps the V2 SPA.                                              |
| `GET`  | `/v2/page/<page_name>`        | Serves pre-rendered HTML content for a specific V2 view (e.g., `index`, `chat`, `kb`, `logs`).             |
| `GET`  | `/item/<int:item_id>`         | Serves the HTML detail page for a Knowledge Base item. For JSON data, use `/api/items/<id>`.             |
| `GET`  | `/synthesis/<int:synthesis_id>`| Serves the HTML detail page for a Synthesis item. For JSON data, use `/api/synthesis/<id>`.              |
| `GET`  | `/chat`                       | Serves the HTML partial for the chat interface.                                                          |
| `GET`  | `/schedule`                   | Serves the HTML partial for the schedule page.                                                           |
| `GET`  | `/environment`                | Serves the HTML partial for the environment settings page.                                               |
| `GET`  | `/logs`                       | Serves the HTML partial for the past logs page.                                                          |
| `GET`  | `/syntheses`                  | Serves the page for the list of all syntheses.                                                           |

### Data API Routes

#### Chat Management

| Method   | Path                               | Description                                                     |
| :------- | :--------------------------------- | :-------------------------------------------------------------- |
| `GET`    | `/api/chat/models`                 | Returns the list of available chat models from the config.      |
| `POST`   | `/api/chat`                        | Handles a chat query. (Primary Chat Endpoint)                   |
| `POST`   | `/api/chat/legacy`                 | Legacy chat endpoint for backward compatibility.                |
| `POST`   | `/api/chat/enhanced`               | Enhanced chat endpoint that persists session data.              |
| `GET`    | `/api/chat/models/available`       | Gets available chat models from the `ChatManager`.              |
| `GET`    | `/api/chat/sessions`               | Gets all chat sessions.                                         |
| `POST`   | `/api/chat/sessions`               | Creates a new chat session.                                     |
| `GET`    | `/api/chat/sessions/<session_id>`  | Gets a specific chat session with messages.                     |
| `DELETE` | `/api/chat/sessions/<session_id>`  | Deletes a chat session and its messages.                        |
| `POST`   | `/api/chat/sessions/<id>/archive`  | Archives or un-archives a chat session.                         |

#### Knowledge Base & Content

| Method | Path                    | Description                                                                                         |
| :----- | :---------------------- | :-------------------------------------------------------------------------------------------------- |
| `GET`  | `/api/kb/all`           | Returns a JSON object with all KB items and syntheses for the table of contents.                    |
| `GET`  | `/api/items/<int:item_id>` | **NEW**: Returns detailed JSON data for a specific knowledge base item.                          |
| `GET`  | `/api/synthesis/<int:synthesis_id>` | **NEW**: Returns detailed JSON data for a specific synthesis document.                    |
| `GET`  | `/api/syntheses`        | Returns a detailed JSON list of all synthesis documents.                                            |
| `GET`  | `/api/synthesis`        | Returns a summary list of all synthesis documents. (Note: different from `/api/syntheses`)          |
| `GET`  | `/media/<path:path>`    | Serves media files (images, videos) from the configured knowledge base directory.                   |

#### Agent & Environment

| Method   | Path                                  | Description                                                                        |
| :------- | :------------------------------------ | :--------------------------------------------------------------------------------- |
| `GET`    | `/api/agent/status`                   | **NEW**: Returns current agent status and state from database.                     |
| `POST`   | `/api/agent/start`                    | **NEW**: Starts the agent with specified preferences (REST alternative to SocketIO). |
| `POST`   | `/api/agent/stop`                     | **NEW**: Stops the currently running agent (REST alternative to SocketIO).        |
| `GET`    | `/api/preferences`                    | **NEW**: Gets current user preferences from configuration.                         |
| `POST`   | `/api/preferences`                    | **NEW**: Validates and saves user preferences.                                     |
| `GET`    | `/api/system/info`                    | **NEW**: Returns comprehensive system information (platform, memory, CPU, GPU).   |
| `GET`    | `/api/environment`                    | Returns a JSON object with non-sensitive environment settings from the app config. |
| `GET`    | `/api/environment-variables`          | Gets all environment variables with metadata.                                      |
| `POST`   | `/api/environment-variables`          | Updates one or more environment variables.                                         |
| `DELETE` | `/api/environment-variables/<var>`    | Deletes a specific environment variable.                                           |

#### Scheduling

| Method         | Path                                 | Description                                                         |
| :------------- | :----------------------------------- | :------------------------------------------------------------------ |
| `GET` / `POST` | `/api/schedule`                      | **V1 LEGACY**: Simulates schedule handling for backward compatibility. |
| `GET` / `POST` | `/api/v2/schedule`                   | **V2**: Gets or sets the agent schedule from the database.          |
| `GET`          | `/api/schedules`                     | Gets all defined schedule objects from the database.                |
| `POST`         | `/api/schedules`                     | Creates a new schedule object.                                      |
| `PUT`          | `/api/schedules/<int:id>`            | Updates an existing schedule.                                       |
| `DELETE`       | `/api/schedules/<int:id>`            | Deletes a schedule.                                                 |
| `POST`         | `/api/schedules/<int:id>/toggle`     | Toggles a schedule's enabled status.                                |
| `POST`         | `/api/schedules/<int:id>/run`        | Triggers an immediate run of a schedule.                            |
| `GET`          | `/api/schedule-history`              | Gets the execution history for all schedules.                       |
| `DELETE`       | `/api/schedule-runs/<int:id>`        | Deletes a specific run from the history.                            |

#### Logging

| Method | Path                  | Description                                            |
| :----- | :-------------------- | :----------------------------------------------------- |
| `GET`  | `/api/logs/files`     | Returns a JSON array of available `.log` file names.   |
| `GET`  | `/api/logs/<filename>`| Gets the content of a specific log file.               |
| `GET`  | `/api/logs/recent`    | **NEW**: Gets recent log messages from in-memory buffer (REST alternative to SocketIO). |
| `POST` | `/api/logs/clear`     | **NEW**: Clears the in-memory log buffer (REST alternative to SocketIO). |
| `POST` | `/api/logs/delete-all`| Deletes all `.log` files from the log directory.       |


#### System & Hardware

| Method | Path                        | Description                                                              |
| :----- | :-------------------------- | :----------------------------------------------------------------------- |
| `GET`  | `/api/gpu-stats`            | REST API fallback for GPU statistics.                                    |
| `GET`  | `/api/gpu-status`           | Checks comprehensive GPU status (NVIDIA, CUDA, Ollama).                  |
| `GET`  | `/api/hardware-detection`   | Gets detected hardware information (CPU, GPU, RAM).                      |
| `POST` | `/api/ollama-optimization`  | Generates and optionally applies Ollama optimization environment variables. |

---

## 3. WebSocket (Socket.IO) Events

### Client to Server
Events emitted by the client to the server.

| Event Name                              | Payload                   | Description                                                              |
| :-------------------------------------- | :------------------------ | :----------------------------------------------------------------------- |
| `connect`                               | `None`                    | A new client connects.                                                   |
| `disconnect`                            | `None`                    | A client disconnects.                                                    |
| `request_initial_status_and_git_config` | `None`                    | Client requests the current agent status and git configuration on load.  |
| `request_initial_logs`                  | `None`                    | Client requests the log buffer upon connecting.                          |
| `clear_server_logs`                     | `None`                    | Requests that the server clears its in-memory log buffer.                |
| `run_agent`                             | `{ preferences: object }` | Requests the server to start an agent run with specified preferences.    |
| `stop_agent`                            | `None`                    | Requests the server to gracefully stop the currently running agent.      |
| `request_gpu_stats`                     | `None`                    | Client requests an immediate update of GPU statistics.                   |

### Server to Client
Events emitted by the server to the client.

| Event Name                  | Payload                                                               | Description                                                                                   |
| :-------------------------- | :-------------------------------------------------------------------- | :-------------------------------------------------------------------------------------------- |
| `agent_status`              | `{ is_running: bool, ...etc }`                                        | Sent on connect. Contains the full agent state from the `AgentState` database table.          |
| `agent_status_update`       | `{ is_running: bool, current_phase_id: string, ...etc }`              | Sent whenever the agent's state changes. Contains the full, updated agent state object.       |
| `agent_run_completed`       | `{ summary_message: string, plan_statuses: object }`                  | Sent when the agent finishes a run (successfully or with errors).                             |
| `agent_error`               | `{ message: string }`                                                 | Sent if an unhandled exception occurs during an agent run.                                    |
| `initial_logs`              | `{ logs: Array<object> }`                                             | Sent on connect, providing the buffer of recent logs.                                         |
| `logs_cleared`              | `None`                                                                | Notifies clients that the log buffer has been cleared.                                        |
| `log`                       | `{ message: string, level: string }`                                  | A new log message.                                                                            |
| `git_config_status`         | `{ auto_commit: bool, auto_push: bool }`                              | Sent on connect to inform the client of the Git auto-commit/push settings.                    |
| `gpu_stats`                 | `{ gpus: Array<object> }` or `{ error: string }`                      | Contains an array of GPU statistics or an error message.                                      |
| `info`                      | `{ message: string }`                                                 | Generic informational message for the user.                                                   |
| `phase_update`              | `{ phase_id: string, status: string, message: string, ...etc }`       | Informs the client about the status of a specific phase of the execution plan.                |

</rewritten_file> 